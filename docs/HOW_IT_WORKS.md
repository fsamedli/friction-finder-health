# How Friction Finder works (one page, for everyone on the team)

**What it is:** an AI-assisted workflow that helps a site manager at an operations-heavy company (warehouse,
logistics, call centre) connect engagement survey results to the site's own operating numbers. It answers four
questions in order: **where is it costing us, why, what do we try, and did it work.**

**Who it's for:** the user is the site or shift manager. The buyer is the operations or HR leader who owns the
site budget. The data comes from the client: the survey export (HR) and operating records (operations).
Gallup Access shows *what* moved in the survey; Gallup's Business Impact Analysis links engagement to
business results once a year as a consulting deck. We do that link monthly, per team, on the client's own data.

## The four steps
1. **Detect (Today, Teams).** For each team, the code compares this quarter's late departures, absences, quits,
   injuries and rework with what teams on the same shift at the other sites would predict for a team that
   size. A number is flagged only if it is beyond normal variation (a statistical test). Rare events are
   marked "too rare to judge". A team is "needs attention" only when operations **and** engagement both moved.
2. **Explain (Team detail, Insights).** Which survey items fell, adjusted for who answered (new hires score
   higher, so a wave where they didn't answer can look like a drop). Then, across all teams: which items move
   with which operating numbers, with a confidence interval. That is an **association, not a cause**. Then the
   evidence: employee comments on the same theme, and who owns the process.
3. **Act (Create plan).** The tool drafts one plan: one focus item, three actions with owners and dates, and a
   review date. **A person edits and approves it.** Nothing happens without that approval.
4. **Prove (Impact).** At the review date, the team's change is compared with the change at similar teams that
   didn't act (difference-in-differences), with a 95% interval and a placebo check. The result is "worked",
   "inconclusive" or "no effect". It is **directional, not causal**, and in the demo the follow-up months are
   synthetic.

## Where AI is used: exactly two places
1. **Reading the question** on the Ask page: turning "why did Richmond nights drop?" into a fixed form
   (site, team, items, intent).
2. **Writing the brief** on the Ask page: plain-language text written **only from evidence the code hands it**.
   A checker rejects the brief if it contains a number or citation that isn't in the evidence (the screen
   shows "N of N numbers checked").

The model (gpt-5-mini on GW's Azure OpenAI) **never writes SQL, never produces a number, never decides the
verdict, never sees individual survey answers, and never approves anything.** Without a model key, everything
still works except the written brief, which falls back to a template.

## What is computed by code
Every number on every screen: the flags, expected values, p-values, associations, the difference-in-differences,
the dollars (from unit costs the buyer can edit), and the verdict on the Ask page (rules, not AI).

## Where a person decides
Approving or editing a plan · approving, rejecting or flagging a brief ("this doesn't sound right") · setting
the unit costs · marking a result "useful" or not. Colour code on screen: **teal** = computed by code, **rust** =
needs your decision, **purple** = written by AI and checked.

## Privacy rules (built into the database, not the prompt)
Teams with fewer than 4 respondents are never shown on their own. Teams under 4 people show no team numbers.
Comments from small teams are never searched. Questions about individual people are declined. Every database
query (the model writes none) can only touch approved views, and a parser checks each one.

## What it cannot do (say this before a judge does)
- It cannot prove a cause. It finds associations and checks whether a fix moved the number.
- It is only as good as the operating data the client uploads, and quits and injuries are too rare to judge for
  one team in one quarter.
- Tested on synthetic data for a fictional company (Northline Logistics). The eval questions were written by the
  team; an independent holdout set and a user test are ready to run but have no results yet.
- Small samples: 24 teams and 2 survey waves. It says "not enough data" rather than guess.

Deeper: `docs/ARCHITECTURE.md` (code references, technique choices) · `docs/risk/TEVV_EVIDENCE.md` (risk
evidence) · `docs/demo/DEMO_SCRIPT.md` (the demo) · Trust & method in the app.
