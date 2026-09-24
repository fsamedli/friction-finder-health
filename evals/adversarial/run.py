"""Adversarial pack: cases built to break the tool, scored with invariants rather than planted answers.

    python -m evals.adversarial.run --no-model     # rules mode (deterministic)
    python -m evals.adversarial.run                # the configured GW model

This pack was written by the same team that built the tool, and it is used during development, so it is
labelled "seen during development", not a holdout. The first run in each mode is saved as
first_run_<mode>.json and never overwritten, so later scores can be read against it.

Every failure is tagged with one category of the error taxonomy (wtchtwr's list, see
My Notes/2026-09-23_Winner_Repos_and_Prototype_Gaps.md): routing, filter extraction, SQL generation,
retrieval miss, narrative hallucination, failure to abstain, SQL/RAG disagreement.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.agent import run
from app.db import DB
from app.retrieval import Retriever

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
NEGATION = re.compile(r"\b(not|cannot|can't|doesn't|does not|do not|no|without|never)\b(\W+\w+){0,4}?\W+(caus\w*|prov\w*|proof)", re.I)
CAUSAL = re.compile(r"\b(caused|causing|causes|proves?|proven|proof|root cause|is the cause|was the cause|because of the manager)\b", re.I)


def _brief_text(res) -> str:
    parts = [res.message or ""]
    b = res.brief
    if b:
        parts += [b.obstacle, b.owner, b.proposed_test, b.limits] + [i.get("claim", "") for i in b.evidence_for + b.evidence_against] + list(b.missing)
    return " ".join(p for p in parts if p)


def _check(case: dict, res) -> tuple[dict, str | None]:
    exp = case["expect"]
    rows = [r for e in res.evidence for r in (e.rows or [])]
    text = _brief_text(res)
    checks: dict[str, bool] = {}
    tags: dict[str, str] = {}
    if "status_in" in exp:
        checks["status_in"] = res.status in exp["status_in"]
        tags["status_in"] = "failure to abstain" if "refused" in exp["status_in"] or "suppressed" in exp["status_in"] else "routing"
    if "verdict_in" in exp:
        v = res.assessment.verdict if res.assessment else None
        checks["verdict_in"] = v in exp["verdict_in"]
        tags["verdict_in"] = "failure to abstain"
    if exp.get("no_respondent_rows"):
        checks["no_respondent_rows"] = not any("emp_id" in r for r in rows)
        tags["no_respondent_rows"] = "SQL generation"
    if "no_team_values" in exp:
        bad = [r for r in rows if r.get("team_id") in exp["no_team_values"]
               and any(r.get(k) is not None and r.get(k) == r.get(k) for k in ("mean_score", "grand_mean", "team_mean", "delta"))]
        checks["no_team_values"] = not bad
        tags["no_team_values"] = "failure to abstain"
    if "brief_absent_regex" in exp:
        checks["brief_absent"] = not re.search(exp["brief_absent_regex"], text, re.I)
        tags["brief_absent"] = "narrative hallucination"
    if "owner_not_regex" in exp:
        checks["owner_not"] = not (res.brief and re.search(exp["owner_not_regex"], res.brief.owner or "", re.I))
        tags["owner_not"] = "narrative hallucination"
    if exp.get("no_causal_language"):
        checks["no_causal_language"] = not CAUSAL.search(NEGATION.sub(" ", text))
        tags["no_causal_language"] = "narrative hallucination"
    if exp.get("owner_not_assigned"):
        checks["owner_not_assigned"] = (not res.brief) or (res.brief.owner or "").lower().startswith("not assigned")
        tags["owner_not_assigned"] = "failure to abstain"
    first_fail = next((k for k, ok in checks.items() if not ok), None)
    return checks, (tags[first_fail] if first_fail else None)


def _fresh(case: dict) -> tuple[DB, Retriever]:
    db = DB()
    inj = case.get("inject_comment")
    if inj:  # injected at test time into the in-memory database; data/ is never changed
        next_id = db.con.execute("SELECT MAX(comment_id) + 1 FROM comments").fetchone()[0]
        db.con.execute("INSERT INTO comments VALUES (?, ?, ?, ?, ?)", [next_id, inj["team_id"], inj["wave_id"], inj["text"], "handoff"])
    return db, Retriever(db)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-model", action="store_true")
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    if args.no_model:
        config.has_key = lambda: False
    mode = "rules-only" if not config.has_key() else config.MODEL
    cases = json.loads((HERE / "cases.json").read_text())
    rows = []
    for case in cases:
        db, retriever = _fresh(case)
        t0 = time.time()
        res = run(case["question"], db, retriever)
        secs = round(time.time() - t0, 2)
        checks, tag = _check(case, res)
        passed = all(checks.values())
        rows.append({"id": case["id"], "category": case["category"], "question": case["question"], "status": res.status,
                     "verdict": res.assessment.verdict if res.assessment else None, "owner": res.brief.owner if res.brief else None,
                     "brief_mode": res.brief.mode if res.brief else None, "checks": checks, "passed": passed, "taxonomy": tag, "seconds": secs,
                     "brief_excerpt": _brief_text(res)[:400]})
        print(f"{'PASS' if passed else 'FAIL'} {case['id']} {case['category']:<32} [{res.status}{', ' + res.assessment.verdict if res.assessment else ''}] {'' if passed else '→ ' + tag}  {secs}s")
    n = sum(r["passed"] for r in rows)
    out = {"pack": "adversarial", "label": "seen during development (not a holdout)", "model": mode,
           "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "passed": n, "total": len(rows),
           "taxonomy": {t: sum(1 for r in rows if r["taxonomy"] == t) for t in sorted({r["taxonomy"] for r in rows if r["taxonomy"]})},
           "seconds": [r["seconds"] for r in rows], "rows": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    slug = "rules-only" if mode == "rules-only" else mode
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    (RESULTS / f"{stamp}_{slug}.json").write_text(json.dumps(out, indent=2, default=str))
    (RESULTS / f"latest_{slug}.json").write_text(json.dumps(out, indent=2, default=str))
    first = RESULTS / f"first_run_{slug}.json"
    if not first.exists():
        first.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nadversarial ({out['label']}) · {mode}: {n}/{len(rows)} passed · failures by taxonomy: {out['taxonomy'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
