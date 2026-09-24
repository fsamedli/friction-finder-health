# Friction Finder demo script (v0.7)

About 5 minutes of demo inside a longer talk. The timings are **targets for rehearsal**, not measurements.
The guided demo (top bar → **Start demo**) follows exactly this path.

## Before you go on stage (5 minutes before)
1. `./scripts/demo_check.sh` must end with `… passed, 0 failed`. If it doesn't, use the fallback laptop (below).
2. `./run_demo.sh`, then user menu → **Reset demo**. Check the demo clock reads **Sept 15**.
3. Browser zoom **100%** (⌘0). Close other tabs. Turn off notifications.
4. Open Ask once and click the first example, so the prepared answer loads instantly later.

## The click path

| # | Target time | Click | Say (one sentence) | If it breaks | Judge question most likely here → where the answer is |
|---|---|---|---|---|---|
| 1 | 0:00–0:45 | Today (home) | "A site manager opens this on Monday: it names the team whose operating numbers are running above comparable teams, and whose engagement fell at the same time." | Page blank → reload; still blank → fallback laptop | "How do you know it isn't noise?" → **Method** on "Needs your attention" (Poisson test p < 0.01, "too rare to judge") |
| 2 | 0:45–1:45 | **Investigate Night A** → Overview | "Late departures ran well above what comparable night teams predict, and 'materials and equipment' fell, even after adjusting for who answered the survey." | Chart missing → the stat cards above carry the same numbers | "Isn't that just who responded?" → the survey card note (adjusted for tenure mix) and the Evidence tab "Is the drop real?" |
| 3 | 1:45–2:30 | **Drivers** tab | "Across every team, that item moves with late departures. That's an association, not a cause, and we say so." | — | "How many things did you test?" → Insights: 65 pairs, "about 3 would light up by chance" |
| 4 | 2:30–3:00 | **Evidence** tab | "Four separate employees describe the same shift-handoff problem, and the directory says who owns that process." | — | "Can the AI make this up?" → comments are quoted from source; Trust › Architecture: the AI never produces numbers |
| 5 | 3:00–3:40 | **Create plan** tab → **Approve plan** (rust button) | "The tool drafts one plan; the manager edits it and approves it. Nothing happens without a person." | Approve fails → set the demo clock to Nov 30 and open **Impact**: it shows the seeded Night A plan's review | "Where is the human in the loop?" → rust means a person decides (legend in the sidebar) |
| 6 | 3:40–4:40 | **See if the plan worked** → **Fast-forward to the review date** | "At the review date, Night A is compared with similar teams that didn't act: late departures fell by this much more than theirs, with a 95% interval and a placebo check." | Fast-forward stuck → demo clock (top bar) → Nov 30 | "Is that causal?" → "Directional, not causal", and the follow-up months are synthetic (on screen). Placebo card |
| 7 | 4:40–5:00 | **What is this worth across sites?** (Business case) | "The buyer can replace every unit cost with their own; the value range and the board recompute." | — | "Where do these numbers come from?" → each cost shows its source or "Assumption"; pricing is labelled a hypothesis |

**Q&A only (not in the main path):**
- **Ask:** type or click an example. Scripted questions show "Prepared answer · generated … with gpt-5-mini ·
  Run live". Say so if asked. **Run live** takes about 10–20 s with the model; the progress steps show while
  it works.
- **Trust & method:** Quality (eval packs, first run vs now, holdout pending), Assumptions, Architecture
  (diagram and technique table), "You told us → we changed".
- **Data sources:** "every source here is a synthetic CSV; in a pilot the client uploads its own team-month
  file"; show the Template.

## Fallbacks
| Problem | Do this |
|---|---|
| Ask is slow (more than 20 s) or the network is down | Use the prepared answer (it's instant and labelled). With no key at all, Ask runs rules mode and says so. |
| The server dies | In the terminal: `./run_demo.sh` (a few seconds once `web/dist` exists). Keep a second terminal ready. |
| The laptop dies | Fallback laptop, cloned and checked the same morning with `scripts/demo_check.sh`. Last resort: `docs/overnight/before_after.html` screenshots (**judges penalise screenshots; use only if everything else fails**). |
| A plan was approved in rehearsal | User menu → **Reset demo**. |
| Wrong date showing | Top bar → demo clock → Sept 15. |

## Speaker handoffs (fill in names)
| Step | Speaker | Backup for Q&A |
|---|---|---|
| 1–2 | | |
| 3–4 | | |
| 5–6 | | |
| 7 + Q&A | | |
