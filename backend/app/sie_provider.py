import httpx

from app import routing_log
from app.agents import get_agent
from app.config import settings
from app.inference import EXTRACT_PROMPT, NOTES_PROMPT
from app.models import Entities, Notes, parse_json_block

# Hosted SIE (https://api.superlinked.com) verified live 2026-08-14; supersedes
# the Task 2 local-install spike. Model ids per the controller amendments.
ENCODE_MODEL = "Qwen/Qwen3-Embedding-4B"
SCORE_MODEL = "Qwen/Qwen3-Reranker-0.6B"
GENERATE_MODEL = "Qwen/Qwen3.5-4B"


class SIEProvider:
    def __init__(self, client: httpx.AsyncClient | None = None, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else settings.sie_api_key
        self.client = client or httpx.AsyncClient(base_url=settings.sie_base_url, timeout=120)

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    async def transcribe(self, wav_bytes: bytes):
        raise NotImplementedError("SIE ASR not wired; cloud handles transcription")

    async def chat(self, model: str, prompt: str, max_tokens: int = 1500) -> str:
        """Free-form generation on SIE, used by the per-meeting chat."""
        resp = await self.client.post(
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    async def generate_notes(self, transcript_text: str, agent_id=None, duration_s: float = 0.0) -> Notes:
        agent = get_agent(agent_id)
        model = agent.model_for(duration_s)
        prompt = f"{agent.context}\n\n{NOTES_PROMPT.format(transcript=transcript_text)}"
        with routing_log.timed("notes", "sie", model, agent=agent.id, duration_s=round(duration_s, 1)):
            resp = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                },
                headers=self._headers(),
            )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        return Notes.from_dict(parse_json_block(raw))

    async def extract(self, transcript_text: str, agent_id=None) -> Entities:
        # gliner_multi-v2.1 missed task spans in the live smoke test, so
        # extract uses the same chat-completions + EXTRACT_PROMPT pattern as
        # generate_notes instead of the /v1/extract endpoint.
        agent = get_agent(agent_id)
        prompt = (
            f"{agent.context}\n\nPay particular attention to: {', '.join(agent.labels)}.\n\n"
            f"{EXTRACT_PROMPT.format(transcript=transcript_text)}"
        )
        # Extraction is narrow and structured, so it stays on the fast model even
        # when the agent uses a heavier one for notes.
        with routing_log.timed("extract", "sie", GENERATE_MODEL, agent=agent.id):
            resp = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": GENERATE_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                },
                headers=self._headers(),
            )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        return Entities.from_dict(parse_json_block(raw))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        with routing_log.timed("embed", "sie", ENCODE_MODEL, items=len(texts)):
            resp = await self.client.post(
                f"/v1/encode/{ENCODE_MODEL}",
                json={"items": [{"text": t} for t in texts]},
                headers=self._headers(),
            )
        resp.raise_for_status()
        return [item["dense"]["values"] for item in resp.json()["items"]]

    async def rerank(self, query: str, docs: list[str]) -> list[float] | None:
        with routing_log.timed("rerank", "sie", SCORE_MODEL, docs=len(docs)):
            resp = await self.client.post(
                f"/v1/score/{SCORE_MODEL}",
                json={"query": {"text": query}, "items": [{"text": d} for d in docs]},
                headers=self._headers(),
            )
        resp.raise_for_status()
        scores = sorted(resp.json()["scores"], key=lambda s: int(s["item_id"].split("-")[1]))
        return [s["score"] for s in scores]
