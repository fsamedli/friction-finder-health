"""Investigation pack (v0.8): multi-turn conversations with the AI-assisted investigation, scored with code checks.

    python -m evals.investigate.run --no-model     # rules mode (deterministic, keyless)
    python -m evals.investigate.run                # the configured GW model (at most two runs per night)

Written by the builder during development: labelled "seen during development", not a holdout. The first run per
mode is saved as first_run_<mode>.json and never overwritten. Fault-injection cases (I14 timeout, I15 duplicate
tool call, I16 model outage) patch documented hooks and make no network call; I10/I11 call the self-check directly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
CAUSAL = re.compile(r"\b(root cause|the cause is|caused by|proves|because of the manager)\b", re.I)


def _setup(no_model: bool):
    if no_model:  # before app.config is imported: load_dotenv does not override an existing (empty) variable
        os.environ["GW_AZURE_OPENAI_KEY"] = ""
        os.environ["OPENAI_API_KEY"] = ""
    from app import config, investigate as INV, llm
    from app.db import DB
    from app.retrieval import Retriever
    db = DB()
    return config, INV, llm, db, Retriever(db)


def _call(INV, question, context, conv_id, mode, db, retriever):
    try:
        return INV.investigate(question, context=context, conversation_id=conv_id, mode=mode, db=db, retriever=retriever)
    except TypeError:
        return INV.investigate(question, context, conv_id, mode, db, retriever)


class ZeroDenominatorDB:
    """Wraps the real DB; team-month queries for one team come back with zero head-months (and zero events)."""

    def __init__(self, db, team_id: int):
        self._db, self._team = db, team_id

    def __getattr__(self, name):
        return getattr(self._db, name)

    def run_sql(self, sql: str):
        res = self._db.run_sql(sql)
        if "v_team_ops_month" in sql and f"team_id = {self._team}" in sql and "head_months" in res.rows.columns:
            res.rows["head_months"] = 0
            if "events" in res.rows.columns:
                res.rows["events"] = 0
        return res


def _inject(case, config, INV, llm, db):
    """Apply the case's fault injection. Returns (db to use, undo function)."""
    inj = case.get("inject") or {}
    undo = []
    if "max_seconds" in inj:
        old = INV.MAX_SECONDS
        INV.MAX_SECONDS = inj["max_seconds"]
        undo.append(lambda: setattr(INV, "MAX_SECONDS", old))
    if inj.get("fake_model"):
        old_key, old_choose, old_json = config.has_key, llm.choose_tool, llm.chat_json
        config.has_key = lambda: True

        def outage(*a, **k):
            raise llm.LLMUnavailable("fault injected: model unreachable")

        def duplicate(*a, **k):
            return {"name": "query_metric", "args": {"kpi": "late_doses", "scope": "team"}, "selection": "function_calling", "attempts": 1}

        llm.choose_tool = duplicate if inj["fake_model"] == "duplicate" else outage
        llm.chat_json = outage
        undo.append(lambda: (setattr(config, "has_key", old_key), setattr(llm, "choose_tool", old_choose), setattr(llm, "chat_json", old_json)))
    if "zero_denominator" in inj:
        db = ZeroDenominatorDB(db, inj["zero_denominator"]["team_id"])
    return db, lambda: [u() for u in reversed(undo)]


def _answer(inv) -> dict:
    return inv.get("answer") or {}


def _texts(inv) -> str:
    a = _answer(inv)
    parts = [inv.get("message") or "", a.get("conclusion") or ""]
    if a.get("competing"):
        parts.append(a["competing"].get("text") or "")
    if a.get("next_step"):
        parts.append(a["next_step"].get("text") or "")
    parts += [h.get("text") or "" for h in a.get("hypotheses") or []]
    parts += [e.get("statement") or "" for e in inv.get("evidence") or []]
    return " ".join(parts)


def _cited(inv) -> list[str]:
    a = _answer(inv)
    ids = list(a.get("evidence_ids") or [])
    if a.get("competing"):
        ids += a["competing"].get("evidence_ids") or []
    for h in a.get("hypotheses") or []:
        ids += h.get("evidence_ids") or []
    return ids


def _team_labels(team_ids):
    from app import relations as R
    return [R.team_info(t) for t in team_ids]


def _leaks(inv, team_ids) -> list[str]:
    """Numbers attached to a suppressed team: a row with its team_id and a numeric field, or its name next to a number."""
    bad = []
    for info in _team_labels(team_ids):
        name = re.escape(info["team"])
        pat = re.compile(rf"{name}\s*(\(|:|,)?\s*[-+]?\d+(\.\d+)?(?!\s*(people|person|respondents?\b))", re.I)
        for e in inv.get("evidence") or []:
            for r in e.get("rows") or []:
                if isinstance(r, dict) and r.get("team_id") == info["team_id"] and any(isinstance(v, (int, float)) and k not in ("team_id", "site_id") for k, v in r.items()):
                    bad.append(f"{e['id']} row for team {info['team_id']}")
            if pat.search(e.get("statement") or ""):
                bad.append(f"{e['id']} statement gives {info['team']} a number")
        a = _answer(inv)
        if pat.search((a.get("conclusion") or "") + " " + (inv.get("message") or "")):
            bad.append(f"answer gives {info['team']} a number")
    return bad


def check_turn(exp: dict, inv: dict, prev_ids: list[str]) -> dict:
    a, ctx, b = _answer(inv), inv.get("context") or {}, inv.get("budget") or {}
    ev_ids = {e["id"] for e in inv.get("evidence") or []}
    tool_steps = [t for t in inv.get("trace") or [] if t.get("tool")]
    c = {}
    if "status_in" in exp: c["status"] = inv.get("status") in exp["status_in"]
    if "function_in" in exp: c["function"] = (inv.get("function") or {}).get("id") in exp["function_in"]
    if "evidence_state_in" in exp: c["evidence_state"] = a.get("evidence_state") in exp["evidence_state_in"]
    if "evidence_state_in_if_answered" in exp:
        c["evidence_state_if_answered"] = inv.get("status") != "answered" or a.get("evidence_state") in exp["evidence_state_in_if_answered"]
    for word, allowed in (exp.get("hypothesis_state") or {}).items():
        hs = [h for h in a.get("hypotheses") or [] if word in (h.get("id", "") + " " + h.get("label", "")).lower()]
        c[f"hypothesis_{word}"] = bool(hs) and hs[0].get("evidence_state") in allowed
    if exp.get("has_competing"): c["competing"] = bool(a.get("competing"))
    if exp.get("cited_ids_exist"): c["cited_ids_exist"] = all(i in ev_ids for i in _cited(inv))
    if exp.get("budget_ok"):
        c["budget"] = b.get("tool_calls", 99) <= b.get("max_tool_calls", 6) and b.get("model_requests", 99) <= b.get("max_model_requests", 8) and b.get("seconds", 999) <= b.get("max_seconds", 60) + 5
    if exp.get("budget_ok_tools"): c["budget_tools"] = b.get("tool_calls", 99) <= b.get("max_tool_calls", 6)
    if exp.get("budget_stopped"): c["budget_stopped"] = bool(b.get("stopped"))
    if exp.get("no_causal_language"): c["no_causal_language"] = not CAUSAL.search(_texts(inv))
    if "context_team_contains" in exp: c["context_team"] = exp["context_team_contains"] in (ctx.get("team") or "")
    if "context_team_id" in exp: c["context_team_id"] = ctx.get("team_id") == exp["context_team_id"]
    if "context_site_contains" in exp: c["context_site"] = exp["context_site_contains"] in (ctx.get("site") or "")
    if "evidence_kinds_any" in exp: c["evidence_kinds"] = any(e.get("kind") in exp["evidence_kinds_any"] for e in inv.get("evidence") or [])
    if "evidence_statement_regex" in exp: c["evidence_statement"] = any(re.search(exp["evidence_statement_regex"], e.get("statement") or "") for e in inv.get("evidence") or [])
    if "conclusion_regex" in exp: c["conclusion"] = bool(re.search(exp["conclusion_regex"], (a.get("conclusion") or "") + " " + (inv.get("message") or "")))
    if "conclusion_not_regex" in exp: c["conclusion_not"] = not re.search(exp["conclusion_not_regex"], (a.get("conclusion") or "") + " " + (inv.get("message") or ""))
    if "text_regex" in exp: c["text"] = bool(re.search(exp["text_regex"], _texts(inv)))
    if exp.get("no_tools_run"): c["no_tools_run"] = not tool_steps and b.get("tool_calls", 0) == 0
    if "no_team_values" in exp:
        leaks = _leaks(inv, exp["no_team_values"])
        c["no_team_values"] = not leaks
        if leaks: c["_leaks"] = leaks[:3]
    if exp.get("prior_evidence_stale_or_trace"):
        stale = [e for e in inv.get("evidence") or [] if e.get("id") in prev_ids and e.get("stale")]
        changed = any(re.search(r"(?i)context|changed|switch|out of date", (t.get("step") or "") + " " + (t.get("detail") or "")) for t in inv.get("trace") or [])
        c["prior_evidence_stale_or_trace"] = bool(stale) or changed
    if "max_tool_runs" in exp:
        for tool, n in exp["max_tool_runs"].items():
            c[f"runs_{tool}"] = sum(1 for t in tool_steps if t.get("tool") == tool) <= n
    if "trace_regex" in exp: c["trace"] = any(re.search(exp["trace_regex"], (t.get("step") or "") + " " + (t.get("detail") or "")) for t in inv.get("trace") or [])
    if exp.get("fallback_truthy"): c["fallback"] = bool(inv.get("fallback"))
    if "mode_in" in exp: c["mode"] = inv.get("mode") in exp["mode_in"]
    if exp.get("no_model_success_in_trace"):
        c["no_model_success"] = not any(t.get("mode") == "model" and not re.search(r"(?i)unavailable|fail|fallback|error", t.get("detail") or "") for t in inv.get("trace") or [])
    return c


def _passed(r) -> bool:
    """Normalise the self-check's return value: a dict with 'passed' (or 'problems'), a (passed, notes) tuple, a list of problems, or a bool."""
    if isinstance(r, dict):
        if "passed" in r: return bool(r["passed"])
        if "problems" in r: return not r["problems"]
        return bool(r.get("ok"))
    if isinstance(r, tuple) and r:
        return r[0] if isinstance(r[0], bool) else not r[0]
    if isinstance(r, list):
        return not r
    return bool(r)


def run_self_check(case, INV, mode, db, retriever) -> dict:
    s = case["self_check"]
    inv = _call(INV, s["setup"]["question"], s["setup"]["context"], None, "rules", db, retriever)
    evidence = inv.get("evidence") or []
    parts_out, ok_all = [], True
    for p in s["parts"]:
        if p.get("use_conclusion"):
            text, ids = (_answer(inv).get("conclusion") or ""), list(_answer(inv).get("evidence_ids") or [])
        elif "cite_ids" in p:
            text, ids = p["text"], p["cite_ids"]
        elif p.get("cite_kind"):
            text, ids = p["text"], [e["id"] for e in evidence if e.get("kind") == p["cite_kind"]][:1]
        else:
            text, ids = p["text"], []
        parts = [{"text": text, "evidence_ids": ids}]
        try:
            try:
                raw = INV.self_check(parts, evidence)
            except (TypeError, AttributeError, KeyError):
                evs = [INV.Ev(e["id"], e["kind"], e["statement"], e.get("tool", ""), e.get("turn", 1), e.get("sql"), e.get("rows") or [], e.get("source", ""), e.get("value") or {}, e.get("origin", "computed"), bool(e.get("stale"))) for e in evidence]
                raw = INV.self_check(parts, evs)
            got = _passed(raw)
            ok = got == p["expect_pass"]
            parts_out.append({"name": p["name"], "text": text, "evidence_ids": ids, "self_check_passed": got, "expected": p["expect_pass"], "ok": ok, "raw": str(raw)[:300]})
        except Exception as e:  # noqa: BLE001 - recorded as a failed part
            ok = False
            parts_out.append({"name": p["name"], "ok": False, "error": f"{type(e).__name__}: {e}"[:300]})
        ok_all &= ok
    return {"passed": ok_all, "parts": parts_out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-model", action="store_true")
    ap.add_argument("--label", default="seen during development (not a holdout)")
    args = ap.parse_args()
    sys.path.insert(0, str(HERE.parents[1]))
    config, INV, llm, db0, retriever = _setup(args.no_model)
    base_mode = "rules" if args.no_model or not config.has_key() else "auto"
    slug = "rules-only" if base_mode == "rules" else config.MODEL
    cases = json.loads((HERE / "cases.json").read_text())
    rows = []
    for case in cases:
        t0 = time.time()
        row = {"id": case["id"], "category": case["category"], "passed": False, "turns": []}
        db, undo = _inject(case, config, INV, llm, db0)
        try:
            if "self_check" in case:
                row.update(run_self_check(case, INV, base_mode, db, retriever))
            else:
                conv, prev_ids, ok_all = None, [], True
                for t in case["turns"]:
                    mode = t.get("mode", base_mode) if not args.no_model or not case.get("inject", {}).get("fake_model") else t.get("mode", base_mode)
                    ts = time.time()
                    inv = _call(INV, t["question"], t.get("context") or {}, conv, mode, db, retriever)
                    conv = inv.get("conversation_id") or conv
                    checks = check_turn(t["expect"], inv, prev_ids)
                    ok = all(v for k, v in checks.items() if not k.startswith("_"))
                    ok_all &= ok
                    row["turns"].append({"question": t["question"], "passed": ok, "checks": checks, "status": inv.get("status"),
                                         "function": (inv.get("function") or {}).get("id"), "evidence_state": _answer(inv).get("evidence_state"),
                                         "context_team": (inv.get("context") or {}).get("team"), "mode": inv.get("mode"), "fallback": inv.get("fallback"),
                                         "conclusion": (_answer(inv).get("conclusion") or inv.get("message") or "")[:300],
                                         "budget": inv.get("budget"), "seconds": round(time.time() - ts, 2)})
                    prev_ids = [e["id"] for e in inv.get("evidence") or []]
                row["passed"] = ok_all
        except Exception as e:  # noqa: BLE001 - a crash is a failed case, recorded
            row["error"] = f"{type(e).__name__}: {e}"[:400]
        finally:
            undo()
        row["seconds"] = round(time.time() - t0, 2)
        rows.append(row)
        fails = [f"{k}" for t in row.get("turns", []) for k, v in t["checks"].items() if not k.startswith("_") and not v] + \
                [p["name"] for p in row.get("parts", []) if not p.get("ok")] + ([row["error"]] if row.get("error") else [])
        print(f"{'PASS' if row['passed'] else 'FAIL'} {case['id']} {case['category'][:58]:<58} {'' if row['passed'] else '-> ' + '; '.join(fails)[:160]}  {row['seconds']}s")
    n = sum(r["passed"] for r in rows)
    out = {"pack": "investigate", "label": args.label, "model": slug, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "passed": n, "total": len(rows), "rows": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    for name in (f"{stamp}_{slug}.json", f"latest_{slug}.json"):
        (RESULTS / name).write_text(json.dumps(out, indent=2, default=str))
    first = RESULTS / f"first_run_{slug}.json"
    if not first.exists():
        first.write_text(json.dumps(out, indent=2, default=str))
    print(f"\ninvestigate ({args.label}) · {slug}: {n}/{len(rows)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
