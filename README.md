# Friction Finder prototype (Group 4, DNSC 6317)

## v0.10 (Oct 27, 2026): money first, a checklist the manager can run, the questions as the path

The health variant is the product going forward. This round answers Prof. Hall's Oct 21 review (his notes:
`../2026-10-21_Prof_Hall_Feedback_for_Group_Chat.txt`; the teammate minutes read Oct 27; the contract all streams
worked to is `docs/specs/2026-10-27-prof-hall-round.md`). He praised the working demo, "showing money on the
dashboard", the five business questions, the editable plan and the before-and-after, and asked for four things:

- *"Approximately $1,700 appeared too small to demonstrate commercial value. Use a larger, credible scenario with
  clear assumptions about hospital size and time period... at least a five-digit impact figure."* → **Review** now
  leads with the verdict and three value tiers, each with its assumption and provenance one click away, full dollars
  everywhere (`app/impact.py` `value_of_plan`, `web/src/components/ValueTiers.tsx`). For the seeded plan at Nov 30:

  | Tier | Figure | Inputs (all shown on screen) |
  |---|---|---|
  | Measured, this unit, per year | $7,104 | late doses only (the established effect, 95% interval excludes zero): 44.4 avoided per quarter × 4 × $40 per dose (client-entered); absences and quits excluded because their intervals include zero |
  | Projected, this unit, if engagement recovers | $31,093 to $75,511 | 14 staff × 17.6% RN turnover (NSI 2026) = 2.46 separations a year × Gallup's top-vs-bottom quartile turnover gap (21% to 51%, Q12 meta-analysis 11th ed.) × $60,090 per separation (NSI); 0.52 to 1.26 separations avoided. Labelled "association, not cause"; a two-month pulse would confirm. Wave 2 (stream F) makes the low bound a return to the median |
  | At hospital scale (300 staff), per year | $228,270 to $588,810 | the Business case scenario: turnover falls 1 to 3 points, one days-away injury avoided ($48,000, NSC) |

  The unit's own associations are shown as the mechanism, not used in the figure: across 34 team-waves the q02
  item relates to late doses (slope −0.58 per head-month per point, 95% CI −0.91 to −0.25) and to quits (−0.043,
  CI −0.065 to −0.021), both clustered by team.
- *"Turn the plan into a checklist with tasks, responsible people, and due dates... A PDF export would be
  sufficient."* → every task has an id, a responsible person, a due date and a status; approval lands on
  **/plans/{id}**, the checklist page; ticks, edits and added tasks are saved with the time (`PATCH
  /api/plans/{id}/actions/{action_id}`, `POST /api/plans/{id}/actions`); the one-page report prints the checklist and
  the approval record, and the browser's print dialog is the PDF. After the draft the loop is explicit: **Approve
  plan**, or **Edit and regenerate** with a different obstacle (`POST /api/plans/regenerate`).
- *"The screen is too busy, with too much small text... make [the questions] prominent and consider using them to
  organize the workflow."* → the five questions are the numbered spine of Investigate (sticky rail with scroll-spy,
  one-sentence answers at 16.5 px, evidence behind "Show the evidence"); Today's headline and tiles are larger; the
  Journey and the guided demo follow his five steps: Today → Investigate → Plan → Checklist → Review.
- *"Which part of this is agentic, and where does the LLM make a decision?"* → the paragraph below, on the Trust
  page (Architecture tab) with a three-row table, and the **execution record**: when a plan is approved, code
  assigns owners (from the manager's edits, the plan owner or the ownership directory), schedules the review in the
  Due reviews queue, sets a KPI watch, and drafts one notice per owner (templated in rules mode; with a key the
  model rewrites them in the background and the text is swapped in only if a check passes: owners match the plan,
  every number is in the plan, under 140 words, no causal claim). **Nothing is sent**; the manager copies each
  notice. Pricing: 33 sourced benchmarks (`data/docs/pricing_benchmarks.json`; note in
  `../My Notes/2026-10-27_Hospital_Ops_Software_Pricing_Benchmarks.md`) sit on the Business case page next to the
  hypothesis.

**The agentic answer, in one paragraph.** Friction Finder is an AI-assisted workflow, not an autonomous agent.
Code detects (Poisson excess vs comparable units), adjusts (tenure-mix shift-share), links (OLS, clustered by team)
and proves (difference-in-differences with a placebo). The language model makes two kinds of decisions, both
bounded: in the investigation it chooses which of eleven read-only checks to run next (function calling, budget of
6 tool calls, 8 requests, 60 seconds), and it writes the brief, the plan draft and the owner notices from the
numbers code handed it; a code check rejects any sentence whose numbers, team or period are not in the cited
evidence. It never writes SQL, never sets a verdict, never sends anything. The nurse manager edits and approves;
after approval the system assigns owners, schedules the review and drafts the notices, and the manager sends them.
Using a coding agent to build the software does not make the product agentic, and we do not call it one.

**Demo (5 to 7 minutes; time limit unconfirmed):** `docs/demo/DEMO_SCRIPT.md`. **Gate, Oct 27 (keyless):** build,
lint, pytest 145 passed, gold 13/13, adversarial 15/15, investigation 16/16, demo_check 356 passed / 0 failed at
1440 and 390 px, axe 0 violations (`docs/overnight/v0.10/_verify/wave1_*.txt`). Wave 2 (same day, in progress when
this was written): a plan that needed revision next to the one that worked (planted P14; stream D), the demo script
and docs (E), and polish (F: synthetic-name dedupe, a hospital-scale tile on Today, the report printing the tiers,
the $4,000 per hospital per month pricing hypothesis from the benchmarks). Prepared answers for this variant still
need `scripts/prepare_investigations.py`.

## v0.9-health (Oct 8, 2026): the same product on a fictional hospital system

Branch `v0.9-health`, a full copy of v0.8 (commit `3e95fe4`) with the industry story changed and nothing
structural touched. **Why:** Gallup's publicized client base is heavy on hospital systems and thin on logistics,
the Gallup judge's own example of linking engagement to operations was patient safety for a hospital, and one
final judge is from HR (research: `My Notes/2026-10-08_Gallup_Client_Base_Research.md`). The contract all three
build agents worked to is `docs/specs/2026-10-08-healthcare-variant.md`; read it first.

- **Company:** Lanford Health (fictional), three hospitals (Lanford, Westbrook, Pine Hollow), eight unit teams
  per hospital (Med-Surg Day, Telemetry Day, ED Day, Med-Surg Night, ICU Night, Resp Therapy Day, Pharmacy Day,
  EVS Night), Day and Night shifts. Same team ids, headcounts, survey waves, seeds and planted patterns P1–P13.
- **User:** the unit nurse manager (and charge nurse). **Buyer:** the Chief Nursing Officer and HR / people
  analytics. **Data owners:** HR (survey export), pharmacy and nursing informatics (eMAR export), timekeeping,
  HRIS, employee health.
- **Operating metrics** (`app/metrics.py`): late medication doses (`late_doses`, eMAR export), unplanned absence
  days, voluntary separations, staff injuries with days away, unplanned overtime shifts (`overtime_shifts`,
  timekeeping), plus the share of doses given late by hour band. **No patient-level data, by design:** every
  record is a count at unit, shift or site level, so HIPAA is out of scope (nothing identifies a patient).
- **The planted obstacle:** pharmacy restocks the Med-Surg automated dispensing cabinet at 07:00, after the
  06:00 medication pass (the SOP says by 05:00); owner, the Pharmacy Operations Manager. The competing
  explanation is a March RN staffing shortage that ends before the rise.
- **Unit costs and segment facts** are sourced or labelled assumption / client-entered on the Business case page
  (`data/generate_impact.py`, `app/impact.py`); no figure is typed into the web app or this README.
- **Ports:** `run_demo.sh` on **8001** (so the v0.8 demo in `../prototype` can run on 8000 at the same time);
  `scripts/demo_check.sh` on 8020; `scripts/gate.sh` a11y on 8021, output in `docs/overnight/v0.9-health/_verify/`.

```bash
cd web && npm run build && cd ..   # run_demo.sh builds only when web/dist is missing
./run_demo.sh                      # http://127.0.0.1:8001, then user menu > Reset demo, demo clock Sept 15
./scripts/gate.sh                  # every check, keyless, raw output in docs/overnight/v0.9-health/_verify/
```

**Demo path (about 4 minutes, no model call until step 6). Start with Reset demo, clock on Sept 15.** The
Business case page computes $228K-$589K per 300-person hospital per year from the sourced unit costs (first
v0.9-health gate run, Oct 8, 2026; RN turnover at $60,090 per quit drives most of it, so say so if asked).
1. **Today** (`/`): "Med-Surg Night needs attention": late doses observed vs expected from comparable night
   teams (Poisson test), and "Materials and equipment" fell between the waves, adjusted for who responded.
2. **Investigate Med-Surg Night** (`/investigate/4`): Is it real (trend vs comparable teams, survey change
   adjusted for tenure mix), Is this normal for teams like ours, What explains it (ranked explanations; Q02 x
   late doses across reportable team-waves; staff comments on the cabinet restock; the process owner), What is
   missing, What do I do.
3. **Draft a plan** → edit → **Approve plan** (focus item Q02, KPI late doses, owner the Pharmacy Operations
   Manager, starts Sept 21, review Nov 30).
4. **See if the plan worked** → countdown → **Fast-forward to the review date** → Review: improved, deteriorated
   or inconclusive, with the 95% interval, a placebo check, and the other KPIs reported as they are. Follow-up
   months are synthetic.
5. **Business case** (`/value`): unit costs for late dose, overtime shift, absence day, quit and injury, each
   sourced, an assumption with its formula, or client-entered; $228K-$589K per 300-person hospital per year
   on the Oct 8, 2026 data; pricing shown as a hypothesis.
6. **Ask** (`/ask`): the investigation panel full width; `/ask?view=brief` for the one-page brief with the
   progress stepper, "N of N numbers checked against the evidence", step trace, evidence register with the SQL.
   Prepared answers must be regenerated for this variant (`scripts/prepare_answers.py`,
   `scripts/prepare_investigations.py`); until then these questions run live.
7. **Trust & method** (`/trust`), **Insights** (`/insights`), **Data sources** (`/data`) for Q&A.

The same path runs as a guided walkthrough: top bar → **Start demo**. Full script with fallbacks:
`docs/demo/DEMO_SCRIPT.md`. Healthcare-specific risks: `docs/risk/TEVV_EVIDENCE.md`.

Scripted Ask questions (the web app's example chips; `scripts/prepare_answers.py` must use the same strings):
"Why did the Lanford night shift's scores drop and why are doses late?", "Did the Westbrook Telemetry Day team
really decline?", "Who owns the medication cabinet restock schedule at Lanford?", and the decline case "Why did
the Denver site drop?".

## v0.8 (Oct 8, 2026): manager-first screens and a bounded AI-assisted investigation

Branch `v0.8-investigate`. What changed and why: `docs/overnight/v0.8/MORNING_REPORT.md`. Research behind the
choices: `docs/research/2026-10-08_Gallup_Access_Overlap.md` (what Gallup Access already does; what this adds).
Both were written for the logistics variant and are kept as history.

- **Screens:** Today → Investigate → Action plans → Review; Workspace: Insights, Data sources, Business case,
  Trust & method. Old URLs (`/teams`, `/impact`, `/why`, `/plan`, `/proof`, `/hood`) redirect.
- **Today** names one team, why it matters in operating terms, and one rust button. **Investigate** is organised
  by the manager's questions. **Review** leads with improved / deteriorated / inconclusive (directional, not causal).
- **Investigation panel** (on the Investigate screen; full width at `/ask`): one coordinator (`app/investigate.py`)
  lets the model choose which of 11 read-only tools (`app/tools.py`) runs next, by function calling, under a budget
  of 6 tool calls, 8 model requests and 60 s. Code computes every number and sets the evidence state (supported,
  mixed, insufficient, unavailable). A code self-check rejects any model wording whose numbers, team or period are
  not in the cited evidence. Keyless, fixed plans per question give the same output shape.
- **Operating metrics** have one definition (`app/metrics.py`) used by the dashboards, Ask and the tools; Ask
  answers questions on every operating KPI. The model writes no SQL.
- **Plans:** drafts, an existing-plan check, double-submission guard, approvals logged with edits and time.
- **Evals (v0.8 data):** gold 13/13 (first run 12/13), adversarial 15/15, investigation pack 16/16 keyless (first
  run 11/16), all rules mode, all written during development. Run `python -m evals.investigate.run --no-model`.
  The packs are being re-pointed at the hospital data; results for this variant land in `evals/**/results/`.

## Version history (v0.2 to v0.7, written for the logistics variant; company and team names removed here)

**v0.6 (Sept 23, 2026): detect → explain → act → prove.** Branch `v0.6-detect-explain-act-prove`. Spec and plan:
`docs/specs/2026-09-23-detect-explain-act-prove-*.md` (historical, logistics names). Why: Gallup Access already
shows what moved and has AI action planning; the gap Gallup named (Keegan, Sept 18) is linking engagement to the
client's own operating data, which Gallup sells today as a once-a-year Business Impact Analysis. v0.6 does that
monthly, per team, and checks whether the fix worked. Development: `.venv/bin/uvicorn api.main:app --reload` and,
in `web/`, `npm run dev` (proxies /api to the API port).

**v0.6.1 (Sept 23 evening): the app is a SaaS product.** Left sidebar, top bar with site switcher, a **demo
clock** (Sept 15 = wave 2 results arrive; Nov 30 = review date), Manager/HR-leader role switch, notifications,
and "Reset demo" in the user menu (removes plans approved in the app and edited unit costs).

**v0.7 (overnight Sept 23–24, branch `v0.7-saas-ui`):** colour roles (teal = computed, rust = needs a person's
decision, purple = AI-written and checked; legend in the sidebar), the v1 logo mark back, a journey strip, a
**Start demo** button (a 4-step guided walkthrough with one sentence of narration per step), "Demo CSV
(synthetic)" on every data source. Before/after screenshots: `docs/overnight/before_after.html`. Brand tokens:
`docs/design/brand.md`.

**v0.7 Part 2 (overnight Sept 24):** `./scripts/demo_check.sh` before every rehearsal (walks the demo at 1440 and
390 px against a keyless private server and a scratch cache; fails on any console error, failed API call, missing
number or label, or horizontal scroll). Ask: scripted questions return **prepared answers** generated once with
gpt-5-mini, labelled with time and model, plus **Run live**. Evals: gold, **adversarial** (`evals/adversarial/`,
15 cases; first run 10/15 → 15/15 after the fix), and a **holdout kit** (`evals/holdout/`, empty). "Useful?" on
briefs and plans; `?study=1` usability mode, SUS page and `scripts/score_study.py`
(`docs/usability/PROTOCOL.md`); print-ready one-page report per plan (`/api/report/<plan>`); CSV export on
every table; team-month operating-data upload. 0 axe-core WCAG A/AA violations on 13 routes
(`node web/scripts/a11y.mjs`); first-load JS about 300 kB; pages lazy-load.

SQL guard: `app/db.py` parses every query with sqlglot; all tables must be allowlisted, table functions are
refused (tests: `tests/test_sql_guard.py`). Methods (all in `app/impact.py`, no model): Poisson excess vs pooled
comparable-team rate (p < 0.01, "too rare to judge" below 3 expected events); item change adjusted for tenure
mix with a Welch t-test, Bonferroni over 12 items; OLS with team-clustered SEs and Gallup-style quartile
comparison; difference-in-differences with Poisson SEs and a placebo run. Tests: `tests/test_impact*.py`,
`tests/test_api.py`.

**Version 0.2, Sept 17, 2026.** Built for the second round of judge meeting 1 (Fri Sept 18: Ethirajan, Fullowan,
Jamshidi, Keegan). Version 0.1 (Sept 14) is the previous git commit. Helps a front-line manager decide **which
obstacle to test first** after an engagement score falls, by answering *where did we drop, is it real, what is
behind it, who owns it, what do we do* from survey aggregates, operational records, procedures, and open-text
comments. Everything in `data/` is synthetic; the company does not exist. Planted patterns are listed in
`data/generated/truth.json` and explained in `DATA_SPEC.md` so the assistant can be scored. Design history:
`SPEC.md`.

Run (v0.2, Streamlit; superseded by `run_demo.sh`):
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then put the GW-provided key in .env (never in code or chat)
.venv/bin/python data/generate.py
.venv/bin/python -m app.probe   # confirms which deployments the GW Azure resource exposes
.venv/bin/streamlit run app/ui.py
```
The model is the GW-assigned Azure OpenAI resource (`gw-sb-04`), deployments `gpt-5-mini` for chat and
`text-embedding-3-small` for embeddings. Without a key the app still runs: rule-based scoping, keyword retrieval,
templated text. With the key: the model reads the question into a schema, embeddings power retrieval, and the
model writes the brief and the action items from the evidence it is handed. Every number still comes from SQL
and Python.

Check (any version):
```bash
.venv/bin/python -m pytest tests -q               # data patterns, suppression, numbers, verdicts, checks, plan, report, log
.venv/bin/python -m evals.run_evals               # gold questions, confusion matrix, saved to evals/results/
.venv/bin/python -m evals.run_evals --no-model    # rules mode
.venv/bin/python -m app.cli "Why did the Lanford night shift's scores drop and why are doses late?"
```

**Three features on one screen (v0.3, Sept 17 evening):** Diagnose (site overview, then the evidence brief for one
team: likely obstacle, evidence for and against, what is missing, the process owner from the directory, a
proposed 30-day test; "Show me" reveals the SQL and rows behind every number). Check the signal (did the team
really decline, or did different people respond? a shift-share adjustment by tenure band). Act and review (for a
supported verdict only: a plan in Gallup's State of the Team shape, a one-page HTML report and a Markdown brief).
Plus CSV upload of operational records, approve / reject / flag with a review log, evals with a confusion matrix
and model comparison, the data specification, and a table of what each judge said and what changed because of it.

**Rules the code enforces (unchanged since v0.2):**
- **Minimum n is 4.** Team-level means and who-responded breakdowns are NULL or omitted below that, in the SQL
  views and in code, before any model call. Comments from those team-waves are never indexed.
- **The model never queries respondent rows.** `run_sql` allows only the views and a short list of tables, and
  only single SELECT statements.
- **The verdict is computed, not generated.** An item must fall 0.30 or more; an hour-band late rate must rise
  5 points and 1.5x; a comment theme must have 3 or more separate comments to corroborate; staffing under 90% is
  a competing explanation. Survey alone = "insufficient evidence", no owner, no test.
- **The brief is checked.** Every citation must exist, every number must appear in the evidence, causal language
  is rejected, the owner must be the directory's owner when supported and "Not assigned" otherwise.
- **Team-level results are watch items.** Inference belongs at site level.
- **No action without a person.** A person approves, rejects, or flags; the plan is a draft until then.
- GW-provided OpenAI API only, via `.env`. No fine-tuning. The key never leaves the laptop.

## Layout

```
app/config.py        .env, model names, threshold
app/db.py            DuckDB, suppressed views, guarded run_sql, CSV upload
app/metrics.py       one definition per operating metric (late doses, absence days, quits, injuries, overtime shifts)
app/impact.py        detect / explain / prove: Poisson excess, OLS, DiD; unit costs and the value case
app/investigate.py   the bounded investigation loop; app/tools.py the read-only tool registry
app/retrieval.py     document and comment chunks; embeddings or keyword search
app/agent.py         Ask: scope, analyze, retrieve, assess, explain; plan, reports, approve/flag, review log
api/main.py          FastAPI; serves web/dist
web/                 React app (Today, Investigate, Action plans, Review, Insights, Data sources, Business case, Trust & method)
data/generate.py     synthetic hospital system with planted patterns P1-P13; writes data/generated, data/docs, DATA_SPEC.md
data/docs/           illustrative SOPs (cabinet restock, nurse staffing), ownership directory, Gallup's item questions (quoted, attributed)
evals/               gold, adversarial, investigation and holdout packs; results/
tests/               pytest
docs/                architecture, how it works, demo script, brand, risk (TEVV), usability kit, specs, overnight history
```
