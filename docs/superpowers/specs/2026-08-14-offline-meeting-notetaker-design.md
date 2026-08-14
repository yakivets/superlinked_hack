# Offline Meeting Notetaker — Design Spec

**Event:** Superlinked x Alibaba Cloud Qwen hackathon (2026-08-14 build day)
**One-line pitch:** A physical, offline-first meeting recorder — press a button, it captures the room. Everything else (transcription, notes, search, dashboard) happens on sync, powered heavily by Superlinked.

## Problem this does NOT solve (scope discipline)

- The device does not do on-device transcription or LLM inference — it is a dumb, reliable capture unit. All "brain" work happens on the backend after sync.
- Not a real-time streaming assistant during the meeting — no live coaching, no live transcript on-device.
- Hardware specifics (exact board/mic part numbers) are still open — this spec is written to hold regardless of the final board choice, as long as it can record audio to local storage and trigger a sync.

## Core concept

### The device (capture only)
- A button starts/stops a recording.
- A PDM microphone captures room audio to local storage (SD card / flash) for the duration of the meeting.
- A small display shows capture status (recording / idle / syncing) — no processing UI needed on-device.
- When the meeting ends, the device syncs the raw audio file to the backend (Wi-Fi, or plug-in/dock sync — TBD based on final hardware) and clears local storage once upload is confirmed.

### The backend (all the real work)
1. **Transcription** — raw audio → text (via a speech-to-text step; can be on the backend LLM stack or a dedicated ASR service — TBD).
2. **Ingest into Superlinked** — every meeting's transcript, along with structured metadata (date, duration, participants if known, meeting title), gets embedded into Superlinked as a multi-attribute vector: transcript text + timestamp + participant/tag metadata, fused into one retrieval space. This is the heavy, load-bearing use of Superlinked the judging criteria reward — every meeting note is retrievable by semantic content *and* filterable/ranked by its metadata in the same query.
3. **Note generation** — SIE (cheap, Qwen catalog) turns each transcript into structured meeting notes: summary, action items, decisions, open questions. High-volume, per-meeting work — the "every request flows through SIE" story.
4. **Cross-meeting synthesis** — qwen-max (Alibaba Cloud, the one expensive call) handles queries that require reasoning across *multiple* meetings at once: "what did we decide about X across the last 5 syncs with this client," "has this action item come up before and never been closed." This is the one step that genuinely needs frontier reasoning — everything else is retrieval + cheap summarization.
5. **Dashboard** — a web UI showing meeting history, searchable/filterable notes, action items, and the cross-meeting synthesis answers. This is also a natural home for the visual-track asset (a Qwen-generated explainer of how a query traces back through specific meetings).

### Why the SIE / qwen-max split is honest here
Superlinked's retrieval is what makes "search my meeting history" actually work — it's not decorative. SIE does the bulk, cheap, per-meeting note generation. qwen-max is reserved for the one genuinely hard case: reasoning across multiple retrieved meetings at once, which a single retrieval call can't do on its own.

## Architecture summary

| Layer | Role |
|---|---|
| Hardware device | Button-triggered recording, PDM mic capture to local storage, status display, sync-on-finish |
| Backend: ingest | Receive synced audio, run ASR, store raw transcript |
| Backend: Superlinked | Index every meeting (transcript text + metadata) into one retrieval space |
| Backend: SIE | Per-meeting note generation (summary, action items, decisions) — high volume, cheap |
| Backend: qwen-max (Alibaba) | Cross-meeting synthesis queries — one call, reserved for multi-meeting reasoning |
| Dashboard | Meeting history, search, notes, cross-meeting answers, visual-track asset source |

## Judging fit

- **Main challenge**: heavy real Superlinked usage (every meeting indexed, every search/filter goes through it) + SIE for high-volume note generation + one justified qwen-max offload for cross-meeting reasoning.
- **Visual track**: Qwen-generated explainer of a cross-meeting query result, sourced from the dashboard.
- **Social track**: post progress with device + dashboard visuals during the build.

## Open items still to resolve

- Final hardware board/mic/display part numbers and how sync actually happens (Wi-Fi vs. dock/cable) — unresolved as of this spec; verify before committing to firmware work.
- ASR choice for audio → text (dedicated speech-to-text service vs. routed through SIE/Alibaba if either exposes an audio-capable model).
- Exact Superlinked schema (spaces for transcript text, recency, participant/tag metadata).
- Whether participant identification (speaker diarization) is in scope for a one-day build, or notes stay unattributed to specific speakers.
- Superlinked SIE's exact API/SDK — HACK.txt's Superlinked startup guide section was blank; assume OpenAI-compatible endpoint until confirmed on-site.

## Explicit non-goals (repeat, for scope discipline)

- No on-device transcription or inference.
- No live/real-time features during the meeting itself — capture only.
- No custom hardware toolchain assumptions baked into this spec — kept board-agnostic pending verified hardware details.
