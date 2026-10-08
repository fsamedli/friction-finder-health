"""AI-assisted investigation (v0.8): ONE bounded coordinator over a fixed registry of read-only tools.

Shape: out_of_scope runs first (every turn) -> the question is read into one manager function and the context
is resolved (app/relations.py) -> tools run, chosen by the model from the registry (model mode) or by a fixed
plan per function (rules mode, no model, same output shape) -> code computes every number and sets the
evidence state by explicit rules -> the answer text is templated, or written by the model and then checked
(coverage, numbers, provenance, causal words) -> a person approves any action.

Budgets, enforced here: at most 6 tool calls, 8 model requests, 1 retry per failed model call, 60 s wall time;
an equivalent repeated tool call is refused. At the limit the answer is built from what was gathered.
Retrieved text and tool output are data: they never change the tool list, the context or the privacy rules."""
from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app import config

MAX_TOOL_CALLS, MAX_MODEL_REQUESTS, MAX_SECONDS = 6, 8, 60.0
TTL_SECONDS = 4 * 3600
STATES = ("supported", "mixed", "insufficient", "unavailable")
RANK = {s: i for i, s in enumerate(STATES)}


@dataclass
class Ev:
    id: str
    kind: str
    statement: str
    tool: str
    turn: int
    sql: str | None = None
    rows: list = field(default_factory=list)
    source: str = ""
    value: dict = field(default_factory=dict)
    origin: str = "computed"     # computed | retrieved
    stale: bool = False

    def public(self) -> dict:
        return {"id": self.id, "kind": self.kind, "statement": self.statement, "sql": self.sql, "rows": self.rows[:60],
                "source": self.source, "origin": self.origin, "tool": self.tool, "turn": self.turn, "stale": self.stale}


@dataclass
class Conversation:
    id: str
    context: dict
    register: dict = field(default_factory=dict)       # evidence id -> Ev, across turns
    turns: list = field(default_factory=list)          # investigation ids
    counter: int = 0
    touched: float = field(default_factory=time.time)

    def new_id(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}{self.counter}"


_CONV: dict[str, Conversation] = {}
_INV: dict[str, dict] = {}
_LOCK = threading.Lock()


def _gc() -> None:
    now = time.time()
    for k in [k for k, c in _CONV.items() if now - c.touched > TTL_SECONDS]:
        _CONV.pop(k, None)


class Run:
    """One turn: budget counters and the live trace (read by GET /api/investigate/{id} while it runs)."""

    def __init__(self, inv: dict):
        self.inv, self.t0 = inv, time.time()
        self.tool_calls = self.model_requests = 0
        self.stopped: str | None = None
        self.seen: set[str] = set()

    def step(self, step: str, detail: str, mode: str, seconds: float | None, tool: str | None = None) -> None:
        self.inv["trace"].append({"step": step, "detail": detail, "mode": mode,
                                  "seconds": None if seconds is None else round(seconds, 1), **({"tool": tool} if tool else {})})
        self.sync()

    def sync(self) -> None:
        self.inv["budget"] = {"tool_calls": self.tool_calls, "max_tool_calls": MAX_TOOL_CALLS, "model_requests": self.model_requests,
                              "max_model_requests": MAX_MODEL_REQUESTS, "seconds": round(time.time() - self.t0, 1),
                              "max_seconds": MAX_SECONDS, "stopped": self.stopped}

    def time_left(self) -> float:
        return MAX_SECONDS - (time.time() - self.t0)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
