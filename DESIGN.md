---
name: Echo
description: The category standard for an AI meeting-notes app, played straight at full craft.
colors:
  paper: "#fbfbfa"
  panel: "#ffffff"
  ink: "#1f1e1c"
  soft: "#6f6d67"
  faint: "#757269"
  line: "rgb(31 30 28 / 0.1)"
  action: "#2563eb"
  danger: "#d33a2f"
typography:
  headline:
    fontFamily: "Inter Variable, Inter, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Inter Variable, Inter, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Inter Variable, Inter, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.65
  secondary:
    fontFamily: "Inter Variable, Inter, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.625
  meta:
    fontFamily: "Inter Variable, Inter, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
  wordmark:
    fontFamily: "Inter Variable, Inter, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    letterSpacing: "-0.025em"
  lead:
    # Answer text, meeting summary, and empty-state titles
    fontFamily: "Inter Variable, Inter, system-ui, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 400
    lineHeight: 1.7
rounded:
  md: "6px"
  lg: "8px"
  xl: "12px"
  full: "9999px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "20px"
  gutter: "24px"
  section: "32px"
components:
  input-search:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "12px 96px 12px 44px"
  button-ask:
    backgroundColor: "{colors.action}"
    textColor: "{colors.panel}"
    rounded: "{rounded.lg}"
    padding: "6px 12px"
  panel-answer:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "20px"
  nav-link:
    backgroundColor: "transparent"
    textColor: "{colors.soft}"
    rounded: "{rounded.md}"
    padding: "4px 10px"
  nav-link-active:
    backgroundColor: "rgb(31 30 28 / 0.06)"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "4px 10px"
  list-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px 12px"
  list-row-hover:
    backgroundColor: "rgb(31 30 28 / 0.03)"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px 12px"
  chip-topic:
    backgroundColor: "rgb(31 30 28 / 0.05)"
    textColor: "{colors.soft}"
    rounded: "{rounded.full}"
    padding: "4px 10px"
---

# Design System: Echo

## Overview

**Creative North Star: "The Category Standard"**

Echo is an AI meeting notetaker that looks the way the category is supposed to look, executed at full craft. The world is a warm near-white page carrying ink-dark text, structured by hairline dividers rather than boxes, with exactly one blue that means "act" and one red that means "failed". This is a user-chosen canon: an expressive galley-proof serif world was built first and rejected (seed 6280867b); basic and understandable beats expressive. Nothing on screen asks to be admired; everything asks to be read.

Density is a single reading column (42rem) that holds the wordmark, one search-or-ask input, and a flat divided list of meetings. The synthesis answer is the only content that earns a full white panel; everything else sits directly on the paper ground. Motion exists only as meaning: text lines settle in as notes arrive, statuses pulse while the pipeline works, and everything respects `prefers-reduced-motion`.

**Key Characteristics:**
- One warm near-white ground, white panels only where content is "served" (input, synthesis answer)
- Hairline dividers (1px at 10% ink) do all the structural work; no card grids
- Inter Variable for every glyph, 15px base, tight semibold headings
- One action blue used sparingly: links, statuses, focus, and a single filled button
- Icons are hand-drawn inline SVG at ~1.6 stroke with round caps; never a glyph font or icon package
- Copy uses middots (·) as separators and never an em dash

## Colors

A two-voice palette: a warm ink-and-paper neutral family carries everything, and a single blue speaks for every action.

### Primary
- **Action Blue** (`{colors.action}`, #2563eb): the only accent. Text links, the Ask button fill, in-flight status words, the caret, text selection (at 18% alpha), and the focus ring (at 12% alpha). It appears as filled background exactly once per screen at most (the Ask button).

### Neutral
- **Paper** (#fbfbfa): the page ground, set on `<html>`. Warm near-white, never pure white.
- **Panel** (#ffffff): pure white, reserved for the search input and the synthesis answer panel; the one step "above" paper.
- **Ink** (#1f1e1c): primary text, the logo tile, graph nodes and edges. Warm near-black, never #000.
- **Soft** (#6f6d67): secondary text — summaries, meta prose, empty-state copy, open questions.
- **Faint** (#757269): the quietest voice — placeholders, drawn-icon strokes, list bullets. Visually a sibling of Soft; the split is role (glyph/placeholder vs. readable prose), not contrast.
- **Hairline** (rgb(31 30 28 / 0.1)): every divider and border. Translucent ink, not a solid gray, so it sits naturally on both paper and panel.

### Signal
- **Danger Red** (`{colors.danger}`, #d33a2f): failures only — "Failed: <error>" lines, the offline banner, the recording dot. Never decorative.

### Named Rules
**The One Blue Rule.** Action Blue is the entire accent system. If something is interactive or in flight, it may be blue; nothing else may. It fills at most one button per screen.

**The Translucent Hairline Rule.** Borders and dividers are always `rgb(31 30 28 / 0.1)` — ink at 10%, never an opaque gray. Hover and active tints are the same ink at 3–6% (`bg-ink/[0.03]` rows, `bg-ink/[0.06]` active nav, `bg-ink/[0.05]` chips).

## Typography

**Body Font:** Inter Variable (via `@fontsource-variable/inter`; falls back to Inter, system-ui)
**Display Font:** none — Inter carries every role.

**Character:** One family, differentiated only by size, weight, and tightness. Headings are semibold and tracking-tight; prose is regular with generous leading; meta is small, gray, and tabular-numbered. Quiet competence, no typographic events.

### Hierarchy
- **Headline** (600, 1.5rem, leading 1.25, tracking -0.025em): the meeting title on its detail page, with `text-wrap: balance`. The largest type in the product.
- **Empty-state lead** (500, 1.05–1.2rem): "No meetings yet", "Not enough meetings yet." The only mid-size step.
- **Title** (600, 0.9375rem): meeting-row titles and the "Transcript" toggle label.
- **Section heading** (600, 0.875rem): "Decisions", "Action items", "Open questions", "Topics" — sentence case, never uppercase, no letterspacing.
- **Body** (400, 0.9375rem = 15px base, leading 1.65–1.7 for prose): summaries, synthesis answers, transcript turns. Prose measures cap around 38–52ch.
- **Secondary** (400, 0.875rem, leading-relaxed): row summaries (2-line clamp), nav links.
- **Meta** (400, 0.8125rem, `{colors.soft}`, `font-variant-numeric: tabular-nums`): the `.meta` utility — dates, durations, sources lines, statuses, graph captions.

### Named Rules
**The Sentence Case Rule.** Every heading, button, and status is sentence case. No uppercase labels, no kickers or eyebrows, no letterspaced smallcaps.

**The Middot Rule.** Meta fragments join with a spaced middot ("14 Aug, 15:02 · 4m 12s"). Copy never uses an em dash.

## Layout

One centered reading column: `max-width: 42rem`, 24px side gutters, 96px bottom padding. The header (logo + wordmark left, test controls + nav right) sits inside the same column at 28px top / 20px bottom padding — there is no full-width bar, no sidebar, no grid.

Vertical rhythm is a small Tailwind-step scale: 6px between siblings, 8–10px after headings, 16px row padding, 24px around the answer panel's content (20px internal), 32px (`mt-8`) between page sections. Lists are flat divided rows (`divide-y` hairlines) whose hit area extends 12px past the text column (`-mx-3 px-3`) so the hover tint reads as a soft slab, not a card.

The Threads graph is the one wide element: an SVG at 720x340 viewBox scaled to full column width. Responsive behavior is minimal by design — the column just narrows; the test-only mic controls hide below `sm`.

## Elevation & Depth

The system is flat with one whispered exception. Depth is conveyed by layer color (paper → white panel) and hairlines, not shadows. The only resting shadow in the product is `0 1px 2px rgb(31 30 28 / 0.04)` on the two white panels (search input, answer panel) — just enough to lift white off near-white. Focus adds a soft ring, not elevation.

### Shadow Vocabulary
- **Panel lift** (`box-shadow: 0 1px 2px rgb(31 30 28 / 0.04)`): resting state of the search input and synthesis answer panel. Nothing else carries a shadow.
- **Focus ring** (`box-shadow: 0 0 0 3px rgb(37 99 235 / 0.12)` plus `border-color` shifting to action at 60%): the search input's focus treatment. Non-input elements use the global `outline: 2px solid {colors.action}` with 2px offset on `:focus-visible`.

### Named Rules
**The One Shadow Rule.** `0 1px 2px rgb(31 30 28 / 0.04)` is the entire shadow vocabulary at rest. Anything needing more separation gets a hairline or a panel background instead.

## Shapes

Soft, small radii that grow with the element's importance: 6px for nav pills, 8px for list-row hover slabs and the Ask button, 12px for the search input and answer panel, full-round only for topic chips and the recording dot. No sharp corners, no oversized radii, no clipping tricks.

Icons are part of the shape language: every icon is drawn inline as SVG geometry at roughly 1.6 stroke (1.4 on the small action-item checkbox) with round linecaps — a magnifier from a circle and a stick, a back arrow from three strokes, an empty rounded checkbox. The logo follows the same grammar: a 32px ink tile (7px radius) holding a paper-colored dot and two concentric arcs, the outer arc at 55% opacity — the "echo".

## Components

### Search / Ask Input (signature)
The primary action of the product; one input that both filters and asks.
- **Style:** white panel on hairline border, 12px radius, panel-lift shadow, drawn magnifier at left (16px, faint), placeholder "Search or ask anything" in faint.
- **Focus:** border shifts to action blue at 60%, soft blue ring shadow (see Elevation); native outline suppressed on inputs in favor of this ring.
- **Behavior:** typing live-filters (280ms debounce); Enter asks; Escape clears. When the query is non-empty an **Ask** button appears inside the right edge.

### Buttons
- **Primary (Ask):** action-blue fill, white text, 8px radius, 6x12px padding, 0.8125rem medium. Hover dims to 90% opacity; disabled to 50%. This is the only filled button in the product.
- **Text buttons:** everything else — transcript Show/Hide (meta-size, action blue), test-mic controls (meta-size, soft, hover to ink). No borders, no fills.

### Navigation
- Two links, "Meetings" and "Threads", as quiet pills: 0.875rem, 6px radius, soft text at rest, hover to ink; active gets ink text, medium weight, and a 6% ink tint. No underlines anywhere in chrome (`no-underline`); underline appears only on hover of inline source links.

### List Rows
- Flat rows in a hairline-divided stack: semibold 0.9375rem title truncated left, meta date/duration right on the same baseline, 2-line-clamped soft summary below, optional status line under that. Whole row is a link; hover paints a 3% ink slab with 8px radius extending past the column edge. No chevrons, no thumbnails.

### Answer Panel
- The synthesis response: white panel, hairline border, 12px radius, 20px padding, panel-lift shadow. Paragraphs animate in with `set-line` (450ms, staggered 120ms). A hairline-topped "Sources:" meta line lists cited meetings as action-blue links.

### Chips
- Topics only: full-round, 5% ink tint, soft text, 0.8125rem, 4x10px padding. Non-interactive; no selected state exists.

### Status Lines
- In-flight: exact words "Transcribing…" / "Writing notes…" in meta size, action blue, pulsing via `ink-pulse` (opacity 0.45↔0.9, 1.5s). Failure: "Failed: <error>" in danger red, static. Loading anywhere is the word "Loading…" in soft, pulsing. There are no spinners or progress bars in the product.

### Threads Graph (signature)
- Force-directed SVG: 11px-radius ink dots, ink edges whose width encodes similarity weight (1.75px + weight-scaled) at 55% opacity, dimming to 18% when another edge is picked and turning action blue at 95% when selected. Node labels are Inter at 16.5px / weight 550 in SVG units — deliberately large for projector legibility. Caption and selection detail render as meta text under a hairline.

## Do's and Don'ts

### Do:
- **Do** keep every screen inside the 42rem column with hairline-divided flat lists; the white panel treatment is reserved for the input and the synthesis answer.
- **Do** draw new icons inline as SVG at ~1.6 stroke with round linecaps, colored via `currentColor` or the token variables.
- **Do** use the exact status vocabulary: "Transcribing…", "Writing notes…", "Failed: <error>", "Loading…" — pulsing opacity for in-flight, static red for failure.
- **Do** join meta fragments with " · " and keep numbers tabular (`.meta` handles both the size and `tabular-nums`).
- **Do** give every animation a `prefers-reduced-motion` fallback, as `set-line`, `ink-pulse`, and `rec-pulse` already have.

### Don't:
- **Don't** introduce a second accent, a gradient, or a filled colored surface; blue text/ring is the ceiling for everything except the single Ask button.
- **Don't** box content into cards or add shadows beyond `0 1px 2px rgb(31 30 28 / 0.04)`; separation comes from hairlines and whitespace.
- **Don't** use uppercase labels, kickers/eyebrows, letterspaced headings, or any typeface other than Inter Variable.
- **Don't** use em dashes in copy, spinners for progress, or icon fonts / icon packages.
- **Don't** use pure #000 text or opaque gray borders; ink is #1f1e1c and lines are translucent ink.
