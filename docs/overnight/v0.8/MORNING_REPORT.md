# Morning report: Friction Finder v0.8 (overnight Oct 7-8, 2026, finished in the morning with Farid present)

Branch `v0.8-investigate` (from `523b2c1`). Every claim below points at a commit, a file or raw output in `_verify/`.

**Plain status.** The night lost about 6.5 hours to three stalls with no activity (01:22-03:02, 03:40-05:14,
05:52-09:37; commit times in section 3 show them). Work resumed at 09:37; from 11:16 four parallel development
subagents (UI earlier; then Phase 5, Phase 6, eval pack, docs) worked on disjoint files while I built the
investigation backend and integrated. Functions 1-11 ship keyless and with the model; 12 is not built (research
label: drop). The model's tool selection was verified live (section 4). What is partial is in section 6.

## 1. Open this first
```bash
cd "~/Desktop/DNSC 6317/prototype" && git checkout v0.8-investigate
./scripts/gate.sh docs/overnight/v0.8/_verify final   # the whole gate, keyless; expect every line exit=0
./run_demo.sh                                          # then user menu -> Reset demo; clock Sept 15
```
- Click path (about 5 minutes; full script `docs/demo/DEMO_SCRIPT.md`): **Today** (one team, one rust button
  "Review Night A and decide") -> **Investigate Night A** (blocks: Is it real? Is this normal for teams like ours?
  What explains it? What is missing? What do I do?) -> panel: **"Why is Night A flagged?"** -> challenge **"Could
  staffing explain this?"** -> **Draft a plan** -> **Approve plan** -> clock **Nov 30** -> **Review**.
- The three scripted investigations answer instantly as **Prepared** (generated live with gpt-5-mini at 11:32-11:34,
  labelled with time and model; **Run live** re-runs them, 19-42 s each).
- Before/after: `docs/overnight/v0.8/before_after.html` (v0.7 vs v0.8, 13 routes x 2 widths x 2 clocks).
- Research: `docs/research/2026-10-08_Gallup_Access_Overlap.md`.

## 2. Research (Phase 1, `0edfcee`)
- **Overlap.** Access documents item-level team results, heat maps, Gallup database percentiles, comment analytics with
  AI summaries, AI "Key Insights" and next steps on a team's results, a plan form with Draft/Active/Complete/Overdue,
  and Gallup AI's **"Q12 Action Planning" guided prompt** (goals, success indicators, follow-ups). That corrects the
  Sept 23 note: AI plan drafting is Gallup's, not ours. No public page says Access takes in client operating data;
  the Help Center says Gallup AI does not use client-specific data (Gallup's marketing page implies managers can ask
  about their survey data: a conflict, marked unverified, question 1 for Gallup).
- **Do-not-build:** survey delivery; item dashboards and heat maps; our own Gallup benchmarks; comment sentiment and
  summaries; generic AI coaching; AI next steps from engagement alone and a general AI plan writer; a plan-management
  system; learning content and discussion guides (no Q12 item wording); mobile app and HRIS sync.
- **Frame:** a startup's product sold to the client (the consultant frame lands on Business Impact Analysis, which
  the sponsor described as a presentation). UI voice: operations language to the site manager, limits on screen.
- **Function labels and what happened:** new 1, 2, 7, 8, 11 (built) · extend 3, 5, 6, 9 (built) · bridge 4 (built
  as the thinnest version: internal peer norm; the external Gallup benchmark returns "unavailable: assumed data
  source") · bridge 10 (built thin: owner, one action, operational measure, baseline, review date, success
  criterion) · **drop 12 (not built)**: the panel says Gallup's State of the Team guide in Access covers it.
- Not acted on, for you: Gallup documents its own meaningful-change rule for item means (about 0.2 points under
  1,000 respondents). Our team-level screen uses 0.30 plus a test; thresholds were left unchanged (hard rule).

## 3. What changed
| Screen / function | What was wrong | What changed | Files | Commit |
|---|---|---|---|---|
| Gate | no single reproducible gate or screenshot script | `scripts/gate.sh` (every check, raw output per check), `web/scripts/screens.mjs` | scripts/, web/scripts/ | `9ef4070` |
| Navigation | Teams/Impact/Ask named by analyst concepts | Today -> Investigate -> Action plans -> Review; Workspace below; every old URL redirects; demo clock and dataset on every screen | web/src/App.tsx, Shell.tsx | `74e3bc7` (UI subagent) |
| Today | four KPI tiles and p-values above the fold | one team, why it matters in plain words, one rust next step; evidence-state chips replace significance language; method below the fold. Method text corrected: comparable teams are the same shift at **every** site (the old text said "other sites"; `impact._comparables` includes same-site Night B) | web/src/pages/Today.tsx | `74e3bc7` |
| Investigate | tabs by analysis type | blocks by the manager's questions, each one sentence + one evidence state, chart under it, SQL/method one click down; all v0.7 numbers and charts moved, none removed; panel docked | Investigate.tsx, InvestigationPanel.tsx | `221da79`, `437a658` |
| Review, Action plans | "It worked"; plans without states | Improved / Deteriorated / Inconclusive / Not ready first, then comparison, then limits (incl. the two-month pulse assumption); plan states and a queue of due reviews, missing follow-ups, inconclusive outcomes | Review.tsx, Plans.tsx | `0e70673` |
| Metrics (Phase 5a) | the dashboards and Ask had no shared metric definitions | `app/metrics.py`: one definition per metric; structured plan -> validated -> templated SQL on `v_team_ops_month` (reads the dashboards' rows, uploads included; teams under 4 left out so totals cannot be differenced); test: board == query for Night A, 5 KPIs x 2 clocks | app/metrics.py, app/db.py | `05a7df7` |
| Ask (Phase 5) | refused absence, turnover and safety while the screens showed them (Sept 24 question 3) | answers every operating metric; declines only what the data cannot answer (causes of quits/injuries: no reasons in the data; 2025: not in the data) | app/agent.py, evals/ | `1016171`, `30fe494` (dev subagent A) |
| Investigation (Phase 3) | no follow-ups, no tool choice, no evidence states | one bounded coordinator; 11 read-only tools; model picks the next tool by function calling (6 tools / 8 model requests / 60 s, duplicates refused, run tools not re-offered); rules mode = fixed plan, same output; explicit evidence-state rules; self-check (citations, numbers in the cited evidence, entity and period, percent vs points, causal words); context kept server-side with stale-evidence marking | app/investigate.py, app/tools.py, app/relations.py, app/llm.py, api/investigate_routes.py | `81d0b79` `d3933af` `ff4e495` `2882f47` `f8611f6` `924b3bb` `15aca9a` |
| Functions (Phase 4) | — | 1 why flagged (ranked hypotheses), 2 could X explain (staffing / who responded / site-wide / hour band), 3 compare, 4 normal (bridge), 5 when did it start, 6 how widespread, 7 what is missing (gaps with owners), 8 provenance, 9 precedent, 10 draft plan (bridge), 11 did it work; each a chip and typed | same | same |
| Plans and feedback (Phase 6) | approvals not recorded with edits; no duplicate guard; feedback only yes/no | plan fields, existing-plan check, request_id double-submit guard (explained 200), approvals.jsonl record, plan board; feedback reasons on answers with evidence ids; Quality counts from zero; `evals/from_feedback.py` | api/main.py, evals/from_feedback.py | `2fe2bb3` (dev subagent B) |
| Eval pack | — | `evals/investigate/` 16 cases (multi-turn, fault injection); first run 11/16 recorded before fixes | evals/investigate/ | `dfa5dc5` (dev subagent C) |
| Concurrency bug | found by the gate: background investigations and requests shared one DuckDB connection; /api/ask failed | one lock around the connection; 20 parallel requests, 0 errors | app/db.py | `7c41a69` |
| Docs | described v0.7 | ARCHITECTURE, HOW_IT_WORKS, DEMO_SCRIPT, README, TEVV, Trust > Assumptions rewritten from the code | docs/, README.md | `b4682ea` `046db00` `afe5738` `779085b` (dev subagent D) |
| Integration | — | demo_check walks the new journey and the 3 scripted investigations; Trust > Architecture for the loop; investigation pack on Quality | web/scripts/demo_check.mjs, Trust.tsx, api/main.py | `660fb07` |

## 4. Verification (raw; files in `docs/overnight/v0.8/_verify/`)
**Gate on HEAD** (`scripts/gate.sh docs/overnight/v0.8/_verify head`, keyless), `head_summary.txt`:
```
build        exit=0  ✓ built in 503ms
lint         exit=0  > oxlint
pytest       exit=0  127 passed, 3 warnings in 8.85s
gold         exit=0  lookups: 6/6 | briefs regenerated or fallen back: 0
adversarial  exit=0  adversarial (seen during development (not a holdout)) · rules-only: 15/15 passed · failures by taxonomy: none
investigate  exit=0  investigate (seen during development (not a holdout)) · rules-only: 16/16 passed
demo_check   exit=0  304 passed, 0 failed
a11y         exit=0  0 rules violated, 0 nodes
gate exit=0
(on afaed90, 12:31 local)
```
Baseline for comparison (`baseline_summary.txt`, on `523b2c1`): pytest 98 · gold 12/12 · adversarial 15/15 ·
demo_check 158/0 · axe 0. The demo_check growth (158 -> 304) is the old checks re-pointed to the new routes plus the
new journey, redirects, plans/review states and the three scripted investigations; two old check texts changed
wording ("It worked" -> "Improved", the upload banner), none were removed.

**pytest with the GW key** (`final_pytest_withkey.txt`, 12:06): `3 failed, 124 passed in 132.40s`. Two are the v0.5
tests that already failed with a key on Sept 23 (the model's wording varies: `test_blip_is_insufficient_no_owner`,
`test_chat_fallback_is_grounded`). The third, `test_main_question_is_supported_and_owned`, passed on a single rerun
with the key (26 s): model nondeterminism, not reproduced. Keyless: 127 passed.

**Eval packs, first run beside final** (all "seen during development", builder-written):
| Pack | Mode | First run | Final |
|---|---|---|---|
| Gold (`evals/questions.json`, now 13 with E13) | rules | 12/13 (`1016171`, E13 refused before the Phase 5 fix) | 13/13, TP 2 FN 0 FP 0 TN 5, lookups 6/6 |
| Adversarial (15) | rules | 15/15 at baseline | 15/15 |
| Investigation (`evals/investigate/`, 16) | rules | **11/16** at 07:20 UTC (I05, I10, I11, I15, I16) | **16/16** |
| Investigation | gpt-5-mini | **15/16** at 08:26 UTC (I09 zero denominator: "investigation failed", a TypeError in a comparison tool the model chose) | not re-run as a pack; I09's scenario re-run alone after the fix: answered "undefined rather than zero", state unavailable (29.7 s) |
Model-mode gold and adversarial were not re-run tonight (last model runs Sept 24: 12/12 and 15/15).

**Live model behaviour: verified.** The GW deployment (gpt-5-mini, API version 2024-10-21) accepted function calling
with strict schemas (`selection: function_calling` in every live turn; the JSON fallback never ran). Eleven live turns outside the pack
plus the 16-case model pack. Saved traces: `live_investigations_2026-10-08T073204+0000_gpt-5-mini.json` (the six
prepared turns: 19.0-41.7 s, 4-6 tool calls, 6-7 model requests, 6/6 passed the self-check, 5 with model wording and
1 with the labelled template after a GW 429). Behaviour seen: the model re-picked a finished check (duplicate guard
stopped it; checks that ran are no longer offered); for a plain count question it still ran 6 checks (29.7 s).

## 5. Live demo risks (what breaks first, and the fallback)
| Step | Mode | Latency (measured today) | Breaks how | Fallback |
|---|---|---|---|---|
| Today, Investigate blocks | code (rules plans) | under 1 s per block (keyless pack: 0.4-0.5 s per case) | server not running | `./run_demo.sh`; check nothing else holds the port first (`lsof -i :8000`): a stale server on 8010 hung one demo_check run for 20 minutes today |
| Panel, scripted questions | Prepared (model output saved 11:32-11:34) | instant | none expected | it is labelled "Prepared"; say so |
| Panel, "Run live" or a new question | model (gpt-5-mini, function calling) | 17.6, 19.0, 21.4, 22.5, 25.7, 26.3, 27.8, 29.7, 29.9, 41.7, 57.8 s (eleven live turns today) | slow; a GW **429 rate limit** happened once (11:33); near the 60 s budget the wording step is skipped | labelled template text; with no key the same tools run as a fixed plan (rules mode) |
| Draft a plan, Approve | code | under 1 s | double click | request_id guard returns the existing plan with an explanation |
| Review (clock Nov 30) | code | under 1 s | wrong clock | top bar -> demo clock -> Nov 30 |

## 6. Not done (blunt)
- **Function 12** (team conversation): not built; research label drop.
- **Tier 2 model-written SQL:** not shipped (optional). The model still writes no SQL; docs say so.
- **Investigation pack in model mode:** see section 4 (run once at the end, or "not run" with the reason).
- **No prompt-injection case in the investigation pack.** Retrieved text is labelled when it looks like an
  instruction and is passed to the model as data, but only the v0.5 adversarial pack (A07, A08) tests injection, on Ask.
- **"Hybrid" retrieval is partial:** comments are ranked by the embedding search after the code-counted top theme's
  keywords are added to the query; there is no single weighted keyword+embedding score. Superseded or conflicting
  procedures are not detected (none exist in the demo documents).
- **Public web search:** off and not implemented; whether the GW deployment exposes it was not checked.
- **Commit gating:** with five writers in one tree, not every individual commit ran the full gate in isolation (my
  backend commits ran pytest; UI commits ran build, lint and demo_check; agents ran their own suites). The full gate
  ran at integration (`660fb07`) and at the end (section 4). The `05a7df7` message says "pytest 120"; the run printed 114.
- **Screens with a live model answer:** the after-screenshots show the prepared answers (model-generated, labelled
  with time and model); no screenshot was taken during a live run.
- `../CLAUDE.md` / `../AGENTS.md` project-state sections are still stale (repo is now React + FastAPI v0.8); not edited.
- Unchanged and still reported: complementary suppression (TEVV gap); the usability study has no data.
- **Next three priorities:** (1) rehearse the 5-minute path on the presentation laptop with `scripts/gate.sh` green;
  (2) add investigation cases for injected comment text and for a second team (Norfolk Night A); (3) cut live latency
  (fewer tool-choice calls: let the model pick 2-3 checks in one call) and re-measure.

## 7. Decisions made for Farid (how to reverse)
1. **Prepared answers by default** for the 3 scripted investigations (labelled, Run live). Reverse: delete `data/prepared/investigations.json`.
2. **Comparable-teams wording fixed to match the code** (same shift at every site) instead of changing `impact._comparables`. Reverse: change the code (statistical logic, your call).
3. **Causal questions about quits and injuries are declined, with the counts shown** (no reason data). Reverse: the decline rules in `app/agent.py` (dev subagent A) and `CAUSE_OF_RARE` in `app/investigate.py`.
4. **"No effect" in impact.did shown as "Deteriorated"** (its CI lies entirely above zero: the KPI rose vs comparison). Reverse: the label maps in `web/src/pages/Review.tsx` and `app/tools.py review_result`.
5. **Function 12 dropped** per the research. Reverse: build it on `agent._item_questions` (already in the repo).

## 8. Questions
1. `data/docs/gallup_item_discussion_questions.md` quotes Gallup's item discussion questions verbatim (since v0.5; the v0.5 plan uses them). The research says verbatim quoting conflicts with the no-item-wording rule and Gallup's copyright. Keep or remove?
2. Adopt Gallup's documented meaningful-change rule for item means (about 0.2 points under 1,000 respondents) instead of our 0.30 screen? It changes thresholds, so it needs your decision.
3. On Dec 10, show the prepared (labelled) answers on stage and run live only in Q&A, or run live on stage (18-58 s today)?
