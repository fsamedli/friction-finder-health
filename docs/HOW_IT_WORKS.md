# How Friction Finder works (one page, for everyone on the team)

**What it is:** an AI-assisted workflow that helps a site manager at an operations-heavy company (warehouse,
logistics, call centre) connect engagement survey results to the site's own operating numbers, and check
whether a fix moved the operating number. Inside it is an **AI-assisted investigation**: the manager asks or
challenges ("Could staffing explain this?"), the model chooses which of a fixed set of read-only checks to run
next under a budget, code computes every number, and a person approves every action.

**Who it's for:** the user is the site or shift manager. The buyer is the operations or HR leader who owns the
site budget. The data comes from the client: the survey export (HR) and operating records (operations).
Gallup Access shows *what* moved in the survey and already offers AI next steps and an AI action-planning
prompt (public Help Center, read Oct 8; `docs/research/2026-10-08_Gallup_Access_Overlap.md`). What Access does
not document is the link to the client's own operating data, or a check of an operating number at a review
date. That link is this product. It is built to sit next to Access, not to repeat it.

## The journey (the screens, in order)
1. **Today.** One team that needs attention, why it matters (its operating number against comparable teams,
   and the survey item that fell), and one rust button: "Review Night A and decide". Method details are one
   click down.
2. **Investigate.** The team screen, organised by the manager's questions: Is it real? Is this normal for teams
   like ours? What explains it? What is missing? What do I do? Each block leads with one sentence and one
   evidence state. The investigation panel is docked here.
3. **Action plans.** Owner, operational measure, review date, success criterion and state (draft, approved, in
   review, reviewed), with a queue of due reviews, missing follow-ups and inconclusive outcomes.
4. **Review.** At the review date: improved, deteriorated or inconclusive, with the interval, a placebo check and
   the limits. **Directional, not causal**; in the demo the follow-up months are **synthetic follow-up data**.

## The investigation panel
- Questions it answers (chips, or typed): why is this team flagged; could staffing / who responded / a site-wide
  change / one hour band explain it; compare with the other night shifts; is this normal for teams like ours;
  when did it start; how widespread is it; what is missing; where does this number come from; has this
  happened elsewhere; draft a plan; did it work. "Prepare the team conversation" is **not built** (Gallup's own
  guide covers it; the research note labels it "drop").
- Every answer has a conclusion, an **evidence state** (supported, mixed, insufficient, unavailable; no
  confidence percentages), a competing explanation with its own state, cited evidence that opens the passage or
  the SQL and rows, and a next step. When evidence is weak, the next step is to collect something, with an owner.
- It keeps context across follow-ups ("it", "the other night shifts", "No, I meant Night B").
- The trace shows each step in plain words, whether code or the AI model did it, and the real seconds.

## Where AI is used
- **Ask** (the one-page brief): reading the question, writing the brief.
- **Investigation:** choosing the next check (up to 6 per question), reading the question only when the rules
  reader matches nothing, and wording the conclusion and competing explanation. A code check rejects any wording
  with a number, team or period that is not in the evidence it cites; then the template is shown, labelled.
- The model (gpt-5-mini on GW's Azure OpenAI) **never writes SQL, never produces a number, never sets an
  evidence state, never sees individual survey answers, and never approves anything.** Without a key everything
  works in rules mode; with a key a question takes about 18 to 58 s (four live turns, Oct 8).

## Privacy rules (in the database, not the prompt)
Teams with fewer than 4 respondents are never shown on their own. Teams under 4 people show no team numbers and
are left out of every team, site or shift total the tools compute, so nothing can be recovered by subtraction.
Comments from small teams are never searched. Questions about individual people are declined on every turn,
before any check runs.

## What it cannot do (say this before a judge does)
- It cannot prove a cause. It finds associations and checks whether the operating number moved.
- It only has internal comparisons. An external Gallup benchmark is an **assumed** data source, shown as
  "unavailable". A two-month follow-up pulse is an **assumption** for a pilot, not in the demo data.
- Tested on synthetic data for a fictional company (Northline Logistics), with eval packs the builder wrote. An
  independent holdout and a user test are ready to run but have no results yet.
- Small samples: 24 teams and 2 survey waves. It says "insufficient" rather than guess.

Deeper: `docs/ARCHITECTURE.md` · `docs/risk/TEVV_EVIDENCE.md` · `docs/demo/DEMO_SCRIPT.md` · Trust & method in the app.
