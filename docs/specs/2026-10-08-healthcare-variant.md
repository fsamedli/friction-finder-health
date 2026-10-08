# Friction Finder, healthcare variant (v0.9-health). Shared spec for the three build agents

Written Oct 8, 2026 by Claude Code for Farid. This folder (`prototype-health/`) is a full copy of
`prototype/` at v0.8 (commit 3e95fe4), branch `v0.9-health`. Goal: the same product, same
architecture, same planted-pattern design, same evals, on a **fictional regional hospital system**
instead of a fictional logistics company. Why: Gallup's publicized client base is heavy on hospital
systems (12 of 78 in the 2026 award list) and thin on logistics (0 of 78); the Gallup judge's own
example of linking engagement to operations was "patient safety for a hospital"; one final judge is
from HR. Research: `My Notes/2026-10-08_Gallup_Client_Base_Research.md`.

Nothing structural changes. Three sites, eight teams per site in the same order with the same shifts
and headcounts, two survey waves on the same dates, the same twelve items, the same seeds, the same
thirteen planted patterns P1 to P13, the same minimum n of 4, the same screens, the same tools, the
same eval packs. Only the industry story changes: names, the operating metrics and their sources, the
documents, the comments, the unit costs, the segment facts, and every piece of copy.

## Hard rules (from the course; do not bend)

- Synthetic data only. **No patient-level data of any kind, ever.** Every operating metric is a
  count at unit, shift, or site level. No patient identifiers, no diagnoses, no HCAHPS responses.
- Label the company fictional everywhere the old copy labelled Northline fictional.
- **No invented numbers.** Every unit cost and segment statistic is either (a) sourced, with the
  publisher, report name, year and figure in the `source` string, verified by a web search during
  this build, or (b) `kind: "assumption"` with the formula and its inputs in the string. If you
  cannot verify a figure, do not guess: use the assumption path or write "needs a source" in the
  note. Never fabricate a citation.
- GW Azure OpenAI only (`app/config.py` unchanged). No Anthropic or other APIs.
- Keep `.env` out of git. Never print the key.

## The fictional company

- **Lanford Health (fictional)**, a regional hospital system. Replace every "Northline Logistics
  (fictional)" with "Lanford Health (fictional)".
- Sites (`sites.csv`, same ids): 1 **Lanford** (Lanford Medical Center), 2 **Westbrook** (Westbrook
  Community Hospital), 3 **Pine Hollow** (Pine Hollow Hospital). `site_name` holds the short form.
- Shifts: **Day** (07:00 to 19:00) and **Night** (19:00 to 07:00). Keep the strings "Day" and "Night".
- Teams (`TEAM_TEMPLATE`, same order, shift, headcount; team ids therefore unchanged, 1 to 24):

| old name | new name | shift | headcount | role in the story |
|---|---|---|---|---|
| Day A | Med-Surg Day | Day | 12 | |
| Day B | Telemetry Day | Day | 12 | site 2 copy is P6 (new-graduate cohort) |
| Day C | ED Day | Day | 8 | site 3 copy is P9 (blip) |
| Night A | Med-Surg Night | Night | 14 | site 1 copy is P1/P2/P3/P8/P11 (the planted team, team_id 4); site 2 copy is P10 |
| Night B | ICU Night | Night | 7 | |
| Yard Day | Resp Therapy Day | Day | 5 | |
| Dispatch Day | Pharmacy Day | Day | 3 | suppressed (n < 4) |
| Maintenance Night | EVS Night | Night | 2 | suppressed (n < 4) |

- People: **user** = unit nurse manager (and charge nurse). **Buyer** = Chief Nursing Officer and
  HR / people analytics. **Data owners** = HR (survey export), pharmacy and nursing informatics
  (eMAR / dispensing-cabinet logs), timekeeping (scheduling and overtime), HRIS (separations).
  Replace "site manager / shift manager" with "nurse manager / charge nurse"; "Site Operations
  Manager" with "Nurse Manager"; "Director of Operations" with "Chief Nursing Officer".

## Operating metrics (keys are renamed; everything that reads them changes)

| old key | new key | label on screen | what it counts | source string (`metrics.py`) |
|---|---|---|---|---|
| absence_days | absence_days | Unplanned absence days (sick calls) | unplanned absence days | timekeeping and attendance |
| late_departures | **late_doses** | Late medication doses | scheduled doses given more than 60 minutes after the scheduled time | eMAR / barcode medication administration export |
| quits | quits | Voluntary separations | RN and staff voluntary separations | HRIS (voluntary separations) |
| injuries | injuries | Staff injuries (days-away) | staff injury cases with days away (patient handling, sharps) | employee health / safety log |
| rework | **overtime_shifts** | Unplanned overtime shifts | shifts extended past schedule or extra shifts worked beyond FTE | timekeeping (overtime) |
| late_rate | late_rate | Share of doses given late | late_doses / scheduled_doses by hour band and period | eMAR export (kept per site and shift, not per team) |

- `KPIS = ["absence_days", "late_doses", "quits", "injuries", "overtime_shifts"]`;
  web `KPI_ORDER = ['late_doses', 'absence_days', 'quits', 'injuries', 'overtime_shifts']`.
- `KPI_COST_KEY`: absence_days→absence_day, late_doses→late_dose, quits→quit, injuries→injury,
  overtime_shifts→**overtime_shift** (overtime now has a cost; rework had none).
- `ops_daily.csv` columns: `date, site_id, shift, hour_band, scheduled_doses, late_doses, missed_doses`
  (old: departures, late_departures, rework_count). Hour bands unchanged; the 06-07 band is the
  06:00 medication pass before the 07:00 shift change. Scale `scheduled_doses` to about 8x the old
  Poisson means (144 and 192) so counts look like a hospital; the late rate stays 8% flat, 18% where
  planted. `missed_doses` ~ Poisson(1.5) as rework_count was.
- `team_ops_monthly.csv` columns: `month, team_id, site_id, shift, headcount, absence_days, late_doses, quits, overtime_shifts, injuries`.
- `UPLOAD_COLUMNS = ["month", "team_id", "absence_days", "late_doses", "quits", "injuries", "overtime_shifts"]`.
- Views: `v_ops_month(site_id, site_name, shift, hour_band, month, scheduled_doses, late_doses, late_rate, missed_doses)`,
  `v_ops_hour(site_id, site_name, shift, hour_band, period, scheduled_doses, late_doses, late_rate)`,
  `v_team_ops_month(month, team_id, team_name, shift, site_id, site_name, headcount, late_doses, absence_days, quits, injuries, overtime_shifts)`.
- `staffing.csv` unchanged in shape: scheduled vs actual **RN** headcount per site, shift, month.
- Generator constants (`generate_impact.py`): keep BASE and ELASTICITY values under the new keys
  (late_doses takes late_departures' values, overtime_shifts takes rework's). Keep SEED values.
- `METRIC_WORDS` (the manager's vocabulary): late_rate: "late rate", "share of doses", "percent of
  doses", "% of doses", "hour band(s)", "med pass"; late_doses: "late dose(s)", "late med(s)", "late
  medication(s)", "late meds", "medication delays", "med pass late", "late"; absence_days: as before
  plus "sick calls", "call-ins"; quits: as before plus "RN turnover", "nurses leaving"; injuries: as
  before plus "needlestick", "sharps", "patient handling"; overtime_shifts: "overtime", "OT", "extra
  shifts", "stayed late", "held over".

## The planted story (same ids, new content)

- **P1, P2** Lanford Med-Surg Night (team 4): Q02 (materials and equipment) and Q07 (opinions
  count) fall in wave 2. Unchanged mechanics.
- **P3** Lanford Night, 06-07 band: late doses rise from ~8% to ~18% from June 1, 2026.
- **P4** Lanford Night RN staffing at 80% of scheduled in March 2026, 90% in April (the competing
  explanation).
- **P8** four wave-2 comments from team 4 about the **automated dispensing cabinet (ADC)**: since
  spring pharmacy restocks the unit cabinet at 07:00, after the 06:00 pass; nurses find empty bins,
  wait for pharmacy or borrow from other units; the 06:00 pass runs late; raised in three huddles
  with no change (that is the Q07 link). Theme key: `restock` (was `handoff`).
- **P11** team 4: late doses x2.0, absences x1.35, quits x1.6 in Jun to Sep 2026; recovery Oct to
  Nov after the plan (Sept 21, review Nov 30). Comparison teams: Night teams at other sites with
  n >= 4 (unchanged rule).
- **P6** Westbrook Telemetry Day (team 10): a **new-graduate nurse residency cohort** (under_1)
  answered wave 1 and not wave 2; apparent decline is a response-mix change.
- **P9** Pine Hollow ED Day (team 19): Q04 falls, no operating signal, no comments: "insufficient".
- **P10** Westbrook Med-Surg Night (team 12): one ~150-word comment about **IV pumps**: half out
  for service since spring, biomed tickets sit for weeks, borrowing pumps from other units, raised in
  huddles. No planted drop. Must be labelled single source.
- **P5, P7, P12, P13** unchanged in nature (honeymoon, suppression, elasticities, injuries
  independent of engagement).
- Eval regex for the planted obstacle: `restock|dispensing cabinet|cabinet|pharmacy` (was
  `handoff|hand-off|hand off|shift change`). Owner regex: `Pharmacy Operations Manager`.

## Documents (`data/docs/`, written by `generate.py`)

1. `medication_cabinet_restock_procedure.md` (SOP-PHARM-021). Purpose: unit cabinets restocked so
   stock is on hand for every scheduled pass. Steps: pharmacy technicians restock each unit cabinet
   **by 05:00 daily**; the restock report lists items below par; the charge nurse reviews it at the
   start of the pass; stock-outs during a pass are logged and pharmacy delivers within 30 minutes.
   Ownership: the **Pharmacy Operations Manager** at each site owns the schedule; the Nurse Manager
   owns the stock-out log. Reviewed annually, last review January 2026. (The comments describe a
   drift away from this SOP: restock moved to 07:00 in spring.)
2. `nurse_staffing_policy.md` (POL-NURS-006). Schedules published at least 4 weeks ahead; minimum
   RN staffing per shift set by the Nurse Manager and reviewed monthly against scheduled versus
   actual; below 85% in a month, the Chief Nursing Officer is notified and a recovery plan is
   required within two weeks; float and agency rules; shift swaps approved by the charge nurse.
   Owner: Chief Nursing Officer.
3. `engagement_action_planning_guide.md`: same text, roles renamed (Nurse Manager, Director of
   Nursing instead of Site Operations Manager).
4. `ownership_directory.md` and `ownership_directory.csv`, per site: "Medication cabinet restocking
   schedule" → Pharmacy Operations Manager; "Unit staffing and bedside shift report" → Nurse
   Manager, Med-Surg; "IV pump and equipment maintenance" → Clinical Engineering Lead. ALL:
   "Engagement survey and action planning" → HR Business Partner, Dana Whitfield; "Nurse staffing
   and float policy" → Chief Nursing Officer, Marcus Okafor. Keep the name banks; site 1's
   Pharmacy Operations Manager is the owner the seeded plan names.
5. `gallup_item_discussion_questions.md`: unchanged.

Generic comment bank: rewrite every line for nursing units (workload, recognition, tools: pumps,
computers on wheels, supplies; communication: huddles, policy changes; schedule: self-scheduling,
swaps, holidays; development: charge nurse path, certifications, preceptor training).

## Seeded plan (`plans_seed.json`)

id `plan-lanford-med-surg-night`, team 4, item q02, kpi `late_doses`, obstacle "Medication cabinet
restocked after the 06:00 pass: night nurses start the pass with empty bins", focus q02. Actions:
(1) Pharmacy restores the 05:00 cabinet restock for the Med-Surg unit, owner: site 1 Pharmacy
Operations Manager, due 2026-09-28; (2) Charge nurse logs stock-outs at 02:00 and sends the list to
pharmacy, owner: Med-Surg Night charge nurse, due 2026-10-05; (3) Ten-minute team check-in on Q02
every other Monday, owner: Med-Surg Night nurse manager, due 2026-10-12. Start 2026-09-21, review
2026-11-30, status approved, note "Seeded for the demo: approved by the nurse manager after wave 2."

## Unit costs (`generate_impact.py: unit_costs()`), verify each with a web search

- `quit`: RN turnover. Preferred: the latest NSI Nursing Solutions "National Health Care Retention
  & RN Staffing Report" average cost of turnover for a staff RN (verify year and figure). Fallback:
  the current method, 20% of annual pay (Center for American Progress, Boushey & Glynn 2012) with
  pay = BLS OES 29-1141 registered nurses mean hourly wage x 2,080 (verify the wage and its year).
- `injury`: keep the National Safety Council figure and source as is.
- `absence_day`: assumption, one 12-hour shift at the BLS RN mean hourly wage (verify the wage).
- `late_dose`: `kind: "client_entered"`, "Client-entered figure: Lanford Health (fictional) pharmacy
  callback and nurse time per late dose. Not a market statistic; no credible public source
  exists." Pick a modest value (tens of dollars) and say so in the note.
- `overtime_shift`: assumption, the premium portion of one extended shift: 4 hours x 0.5 x BLS RN
  mean hourly wage (state the formula; "replace with the client's overtime report").

## Segment facts (`impact.py`: TURNOVER_RATE, INJURY_RATE, SEGMENT), verify with a web search

- Turnover: NSI's latest national RN turnover rate, or BLS JOLTS health care and social assistance
  quits rate x 12. Name the source, year and figure.
- Injury: BLS SOII, hospitals (NAICS 622), days-away cases per 100 FTE, latest year.
- Segment size: BLS QCEW or CES, hospitals (NAICS 622): establishments and employees, latest year.
- If a figure cannot be verified, keep the field, set the value to the best verified alternative,
  and say in the source string what it is a proxy for. Do not leave logistics figures in place.

## Ports and names

- `run_demo.sh`: default port **8001** (so the logistics demo can run on 8000 at the same time).
- `scripts/demo_check.sh`: port 8020. `scripts/gate.sh`: a11y port 8021, output dir
  `docs/overnight/v0.9-health/_verify`.
- Product name stays **Friction Finder**. Subtitle, where one exists: "for nursing units".
- Demo clock and dates unchanged (wave 2 closes Sept 10, 2026; as-of Sept 15; review Nov 30).

## Ownership of files (one agent per file; do not edit another agent's files)

- **Agent A, data and metrics:** `data/generate.py`, `data/generate_impact.py`, `data/docs/*`,
  `app/db.py`, `app/metrics.py`, `app/impact.py`, `app/relations.py`, `DATA_SPEC.md` (generated),
  `tests/test_data.py`, `tests/test_impact_data.py`, `tests/test_impact.py`, `tests/test_metrics.py`.
- **Agent B, model layer, API, evals:** `app/agent.py`, `app/tools.py`, `app/investigate.py`,
  `app/retrieval.py`, `app/probe.py`, `app/ui.py`, `app/cli.py`, `api/*`, `evals/*` (cases, runners,
  from_feedback), `scripts/prepare_answers.py`, `scripts/prepare_investigations.py`,
  `data/prepared/*`, `tests/test_agent.py`, `tests/test_api.py`, `tests/test_plans.py`,
  `tests/test_sql_guard.py`, `tests/test_study.py`.
- **Agent C, web and docs:** `web/**` (src, index.html, scripts), `README.md`, `SPEC.md`,
  `run_demo.sh`, `scripts/demo_check.sh`, `scripts/gate.sh`, `docs/**` except this spec and
  `docs/overnight/`.

## Definition of done (the integrator runs this after all three finish)

1. `grep -rniE "northline|logistic|late.departure|late_departure|truck|trailer|forklift|dispatch|warehouse|rework|yard|dock|handoff|hand-off|richmond|norfolk|roanoke|night a|day b|day c|night b|shipping|delivery|deliveries|wms|site operations manager|director of operations" --include=*.py --include=*.ts --include=*.tsx --include=*.md --include=*.json --include=*.sh --include=*.html . | grep -v node_modules | grep -v "\.venv" | grep -v "docs/overnight/" | grep -v "evals/results" | grep -v "docs/specs/2026-10-08-healthcare-variant.md"`
   returns nothing (old eval result files and the v0.8 overnight folder are history and may keep the old words).
2. `./scripts/gate.sh docs/overnight/v0.9-health/_verify gate` exits 0: build, lint, pytest, gold,
   adversarial, investigate (rules mode), demo_check, a11y.
3. `data/generated/truth.json` says "Lanford Health (fictional)" and every pattern P1 to P13 is present.
4. The seeded plan, the Today screen, and the Business case page show hospital metrics and sourced costs.
