# Friction Finder architecture (v0.8)

Drawn from the code on branch `v0.8-investigate` (Oct 8, 2026); v0.9-health keeps this architecture unchanged and
renames the data (Lanford Health, fictional; late doses, overtime shifts; `docs/specs/2026-10-08-healthcare-variant.md`).
References name the function; line numbers are left out because several of these files changed during the night.
No patient-level data exists anywhere in the pipeline: every operating record is a count at unit, shift or site level.
v0.10 (Oct 27, 2026) adds the execution record, owner notices and value tiers on top of this; see the section near
the end.

Friction Finder is an **AI-assisted workflow** with one **AI-assisted investigation** inside it. The model
chooses which of a fixed set of read-only tools to run next, under a budget; code computes every number and
sets every evidence state; a person approves every action. Nothing is sent anywhere and nothing changes in the
client's systems.

```mermaid
flowchart LR
  subgraph Client data (synthetic CSVs in the demo)
    S[Survey export<br/>responses, comments]
    O[Operating records<br/>team-month, eMAR doses by hour]
    D[Procedures &<br/>ownership directory]
  end
  S & O & D --> V[(DuckDB views<br/>n ≥ 4 in SQL; teams under 4<br/>left out of v_team_ops_month)]
  V --> G{{sqlglot guard<br/>allowlist, no table functions}}
  Q[Manager's question<br/>+ context chips] --> OOS{{out_of_scope<br/>every turn, before any tool}}
  OOS --> RD[Question reader<br/>rules; model only if no match]
  RD --> CO[Coordinator<br/>app/investigate.py]
  CO <--> M1([AI: choose the next tool<br/>function calling])
  CO --> T[11 read-only tools<br/>app/tools.py · numbers in code]
  T --> G
  T --> EV[Evidence register<br/>ids across turns]
  EV --> ES[Evidence-state rules<br/>code]
  ES --> M2([AI: wording of conclusion<br/>and competing explanation])
  M2 --> CK{{Self-check: citations, numbers,<br/>entity, period, unit, causal words}}
  CK --> UI[Web app: panel, Investigate, Review]
  UI --> H[/Person: edit and approve a plan;<br/>keep, change or stop at review/]
```

## The investigation loop (`app/investigate.py`, `investigate()`)

1. **Scope first, every turn.** `agent.out_of_scope` declines questions about individuals, individual answers,
   or judging or predicting a person before any tool or query runs, on the first question and on every
   follow-up. Places not in the data, periods not in the data (`PAST_YEAR`), and questions asking what
   *caused* quits or injuries (`CAUSE_OF_RARE`: the data has counts, not reasons) are declined too; the causal
   decline still reports the counts.
2. **Context.** `{site, team, as_of, kpi, item, dataset version}` is kept server-side per conversation
   (`Conversation`, 4-hour TTL). `app/relations.py` `resolve()` turns "it", "the other night shifts", "Westbrook",
   "No, I meant ICU Night" into a context change, or asks which team when the referent is ambiguous. A context
   change marks earlier evidence `stale`; it stays in the register so old citations still open.
3. **Question reader.** `classify()`: regular expressions map the question to one manager function and its
   parameters (for example `could_explain` with `x = staffing`). Only when nothing matches and a key is present
   does the model read it into the same fixed list of function ids (`_model_read`).
4. **Tools.** Rules mode: a fixed plan per function (`plan_for`). Model mode (`_model_loop`): the model picks
   the next tool by function calling with strict JSON schemas (`app/llm.py` `choose_tool`); code validates the
   arguments against the registry's enums, runs the tool, appends evidence, and asks again. Checks the model
   skipped that the function requires are then run by code, labelled in the trace. Team, site and dates are
   fixed by code; the model cannot change them.
5. **Answer.** `compose()` builds the structured answer from tool results: conclusion, evidence state,
   evidence ids, competing explanation with its own state, next step (an action, or an information-gathering
   step with an owner from the directory), plus hypotheses, gaps, a chart or table spec, a plan draft or a
   review where the function has one. The text is a template filled only from tool results.
6. **Wording (model mode).** `_model_write` asks the model to rewrite the conclusion and the competing
   explanation in plain words. `self_check()` must pass or the template stays and the rejection is recorded
   (`check.rejected`, `fallback`).

**Budgets, enforced in host code** (`MAX_TOOL_CALLS, MAX_MODEL_REQUESTS, MAX_SECONDS = 6, 8, 60.0`; class `Run`):
at most 6 tool calls, 8 model requests, 1 retry per failed model call (`llm._retry`, backoff 1.5 s), 60 s wall
time per turn. An equivalent repeated tool call is refused ("Skip a repeated check" in the trace) and two
refusals stop the loop; a tool that already ran this turn is not offered to the model again. At a limit the
answer is built from what was gathered and `budget.stopped` says why. If the model cannot be reached after
the retry, the fixed plan runs instead and `fallback` says so. These are engineering defaults, not promised
latency. Every step appears in the trace with its mode (code or AI model) and real seconds; the panel polls
`GET /api/investigate/{id}` while a turn runs (`async: true`), so the trace is real activity, never a timer.

**Tool registry** (`app/tools.py` `REGISTRY`; every tool is read-only and computes its numbers in code):

| Tool | What it does |
|---|---|
| `query_metric` | one operating metric for the team over the board's 3-month window, plus the comparable teams' pooled rate (`app/metrics.py`) |
| `compare_teams` | the team vs its comparable teams (same shift at every site, 4+ people, excluding itself) on the metric and the focus item, with n; teams under 4 named, never numbered |
| `benchmark` | internal norm (median and range of comparable teams); all-night vs all-day shift rates; the external Gallup benchmark returns **unavailable** (assumed source) |
| `signal_check` | the v0.5 who-responded check (shift-share by tenure band) and the board's tenure-adjusted largest item change |
| `timeline` | month by month: the metric vs the comparable range, staffing months under 90% of scheduled, survey waves, plan dates |
| `hour_bands` | late-dose share by hour band, Jan–May vs Jun–Sep (the eMAR export is recorded per site and shift, not per team) |
| `retrieve_passages` | reportable comments counted by theme in code, wave-2 comments re-ranked for the top theme (keyword + embeddings), procedures; deduplicated; instruction-like text labelled as data (`INJECTION`) |
| `owner_lookup` | the process owner at the team's site (ownership directory) |
| `precedent` | other teams flagged on the same metric or with the same item drop, their plans and results, or "no precedent" |
| `draft_plan` | the thinnest plan the review needs: owner, action, operational measure, baseline, review date (end of the second full month after start), success criterion (back inside the comparable range), assumptions. It cannot approve, notify or write |
| `review_result` | `impact.did_all` for the team's approved plan: improved / deteriorated / inconclusive, or not ready |

**Evidence states** are set by explicit rules (`hypotheses()`, `compose()`), never by the model, and there are
no confidence percentages:

| Explanation or answer | supported | mixed | insufficient | unavailable |
|---|---|---|---|---|
| Process or restock | 3+ separate comments on one theme **and** an hour-band rise in the medication pass before the shift change | one of the two | neither | — |
| Staffing | a month under 90% of scheduled falls inside the flagged window | — | no shortage month in the window | — |
| Who responded | a large change in who answered and the item change within noise after adjusting | — | the drop persists after adjusting | a wave under 4 respondents |
| Site-wide or seasonal | — | team inside the comparable range | team above every comparable team (same months, so shared seasonality is netted out) | — |
| A single loud comment | one long comment and no theme with 3+ comments | — | 3+ separate comments | — |
| Why flagged (overall) | the top explanation's state; **mixed** when two explanations are both supported | | | |
| Compare / normal | 2+ comparable teams with data | | fewer than 2 | none, or the external benchmark |
| Did it work | improved or deteriorated (95% interval excludes zero) | | inconclusive | before the review date, or no plan |

**Self-check** (`self_check()`), run on every answer in both modes. Coverage: the conclusion and the competing
explanation must cite evidence ids that exist. Numbers: every number must appear in the evidence that part
cites; the same digits elsewhere do not count. Provenance: a team named next to a number must be the team in
the cited evidence, and a period such as "Jun-Aug 2026" must be the cited period; a percent must be a percent in
the evidence. No causal wording. A model rewrite that fails any of these is discarded; the template is shown.

## Where the AI model is used (and only there)

All calls go through `app/llm.py` to the GW Azure OpenAI deployment (`gpt-5-mini`). Without a key every
function still runs (rules reader, fixed plans, templated text, keyword retrieval).

| # | Step | Code | Calls per question | What it returns |
|---|---|---|---|---|
| 1 | Ask: read the question | `agent._scope_llm` | 1 | JSON intent, site, team, items; checked against the tables |
| 2 | Ask: write the brief | `agent.write_brief` → `explain` | 1, plus 1 regeneration if the check fails | JSON brief from evidence only; `check_brief` |
| 3 | Investigation: read the question | `investigate._model_read` | 0 or 1 (only when the rules reader matches nothing) | one function id from a fixed list |
| 4 | Investigation: choose the next tool | `investigate._model_loop` → `llm.choose_tool` | up to 6 (each may retry once; all count against 8) | one tool name and its arguments, validated by code |
| 5 | Investigation: word the answer | `investigate._model_write` | 1 | conclusion and competing explanation text with citations; `self_check` |
| 6 | Plan: regenerate the action list (v0.10) | `agent.regenerate_actions` ← `POST /api/plans/regenerate` | 1 per "Edit and regenerate" click | three actions with owners from the ownership directory, from the manager's edited obstacle; rules mode uses a theme-matched action bank |
| 7 | Plan: word the owner notices (v0.10) | `agent.draft_notices_llm`, started by `api.main._redraft_notices_async` after approval | 0 or 1 per approval (plus 1 retry), in a background thread; approval never waits | one notice per owner from the plan's facts only; swapped in only if the check passes (owners match the plan, every number is in the plan, under 140 words, no causal claim); otherwise the templated notices stay, labelled |

Also: embeddings for retrieval (`app/retrieval.py`, text-embedding-3-small; keyword search without a key).
`choose_tool` uses function calling with strict schemas; on a 400 from the deployment it would fall back to a
JSON next-tool object. **Verified live on Oct 8, 2026:** the GW deployment accepted function calling
(`selection: "function_calling"`) in ten live turns. Four test turns took 22.5, 17.6, 27.8 and 57.8 s; in the
57.8 s turn under 5 s of the 60 s budget remained, so the wording step was skipped and the templated text shown.
Six turns saved as prepared answers by `scripts/prepare_investigations.py` took 19.0 to 41.7 s; in one, the
wording call got a GW 429 rate-limit error and the labelled template was kept. The JSON fallback has not run.

**The model never writes SQL, never produces a number, never sets an evidence state, never sees respondent
rows, and never approves anything.** Text-to-SQL is tier 1 only: question → structured plan → validated →
templated SQL. Model-written SQL (tier 2) was not shipped.

## Question → validated query → computed result → plain-English sentence (`app/metrics.py`)

One definition per operating metric the screens show (`METRICS`: late doses, absence days, quits,
injuries, overtime shifts, plus the late-dose share by hour band): view, numerator, denominator (head-months),
unit (per 10 people per month), period, grain, source. `validate()` checks metric, entity, team size, period
and grain; missing periods, unknown metrics or entities, suppressed teams and zero denominators come back as
named statuses, never as zeros. `query_metric()` compiles the plan to templated SQL on `v_team_ops_month`,
which reads exactly the rows `app/impact.py` uses (uploads included, `DB.sync_team_ops`) and leaves out teams
under 4 people, so no site or shift total can be differenced to recover them. `sentence()` writes the rules-mode
explanation with unit and period. `tests/test_metrics.py` checks that the board and `query_metric` agree for
the planted team (Lanford Med-Surg Night) on all five metrics at both demo dates. Ask (`agent._ops_metric`) and the investigation tools use the
same path, so a question and a dashboard cannot disagree.

## What is deterministic

| Component | Code |
|---|---|
| Suppression | `app/db.py` views (`CASE WHEN COUNT(*) >= MIN_N`), `v_comments_reportable`, `v_team_ops_month` (teams under 4 excluded) |
| SQL guard | `app/db.py` `_check_query` via `run_sql`: one read-only SELECT, every table allowlisted, no table functions, no schema-qualified names, CTEs may not shadow real tables (now including `team_ops_monthly`) |
| Out of scope | `app/agent.py` `out_of_scope`, first in `agent.run` and in `investigate()` on every turn |
| Detect / explain / prove | `app/impact.py` `_elevation`, `board`, `association`, `did` (unchanged in v0.8) |
| Ask verdict and brief check | `app/agent.py` `assess`, `check_brief` (unchanged) |
| Investigation evidence states and self-check | `app/investigate.py` `hypotheses`, `compose`, `self_check` |

## Where the human decides

| Decision | Screen | Code |
|---|---|---|
| Edit and approve a plan (drafts can be saved) | Investigate › What do I do?; panel › Draft a plan | `POST /api/plans`; an existing plan for the same team, KPI and period is shown first (`GET /api/plans/check`); a repeated `request_id` returns the saved plan; every approval appends edits, decision and time to `approvals.jsonl` |
| Regenerate the draft with a different obstacle (v0.10) | Investigate › What do I do? › "Edit and regenerate" | `POST /api/plans/regenerate`; nothing is saved until the manager approves |
| Run the checklist: tick, untick, block or edit a task; add a task (v0.10) | `/plans/{id}` | `PATCH /api/plans/{id}/actions/{action_id}`, `POST /api/plans/{id}/actions`; every change appended to `approvals.jsonl` with `target: "action"` and the time |
| Send an owner notice (v0.10) | `/plans/{id}` › Owner notices › Copy | No code path sends anything: every notice carries `sent: false`, the plan carries `nothing_sent: true`, and the screen says "Nothing is sent by this prototype" |
| Keep, change or stop at the review date | Review | `GET /api/plans/{id}/result` (now with the three value tiers, `impact.value_of_plan`) |
| Approve / reject / flag an Ask brief | `/ask?view=brief` (the v0.7 one-page brief) | `POST /api/approve` |
| Feedback on an answer (wrong context, not actionable, missing evidence, wrong number, other) | panel | `POST /api/useful` → `feedback.jsonl`; `evals/from_feedback.py` drafts eval cases for a person to review. Approvals are never evidence that an answer was correct |
| Unit costs | Business case | `PUT /api/costs` |

## Why these techniques

Alternatives are taken only from `SPEC.md`, `docs/specs/`, git history, the Oct 8 overnight prompt and
`My Notes/2026-09-23_Winner_Repos_and_Prototype_Gaps.md`. Where no reason was recorded, the table says
**Farid to confirm**.

| Technique | Pros | Cons | Alternatives considered | Why not used (recorded source) |
|---|---|---|---|---|
| **One bounded coordinator: the model picks the next read-only tool from a fixed registry** (v0.8) | the manager can challenge an explanation and get a checked answer; the model never touches data directly; budgets and a duplicate guard bound cost and time; keyless rules plans give the same output shape | live latency (17.6 to 57.8 s over ten live turns on Oct 8; one GW 429 rate-limit error); the model repeated a tool in the first live test until already-run tools stopped being offered; tool choice in model mode is not yet covered by a model-mode eval run | fixed steps only (v0.7); an orchestration framework (LangGraph) | fixed steps: superseded by Farid's approval of this scope on Oct 8, 2026 (overnight prompt, "authorization"). Frameworks: out of scope (SPEC §3) |
| **Question → structured plan → templated SQL on views, sqlglot guard** (tier 1) | the model cannot write arbitrary SQL; every query auditable ("Show SQL"); suppression in the views; one metric definition for screens and questions | only answers question types with a plan; new metrics need a definition | free-form model-written SQL (tier 2); vanna.ai; the earlier regex guard | tier 2: not shipped in v0.8 (the prompt allowed it only after tier 1 fails to match). vanna.ai: archived, last release Feb 2, 2026 (Gaps note). Regex guard: bypassed by comma joins and `read_csv`, replaced Sept 23 (`260d248`). Free-form SQL in general: **Farid to confirm** (no recorded reason; SPEC §6 specifies views plus an allowlist) |
| **Retrieval with citations** (embeddings + keyword re-rank for the code-counted theme; keyword fallback) | small corpus, no extra service; every passage cited; works without a key | no reranker model; retrieval quality not measured with a retrieval metric | a vector database; RAGAS | vector DB: out of scope for this cut (SPEC §3). RAGAS: development has slowed (Gaps note) |
| **Rule-based verdict and evidence states** | transparent; the model cannot overclaim; tested on planted cases | screening rules, not significance tests; thresholds are judgement calls | a trained classifier (EBM, as in FraudLens); an orchestration framework | 24 teams × 2 waves is too small, "do not report an AUC" (Gaps note, gap 2); frameworks out of scope (SPEC §3) |
| **Poisson excess vs comparable teams** (detect) | flags only what exceeds normal variation; "too rare to judge" is explicit | assumes Poisson counts; about 1 false flag per site at p < 0.01 | positive excess over the comparable-team median (v0.6 design spec) | tried Sept 23: it turned half the teams red on noise; replaced ("v0.6 analytics: excess vs normal variation") |
| **Difference-in-differences with a placebo check** (prove) | cancels site-wide and seasonal shifts; the placebo shows how unusual the result is | one treated team, 4 comparison teams; directional, not causal; the follow-up data is synthetic | bootstrap CI over comparison teams (v0.6 design spec §4); DoWhy | bootstrap: the plan switched to Poisson SEs, reason not recorded, **Farid to confirm**. DoWhy: the data cannot defend causal claims (Gaps note) |
| **OLS association + quartile comparison** (explain) | the same presentation as Gallup's meta-analysis; CIs and n shown; clustered SEs | 34 team-waves; about 3 of 65 pairs light up by chance (shown on screen) | a driver model with statsmodels (Gaps note, gap 2) | adopted in this form (statsmodels OLS) |

## v0.10 additions (Oct 27, 2026): execution record, owner notices, value tiers

Added for Prof. Hall's Oct 21 review (`docs/specs/2026-10-27-prof-hall-round.md`). The architecture above is
unchanged; three things sit on top of it.

- **Execution record** (`api.main._execute`, `agent.execution_record`), written inside both approval paths under
  the plan lock and idempotent on a repeated approval. Code assigns an owner to every task (the manager's entry
  first, then the plan owner, then the ownership directory; the source is recorded per task), schedules the review
  (the plan's review date, in the Due reviews queue), sets the KPI watch (the plan's KPI for the team, monthly, from
  start to review), and drafts one notice per owner. Plans saved before v0.10 (the seeded plan, v0.7 and v0.8
  approvals) get a `derived: true` record on read, so nothing old breaks. Every task carries `id`, `status`
  (`todo | done | blocked`) and `done_at`; `progress {done, total}` is on every plan and board row.
- **Owner notices.** Templated at approval from the plan's fields (`agent._template_notices`). With a key,
  `agent.draft_notices_llm` rewrites them in a background thread from a facts object (team, obstacle, focus item,
  KPI, start, review, manager, tasks with owner and due date) and the result replaces the templates only if the
  check passes: the set of `to` fields equals the plan's owners; every number in subject and body is in the set
  `_notice_allowed_numbers` builds from the plan; no body over 140 words; no `caused | causes | because of the
  survey | proves`. Two failures and the templates stay, labelled "Templated · rules mode" in the UI with the
  rejection notes in `check`. `sent` is always `false`; no code path sends mail or messages.
- **Value tiers** (`impact.value_of_plan`, returned under `value` by `GET /api/plans/{id}/result`). Measured: only
  KPIs whose DiD interval excludes zero, events avoided per quarter × 4 × the unit cost, with the unit cost's kind
  (`sourced | assumption | client_entered`) and source. Projected: the unit's headcount × the sector turnover rate ×
  Gallup's top-vs-bottom quartile turnover gap (21% to 51%) × the cost per RN separation; a sanity range of 0.3 to 3
  separations a year for a unit this size is enforced and reported (`in_range`); the unit's own OLS associations
  are returned as `mechanism` and shown, not used in the figure (the quits slope applied to the item drop gives
  5.8 separations a year on 14 people, out of range). Hospital scale: `value_case` for the Business case headcount.
  Every tier returns its `inputs` with sources so the UI prints the assumption next to the number, and the result
  carries `illustrative: true` with the reason (synthetic follow-up months).

**Which part is agentic (the answer for judges).** Code decides: what is flagged, whether a change is beyond normal
variation, every evidence state, the verdict and its interval, the placebo, the value tiers, and the owners, review
date and KPI watch at approval. The model decides: which read-only check runs next (from a fixed registry, under
the budget) and the wording of the brief, the plan draft, a regenerated action list and the owner notices, all from
numbers it is handed and all checked by code. The person decides: whether to act, what the plan says, who owns
what by when, when a task is done, whether to send a notice, and whether to keep, change or stop at the review
date. Using a coding agent to build the software does not make the product agentic.

## Known gaps (reported, not changed)

- `app/impact.py` `_comparables` uses the same shift at **every** site (Lanford ICU Night is a comparable for
  Lanford Med-Surg Night). The v0.7 Method text said "other sites"; the v0.8 UI text now matches the code. The DiD comparison
  uses other-site teams only. Statistical logic was not changed.
- Complementary suppression on survey roll-ups is still not enforced (`docs/risk/TEVV_EVIDENCE.md`).
