# Notetaker

An offline meeting notetaker for a hardware recorder. It turns raw audio into
speaker-diarized transcripts, meeting notes, action items, semantic search
across meetings, and a cross-meeting synthesis and graph view.

## Stack

Alibaba Cloud Qwen omni-flash for transcription and Qwen chat models for
notes and synthesis, with Superlinked SIE (hosted) as an alternate provider
for notes, extraction, embedding, and reranking. Provider routing is
per-primitive and configurable via env vars.

## Running it

```bash
cp .env.example .env   # fill in your API keys
cd backend
uv venv --python 3.12 .venv
uv pip install -e . --group dev
.venv/bin/uvicorn app.main:app --port 8000
```

See `backend/API.md` for the full HTTP and WebSocket contract.

## Tests

```bash
cd backend
.venv/bin/pytest -v            # offline suite
.venv/bin/pytest -v -m live    # live suite, needs real API keys
```
