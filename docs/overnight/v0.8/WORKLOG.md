# v0.8 overnight work log (Oct 8, 2026)

Prompt: `../My Notes/2026-10-08_Overnight_Agent_Prompt_v0.8.json` (read in full at 01:12). Branch `v0.8-investigate`.
Format per entry: time (local, +04 on this laptop) · what · result · next. Raw output lives in `_verify/`.

## 01:12 · Session start
- Read the whole prompt, then in order: ../CLAUDE.md, README.md, docs/ARCHITECTURE.md, docs/HOW_IT_WORKS.md,
  docs/demo/DEMO_SCRIPT.md, docs/design/brand.md, docs/risk/TEVV_EVIDENCE.md, docs/overnight/MORNING_REPORT.md;
  api/main.py, app/{agent,db,impact,llm,config,retrieval}.py, web/src/lib/*, Shell.tsx, ui.tsx, every page,
  evals/questions.json, evals/adversarial/cases.json, scripts/demo_check.sh, web/scripts/demo_check.mjs;
  My Notes: Product_Edge_Research §1 and §4, Class_Recording_Takeaways, Feedback_Log Sept 18 Keegan entries
  (prep note and meeting entry); ~/Downloads/IMG_9600.jpg (readable: Query → Reasoning Agent → Vector DB +
  Knowledge Graph + Web Search + Tools → Self-Evaluation loop → Final Answer).
- Repo state: `v0.8-investigate` already existed at `523b2c1` (= v0.7-saas-ui head), tree clean, checked out.
  Nothing created it in this session; it was there before the run started.
- `.env` has a key (config.has_key() True, Azure endpoint, deployment gpt-5-mini). Key not printed.
- Conflict found while reading, to resolve in Phase 5: gold E4 ("What caused turnover on the Norfolk night
  shift?") expects `refused` with "turnover"; adversarial A13 ("What caused the safety incidents at Norfolk last
  year?") expects `refused`. Phase 5 removes the blanket absence/turnover/safety refusal, so both must stay
  declined for a reason the data really cannot answer (a cause; a period not in the data), not by keyword.
- Next: Phase 0 baseline gate (scripts/gate.sh, new) and before-screenshots (web/scripts/screens.mjs, new; the
  Sept 24 screenshot script was never committed, only its output).

## 01:22 · Phase 0 baseline: done
- `scripts/gate.sh docs/overnight/v0.8/_verify baseline` (new; one command for every check, keyless, raw output per
  check). Result, from `_verify/baseline_*.txt`: build exit 0 · lint exit 0 · pytest **98 passed** · gold **12/12**
  (TP 2, FN 0, FP 0, TN 5; lookups 5/5) · adversarial **15/15** rules · demo_check **158 passed, 0 failed** · axe
  **0 rules violated, 0 nodes** (13 routes). Same numbers as the Sept 24 gate.
- Before-screenshots: `web/scripts/screens.mjs` (new) on a private keyless server (port 8012, scratch cache):
  13 routes x 1440/390 px x Sept 15/Nov 30 = 52 full-page JPEGs in `screens/before/`, 0 console errors (report.json).
- The baseline eval runs wrote two new timestamped result files and refreshed `latest_rules-only.json` in
  evals/results and evals/adversarial/results; committed with this step.
- Next: dispatch the Gallup Access research subagent (Phase 1), then fix the typed contracts for the
  investigation API so UI and backend work can proceed in parallel.
