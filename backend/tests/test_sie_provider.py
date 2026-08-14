import json

import httpx
import pytest

from app.models import Entities, ActionItem, Notes
from app.sie_provider import SIEProvider


def make_provider(handler, api_key="test-key"):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://fake:8080")
    return SIEProvider(client=client, api_key=api_key)


async def test_embed_uses_encode_endpoint():
    def handler(request):
        assert request.url.path == "/v1/encode/Qwen/Qwen3-Embedding-4B"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body == {"items": [{"text": "a"}, {"text": "b"}]}
        return httpx.Response(
            200,
            json={
                "items": [
                    {"dense": {"dims": 2, "dtype": "float32", "values": [0.1, 0.2]}},
                    {"dense": {"dims": 2, "dtype": "float32", "values": [0.3, 0.4]}},
                ]
            },
        )

    p = make_provider(handler)
    assert await p.embed(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]


async def test_rerank_uses_score_endpoint():
    def handler(request):
        assert request.url.path == "/v1/score/Qwen/Qwen3-Reranker-0.6B"
        body = json.loads(request.content)
        assert body == {"query": {"text": "q"}, "items": [{"text": "d0"}, {"text": "d1"}]}
        return httpx.Response(
            200,
            json={
                "scores": [
                    {"item_id": "item-1", "rank": 1, "score": 0.1},
                    {"item_id": "item-0", "rank": 0, "score": 0.9},
                ]
            },
        )

    p = make_provider(handler)
    assert await p.rerank("q", ["d0", "d1"]) == [0.9, 0.1]


async def test_generate_notes_uses_chat():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "Qwen/Qwen3.5-4B"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"summary": "s", "decisions": [], "open_questions": []}'}}]},
        )

    p = make_provider(handler)
    assert await p.generate_notes("Speaker 1: hi") == Notes(summary="s", decisions=[], open_questions=[])


async def test_extract_uses_chat_completions_not_gliner():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "Qwen/Qwen3.5-4B"
        content = json.dumps(
            {
                "action_items": [{"text": "fix the payment bug", "owner": "Sarah"}],
                "people": ["Sarah"],
                "dates": ["Monday"],
                "topics": ["payments"],
            }
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    p = make_provider(handler)
    e = await p.extract("Sarah will fix the payment bug by Monday")
    assert e == Entities(
        action_items=[ActionItem(text="fix the payment bug", owner="Sarah")],
        people=["Sarah"],
        dates=["Monday"],
        topics=["payments"],
    )


async def test_transcribe_not_implemented():
    p = make_provider(lambda request: httpx.Response(500))
    with pytest.raises(NotImplementedError):
        await p.transcribe(b"RIFFfakewav")


@pytest.mark.live
async def test_live_embed_smoke():
    p = SIEProvider(client=None, api_key=None)  # real settings
    vecs = await p.embed(["hello meeting"])
    assert len(vecs) == 1 and len(vecs[0]) == 2560
