"""v0.8 investigation endpoints (GET /api/functions, POST /api/investigate, GET /api/investigate/{id}).
Kept out of api/main.py so the investigation and the plans/feedback work can change in parallel."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

import threading

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app import investigate as V


class InvestigateIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    conversation_id: str | None = Field(default=None, max_length=40)
    context: dict | None = None
    mode: str = Field(default="auto", pattern="^(auto|rules)$")
    live: bool = False
    function: str | None = None
    async_: bool = Field(default=False, alias="async")


def _clean(x):
    from api import main as M
    return M._jsonable(x)


def _deps():
    from api import main as M     # the app's shared DuckDB and retriever
    return M._db(), M._retriever()


@router.get("/api/functions")
def functions():
    return [{"id": f[0], "label": f[1], "chip": f[2], "question": f[3], "shipped": f[4], "research_label": f[5]} for f in V.FUNCTIONS]


@router.post("/api/investigate")
def investigate(body: InvestigateIn):
    if body.function is not None and body.function not in {f[0] for f in V.FUNCTIONS} | {"metric"}:
        raise HTTPException(422, "unknown function")
    ctx = {k: v for k, v in (body.context or {}).items() if k in ("site_id", "team_id", "as_of", "kpi", "item")}
    hit = None if (body.live or body.mode == "rules") else V.prepared(body.question, ctx, body.conversation_id)
    if hit:
        return _clean(hit)
    db, rt = _deps()
    if body.async_:
        inv = V.new_inv(body.question, body.conversation_id or "")
        V._INV[inv["id"]] = inv
        threading.Thread(target=V.investigate, args=(body.question, ctx, body.conversation_id, body.mode, db, rt, body.function, inv), daemon=True).start()
        return _clean(inv)
    return _clean(V.investigate(body.question, ctx, body.conversation_id, body.mode, db, rt, body.function))


@router.get("/api/investigate/{inv_id}")
def get_investigation(inv_id: str):
    inv = V._INV.get(inv_id)
    if not inv:
        raise HTTPException(404, "unknown investigation (they are kept for 4 hours)")
    return _clean(inv)
