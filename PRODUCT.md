# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vite + React + Tailwind (user-confirmed 2026-08-14). Frontend lives in `frontend/`, talks to the FastAPI backend at `http://localhost:8000` (CORS wide open). d3 allowed for the similarity graph.

## Users

Oriol and his hackathon team, demoing live to Superlinked x Alibaba Qwen hackathon judges (2026-08-14, London, submission 18:00). Secondary viewer: judges watching on a projector from a distance, and screenshots/video for the visual-track submission.

## Product Purpose

An offline-first meeting notetaker: a physical ESP32 device streams room audio to a laptop backend, which transcribes with speaker diarization, generates notes (summary, decisions, open questions), extracts action items/people/dates/topics, embeds every meeting, and answers questions across meetings. The web dashboard is where all of that becomes visible. Success = judges immediately understand the pipeline's power without explanation.

## Positioning

Everything runs through the Superlinked Inference Engine locally (encode/score/extract/generate); the only cloud calls are diarized ASR and cross-meeting synthesis via Alibaba qwen3.8-max — a deliberate, defensible local/cloud split. The dashboard must make retrieval quality (fusion-scored search) and cross-meeting reasoning (cited synthesis answers) legible.

## Operating Context

- Live demo: meetings recorded by hardware device (or test WAV uploads), appear in the dashboard while processing, poll `GET /meetings/{id}` ~2s until `done`/`error`.
- Backend contract: `backend/API.md` (meetings list/detail, `/search?q&k`, `POST /synthesis`, `/graph`, `POST /meetings/upload`, `WS /ws/device`).
- Demo environment: projector at hackathon venue; also the source of the mandatory visual-track screenshot.

## Capabilities and Constraints

- Screens confirmed: home (meeting list + one unified bar that live-searches while typing and runs synthesis on Enter), meeting detail (summary, decisions, action items with owners, open questions, collapsible speaker-labeled transcript, topic chips), similarity graph (nodes = meetings, weighted edges with shared topics).
- Laptop-mic record affordance is TEST-ONLY: hardware is the real capture path; the mic feature must be small and trivially removable (isolated component).
- Meetings can be in `processing`/`transcribed`/`done`/`error`; the UI must show in-flight meetings gracefully.
- Minimal text everywhere — the user explicitly wants low copy, intuitive structure.
- Hard deadline: code freeze ~16:45 today.

## Brand Commitments

- Product name: **Echo** (user-chosen 2026-08-14; replaced working name "Minutes."). Mark: concentric echo arcs in a dark rounded square.
- Visual register (user-chosen, standing): the clean category standard — basic and understandable, at home alongside Granola/Otter, Notion, and Apple Notes. Inter for all type. Light warm-white ground, one action blue, hairline dividers. Expressive or antiquarian typography is explicitly rejected (a galley-proof serif direction was built 2026-08-14 and rejected as confusing).

## Evidence on Hand

- Real API response shapes with genuine sample content in `backend/API.md` (verbatim from a live run).
- Working backend on `localhost:8000` with a seeded `notetaker.db`.
- No logo, no product name confirmed yet (inferred gap — pick a modest wordmark, easy to change).

## Product Principles

1. The content is the interface: meeting notes should read like typeset documents, chrome recedes.
2. One input, two powers: search-as-you-type and ask-on-Enter live in the same bar.
3. Show the pipeline: processing states, fusion scores, and cited sources are the proof of the tech.
4. Everything demoable in under 90 seconds from a projector.
5. Test scaffolding (laptop mic) stays isolated and deletable.
