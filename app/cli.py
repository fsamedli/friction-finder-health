"""Command-line runner:  python -m app.cli "Why did the Lanford night shift's scores drop?" """
from __future__ import annotations

import sys
from dataclasses import asdict

from app.agent import run
from app.db import DB
from app.retrieval import Retriever


def main():
    q = " ".join(sys.argv[1:]) or "Why did the Lanford night shift's scores drop and why are doses late?"
    db = DB()
    retriever = Retriever(db)
    res = run(q, db, retriever)
    print(f"QUESTION: {q}\nSTATUS: {res.status}\nNOTES: {res.notes}")
    if res.scope:
        print("SCOPE:", {k: v for k, v in asdict(res.scope).items() if v not in (None, [], "")})
    if res.message:
        print("MESSAGE:", res.message)
    if res.evidence:
        print("\nEVIDENCE")
        for e in res.evidence:
            print(f"  [{e.id}] {e.kind}: {e.statement[:220]}")
    if res.brief:
        b = res.brief
        print(f"\nBRIEF ({b.mode}; checks: {b.check_notes})")
        print("  Obstacle:", b.obstacle)
        print("  For:")
        for i in b.evidence_for:
            print("   -", i.get("claim"), i.get("evidence_ids"))
        print("  Against:")
        for i in b.evidence_against:
            print("   -", i.get("claim"), i.get("evidence_ids"))
        print("  Missing:", b.missing)
        print("  Owner:", b.owner)
        print("  Test:", b.proposed_test)
        print("  Limits:", b.limits)


if __name__ == "__main__":
    main()
