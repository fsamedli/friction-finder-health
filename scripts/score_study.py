"""Score the usability study log (docs/usability/PROTOCOL.md): task success, time on task, SUS (Brooke, 1996).

    .venv/bin/python scripts/score_study.py [path/to/study.jsonl]

Prints "no data yet" when the log is missing or empty. Never invents or imputes values.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import config  # noqa: E402


def sus_score(answers: list[int]) -> float:
    """Brooke (1996): odd items contribute (score - 1), even items (5 - score); the sum times 2.5 gives 0-100."""
    if len(answers) != 10 or any(a < 1 or a > 5 for a in answers):
        raise ValueError("SUS needs 10 answers from 1 to 5")
    return 2.5 * sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))


def score(records: list[dict]) -> dict:
    people: dict[str, dict] = {}
    for r in records:
        p = people.setdefault(r["participant"], {"tasks": {}, "sus": None, "open": None})
        if r["event"] == "task_start":
            p["tasks"].setdefault(r["task"], {})["start"] = r["ts"]
        elif r["event"] == "task_finish":
            t = p["tasks"].setdefault(r["task"], {})
            t["finish"], t["success"] = r["ts"], r.get("success")
        elif r["event"] == "sus":
            p["sus"], p["open"] = sus_score(r["answers"]), r.get("open_answers")
    for p in people.values():
        for t in p["tasks"].values():
            if "start" in t and "finish" in t:
                t["seconds"] = round((datetime.fromisoformat(t["finish"]) - datetime.fromisoformat(t["start"])).total_seconds(), 1)
    sus = [p["sus"] for p in people.values() if p["sus"] is not None]
    return {"participants": people, "n": len(people), "sus_n": len(sus),
            "sus_mean": round(sum(sus) / len(sus), 1) if sus else None, "sus_range": [min(sus), max(sus)] if sus else None}


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else config.APPROVALS_PATH.parent / "study.jsonl"
    recs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    if not recs:
        print(f"no data yet ({path})")
        return 0
    s = score(recs)
    for pid, p in sorted(s["participants"].items()):
        tasks = ", ".join(f"T{k}: {'ok' if v.get('success') else 'gave up' if v.get('success') is False else '?'} {v.get('seconds', '?')}s" for k, v in sorted(p["tasks"].items()))
        print(f"{pid}: {tasks} | SUS {p['sus'] if p['sus'] is not None else '—'}")
    print(f"\nn={s['n']} participants · SUS n={s['sus_n']} mean={s['sus_mean']} range={s['sus_range']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
