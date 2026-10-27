# Oct 27, 2026 round: what Prof. Hall asked for on Oct 21, and what we build today

Sources, in order of authority: Farid's same-day notes (`2026-10-21_Prof_Hall_Feedback_for_Group_Chat.txt`, one
folder up) and the teammate minutes (`~/Downloads/Meeting Minitue.pdf`, read Oct 27). Where they differ, both are
quoted. The team chose the **health variant** (`prototype-health/`, Lanford Health) as the product going forward.
Next checkpoint: a meeting with Prof. Hall on Oct 27 (today); the preliminary-results date is also Oct 27.

## What he said (verbatim where we have it)

Praised: the working demo, "showing money on the dashboard", the business questions ("Is it real?", "Is it normal?",
"What explains it?", "What is missing?", "What do I do?"), the editable action plan, the before-and-after visuals,
and the link from finding to plan to outcome. "The project is on track and potentially ahead of many other groups."

Asked for (minutes, section 2 and 7, all marked High):

| Area | His words (minutes) | Farid's notes |
|---|---|---|
| Dashboard readability | "The screen is too busy, with too much small text. Enlarge key information and reduce visual distractions." | "The Review page is too busy... Highlight [the money and the action report], grey out the secondary detail (the bottom-right panel especially)." |
| Financial impact | "Approximately $1,700 appeared too small to demonstrate commercial value. Use a larger, credible scenario with clear assumptions about hospital size and time period... at least a five-digit impact figure." | "Show the savings as full dollar figures ($228,000 to $589,000), not '$228K'." |
| Business questions | "Valuable but too small and easy to overlook. Make them prominent and consider using them to organize the workflow." | "Add UI structure around the investigation questions... so they read as a guided path, not a wall of text." |
| Action plan | "Turn the plan into a checklist with tasks, responsible people, and due dates." Output: a clear task, the person responsible, a due date, an editable checklist. "A PDF export would be sufficient for the demo." | "Each step with an owner, a date, and a status. Clear loop after the draft: review it > approve and get the one-page report; if not, edit and regenerate." |
| Outcome credibility | "Consider briefly showing a plan that required revision alongside one that worked. Clearly identify illustrative demo results." | "A plan that did NOT work at first, then the one that did." |
| Demo focus | "Focus on financial impact, investigation, the action plan, and results." Suggested flow: problem and money → investigate with the questions → create the plan and edit → execute (checklist, owners, deadlines) → review (before/after). 5 to 7 minutes expected, limit unconfirmed. | same |
| Pricing | "SaaS or usage-based... research comparable healthcare operations software... actual industry pricing... avoid unrealistically low commercial prices." | "He reads our model as pay-per-use. Research what operational software for hospitals charges (per bed, per user, per site, per month)." |
| AI / agentic | "Which part of this is agentic, and where does the LLM make a decision?" Roles agreed: Python computes and compares; the LLM drafts the report or plan from the findings; the nurse manager reviews, edits, approves. "Using a coding agent to build the software does not make the product itself agentic." Stronger agentic behaviour "not essential"; "optional improvement". | "He wants the prototype to show an agent taking an action... after approval, the system assigns the owner, schedules the review date, drafts the owner notification, and sets the KPI watch. Still with human approval." |

"The team does not have to remove features. At minimum, the important elements should stand out. A larger
redesign is optional."

## Where the $1,700 comes from, and why it cannot simply be made bigger

`GET /api/plans/plan-lanford-med-surg-night/result?as_of=2026-11-30` (keyless, Oct 27 data):

| KPI | DiD estimate per head-month | 95% CI | verdict | events avoided / quarter | unit cost | dollars / quarter |
|---|---|---|---|---|---|---|
| late doses | −1.056 | −1.674 to −0.437 | worked | 44.4 | $40 (client-entered) | $1,774 |
| absence days | −0.032 | −0.428 to 0.365 | inconclusive | 1.3 | $562.80 (assumption) | $756 |
| quits | −0.056 | −0.164 to 0.053 | inconclusive | 2.4 | $60,090 (NSI, sourced) | $141,332 |

Med-Surg Night has 14 people. Any per-unit figure from a 14-person team is small; the quits point estimate
annualised would be 9.6 quits a year on 14 people, which is noise and must never be shown as money. The Today
board's "excess, 3 mo" for the same team is $1,184 (late doses only; absences were not elevated in the draws, quits
not judgeable below 3 expected events). The Business case page already computes **$228,270 to $588,810 per
300-person hospital per year** (1 to 3 point turnover reduction at $60,090 per RN quit, plus one avoided injury).

So the five-digit figure comes from the product's own argument, stated as a scenario with its assumptions, not
from inflating a late dose. Three tiers, each labelled:

1. **Measured, this unit, per year:** the established DiD effects only (CI excludes zero), annualised (× 4), at the
   unit cost shown with its provenance. Today that is late doses: 44.4 × 4 × $40 ≈ $7,100 a year. Say "measured".
2. **Projected, this unit, if engagement recovers:** the app already measures the association between the item /
   grand mean and quits across the 24 teams (`app/impact.py` `association` / `quartile_link`, OLS with
   team-clustered SEs). Use that slope: if this unit's grand mean (or focus item) returns to its wave-1 level, the
   predicted change in its annual quit count × headcount × $60,090. Compute it; do not guess it. Label "projection ·
   association across teams, not cause · assumes the focus item recovers (a two-month pulse would confirm; not in
   the demo data)". If the number is not in a sane range (0.3 to 3 quits a year for 14 people), say so in the UI
   copy rather than hide it, and tell the integrator.
3. **At hospital scale:** the Business case figure for the hospital's size, in full dollars, linked to `/value`
   with the assumption sentence next to it: "300 nursing and support staff · turnover falls 1 to 3 points · NSI
   $60,090 per RN separation". This is the number that belongs in the deck.

Full dollars everywhere: `$228,270`, never `$228K`. `money()` in `web/src/lib/format.ts` loses the `K` path; keep
`M` only at $10,000,000 and above, if at all.

## The agentic answer (one paragraph the whole team can say)

"Friction Finder is an AI-assisted workflow, not an autonomous agent. Code detects (Poisson excess vs comparable
units), adjusts (tenure-mix shift-share), links (OLS, clustered by team) and proves (difference-in-differences with a
placebo). The language model makes two kinds of decisions, both bounded: in the investigation it chooses which of
eleven read-only checks to run next (function calling, budget of 6 tool calls, 8 requests, 60 seconds), and it
writes the brief, the plan draft and the owner notices from the numbers code handed it; a code check rejects any
sentence whose numbers, team or period are not in the cited evidence. It never writes SQL, never sets a verdict,
never sends anything. The nurse manager edits and approves; after approval the system assigns owners, schedules the
review and drafts the notices, and the manager sends them." Keep the voice rules in `docs/design/brand.md`: say
"AI-assisted", never "agent" or "agents", on screen.

## Streams, owners, files

Wave 1 runs in parallel in the same working tree. **Own your files; do not edit another stream's files.** Shared
files are split by region below. Re-read a shared file right before each edit, use small targeted edits, never
rewrite a shared file whole. No `git commit`; the integrator commits per wave.

### A. Money first: Review and Business case pages

Goal: on Review the manager sees the verdict and the money in the first viewport, in full dollars, with the
assumptions one line away; the evidence (interval, placebo, DiD table, other KPIs, limits) stays but reads as
secondary; illustrative results are labelled as such.

- `app/impact.py`: extend `did()` / a new `value_of_plan(plan, as_of, costs)` that returns the three tiers above
  with every input (events avoided, unit cost and its kind, slope, headcount, wave-1 level, hospital headcount) so
  the UI can print the assumptions. Reuse `association()` for the slope; reuse `value_case()` for tier 3. Add
  `illustrative: true` and the reason (synthetic follow-up months) to the result.
- `api/main.py`: only `/api/plans/{plan_id}/result` and `/api/value` (lines ~359 to 398). Add the value block to
  the result response.
- `web/src/lib/api.ts`: fields inside `interface Did` only (B owns the rest of the file).
- `web/src/lib/format.ts`: full dollars (owner A).
- `web/src/pages/Review.tsx`: redesign. First viewport: verdict badge + one sentence; a money block of the three
  tiers with large figures (28 to 36 px, `.tnum`), each with its one-line assumption and provenance chip
  ("Measured", "Projection", "Scenario"); the one-page report button (primary) and "Open the checklist" (→
  `/plans/{planId}`, B's page). Then the before/after chart (keep; it was praised). Then a muted "Evidence detail"
  section (collapsed `<details>` or a visually secondary band): DiD table, placebo, other KPIs, limits. A visible
  label near the headline: "Illustrative: Lanford Health is fictional; follow-up months are synthetic."
- `web/src/pages/Value.tsx`: lead with the two full-dollar figures in large type; the headcount slider stays; the
  pricing card becomes "Pricing (SaaS, per hospital per month) · benchmark pending" and reads a benchmark line from
  `data/docs/pricing_benchmarks.json` **if** stream P has written it by the time you finish (fields: vendor, model,
  price, unit, source_url, retrieved). Otherwise print "Benchmark research in progress (Oct 27)". No invented
  prices.
- Tests: `tests/test_impact.py` (value tiers: measured uses only CI-excludes-zero KPIs; projection in range or
  flagged; full inputs returned), `tests/test_api.py` (result carries the block).
- Keep every existing assertion in `web/scripts/demo_check.mjs` passing; if you rename a string it asserts,
  update that one assertion.

### B. The plan a manager can run: checklist, approve-or-edit loop, execution, report

Goal: after approval the plan is a checklist (task, owner, due date, status) the manager can tick and edit; the
loop after the draft is explicit (approve → checklist and report; or edit and regenerate); the one-page report
prints the checklist; and "what happened when you approved" is visible: owners assigned, review scheduled, KPI
watch set, owner notices drafted (never sent). This is the "Execute" step of his five-step flow.

- Data: `PlanAction` gains `id`, `status: 'todo' | 'done' | 'blocked'`, `done_at`; plans gain `execution`
  (`assigned`, `review_scheduled`, `kpi_watch`, `notices[]` with `to`, `subject`, `body`, `written_by:
  'model' | 'rules'`, `sent: false`). Old plans without these fields must still load (`approvals.jsonl`, the seeded
  plan, `data/generated/plans_seed.json` are read as they are; migrate on read).
- `api/main.py` (plans region, lines ~171 to 310, plus new routes): `GET /api/plans/{plan_id}`; `PATCH
  /api/plans/{plan_id}/actions/{action_id}` (status, text, owner, due; logged to `approvals.jsonl` as
  `target: "action"`); `POST /api/plans/{plan_id}/actions` (add a task); execution runs inside both approval paths
  (`create_plan` with status approved and `approve_plan`) under `_plan_lock`; idempotent. Owners default from the
  ownership directory for the role when the manager left one blank.
- `app/agent.py`: the notice drafting (model mode: short, from the plan fields only, checked the same way the brief
  is; rules mode: template) and `report_html` / `report_markdown` gain the checklist (checkbox glyphs, owner, due,
  status) and the execution record. The report is the PDF: print-ready HTML, `?download=true` already exists.
- `web/src/lib/api.ts` (everything except `interface Did`), `web/src/App.tsx` (route `plans/:planId`),
  `web/src/components/PlanEditor.tsx` (keep the props `seed`, `onSaved`, `title` unchanged; after "Approve plan"
  the caller navigates to `/plans/{id}`; add "Edit and regenerate": re-request the draft with the manager's edited
  obstacle as the hint, keeping their owner/measure edits), `web/src/pages/Plans.tsx` (a checklist-progress column
  "2 of 3 done", rows link to `/plans/{id}`), new `web/src/pages/PlanDetail.tsx` (the Execute page: checklist with
  inline edit and add; the "What happened when you approved" panel; notices with purple "written by AI, checked"
  provenance and a Copy button and the line "Nothing is sent by this prototype"; buttons "See if the plan worked" →
  `/review/{id}` and "One-page report"). Place `<Journey at="execute" planId=... />` once C has added the step
  (check `web/src/components/Journey.tsx` for `'execute'` before you import it; if it is not there yet at the end,
  leave the Journey out and tell the integrator).
- `web/src/pages/Investigate.tsx` is C's file. The one change you need there, `onSaved` navigating to
  `/plans/{p.id}`, is C's to make (listed under C); do not edit the file.
- Tests: `tests/test_plans.py`, `tests/test_api.py` (plan region): PATCH, add, idempotent execution, old plans load,
  report contains the checklist. `web/scripts/demo_check.mjs`: add the Execute step to the walk after approval.

### C. The questions as the path, and a screen a manager can read from the back of the room

Goal: the five business questions organise the Investigate screen visibly; key information is large; small text
is cut from the main path; the journey and the guided demo follow his five steps; nothing that passed a11y breaks.

- `web/src/components/Journey.tsx` **first, in your first ten minutes**: five steps `detect` (Today: "What is
  happening, and what is it costing?") → `explain` (Investigate: "Is it real, and what explains it?") → `act`
  (Plan: "One plan, one owner, one date") → `execute` (Checklist: "Who does what by when") → `prove` (Review:
  "Did the operating number move, and what is it worth?"). `execute` links to `/plans/{planId}` when a planId is
  known. Export the `Step` type with `'execute'`.
- `web/src/pages/Investigate.tsx` and `web/src/components/InvParts.tsx`: the five questions become the visible
  spine: a numbered question rail (sticky at ≥1280 px, horizontal chips below) and, per block, the question as a
  20 to 22 px heading, the one-sentence answer at 16 to 17 px with its evidence chip directly under it, and the
  tables/charts behind "Show the evidence" (open by default only for "What explains it?", which the demo points
  at). Change `onSaved` in the ActBlock caller to navigate to `/plans/${p.id}` (B's page) after approval. Do not
  change `PlanEditor`'s props.
- `web/src/pages/Today.tsx`: the headline team and its reason in larger type; the excess cost in full dollars
  (format.ts is A's; just call `money`); fewer competing panels above the fold; the Method stays one scroll down.
- `web/src/components/DemoGuide.tsx`: five steps matching the Journey, one sentence each, no numbers in the
  narration; the guided highlighting he suggested as optional: the current step's target block gets a
  `data-demo` attribute and a soft ring (`index.css`), nothing animated beyond the existing fade.
- `web/src/components/Shell.tsx`, `ui.tsx`, `index.css`, `tailwind.config.js`: type scale up one notch on the main
  path (body 14 → 15 px where it does not overflow at 390 px; big numbers 26 → 32 px; labels 12 → 13 px). Keep the
  colour meanings (`docs/design/brand.md`); update brand.md's Type section to what you ship.
- Verify: `node web/scripts/a11y.mjs` 0 violations; `demo_check` at 1440 and 390 px (no horizontal scroll).

### P. Pricing benchmarks (research, no code)

Goal: real prices for comparable software a hospital buys, so pricing stops being "10% of the low value case".
Deliverable: `My Notes/2026-10-27_Hospital_Ops_Software_Pricing_Benchmarks.md` (one folder up from
`prototype-health/`) and `prototype-health/data/docs/pricing_benchmarks.json` (array of `{vendor, product,
category, model, price, unit, basis, source_url, retrieved, confidence}`), with every price traceable to a URL and
"not public" written where it is not public. Candidates: Laudio (frontline leader platform for hospitals), Press
Ganey, Qualtrics XM for healthcare, Perceptyx, Culture Amp, Workday Peakon, UKG / Kronos for healthcare, Epic or
Oracle Health workforce modules, Gallup Access itself, Vocera / Stryker, QGenda, Hyland, plus any per-bed or
per-site SaaS benchmarks from HIMSS or KLAS reports. Then a one-page recommendation: a SaaS price per hospital per
month (and the per-bed and per-user equivalents for a 300-staff hospital), positioned against the benchmarks and
against the app's value range, and a short "why this is worth it" paragraph from the Chief Nursing Officer's point
of view using only numbers the app computes or the sources give. No invented figures.

### Wave 2 (after wave 1 is integrated and the gate passes)

Wave 1 landed on Oct 27 (streams A, B, C, P; gate run `docs/overnight/v0.10/_verify/wave1_*.txt`). What wave 1
produced, for reference: Review leads with the verdict and three value tiers ($7,104 measured; $31,093 to $75,511
projected; $228,270 to $588,810 at hospital scale); `/plans/{id}` is the checklist page with the approval record
and draft notices; Investigate has the numbered question rail; the Journey has five steps (Today, Investigate,
Plan, Checklist, Review); `data/docs/pricing_benchmarks.json` holds 33 sourced rows and the note is in
`My Notes/2026-10-27_Hospital_Ops_Software_Pricing_Benchmarks.md`.

Same rules: own your files, re-read shared files before each edit, no `git commit`, ports D 8033, E 8034, F 8035
(a11y servers 8043, 8044, 8045). Wave 2 file ownership:

| Stream | Owns |
|---|---|
| D | `data/generate_impact.py`, `data/generated/*` (regenerate), `DATA_SPEC.md`, `tests/test_impact_data.py`, `tests/test_data.py`, `web/src/pages/Review.tsx` (the revised-plan strip only), `web/src/pages/Plans.tsx` (the "revised" link only), `web/src/lib/store.tsx` `visiblePlans` if the new seeded plans need a rule, `web/scripts/demo_check.mjs` (its own new assertions) |
| E | `docs/demo/DEMO_SCRIPT.md`, `README.md`, `docs/HOW_IT_WORKS.md`, `docs/ARCHITECTURE.md`, `web/src/pages/Trust.tsx`, `../My Notes/Feedback_Log.md`, `../CLAUDE.md`, `../AGENTS.md`, `../My Notes/Cassin_Coffee_Prep.md` (Q&A bank), `docs/risk/TEVV_EVIDENCE.md` |
| F | `data/generate.py` (name dedupe only) and the name columns of `data/generated/teams.csv`, `ownership_directory.csv`, `data/docs/ownership_directory.md`; `web/src/lib/store.tsx` (PERSONA only), `web/src/pages/Today.tsx`, `web/src/pages/Investigate.tsx` (rail wrapping only), `web/src/pages/Value.tsx`, `web/src/components/ValueTiers.tsx`, `app/impact.py` (`value_of_plan` projection bounds only), `app/agent.py` (report tiers; blank-owner default), `api/main.py` (`_execute` owner default and `/api/assumptions` only), `tests/test_impact.py`, `tests/test_plans.py` |

- **D. The plan that needed revision.** Goal: a judge sees a plan that did not work next to the one that did
  ("Clearly identify illustrative demo results"). Design: pick a **Day** team at Westbrook or Pine Hollow that no
  planted pattern P1 to P13 uses (check `truth.json` and `DATA_SPEC.md`; avoid Westbrook Telemetry Day, the
  survey-only counter-example) and a KPI that is not late doses (overtime shifts fits the q02 story). Plant P14:
  the KPI elevated from February through August (multiplier about 1.8), plan 1 approved June 21 (wrong obstacle,
  e.g. "add a float RN to cover breaks", owner the unit's nurse manager, review Aug 31) reviews as **no effect or
  inconclusive** because the rate stays elevated; plan 2 approved Sept 1 on the obstacle the evidence pointed at
  (e.g. supply room restocking or the dispensing workflow for that unit), review Nov 30, and the multiplier returns
  to 1.0 from September, so plan 2 reviews as **improved**. Implementation: add the excess as an independent
  Poisson draw from a second generator (`np.random.default_rng(SEED + 1)`) on top of the existing draw
  (Poisson(a) + Poisson(b) = Poisson(a + b)), so every existing team-month stays byte-identical; verify with
  `git diff --stat data/generated` (only the chosen team's rows change). Seed both plans in `plans_seed.json` with
  `revised_from: <plan 1 id>` on plan 2 and `superseded_by` on plan 1; register P14 in `truth.json` and
  `DATA_SPEC.md`. UI: on plan 2's Review a strip above the money block, "Revised plan. The first plan (June 21 to
  Aug 31, add a float RN) showed no effect; this one changed the obstacle" with a link to plan 1's Review; on the
  Plans board a "Revised" badge and the link both ways. Check the Med-Surg Night numbers are unchanged (81 vs 51,
  the DiD −1.056, CI −1.674 to −0.437) and that the board at Sept 15 for Lanford still flags one team; the
  HR-leader all-sites view may show the new team, which is fine. The whole gate must stay green; if the gold or
  adversarial pack breaks, change the team or KPI rather than the pack.
- **E. Words.** `docs/demo/DEMO_SCRIPT.md` rewritten to his five steps in 5 to 7 minutes (problem and money →
  investigate with the questions → plan and edit → checklist → review and worth), one sentence per click, the
  fallbacks table kept, and a Q&A column that points at the new screens. The agentic paragraph from this spec on
  the Trust page (Architecture tab, first paragraph, plus a three-row table: code decides / the model decides /
  the person decides) and in `README.md`; a README "v0.10 (Oct 27, 2026)" section that lists what changed and why,
  with the professor's words quoted; the Oct 27 entry in `../My Notes/Feedback_Log.md` in the log's existing
  format ("What he said" / "What changes because of it" / "Actions"), each minute item marked done, in progress or
  open, dated; `../CLAUDE.md` and `../AGENTS.md` "Where the project stands" paragraph updated to v0.10 (keep the two
  files identical in that section); five Q&A lines in `../My Notes/Cassin_Coffee_Prep.md` for the money tiers, the
  projection's assumption, the checklist, the notices never being sent, and the pricing benchmark; one TEVV line in
  `docs/risk/TEVV_EVIDENCE.md` for the notice check (numbers, owner, length, causal language). No numbers from
  memory: take every figure from the API or the result files.
- **F. Polish the wave-1 screens.** (1) Names: the synthetic directory has Priya Singh as both the Lanford
  Pharmacy Operations Manager and the Lanford Med-Surg Day manager, Priya Quinn as both the Lanford Med-Surg
  Night manager and Westbrook's pharmacy manager, Ravi Singh twice at Pine Hollow, and the UI persona is "Priya
  Singh, Nurse Manager", so the demo shows Priya Singh assigning a task to Priya Singh and signing as Priya
  Quinn. Keep Priya Singh as the Lanford pharmacy owner (the eval results name her); dedupe every other collision
  with a fixed rename map applied in `data/generate.py` after the draws (never change the RNG calls), regenerate,
  confirm `git diff` shows only name strings; set `PERSONA.manager` in `store.tsx` to team 4's manager name and
  initials. (2) Blank task owner: default to the approving nurse manager (team 4's manager), not the plan owner;
  the plan owner is used only when the task text names their process. (3) Investigate rail: the fifth chip is cut
  off at 1440 px; let the chips wrap or shorten the rail labels ("Is it real?", "Is this normal?", "What explains
  it?", "What is missing?", "What do I do?"). (4) Today, step 1 of his flow ("what is happening, and what is it
  costing?"): add one tile from `value_case` for the current site's hospital, "What turnover costs this hospital:
  $3,172,752 a year (53 quits × $60,090)", sourced, so the first screen carries a hospital-scale figure next to
  the unit's $1,184; full dollars. (5) Projection tier: low bound = the unit returns to the median (half the
  Gallup gap), high bound = top quartile (the full gap); label both; update the test. (6) One-page report
  (`report_html` / `report_markdown`): print the three tiers with their one-line assumptions under the verdict.
  (7) `/api/assumptions`: add the Gallup quartile gap, the 300-staff scenario, and the pricing benchmark note.
  (8) Pricing card on Value: the working figure becomes the researched hypothesis, $4,000 per hospital per month
  for up to 300 nursing staff ("assumption, Oct 27 research; 21% of the low case, 8% of the high case; the
  hospital keeps 79 to 92%"), with the per-staff ($160 a year) and per-unit equivalents, and the benchmark list
  compacted to a six-row table (vendor, model, price as stated, basis) with "27 more in the research note". Keep
  every string `demo_check.mjs` asserts.

## Rules that do not move

- GW-provided OpenAI API only, via `.env`; keyless rules mode must keep working and say so.
- Every number on screen comes from the API; narration has no numbers; nothing is sent to anyone.
- Say "AI-assisted workflow"; never "agent" or "agents" on screen or in docs. Say "association, not cause" and
  "directional, not causal". Label follow-up months "synthetic" and demo results "illustrative".
- Minimum n is 4; the model never queries respondent rows; no patient-level data.
- Verification before "done": `cd web && npx tsc -b --noEmit` while working; at the end `npm run build`,
  `npm run lint`, `env GW_AZURE_OPENAI_KEY= OPENAI_API_KEY= .venv/bin/python -m pytest tests -q`, and
  `CHECK_PORT=<your port> ./scripts/demo_check.sh` (A: 8030, B: 8031, C: 8032, D: 8033). Concurrent builds share
  `web/dist`; if demo_check fails only on missing assets or 404s, wait a minute and rerun once. Report what you ran
  and what it printed, including failures.
