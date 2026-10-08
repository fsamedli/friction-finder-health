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

## 03:02 · Restart recorded
- The prompt arrived again at about 03:02. Last entry above was 01:22; nothing happened in between (no commits,
  no file changes; `git status` clean at `9ef4070`). About 100 minutes lost, cause not visible from inside the
  session (consistent with an API stall and the watchdog re-sending the prompt). Continuing from the last 'next'.
- Schedule compressed: the UI work (Phase 2, plus the panel UI) goes to one development subagent working only in
  `web/`, after I fix the typed contracts; I build the backend (Phases 3 to 6) in `app/`, `api/`, `tests/`,
  `evals/`. I own integration, every commit and every gate run.
- MORNING_REPORT.md was not created in Phase 0 as the prompt asked; created now.
- Next: dispatch the research subagent; write the investigation API contract.

## 03:40 · Phase 5a (pulled forward: the tools need it): metric definitions and the structured query path
- `app/metrics.py` (new), `app/db.py` (v_team_ops_month synced from impact's data incl. uploads; teams under 4
  people excluded so totals cannot be differenced; guard blocks `team_ops_monthly` and a CTE shadowing it).
- Tests: `tests/test_metrics.py` (board == query_metric for Night A, 5 KPIs x 2 clocks; small team suppressed and
  absent from totals; missing period, unknown metric/entity; sentence has unit and period). pytest 114 passed.
- Commit `05a7df7`. **Correction:** its message says "pytest 120 passed"; the run printed **114 passed** (98 + 14
  metrics + 2 guard). Not amended (no history rewrites).
- Next: app/llm.py tool-selection helper, app/relations.py, app/investigate.py.

### UI subagent
- 03:13 · UI 1 (`74e3bc7`): nav Today → Investigate → Action plans → Review (+ Workspace), redirects for every v0.6/v0.7 URL, context strip (demo clock + dataset) on every screen, Today first viewport rebuilt (one team, plain-words why, rust "Review Night A and decide"; Nov 30 leads with the review result), warm canvas tokens, EvidenceChip + state components; Method text corrected to "same shift at every site, 4+ people, excluding the team" (what `_comparables` computes) · demo_check 172 passed, 0 failed · next: Investigate screen by the manager's questions.
- 03:24 · UI 2 (`221da79`): Investigate by the manager's questions (5 blocks, each sentence + evidence chip, method one click down), all v0.7 team-screen numbers/charts moved into blocks, PlanEditor (owner, measure, success, existing-plan check, request id, draft kept in localStorage until approved) · demo_check 172 passed, 0 failed · next: Review + Action plans.
- 03:29 · UI 3 (`0e70673`): Review (verdict word first, comparison, limits incl. two-month pulse assumption) and Action plans (owner, measure, success, state, queue) · demo_check 194 passed, 0 failed · next: investigation panel (docked + /ask).
- 03:40 · UI 4 (`437a658`): investigation panel (docked + /ask; v0.7 brief kept at /ask?view=brief) · demo_check 194 passed, 0 failed; axe 0 on 14 routes · next: wait for /api/functions + /api/investigate, then verify the panel against real responses and add the journey + 3 scripted investigations to demo_check.

## 03:50 · Phase 1 research: final note received (subagent ran 03:03-03:45, 107 tool uses)
- `docs/research/2026-10-08_Gallup_Access_Overlap.md`, status "final, 03:45". 27-row overlap table with Help Center
  sources; the three support.gallup.com pages that returned 403 to a plain fetch opened in a browser tab; three
  other URLs 404 (logged in section e). Checked: no gendered pronouns for the sponsor; quotes limited to the two
  allowed sponsor sentences and the allowed class lines.
- Main correction to the Sept 23 note: Gallup AI's "Q12 Action Planning" guided prompt is documented (goals,
  success indicators, follow-up actions). Plan drafting is not our edge; the operating measure and the review-date
  check are. The Help Center says Gallup AI does not use client-specific data; Gallup's marketing page implies
  managers can ask about their survey data (conflict, marked unverified, question 1 for Gallup).
- Frame chosen by the note: a startup's product sold to the client; UI voice = operations language to the site
  manager, limits on screen, no Gallup branding or item wording.
- **Phase 4 labels (gate for building):** 1 why flagged = new · 2 could X explain = new · 3 compare = extend ·
  4 normal for teams like ours = **bridge** (internal peer norm only; external benchmark labelled assumption) ·
  5 when did it start = extend · 6 how widespread = extend · 7 what is missing = new · 8 where does this number
  come from = new · 9 precedent = extend · 10 draft a plan = **bridge** (thinnest plan: operating measure + review
  date) · 11 did it work = new · 12 team conversation = **drop** (not built; quoting Gallup's questions verbatim
  conflicts with the no-item-wording rule; the existing data/docs file stays as it was, see the report).
- Noted, not acted on (hard rule: thresholds unchanged): Gallup documents a meaningful-change rule for item means
  (about 0.2 under 1,000 respondents). Our team-level screen uses 0.30 and a test. Reported for Farid.
- Next: app/investigate.py (coordinator, registry, rules plans, self-check), then the API.
- 03:42 · UI 5 (`e06c0fb`): brand.md v0.8, list page renamed Investigate, Quality approvals note · demo_check 194 passed, 0 failed · next: journey + scripted investigations in demo_check once the endpoints are live.
- 04:24 · UI 6 (`ae20272`): plan editor bug fix (stale prefill restored over the evidence draft) · demo_check 194 passed, 0 failed (HEAD script; the new journey checks wait for the endpoints) · next: still waiting for /api/functions and /api/investigate (not in api/main.py at 04:24).
- 05:14 · UI subagent stopping and reporting. Waited for /api/functions and /api/investigate from 04:15 to 05:13; neither
  `app/investigate.py` nor the endpoints exist yet. Two pieces are written but deliberately NOT committed, because they
  depend on those endpoints: (1) `web/scripts/demo_check.mjs`: the v0.8 journey (Today → Investigate → panel question →
  follow-up → draft → approve in the panel → reload → Action plans → Review) and the three scripted investigations with
  one follow-up each, asserting on the API response shape (status, conclusion, evidence_state, every cited id in the
  register, same conversation_id, context.team_id 4) and on the visible chip, citation and trace; also sets ff.team=4 in
  the init script. They fail until the endpoints answer. (2) `web/src/pages/Trust.tsx`: Architecture tab rewritten for
  the bounded loop (diagram, technique row, "what the AI does/never does", "without a key"). Commit it only once it
  describes code that runs; check the budget numbers in the diagram (6 checks, 8 model calls, 60 s) against the code.
  Next: main session integrates the endpoints, runs ./scripts/demo_check.sh with these checks, then commits both.

## 05:14 · Timestamp correction and second gap
- The two entries above headed "03:40" and "03:50" were written without checking the clock. Git commit times
  (`git log --date=format:%H:%M`) put them at about **03:10** (`05a7df7`) and **03:40** (`0edfcee`).
- Nothing of mine ran between 03:40 and 05:14 (no commits, no edits). Second unexplained gap of about 90 minutes.
- The UI subagent finished at 05:14: `74e3bc7`, `221da79`, `0e70673`, `437a658`, `e06c0fb`, `ae20272` (each
  passed build, lint and demo_check before commit; last demo_check 194 passed, 0 failed). Left uncommitted on
  purpose: demo_check.mjs journey + three scripted investigations (fail until my endpoints exist) and Trust.tsx
  Architecture tab (to commit only when it matches the code).
- From now on every entry time is taken from `date`. Remaining plan, compressed: investigation backend (rules,
  then model) -> plans/feedback endpoints -> Phase 5 scope -> eval pack -> docs -> Phase 7.

## 05:51 · Restart (prompt re-sent at about 05:50)
- Between 05:19 and 05:50 the session stopped while generating app/investigate.py in one long output; the file
  was never written. Same pattern as the 01:22 and 03:40 gaps (each right before a long single output).
  Mitigation: write long files in parts of about 150 lines, commit often.
- State at restart: clean except app/llm.py (choose_tool helper), app/relations.py (new), MORNING_REPORT.md,
  and the UI subagent's two deliberate uncommitted files. Committing llm.py and relations.py now.
