import base64
import json
import logging

import httpx

from app import routing_log
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

    async def generate_notes(self, transcript_text: str, agent_id=None, duration_s: float = 0.0) -> Notes:
        from app.agents import get_agent

        agent = get_agent(agent_id)
        prompt = f"{agent.context}\n\n{NOTES_PROMPT.format(transcript=transcript_text)}"
        with routing_log.timed("notes", "cloud", "qwen3.7-flash", agent=agent.id):
            raw = await self.chat("qwen3.7-flash", prompt)
        return Notes.from_dict(parse_json_block(raw))

    async def extract(self, transcript_text: str, agent_id=None) -> Entities:
        from app.agents import get_agent

        agent = get_agent(agent_id)
        prompt = (
            f"{agent.context}\n\nPay particular attention to: {', '.join(agent.labels)}.\n\n"
            f"{EXTRACT_PROMPT.format(transcript=transcript_text)}"
        )
        with routing_log.timed("extract", "cloud", "qwen3.7-flash", agent=agent.id):
            raw = await self.chat("qwen3.7-flash", prompt)
        return Entities.from_dict(parse_json_block(raw))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        with routing_log.timed("embed", "cloud", "qwen3.7-text-embedding", items=len(texts)):
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

    async def generate_notes(self, transcript_text, agent_id=None, duration_s: float = 0.0):
        return await self._call("generate_notes", transcript_text, agent_id, duration_s)

    async def extract(self, transcript_text, agent_id=None):
        return await self._call("extract", transcript_text, agent_id)

    async def embed(self, texts):
        return await self._call("embed", texts)

    async def rerank(self, query, docs):
        return await self._call("rerank", query, docs)

    async def chat(self, model, prompt, max_tokens: int = 2000):
        """Alibaba chat - used for the cross-meeting synthesis offload."""
        return await self.cloud.chat(model, prompt, max_tokens)

    async def chat_sie(self, model, prompt, max_tokens: int = 1500):
        """SIE chat, falling back to Alibaba so a SIE outage degrades rather
        than breaks. The model id differs per provider, hence the swap."""
        if self.sie is not None:
            try:
                return await self.sie.chat(model, prompt, max_tokens)
            except Exception as exc:
                logging.getLogger("notetaker").warning(
                    "SIE chat failed, falling back to cloud: %s", exc
                )
        return await self.cloud.chat("qwen3.7-flash", prompt, max_tokens)


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
