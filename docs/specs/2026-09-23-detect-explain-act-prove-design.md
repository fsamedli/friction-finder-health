# Friction Finder v0.6: detect → explain → act → prove

Design spec, Sept 23, 2026. Owner: Farid. Branch `v0.6-detect-explain-act-prove`.
Rationale and sources: `../../../My Notes/2026-09-23_Product_Edge_Research.md`.

## 1. Why this version exists

Gallup Access already shows managers what moved and has AI action planning (Gallup AI). The gap
Gallup named (Keegan, Sept 18) is linking engagement to the client's own operating data. Today
Gallup does that by hand as Business Impact Analysis, a once-a-year consulting deck. No
manager-facing tool we found checks whether a fix moved an operating number.

v0.6 turns the prototype from "ask a question, get a brief" into a four-step loop for one site:

1. **Detect.** Which team is costing this site money right now, in dollars?
2. **Explain.** Which engagement items move with which operating KPIs, and what is behind this
   team's drop?
3. **Act.** One-card plan in Gallup's State of the Team shape, with an owner and a review date.
   The manager approves it.
4. **Prove.** At the review date, did the operating number move for this team compared with
   similar teams that did not act?

The v0.5 question box stays as the drill-down ("Ask"). RAG and text-to-SQL improvements come later.

## 2. Demo success test (verifiable, laptop, one command)

`./run_demo.sh` starts one process (FastAPI serving the built React app) and the browser opens.
Without an API key, everything below except "Ask" still works, and it answers in under 1 second.

1. **Site board.**
   - Header: "Richmond: $X excess cost this quarter," with a breakdown.
   - Team grid: Richmond Night A shows red, with its excess dollars, KPI sparklines and engagement
     change.
   - Teams under n=4 show as "rolled up to site," with no scores.
2. **Why (Night A).**
   - Late departures and absences rose from June. Q02 (materials and equipment) and Q07 fell.
   - Linkage panel: top vs bottom quartile teams on each KPI (Gallup's own method), plus an
     association table with an estimate, 95% CI and n. Labeled "association, not cause."
   - The v0.5 signal check (response-mix adjustment) and comment evidence are shown.
3. **Plan.** One card: focus item, three actions with owners and dates, review date 60 days out.
   Approve / edit / reject go to the review log. Download as a one-page report.
4. **Did it work.**
   - Night A before vs after compared with other night teams, as a difference-in-differences
     estimate with a CI.
   - Converted to dollars. Verdict: worked / inconclusive / no effect.
   - Labeled "directional, not causal; synthetic follow-up data."
5. **Business case.**
   - Editable unit costs, each with its source.
   - Per-site annual value range recomputes live.
6. **Under the hood.** Assumptions (company size, response rate, waves, min n, first-year
   effect), architecture, eval results, the SQL behind each number, and a "what judges told us →
   what changed" table.
7. **Ask.** The v0.5 question → brief flow, unchanged in logic, rendered in the new UI.

## 3. Data (extend; do not break v0.5)

New outputs from `data/generate.py`. Existing files, tests and evals stay valid.

- `team_ops_monthly.csv`: month × team, Jan–Nov 2026. Columns: `headcount, absence_days,
  late_departures, quits, injuries, rework`.
- Planted patterns, added to `truth.json`:
  - **P9.** Richmond Night A: absences, late departures and quits are elevated Jun–Sep and
    consistent with P3/P4. After the plan starts on Sept 21, they fall in Oct–Nov. Comparison
    night teams stay flat.
  - **P10.** Across teams, lower Q02 goes with more late departures and rework, and a lower grand
    mean goes with more absences. The effects are modest and noisy, and only a few survive the CI.
    One KPI–item pair is planted as **null** so the tool must show "no association."
- `unit_costs.json`: each value has a source and a note.
  - Replacement cost: $10,704. CAP 2012, 20% of $53,518 (BLS $25.73/hr × 2,080). Floor: SHRM $5,475.
  - Injury (days-away case): $48,000. NSC 2024; an upper bound because it includes societal cost.
  - Absence day: $205.84. **Assumption:** one day's pay, 8 × $25.73.
  - Late departure: no sourced cost. Shown as a count only; the buyer can enter a value.
- Accepted plans are stored in `plans.jsonl`, next to `approvals.jsonl`. The demo ships with the
  Night A plan pre-seeded, dated Sept 21, 2026, review Nov 20, 2026. The demo can also create a
  new plan live.

## 4. Analytics module: `app/impact.py` (pure functions, no model calls)

- `excess_cost(team, quarter)`: team KPI rate minus the site baseline rate (the median of other
  teams on the same shift), × headcount × unit cost. Only positive excess counts.
- `status(team)`: red / amber / green from excess cost and engagement change. The thresholds are
  constants with a comment explaining them.
- `quartile_link(kpi)`: splits reportable teams into quartiles by grand mean (or by an item) and
  returns the median KPI rate for the top vs bottom quartile, the percent difference and n.
  Mirrors the Gallup meta-analysis presentation.
- `association(kpi, item)`: statsmodels OLS of the team-wave KPI rate on the item mean, with a
  robust SE and a 95% CI. Returns n. With 24 teams × 2 waves minus suppressed cells, the n is
  small, and the output says so.
- `did(team, metric, start, review, comparison)`: difference-in-differences of monthly rates,
  treated vs comparison teams. Returns the estimate, CI (bootstrap over comparison teams) and
  dollars. The verdict is "worked" only if the CI excludes zero in the helpful direction.
- **Suppression.** Any output that joins survey values to a team requires n ≥ 4 (MIN_N) for that
  team-wave. Operating-only views are not suppressed, but they never show individual rows.
- **Not a manager ranking.** The board ranks obstacles and teams by cost. It exposes no manager
  scorecard. The UI says so.

## 5. API: `api/main.py` (FastAPI)

Endpoints return plain JSON built from dataclasses:
- `GET /api/sites`
- `GET /api/board?site=`
- `GET /api/team/{id}/why`
- `GET /api/link?kpi=&item=`
- `GET/POST /api/plans`
- `GET /api/plans/{id}/result`
- `GET/PUT /api/costs`
- `GET /api/assumptions`
- `GET /api/evals/latest`
- `POST /api/ask`, which wraps `agent.run`
- `POST /api/approve`
- `GET /api/report/{plan_id}`, which returns HTML
- `POST /api/upload`, which takes a CSV

It also serves `web/dist` at `/`.

## 6. Frontend: `web/` (Vite + React + TypeScript + Tailwind + Recharts)

- Brand carried over from v0.5: slate ink on warm paper; teal = computed by code; orange = needs a
  person. Fraunces for headlines, Source Sans 3 for text.
- Left rail with six steps (Board, Why, Plan, Did it work, Business case, Under the hood) plus Ask.
- The top bar shows the site picker and the "as of" date. Every number has a "how computed"
  popover.
- Built once (`npm run build`). The demo does not need the Node dev server.

## 7. Judge feedback this answers

| Who, when | Said | Where v0.6 answers it |
|---|---|---|
| Keegan, Sept 18 | Gap is the link to business operations; action planning must be effortless | Why / linkage; one-card Plan |
| Jamshidi, Sept 18 | Start from KPIs the manager cares about, one signal; pricing; feedback loop | Site board; Business case; plan feedback |
| Fullowan, Sept 14/18 | Human in the loop, spot-checking with numbers; state assumptions up front | Approve log; Under the hood assumptions |
| Kaznachey, Sept 16 | Not "agents," not "eliminates hallucinations" | Copy uses "AI-assisted workflow" |
| Rubric | Several features, charts, metrics, tables, upload, doc generation | All pages |

## 8. Testing

- `tests/test_impact.py`:
  - P9 is recovered: Night A is red, and its DiD CI excludes zero in the helpful direction.
  - A comparison team's DiD is inconclusive.
  - P10 finds the planted association and reports the null pair as null.
  - Suppression holds on joined outputs.
  - Excess cost is never negative.
- `tests/test_api.py`: FastAPI TestClient; every endpoint returns 200 with the expected keys, and
  the suppressed team has no score fields.
- Existing 32 tests and 12 evals must still pass.
- Visual check in Chrome before calling it done.

## 9. Out of scope for v0.6

RAG and text-to-SQL upgrades, the sqlglot guard (logged in My Notes, separate fix), auth and
roles, multi-client support, real Gallup data, and the mobile layout beyond "doesn't break."
