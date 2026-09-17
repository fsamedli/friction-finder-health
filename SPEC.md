# Friction Finder prototype: design spec

Version 0.1, Sept 14, 2026. Owner: Farid (Product and AI lead). Status: approved for a
four-day build to show O'Neal Keegan (Gallup) on Friday, Sept 18, 2026, 2:30 PM.

This is a spike for judge meeting 2, not the final backend. Tatenda owns the platform lane;
this code exists so the team has something running to react to.

## 1. Purpose

An assistant for an HR or operations leader at a Gallup client who sees a team's Q12 score
drop and has to work out the likely obstacle and who owns the fix. It joins three sources a
manager cannot join by hand in an afternoon: survey aggregates, operational records, and
documents. It writes a cited one-page brief. A person approves it. It declines when the data
cannot answer.

## 2. Friday success test (verifiable)

Running on Farid's laptop in a browser, with the GW-provided OpenAI key in `.env`:

1. Question: "Why did the Richmond night shift's scores drop and why are deliveries late?"
   Output: a chart, an evidence table, and a brief with likely obstacle, evidence for, evidence
   against, what is missing, the named process owner, and a proposed test. Every number has a
   "show me" that reveals the SQL and the rows it came from.
2. Question about a team with fewer than four respondents. Output: suppressed, rolled up to
   the site level, with a sentence saying why. (Keegan's first open question.)
3. Upload a CSV of delay records. Output: the records appear in the operational evidence for
   the next question. (Keegan's second open question.)
4. Question the data cannot answer ("Why did the Denver site drop?" or "What caused
   turnover?"). Output: a decline with a reason, no invented numbers.
5. Approve or reject the brief. Output: the decision, note, and brief are appended to
   `approvals.jsonl`.
6. Evals tab: eight gold questions run against the truth file; found, missed, and
   refused-correctly are shown.

If the key or network fails during the demo, a templated brief built from the same evidence
takes over, and the screen says so.

## 3. In scope and out of scope

In: synthetic data with planted patterns and a truth file; DuckDB views with suppression;
scope, analyze, retrieve, explain, approve as five plain functions; OpenAI tool calling for
scope and explain; embeddings plus cosine similarity for retrieval; Streamlit single page;
CSV upload of operational records; evals script; README.

Out, for this cut: authentication, multi-user, PDF export (Markdown download instead), vector
database, LangGraph or any agent framework, Flask or Flutter, fine-tuning, any non-GW API,
document upload beyond CSV operational records.

## 4. Data design (all synthetic, all labeled)

Fictional company: Northline Logistics. Three sites: Richmond, Norfolk, Roanoke. Each site has
Day and Night shifts split into teams (about 24 teams total, sizes 2 to 15, so at least four
teams fall under the reporting threshold). Two survey waves: Wave 1 closes 2026-03-15, Wave 2
closes 2026-09-10.

Tables (CSV in `data/generated/`, loaded into DuckDB in memory):

| Table | Grain | Key columns |
|---|---|---|
| sites | site | site_id, site_name |
| teams | team | team_id, site_id, team_name, shift, manager_name, headcount |
| employees | employee (no PII) | emp_id, team_id, tenure_band (under_1, 1_to_3, 3_to_10, over_10), hire_date |
| waves | wave | wave_id, wave_name, close_date |
| responses | respondent × wave | emp_id, team_id, wave_id, q01..q12 (1 to 5) |
| comments | comment | comment_id, team_id, wave_id, text, theme (hidden, truth only) |
| ops_daily | site × shift × hour band × day | date, site_id, shift, hour_band, departures, late_departures, rework_count |
| staffing | site × shift × month | month, site_id, shift, scheduled_headcount, actual_headcount |
| ownership_directory | process | process_name, site_id or ALL, owner_role, owner_name |
| documents | document | doc_id, title, type (sop, policy, directory), path |

Q12 items follow Gallup's public numbering; Q02 is "materials and equipment," Q07 is "opinions
seem to count." Item wording is stored once in `data/q12_items.csv`.

Planted patterns, each recorded in `data/generated/truth.json` with an id:

- P1: Richmond Night team A, Q02 mean falls from about 3.9 to about 3.2 between waves.
- P2: Same team, Q07 falls from about 3.8 to about 3.3.
- P3: Richmond Night late-departure rate in the 06:00 to 07:00 hour band rises from about 8% to
  about 18% from June 2026 on; other hour bands and sites stay flat.
- P4: Richmond Night staffing shortage in March 2026 (actual about 80% of scheduled), back to
  normal by May. The competing explanation.
- P5: Honeymoon effect: employees under one year score about 0.3 higher on the grand mean in
  every team and wave. (Keegan, Sept 14.)
- P6: Norfolk Day team B: within each tenure band scores are stable across waves, but Wave 2
  has far fewer under-one-year respondents, so the team mean appears to fall. The reviewer
  case.
- P7: The list of teams with fewer than four respondents in either wave.
- P8: At least three Wave 2 comments from Richmond Night describing missing information at the
  shift handoff.

Documents (Markdown in `data/docs/`): shift handoff procedure (requires a load checklist
completed by the outgoing shift), a scheduling policy, and the ownership directory rendered
as text. All written by the team; all labeled illustrative.

## 5. Suppression rule

Minimum n is 4 (Keegan, Sept 14). Implemented in DuckDB views, not in prompts:

- `v_team_wave_item`: team, wave, item, mean, n. Mean is NULL when n < 4.
- `v_site_wave_item`: site-level roll-up with its own n.
- `v_tenure_wave_item`: by tenure band, same rule.
- Comments from a team with n < 4 in that wave are excluded from retrieval.
- Respondent-level rows never reach the model. The model only ever sees view output.

## 6. Architecture

Plain Python 3, no framework. Modules in `app/`:

- `config.py`: loads `.env`; exposes model names, key presence, base URL.
- `db.py`: builds the DuckDB connection, loads CSVs, creates views; `run_sql(sql)` on a
  read-only connection restricted to the views and an allowlist of tables, with a row cap.
  Returns rows plus the SQL for the "show me" panel.
- `retrieval.py`: chunks documents and comments; embeds with the OpenAI embeddings model;
  caches vectors on disk; `search(query, filters, k)` by cosine similarity in numpy; applies
  the suppression filter to comments. Falls back to keyword search when no key.
- `agent.py`: the five steps.
  - `scope(question)`: the model extracts site, shift or team, waves, items, and intent into a
    fixed schema, or returns a refusal when named entities do not exist in the data or the
    intent needs data we do not have. Entities are checked against the tables, not trusted.
  - `analyze(scope)`: deterministic. Runs the survey delta query, the operations query, and
    the staffing query. Python computes every number. Returns Evidence records
    `{id, kind, statement, value, sql, rows, source}`.
  - `retrieve(scope, question)`: top passages from documents and comments, plus the owner from
    the directory. Returns Evidence records with `kind` in doc, comment, owner.
  - `explain(question, evidence)`: the model writes a Brief
    `{obstacle, evidence_for[], evidence_against[], missing[], owner, proposed_test,
    limits}` where each item cites evidence ids. `check_brief()` rejects any cited id that
    does not exist and any number in the text that does not appear in the evidence, and
    regenerates once before falling back.
  - `fallback_brief(evidence)`: templated brief from the same evidence, no model.
  - `approve(brief, decision, note)`: appends to `approvals.jsonl`.
- `ui.py`: Streamlit. Sidebar: data status, key status, CSV upload of operational records.
  Main: question box with four example buttons; tabs for Brief, Evidence, Chart, Show me;
  approve and reject buttons; an Evals tab.
- `evals/questions.json` and `evals/run_evals.py`: eight questions with expected outcomes
  keyed to truth ids; prints found, missed, refused correctly, and number accuracy.
- `tests/`: pytest for the generator (patterns present, threshold list correct), the views
  (NULL under four), `analyze()` numbers, `scope()` refusals on unknown entities, and
  `check_brief()` on a brief with a fabricated number.

Data flow: question → scope → analyze + retrieve → explain (or fallback) → check → screen →
approve. Nothing is cached between questions except embeddings.

## 7. Model use

The GW-assigned Azure OpenAI resource only (`gw-sb-04`, instructor's variable
`GW_AZURE_OPENAI_KEY`). Deployments found on Sept 14, 2026: `gpt-5-mini`, `gpt-5`, `gpt-5-nano`
for chat and `text-embedding-3-small` for embeddings. Default: `gpt-5-mini` with reasoning effort
"minimal" for scope extraction and "low" for brief writing. The model never performs arithmetic
and never sees respondent rows. Every model call has a timeout; on failure the fallback path
runs and the UI shows a notice.

## 8. Build plan

- Day 1, Sept 14 (tonight): environment, data generator, truth file, DuckDB views, tests.
- Day 2, Sept 15: scope, analyze, retrieve, explain, fallback, check; command-line run.
- Day 3, Sept 16: Streamlit screen, upload, show-me, approve, evals tab; README.
- Day 4, Sept 17: rehearse the five success tests, fix, freeze; record the fallback works with
  the key removed.
- Sept 18, 2:30 PM: show it.

## 9. Open questions

- Which model names the GW key permits. Configurable; confirm on first run.
- Whether the GW key uses a custom base URL. Configurable.
- Whether Gallup data arrives (Keegan's "grapevine"). Tables are shaped like a Gallup export
  so real aggregates can replace the generated ones.

---

# Version 0.2, Sept 17, 2026: judge meeting 1 recommendations built in

Status: built and verified (32 tests, 12/12 evals in rules mode; model-mode runs saved under
`evals/results/`). Shown Fri Sept 18 to Ethirajan (10:30), Fullowan (12:00), Jamshidi (1:00),
Keegan (2:30). Version 0.1 is git commit `4ee1144` in this folder.

## What changed and why (judge → change → where)

| Judge, date | What they asked or objected to | Change | Where |
|---|---|---|---|
| Keegan (Gallup), Sept 14 | Managers under four; how operational records connect | Kept: suppression in SQL, site roll-up, CSV upload. Added: who-responded breakdown also hidden under n<4 | `db.py`, `agent._analyze_mix` |
| Fullowan (Freddie Mac), Sept 14 | Human in the loop, spot checks with numbers, response bias | Approve / reject / **flag** with a review log; response bias in every brief's limits | `agent.approve`, `review_log`, UI |
| Lederman (MITRE), Sept 15 | "What's the data"; do not attribute causation to a blip; one-pager | `DATA_SPEC.md` generated with the data; P9 blip → verdict "insufficient", no owner, no test; one-page HTML report | `generate.write_data_spec`, `assess`, `report_html` |
| Chang (FI), Sept 15 | One loud comment over-indexes; weight by breadth | Comment themes counted in code; a theme corroborates only with ≥3 separate comments; P10 loud comment → "single source" | `retrieve`, `assess`, `THEMES` |
| Finan (Mizuho), Sept 15 | Confusion-matrix evals, weight misses; model reasons over text; gpt-5 vs mini | Evals report TP/FN/FP/TN per run, saved per model; `--model` flag; origin labels on every element | `evals/run_evals.py`, UI |
| Kaznachey (FI), Sept 16 | Playbook questions, not only free text; team n is small; deterministic vs textual | Playbook buttons for the three features; team-level = watch items, thresholds stated; computed / generated / retrieved / templated chips | `ui.py` |
| Jamshidi (Promontory), Sept 16 | Flag-this loop; admin review; transparency about what is AI; one-sentence idea statement | Flag button; review log expander; chips; idea statement in the header | `ui.py` |
| Hall (instructor), Sept 14 | Three strong analytics features on a professional UI | Diagnose (site overview + brief), Check the signal (mix-adjusted), Act and review (plan + report) | `ui.py`, `agent.plan` |

## The computed verdict (step 4, new)

Code decides whether the evidence supports naming an obstacle; the model is told the verdict and
cannot change it (the checker rejects a brief that does). Thresholds, all in `agent.py`:

- `SURVEY_MATERIAL = 0.30`: an item mean change of 0.30 or more on the 5-point scale is material.
  Screening rule, not a significance test; team-level findings are watch items.
- `OPS_SIGNAL_ABS = 0.05` and `OPS_SIGNAL_RATIO = 1.5`: a late-departure band is a signal when its
  rate rises 5 points or more and to at least 1.5x the earlier rate.
- `COMMENT_BREADTH = 3`: a comment theme corroborates only with three or more separate comments.
- `STAFFING_LOW = 0.90`: a month under 90% of scheduled headcount is a competing explanation.
- `MIX_EXPLAINS = 0.30`: in the signal check, a residual below 0.30 after the who-responded
  adjustment means "not a real decline beyond the mix".

Verdicts: `supported` (material fall + operational signal or comment breadth) → obstacle, owner,
test, plan. `insufficient` (survey moved, nothing else) → watch item, no owner, no test.
`no_material_change` → watch list. `suppressed_insufficient` → site view with the Site Operations
Manager.

## The signal check (feature 2, new)

Shift-share: expected change = Σ over tenure bands of (share in Wave 2 − share in Wave 1) ×
company-wide band mean. Residual = observed change in the team grand mean − expected. Norfolk Day
B: observed −0.45, expected from mix −0.20, residual −0.25 → "mostly a change in who responded".

## The action plan and report (feature 3, new)

Only for `supported`. Goal from the operational signal (bring the 06-07 late rate from 17.8% back
to 7.4% by the review date); focus item = the fallen item most relevant to the theme (handoff →
Q02); three or four actions written by the model from the brief, checked (owner roles must exist
in the directory for that site, numbers must appear in the evidence) or templated from a bank per
theme; owners and dates computed; Gallup's item-specific discussion questions quoted verbatim with
attribution (license: may be copied for individual use, not altered). Report: self-contained HTML
(no scripts) with two SVG charts, plus Markdown.

## Evals (rewritten)

12 gold questions with a class: positive (E1, E12), negative (E2, E3, E4, E9, E10), lookup (E5,
E6, E7, E8, E11). Outcome per question: TP / FN / FP / TN, or pass / fail for lookups. Misses (FN)
are the outcome we weight highest (Finan). Runs are saved to `evals/results/latest_<model>.json`
and shown in the UI, so the gpt-5 vs gpt-5-mini comparison lives in the technical evaluation, not
the main deck (Hall).

## Known limits carried into November

- No Gallup global-database benchmark or percentile rank (no licensed source); strength and
  opportunities are measured against the company mean instead.
- Two waves; no next-wave comparison yet (the review step is designed, not exercised).
- Response bias is stated, not modelled. Real survey text is human behaviour; ours is a small bank.
- gpt-5-mini takes about 30 s on the main question; gpt-5 about 60 s. The templated fallback covers
  a model outage but reads flatter.
