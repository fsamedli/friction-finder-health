# Friction Finder brand tokens (v0.8)

This is the source of truth for the app, the deck and any website. The tokens live in code in
`web/tailwind.config.js` and `web/src/index.css`. v0.8 (Oct 8, 2026) warmed the canvas, deepened the ink and
added evidence states; every colour meaning from v0.7 is unchanged, because judges have seen them.

## Colour: every colour means one thing

| Role | Token | Hex | Use only for |
|---|---|---|---|
| **Computed by code** | `brand` / `brand-500` | `#0E8A7E` / `#12A594` (tints `#E7F6F4`, `#C9ECE7`) | numbers and badges the code computed, "Computed" provenance, links to a method, "linked" cells, the "Supported" evidence state |
| **Needs a human decision** | `act` | `#C4501E` (tints `#FDF1EC`, `#F9DCCF`; text `#9C3A12`) | the one next action on Today, Draft a plan, Approve plan, "Decide: keep, change or stop", "Needs your decision" |
| **Written by AI, checked** | `ai` | `#6941C6` (tints `#F4F3FF`) | model-written text (an investigation conclusion in model mode), the Ask button, AI steps in a trace |
| Navigation / primary UI | `fg` (ink) | `#101828`, soft `#344054`, mute `#525E70`, faint `#667085` (all ≥ 4.5:1 on white and on the canvas, WCAG AA) | text, primary navigation buttons |
| Sidebar (deep ink) | `side` | `#0A1726`, hover `#12253A`, active `#1A3350` | app chrome only |
| Canvas / surface / border | | warm white `#F8F7F4` / `#FFFFFF` / `#E7E5E0` (strong `#D3D0C8`) | backgrounds, cards, rules |

The sidebar keeps the legend: teal computed by code, rust needs your decision, purple written by AI and checked.

Status colours are a separate system and never mean "computed" or "decision":

| Status | Token | Hex | Meaning |
|---|---|---|---|
| Needs attention | `crit` | `#D92D20` | operations **and** engagement moved beyond normal variation; a review that deteriorated |
| Watch | `warn` | `#CA8504` (amber-yellow, kept apart from rust) | one of the two moved; "Mixed" evidence; "Inconclusive" review |
| Normal / improved | `ok` | `#079455` | within normal variation; review "Improved" |
| Info | `info` | `#2E6BE6` | in progress, "Not ready", the uploaded-data strip, prepared answers |
| Rolled up | neutral grey | `#98A2B3` | team under 4 people, no numbers shown |

## Evidence states (new in v0.8)

Every answer and every block on Investigate carries one chip. They are set by explicit rules in code, never a
confidence percentage. The tooltip says what the state means in plain words.

| State | Chip | Plain words |
|---|---|---|
| Supported | teal | The checks agree and cover the question. |
| Mixed | amber | Some checks point one way and some the other; both are shown. |
| Insufficient | grey, dashed | Not enough evidence to say. The next step is to gather it, with an owner. |
| Unavailable | grey, dashed | The data this needs is not in this prototype (e.g. the external Gallup benchmark). |

Review results use plain words too: **Improved**, **Deteriorated**, **Inconclusive**, or **Not ready** before the
review date. `app/impact.py` returns worked / no effect / inconclusive; the UI maps them (no effect = the whole 95%
interval above zero, i.e. the KPI rose relative to comparable teams = Deteriorated).

## Charts

Charts only where they change a decision. Every chart says its **unit, period and baseline** in its caption or
legend. The team line is `crit` `#D92D20` with a light area fill; comparable teams are a dashed grey `#98A2B3`
line; gridlines `#EEECE7`. Before/after shading uses 5–8% `crit` / `brand`. Quartile bars run from bottom `crit`
through middle `#D0D5DD` to top `brand`. Charts the investigation API describes (`ChartSpec`) render as simple bars
or a range strip from the rows in the response; nothing is drawn from numbers the API did not send.

## Type (v0.10, Oct 27, 2026: one notch larger on the main path)

Prof. Hall (Oct 21): "too much small text; enlarge key information." The scale moved up one step on Today,
Investigate, Plans and Review; the technical layer (methods, SQL, traces) kept its size.

- **Geist** (Google Fonts) for everything; **Geist Mono** for SQL, ids and item codes.
- Page title 26 px / 600 / −0.02em; the Today headline 26 px, 32 px from the `sm` breakpoint; its bullet lines 16 px.
- **Investigate question blocks:** a numbered ink circle, the question as an `h2` at 20 px (22 px from `sm`) / 600 /
  −0.02em, the one-sentence answer at 16.5 px regular, the evidence chip under it, and the charts and tables behind a
  "Show the evidence" disclosure (open by default only on "What explains it?"). The sticky question rail is numbered
  and follows the reader (13 px). Body 15 px. Labels (`.label`) 13 px / 500 in mute. Eyebrow (`.eyebrow`) 12 px / 600
  / +0.06em uppercase in faint (the old `.overline` class name collided with Tailwind's text-decoration utility and
  drew a line; renamed).
- Big numbers (`Stat`) 32 px / 600, tabular figures (`.tnum`). Units sit beside or under the number. Card titles
  16 px, subtitles 13.5 px; buttons 14 px (13.5 px small); badges 12.5 px.
- Guided demo: the block the current step talks about carries `data-demo="focus|explain|act|checklist|money"` and
  gets a static 6 px rust ring at 45% (`index.css`, `body[data-demo-step]`). Static, so reduced motion needs nothing.

## Shape, space and motion

- Radius: question blocks 16 px (`rounded-2xl`), cards 12 px, controls 8 px, badges 6 px, pills full.
- More breathing room than v0.7: the Today focus card has 24–32 px padding, sections are 40 px apart below it.
- Page gutter 16 px mobile, 32 px desktop. Max content width 1360 px. The Investigate panel sits in a 400 px
  right column from 1280 px; below that it is a full-width section reached from the "Ask" question chip.
- Motion: a 0.28 s fade-up on first paint, nothing else. `prefers-reduced-motion` turns all animation off.
- Every call has a loading, empty, error (with Try again), suppressed, insufficient, unavailable and fallback state.

## Logo

The v1 mark, refined: an ink tile `#1B3A4B` with a teal ring `#12A594` that has a gap, and a rust dot
`#E0703E`. The ring is what the code computes; the dot is the decision a person makes.
Files: `web/public/favicon.svg`; the React component is `Logo` in `web/src/components/Shell.tsx`.

## Voice

- Say "AI-assisted workflow" and "AI-assisted investigation", never "agent". Say "association, not cause" and
  "directional, not causal". Label follow-up months as "synthetic".
- Lead each screen with one sentence: what the manager should conclude. Give one primary action per screen; the
  first-viewport action on Today is rust because it is the manager's decision.
- The first viewport of Today has no p-values, methods or journey strip; those are one scroll or one click down.
- Numbers come only from the API. The narration in the guided demo contains no numbers.
- Every screen shows the demo-clock date and the dataset (demo CSV, synthetic; or the hospital's upload).
- v0.9-health: say "nurse manager" and "charge nurse", "unit team", "hospital"; name the operating metrics as
  late doses, absence days, quits, injuries, overtime shifts; say "unit-level counts, no patient data" wherever the
  old copy said the data was synthetic. The sidebar subtitle is "for nursing units". Lanford Health is fictional.
