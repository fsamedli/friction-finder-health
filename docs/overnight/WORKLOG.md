# Overnight work log (branch v0.7-saas-ui)

Re-read this file and `../../../My Notes/2026-09-23_Overnight_Agent_Prompt.md` after any context summary.
Farid's instructions (Sept 23, 23:40): finish the evening report first (done, top of MORNING_REPORT.md), then
run the overnight prompt without waiting. Don't redo finished phases: verify them and move on. Still write
the v1 parity checklist (v1 was deleted in 676ff54; reconstruct it from git history at 35791b0). Keep the SaaS
direction and look; Phase 3 refines it, it does not start over.

| Time | Step | Result | Next |
|---|---|---|---|
| 23:45 | Phase 0: branch `v0.7-saas-ui` from `2ff26f9`; WORKLOG and MORNING_REPORT created; verification captured in `docs/overnight/_verify/` | build ok, lint ok, pytest 90/92 with key (2 model-wording tests, pre-existing), 92/92 without key, evals 12/12 | Phase 1 check |
| 23:45 | Phase 1 (privacy fix): already done in `260d248`; verified | `tests/test_sql_guard.py` 18 passed; both bypass queries raise ValueError; evals 12/12 | Rule 6 fix on /api/sources, then Phase 2 |
| 00:05 | Rule 6: `/api/sources` statuses changed to `demo_csv` / `not_connected`; vendors read "Would connect to, e.g. …"; test added | 15/15 API tests; build and lint clean | Phase 2 |
| 00:20 | Phase 2: v1 served from worktree `004280d` on :8002 (no key); `playwright-core` driving installed Chrome; 28 screenshots in `screens/before/` (7 routes × 1440/390 × Sept 15/Nov 30); `report.json` alongside | 0 JS errors; v1 `/` overflows at 390 px (500 px wide) in both dates | Parity checklist |

## v1 parity checklist (from v1 source at `004280d`, `web/src/pages/*.tsx`)

The "Where in v2" column is filled in as items are verified. [x] = present in v2 and checked; [ ] = missing or not yet checked.

**Global**
- [x] As-of switch Sept 15 / Nov 30 → top bar "demo clock" dropdown
- [x] Site picker → top bar select (locked to Richmond in the Manager view, open in the HR view)
- [ ] Detect → Explain → Act → Prove loop visible as a narrative device (v1 header stepper) → **missing in v2**
- [ ] Colour legend "computed by code / needs a person" (v1 footer) → **missing as a legend**
- [ ] "Ranks obstacles, not managers." visible on the board (v1 footer) → only on Data sources in v2
- [x] Company "Northline Logistics (fictional) · synthetic data" → sidebar demo box and org chip

**Detect (v1 `/`)**
- [x] Headline sentence naming the team, the KPI, the excess and "engagement fell at the same time" → Today subtitle
- [x] Stat: excess operating cost with window → Today
- [ ] Stat: annualized excess ("if the pattern held for a year") → **missing in v2**
- [x] Stat: teams to look at → Today "Teams needing attention"
- [x] Stat: rolled up for privacy → Today sub-line and Teams table rows
- [x] "Where the excess sits" by KPI, count and $ → Today card
- [x] "How computed" method text (Poisson p < 0.01, item drop 0.30 + Welch/Bonferroni, too rare to judge, n < 4) → Method popover on Today
- [x] Every team listed with status, excess $, signal → Teams table
- [~] Per team: sparklines for late departures, absence days, **quits** with "too rare to judge" → v2 Teams table has late departures and absences only; **quits and the "too rare to judge" label are missing**
- [x] Per team: biggest item change in points, significance → Teams table
- [x] Rolled-up teams: "Fewer than 4 people … no one can be identified" → Teams table row
- [x] Click a team → explain page → Teams row → `/teams/:id`

**Explain (v1 `/why/4`)**
- [x] Headline: KPI ran N× comparable teams while items fell → Team detail subtitle
- [x] Status chip → Team detail title
- [x] Trend chart per KPI with KPI toggle, comparable-teams baseline, wave 1 and 2 marks, 3-month window shaded, unit "per 10 people per month" → Overview tab
- [x] Observed vs expected sentence with p and $ → Overview tab
- [x] Item changes wave 1 → wave 2 in points, n → Overview tab
- [x] Adjusted-for-who-responded note with p and the 0.0042 threshold → Overview tab
- [x] Linkage grid KPI × item → Insights page (full grid) and Drivers tab (pairs for this team)
- [x] "N pairs tested; about M would light up by chance" → Insights
- [x] Scatter of team-waves with this team highlighted and OLS line → Drivers tab and Insights
- [x] Quartile bars with % difference and n → Drivers tab and Insights
- [x] Slope, 95% CI, p, n sentence and OLS/cluster method → Drivers tab
- [x] "Association, not cause" → Drivers tab and Insights
- [x] Evidence: verdict label, "Is the drop real?" (signal check), operating detail, employee comments, process owner, reasons → Evidence tab
- [ ] Evidence card showing mode and seconds ("rules mode · 0s") → v2 shows a "Computed" badge but **no seconds**
- [x] Primary action "Draft a plan for this team" → header "Create action plan"
- [~] Suppressed team page with explanation → v2 has the explanation; **no "Back" button**

**Act (v1 `/plan/4`)**
- [x] Existing plan: obstacle, focus item, KPI to watch, numbered actions with owner and due date → Plan tab
- [x] "Approved by a person" chip → "Approved" badge
- [x] Start date and review date → Plan tab review card
- [x] "Did it work?" button and one-page report link → Plan tab
- [x] "Every other Monday, ten minutes" questions and the State of the Team note → Plan tab
- [x] Draft: editable obstacle and actions (text, owner, date), "Drafted from the evidence" and "Needs your decision" chips → Plan tab ("Needs a decision" badge)
- [x] Approve → saved → link to the review → header action switches to "See if the plan worked"
- [x] Teams under 4: plans at site level → suppressed team detail

**Prove (v1 `/proof/...`)**
- [x] Not reached: days to go, review date, Fast-forward button, "demo only … synthetic" note → Impact
- [x] Insufficient state → Impact
- [x] Worked headline: KPI fell X per 10 people a month more than comparable teams, $ a quarter, "directional, not causal" → Impact subtitle
- [x] Chart: team vs comparison, before/after shading, plan-start line → Impact
- [x] Verdict chip, estimate, 95% CI → Impact stats
- [x] Per quarter events and $ worth with unit cost → Impact stats
- [x] Method: difference-in-differences, Poisson SE, "worked only if the whole CI is below zero" → Impact Method popover
- [x] Before/after table (team, comparison, difference) → Impact
- [x] Placebo strip → Impact
- [x] Other KPIs with honest "inconclusive" and the note → Impact
- [x] "Oct–Nov synthetic" label → "Synthetic data" badge on the chart
- [x] Closing next step and link to the business case → Impact green banner

**Business case (v1 `/value`)**
- [x] 4 stats (turnover, injuries, value range, US warehousing sites) → Value
- [x] Unit costs editable, kind badge, source, note; validation; reset → Value
- [x] Assumption stated plainly; headcount slider → Value
- [x] Sector inputs with sources → Value
- [x] Who is who (user, buyer, data owners, pilot test) → Value pricing card

**Ask (v1 `/ask`)**
- [x] Question box, example chips → Ask
- [x] Mode chip, seconds, "verdict computed by code" → Ask
- [x] Brief: obstacle, evidence for/against with ids, missing, owner, proposed test → Ask
- [x] Approve / Reject / "This doesn't sound right" → recorded → Ask
- [x] Evidence register with computed/retrieved labels and "Show SQL" → Ask
- [x] Refused / out-of-scope message → Ask

**Under the hood (v1 `/hood`)**
- [x] Assumptions table and "with real data we would need" → Trust › Assumptions
- [x] Architecture diagram with code / model / person legend → Trust › Architecture
- [x] Eval results with confusion matrix; known-limit note → Trust › Evaluation
- [x] "You told us → we changed" table → Trust › feedback tab
- [x] "AI-assisted workflow, not autonomous agents" wording → Trust › Architecture

**Gaps to close in Phase 4:** loop narrative; colour legend; "ranks obstacles, not managers" on Detect; annualized stat; quits sparkline and "too rare to judge" in the Teams table; seconds on the Evidence tab; Back button on the suppressed team page.
