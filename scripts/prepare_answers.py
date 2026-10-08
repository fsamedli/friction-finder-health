"""Generate the prepared answers for the demo's scripted Ask questions, once, in model mode.

Run:  .venv/bin/python scripts/prepare_answers.py
Needs the GW key in .env. Without a key it writes nothing and says so. Each answer is saved with the time
it was generated and the model, and the app labels it "Prepared answer · generated <time> with <model>".
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402

from api import main as M  # noqa: E402
from app import config  # noqa: E402

QUESTIONS = [
    "Why did the Lanford night shift's scores drop and why are doses late?",
    "Did the Westbrook Telemetry Day team really decline?",
    "Who owns the medication cabinet restock schedule at Lanford?",
]


def main() -> int:
    if not config.has_key():
        print("No GW key: nothing generated. The app runs Ask live (rules mode) instead.")
        return 0
    c = TestClient(M.app)
    out = {}
    for q in QUESTIONS:
        d = c.post("/api/ask", json={"question": q, "live": True}).json()
        if d.get("mode") != "model":
            print(f"skipped (not model mode): {q}")
            continue
        res = M._state["results"][d["id"]]
        approval = {"question": res.question, "verdict": res.assessment.verdict if res.assessment else None,
                    "brief_mode": res.brief.mode if res.brief else None, "brief": asdict(res.brief) if res.brief else None,
                    "evidence_ids": [e.id for e in res.evidence]}
        response = {k: v for k, v in d.items() if k not in ("id", "prepared")}
        out[M._norm(q)] = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": config.MODEL,
                           "response": response, "approval": approval}
        g = d.get("grounding", {})
        print(f"{d['seconds']:>5}s  {g.get('checked')}/{g.get('total')} numbers checked  {q}")
    M.PREPARED_PATH.parent.mkdir(parents=True, exist_ok=True)
    M.PREPARED_PATH.write_text(json.dumps(out, indent=2, default=str))
    print(f"wrote {len(out)} prepared answers to {M.PREPARED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
