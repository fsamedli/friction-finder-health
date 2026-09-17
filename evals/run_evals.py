"""Run the gold questions against the truth file.  python -m evals.run_evals"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.agent import check_brief, run
from app.db import DB
from app.retrieval import Retriever

HERE = Path(__file__).resolve().parent
TRUTH = HERE.parent / "data" / "generated" / "truth.json"


def _lookup(truth: dict, path: str):
    cur = truth
    for part in path.split("."):
        cur = cur[part]
    return cur


import re

_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)")


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


def evaluate(db: DB | None = None, retriever: Retriever | None = None) -> list[dict]:
    db = db or DB()
    retriever = retriever or Retriever(db)
    truth = json.loads(TRUTH.read_text())["patterns"]
    questions = json.loads((HERE / "questions.json").read_text())
    results = []
    for q in questions:
        res = run(q["question"], db, retriever)
        exp = q["expect"]
        checks = {}
        checks["status"] = res.status == exp["status"]
        kinds = {e.kind for e in res.evidence}
        if "evidence_kinds" in exp:
            checks["evidence_kinds"] = set(exp["evidence_kinds"]) <= kinds
        if "evidence_kinds_absent" in exp:
            checks["evidence_kinds_absent"] = not (set(exp["evidence_kinds_absent"]) & kinds)
        if "message_contains" in exp:
            checks["message_contains"] = exp["message_contains"].lower() in (res.message or "").lower()
        if "obstacle_contains" in exp:
            checks["obstacle_contains"] = bool(res.brief) and exp["obstacle_contains"] in res.brief.obstacle.lower()
        if exp.get("brief_checks_pass"):
            checks["brief_checks_pass"] = bool(res.brief) and check_brief(res.brief, res.evidence) == []
        if "truth_numbers" in exp:
            text = (res.message or "") + " " + " ".join(e.statement for e in res.evidence)
            if res.brief:
                text += " " + json.dumps(res.brief.__dict__)
            checks["truth_numbers"] = all(_num_in_text(_lookup(truth, p), text) for p in exp["truth_numbers"])
        if "mix_shift" in exp:
            mix = [e for e in res.evidence if e.kind == "tenure_mix"]
            checks["mix_shift"] = bool(mix) and mix[0].value.get("mix_shift") is exp["mix_shift"]
        results.append({"id": q["id"], "question": q["question"], "status": res.status,
                        "brief_mode": res.brief.mode if res.brief else "", "passed": all(checks.values()),
                        "checks": checks})
    return results


def main():
    results = evaluate()
    n_pass = sum(r["passed"] for r in results)
    for r in results:
        flag = "PASS" if r["passed"] else "FAIL"
        failed = [k for k, v in r["checks"].items() if not v]
        print(f"{flag} {r['id']} [{r['status']}{', ' + r['brief_mode'] if r['brief_mode'] else ''}] {r['question'][:70]}"
              + (f"  -> failed: {failed}" if failed else ""))
    print(f"\n{n_pass}/{len(results)} passed")
    sys.exit(0 if n_pass == len(results) else 1)


if __name__ == "__main__":
    main()
