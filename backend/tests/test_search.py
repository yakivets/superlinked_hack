from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import Entities, Notes, SpeakerTurn
from app.search import cosine, fusion_score, search_meetings
from app.store import Store


def test_cosine():
    assert abs(cosine([1, 0], [1, 0]) - 1.0) < 1e-9
    assert abs(cosine([1, 0], [0, 1])) < 1e-9


def test_fusion_recency_prefers_new():
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=30)).isoformat()
    new = now.isoformat()
    s_old = fusion_score(0.8, old, "payment", [], now=now)
    s_new = fusion_score(0.8, new, "payment", [], now=now)
    assert s_new > s_old


def test_fusion_topic_overlap_bonus():
    now = datetime.now(timezone.utc)
    with_topic = fusion_score(0.5, now.isoformat(), "payment bug", ["payments"], now=now)
    without = fusion_score(0.5, now.isoformat(), "payment bug", ["lunch"], now=now)
    assert with_topic > without


class EmbedRouter:
    async def embed(self, texts):
        return [[1.0, 0.0]]

    async def rerank(self, query, docs):
        return None


async def test_search_meetings_ranks_by_similarity(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    a = store.create_meeting("about payments")
    b = store.create_meeting("about lunch")
    notes = Notes(summary="x", decisions=[], open_questions=[])
    ents = Entities(action_items=[], people=[], dates=[], topics=[])
    store.update_meeting(a, status="done", embedding=[1.0, 0.0], notes=notes, entities=ents)
    store.update_meeting(b, status="done", embedding=[0.0, 1.0], notes=notes, entities=ents)
    results = await search_meetings(store, EmbedRouter(), "payments", k=2)
    assert results[0]["id"] == a
    assert results[0]["score"] > results[1]["score"]


class RerankInvertingRouter:
    async def embed(self, texts):
        return [[1.0, 0.0]]

    async def rerank(self, query, docs):
        # Deliberately inverts the cosine ordering: the first doc (highest
        # cosine similarity) gets the lowest rerank score and vice versa.
        return [0.1, 0.9][: len(docs)]


async def test_search_meetings_uses_rerank_scores_when_present(tmp_path):
    store = Store(str(tmp_path / "s3.db"))
    a = store.create_meeting("about payments")
    b = store.create_meeting("about lunch")
    notes = Notes(summary="x", decisions=[], open_questions=[])
    ents = Entities(action_items=[], people=[], dates=[], topics=[])
    store.update_meeting(a, status="done", embedding=[1.0, 0.0], notes=notes, entities=ents)
    store.update_meeting(b, status="done", embedding=[0.0, 1.0], notes=notes, entities=ents)
    # By cosine alone, "a" ranks first (matches the query vector exactly).
    # The rerank scores invert that: "b" should now win.
    results = await search_meetings(store, RerankInvertingRouter(), "payments", k=2)
    assert results[0]["id"] == b
    assert results[0]["score"] > results[1]["score"]


def _seeded_client(tmp_path, router):
    store = Store(str(tmp_path / "search_api.db"))
    app.state.store = store
    app.state.router = router
    a = store.create_meeting("about payments")
    b = store.create_meeting("about lunch")
    notes = Notes(summary="x", decisions=[], open_questions=[])
    ents = Entities(action_items=[], people=[], dates=[], topics=[])
    store.update_meeting(a, status="done", embedding=[1.0, 0.0], notes=notes, entities=ents)
    store.update_meeting(b, status="done", embedding=[0.0, 1.0], notes=notes, entities=ents)
    return TestClient(app), a, b


def test_search_route_returns_top_result(tmp_path):
    client, a, _b = _seeded_client(tmp_path, EmbedRouter())
    r = client.get("/search", params={"q": "payments"})
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert body["results"][0]["id"] == a


def test_search_route_missing_query_returns_400(tmp_path):
    client, _a, _b = _seeded_client(tmp_path, EmbedRouter())
    assert client.get("/search").status_code == 400
    assert client.get("/search", params={"q": ""}).status_code == 400
