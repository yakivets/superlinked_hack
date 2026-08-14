# Codebase Architecture Graph — Design Spec

**Event:** Superlinked x Alibaba Cloud Qwen hackathon (2026-08-14 build day)
**One-line pitch:** Paste a GitHub repo. See its real architecture as a living graph. Ask "what if I change X" and watch the graph light up with exactly what breaks, why, where, and what to do about it — grounded in real commit history, not guesses.

## Problem this does NOT solve (scope discipline)

- Does not fork, execute, or actually run the codebase.
- Not a compiler, not a sandbox, not a "rewrite history and run tests" tool.
- Not a general-purpose static analyzer for every language — dependency signal comes from commit co-change history, not AST parsing.
- Reasoning is grounded in real evidence (commits, diffs, PRs) but the *outcome* (what breaks) is still a model's inference over that evidence, not a guarantee.

## Core concept

1. **Input**: a public GitHub repo URL.
2. **Ingest**: pull commit history (messages + diffs), PR titles/descriptions/discussion, and the file list.
3. **Build the graph**:
   - **Nodes** = files/modules.
   - **Edges** = co-change relationships: `co_change_score(A,B) = count(commits touching both A and B) / count(commits touching A)`, weighted by frequency. Language-agnostic — no per-language static-analysis tooling required, works on any repo in any language.
4. **Index into Superlinked**: every node gets a multi-attribute vector combining text (commit messages/diffs/PR discussion touching that file) with structured metadata (author, timestamp, file path, change frequency) in one retrieval space. This is Superlinked's real differentiator — multi-space fusion, not plain semantic search — and it is the backbone of the whole product. **Superlinked usage should be as heavy and central as possible**; it is not a thin retrieval layer bolted onto an LLM pipeline, it's the thing doing the actual ranking work.
5. **Render**: one-page graph view. Engineers see the whole architecture at a glance — clusters of related files, connection strength as edge weight.
6. **Ask a hypothetical**: "what if I change auth / migrate off OpenAI / refactor payments."
7. **Highlight**: Superlinked retrieves and ranks the nodes at risk, fusing semantic relevance to the query + co-change edge weight + metadata into one relevance score. **The ranking — not an LLM guess — decides which nodes light up.**
8. **Explain per node** (SIE, cheap, parallel — one call per highlighted node): for each lit-up node, produce:
   - **What will happen** — the specific predicted effect on this file/module.
   - **Why** — the evidence this is grounded in (which commits/PRs/co-change pattern support this).
   - **Where it breaks** — the specific location/responsibility within that file (e.g. "the retry-on-429 handler", "the request-schema validator") inferred from the retrieved diffs/commit messages.
   - **Potential solution** — a concrete suggested fix or migration path for that node.
9. **Synthesize** (qwen-max, one call, the single frontier-reasoning step): given all per-node evidence + explanations, produce the overall cascade narrative — how the highlighted nodes relate to each other, ordered risk/effort view, and a top-level recommended sequencing of changes.

## Why the SIE / qwen-max split is honest, not decorative

- **Superlinked** does the retrieval and ranking — the load-bearing part that determines correctness. Not an LLM's job.
- **SIE** does high-volume, cheap, parallel per-node explanation (what/why/where/solution) — this is the "every request flows through SIE" story the judging criteria reward.
- **qwen-max** is reserved for exactly one expensive call: cross-node synthesis, the one step that genuinely requires holding many pieces of evidence in tension. If a judge asks "why not one model for everything," the answer is concrete and defensible.

## Per-node output contract (what the UI renders on click/hover)

```
Node: services/auth/session.py
Risk: HIGH
What happens: Session refresh logic assumes REST-style token introspection;
  event-based auth removes the synchronous introspection call this depends on.
Why (evidence): 3 commits in the last year modified this file alongside
  services/auth/rest_client.py (co-change score 0.71); PR #482 "refactor auth
  retry logic" shows this dependency explicitly.
Where it breaks: `refresh_token()` — the synchronous call at line-level
  responsibility described in commit diff, not live line numbers (no code
  execution/parsing beyond diff text).
Potential solution: Introduce an async callback/webhook handler for token
  refresh instead of the current synchronous call; PR #482's retry wrapper
  can likely be reused with an event listener swapped in.
```

## Flagship demo query

"What if we migrated this codebase from OpenAI to Qwen?" — meta (the theme of the whole event), relatable to every team in the room, and the co-change graph naturally clusters around SDK call sites without needing to special-case that scenario in code.

## Visual track — free by construction

The live graph, lighting up in real time as a hypothetical is typed, is inherently visual. A screenshot/recording of it feeds directly into Qwen image or video generation on Alibaba Cloud for the required visual-track explainer asset — not separate work from the core build.

## Architecture summary

| Layer | Tech | Role |
|---|---|---|
| Ingestion | GitHub API | pull commits, diffs, PRs, file list |
| Graph construction | co-change heuristic (in-process) | build weighted edge list, language-agnostic |
| Retrieval & ranking | **Superlinked** | multi-space vectors (text + metadata), the core relevance engine |
| Per-node explanation | SIE (Qwen catalog via Superlinked inference engine) | cheap, parallel, one call per highlighted node |
| Cross-node synthesis | qwen-max (Alibaba Cloud Model Studio) | one call, overall cascade narrative + sequencing |
| Visual asset | Qwen image/video gen (Alibaba Cloud) | explainer generated from the live graph |
| Frontend | force-directed graph (e.g. d3 or cytoscape.js) | one-page graph view, highlight rendering |

## Judging criteria mapping (from HACK.txt)

- **Main challenge** (best app around SIE, offload rewarded): every highlighted node triggers an SIE call (heavy, real usage); qwen-max offload is small, singular, and justified — not decorative.
- **Alibaba visual track**: graph visualization → Qwen image/video explainer, generated as a natural pipeline output.
- **Social track**: post progress with the generated graph visuals throughout the day.

## Open items still to resolve

- Exact Superlinked schema: which "spaces" per attribute (text embedding space, recency/decay space, file-path categorical space, author categorical space) and how they're weighted/combined.
- Frontend graph library choice (d3 vs cytoscape.js vs alternative).
- Whether the qwen-max synthesis step is cut entirely under time pressure (SIE-only fallback: skip cross-node narrative, keep per-node explanations only).
- Repo(s) to pre-test ingestion against before the event, so ingestion pipeline isn't a live risk on the day.
- Superlinked SIE's actual API/SDK details — the "Superlinked startup guide" section in HACK.txt was blank; design currently assumes an OpenAI-compatible endpoint until confirmed on-site.

## Explicit non-goals (repeat, for scope discipline)

- No code execution, no test running, no actual repo mutation.
- No claim of certainty — output is model inference over real evidence, framed as "here's what the evidence suggests," not "here's what will definitely happen."
- No per-language AST parsing — co-change is the only dependency signal, by design, for one-day feasibility across arbitrary repos.
