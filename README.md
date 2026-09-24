# Friction Finder prototype (Group 4, DNSC 6317)

## v0.6 (Sept 23, 2026): detect → explain → act → prove

Branch `v0.6-detect-explain-act-prove`. Spec and plan: `docs/specs/2026-09-23-detect-explain-act-prove-*.md`.
Why: Gallup Access already shows what moved and has AI action planning; the gap Gallup named (Keegan,
Sept 18) is linking engagement to the client's own operating data, which Gallup sells today as a
once-a-year Business Impact Analysis. v0.6 does that monthly, per team, and checks whether the fix worked.

```bash
./run_demo.sh            # builds web/ if needed, starts FastAPI on :8000, opens the browser
```

Development: `.venv/bin/uvicorn api.main:app --reload` and, in `web/`, `npm run dev` (proxies /api to :8000).

**v0.6.1 (Sept 23 evening): the app is a SaaS product.** Left sidebar (Today, Teams, Action plans, Impact,
Insights, Ask; Data sources, Business case, Trust & method), top bar with site switcher, a **demo clock**
(Sept 15 = wave 2 results arrive; Nov 30 = review date), Manager/HR-leader role switch, notifications,
and "Reset demo" in the user menu (removes plans approved in the app and edited unit costs).

**v0.7 (overnight Sept 23–24, branch `v0.7-saas-ui`):** colour roles (teal = computed, rust = needs a
person's decision, purple = AI-written and checked; legend in the sidebar), the v1 logo mark back, a
Detect → Explain → Act → Prove journey strip, a **Start demo** button in the top bar (a 4-step guided
walkthrough with one sentence of narration per step), "Demo CSV (synthetic)" on every data source.
Before/after screenshots: `docs/overnight/before_after.html`. Brand tokens: `docs/design/brand.md`.

**Demo path (about 4 minutes, no model call until step 6). Start with Reset demo, clock on Sept 15:**
1. **Today** (`/`): "Night A needs attention: late departures are running 1.6x what comparable teams would
   predict, and engagement fell at the same time." 81 observed vs 51 expected (Poisson p < 0.001).
2. **Investigate Night A** (`/teams/4`): Overview (trend vs comparable teams, survey change adjusted for who
   responded), Drivers (Q02 x late departures across 34 team-waves, quartile comparison), Evidence
   (verdict, signal check, employee comments, process owner).
3. **Create action plan** tab -> **Approve plan** (focus item Q02, starts Sept 21, review Nov 30).
4. **See if the plan worked** -> "76 days" -> **Fast-forward to the review date** -> Impact: it worked,
   -10.6 late departures per 10 people a month vs comparable teams (95% CI -16.7 to -4.4), about $6,653 a
   quarter; placebo check; absences and quits honestly inconclusive. Follow-up months are synthetic.
5. **Business case** (`/value`): sourced unit costs, editable; $80K-$144K per 300-person site per year;
   pricing shown as a hypothesis.
6. **Ask** (`/ask`): model mode ~15 s; progress stepper, "N of N numbers checked against the evidence",
   step trace with real timings, evidence register with the SQL.
7. **Trust & method** (`/trust`), **Insights** (`/insights`), **Data sources** (`/data`) for Q&A.

Old v0.6 URLs (`/why/4`, `/plan/4`, `/proof/...`, `/hood`) redirect to the new screens.
SQL guard: `app/db.py` parses every query with sqlglot; all tables must be allowlisted, table functions are
refused (tests: `tests/test_sql_guard.py`).

Methods (all in `app/impact.py`, no model): Poisson excess vs pooled comparable-team rate (p < 0.01,
"too rare to judge" below 3 expected events); item change adjusted for tenure mix with a Welch t-test,
Bonferroni over 12 items; OLS with team-clustered SEs and Gallup-style quartile comparison;
difference-in-differences with Poisson SEs and a placebo run. Tests: `tests/test_impact*.py`, `tests/test_api.py`.

---

Version 0.2, Sept 17, 2026. Built for the second round of judge meeting 1 (Fri Sept 18: Ethirajan,
Fullowan, Jamshidi, Keegan). Version 0.1 (Sept 14) is the previous git commit.

Helps a **site or shift manager** decide **which obstacle to test first** after an engagement score
falls, by answering *where did we drop, is it real, what is behind it, who owns it, what do we do*
from survey aggregates, operational records, procedures, and open-text comments. Starting segment:
operations-heavy workplaces where daily work is logged (warehouses, logistics, call centers).

Everything in `data/` is synthetic. Northline Logistics does not exist. Planted patterns are
listed in `data/generated/truth.json` and explained in `DATA_SPEC.md` so the assistant can be
scored. Design history: `SPEC.md`.

## Run it

```bash
cd prototype
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then put the GW-provided key in .env (never in code or chat)
.venv/bin/python data/generate.py
.venv/bin/python -m app.probe   # confirms which deployments the GW Azure resource exposes
.venv/bin/streamlit run app/ui.py
```

The model is the GW-assigned Azure OpenAI resource (`gw-sb-04`), deployments `gpt-5-mini` for
chat and `text-embedding-3-small` for embeddings. Without a key the app still runs: rule-based
scoping, keyword retrieval, templated text. With the key: the model reads the question into a
schema, embeddings power retrieval, and the model writes the brief and the action items from the
evidence it is handed. Every number still comes from SQL and Python. The main question takes
about 30 seconds with gpt-5-mini (about 60 with gpt-5); under a second without a model.

## Check it

```bash
.venv/bin/python -m pytest tests -q               # 32 tests: data patterns, suppression, numbers, verdicts, checks, plan, report, log
.venv/bin/python -m evals.run_evals               # 12 gold questions, confusion matrix, saved to evals/results/
.venv/bin/python -m evals.run_evals --model gpt-5 # same questions on another deployment, for the comparison
.venv/bin/python -m evals.run_evals --no-model    # rules mode
.venv/bin/python -m app.cli "Why did the Richmond night shift's scores drop and why are deliveries late?"
```

## The screen (v0.3, Sept 17 evening): a decision memo, not a dashboard

The business answer comes first: a headline verdict in plain language, four computed tiles (what
fell, the operational rate, comments on the theme, respondents), then "What we found" beside
"What to do on Monday" (the process owner from the directory, the proposed test, and the human
decision: approve, reject, flag, download). Charts, the action plan, the signal check, and the
technical appendix (evidence register and the SQL behind every number) sit in tabs underneath.
Brand: slate ink on warm paper, teal for what code computed, orange for what needs a person;
Fraunces for headlines, Source Sans 3 for text (loaded from Google Fonts; falls back to Georgia
and Calibri offline). Theme lives in `.streamlit/config.toml`.

## Three features on one screen

1. **Diagnose.** Site overview (which teams moved, which are hidden under n<4, strength and two
   opportunities vs the company), then the evidence brief for one team: likely obstacle, evidence
   for and against, what is missing, the process owner from the directory, a proposed 30-day test.
   "Show me" reveals the SQL and rows behind every number.
2. **Check the signal.** Did the team really decline, or did different people respond? A
   shift-share adjustment holds each tenure band at its company-wide mean and reports how much of
   the change the mix explains; the remainder is judged against a threshold. Tenure chart shows the
   year-one effect.
3. **Act and review.** For a supported verdict only: a plan in Gallup's State of the Team shape
   (one performance goal, one focus item, three or four actions with owners and dates, a review
   cadence, and the item's discussion questions quoted verbatim from Gallup's outline), plus a
   one-page HTML report and a Markdown brief.

Plus: CSV upload of operational records, approve / reject / flag with a review log, evals with a
confusion matrix and model comparison, the data specification, and a table of what each judge
said and what changed because of it.

## Rules the code enforces

- **Minimum n is 4.** Team-level means and who-responded breakdowns are NULL or omitted below
  that, in the SQL views and in code, before any model call. Comments from those team-waves are
  never indexed.
- **The model never queries respondent rows.** `run_sql` allows only the views and a short list
  of tables, and only single SELECT statements.
- **The verdict is computed, not generated.** An item must fall 0.30 or more; a late-departure
  band must rise 5 points and 1.5x; a comment theme must have 3 or more separate comments to
  corroborate; staffing under 90% is a competing explanation. Survey alone = "insufficient
  evidence", no owner, no test. No material fall = "no material change".
- **The brief is checked.** Every citation must exist, every number must appear in the evidence,
  causal language is rejected, the owner must be the directory's owner when supported and "Not
  assigned" otherwise. Two failures and the templated brief is shown, labelled.
- **Team-level results are watch items.** Inference belongs at site level (n about 50 here).
- **No autonomous action.** A person approves, rejects, or flags; the plan is a draft until then.
- GW-provided OpenAI API only, via `.env`. No fine-tuning. The key never leaves the laptop.

## Layout

```
app/config.py     .env, model names, threshold
app/db.py         DuckDB, suppressed views, guarded run_sql, CSV upload
app/retrieval.py  document and comment chunks; embeddings or keyword search
app/agent.py      scope, analyze, retrieve, assess, explain; plan, reports, approve/flag, review log
app/ui.py         Streamlit screen (playbook, tabs, footer panels)
app/cli.py        command-line runner
data/generate.py  synthetic company with planted patterns P1-P10; writes data/generated, data/docs, DATA_SPEC.md
data/docs/        illustrative SOPs plus Gallup's item questions (quoted, attributed)
evals/            questions.json, run_evals.py, results/
tests/            pytest
```
