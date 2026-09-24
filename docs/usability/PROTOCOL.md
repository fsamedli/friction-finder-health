# Usability test protocol: 5 people acting as site managers

**Status: ships empty. No sessions have been run. No results exist.** Scores appear only after real sessions.

## Why
The rubric rewards "quality measured by analytical metrics **and user satisfaction**". Neither Fall 2025 winner
measured satisfaction. This kit makes a small, honest measurement possible in one afternoon.

## Participants
- 5 people who have not seen the app. Ideally 1–2 with operations or HR experience; classmates are fine and
  are reported as such.
- Each one plays **the site operations manager at the Richmond distribution center**. Read them this, and only
  this: "Your site runs three shifts. You got the latest engagement survey results this week. Use this tool to
  decide where to look first."

## Setup (5 minutes)
1. `./run_demo.sh`, open `http://127.0.0.1:8000/?study=1`, enter the participant id (`P1`–`P5`) and click Begin.
2. In the user menu, **Reset demo** before each participant. Make sure the demo clock is on **Sept 15**.
3. Do not use Start demo. Do not show the Ask page first.

## Tasks (the study bar logs start and finish times)
| # | Task (read aloud) | Success means |
|---|---|---|
| 1 | "Find the team that is costing the site the most right now." | lands on Richmond Night A (Today card or Teams table) |
| 2 | "Explain why: what moved, and what is behind it?" | names late departures **and** the materials/equipment or shift-handoff evidence |
| 3 | "Approve a plan for that team, then check whether it worked." | approves a plan, then reaches the Impact review with a verdict (they may use the demo clock) |

The participant clicks **Task n** to start and **Done** or **Gave up** to finish. Don't help. If they are stuck
for 2 minutes, say "take your best guess", then mark it as gave up.
Think-aloud is encouraged; the moderator writes down quotes by hand. Do not record names.

## Questionnaire
After task 3 the study bar shows **Questionnaire** (`/study/sus`): the 10-item System Usability Scale
(Brooke, 1996), standard wording, 1–5, plus two open questions:
1. What would stop you from using this at your site?
2. What was the most useful thing you saw, and why?

## Scoring
```bash
.venv/bin/python scripts/score_study.py            # reads study.jsonl next to approvals.jsonl
```
It reports per participant: task success, time on task, and SUS score; then the mean and range across
participants. SUS: odd items (score − 1), even items (5 − score), sum × 2.5, so the range is 0–100.
Report n = 5 honestly. With five people this finds usability problems; it does not estimate a population score.

## Privacy
`study.jsonl` holds participant ids (P1–P5), timestamps, task outcomes and answers. It holds no names. It is
git-ignored. Keep it on this machine.
