# Friction Finder brand tokens (v0.7)

This is the source of truth for the app, the deck and any website. The tokens live in code in
`web/tailwind.config.js` and `web/src/index.css`.

## Colour: every colour means one thing

| Role | Token | Hex | Use only for |
|---|---|---|---|
| **Computed by code** | `brand` / `brand-500` | `#0E8A7E` / `#12A594` (tints `#E7F6F4`, `#C9ECE7`) | numbers and badges the code computed, "Computed" provenance, links to a method, "linked" cells |
| **Needs a human decision** | `act` | `#C4501E` (tints `#FDF1EC`, `#F9DCCF`; text `#9C3A12`) | Create action plan, Approve, "Needs your decision" |
| **Written by AI, checked** | `ai` | `#6941C6` (tints `#F4F3FF`) | model-written text and the AI steps in a trace |
| Navigation / primary UI | `fg` (ink) | `#101828`, soft `#344054`, mute `#525E70`, faint `#667085` (both ≥ 4.5:1, WCAG AA) | text, primary navigation buttons |
| Sidebar | `side` | `#0B1B2B`, hover `#13283D`, active `#1B3550` | app chrome only |
| Canvas / surface / border | | `#F5F6F8` / `#FFFFFF` / `#E4E7EC` (strong `#D0D5DD`) | backgrounds, cards, rules |

Status colours are a separate system and never mean "computed" or "decision":

| Status | Token | Hex | Meaning |
|---|---|---|---|
| Needs attention | `crit` | `#D92D20` | operations **and** engagement moved beyond normal variation |
| Watch | `warn` | `#CA8504` (amber-yellow, kept apart from rust) | one of the two moved; also "inconclusive" and "hypothesis" |
| Normal / worked | `ok` | `#079455` | within normal variation; plan review "worked" |
| Info | `info` | `#2E6BE6` | in progress, demo CSV |
| Rolled up | neutral grey | `#98A2B3` | team under 4 people, no numbers shown |

Charts: the team line is `crit` `#D92D20` with a light area fill. Comparable teams are a dashed grey
`#98A2B3` line. Gridlines are `#EEF0F3`. Before/after shading uses 5–8% `crit` / `brand`. Quartile bars
run from bottom `crit` through middle `#D0D5DD` to top `brand`.

## Type

- **Geist** (Google Fonts) for everything; **Geist Mono** for SQL, ids and item codes.
- Page title 24 px / 600 / −0.02em. Card title 15 px / 600. Body 14 px. Labels 12 px / 500 in mute.
  Overline 11 px / 600 / +0.06em uppercase.
- Big numbers 26 px / 600, tabular figures (`.tnum`). Units always sit beside or under the number:
  "per 10 people / month", "pts on a 5-point scale", "3 months".

## Shape and space

- Radius: cards 12 px (`rounded-xl`), controls 8 px (`rounded-lg`), badges 6 px, pills full.
- Card padding 20 px. Page gutter 16 px mobile, 32 px desktop. Max content width 1360 px.
- Shadows: `card` for resting, `pop` for menus and hover. No heavy shadows.
- Sidebar 248 px. Top bar 64 px, white, bottom border.

## Logo

The v1 mark, refined: an ink tile `#1B3A4B` with a teal ring `#12A594` that has a gap, and a rust dot
`#E0703E`. The ring is what the code computes; the dot is the decision a person makes.
Files: `web/public/favicon.svg`; the React component is `Logo` in `web/src/components/Shell.tsx`.

## Voice

- Say "AI-assisted workflow", never "agent". Say "association, not cause" and "directional, not causal".
  Label follow-up months as "synthetic".
- Lead each screen with one sentence: what the manager should conclude. Give one primary action per screen.
- Numbers come only from the API. The narration in the guided demo contains no numbers.
