"""Meetings are titled from their content, once there is content to title from."""

import pytest

from app import pipeline
from app.models import Entities, Notes, SpeakerTurn
from app.store import Store
from tests.test_pipeline import FakeRouter, tiny_wav


class TitlingRouter(FakeRouter):
    def __init__(self, title="Payment bug blocking release"):
        super().__init__()
        self.title = title
        self.title_prompts = []

    async def chat_sie(self, model, prompt, max_tokens=1500):
        self.title_prompts.append(prompt)
        return self.title


class FailingTitleRouter(FakeRouter):
    async def chat_sie(self, model, prompt, max_tokens=1500):
        raise RuntimeError("model down")


# --- cleaning --------------------------------------------------------------

def test_quotes_and_trailing_stops_are_stripped():
    assert pipeline._clean_title('"Payment bug fix."') == "Payment bug fix"
    assert pipeline._clean_title("'Q3 budget'") == "Q3 budget"


def test_only_the_first_line_is_used():
    assert pipeline._clean_title("Payment bug fix\nsome rambling") == "Payment bug fix"


def test_overlong_titles_are_truncated():
    assert len(pipeline._clean_title("x" * 200)) == pipeline.MAX_TITLE_CHARS


def test_empty_output_yields_empty_not_a_crash():
    assert pipeline._clean_title("") == ""
    assert pipeline._clean_title(None) == ""


# --- pipeline behaviour ----------------------------------------------------

@pytest.mark.asyncio
async def test_placeholder_titles_are_replaced(tmp_path):
    store, router = Store(str(tmp_path / "t.db")), TitlingRouter()
    mid = store.create_meeting("Device meeting")
    await pipeline.process_meeting(store, router, mid, tiny_wav())
    assert store.get_meeting(mid)["title"] == "Payment bug blocking release"


@pytest.mark.asyncio
async def test_a_title_someone_chose_is_left_alone(tmp_path):
    store, router = Store(str(tmp_path / "t.db")), TitlingRouter()
    mid = store.create_meeting("Board review with Acme")
    await pipeline.process_meeting(store, router, mid, tiny_wav())
    assert store.get_meeting(mid)["title"] == "Board review with Acme"
    assert router.title_prompts == [], "should not spend a call on a named meeting"


@pytest.mark.asyncio
async def test_a_failed_title_does_not_fail_the_meeting(tmp_path):
    store, router = Store(str(tmp_path / "t.db")), FailingTitleRouter()
    mid = store.create_meeting("Device meeting")
    await pipeline.process_meeting(store, router, mid, tiny_wav())
    m = store.get_meeting(mid)
    assert m["status"] == "done"
    assert m["title"] == "Device meeting"


@pytest.mark.asyncio
async def test_an_empty_title_leaves_the_placeholder(tmp_path):
    store, router = Store(str(tmp_path / "t.db")), TitlingRouter(title="   ")
    mid = store.create_meeting("Device meeting")
    await pipeline.process_meeting(store, router, mid, tiny_wav())
    assert store.get_meeting(mid)["title"] == "Device meeting"


@pytest.mark.asyncio
async def test_the_new_title_is_what_gets_embedded(tmp_path):
    """The title feeds the embedding, so it must be set before embedding runs -
    otherwise search and the graph index the word 'Device'."""
    store, router = Store(str(tmp_path / "t.db")), TitlingRouter()
    embedded = []

    async def embed(texts):
        embedded.extend(texts)
        return [[0.5, 0.5] for _ in texts]

    router.embed = embed
    mid = store.create_meeting("Device meeting")
    await pipeline.process_meeting(store, router, mid, tiny_wav())

    assert embedded and embedded[0].startswith("Payment bug blocking release")
