import base64
import json
import logging

import httpx

from app.config import settings
from app.models import (
    Entities,
    Notes,
    SpeakerTurn,
    parse_json_block,
    parse_speaker_turns,
)

TRANSCRIBE_PROMPT = (
    "Transcribe this meeting verbatim with speaker diarization. Label each "
    "distinct voice as Speaker 1, Speaker 2, etc. Format: one line per "
    "speaker turn, 'Speaker N: <text>'. Output only transcript lines."
)

NOTES_PROMPT = """You are a meeting-notes writer. Given the speaker-labeled transcript below, return ONLY a JSON object:
{{"summary": "<3-5 sentence summary>", "decisions": ["<decision made, with who made it>"], "open_questions": ["<unresolved question>"]}}

Transcript:
{transcript}"""

EXTRACT_PROMPT = """Extract structured data from the meeting transcript below. Return ONLY a JSON object:
{{"action_items": [{{"text": "<task>", "owner": "<speaker label or name, or null>"}}], "people": ["<names mentioned>"], "dates": ["<dates/deadlines mentioned>"], "topics": ["<3-6 short topic tags>"]}}

Transcript:
{transcript}"""


class CloudProvider:
    def __init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None):
        self.api_key = api_key or settings.alibaba_api_key
        self.client = client or httpx.AsyncClient(
            base_url=settings.alibaba_base_url, timeout=180
        )

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    async def _stream_chat(self, body: dict) -> str:
        text = ""
        async with self.client.stream(
            "POST", "/compatible-mode/v1/chat/completions", json=body, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                chunk = json.loads(line[6:])
                for choice in chunk.get("choices", []):
                    text += choice.get("delta", {}).get("content") or ""
        return text

    async def chat(self, model: str, prompt: str, max_tokens: int = 2000) -> str:
        resp = await self.client.post(
            "/compatible-mode/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def transcribe(self, wav_bytes: bytes) -> list[SpeakerTurn]:
        b64 = base64.b64encode(wav_bytes).decode()
        raw = await self._stream_chat(
            {
                "model": "qwen3.5-omni-flash",
                "stream": True,
                "modalities": ["text"],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": f"data:audio/wav;base64,{b64}",
                                    "format": "wav",
                                },
                            },
                            {"type": "text", "text": TRANSCRIBE_PROMPT},
                        ],
                    }
                ],
            }
        )
        return parse_speaker_turns(raw)

    async def generate_notes(self, transcript_text: str) -> Notes:
        raw = await self.chat("qwen3.7-flash", NOTES_PROMPT.format(transcript=transcript_text))
        return Notes.from_dict(parse_json_block(raw))

    async def extract(self, transcript_text: str) -> Entities:
        raw = await self.chat("qwen3.7-flash", EXTRACT_PROMPT.format(transcript=transcript_text))
        return Entities.from_dict(parse_json_block(raw))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.post(
            "/compatible-mode/v1/embeddings",
            json={"model": "qwen3.7-text-embedding", "input": texts},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    async def rerank(self, query: str, docs: list[str]) -> list[float] | None:
        return None


class InferenceRouter:
    PRIMITIVES = ("transcribe", "generate_notes", "extract", "embed", "rerank")
    _KEYMAP = {"generate_notes": "notes"}

    def __init__(self, cloud, sie=None, providers: dict | None = None):
        self.cloud = cloud
        self.sie = sie
        self.providers = providers if providers is not None else settings.providers

    async def _call(self, name: str, *args):
        key = self._KEYMAP.get(name, name)
        if self.providers.get(key) == "sie" and self.sie is not None:
            try:
                return await getattr(self.sie, name)(*args)
            except Exception as exc:
                logging.getLogger("notetaker").warning(
                    "SIE %s failed, falling back to cloud: %s", name, exc
                )
        return await getattr(self.cloud, name)(*args)

    async def transcribe(self, wav_bytes):
        return await self._call("transcribe", wav_bytes)

    async def generate_notes(self, transcript_text):
        return await self._call("generate_notes", transcript_text)

    async def extract(self, transcript_text):
        return await self._call("extract", transcript_text)

    async def embed(self, texts):
        return await self._call("embed", texts)

    async def rerank(self, query, docs):
        return await self._call("rerank", query, docs)

    async def chat(self, model, prompt, max_tokens: int = 2000):
        return await self.cloud.chat(model, prompt, max_tokens)


_router: InferenceRouter | None = None


def get_router() -> InferenceRouter:
    global _router
    if _router is None:
        sie = None
        if "sie" in settings.providers.values():
            from app.sie_provider import SIEProvider

            sie = SIEProvider()
        _router = InferenceRouter(cloud=CloudProvider(), sie=sie)
    return _router
