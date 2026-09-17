# Friction Finder prototype (Group 4, DNSC 6317)

An assistant for an HR or operations leader who sees a team's engagement score drop and has to
work out the likely obstacle and who owns the fix. It joins survey aggregates, operational
records, and documents, and writes a cited one-page brief. A person approves it. It declines
when the data cannot answer.

Everything in `data/` is synthetic. Northline Logistics does not exist. Planted patterns are
listed in `data/generated/truth.json` so the assistant can be scored. Design: `SPEC.md`.

## Run it

```bash
cd prototype
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # then put the GW-provided key in .env as GW_AZURE_OPENAI_KEY
.venv/bin/python data/generate.py
.venv/bin/python -m app.probe   # confirms which deployments the GW Azure resource exposes
.venv/bin/streamlit run app/ui.py
```

The model is the GW-assigned Azure OpenAI resource (`gw-sb-04`), deployments `gpt-5-mini` for
chat and `text-embedding-3-small` for embeddings, as found by the probe on Sept 14, 2026. The
key lives only in `.env` (git-ignored). Never paste it into code, notebooks, or chat.

Without a key the app still runs: rule-based scoping, keyword retrieval, and a templated brief.
With the key: the model extracts the question's scope, embeddings power retrieval, and the model
writes the brief from the evidence it is handed. Every number still comes from SQL and Python.
A full question takes roughly 10 to 25 seconds with the model, under a second without.

## Check it

```bash
.venv/bin/python -m pytest tests -q        # data patterns, suppression, numbers, brief checks, refusals
.venv/bin/python -m evals.run_evals        # eight gold questions against the truth file
.venv/bin/python -m app.cli "Why did the Richmond night shift's scores drop and why are deliveries late?"
```

## The five demo moments

1. "Why did the Richmond night shift's scores drop and why are deliveries late?" Chart, evidence
   table, brief with owner and proposed test, "show me" SQL under every number.
2. "Why did the Richmond Dispatch Day team's scores drop?" Fewer than 4 respondents: suppressed,
   rolled up to the site, with the reason. (Keegan's first question.)
3. Sidebar: upload a CSV of delay records; ask again; the new rows are in the evidence.
   (Keegan's second question.)
4. "What caused turnover on the Norfolk night shift?" or "Why did the Denver site drop?" Declined
   with a reason.
5. Approve or reject the brief; the decision lands in `approvals.jsonl`.

## Rules the code enforces

- Minimum n is 4. Team-level means are NULL below that, in the SQL views, before any model
  call. Comments from those team-waves are never indexed.
- The model never queries respondent rows: `run_sql` allows only the views and a short list of
  tables, and only single SELECT statements.
- The brief is checked: every citation must exist, every number must appear in the evidence,
  and causal language is rejected. Two failures and the templated brief is shown instead.
- GW-provided OpenAI API only, via `.env`. No fine-tuning. The key never leaves the laptop.

## Layout

```
app/config.py     .env, model names, threshold
app/db.py         DuckDB, suppressed views, guarded run_sql, CSV upload
app/retrieval.py  document and comment chunks; embeddings or keyword search
app/agent.py      scope, analyze, retrieve, explain (+ check + fallback), approve, run
app/ui.py         Streamlit screen
app/cli.py        command-line runner
data/generate.py  synthetic company with planted patterns; writes data/generated and data/docs
evals/            questions.json and run_evals.py
tests/            pytest
```
