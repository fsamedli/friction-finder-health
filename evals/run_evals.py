"""Run the gold questions against the truth file and score them as a confusion matrix.

    python -m evals.run_evals                 # the configured model (or rules mode without a key)
    python -m evals.run_evals --model gpt-5   # another deployment on the same GW resource
    python -m evals.run_evals --no-model      # force rules + templated text

Scoring (judge Finan, Mizuho, Sept 15, 2026: "test cases with expected outcomes, scored as a
confusion matrix; weight false negatives highest"):
- positive cases: a planted, corroborated problem exists. Found = true positive; missed = false negative.
- negative cases: no corroborated problem (a blip, one loud comment, a suppressed team, data we do
  not have). Declined or 'insufficient' with no owner = true negative; an obstacle named = false positive.
- lookup cases: pass or fail on the expected numbers and kinds; not part of the matrix.
Every run is saved under evals/results/ so the UI can show the last run and compare models."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.agent import check_brief, plan, run
from app.db import DB
from app.retrieval import Retriever

HERE = Path(__file__).resolve().parent
TRUTH = HERE.parent / "data" / "generated" / "truth.json"
RESULTS = HERE / "results"

_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)")


def _lookup(truth: dict, path: str):
    cur = truth
    for part in path.split("."):
        cur = cur[part]
    return cur


def _num_in_text(value, text: str, tol: float = 0.015) -> bool:
    """A truth number counts as present if a number in the text matches it within `tol`
    (rounding through the SQL views can move the second decimal). Percentages are compared
    on the 0-1 scale."""
    found = []
    for m in _NUM.finditer(text):
        x = float(m.group(1))
        found.append(x / 100 if m.group(2) else x)
    if isinstance(value, float):
        return any(abs(x - value) <= tol for x in found)
    return any(abs(x - float(value)) < 1e-9 for x in found)


def _check(q: dict, res, db: DB, truth: dict) -> dict:
    exp = q["expect"]
    checks = {"status": res.status == exp["status"]}
    kinds = {e.kind for e in res.evidence}
    a = res.assessment
    if "verdict" in exp:
        checks["verdict"] = bool(a) and a.verdict == exp["verdict"]
    if "verdict_in" in exp:
        checks["verdict_in"] = bool(a) and a.verdict in exp["verdict_in"]
    if "evidence_kinds" in exp:
        checks["evidence_kinds"] = set(exp["evidence_kinds"]) <= kinds
    if "evidence_kinds_absent" in exp:
        checks["evidence_kinds_absent"] = not (set(exp["evidence_kinds_absent"]) & kinds)
    if "message_contains" in exp:
        checks["message_contains"] = exp["message_contains"].lower() in (res.message or "").lower()
    if "obstacle_contains" in exp:
        checks["obstacle_contains"] = bool(res.brief) and exp["obstacle_contains"] in res.brief.obstacle.lower()
    if "obstacle_matches" in exp:
        checks["obstacle_matches"] = bool(res.brief) and re.search(exp["obstacle_matches"], res.brief.obstacle, re.I) is not None
    if "obstacle_not_contains" in exp:
        checks["obstacle_not_contains"] = bool(res.brief) and exp["obstacle_not_contains"] not in res.brief.obstacle.lower()
    if "owner_contains" in exp:
        checks["owner_contains"] = bool(res.brief) and exp["owner_contains"] in res.brief.owner
    if exp.get("owner_not_assigned"):
        checks["owner_not_assigned"] = (res.brief is None) or res.brief.owner.lower().startswith("not assigned")
    if exp.get("brief_checks_pass"):
        checks["brief_checks_pass"] = bool(res.brief) and check_brief(res.brief, res.evidence, a) == []
    if "truth_numbers" in exp:
        text = (res.message or "") + " " + " ".join(e.statement for e in res.evidence)
        if res.brief:
            text += " " + json.dumps(res.brief.__dict__)
        checks["truth_numbers"] = all(_num_in_text(_lookup(truth, p), text) for p in exp["truth_numbers"])
    if "mix_shift" in exp:
        mix = [e for e in res.evidence if e.kind == "tenure_mix"]
        checks["mix_shift"] = bool(mix) and mix[0].value.get("mix_shift") is exp["mix_shift"]
    if "signal_verdict" in exp:
        sig = [e for e in res.evidence if e.kind == "signal_check"]
        checks["signal_verdict"] = bool(sig) and sig[0].value.get("verdict") == exp["signal_verdict"]
    if "comment_top_count_below" in exp:
        th = [e for e in res.evidence if e.kind == "comment_themes"]
        checks["comment_top_count_below"] = bool(th) and th[0].value.get("top_count", 0) < exp["comment_top_count_below"]
    if "watch_contains" in exp:
        hm = [e for e in res.evidence if e.kind == "site_heatmap"]
        want = exp["watch_contains"]
        checks["watch_contains"] = bool(hm) and any(w["team"] == want["team"] and w["item"] == want["item"] for w in hm[0].value.get("watch", []))
    if "plan_actions" in exp:
        p = plan(res, db)
        lo, hi = exp["plan_actions"]
        checks["plan_actions"] = bool(p) and lo <= len(p.actions) <= hi and all(x.get("owner_name") for x in p.actions)
    return checks


def _outcome(q: dict, res, passed: bool) -> str:
    """Confusion-matrix cell for positive and negative cases; 'pass'/'fail' for lookups."""
    cls = q.get("class", "lookup")
    a = res.assessment
    named = bool(a and a.verdict == "supported") or bool(res.brief and not res.brief.owner.lower().startswith("not assigned"))
    if cls == "positive":
        return "TP" if (passed and named) else "FN"
    if cls == "negative":
        return "FP" if named else ("TN" if passed else "FN*")   # FN*: declined for the wrong reason (counts as a miss)
    return "pass" if passed else "fail"


def evaluate(db: DB | None = None, retriever: Retriever | None = None, save: bool = True, label: str | None = None) -> dict:
    db = db or DB()
    retriever = retriever or Retriever(db)
    truth = json.loads(TRUTH.read_text())["patterns"]
    questions = json.loads((HERE / "questions.json").read_text())
    rows = []
    t_all = time.time()
    for q in questions:
        t0 = time.time()
        res = run(q["question"], db, retriever)
        checks = _check(q, res, db, truth)
        passed = all(checks.values())
        rows.append({"id": q["id"], "class": q.get("class", "lookup"), "planted": q.get("planted", []), "question": q["question"],
                     "status": res.status, "verdict": res.assessment.verdict if res.assessment else "",
                     "brief_mode": res.brief.mode if res.brief else "", "check_notes": res.brief.check_notes if res.brief else [],
                     "passed": passed, "checks": checks, "outcome": _outcome(q, res, passed), "seconds": round(time.time() - t0, 1)})
    matrix = {k: sum(1 for r in rows if r["outcome"] == k) for k in ("TP", "FN", "FP", "TN", "FN*")}
    lookups = [r for r in rows if r["class"] == "lookup"]
    regenerated = sum(1 for r in rows if any("failed" in n for n in r["check_notes"]))
    model = label or (config.MODEL if config.has_key() else "rules-only")
    summary = {"model": model, "retrieval": retriever.mode, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "passed": sum(r["passed"] for r in rows), "total": len(rows), "matrix": matrix,
               "lookups_passed": sum(r["passed"] for r in lookups), "lookups_total": len(lookups),
               "briefs_regenerated_or_fallback": regenerated, "seconds": round(time.time() - t_all, 1), "rows": rows}
    if save:
        RESULTS.mkdir(exist_ok=True)
        safe = re.sub(r"[^a-z0-9.-]+", "_", model.lower())
        (RESULTS / f"latest_{safe}.json").write_text(json.dumps(summary, indent=2))
        (RESULTS / f"{summary['ts'].replace(':', '')}_{safe}.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="Azure deployment name to use for this run (e.g., gpt-5)")
    ap.add_argument("--no-model", action="store_true", help="force rules mode: no key, keyword retrieval, templated text")
    args = ap.parse_args()
    if args.no_model:
        os.environ["GW_AZURE_OPENAI_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""
    if args.model:
        config.MODEL = args.model
    s = evaluate()
    for r in s["rows"]:
        flag = "PASS" if r["passed"] else "FAIL"
        failed = [k for k, v in r["checks"].items() if not v]
        print(f"{flag} {r['id']:>3} {r['outcome']:<4} [{r['status']}{', ' + r['verdict'] if r['verdict'] else ''}{', ' + r['brief_mode'] if r['brief_mode'] else ''}] "
              f"{r['question'][:62]:<62} {r['seconds']:>5}s" + (f"  -> failed: {failed}" if failed else ""))
    m = s["matrix"]
    print(f"\nmodel: {s['model']} | retrieval: {s['retrieval']} | {s['passed']}/{s['total']} passed in {s['seconds']}s")
    print(f"confusion matrix over planted problems: TP={m['TP']} FN={m['FN']} FP={m['FP']} TN={m['TN']}" + (f" FN*={m['FN*']}" if m["FN*"] else ""))
    print(f"lookups: {s['lookups_passed']}/{s['lookups_total']} | briefs regenerated or fallen back: {s['briefs_regenerated_or_fallback']}")
    sys.exit(0 if s["passed"] == s["total"] else 1)


if __name__ == "__main__":
    main()
