# Morning report: Friction Finder overnight run

The overnight sections (the format from `My Notes/2026-09-23_Overnight_Agent_Prompt.md`) are filled in
below as the night goes on. First: the report for the evening session (Sept 23, about 21:30–23:45), in
the 5-part format of the JSON prompt, as requested.

---

## Evening session report (Sept 23, 2026, ends 23:45)

Branch at the end of the evening: `v0.6-detect-explain-act-prove` (last commit `2ff26f9`). The overnight
work continues on `v0.7-saas-ui`, branched from that commit.

### 1. Review findings (v1, before any rebuild)

Measured with in-page iframes at 1440 px and 390 px, both as-of dates. Screenshots in `docs/review/before-*.jpg`.

| # | Page | Issue | Severity | Screenshot |
|---|---|---|---|---|
| 1 | All pages at 390 px | Board page 499 px wide on a 390 px screen (horizontal scroll); header 166 of 844 px tall; step nav clipped | blocks demo | `before-board-390.jpg` |
| 2 | /ask | ~30 s model call shows one line of text; looks frozen | blocks demo | — |
| 3 | All | No product frame: Ask, Business case, Under the hood reachable only from the footer; reads as a report | a judge would notice | `before-board-1440.jpg` |
| 4 | /why/4 | Page 2,387 px tall; primary action ("Draft a plan") at the very bottom | a judge would notice | `before-why-1440.jpg` |
| 5 | /why/4 | 6 item labels clipped with an ellipsis | a judge would notice | `before-why-1440.jpg` |
| 6 | / at Nov 30 | "No team is outside normal variation" with no link to the plan that fixed it; the story is lost | a judge would notice | — |
| 7 | /ask, /why | Grounding not visible (no "numbers checked", no step trace) | a judge would notice | — |
| 8 | app/db.py | False privacy claim: comma-join and `read_csv` bypass the SQL guard | a judge would notice (security) | — |
| 9 | /why/4 at Nov 30 | Headline mixes two time windows | polish | — |
| 10 | All | 2.35 rem serif headlines push content below the fold | polish | — |

Found later while rebuilding, both fixed:
- **Story bug:** at "Sept 15" the app showed Night A's plan as already in progress (it starts Sept 21).
- **Demo-breaking bug:** a plan approved live got a review date of start + 60 days (Nov 20). On the
  Nov 30 clock that leaves one full month of follow-up, so the review would have said "insufficient"
  at the demo's high point.

### 2. Changes made

| Page / area | What was wrong | What changed | Files | Commit |
|---|---|---|---|---|
| API | Grounding not visible | `/api/ask` returns `grounding` (numbers in the brief found in the evidence) and `trace` (steps with real seconds, from the run's own notes); `/api/sources` added | `api/main.py`, `tests/test_api.py` | `35791b0` |
| Whole app | Report, not product (#3); mobile broken (#1) | New SaaS shell: dark sidebar, top bar with site switcher, demo clock, Manager/HR role switch, notifications; 10 screens (Today, Teams, Team detail with tabs, Action plans, Impact, Insights, Ask, Data sources, Business case, Trust & method); old URLs redirect | `web/src/**` | `676ff54` |
| Team detail | #4, #5, #9 | Conclusion sentence in the header; one primary action; tabs instead of one long scroll; labels wrap | `web/src/pages/TeamDetail.tsx` | `676ff54` |
| Today | #6 | At Nov 30 the headline reads "Richmond Night A's plan worked…" with "See the review" | `web/src/pages/Today.tsx` | `676ff54` |
| Plans / demo path | Story bug; review-date bug | Seeded plan appears only once the clock passes its start, or as a fallback; plans approved live show everywhere; review date snaps to the end of the second full month (Sept 21 → Nov 30); "Reset demo" in the user menu | `web/src/lib/store.tsx`, `api/main.py`, `tests/test_api.py` | `676ff54` |
| Plan draft | Focus item was "My opinions seem to count" while the KPI was late departures | Focus is the dropped item linked to the plan's KPI (Q02, Materials and equipment) | `TeamDetail.tsx` | `676ff54` |
| 390 px | Top bar 409 px; Today 594 px at Nov 30 | Compact top bar; explicit single-column grids; captions wrap | `Shell.tsx`, `pages/*` | `5cb5e15` |
| Ask | #2, #7 | Progress stepper (labelled estimated, retimed to measured gpt-5-mini timings); "N of N numbers checked against the evidence"; collapsible step trace | `pages/Ask.tsx` | `676ff54`, `260d248` |
| Security | #8 | `run_sql` parses with sqlglot; every table must be allowlisted; table functions, schema-qualified names, multi-statements and CTEs that shadow real tables are refused | `app/db.py`, `tests/test_sql_guard.py`, `requirements.txt` | `260d248` |
| README | Demo path out of date | New demo path, old-URL redirects, SQL guard | `README.md` | `2ff26f9` |

Evidence that the two bypasses are blocked (run after `260d248`):
```
BLOCKED SELECT r.* FROM sites, responses r LIMIT 3 -> Query touches non-allowed tables: ['responses']. Respondent rows are never exposed.
BLOCKED SELECT x.* FROM sites, read_csv('data/generated/responses.csv') x LIMIT 3 -> Table functions are not allowed: READ_CSV('data/generated/responses.csv')
```
Before the fix, `tests/test_sql_guard.py` had 3 failures: both bypasses got through, and a legitimate
CTE query was wrongly blocked. After the fix, 18 pass.

Live demo path, driven in Chrome (Sept 15 → Investigate Night A → Create plan → Approve → See if the plan
worked → "76 days" → Fast-forward): the Impact page read "It worked … −10.6 per 10 people / month · 95% CI
−16.7 to −4.4 … about $6,653 a quarter". Screenshots: `docs/review/after-impact-countdown.jpg`,
`docs/review/after-impact-worked.jpg`.

Model mode, one real `/api/ask` call: 14.6 s, `grounding {'checked': 12, 'total': 12, 'unmatched': []}`.
Trace: understand 2.8 s (model) · query 0.5 s (code, 11 SQL queries, 73 rows) · retrieve (embeddings,
5 passages) · verdict (code) · write 11.2 s (model) · check (code, 12 of 12, 1 repair).

### 3. Verification (raw, captured 23:45 on `v0.7-saas-ui` = `2ff26f9`)

`npm run build` (web/), tail:
```
✓ built in 470ms
exit=0
```
It also warns that the JS bundle is over 500 kB (it is 1 file; no functional impact).

`npm run lint`:
```
> oxlint

exit=0
```

`.venv/bin/python -m pytest tests -q` **with the GW key present** (model calls live):
```
FAILED tests/test_agent.py::test_blip_is_insufficient_no_owner - assert 'no t...
FAILED tests/test_agent.py::test_chat_fallback_is_grounded - AssertionError: ...
2 failed, 90 passed in 116.73s (0:01:56)
```
**Without a key** (deterministic rules mode): `92 passed in 5.29s`.
Both failures are model-dependent v0.5 tests and existed before these changes:
- `test_chat_fallback_is_grounded` expects rules mode but gets the model when a key is present.
- `test_blip_is_insufficient_no_owner`: gpt-5-mini wrote "No test **is** proposed…" and the test expects
  "no test proposed". It passes in rules mode.

`agent.py` was not changed. The tests were not weakened. Full logs are in `docs/overnight/_verify/`.

`.venv/bin/python -m evals.run_evals --no-model`:
```
model: rules-only | retrieval: keyword | 12/12 passed in 0.2s
confusion matrix over planted problems: TP=2 FN=0 FP=0 TN=5
lookups: 5/5 | briefs regenerated or fallen back: 0
```

Route audit (in-page iframes, after `5cb5e15`): every route at 1440 px and 390 px, both dates. 0 JS
errors, 0 horizontal overflow, no page stuck loading. Remaining truncations are deliberate: a label inside
the horizontally scrollable Teams table, which has a tooltip.

`./run_demo.sh` from a clean state (`web/dist` removed, PORT=8001): it ran `npm ci` and the build, then
served. `GET /` 200, `GET /api/board` 200, deep link `GET /teams/4` 200.

Screenshots: `docs/review/before-{board-1440,board-390,why-1440}.jpg` and
`docs/review/after-{today-1440,today-390,teams-1440,team-detail-1440,impact-countdown,impact-worked}.jpg`.

### 4. Not done

- **Your Chrome tab for 127.0.0.1 is zoomed to 125%**, measured (window 1440 px, page 1152 px).
  Everything you looked at was oversized. Press ⌘0 on that tab.
- Coordinate clicks from the browser automation missed at that zoom, so the Approve and Fast-forward
  buttons in the live walkthrough were clicked from inside the page (`element.click()`). The handlers,
  the POST and the pages that followed are verified; a physical mouse click at 100% zoom was not.
- `pages_v1/` and `components_v1/` were deleted in `676ff54`, before the "parity checklist first"
  instruction arrived. The v1 code is intact in git history (`35791b0` and earlier). The parity
  checklist is being written from that history overnight.
- `/api/sources` says "connected" next to vendor names. That breaks overnight rule 6; it is fixed first
  thing overnight.
- The pricing figure on Business case is derived from our own value estimate (10% of the low case, per
  site per month) and labelled "Hypothesis". It is not a market price. Simon should own and validate it.
- No held-out eval set and no user test yet (known limit, shown on the Trust page).

### 5. Questions

1. Pricing: keep the derived hypothesis on screen, or show no number until Simon has a validated one?
2. Should "Reset demo" stay visible in the user menu for the real presentation, or be hidden behind a URL flag?
3. The v0.5 Ask engine still refuses questions about "absence", "turnover" and "safety" (a v0.5 rule),
   while the new screens show absences and quits. Change that rule in the RAG/SQL phase you planned, or now?

---

## Overnight run, Part 1 (Phases 0–6), Sept 24, 00:00–01:30

### 1. Open this first
```bash
cd "~/Desktop/DNSC 6317/prototype" && git checkout v0.7-saas-ui
./run_demo.sh                      # rebuilds web/ if needed, serves http://127.0.0.1:8000, opens the browser
```
Then click **Start demo** in the top bar: 4 steps, Detect → Explain → Act → Prove. Use **Reset demo** in
the user menu (top right) between rehearsals. **Press ⌘0 first**: your Chrome tab for 127.0.0.1 was at 125% zoom.

Before/after screenshots: `docs/overnight/before_after.html` (open it in a browser; 28 pairs plus the guided-demo strip).

### 2. What changed (overnight, on top of the evening work above)
| Page / area | What was wrong | What changed | Commit |
|---|---|---|---|
| Data sources | Said "connected" next to UKG, Workday and others (breaks rule 6) | Every source reads **Demo CSV (synthetic)**; vendors read "Would connect to, e.g. …"; HRIS "Not connected"; test added | `bc16080` |
| Whole app | Teal used for buttons; rust unused; v1 logo lost | Colour roles: teal only for computed things; rust only for human decisions (Create action plan, Approve plan, Approve in Ask, New plan); ink for navigation; "Watch" moved to amber-yellow so it can't be confused with rust; v1 mark restored; legend in the sidebar | `14b40c3` |
| Today, Team detail, Impact | The Detect → Explain → Act → Prove loop from v1 was gone | Journey strip on the four loop screens; each step links to its screen | `14b40c3` |
| Today | No annualized figure; "ranks obstacles, not managers" not visible | "$X a year if it held" under the excess figure; note under the attention list; "data through Aug 31, 2026" stamp | `14b40c3`, `43ec060` |
| Teams | No quits column; no "too rare to judge" | Quits column showing "too rare to judge" when fewer than 3 are expected; footer explains observed / expected | `14b40c3` |
| Team detail | Evidence tab without timing; small-team page had no way back | "rules mode · 0.1 s" badge; "Back to teams" button | `14b40c3` |
| Top bar | No guided demo | **Start demo**: 4-step walkthrough with one sentence per step and no numbers in the narration; step 3 approves the plan live; step 4 fast-forwards to the review | `43ec060` |
| Docs | — | `docs/design/brief.md` (9 patterns and 3 anti-patterns with sources; notes what could not be verified); `docs/design/brand.md` (tokens); README v0.7 section | `14b40c3`, `43ec060`, this commit |

Phase 1 (privacy fix) was done in the evening (`260d248`) and re-verified. Phase 4's "delete `pages_v1/`" step had
already happened in `676ff54`; the parity checklist was reconstructed from `004280d` and every item is ticked
(WORKLOG.md).

### 3. Verification (raw; captured at `43ec060`; files in `docs/overnight/_verify/`)
`npm run build`:
```
✓ built in 510ms
exit=0
```
`npm run lint`:
```
> web@0.0.0 lint
> oxlint

exit=0
```
`pytest tests -q`, no key: `92 passed in 5.40s` (exit 0). With the GW key present, the evening run gave
`2 failed, 90 passed`; both failures are model-wording tests from v0.5 (see the evening section).

`evals.run_evals --no-model`:
```
model: rules-only | retrieval: keyword | 12/12 passed in 0.2s
confusion matrix over planted problems: TP=2 FN=0 FP=0 TN=5
lookups: 5/5 | briefs regenerated or fallen back: 0
exit=0
```
Screenshots: 28 before (v1 from a worktree at `004280d`) and 56 after (14 routes × 1440/390 × Sept 15/Nov 30).
**All 56 after: no horizontal overflow, 0 JS or console errors** (`screens/after/report.json`). v1 overflowed
at 390 px on `/` (500 px wide).

Guided demo with **real mouse clicks** (headless Chrome at 100% zoom, `demo_walk.mjs`):
```
ok  step 1 detect: found "Night A needs attention"
ok  guide: found "Step 1 of 4"
ok  step 2 explain: found "what comparable teams predict"
ok  step 3 act: found "Draft action plan"
ok  approved: found "See if the plan worked"
ok  step 4 prove: found "It worked"
ok  ci: found "95% CI"
ok  synthetic: found "Synthetic data"
plans now: plan-richmond-night-a 2026-09-21->2026-11-30 | plan-accb0192 2026-09-21->2026-11-30
console errors: 0 []
```
`./run_demo.sh` from a clean state (`web/dist` removed, PORT=8001): `added 148 packages`, `✓ built`,
`Uvicorn running`, `GET / 200`, `GET /api/board 200`, `GET /impact/plan-richmond-night-a 200`
(`_verify/run_demo.txt`).

### 4. Parity checklist
All items are ticked; the full list is in `docs/overnight/WORKLOG.md` under "v1 parity checklist". The 7 gaps
found in Phase 2 were closed in `14b40c3`.

### 5. Not done / broken / worried about (live-demo risks first)
1. **Ask with the model takes about 15 s** (measured 14.6 s) and depends on GW Azure and the network. On
   stage, run the guided demo, which makes no model calls, and use Ask only in Q&A. Without a key, Ask falls
   back to rules mode and says so.
2. Two v0.5 tests fail when the key is present because the model's wording varies
   ("No test is proposed" vs "No test proposed"). Deterministic mode is 92/92. I did not change the tests.
3. The v0.5 Ask engine refuses "absence", "turnover" and "safety" questions, while the new screens show
   absences and quits. A judge could spot that contradiction; see question 3.
4. The pricing figure is a hypothesis derived from our own value estimate, labelled as such. Simon should
   validate it before it goes in the deck.
5. The JS bundle is one 600 kB file (Vite warning). It loads in well under a second locally; not a demo risk.

### 6. Decisions I made for you
1. **Colour roles are strict:** only "decide" actions are rust, so "Investigate Night A" and "See the review"
   are ink. Reversible in `components/ui.tsx`.
2. **The review date snaps to the end of the second full month** after the start (Sept 21 → Nov 30), because
   the operating data is monthly.
3. **The seeded Night A plan is a fallback:** hidden before Sept 21 and whenever a plan was approved live, so
   the demo shows the manager creating it.
4. **Guided demo narration contains no numbers**, so it can never contradict the screen.
5. **The v1 logo was restored** (as the prompt asked) instead of the evening's chart-line mark.

### 7. Questions for me
1. Pricing: keep the derived hypothesis on screen, or show no number until Simon has a validated one?
2. Keep "Reset demo" in the user menu for the real presentation, or hide it?
3. Update the v0.5 Ask rule so questions about absences and quits are answered from the new team-month
   data now, or wait for your planned RAG/SQL phase?
