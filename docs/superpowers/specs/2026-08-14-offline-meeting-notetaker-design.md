# Offline Meeting Notetaker — Design Spec (v2, verified)

**Event:** Superlinked x Alibaba Cloud Qwen hackathon (2026-08-14 build day)
**One-line pitch:** A physical meeting recorder for in-person meetings — press a button, it captures the room and streams it over Wi-Fi to the backend. Everything downstream (transcription, notes, extraction, search, cross-meeting insights) runs through SIE, with one justified Alibaba Cloud offload.

## What changed from v1 (all verified, not assumed)

- **SIE is the whole backend brain, not just note generation.** SIE has four primitives — `encode`, `score`, `extract`, `generate` — plus OpenAI-compatible `/v1/embeddings`, `/v1/chat/completions`, and audio endpoints. We use all of them.
- **The legacy `superlinked` framework is dropped.** It is officially deprecated ("for new development, use SIE Server") and cannot use SIE as its embedding backend. Multi-attribute fusion (semantic + recency + tags) is ~20 lines of our own scoring on top of SIE `encode` + `score`.
- **Device stores nothing — it streams.** Axiometa Genesis (ESP32-S3) has no SD by default; instead of record-to-storage-then-sync, the device streams mic audio over a WebSocket to the laptop backend while recording. Simpler firmware, no storage handling, and enables live status/transcript feedback to the device display.
- **Hardware is a parallel track, not a dependency.** The dashboard has an "upload/record audio" path so the full pipeline demos even if firmware fights us. Judging criteria award SIE usage, not hardware — the device is the wow factor, not the submission.

## Core concept

### The device (Axiometa Genesis, ESP32-S3 — capture + stream only)
- Button press starts a session: device opens a WebSocket to the laptop backend (same Wi-Fi network) and streams PDM mic audio (16 kHz mono 16-bit, 32 KB/s — trivial over Wi-Fi).
- Button press again stops it; backend finalizes the WAV and kicks off the pipeline.
- Display shows status: idle / REC / syncing / done.
- **Stretch (cute demo moment):** backend pushes the live transcript tail back over the same WebSocket; device renders the last couple of lines on the LCD module.
- No on-device inference, no storage, no processing. Dumb and reliable.

### The backend (laptop, FastAPI or similar — every request flows through SIE)
1. **Transcription + speaker diarization** — `qwen3.5-omni-flash` (Alibaba, verified live twice): transcribes perfectly AND labels distinct voices as Speaker 1/2/3 when prompted — verified on a synthesized two-voice meeting, including a speaker returning for a later turn. This is a second honest Alibaba offload: SIE's catalog has no diarization model, so speaker attribution genuinely needs the cloud call. Call shape: OpenAI-compatible chat completions, base64 data-URI `input_audio`, `stream:true`, `modalities:["text"]`. (Do NOT use `qwen-audio-3.0-asr-flash` — it 400s on this gateway on every request shape.) SIE's local audio endpoint remains the no-diarization fallback if the venue network dies.
   - Speaker labels flow downstream: notes say who decided what, action items get owners ("Speaker 2 owns the payment bug"), and a stretch prompt maps Speaker N → real names when people address each other by name.
2. **Note generation** — SIE `generate` (Qwen3-4B-Instruct via MLX on Apple Silicon): summary, decisions, open questions per meeting.
3. **Structured extraction** — SIE `extract` (GLiNER, labels at query time — no LLM call): action items, people, dates, projects. Feeds the action-item tracker and graph node metadata.
4. **Indexing** — SIE `encode` (Qwen3-Embedding-0.6B): every meeting gets a transcript embedding + metadata (timestamp, duration, extracted tags). Stored in-process (list of vectors + numpy is enough at hackathon scale).
5. **Search** — query → SIE `encode`, cosine top-k, then SIE `score` (Qwen3-Reranker-0.6B) reranks, then our fusion scoring blends semantic score + recency + tag match. This is the load-bearing retrieval story.
6. **Cross-meeting synthesis (the Alibaba offload)** — `qwen3.8-max` via `/compatible-mode/v1/chat/completions`, one call, only for queries that need reasoning across multiple retrieved meetings ("what did we decide about X across the last 5 syncs", "has this action item come up before and never been closed"). Everything else stays local on SIE.

### The dashboard (web UI)
- Meeting history, per-meeting notes, action items, search box.
- **Meeting-similarity graph (iteration 1):** cosine similarity between meeting embeddings (already computed for search — zero extra model calls) → force-directed graph (d3/cytoscape). Related meetings cluster; clicking an edge shows why (shared entities from `extract`).
- **Insights (iteration 2):** open-action-items view (extracted items never marked closed in later meetings), synthesis answers rendered with per-meeting citations.
- The graph + a synthesis answer trace is the source material for the visual-track asset.

## Why the SIE / qwen-max split is honest here
Per meeting: 1 ASR call + 1 generate + 1 extract + 1 encode — all SIE, all local. Per search: 1 encode + 1 score — SIE. The ONLY cloud LLM call is multi-meeting synthesis, which genuinely can't be done by retrieval + a 4B model holding many transcripts in tension. If a judge asks "why not one model for everything," the answer is concrete.

## Where Alibaba Cloud is used (it is, three places)
1. **`qwen3.8-max` synthesis offload** — the rewarded offload in the main-track criteria.
2. **Visual track (mandatory):** `qwen-image-3.0-pro` via DashScope path `/api/v1/services/aigc/multimodal-generation/generation` (sync, ~15 s, returns URL — expires in 24 h, download immediately). `qwen-image-edit` can stylize a dashboard screenshot into the explainer. Optional video: wan2.x via `/api/v1/services/aigc/video-generation/video-synthesis` (async, poll `/api/v1/tasks/{id}`, 1–5 min).
3. **ASR fallback:** `qwen3.5-omni-flash` (verified working) if local SIE ASR misbehaves.

NOTE: image/video generation is DashScope-path only — the OpenAI-style `/images/generations` 404s on this gateway.

## Architecture summary

| Layer | Tech | Role |
|---|---|---|
| Device | Axiometa Genesis (ESP32-S3), button + PDM mic + LCD modules | capture, WebSocket audio stream, status display |
| Transport | Wi-Fi, WebSocket to laptop | live audio in, status/transcript tail back |
| ASR + diarization | qwen3.5-omni-flash (Alibaba, verified; SIE audio as offline fallback) | audio → speaker-labeled transcript |
| Notes | SIE `generate` (Qwen3-4B, MLX) | summary, decisions, questions |
| Extraction | SIE `extract` (GLiNER) | action items, people, dates, tags |
| Index + search | SIE `encode` + `score` + own fusion scoring | semantic + recency + tag retrieval |
| Synthesis | qwen3.8-max (Alibaba, OpenAI-compatible) | cross-meeting reasoning, one call |
| Dashboard | web UI + d3/cytoscape graph | history, search, action items, similarity graph |
| Visual asset | qwen-image-3.0-pro / qwen-image-edit (DashScope path) | explainer for the visual track |

## Build order (deadline 18:00 hard; code freeze ~16:45)

1. **First:** `uv venv --python 3.12` + `pip install "sie-server[local]"` + smoke-test encode/generate/extract locally — the last unverified load-bearing piece. If SIE-local ASR or generate stalls on Apple Silicon, fall back to verified cloud calls immediately and move on.
2. Backend pipeline with **file-upload input** (no hardware): upload WAV → transcript → notes → extract → index. Demoable end-to-end ASAP.
3. Dashboard: list + notes + search.
4. Similarity graph + synthesis query.
5. **Parallel track (one person, timeboxed):** ESP32-S3 firmware — I2S PDM read → WebSocket stream; button + status display. If not working by ~15:30, the phone/laptop records and the device becomes a table prop.
6. 16:45–18:00: visual asset (generate from dashboard screenshot), 2-min video, social post, submission form.

## Verified endpoint facts (tested live 2026-08-14 morning with the hackathon key)

- Host: `https://ws-217y1bpliyzcf5nl.ap-southeast-1.maas.aliyuncs.com`; 158 models on `/compatible-mode/v1/models`.
- `qwen3.7-flash` chat works (reasoning model — emits `reasoning_content`, strip it). `qwen3.8-max`, `qwen3.7-max` listed.
- `qwen3.5-omni-flash` ASR: perfect transcription, needs `stream:true` + `modalities:["text"]` + base64 data-URI `input_audio`.
- `qwen3.7-text-embedding` works on `/compatible-mode/v1/embeddings` (cloud fallback for encode).
- `qwen-image-3.0` generation verified: sync, ~15 s, returns OSS URL.

## Open items
- SIE local install on this laptop (Python 3.12 via uv — uv already installed). MLX generation needs an `mlx_repo` adapter option per model.
- Which SIE ASR model runs acceptably on Apple Silicon (fallback is verified cloud omni-flash, so this cannot block).
- Axiometa mic module part + I2S pinout on the AX22 connector — confirm with the kit in hand.
- Speaker N → real-name mapping (infer from people addressing each other): stretch prompt on top of verified diarization.

## Explicit non-goals
- No on-device transcription or inference.
- No storage on device — stream-only.
- No real-time coaching during the meeting; live transcript tail on the LCD is display-only stretch.
- No claim the hardware is required for submission — the pipeline demos standalone.
