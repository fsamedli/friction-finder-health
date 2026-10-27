# How Friction Finder works (one page, for everyone on the team)

**What it is:** an AI-assisted workflow that helps a nurse manager at a hospital system connect engagement
survey results to the hospital's own operating numbers (late medication doses, unplanned absence days, voluntary
separations, staff injuries, unplanned overtime shifts), and check whether a fix moved the operating number.
Inside it is an **AI-assisted investigation**: the manager asks or challenges ("Could staffing explain this?"), the
model chooses which of a fixed set of read-only checks to run next under a budget, code computes every number, and
a person approves every action.

**Who it's for:** the user is the unit nurse manager (and the charge nurse). The buyer is the Chief Nursing
Officer and HR / people analytics. The data comes from the hospital: the survey export (HR), the eMAR export
(pharmacy and nursing informatics), timekeeping (scheduling and overtime), HRIS (separations) and the employee
health log (staff injuries). **No patient-level data, by design:** every operating record is a count at unit, shift
or site level, so nothing in the product identifies a patient.
Gallup Access shows *what* moved in the survey and already offers AI next steps and an AI action-planning
prompt (public Help Center, read Oct 8; `docs/research/2026-10-08_Gallup_Access_Overlap.md`). What Access does
not document is the link to the client's own operating data, or a check of an operating number at a review
date. That link is this product. It is built to sit next to Access, not to repeat it.

**The company is fictional.** Lanford Health (fictional) has three hospitals (Lanford, Westbrook, Pine Hollow)
and eight unit teams per hospital; all data is synthetic (`docs/specs/2026-10-08-healthcare-variant.md`).

## The journey (the screens, in order)
1. **Today.** One unit team that needs attention, why it matters (its operating number against comparable teams,
   and the survey item that fell), and one rust button: "Review Med-Surg Night and decide". Method details are one
   click down.
2. **Investigate.** The team screen, organised by the manager's questions: Is it real? Is this normal for teams
   like ours? What explains it? What is missing? What do I do? Each block leads with one sentence and one
   evidence state. The investigation panel lives on this screen.
3. **Plan.** On Investigate under "What do I do?": one drafted plan with an owner, an operational measure, a
   review date two full months out, a success criterion and three tasks, each with a responsible person and a
   due date. The manager edits, or presses "Edit and regenerate" with a different obstacle, then approves.
4. **Checklist** (`/plans/{id}`, added Oct 27). Approval turns the plan into a checklist the manager runs: tick a
   task, edit any cell, add a task; every change is saved with the time. Next to it, what code did the moment the
   plan was approved: owners assigned, the review scheduled in the Due reviews queue, a KPI watch set, and one
   notice drafted per owner. **Nothing is sent**: the manager reads, copies and sends. The one-page report prints
   the checklist and the approval record (print to PDF). The **Action plans** board shows every plan's state
   (draft, approved, in review, reviewed) and checklist progress, with queues for due reviews, missing follow-ups
   and inconclusive outcomes.
5. **Review.** At the review date: improved, deteriorated or inconclusive, with the interval, a placebo check and
   the limits, and (Oct 27) **what it is worth** in three labelled tiers: measured (the established effect,
   annualised, at the unit cost shown), projected (fewer separations if the unit's engagement recovers, from
   Gallup's quartile gap and NSI's cost per separation), and at hospital scale (the Business case scenario).
   **Directional, not causal**; in the demo the follow-up months are **synthetic follow-up data** and the screen
   says "Illustrative".

## The planted story (so the demo has an answer)
Lanford Med-Surg Night (team 4): Q02 (materials and equipment) and Q07 (opinions count) fall in wave 2; late
doses in the 06:00 to 07:00 medication pass rise from June; four wave-2 comments say pharmacy restocks the
automated dispensing cabinet at 07:00, after the 06:00 pass, so nurses start the pass with empty bins. The SOP says
restock by 05:00; the owner is the Pharmacy Operations Manager. A March RN staffing shortage is the competing
explanation (it ends before the rise). Westbrook Telemetry Day is a response-mix artifact (a new-graduate cohort
answered wave 1 only); Pine Hollow ED Day is a blip ("insufficient"); Westbrook Med-Surg Night has one long comment
about IV pumps ("single source").

## The investigation panel
- Questions it answers (chips, or typed): why is this team flagged; could staffing / who responded / a site-wide
  change / one hour band explain it; compare with the other night shifts; is this normal for teams like ours;
  when did it start; how widespread is it; what is missing; where does this number come from; has this
  happened elsewhere; draft a plan; did it work. "Prepare the team conversation" is **not built** (Gallup's own
  guide covers it; the research note labels it "drop").
- Every answer has a conclusion, an **evidence state** (supported, mixed, insufficient, unavailable; no
  confidence percentages), a competing explanation with its own state, cited evidence that opens the passage or
  the SQL and rows, and a next step. When evidence is weak, the next step is to collect something, with an owner.
- It keeps context across follow-ups ("it", "the other night shifts", "No, I meant ICU Night").
- The trace shows each step in plain words, whether code or the AI model did it, and the real seconds.

## Where AI is used
- **Ask** (the one-page brief): reading the question, writing the brief.
- **Investigation:** choosing the next check (up to 6 per question), reading the question only when the rules
  reader matches nothing, and wording the conclusion and competing explanation. A code check rejects any wording
  with a number, team or period that is not in the evidence it cites; then the template is shown, labelled.
- **Plan execution** (Oct 27): "Edit and regenerate" asks the model for a new action list from the manager's
  edited obstacle (rules mode uses a theme-matched action bank); the owner notices are templated at approval and,
  with a key, rewritten by the model in the background from the plan's facts only. A check rejects any notice
  whose owners do not match the plan, that contains a number not in the plan, that is over 140 words, or that
  claims the survey caused anything; two failures and the templated notices stay, labelled.
- **Which part is agentic?** Code decides what is flagged, every evidence state, the verdict, the value tiers,
  and the owners, review date and KPI watch at approval. The model decides which read-only check to run next
  and how to word the brief, the plan draft and the notices, from numbers it is handed. The person decides
  whether to act, what the plan says, who does what by when, whether to send a notice, and what to do at the
  review date. Say "AI-assisted workflow"; a coding agent built parts of the software, which does not make the
  product agentic.
- The model (gpt-5-mini on GW's Azure OpenAI) **never writes SQL, never produces a number, never sets an
  evidence state, never sees individual survey answers, never approves anything, and never sends anything.** Without a key everything
  works in rules mode; with a key a question took about 18 to 58 s on the v0.8 data (ten live turns, Oct 8). The
  demo's scripted turns are saved model runs, shown labelled "Prepared answer" with a **Run live** button; they
  must be regenerated for this variant (`scripts/prepare_investigations.py`).

## Privacy rules (in the database, not the prompt)
Teams with fewer than 4 respondents are never shown on their own. Teams under 4 people show no team numbers and
are left out of every team, site or shift total the tools compute, so nothing can be recovered by subtraction.
Comments from small teams are never searched. Questions about individual people are declined on every turn,
before any check runs. There is no patient data anywhere in the product, so HIPAA is out of scope: the records are
staff-level counts (doses, shifts, absences), never a patient, a diagnosis or an HCAHPS response.

## What it cannot do (say this before a judge does)
- It cannot prove a cause. It finds associations and checks whether the operating number moved.
- It only has internal comparisons. An external Gallup benchmark is an **assumed** data source, shown as
  "unavailable". A two-month follow-up pulse is an **assumption** for a pilot, not in the demo data.
- It is not a patient-safety system. A late dose is counted as an operating signal, never judged clinically.
- Tested on synthetic data for a fictional hospital system (Lanford Health), with eval packs the builder wrote.
  An independent holdout and a user test are ready to run but have no results yet.
- Small samples: 24 teams and 2 survey waves. It says "insufficient" rather than guess.

Deeper: `docs/ARCHITECTURE.md` · `docs/risk/TEVV_EVIDENCE.md` · `docs/demo/DEMO_SCRIPT.md` · Trust & method in the app.
