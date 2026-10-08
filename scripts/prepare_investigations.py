"""Generate the prepared answers for the demo's three scripted investigations (each with one follow-up), once, in
model mode. Saved with the time and the model; the panel labels them "Prepared · generated <time> with <model>"
and offers "Run live". Needs the GW key; without it, writes nothing.

Run:  .venv/bin/python scripts/prepare_investigations.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api import main as M  # noqa: E402
from app import config  # noqa: E402
from app import investigate as V  # noqa: E402

SCRIPTS = [("Why is Night A flagged?", "Could staffing explain this?"),
           ("Compare it with the other night shifts", "When did it start?"),
           ("Is this normal for teams like ours?", "What is missing?")]
CTX = {"team_id": 4, "site_id": 1, "as_of": "2026-09-15"}


def key(q: str, followup: bool) -> str:
    return " ".join(q.lower().strip().rstrip("?.! ").split()) + f"|{CTX['team_id']}|{CTX['as_of']}|{'followup' if followup else 'first'}"


def main() -> int:
    if not config.has_key():
        print("No GW key: nothing generated.")
        return 0
    db, rt = M._db(), M._retriever()
    out, traces = {}, []
    for first, follow in SCRIPTS:
        cid = None
        for i, q in enumerate((first, follow)):
            inv = M._jsonable(V.investigate(q, CTX, cid, "auto", db, rt))
            cid = inv["conversation_id"]
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            out[key(q, i == 1)] = {"generated_at": stamp, "model": config.MODEL, "investigation": inv}
            traces.append(inv)
            b = inv["budget"]
            print(f"{b['seconds']:>5}s  mode={inv['mode']} sel={inv['selection']} tools={b['tool_calls']} model={b['model_requests']} "
                  f"written_by={(inv['answer'] or {}).get('written_by')} check={inv['check']['passed']}  {q}")
    V.PREPARED_PATH.parent.mkdir(parents=True, exist_ok=True)
    V.PREPARED_PATH.write_text(json.dumps(out, indent=1, default=str))
    print(f"wrote {len(out)} prepared investigations to {V.PREPARED_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
