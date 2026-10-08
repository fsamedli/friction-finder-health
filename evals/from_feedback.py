"""Turn 'what was wrong' feedback on investigation answers (feedback.jsonl) into DRAFT eval cases for a person to review.

    python -m evals.from_feedback                  # reads feedback.jsonl next to approvals.jsonl
    python -m evals.from_feedback --out evals/from_feedback_drafts.json

Nothing here becomes a test by itself: each draft says what the user flagged and which evidence ids the answer
cited, and leaves the expectation for a reviewer to write. Ships with no output because there is no feedback yet.
The question and context come from the saved investigation when the server still has it in memory; otherwise the
draft carries only the ids and the reason."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app import config

FEEDBACK = config.APPROVALS_PATH.parent / "feedback.jsonl"


def drafts(rows: list[dict], lookup=None) -> list[dict]:
    out = []
    for i, r in enumerate(x for x in rows if x.get("target") == "investigation" and not x.get("useful")):
        inv = lookup(r["target_id"]) if lookup else None
        out.append({
            "id": f"FB{i + 1:03d}",
            "status": "draft: needs a reviewer",
            "source": {"feedback_ts": r.get("ts"), "investigation_id": r.get("target_id"), "reason": r.get("reason"), "note": r.get("note", "")},
            "question": (inv or {}).get("question"),
            "context": (inv or {}).get("context"),
            "cited_evidence_ids": r.get("evidence_ids", []),
            "expect": None,   # written by a person after checking the answer against the data
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feedback", default=str(FEEDBACK))
    ap.add_argument("--out", default=None, help="write the drafts here (default: print only)")
    a = ap.parse_args()
    path = Path(a.feedback)
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    d = drafts(rows)
    print(f"{len(rows)} feedback rows, {len(d)} draft cases from investigation answers marked wrong")
    if a.out and d:
        Path(a.out).write_text(json.dumps(d, indent=2))
        print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
