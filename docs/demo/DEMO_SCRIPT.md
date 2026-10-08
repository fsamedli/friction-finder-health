# Friction Finder demo script (v0.9-health, Lanford Health)

About **5 minutes of demo inside a 15 to 20 minute talk of about 10 slides** (class, Oct 8: leave time for
questions). Timings are **targets for rehearsal**, not measurements, except where a measured time is given.
The guided demo (top bar → **Start demo**: Today → Investigate → Decide → Review) follows the same path and makes
no model call. The company (Lanford Health), its three hospitals and all data are fictional and synthetic; the
operating records are unit-level counts, never patient data.

## Before you go on stage (5 minutes before)
1. `./scripts/demo_check.sh` must end with `… passed, 0 failed` (keyless, 1440 and 390 px, private port 8020). If
   not, use the fallback laptop.
2. `cd web && npm run build` if you pulled new code (`run_demo.sh` only builds when `web/dist` is missing), then
   `./run_demo.sh` (port 8001), user menu → **Reset demo**, demo clock reads **Sept 15**.
3. Browser zoom **100%** (⌘0). Close other tabs. Notifications off.
4. Use the scripted questions in the order below. Once prepared answers have been regenerated for this variant
   (`scripts/prepare_investigations.py`, `scripts/prepare_answers.py`) they are served labelled "Prepared answer".
   Anything else runs live: with the GW key the model took about 18 to 58 s per question on the v0.8 data (ten
   live turns on Oct 8); without a key, rules mode answers in under a second and says "rules mode, no model".

## The click path

| # | Target | Click | Say (one sentence) | If it breaks | Likely judge question → where the answer is |
|---|---|---|---|---|---|
| 1 | 0:00–0:40 | **Today** (home) | "The nurse manager opens this on Monday: one unit team needs attention, why it matters in operating terms (late doses against comparable units), and one next step." | Blank page → reload; still blank → fallback laptop | "How do you know it isn't noise?" → **Method** below the fold (Poisson test vs comparable teams, "too rare to judge") |
| 2 | 0:40–1:20 | Rust **Review Med-Surg Night and decide** → Investigate Med-Surg Night | "The team screen is organised by the manager's questions: is it real, is it normal for teams like ours, what explains it, what is missing, what do I do." | A block shows "unavailable" → the API is down: restart `./run_demo.sh` | "Isn't that just who responded?" → **Is it real?** block (adjusted for tenure mix); the Westbrook Telemetry Day team is the planted counter-example |
| 3 | 1:20–2:20 | Panel chip **Why flagged?** | "The AI-assisted investigation chooses which read-only checks to run; code computes every number; the answer says how strong the evidence is: the comments point at the dispensing-cabinet restock moving to 07:00, after the 06:00 medication pass, and the late doses sit in that hour band." Point at the evidence state and one citation. | The chip asks the saved question, so it shows the labelled prepared answer instantly once regenerated; a typed variant runs live (about 20–40 s) → keep talking over the live trace | "Can the AI make numbers up?" → citations open the SQL and rows; Trust › Architecture: the model never writes SQL or numbers; a code check rejects any number, team or period not in the cited evidence |
| 4 | 2:20–3:10 | Type **Could staffing explain this?** | "The manager challenges the explanation. RN staffing was short only in March; the rise is from June, so the evidence does not support it." Point at the competing explanation and its own state. | Answer asks "which team?" → the context chip lost the team: pick Med-Surg Night in the Team chip | "What if the data can't answer?" → evidence states *insufficient* / *unavailable*, and the next step becomes collecting a record, with an owner |
| 5 | 3:10–3:50 | Rust **Draft a plan** → edit → rust **Approve plan** | "The plan has an owner from the directory (the Pharmacy Operations Manager), the operating measure, a review date and a success criterion. The nurse manager edits and approves; nothing is sent anywhere." | Approve fails → demo clock → Nov 30 → Review shows the seeded Med-Surg Night plan (it starts Sept 21) | "Where's the human?" → rust = a person decides (sidebar legend); approvals are logged with edits and time |
| 6 | 3:50–4:40 | **See if the plan worked** → **Fast-forward to the review date** | "At the review date Med-Surg Night is compared with night units at the other hospitals that didn't act. Improved, with an interval and a placebo check. Directional, not causal; the follow-up months are synthetic." | Fast-forward stuck → demo clock (top bar) → Nov 30 → Review | "Is that causal?" → no, and it says so on screen; limits list the two-month pulse as an assumption |
| 7 | 4:40–5:00 | **Business case** (optional) | "Every unit cost (late dose, overtime shift, absence day, quit, injury) shows its source, its assumption formula, or that the hospital entered it; pricing is a labelled hypothesis." | — | "Where do these numbers come from?" → each cost shows its source, "Assumption" or "Client-entered (fictional)" |

**Q&A only, one click away:**
- **Trust & method › Quality:** the gold and adversarial packs, first run beside now, declines, numbers checked,
  feedback counts from zero, and "approvals are never evidence that an answer was correct". The investigation
  pack's results are in `evals/investigate/results/`; the Quality tab does not show them yet.
- **Trust & method › Architecture:** the loop, the tool registry, the budgets, where the model is used.
- **Trust & method › Assumptions:** includes the external benchmark (assumed source, unavailable) and the
  two-month follow-up pulse (assumed for a pilot, not in the demo data).
- **Data sources:** every source is a synthetic CSV (survey export, eMAR export, timekeeping, HRIS, employee
  health log, procedures); in a pilot the hospital uploads its own team-month file. No patient-level data.
- **/ask** (top bar **Ask**): the panel full width; `/ask?view=brief` keeps the v0.7 one-page brief.

## What breaks first, and the fallback

| Step | Mode | Latency | What breaks first | Fallback |
|---|---|---|---|---|
| Today, Investigate blocks, Plans, Review | code only | under 1 s (no model call) | the server dies | `./run_demo.sh` in a second terminal (seconds once `web/dist` exists) |
| Panel question (key present) | model chooses checks; code computes; model words the answer, then code checks it | on the v0.8 data: 17.6, 22.5, 27.8, 57.8 s in four test turns and 19.0 to 41.7 s in six generation turns on Oct 8 (in the 57.8 s turn under 5 s of the 60 s budget remained, so the wording step was skipped and the templated text shown; one GW 429 rate-limit error during generation). Not yet measured on the hospital data | **model latency or GW Azure down** | If the model is unreachable the app falls back to the fixed plan by itself and says so. For a predictable demo, run keyless: `env GW_AZURE_OPENAI_KEY= OPENAI_API_KEY= ./run_demo.sh` (rules mode, under a second, labelled "rules mode, no model"); say so if asked |
| Panel, prepared answer | model run saved earlier, labelled | instant | asking a question that is not one of the saved turns (it runs live); **no prepared answers exist for this variant until `scripts/prepare_investigations.py` is re-run** | The six scripted turns, asked in this order with the team context Med-Surg Night on Sept 15: "Why is Med-Surg Night flagged?" → "Could staffing explain this?"; "Compare it with the other night shifts" → "When did it start?"; "Is this normal for teams like ours?" → "What is missing?". Shown as "Prepared answer · generated … · Run live" once generated. Use the prepared path on stage; **Run live** only in Q&A |
| Approve plan | code | under 1 s | a double click | blocked: one `request_id` per draft; a repeat returns the saved plan with an explanation |

Other fallbacks:

| Problem | Do this |
|---|---|
| The laptop dies | Fallback laptop, cloned and checked the same morning with `scripts/demo_check.sh`. Last resort: the before/after screenshot page from the v0.8 run (`docs/overnight/before_after.html`; it shows the v0.8 data). Judges penalise screenshots; only if everything else fails |
| A plan was approved in rehearsal | User menu → **Reset demo** |
| Wrong date showing | Top bar → demo clock → Sept 15 |

## Speaker hand-overs (fill in names)
| Step | Speaker | Backup for Q&A |
|---|---|---|
| 1–2 | | |
| 3–4 | | |
| 5–6 | | |
| 7 + Q&A | | |
