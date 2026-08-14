---
version: 1
slug: "frontend-src-app-jsx"
primary_target: "frontend/src/App.jsx"
related_targets: ["frontend/index.html","frontend/src/screens","frontend/src/components"]
---

# Dashboard (whole frontend surface)

Scope: the entire web dashboard (home, meeting detail, threads). Visitor mode: Operate.

Audience & job: Oriol demoing to hackathon judges on a projector, 2026-08-14; judges must grasp the pipeline (diarized transcripts, notes, extraction, fusion search, cited synthesis) in under 90 seconds.

Chosen direction: THE CATEGORY STANDARD (standing exit, user-chosen 2026-08-14 after building and rejecting a galley-proof serif world from seed 6280867b as "too much, too confusing"). Basic and understandable, at home alongside Granola/Otter, Notion, Apple Notes — their craft level is the bar. Name: Echo, concentric-arc mark. Inter everywhere. Ground #fbfbfa, ink #1f1e1c, action blue #2563eb, hairline dividers, flat divided lists, one rounded search input, soft white panel for the synthesis answer. Code-led; no comp exists.

Memorable moment: the unified input — search-as-you-type re-ranks meetings with match %, Enter produces a cross-meeting answer in a panel with clickable sources.

Constraints: minimal copy; laptop-mic recorder is test-only, isolated in MicTest.jsx, hidden on mobile, trivially removable; backend contract backend/API.md at http://localhost:8000; poll meetings ~2.5s; statuses render as "Transcribing…" / "Writing notes…" / red "Failed — <error>".

Unresolved: none material.
