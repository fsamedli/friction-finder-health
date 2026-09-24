# Friction Finder architecture (v0.7)

Drawn from the code on branch `v0.7-saas-ui` (Sept 24, 2026). File:line references were checked on that
day and point at the start of the function or block named.

Friction Finder is an **AI-assisted workflow**, not an autonomous agent. The steps are fixed; the AI model
is used at exactly two of them; every number is computed by code; a person makes every decision.

```mermaid
flowchart LR
  subgraph Client data (synthetic CSVs in the demo)
    S[Survey export<br/>responses, comments]
    O[Operating records<br/>team-month, dispatch by hour]
    D[Procedures &<br/>ownership directory]
  end
  S & O & D --> V[(DuckDB<br/>views with n ≥ 4<br/>suppression in SQL)]
  V --> G{{sqlglot guard<br/>allowlist every table,<br/>no table functions}}
  G --> A[Evidence engine<br/>agent.py]
  O --> I[Impact engine<br/>impact.py<br/>Poisson · OLS · DiD]
  Q[Manager's question] --> OOS{{Out-of-scope guard<br/>no individuals}}
  OOS --> M1([AI: read the question<br/>into a fixed schema])
  M1 --> A
  A --> R[Retrieval<br/>comments & docs,<br/>small teams excluded]
  A --> VR[Verdict rules<br/>computed by code]
  VR --> M2([AI: write the brief<br/>from evidence only])
  M2 --> CK{{Checker: every number<br/>and citation must be<br/>in the evidence}}
  CK --> UI[Web app]
  I --> UI
  UI --> H[/Person: approve, reject,<br/>flag, approve a plan/]
```

## Where the AI model is used (and only there)

Both calls go through `app/llm.py` to the GW Azure OpenAI deployment (`gpt-5-mini`).

| # | Step | Code | What the model sees | What it returns |
|---|---|---|---|---|
| 1 | Read the question | `app/agent.py:243` `_scope_llm` | the question, site and team names | JSON: intent, site, team, items. Every entity is checked against the tables; unknown names are declined. |
| 2 | Write the brief | `app/agent.py:1052` `write_brief` | the evidence records (statements and ids) and the computed verdict | JSON brief: obstacle, evidence for and against with ids, missing, owner, test, limits |

Also: embeddings for retrieval (`app/retrieval.py:76`, text-embedding-3-small; keyword search without a
key). The v0.5 plan writer and follow-up chat (`agent.py:1119`, `:1396`) still exist but are **not used**
by the v0.7 web app.

**The model never writes SQL, never produces a number, never decides the verdict, never sees respondent
rows, and never approves anything.** Text-to-SQL here is *question → structured intent → parameterized SQL
templates* (`app/agent.py:329` `analyze`). Every query still goes through the sqlglot guard.

## What is deterministic

| Component | Code | What it does |
|---|---|---|
| Suppression | `app/db.py` views (`CASE WHEN COUNT(*) >= {MIN_N}`), `app/db.py:135` `v_comments_reportable` | team means are NULL under 4 respondents; comments from those team-waves are never indexed |
| SQL guard | `app/db.py:154` `_check_query`, called by `run_sql` (`:201`) | parses with sqlglot (DuckDB dialect); one read-only SELECT; every table must be allowlisted; table functions (`read_csv`, `glob`, …), schema-qualified names and CTEs shadowing tables are refused |
| Out-of-scope guard | `app/agent.py:984` `out_of_scope`, applied at `:995` | declines questions about individuals, individual answers, or judging or predicting a person, before any query |
| Evidence | `app/agent.py:329` `analyze`, `:636` `retrieve` | survey deltas, who-responded signal check, operating bands, staffing, comment themes counted in code, owner from the directory |
| Verdict | `app/agent.py:704` `assess` | screening rules (thresholds in `SPEC.md`): supported / insufficient / no material change / suppressed |
| Brief checker | `app/agent.py:793` `check_brief`; `api/main.py:463` `_grounding` | rejects uncited ids and numbers not in the evidence; one regeneration, then a templated fallback |
| Detect | `app/impact.py:185` `_elevation`, `:199` `board` | observed vs expected from comparable teams' pooled rate; Poisson p < 0.01; "too rare to judge" under 3 expected; engagement change adjusted for who responded, Welch t-test with Bonferroni over 12 items; teams under 4 people rolled up (`:207`) |
| Explain | `app/impact.py:264` `association`, `quartile_link` | OLS of KPI rate on item mean over team-waves, SEs clustered by team; quartile comparison |
| Prove | `app/impact.py:353` `did` | difference-in-differences vs other-site teams on the same shift; Poisson SE; placebo run per comparison team |

## Where the human decides

| Decision | Screen | Code |
|---|---|---|
| Approve, edit or reject a drafted action plan | Team detail › Create plan | `POST /api/plans` (`api/main.py:157`) |
| Approve / reject / "this doesn't sound right" on a brief | Ask | `POST /api/approve` (`api/main.py:504`) → `approvals.jsonl` |
| "Useful? yes / no" plus a reason | Ask, action plan | `POST /api/useful` → `feedback.jsonl` |
| Unit costs used for dollars | Business case | `PUT /api/costs`; validation `app/impact.py:85` |

Nothing is sent to anyone and nothing changes in the client's systems. The tool reads data and records decisions.

## Why these techniques

Alternatives are taken only from `SPEC.md`, `docs/specs/`, git history and
`My Notes/2026-09-23_Winner_Repos_and_Prototype_Gaps.md`. Where no reason was recorded, the table says
**Farid to confirm**.

| Technique | Pros | Cons | Alternatives considered | Why not used (recorded source) |
|---|---|---|---|---|
| **Question → fixed schema → parameterized SQL on views, with a sqlglot guard** | the model cannot write arbitrary SQL; every query is auditable ("Show SQL"); suppression lives in the views, not the prompt | can only answer question types that have a template; new question types need code | free-form model-written SQL; vanna.ai; the earlier regex guard | vanna.ai: archived on GitHub, last release Feb 2, 2026 (Gaps note). Regex guard: bypassed by comma joins and `read_csv`, replaced Sept 23 (`260d248`). Free-form SQL: **Farid to confirm** (no recorded reason; SPEC §6 specifies views plus an allowlist) |
| **Retrieval with citations** (embeddings + cosine in numpy; keyword fallback) | small corpus, no extra service; every passage cited with an id; works without a key | no reranker; quality not yet measured with a retrieval metric | a vector database; RAGAS for retrieval evals | vector DB: out of scope for this cut (SPEC §3). RAGAS: development has slowed (Gaps note) |
| **Rule-based verdict** (thresholds in code; the model is told the verdict) | transparent; the model cannot overclaim; testable against planted cases | screening rules, not significance tests (SPEC); thresholds are judgement calls | a trained classifier, e.g. an EBM as in FraudLens; an agent framework | EBM / trained model: 24 teams × 2 waves is too small, "do not report an AUC" (Gaps note, gap 2). LangGraph or any agent framework: out of scope (SPEC §3) |
| **Poisson excess vs comparable teams** (detect) | flags only what exceeds normal variation; "too rare to judge" is explicit; costs only the excess | assumes Poisson counts (no overdispersion); about 1 false flag per site at p < 0.01 | positive excess over the median of comparable teams (v0.6 design spec) | tried on Sept 23: it turned half the teams red on noise (one chance quit = $10.7K). Replaced by the Poisson test in commit "v0.6 analytics: excess vs normal variation" (`git log`) |
| **Difference-in-differences with a placebo check** (prove) | cancels site-wide and seasonal shifts; the placebo shows how unusual the result is | one treated team, 4 comparison teams; directional, not causal; the follow-up data is synthetic | bootstrap CI over comparison teams (v0.6 design spec §4); causal-inference libraries (DoWhy) | bootstrap: the plan (`docs/specs/…-plan.md`, Task 2) switched to Poisson SEs, reason not recorded, **Farid to confirm**. DoWhy: the data cannot defend causal claims (Gaps note) |
| **OLS association + quartile comparison** (explain) | the same presentation as Gallup's meta-analysis; CIs and n shown; clustered SEs | 34 team-waves; about 3 of 65 pairs light up by chance (shown on screen) | a driver model with statsmodels (Gaps note, gap 2) | adopted in this form (statsmodels OLS) |
