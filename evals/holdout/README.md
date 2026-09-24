# Holdout kit: questions written by someone who has not seen the answers

The gold set (`evals/questions.json`) and the adversarial pack were written by the person who built the tool
and planted the data. That grades our own homework. This kit is for a teammate who has **not** opened
`data/generated/truth.json` or the planted-pattern list in `DATA_SPEC.md` ("P1–P13").

## Rules for the author
1. Do not open `data/generated/truth.json`, `data/generate.py`, `data/generate_impact.py`, or the "Planted patterns"
   section of `DATA_SPEC.md`. Do use the app itself and the rest of `DATA_SPEC.md` (what tables exist).
2. Write about **15 questions** into `evals/holdout/questions.json`, copying the shape of `template.json`:
   - ~5 **positive**: you believe the tool should find and name an obstacle.
   - ~5 **negative**: it should decline, say "insufficient", or suppress (small team, data we don't have, a blip).
   - ~5 **lookup**: a factual question with a checkable answer (use `owner_contains` / `message_contains`).
3. Write your expectation *before* running the tool, and give the reason in `why`. Do not edit an expectation
   after you see the answer. If you think the tool was right and you were wrong, add a new question instead
   and note it.
4. Commit `questions.json` before the first run.

## Run it
```bash
.venv/bin/python -m evals.holdout.run --no-model      # rules mode
.venv/bin/python -m evals.holdout.run                 # the GW model
```
Results go to `evals/holdout/results/`. The first run in each mode is kept as `first_run_<mode>.json`, and the
Quality tab in the app shows it as the holdout score. Until `questions.json` exists, the app shows "pending".
