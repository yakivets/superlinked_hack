"""Per-meeting RAG chat: chunking, related-meeting selection, and retrieval."""

import pytest

from app import chat
from app.models import Notes, SpeakerTurn
from app.store import Store


@pytest.fixture(autouse=True)
def clear_cache():
    chat._cache.clear()
    yield
    chat._cache.clear()


class ChatRouter:
    """Embeds on word overlap so retrieval is deterministic and checkable."""

    VOCAB = ["payment", "onboarding", "budget", "hiring", "monday"]

    def __init__(self):
        self.prompts = []

    async def embed(self, texts):
        out = []
        for t in texts:
            low = t.lower()
            out.append([1.0 if w in low else 0.0 for w in self.VOCAB])
        return out

    async def rerank(self, query, docs):
        return None      # exercise the no-reranker path

    async def chat_sie(self, model, prompt, max_tokens=1500):
        self.prompts.append(prompt)
        return "answered"


def make_meeting(store, title, turns, summary="", embedding=None):
    mid = store.create_meeting(title, "general")
    store.update_meeting(
        mid,
        transcript=[SpeakerTurn(s, t) for s, t in turns],
        notes=Notes(summary=summary, decisions=[], open_questions=[]),
        embedding=embedding or [1.0, 0.0, 0.0],
        status="done",
    )
    return mid


def test_chunk_meeting_includes_summary_and_transcript():
    meeting = {
        "id": "m1", "title": "Sync",
        "notes": {"summary": "we shipped"},
        "transcript": [{"speaker": "Speaker 1", "text": "hello there"}],
    }
    kinds = [p["kind"] for p in chat.chunk_meeting(meeting)]
    assert "summary" in kinds and "transcript" in kinds


def test_chunk_meeting_splits_long_transcripts():
    meeting = {
        "id": "m1", "title": "Long", "notes": {},
        "transcript": [{"speaker": "S", "text": "x" * 300} for _ in range(6)],
    }
    assert len(chat.chunk_meeting(meeting)) > 1


def test_chunk_meeting_handles_a_meeting_with_no_transcript():
    assert chat.chunk_meeting({"id": "m", "title": "t", "notes": {}, "transcript": []}) == []


def test_related_meetings_exclude_self_and_the_unrelated(tmp_path):
    store = Store(str(tmp_path / "c.db"))
    a = make_meeting(store, "A", [("S", "payment")], embedding=[1.0, 0.0])
    near = make_meeting(store, "Near", [("S", "payment")], embedding=[1.0, 0.0])
    far = make_meeting(store, "Far", [("S", "other")], embedding=[0.0, 1.0])

    related = chat.related_meeting_ids(store, a)
    assert near in related
    assert far not in related and a not in related


@pytest.mark.asyncio
async def test_answer_pulls_context_from_related_meetings(tmp_path):
    store, router = Store(str(tmp_path / "c.db")), ChatRouter()
    main = make_meeting(store, "Main", [("S", "the payment bug is open")],
                        embedding=[1.0, 0.0])
    make_meeting(store, "Related", [("S", "we fixed the payment bug on monday")],
                 embedding=[1.0, 0.0])

    result = await chat.answer(store, router, main, "what about the payment bug?")

    assert result["answer"] == "answered"
    assert [r["title"] for r in result["related"]] == ["Related"]
    # The related meeting's content must actually reach the model.
    assert "monday" in router.prompts[0].lower()


@pytest.mark.asyncio
async def test_answer_is_honest_when_there_is_no_transcript(tmp_path):
    store, router = Store(str(tmp_path / "c.db")), ChatRouter()
    mid = store.create_meeting("Empty", "general")
    result = await chat.answer(store, router, mid, "anything?")
    assert "no transcript" in result["answer"].lower()


@pytest.mark.asyncio
async def test_answer_404s_on_a_missing_meeting(tmp_path):
    store, router = Store(str(tmp_path / "c.db")), ChatRouter()
    result = await chat.answer(store, router, "nope", "hi")
    assert "does not exist" in result["answer"]


@pytest.mark.asyncio
async def test_history_is_passed_to_the_model(tmp_path):
    store, router = Store(str(tmp_path / "c.db")), ChatRouter()
    mid = make_meeting(store, "M", [("S", "budget talk")])
    await chat.answer(store, router, mid, "and then?",
                      [{"role": "user", "content": "who owns the budget"}])
    assert "who owns the budget" in router.prompts[0]


@pytest.mark.asyncio
async def test_passage_cache_is_reused_then_invalidated(tmp_path):
    store, router = Store(str(tmp_path / "c.db")), ChatRouter()
    mid = make_meeting(store, "M", [("S", "payment")])

    await chat.answer(store, router, mid, "q1")
    assert mid in chat._cache
    chat.invalidate(mid)
    assert mid not in chat._cache
