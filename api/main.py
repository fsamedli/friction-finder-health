"""Friction Finder v0.6 API. Serves the React app from web/dist and a small set of typed endpoints.

The endpoints double as the tool set for the later tool-using "Ask" assistant: each one is a
deterministic function the model can call, and every number on screen comes from one of them.

Run:  .venv/bin/uvicorn api.main:app --port 8000
"""
from __future__ import annotations

import html
import io
import json
import re
import threading
import time
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import agent, config
from app import impact as I
from app.db import DB

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"

app = FastAPI(title="Friction Finder", version="0.6")

_state: dict = {"db": None, "retriever": None, "results": {}}


@app.on_event("startup")
def _warm() -> None:
    """Compute the cross-team associations once at startup (about 0.8 s cold), so the first click on
    Insights or Drivers during a demo is instant. Deterministic; no model call."""
    try:
        I.link_matrix()
    except Exception:  # never block startup on a warm-up
        pass


def _db() -> DB:
    if _state["db"] is None:
        _state["db"] = DB()
    return _state["db"]


def _retriever():
    if _state["retriever"] is None:  # lazy: building the index may call the embeddings API
        from app.retrieval import Retriever
        _state["retriever"] = Retriever(_db())
    return _state["retriever"]


def _jsonable(x):
    def default(o):
        if hasattr(o, "item"):
            return o.item()
        if isinstance(o, (pd.Timestamp, date)):
            return o.isoformat()
        return str(o)
    def clean(o):  # NaN (suppressed cells) -> null; JSON has no NaN
        if isinstance(o, float) and not np.isfinite(o):
            return None
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    return clean(json.loads(json.dumps(x, default=default)))


def _costs() -> dict:
    return I.default_costs()


def _check_as_of(as_of: str) -> str:
    try:
        date.fromisoformat(as_of)
    except ValueError:
        raise HTTPException(422, "as_of must be YYYY-MM-DD")
    return as_of


# ------------------------------------------------------------------ meta
@app.get("/api/meta")
def meta():
    sites = pd.read_csv(config.DATA_DIR / "sites.csv")
    return {"company": "Lanford Health (fictional)",
            "sites": sites.to_dict("records"),
            "as_of_presets": [{"value": I.AS_OF_DETECT, "label": "Sept 15, 2026", "hint": "Wave 2 results are in"},
                              {"value": I.AS_OF_REVIEW, "label": "Nov 30, 2026", "hint": "Plan review date"}],
            "kpis": I.KPI_LABELS, "items": I.item_labels(), "min_n": config.MIN_N,
            "model": config.MODEL if config.has_key() else None}


# ------------------------------------------------------------------ detect / explain
@app.get("/api/board")
def board(site_id: int = 1, as_of: str = I.AS_OF_DETECT):
    return _jsonable(I.board(site_id, _check_as_of(as_of), _costs()))


@app.get("/api/why/{team_id}")
def why(team_id: int, as_of: str = I.AS_OF_DETECT):
    try:
        return _jsonable(I.why(team_id, _check_as_of(as_of), _costs()))
    except IndexError:
        raise HTTPException(404, "unknown team")


@app.get("/api/link")
def link(kpi: str = "late_doses", item: str = "q02"):
    if kpi not in I.KPIS or item not in I.item_labels():
        raise HTTPException(422, "unknown kpi or item")
    return _jsonable({"quartile": I.quartile_link(kpi, item), "association": I.association(kpi, item)})


@app.get("/api/links")
def links():
    return _jsonable(I.link_matrix())


# ------------------------------------------------------------------ act
class Action(BaseModel):
    text: str = Field(min_length=3)
    owner: str = ""                       # blank = assigned at approval (ownership directory, else the team manager)
    due: str
    # Oct 27 round: the plan is a checklist the manager runs
    id: str | None = None
    status: str = Field(default="todo", pattern="^(todo|done|blocked)$")
    done_at: str | None = None


class PlanIn(BaseModel):
    team_id: int
    item: str
    kpi: str = "late_doses"
    obstacle: str = ""
    focus: str = ""
    actions: list[Action] = Field(min_length=1)
    start: str
    review: str | None = None
    status: str = Field(default="approved", pattern="^(draft|approved)$")
    note: str = ""
    # v0.8: the thinnest plan the review needs, plus where it came from and what the manager changed
    owner: str | None = None
    measure: str | None = None
    baseline: str | None = None
    success: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    finding: str | None = None
    rationale: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    investigation_id: str | None = None
    request_id: str | None = Field(default=None, max_length=80)
    edits: list[dict] = Field(default_factory=list)


def _default_review(start: date) -> date:
    """Operating data is monthly, so a review needs two complete months after the plan starts:
    the review date is the last day of the second full month after the start (Sept 21 -> Nov 30)."""
    y, m = start.year, start.month + 3  # first day of the month after the second full month
    y, m = (y + 1, m - 12) if m > 12 else (y, m)
    return date(y, m, 1) - timedelta(days=1)


@app.get("/api/plans")
def plans():
    teams = pd.read_csv(config.DATA_DIR / "teams.csv").merge(pd.read_csv(config.DATA_DIR / "sites.csv"), on="site_id")
    label = {int(t.team_id): f"{t.site_name} {t.team_name}" for t in teams.itertuples()}
    return [_with_progress({**_norm_plan(p), "team_label": label.get(int(p["team_id"]), "")}) for p in I.load_plans()]


SEED_PLAN_ID = "plan-lanford-med-surg-night"


def _same_issue(team_id: int, kpi: str, start: str, review: str | None = None) -> list[dict]:
    """Approved plans on the same team and KPI whose start-to-review period overlaps this one. The seeded demo plan
    is a fallback the app hides as soon as a plan is approved live, so it never blocks one."""
    s0 = date.fromisoformat(start)
    r0 = date.fromisoformat(review) if review else _default_review(s0)
    out = []
    for x in I.load_plans():
        if x["id"] == SEED_PLAN_ID or x.get("status") != "approved" or int(x["team_id"]) != int(team_id) or x.get("kpi", "late_doses") != kpi:
            continue
        if date.fromisoformat(x["start"]) <= r0 and date.fromisoformat(x["review"]) >= s0:
            out.append(x)
    return out


_plan_lock = threading.Lock()


@app.post("/api/plans")
def create_plan(p: PlanIn):
    """Save a draft or an approved plan. Approval is the manager's: this records it with the edits and the time.
    A repeated request_id, or an approved plan already covering the same team, KPI and period, returns that plan
    with an explanation instead of a second copy (a 200, so a double click is never an error)."""
    if p.kpi not in I.KPIS:
        raise HTTPException(422, "unknown kpi")
    start = date.fromisoformat(p.start)
    with _plan_lock:
        if p.request_id:
            prior = next((x for x in I.load_plans() if x.get("request_id") == p.request_id), None)
            if prior:
                return {**prior, "duplicate": True, "explanation": "This approval was already recorded (same request); no second plan was created."}
        if p.status == "approved":
            same = _same_issue(p.team_id, p.kpi, p.start, p.review)
            if same:
                x = same[-1]
                return {**x, "duplicate": True, "explanation": f"An approved plan already covers this team and KPI from {x['start']} to {x['review']} ({x['id']}); no second plan was created."}
        plan = p.model_dump()
        plan["review"] = p.review or _default_review(start).isoformat()
        plan["id"] = f"plan-{uuid.uuid4().hex[:8]}"
        plan["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        plan = _norm_plan(plan)
        if p.status == "approved":
            plan["decided_at"] = plan["created_at"]
            plan["execution"] = _execute(plan)
        saved = I.save_plan(plan)
        if p.status == "approved":
            _record_plan_decision(saved, "approved", p.edits)
            _redraft_notices_async(saved["id"])
        return _with_progress(saved)


@app.get("/api/plans/check")
def plan_check(team_id: int, kpi: str = "late_doses", start: str = "2026-09-21"):
    """Before approval: is there already an approved plan on the same team, KPI and period? Explained in words."""
    if kpi not in I.KPIS:
        raise HTTPException(422, "unknown kpi")
    try:
        same = _same_issue(team_id, kpi, start)
    except ValueError:
        raise HTTPException(422, "start must be YYYY-MM-DD")
    label = {int(r["team_id"]): r["label"] for r in _team_labels()}
    rows = [{**x, "team_label": label.get(int(x["team_id"]), "")} for x in same]
    review = _default_review(date.fromisoformat(start)).isoformat()
    expl = (f"Checked approved plans for this team on {I.KPI_LABELS[kpi].lower()} between {start} and {review}: "
            + (f"{len(rows)} already cover this period. Approving again would not create a second plan." if rows else "none found."))
    return {"existing": rows, "explanation": expl}


def _team_labels() -> list[dict]:
    teams = pd.read_csv(config.DATA_DIR / "teams.csv").merge(pd.read_csv(config.DATA_DIR / "sites.csv"), on="site_id")
    return [{"team_id": int(t.team_id), "label": f"{t.site_name} {t.team_name}"} for t in teams.itertuples()]


def _visible(plans: list[dict], as_of: str) -> list[dict]:
    """Same rule as the web app (visiblePlans): approved plans; the seeded plan only once the clock passes its start
    and only when no plan for that team was approved live."""
    live = [p for p in plans if p["id"] != SEED_PLAN_ID and p.get("status") == "approved"]
    return [p for p in plans if p.get("status") == "approved"
            and (p["id"] != SEED_PLAN_ID or (as_of >= p["start"] and not any(int(l["team_id"]) == int(p["team_id"]) for l in live)))]


@app.get("/api/plans/board")
def plans_board(as_of: str = I.AS_OF_DETECT):
    """Plans with a state (draft, approved, in review, reviewed) and the review queue, for the Action plans screen.
    in_review = the review date has passed but the follow-up months are not complete; reviewed = the computed result exists."""
    _check_as_of(as_of)
    all_ = I.load_plans()
    label = {r["team_id"]: r["label"] for r in _team_labels()}
    rows = []
    for p in _visible(all_, as_of) + [x for x in all_ if x.get("status") == "draft"]:
        r = None if p.get("status") == "draft" else _jsonable(I.did_all(p, as_of, _costs())[0])
        state = ("draft" if p.get("status") == "draft" else "approved" if (r is None or r["status"] == "not_reached")
                 else "in_review" if r["status"] == "insufficient" else "reviewed")
        rows.append(_with_progress({**_norm_plan(p), "team_label": label.get(int(p["team_id"]), ""), "state": state, "result": r}))
    return {"plans": rows, "queue": {
        "due_reviews": [p["id"] for p in rows if p["state"] in ("in_review", "reviewed")],
        "missing_follow_ups": [p["id"] for p in rows if p["state"] == "in_review"],
        "inconclusive": [p["id"] for p in rows if (p["result"] or {}).get("status") == "ok" and p["result"].get("verdict") == "inconclusive"]}}


class ApprovePlanIn(BaseModel):
    request_id: str = Field(min_length=1, max_length=80)
    edits: list[dict] = Field(default_factory=list)


@app.post("/api/plans/{plan_id}/approve")
def approve_plan(plan_id: str, a: ApprovePlanIn):
    """Approve a saved draft. Idempotent on request_id; an overlapping approved plan is explained, not duplicated."""
    with _plan_lock:
        plan = next((x for x in I.load_plans() if x["id"] == plan_id), None)
        if not plan:
            raise HTTPException(404, "unknown plan")
        if plan.get("status") == "approved":
            return {**plan, "duplicate": True, "explanation": "This plan is already approved; nothing changed."}
        same = _same_issue(int(plan["team_id"]), plan.get("kpi", "late_doses"), plan["start"], plan["review"])
        if same:
            x = same[-1]
            return {**x, "duplicate": True, "explanation": f"An approved plan already covers this team and KPI from {x['start']} to {x['review']} ({x['id']}); the draft was not approved."}
        new = _norm_plan({**plan, "status": "approved", "request_id": a.request_id, "edits": list(plan.get("edits", [])) + a.edits,
                          "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        new["execution"] = _execute(new)
        I.save_plan(new)   # load_plans keeps the last line per id
        _record_plan_decision(new, "approved", a.edits)
        _redraft_notices_async(new["id"])
        return _with_progress(new)


def _record_plan_decision(plan: dict, decision: str, edits: list[dict]) -> None:
    """approvals.jsonl gets the person's decision on a plan: what was approved, what they changed, when."""
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "who": "manager", "target": "plan", "decision": decision,
           "plan_id": plan["id"], "team_id": plan["team_id"], "kpi": plan.get("kpi"), "start": plan["start"], "review": plan["review"],
           "edits": edits, "investigation_id": plan.get("investigation_id"), "evidence_ids": plan.get("evidence_ids", [])}
    with open(config.APPROVALS_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------------ the plan as a checklist (Oct 27, 2026 round)
# Prof. Hall, Oct 21: "turn the plan into a checklist with tasks, responsible people, and due dates", and show what happens
# after approval. Old plans (the seeded one, v0.7 and v0.8 records) have no ids or statuses: they are added on read.

def _norm_plan(p: dict) -> dict:
    out = dict(p)
    acts = []
    for i, a in enumerate(out.get("actions", [])):
        acts.append({**a, "id": a.get("id") or f"a{i + 1}", "status": a.get("status") or "todo", "done_at": a.get("done_at")})
    out["actions"] = acts
    out.setdefault("execution", None)
    return out


def _with_progress(p: dict) -> dict:
    acts = p.get("actions", [])
    return {**p, "progress": {"done": sum(1 for a in acts if a.get("status") == "done"), "total": len(acts)}}


def _team_ctx(team_id: int) -> tuple[dict, str, dict]:
    """(team info, team manager name, {role: name} for the site plus the system-wide roles)."""
    from app import relations as R
    team = R.team_info(int(team_id))
    t = pd.read_csv(config.DATA_DIR / "teams.csv")
    manager = str(t[t.team_id == int(team_id)].iloc[0].manager_name)
    d = pd.read_csv(config.DATA_DIR / "ownership_directory.csv")
    rows = d[(d.site_name == team["site"]) | (d.site_name == "ALL")].sort_values("site_name", key=lambda s_: s_ == "ALL")
    owners = {}
    for r in rows.itertuples():
        owners.setdefault(r.owner_role, r.owner_name)
    return team, manager, owners


def _execute(plan: dict, derived: bool = False) -> dict:
    """What the system does once a person has approved: assign owners, schedule the review, set the KPI watch, draft the
    notices. Code only; nothing is sent. `derived` marks a record built on read for a plan approved before this existed."""
    team, manager, owners = _team_ctx(int(plan["team_id"]))
    rec = agent.execution_record(plan, team, manager, owners, I.KPI_LABELS.get(plan.get("kpi", "late_doses"), plan.get("kpi", "")))
    if derived:
        rec["derived"] = True
        rec["note"] = "Derived from the plan as saved (approved before the execution record existed). Nothing was sent."
    elif config.has_key():
        rec["notices_status"] = "drafting"   # the model rewords the templated notices in the background; see _redraft_notices_async
    return rec


def _redraft_notices_async(plan_id: str) -> None:
    """Model mode only: approval stays instant (templated notices); a background thread asks the model to reword them from
    the plan facts and keeps the result only if the check passes."""
    if not config.has_key():
        return

    def work():
        try:
            plan = next((x for x in I.load_plans() if x["id"] == plan_id), None)
            if not plan or not plan.get("execution"):
                return
            team, manager, _ = _team_ctx(int(plan["team_id"]))
            notices, notes = agent.draft_notices_llm(plan, team, manager, I.KPI_LABELS.get(plan.get("kpi", "late_doses"), ""))
            with _plan_lock:
                cur = next((x for x in I.load_plans() if x["id"] == plan_id), None)
                if not cur or not cur.get("execution"):
                    return
                ex = dict(cur["execution"])
                if notices:
                    ex["notices"], ex["mode"] = notices, "model"
                ex["notices_status"], ex["notice_notes"] = "ready", notes
                I.save_plan({**cur, "execution": ex})
        except Exception as e:  # never let a background rewrite break anything the manager sees
            try:
                with _plan_lock:
                    cur = next((x for x in I.load_plans() if x["id"] == plan_id), None)
                    if cur and cur.get("execution"):
                        I.save_plan({**cur, "execution": {**cur["execution"], "notices_status": "ready", "notice_notes": [f"model rewrite skipped ({type(e).__name__})"]}})
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()


def _record_action_event(plan: dict, action: dict, changes: dict, event: str) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "who": "manager", "target": "action", "decision": event,
           "plan_id": plan["id"], "team_id": plan["team_id"], "action_id": action.get("id"), "changes": changes}
    with open(config.APPROVALS_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _plan_or_404(plan_id: str) -> dict:
    plan = next((x for x in I.load_plans() if x["id"] == plan_id), None)
    if not plan:
        raise HTTPException(404, "unknown plan")
    return _norm_plan(plan)


def _plan_view(plan: dict) -> dict:
    label = {r["team_id"]: r["label"] for r in _team_labels()}
    out = {**plan, "team_label": label.get(int(plan["team_id"]), "")}
    if out.get("status") == "approved" and not out.get("execution"):
        out["execution"] = _execute(out, derived=True)
    return _with_progress(out)


class ActionPatch(BaseModel):
    text: str | None = Field(default=None, min_length=3)
    owner: str | None = None
    due: str | None = None
    status: str | None = Field(default=None, pattern="^(todo|done|blocked)$")


@app.get("/api/plans/{plan_id}")
def get_plan(plan_id: str):
    """One plan as a checklist, with what happened at approval (owners, review date, KPI watch, draft notices)."""
    return _plan_view(_plan_or_404(plan_id))


@app.patch("/api/plans/{plan_id}/actions/{action_id}")
def patch_action(plan_id: str, action_id: str, a: ActionPatch):
    """Tick, untick, block or edit one task. Every change is recorded with the time (approvals.jsonl, target 'action')."""
    with _plan_lock:
        plan = _plan_or_404(plan_id)
        act = next((x for x in plan["actions"] if x["id"] == action_id), None)
        if not act:
            raise HTTPException(404, "unknown action")
        changes = {k: v for k, v in a.model_dump().items() if v is not None and v != act.get(k)}
        if not changes:
            return _plan_view(plan)
        if "due" in changes:
            try:
                date.fromisoformat(changes["due"])
            except ValueError:
                raise HTTPException(422, "due must be YYYY-MM-DD")
        act.update(changes)
        if "status" in changes:
            act["done_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds") if changes["status"] == "done" else None
        I.save_plan(plan)
        _record_action_event(plan, act, changes, "updated")
        return _plan_view(plan)


@app.post("/api/plans/{plan_id}/actions")
def add_action(plan_id: str, a: Action):
    """Add a task to an approved plan's checklist (owner defaults to the plan owner, then the team manager)."""
    with _plan_lock:
        plan = _plan_or_404(plan_id)
        try:
            date.fromisoformat(a.due)
        except ValueError:
            raise HTTPException(422, "due must be YYYY-MM-DD")
        n = 1 + max([int(x["id"][1:]) for x in plan["actions"] if re.fullmatch(r"a\d+", x["id"] or "")] + [len(plan["actions"])])
        owner = a.owner.strip() or plan.get("owner") or f"{_team_ctx(int(plan['team_id']))[1]}, nurse manager"
        act = {"id": f"a{n}", "text": a.text, "owner": owner, "due": a.due, "status": a.status, "done_at": None}
        plan["actions"].append(act)
        if plan.get("execution"):
            plan["execution"] = {**plan["execution"], "assigned": list(plan["execution"].get("assigned", [])) + [{"action_id": act["id"], "owner": owner, "source": "manager"}]}
        I.save_plan(plan)
        _record_action_event(plan, act, {"added": act["text"]}, "added")
        return _plan_view(plan)


class RegenerateIn(BaseModel):
    team_id: int
    obstacle: str = Field(min_length=3)
    kpi: str = "late_doses"
    start: str = "2026-09-21"


@app.post("/api/plans/regenerate")
def regenerate_plan(r: RegenerateIn):
    """The 'edit and regenerate' half of the loop: new actions drafted from the obstacle the manager typed. The owner comes
    from the ownership directory for the theme named; rules mode uses the action bank; model mode rewords within checks."""
    if r.kpi not in I.KPIS:
        raise HTTPException(422, "unknown kpi")
    try:
        date.fromisoformat(r.start)
    except ValueError:
        raise HTTPException(422, "start must be YYYY-MM-DD")
    team, manager, owners = _team_ctx(r.team_id)
    return agent.regenerate_actions(r.obstacle, team, manager, owners, r.start, I.KPI_LABELS.get(r.kpi, r.kpi))


@app.delete("/api/demo")
def reset_demo():
    """Between rehearsals: remove plans created in the app, edited unit costs and uploaded operating data."""
    for name in ("plans.jsonl", "costs.json", "team_ops_upload.csv"):
        (config.CACHE_DIR / name).unlink(missing_ok=True)
    I.reload()
    return {"ok": True}


@app.get("/api/ops-upload")
def ops_upload_status():
    p = I.upload_path()
    if not p.exists():
        return {"active": False}
    df = pd.read_csv(p)
    return {"active": True, "rows": int(len(df)), "teams": int(df.team_id.nunique()), "months": sorted(df.month.unique().tolist())}


@app.get("/api/ops-upload/template", response_class=PlainTextResponse)
def ops_upload_template():
    """Template = the real demo rows for Lanford Med-Surg Night, so the columns and scale are clear."""
    ops = pd.read_csv(config.DATA_DIR / "team_ops_monthly.csv")
    rows = ops[ops.team_id == 4][I.UPLOAD_COLUMNS]
    return PlainTextResponse(rows.to_csv(index=False), headers={"Content-Disposition": "attachment; filename=team_ops_template.csv"})


@app.post("/api/ops-upload")
async def ops_upload(file: UploadFile):
    try:
        df = pd.read_csv(io.BytesIO(await file.read()))
    except Exception as e:
        raise HTTPException(422, f"Could not read that file as CSV: {e}")
    clean, problems = I.validate_upload(df)
    if problems:
        raise HTTPException(422, {"problems": problems})
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(I.upload_path(), index=False)
    I.reload()
    return {**ops_upload_status(), "message": f"{len(clean)} team-months loaded. They replace the demo rows for the same teams and months."}


@app.delete("/api/ops-upload")
def ops_upload_clear():
    I.upload_path().unlink(missing_ok=True)
    I.reload()
    return {"active": False}


@app.get("/api/plans/{plan_id}/result")
def plan_result(plan_id: str, as_of: str = I.AS_OF_REVIEW):
    plan = next((p for p in I.load_plans() if p["id"] == plan_id), None)
    if not plan:
        raise HTTPException(404, "unknown plan")
    as_of = _check_as_of(as_of)
    costs = _costs()
    res = I.did_all(plan, as_of, costs)
    # value: the three labelled tiers (measured / projected / hospital scenario); None before the result exists
    return _jsonable({**res[0], "also": res[1:], "value": I.value_of_plan(plan, as_of, costs, res)})


# ------------------------------------------------------------------ business case
@app.get("/api/costs")
def costs():
    return _costs()


@app.put("/api/costs")
def put_costs(update: dict):
    try:
        clean = I.validate_costs(update)
    except ValueError as e:
        raise HTTPException(422, str(e))
    path = config.CACHE_DIR / "costs.json"
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cur = json.loads(path.read_text()) if path.exists() else {}
    cur.update(clean)
    path.write_text(json.dumps(cur))
    return _costs()


@app.delete("/api/costs")
def reset_costs():
    (config.CACHE_DIR / "costs.json").unlink(missing_ok=True)
    return _costs()


@app.get("/api/value")
def value(headcount: int = 300):
    """The business case plus, when the research file exists, comparable-software price benchmarks (each row carries its
    source URL and retrieval date; nothing is typed into the app)."""
    out = I.value_case(_costs(), headcount)
    bm = ROOT / "data" / "docs" / "pricing_benchmarks.json"
    rows = None
    if bm.exists():
        try:
            rows = json.loads(bm.read_text())
            rows = rows if isinstance(rows, list) else rows.get("benchmarks")
        except (ValueError, AttributeError):
            rows = None
    return {**out, "benchmarks": rows, "benchmarks_note": None if rows else "Benchmark research in progress (Oct 27, 2026): prices of comparable hospital operations software, each with its source, will be listed here."}


# ------------------------------------------------------------------ data sources
@app.get("/api/sources")
def sources():
    d = config.DATA_DIR
    resp = pd.read_csv(d / "responses.csv")
    ops = pd.read_csv(d / "ops_daily.csv")
    tom = pd.read_csv(d / "team_ops_monthly.csv")
    com = pd.read_csv(d / "comments.csv")
    docs = sorted(p.name for p in config.DOCS_DIR.glob("*")) if config.DOCS_DIR.exists() else []
    up = _state["db"].uploaded_ops_rows if _state["db"] else 0
    demo = "demo_csv"  # nothing is connected to a live system; every source here is a synthetic CSV
    return [
        {"id": "survey", "name": "Engagement survey export", "vendor": "Would come from: a Gallup Access export (Q12-style CSV)", "owner": "HR / People analytics",
         "status": demo, "method": "CSV per survey wave", "rows": int(len(resp)), "detail": f"{resp.wave_id.nunique()} waves · {resp.team_id.nunique()} teams · respondent rows stay inside the database",
         "last": "2026-09-10"},
        {"id": "comments", "name": "Survey comments", "vendor": "Would come from: the same Gallup Access export (open text)", "owner": "HR / People analytics",
         "status": demo, "method": "CSV per survey wave", "rows": int(len(com)), "detail": "Indexed for retrieval; teams under 4 respondents never indexed", "last": "2026-09-10"},
        {"id": "timekeeping", "name": "Timekeeping & attendance", "vendor": "Would connect to, e.g., UKG / Kronos", "owner": "Nursing administration / timekeeping",
         "status": demo, "method": "Monthly CSV (unit template)", "rows": int(len(tom)), "detail": "Sick calls, overtime shifts and late doses by unit-month (one template with separations and staff injuries)", "last": "2026-11-30"},
        {"id": "safety", "name": "Employee health / safety log", "vendor": "Would connect to, e.g., the employee health or OSHA 300 log", "owner": "Employee health",
         "status": demo, "method": "Monthly CSV (same unit template)", "rows": int(len(tom)), "detail": "Staff injury cases with days away (patient handling, sharps) by unit-month; no patient-level data", "last": "2026-11-30"},
        {"id": "emar", "name": "eMAR / barcode medication administration", "vendor": "Would connect to, e.g., Epic, Oracle Health", "owner": "Pharmacy and nursing informatics",
         "status": demo, "method": "Daily CSV by shift and hour band (counts only, no patient records)", "rows": int(len(ops)) + int(up), "detail": f"Scheduled, late and missed doses by hour band{f' · {up} rows uploaded this session' if up else ''}", "last": "2026-09-10"},
        {"id": "docs", "name": "Procedures & ownership directory", "vendor": "Would connect to, e.g., a SharePoint policy library", "owner": "Nursing administration",
         "status": demo, "method": "Document folder", "rows": len(docs), "detail": ", ".join(docs[:4]), "last": "2026-09-01"},
        {"id": "hris", "name": "HRIS (separations, tenure bands)", "vendor": "Would connect to, e.g., Workday", "owner": "HR",
         "status": "not_connected", "method": "Not used in the demo", "rows": 0, "detail": "Voluntary separations arrive on the unit template; tenure bands come with the survey export in this demo", "last": None},
    ]


# ------------------------------------------------------------------ under the hood
@app.get("/api/assumptions")
def assumptions():
    teams = pd.read_csv(config.DATA_DIR / "teams.csv")
    resp = pd.read_csv(config.DATA_DIR / "responses.csv")
    emp = pd.read_csv(config.DATA_DIR / "employees.csv")
    ops = pd.read_csv(config.DATA_DIR / "team_ops_monthly.csv")
    rate = resp.groupby("wave_id").size() / len(emp)
    return {"rows": [
        {"k": "Company", "v": "Lanford Health, fictional: 3 hospitals, 24 nursing and support units, 189 staff", "why": "Small enough to inspect by hand; big enough to show suppression and site-level inference."},
        {"k": "Survey", "v": f"12-item, 1-5 scale, 2 waves (Mar 15 and Sep 10, 2026); {len(resp)} responses", "why": "Shaped like Gallup's Q12; the items themselves are paraphrased."},
        {"k": "Response rate", "v": f"{rate.get(1, 0):.0%} wave 1, {rate.get(2, 0):.0%} wave 2", "why": "Typical of an engaged client; the real rate must come from Gallup."},
        {"k": "Minimum n", "v": f"{config.MIN_N} respondents per team-wave; teams under {config.MIN_N} people show no team numbers", "why": "Gallup's reporting threshold (Keegan, Sept 14). Applied in SQL and code, before any model call."},
        {"k": "Operating data", "v": f"{len(ops)} unit-months (Jan-Nov 2026): sick calls, late doses, separations, staff injuries, overtime shifts. Counts only; no patient-level data", "why": "Comes from the client (timekeeping, eMAR, HRIS), never from Gallup (Keegan, Sept 18)."},
        {"k": "First-year effect", "v": "New hires score about 0.35 points higher; the signal check adjusts for who responded", "why": "A drop can be a change in who answered, not in how people feel."},
        {"k": "Follow-up months", "v": "Oct-Nov 2026 are synthetic, planted so the plan's effect can be tested", "why": "Real follow-up needs a pilot; the method is what we are showing."},
        {"k": "Inference level", "v": "Team results are screening signals; associations use 34 team-waves; nothing here is causal", "why": "24 teams x 2 waves is small. We say so on screen."},
        {"k": "External benchmark", "v": "Assumed data source: Gallup's database norms for similar roles or industries. Unavailable in the demo; the app shows 'unavailable' and computes only an internal norm (comparable teams)", "why": "Class, Oct 8: stating benchmark access as an assumption is acceptable. With a client's Access export it would be read from the export, never estimated."},
        {"k": "Follow-up pulse", "v": "Assumed: a pilot adds a two-month follow-up pulse on the plan's focus item. Not in the demo data", "why": "Class, Oct 8: a two-month follow-up survey may be assumed if stated. The demo's review uses operating data only."},
    ], "with_real_data": ["Response counts and rates from Gallup Access exports", "The client's own cost per late dose and per absence day",
                          "Team-to-cost-center mapping from the client's timekeeping system", "12+ months of history for rare events (quits, injuries)"]}


@app.get("/api/evals/latest")
def evals_latest():
    res = sorted((ROOT / "evals" / "results").glob("latest_*.json"))
    out = []
    for p in res:
        d = json.loads(p.read_text())
        out.append({"file": p.name, "model": d.get("model"), "passed": d.get("passed"), "total": d.get("total"),
                    "matrix": d.get("matrix"), "ts": d.get("ts"),
                    "rows": [{k: r.get(k) for k in ("id", "class", "question", "status", "verdict", "passed", "outcome")} for r in d.get("rows", [])]})
    return out


def _pct(xs: list[float], q: float) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 2)


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@app.get("/api/quality")
def quality():
    """Every number here is read from a saved result file; the file name and run date travel with it."""
    ev = ROOT / "evals"
    def summ(d: dict | None, path: Path) -> dict | None:
        if not d:
            return None
        return {"file": str(path.relative_to(ROOT)), "ts": d.get("ts"), "model": d.get("model"), "passed": d.get("passed"), "total": d.get("total")}
    packs = []
    # gold: first run = the earliest saved file for that mode
    for mode in ("rules-only", "gpt-5-mini"):
        files = sorted(p for p in (ev / "results").glob(f"*_{mode}.json") if not p.name.startswith("latest"))
        latest = ev / "results" / f"latest_{mode}.json"
        if files:
            packs.append({"pack": "Gold questions", "note": "written by the builder, planted answers", "mode": mode,
                          "first": summ(_load(files[0]), files[0]), "now": summ(_load(latest), latest)})
    for mode in ("rules-only", "gpt-5-mini"):
        first, latest = ev / "adversarial" / "results" / f"first_run_{mode}.json", ev / "adversarial" / "results" / f"latest_{mode}.json"
        if first.exists():
            packs.append({"pack": "Adversarial", "note": "seen during development, not a holdout", "mode": mode,
                          "first": summ(_load(first), first), "now": summ(_load(latest), latest)})
    for mode in ("rules-only", "gpt-5-mini"):   # v0.8 investigation pack (evals/investigate/)
        first, latest = ev / "investigate" / "results" / f"first_run_{mode}.json", ev / "investigate" / "results" / f"latest_{mode}.json"
        if first.exists():
            packs.append({"pack": "Investigation", "note": "multi-turn and fault-injected cases; seen during development, not a holdout", "mode": mode,
                          "first": summ(_load(first), first), "now": summ(_load(latest), latest)})
    hq = ev / "holdout" / "questions.json"
    hold = []
    for mode in ("rules-only", "gpt-5-mini"):
        first, latest = ev / "holdout" / "results" / f"first_run_{mode}.json", ev / "holdout" / "results" / f"latest_{mode}.json"
        if first.exists():
            hold.append({"pack": "Holdout", "note": "written by a teammate who has not seen the answers", "mode": mode,
                         "first": summ(_load(first), first), "now": summ(_load(latest), latest)})
    packs += hold or [{"pack": "Holdout", "note": "pending: " + ("questions written, not run yet" if hq.exists() else "no questions yet (evals/holdout/README.md)"),
                       "mode": None, "first": None, "now": None}]
    # decline accuracy: cases that should decline, suppress or say 'insufficient'
    declines = []
    for path in [ev / "results" / "latest_rules-only.json", ev / "adversarial" / "results" / "latest_rules-only.json"]:
        d = _load(path)
        if not d:
            continue
        if "matrix" in d:
            neg = [r for r in d["rows"] if r.get("class") == "negative"]
        else:
            neg = [r for r in d["rows"] if any(k in r["checks"] for k in ("status_in", "verdict_in", "owner_not_assigned", "no_team_values"))]
        declines.append({"file": str(path.relative_to(ROOT)), "ts": d.get("ts"), "correct": sum(r["passed"] for r in neg), "total": len(neg)})
    # numbers checked against the evidence: the model-written briefs saved tonight (prepared answers)
    prep = _load(PREPARED_PATH) or {}
    g = [v["response"].get("grounding", {}) for v in prep.values()]
    grounding = {"file": str(PREPARED_PATH.relative_to(ROOT)), "briefs": len(g), "checked": sum(x.get("checked", 0) for x in g),
                 "total": sum(x.get("total", 0) for x in g), "generated": sorted(v["generated_at"] for v in prep.values())[:1]} if prep else None
    # latency per question, from the latest saved runs
    lat = []
    for mode in ("rules-only", "gpt-5-mini"):
        secs, files = [], []
        for path in [ev / "results" / f"latest_{mode}.json", ev / "adversarial" / "results" / f"latest_{mode}.json"]:
            d = _load(path)
            if d:
                secs += [r.get("seconds") for r in d["rows"]]
                files.append(str(path.relative_to(ROOT)))
        if secs:
            lat.append({"mode": mode, "n": len(secs), "p50": _pct(secs, 0.5), "p95": _pct(secs, 0.95), "files": files})
    fb_path = FEEDBACK_PATH
    fb = [json.loads(l) for l in fb_path.read_text().splitlines() if l.strip()] if fb_path.exists() else []
    feedback = {"file": str(fb_path.name), "total": len(fb), "useful": sum(1 for x in fb if x.get("useful")),
                "not_useful": sum(1 for x in fb if not x.get("useful")),
                "reasons": {r: sum(1 for x in fb if x.get("reason") == r) for r in sorted({x.get("reason") for x in fb if x.get("reason")})},
                # v0.8: answers in the investigation panel, every reason listed from zero
                "investigation": {"total": sum(1 for x in fb if x.get("target") == "investigation"),
                                  "by_reason": {r: sum(1 for x in fb if x.get("target") == "investigation" and x.get("reason") == r) for r in FEEDBACK_REASONS}},
                "note": "Approvals are never evidence that an answer was correct: a person approves an action, not the analysis behind it."}
    return {"packs": packs, "declines": declines, "grounding": grounding, "latency": lat, "feedback": feedback}


FEEDBACK_PATH = config.APPROVALS_PATH.parent / "feedback.jsonl"


FEEDBACK_REASONS = ["wrong context", "not actionable", "missing evidence", "wrong number", "wrong owner", "other"]


class FeedbackIn(BaseModel):
    target: str = Field(pattern="^(ask|plan|investigation)$")
    target_id: str = Field(min_length=1, max_length=80)
    useful: bool
    reason: str | None = Field(default=None, pattern="^(wrong context|not actionable|missing evidence|wrong number|wrong owner|other)$")
    note: str = Field(default="", max_length=500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=60)


@app.post("/api/useful")
def post_feedback(f: FeedbackIn):
    """'Useful? yes / no' on an Ask brief or a plan, and 'what was wrong' on an investigation answer (with the evidence
    ids it cited). Appended next to approvals.jsonl; starts empty. evals/from_feedback.py turns rows into draft cases."""
    if not f.useful and not f.reason:
        raise HTTPException(422, "say why it was not useful")
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **f.model_dump()}
    with open(FEEDBACK_PATH, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


STUDY_PATH = config.APPROVALS_PATH.parent / "study.jsonl"


class StudyIn(BaseModel):
    participant: str = Field(pattern=r"^P\d{1,3}$")
    event: str = Field(pattern="^(task_start|task_finish|sus)$")
    task: int | None = Field(default=None, ge=1, le=3)
    success: bool | None = None
    answers: list[int] | None = None       # SUS: 10 answers, 1..5
    open_answers: list[str] | None = None  # the 2 open questions


@app.post("/api/study")
def study(e: StudyIn):
    """Usability study log (docs/usability/). Only written when a session runs with ?study=1; starts empty."""
    if e.event == "sus" and (not e.answers or len(e.answers) != 10 or any(a < 1 or a > 5 for a in e.answers)):
        raise HTTPException(422, "SUS needs 10 answers from 1 to 5")
    if e.event.startswith("task") and e.task is None:
        raise HTTPException(422, "task number required")
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **e.model_dump(exclude_none=True)}
    with open(STUDY_PATH, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


FEEDBACK = [
    {"who": "O'Neal Keegan, Gallup", "when": "Sept 18", "said": "Access shows what moved; what we don't have is comparisons to business operations. Action planning breaks down because managers are busy.", "changed": "Why page links engagement to the client's operating data; the plan is one card, one click."},
    {"who": "Taher Jamshidi, Promontory AI", "when": "Sept 18", "said": "Start from the KPIs the site manager cares about, one signal; show pricing and a feedback loop.", "changed": "Site board opens on operating KPIs in dollars; Business case page; approve/flag log."},
    {"who": "Katie Fullowan, Freddie Mac", "when": "Sept 14 & 18", "said": "Show the human in the loop and spot-checks with numbers; state assumptions up front.", "changed": "Approve/reject/flag log; Under the hood opens with assumptions; every number has 'how computed'."},
    {"who": "Dmitri Kaznachey, FI Consulting", "when": "Sept 16", "said": "Don't call it three agents; don't claim it eliminates hallucinations.", "changed": "Described as an AI-assisted workflow; numbers come from code and are checked."},
    {"who": "O'Neal Keegan, Gallup", "when": "Sept 14", "said": "Teams under four respondents are not reported.", "changed": "n >= 4 enforced in SQL and code; teams under 4 people show no team numbers at all."},
    {"who": "Keegan, Sept 18 (data)", "when": "Sept 18", "said": "Gallup does not usually receive operations records; the client provides them.", "changed": "Operating data is uploaded by the client; the tool runs on the client's side."},
]


@app.get("/api/feedback")
def feedback():
    return FEEDBACK


# ------------------------------------------------------------------ ask (v0.5 flow)
class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    rules: bool = False   # True: rules mode (no model call), used by the Why page so it stays under a second
    live: bool = False    # True: skip a prepared answer and run the model now


PREPARED_PATH = ROOT / "data" / "prepared" / "answers.json"


def _norm(q: str) -> str:
    return " ".join(q.lower().strip().rstrip("?.! ").split())


def _prepared() -> dict:
    """Answers generated once in model mode for the demo's scripted questions (scripts/prepare_answers.py).
    Served labelled as prepared, with the time and model, never as live."""
    try:
        return json.loads(PREPARED_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_rules_lock = threading.Lock()


def _brief_mode(res) -> str:
    b = res.brief
    return "model" if (b and b.mode == "llm") or (res.scope and res.scope.mode == "llm") else "rules"


@app.post("/api/ask")
def ask(q: AskIn):
    if not q.rules and not q.live:
        hit = _prepared().get(_norm(q.question))
        if hit:
            rid = uuid.uuid4().hex[:10]
            _state.setdefault("prepared", {})[rid] = hit["approval"]
            return {**hit["response"], "id": rid, "prepared": {"generated_at": hit["generated_at"], "model": hit["model"]}}
    t0 = time.time()
    retriever = _retriever()  # build outside the rules switch, so model-mode retrieval keeps its embeddings
    if q.rules:
        with _rules_lock:  # the v0.5 agent reads config.has_key(); switch it off for this one call
            real = config.has_key
            config.has_key = lambda: False
            try:
                res = agent.run(q.question, _db(), retriever, fast=True)
            finally:
                config.has_key = real
    else:
        res = agent.run(q.question, _db(), retriever)
    rid = uuid.uuid4().hex[:10]
    _state["results"][rid] = res
    return _jsonable({"id": rid, "status": res.status, "question": res.question, "message": res.message,
                      "mode": _brief_mode(res), "seconds": round(time.time() - t0, 1), "notes": res.notes,
                      "grounding": _grounding(res), "trace": _trace(res, retriever), "prepared": None,
                      "assessment": asdict(res.assessment) if res.assessment else None,
                      "brief": asdict(res.brief) if res.brief else None,
                      "evidence": [asdict(e) for e in res.evidence]})


def _secs(notes: list[str], prefix: str) -> float | None:
    for n in notes:
        if n.startswith(prefix):
            m = re.search(r"([0-9]+\.[0-9]+)s", n)
            return float(m.group(1)) if m else None
    return None


def _grounding(res) -> dict:
    """Every number in the written brief must already appear in the evidence (statements or SQL rows)."""
    if not res.brief:
        return {"checked": 0, "total": 0, "unmatched": []}
    b = res.brief
    text = " ".join([b.obstacle, b.owner, b.proposed_test, b.limits] + [i.get("claim", "") for i in b.evidence_for + b.evidence_against] + list(b.missing))
    ctx = " ".join(e.statement + " " + json.dumps(e.rows, default=str) for e in res.evidence)
    allowed = agent._numbers_in(ctx)
    found = [m.group(1) for m in agent.NUM_RE.finditer(text)]
    bad = [n for n in found if n not in allowed and (n.rstrip("0").rstrip(".") if "." in n else n) not in allowed]
    return {"checked": len(found) - len(bad), "total": len(found), "unmatched": bad}


def _trace(res, retriever) -> list[dict]:
    """What happened, in order, from the run's own notes and evidence. No step is invented."""
    sc = res.scope
    ev = res.evidence
    sql = [e for e in ev if e.sql]
    rows = sum(len(e.rows) for e in ev)
    retrieved = [e for e in ev if e.origin == "retrieved"]
    steps = [{"step": "Understand the question", "detail": (f"{sc.intent.replace('_', ' ')}" + (f" · {sc.site or ''} {sc.team or ''}".rstrip() if sc and (sc.site or sc.team) else "")) if sc else "not in scope",
              "mode": "model" if sc and sc.mode == "llm" else "rules", "seconds": _secs(res.notes, "scope mode")}]
    if res.status != "refused":
        steps.append({"step": "Query the database views", "detail": f"{len(sql)} SQL queries · {rows} rows · teams under {config.MIN_N} suppressed in SQL", "mode": "code", "seconds": _secs(res.notes, "analyze + retrieve")})
        steps.append({"step": "Retrieve comments and documents", "detail": f"{len(retrieved)} passages · {retriever.mode.split(' ')[0]} search", "mode": "code", "seconds": None})
    if res.assessment:
        steps.append({"step": "Compute the verdict", "detail": res.assessment.label, "mode": "code", "seconds": None})
    if res.brief:
        g = _grounding(res)
        steps.append({"step": "Write the brief", "detail": "from the evidence above only", "mode": "model" if res.brief.mode == "llm" else "template", "seconds": _secs(res.notes, "brief mode")})
        steps.append({"step": "Check the brief", "detail": f"{g['checked']} of {g['total']} numbers found in the evidence" + (f"; {len(res.brief.check_notes)} repairs" if res.brief.check_notes else ""), "mode": "code", "seconds": None})
    return steps


class ApproveIn(BaseModel):
    result_id: str
    decision: str = Field(pattern="^(approved|rejected|flagged)$")
    note: str = ""


@app.post("/api/approve")
def approve(a: ApproveIn):
    prep = _state.get("prepared", {}).get(a.result_id)
    if prep:  # a prepared answer: record the decision in the same format agent.approve uses
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "who": "reviewer", "decision": a.decision, "note": a.note, **prep, "prepared": True}
        with open(config.APPROVALS_PATH, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec
    res = _state["results"].get(a.result_id)
    if not res:
        raise HTTPException(404, "unknown result; ask the question again")
    return _jsonable(agent.approve(res, a.decision, a.note))


@app.get("/api/review-log")
def review_log():
    return _jsonable(agent.review_log()[-20:])


@app.post("/api/upload")
async def upload(file: UploadFile):
    try:
        df = pd.read_csv(io.BytesIO(await file.read()))
        n = _db().add_ops_upload(df)
    except Exception as e:
        raise HTTPException(422, f"could not read that CSV: {e}")
    return {"rows_added": n}


# ------------------------------------------------------------------ report
@app.get("/api/report/{plan_id}", response_class=HTMLResponse)
def report(plan_id: str, as_of: str = I.AS_OF_REVIEW, download: bool = False):
    """One page, print-ready: the finding, the plan, the owners, the review result, the caveats. No scripts
    except a print button; every number comes from the same functions the app uses."""
    plan = next((p for p in I.load_plans() if p["id"] == plan_id), None)
    if not plan:
        raise HTTPException(404, "unknown plan")
    costs = _costs()
    w = I.why(int(plan["team_id"]), I.AS_OF_DETECT, costs)
    results = I.did_all(plan, _check_as_of(as_of), costs)
    r = results[0]
    e = html.escape
    kpi = plan.get("kpi", "late_doses")
    ex = (w.get("excess") or {}).get(kpi) or {}
    drops = [c for c in w.get("item_changes", []) if c["delta"] <= -0.30][:3]
    finding = (f"In {', '.join(w.get('window') or [])}, {e(I.KPI_LABELS[kpi].lower())} on this team were {ex.get('observed', 0):.0f} "
               f"against {ex.get('expected', 0):.1f} expected from comparable teams (Poisson p {'&lt; 0.001' if (ex.get('p') or 1) < 0.001 else '= ' + str(ex.get('p'))}). "
               if ex else "")
    if drops:
        finding += "Survey items that fell between waves: " + "; ".join(f"{e(c['label'])} {c['delta']:+.2f} pts" for c in drops) + "."
    plan = _plan_view(_norm_plan(plan))
    glyph = {"done": "&#9745;", "blocked": "&#9888;", "todo": "&#9744;"}
    acts = "".join(f"<tr><td class='tick'>{glyph.get(a.get('status'), '&#9744;')}</td><td>{e(a['text'])}</td><td>{e(a['owner'])}</td><td>{e(a['due'])}</td>"
                   f"<td>{e({'done': 'Done', 'blocked': 'Blocked', 'todo': 'Open'}.get(a.get('status'), 'Open'))}{(' · ' + e(a['done_at'][:10])) if a.get('done_at') else ''}</td></tr>" for a in plan["actions"])
    ex = plan.get("execution") or {}
    done = sum(1 for a in plan["actions"] if a.get("status") == "done")
    if ex:
        srcs = {}
        for x in ex.get("assigned", []):
            srcs[x["source"]] = srcs.get(x["source"], 0) + 1
        notices = "".join(f"<div class='box'><b>To:</b> {e(n['to'])}<br><b>Subject:</b> {e(n['subject'])}<pre>{e(n['body'])}</pre>"
                          f"<span class='muted'>{'AI-written from the plan facts, checked' if n.get('written_by') == 'model' else 'Templated from the plan'} · not sent</span></div>" for n in ex.get("notices", []))
        execution = (f"<ul><li><b>Owners assigned:</b> {len(ex.get('assigned', []))} tasks ({', '.join(f'{v} from the {k}' if k != 'manager' else f'{v} chosen by the manager' for k, v in srcs.items())}).</li>"
                     f"<li><b>Review scheduled:</b> {e(ex.get('review_scheduled', {}).get('date', plan['review']))}, in the Due reviews queue.</li>"
                     f"<li><b>KPI watch set:</b> {e(ex.get('kpi_watch', {}).get('kpi_label', ''))} for {e(ex.get('kpi_watch', {}).get('team_label', ''))}, {e(ex.get('kpi_watch', {}).get('cadence', 'monthly'))}, until {e(ex.get('kpi_watch', {}).get('until', plan['review']))}.</li>"
                     f"<li><b>Owner notices drafted:</b> {len(ex.get('notices', []))}. Nothing is sent by this prototype; the manager sends them.</li></ul>{notices}")
    else:
        execution = "<p class='muted'>This plan is a draft; nothing happens until a person approves it.</p>"
    if r["status"] == "ok":
        rows = "".join(f"<tr><td>{e(x['kpi_label'])}</td><td>{x['estimate'] * 10:+.1f}</td><td>{x['ci_low'] * 10:+.1f} to {x['ci_high'] * 10:+.1f}</td><td><b>{e(x['verdict'])}</b></td></tr>"
                       for x in results if x["status"] == "ok")
        money = f" About ${r['dollars_per_quarter']:,.0f} a quarter at the client-entered unit cost." if r.get("dollars_per_quarter") and r["verdict"] == "worked" else ""
        result = (f"<p>Compared with {e(', '.join(r['comparison']['teams']))} over the same months (before: {e(', '.join(r['pre_months']))}; after: {e(', '.join(r['post_months']))}).{money}</p>"
                  f"<table><tr><th>KPI (per 10 people / month)</th><th>Change vs comparison</th><th>95% CI</th><th>Verdict</th></tr>{rows}</table>")
    elif r["status"] == "not_reached":
        result = f"<p>The review is on {e(plan['review'])}: {r['days_to_go']} days to go.</p>"
    else:
        result = f"<p>{e(r.get('reason', 'Not enough follow-up data yet.'))}</p>"
    team = f"{w['team']['site']} {w['team']['team_name']}"
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Friction Finder · {e(team)} · plan and review</title>
<style>
body{{font-family:Geist,'Source Sans 3',Calibri,sans-serif;color:#101828;background:#fff;max-width:780px;margin:28px auto;padding:0 20px;font-size:13.5px;line-height:1.45}}
h1{{font-size:21px;margin:6px 0 2px}} h2{{font-size:14px;margin:18px 0 6px;text-transform:uppercase;letter-spacing:.05em;color:#344054}}
table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid #E4E7EC;padding:5px 6px;text-align:left;vertical-align:top}} th{{font-size:12px;color:#667085;font-weight:600}}
.tag{{display:inline-block;background:#E7F6F4;color:#0B6E65;border-radius:6px;padding:2px 8px;font-size:11.5px;font-weight:600}}
.muted{{color:#667085;font-size:12px}} .box{{border:1px solid #E4E7EC;border-radius:10px;padding:10px 12px;margin-top:6px}} .tick{{font-size:16px;width:22px}} pre{{white-space:pre-wrap;font:inherit;margin:6px 0;color:#344054}}
.print{{float:right;border:1px solid #D0D5DD;background:#fff;border-radius:8px;padding:6px 10px;font:inherit;cursor:pointer}}
@media print{{.print{{display:none}} body{{margin:0}} @page{{margin:14mm}}}}
</style></head><body>
<button class="print" onclick="window.print()">Print / Save as PDF</button>
<span class="tag">Friction Finder · Lanford Health (fictional) · synthetic data, no patient records</span>
<h1>{e(team)}: plan and review</h1>
<div class="muted">{w['team']['shift']} shift · {w['team']['headcount']} people · report as of {e(as_of)}</div>
<h2>What we found</h2><div class="box">{finding or 'No operating KPI beyond normal variation.'}</div>
<h2>Obstacle and plan</h2>
<p><b>Obstacle to test:</b> {e(plan.get('obstacle', ''))}<br><b>Focus item:</b> {e(plan.get('focus', plan['item']))} · <b>KPI to watch:</b> {e(I.KPI_LABELS[kpi])}<br>
<b>Start:</b> {e(plan['start'])} · <b>Review:</b> {e(plan['review'])} · <b>Status:</b> {e(plan['status'])} (approved by a person)</p>
<h2>Checklist · {done} of {len(plan['actions'])} done</h2>
<table><tr><th></th><th>Task</th><th>Responsible</th><th>Due</th><th>Status</th></tr>{acts}</table>
<h2>What happened when the plan was approved</h2>{execution}
<h2>Did it work?</h2>{result}
<h2>Read this before acting on it</h2>
<ul class="muted"><li>Directional, not causal: another change at the same time could explain the result. The plan owner should confirm what else changed.</li>
<li>Survey–KPI links are associations across teams, not causes. Teams under 4 people are never shown on their own.</li>
<li>Lanford Health is fictional and all data is synthetic (unit-level counts, no patient-level data); the follow-up months (Oct–Nov 2026) are synthetic.</li>
<li>Every number is computed by code from the survey export and operating records. The AI model does not produce numbers.</li></ul>
</body></html>"""
    headers = {"Content-Disposition": f'attachment; filename="friction_finder_{plan_id}.html"'} if download else None
    return HTMLResponse(doc, headers=headers)


# ------------------------------------------------------------------ v0.8 investigation (api/investigate_routes.py)
from api.investigate_routes import router as _investigate_router  # noqa: E402
app.include_router(_investigate_router)


# ------------------------------------------------------------------ static app
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
