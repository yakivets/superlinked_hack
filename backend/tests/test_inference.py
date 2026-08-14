import base64
import json

import httpx
import pytest

from app.inference import CloudProvider, InferenceRouter
from app.models import Notes, SpeakerTurn


def sse(chunks):
    lines = []
    for c in chunks:
        payload = {"choices": [{"delta": {"content": c}, "finish_reason": None}]}
        lines.append(f"data: {json.dumps(payload)}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def make_provider(handler):
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="https://fake")
    return CloudProvider(client=client, api_key="k")


async def test_transcribe_parses_streamed_speaker_turns():
    def handler(request):
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["model"] == "qwen3.5-omni-flash"
        return httpx.Response(
            200,
            content=sse(["Speaker 1: Hello.\n", "Speaker 2: Hi."]),
            headers={"content-type": "text/event-stream"},
        )

    p = make_provider(handler)
    turns = await p.transcribe(b"RIFFfakewav")
    assert turns == [SpeakerTurn("Speaker 1", "Hello."), SpeakerTurn("Speaker 2", "Hi.")]


async def test_generate_notes_parses_json():
    def handler(request):
        content = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "reasoning_content": "thinking...",
                            "content": '{"summary": "s", "decisions": ["d"], "open_questions": []}',
                        }
                    }
                ]
            }
        )
        return httpx.Response(200, content=content, headers={"content-type": "application/json"})

    p = make_provider(handler)
    notes = await p.generate_notes("Speaker 1: we decided d")
    assert notes == Notes(summary="s", decisions=["d"], open_questions=[])


async def test_embed_returns_vectors():
    def handler(request):
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1, 0.2]}, {"index": 1, "embedding": [0.3, 0.4]}]},
        )

    p = make_provider(handler)
    vecs = await p.embed(["a", "b"])
    assert vecs == [[0.1, 0.2], [0.3, 0.4]]


async def test_cloud_rerank_is_none():
    p = make_provider(lambda request: httpx.Response(500))
    assert await p.rerank("q", ["d1"]) is None


async def test_router_falls_back_to_cloud_on_sie_error():
    class BoomSIE:
        async def embed(self, texts):
            raise RuntimeError("sie down")

    class OkCloud:
        async def embed(self, texts):
            return [[1.0]]

    r = InferenceRouter(cloud=OkCloud(), sie=BoomSIE(), providers={"embed": "sie"})
    assert await r.embed(["x"]) == [[1.0]]


@pytest.mark.live
async def test_live_embed_smoke():
    p = CloudProvider(client=None, api_key=None)  # real settings
    vecs = await p.embed(["hello meeting"])
    assert len(vecs) == 1 and len(vecs[0]) > 100
