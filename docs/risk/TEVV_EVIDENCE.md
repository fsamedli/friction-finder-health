# TEVV evidence map, Friction Finder v0.7

**This is evidence for Yukari's risk write-up, not the write-up.** One row per NIST AI RMF trustworthy
characteristic. Each row gives the risk in *this* product, the control in code (file:line on branch
`v0.7-saas-ui`, Sept 24, 2026), the test or eval that checks it, the **current result from a real run
tonight**, and the gap.

**Structure.** This follows Patrick Hall's `github.com/jphall663/gai_risk_management` (read Sept 24, 2026;
README last pushed Jan 17, 2026):
- characteristics crossed with NIST AI 600-1 GAI risks (its Section A)
- risk tiers from an impact × likelihood matrix (Section B.4, adapted from NIST SP 800-30)
- measurement scaled to the tier (Sections F–H). Low: model testing. Medium: plus red-teaming. High: plus
  structured experiments and human feedback.

I did not copy its tables; the risk names follow its NIST 600-1 vocabulary.

## System-level tier (proposal for Yukari; Farid and Yukari to confirm)

**Medium.** The AI model only reads questions and writes text from computed evidence. Numbers, verdicts and
plans are computed by code and approved by a person, and the tool takes no action outside itself (**impact:
moderate**). But its output steers where managers spend effort, it runs on employee survey data, and a
wrong or overclaimed finding could be pinned on a team (**likelihood: moderate**). Under the repo's scheme,
Medium calls for model testing **and red-teaming**; we have both (gold and adversarial packs).
"Structured experiments and human feedback", which the High tier requires, exist only as an empty kit
(usability study, "Useful?").

## Evidence by characteristic

Results are from runs on Sept 24, 2026 unless marked. Files: `docs/overnight/_verify/`, `evals/**/results/`.

| Characteristic | Tier | Risk in this product (NIST 600-1 risk) | Control in code | Test / eval | Current result (real run) | Gap |
|---|---|---|---|---|---|---|
| **Valid and reliable** | Medium: a wrong "look here first" wastes a site's effort, but a person reviews it | The tool flags noise as a finding, or the model states numbers that are not in the data (Confabulation) | Detection only beyond normal variation: `app/impact.py:47` (OPS_P), `:45` (ITEM_P, Bonferroni), `:46` (MIN_EXPECTED); verdict rules `app/agent.py:704`; brief checker `app/agent.py:793`; grounding count `api/main.py:528` | Gold questions (`evals/questions.json`, 12, confusion matrix); `tests/test_impact.py` (planted blip → not flagged; mix artifact → not red; DiD CI); number check on model briefs | Gold **12/12 rules** (`evals/results/latest_rules-only.json`), **12/12 gpt-5-mini** (run 04:17 UTC, 73.6 s); TP 2, FN 0, FP 0, TN 5. Model-brief numbers checked **19/19** (3 prepared briefs). pytest 98/98 (no key) | The builder wrote both the data and the questions (**not independent**; the holdout kit `evals/holdout/` is empty). Synthetic data; 24 teams. About 1 false operating flag per site expected at p < 0.01 |
| **Safe** | Medium | Output used to blame or discipline a person; a manager scorecard invites gaming (Human-AI Configuration) | No manager names in any board, team or impact output (`app/impact.py` returns team, shift, headcount only); out-of-scope guard `app/agent.py:984` (performance reviews, discipline, predicting who quits); causal wording avoided ("association, not cause", "directional, not causal"); every plan approved by a person (`api/main.py` `POST /api/plans`) | Adversarial pack: causal bait A09–A10, out of scope A11–A12 | **4/4** in rules and gpt-5-mini (`evals/adversarial/results/latest_*.json`). First run before the fix: A11 and A12 **failed** in both modes | No live user study; the harm pathway (misuse by leadership) is untested. Adversarial cases were written by the builder |
| **Secure and resilient** | Medium | Prompt injection through an employee comment; data exfiltration through generated SQL; the demo dies with the network (Information Security, Value Chain) | SQL guard (sqlglot) `app/db.py:154`, called by `run_sql` `:201`: allowlist every table, no table functions, single SELECT; the model never writes SQL (templated queries); rules-mode fallback without a key or network; upload validation `app/impact.py:92` | `tests/test_sql_guard.py` (18 parametrized cases incl. comma-join and `read_csv` bypasses); adversarial A07–A08 (injection hidden in a comment); `scripts/demo_check.sh` runs **without a key** | Guard **all cases pass**; both Sept 23 bypasses now raise ValueError. Injection **2/2** in both modes. Demo gate **158/158**, keyless | No authentication, no rate limiting; runs on localhost only. Only 2 injection cases. No dependency or supply-chain scan |
| **Accountable and transparent** | Low: logs exist; the user can see what the AI did | Users can't tell what the AI wrote vs what code computed; decisions not traceable (Human-AI Configuration, Information Integrity) | Provenance badges (Computed / AI-written, checked / Needs your decision); step trace with real timings `api/main.py:541`; evidence register with SQL; prepared answers labelled with time, model and "Run live" (`api/main.py:473`); review log `approvals.jsonl` (`api/main.py:569`); feedback `feedback.jsonl` | `tests/test_api.py::test_ask_reports_grounding_and_trace`, `::test_prepared_answer_is_labelled_and_live_bypasses_it`; gate checks "Prepared answer", "Run live", "How this answer was produced" | All pass (pytest 98/98; gate 158/158) | Logs are local files, not tamper-evident, with no user identity. The prepared answers are cached (labelled), so the live model path is exercised only on "Run live" |
| **Explainable and interpretable** | Low | A manager can't tell why a team is flagged or how sure the tool is (Human-AI Configuration) | Every flag shows observed vs expected, p, and a "Method" popover; CIs and n on associations and the DiD; "too rare to judge"; a plain-language conclusion at the top of each screen; technique table (Trust › Architecture, `docs/ARCHITECTURE.md`) | Gate checks labels: "Association, not cause", "95% CI", "Synthetic data", "too rare"… | Present on every screen (gate 158/158) | **Comprehension is not measured.** The usability kit (`docs/usability/`) has **no data yet** |
| **Privacy-enhanced** | Medium: employee survey data | Individual answers or small teams identified, directly or by differencing (Data Privacy) | n ≥ 4 in SQL views (`app/db.py:39`, `:59`, `:76`, `:92`); comments from small teams never indexed (`app/db.py:135`); teams under 4 people show no team numbers (`app/impact.py:265`); individual-level requests declined (`app/agent.py:984`); `responses` not in the allowlist (`app/db.py:154`) | `tests/test_impact.py` (small team rolled up), `tests/test_api.py::test_small_team_no_scores`, SQL guard tests; adversarial A01–A06 | Adversarial privacy cases **6/6** in both modes (first run: A02–A04 rules, A03–A05 model **failed**). **Differencing check tonight:** site mean minus visible team means gives the pooled mean of the suppressed teams. In all 6 site-waves that pool is **n ≥ 4 (4 to 8 people)**, so no single team is revealed in this data | **Complementary suppression is not enforced.** With other data, a site-wave with exactly one suppressed team would let a user back out that team's mean. Fix: suppress the site figure, or a second team, when the residual n < 4. Not done |
| **Fair with harmful bias managed** | Medium | A team looks worse because of who responded (new hires, non-response), or a shift is compared unfairly (Toxicity, Bias, and Homogenization) | Engagement change adjusted for tenure mix (`app/impact.py:204`, `_engagement`); v0.5 signal check (shift-share); comparisons only within the same shift at other sites (`app/impact.py:243`) | `tests/test_impact.py::test_mix_artifact_is_not_red` (planted P6); gold E6 (decline real?) | Pass (pytest 98/98; gold 12/12) | No demographic or protected attributes exist in the data, so group fairness **cannot be tested**. Non-response bias beyond tenure is not modelled (raised by a judge, per the feedback log) |

## What a reviewer can re-run

```bash
.venv/bin/python -m pytest tests -q                    # 98 tests (no key needed)
.venv/bin/python -m evals.run_evals --no-model         # gold, 12 questions
.venv/bin/python -m evals.adversarial.run --no-model   # adversarial, 15 cases
./scripts/demo_check.sh                                # demo path at 1440/390 px, keyless
```
