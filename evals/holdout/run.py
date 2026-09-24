"""Run the holdout questions (written by a teammate who has not seen truth.json). See README.md."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from app import config
from evals.run_evals import evaluate

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-model", action="store_true")
    args = ap.parse_args()
    qpath = HERE / "questions.json"
    if not qpath.exists():
        print("No evals/holdout/questions.json yet: the holdout set is pending. See evals/holdout/README.md.")
        return 0
    if args.no_model:
        config.has_key = lambda: False
    out = HERE / "results"
    s = evaluate(questions_path=qpath, results_dir=out, label=None if config.has_key() else "rules-only")
    safe = "rules-only" if s["model"] == "rules-only" else s["model"]
    first = out / f"first_run_{safe}.json"
    if not first.exists():
        shutil.copy(out / f"latest_{safe}.json", first)
    print(f"holdout · {s['model']}: {s['passed']}/{s['total']} passed · matrix {s['matrix']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
