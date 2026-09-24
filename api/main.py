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
    return {"company": "Northline Logistics (fictional)",
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
def link(kpi: str = "late_departures", item: str = "q02"):
    if kpi not in I.KPIS or item not in I.item_labels():
        raise HTTPException(422, "unknown kpi or item")
    return _jsonable({"quartile": I.quartile_link(kpi, item), "association": I.association(kpi, item)})


@app.get("/api/links")
def links():
    return _jsonable(I.link_matrix())


# ------------------------------------------------------------------ act
class Action(BaseModel):
    text: str = Field(min_length=3)
    owner: str = Field(min_length=2)
    due: str


class PlanIn(BaseModel):
    team_id: int
    item: str
    kpi: str = "late_departures"
    obstacle: str = ""
    focus: str = ""
    actions: list[Action] = Field(min_length=1)
    start: str
    review: str | None = None
    status: str = "approved"
    note: str = ""


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
    return [{**p, "team_label": label.get(int(p["team_id"]), "")} for p in I.load_plans()]


@app.post("/api/plans")
def create_plan(p: PlanIn):
    if p.kpi not in I.KPIS:
        raise HTTPException(422, "unknown kpi")
    start = date.fromisoformat(p.start)
    plan = p.model_dump()
    plan["review"] = p.review or _default_review(start).isoformat()
    plan["id"] = f"plan-{uuid.uuid4().hex[:8]}"
    return I.save_plan(plan)


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
    """Template = the real demo rows for Richmond Night A, so the columns and scale are clear."""
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
    res = I.did_all(plan, _check_as_of(as_of), _costs())
    return _jsonable({**res[0], "also": res[1:]})


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
    return I.value_case(_costs(), headcount)


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
        {"id": "timekeeping", "name": "Timekeeping & attendance", "vendor": "Would connect to, e.g., UKG / Kronos", "owner": "Operations",
         "status": demo, "method": "Monthly CSV (team template)", "rows": int(len(tom)), "detail": "Absences, quits, injuries, late departures, rework by team-month", "last": "2026-11-30"},
        {"id": "wms", "name": "Dispatch / WMS", "vendor": "Would connect to, e.g., Manhattan, Blue Yonder", "owner": "Operations",
         "status": demo, "method": "Daily CSV by shift and hour", "rows": int(len(ops)) + int(up), "detail": f"Departures and late departures by hour band{f' · {up} rows uploaded this session' if up else ''}", "last": "2026-09-10"},
        {"id": "docs", "name": "Procedures & ownership directory", "vendor": "Would connect to, e.g., a SharePoint policy library", "owner": "Site operations",
         "status": demo, "method": "Document folder", "rows": len(docs), "detail": ", ".join(docs[:4]), "last": "2026-09-01"},
        {"id": "hris", "name": "HRIS (tenure bands)", "vendor": "Would connect to, e.g., Workday", "owner": "HR",
         "status": "not_connected", "method": "Not used in the demo", "rows": 0, "detail": "Tenure bands come with the survey export in this demo", "last": None},
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
        {"k": "Company", "v": "Northline Logistics, fictional: 3 distribution sites, 24 teams, 189 employees", "why": "Small enough to inspect by hand; big enough to show suppression and site-level inference."},
        {"k": "Survey", "v": f"12-item, 1-5 scale, 2 waves (Mar 15 and Sep 10, 2026); {len(resp)} responses", "why": "Shaped like Gallup's Q12; the items themselves are paraphrased."},
        {"k": "Response rate", "v": f"{rate.get(1, 0):.0%} wave 1, {rate.get(2, 0):.0%} wave 2", "why": "Typical of an engaged client; the real rate must come from Gallup."},
        {"k": "Minimum n", "v": f"{config.MIN_N} respondents per team-wave; teams under {config.MIN_N} people show no team numbers", "why": "Gallup's reporting threshold (Keegan, Sept 14). Applied in SQL and code, before any model call."},
        {"k": "Operating data", "v": f"{len(ops)} team-months (Jan-Nov 2026): absences, late departures, quits, injuries, rework", "why": "Comes from the client (timekeeping, WMS, HRIS), never from Gallup (Keegan, Sept 18)."},
        {"k": "First-year effect", "v": "New hires score about 0.35 points higher; the signal check adjusts for who responded", "why": "A drop can be a change in who answered, not in how people feel."},
        {"k": "Follow-up months", "v": "Oct-Nov 2026 are synthetic, planted so the plan's effect can be tested", "why": "Real follow-up needs a pilot; the method is what we are showing."},
        {"k": "Inference level", "v": "Team results are screening signals; associations use 34 team-waves; nothing here is causal", "why": "24 teams x 2 waves is small. We say so on screen."},
    ], "with_real_data": ["Response counts and rates from Gallup Access exports", "The client's own cost per late departure and per absence day",
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
                "reasons": {r: sum(1 for x in fb if x.get("reason") == r) for r in sorted({x.get("reason") for x in fb if x.get("reason")})}}
    return {"packs": packs, "declines": declines, "grounding": grounding, "latency": lat, "feedback": feedback}


FEEDBACK_PATH = config.APPROVALS_PATH.parent / "feedback.jsonl"


class FeedbackIn(BaseModel):
    target: str = Field(pattern="^(ask|plan)$")
    target_id: str = Field(min_length=1, max_length=80)
    useful: bool
    reason: str | None = Field(default=None, pattern="^(wrong number|wrong owner|not actionable|other)$")
    note: str = Field(default="", max_length=500)


@app.post("/api/useful")
def post_feedback(f: FeedbackIn):
    """'Useful? yes / no' on an Ask brief or a plan. Appended next to approvals.jsonl; starts empty."""
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
    kpi = plan.get("kpi", "late_departures")
    ex = (w.get("excess") or {}).get(kpi) or {}
    drops = [c for c in w.get("item_changes", []) if c["delta"] <= -0.30][:3]
    finding = (f"In {', '.join(w.get('window') or [])}, {e(I.KPI_LABELS[kpi].lower())} on this team were {ex.get('observed', 0):.0f} "
               f"against {ex.get('expected', 0):.1f} expected from comparable teams (Poisson p {'&lt; 0.001' if (ex.get('p') or 1) < 0.001 else '= ' + str(ex.get('p'))}). "
               if ex else "")
    if drops:
        finding += "Survey items that fell between waves: " + "; ".join(f"{e(c['label'])} {c['delta']:+.2f} pts" for c in drops) + "."
    acts = "".join(f"<tr><td>{e(a['text'])}</td><td>{e(a['owner'])}</td><td>{e(a['due'])}</td></tr>" for a in plan["actions"])
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
.muted{{color:#667085;font-size:12px}} .box{{border:1px solid #E4E7EC;border-radius:10px;padding:10px 12px;margin-top:6px}}
.print{{float:right;border:1px solid #D0D5DD;background:#fff;border-radius:8px;padding:6px 10px;font:inherit;cursor:pointer}}
@media print{{.print{{display:none}} body{{margin:0}} @page{{margin:14mm}}}}
</style></head><body>
<button class="print" onclick="window.print()">Print / Save as PDF</button>
<span class="tag">Friction Finder · Northline Logistics (fictional) · synthetic data</span>
<h1>{e(team)}: plan and review</h1>
<div class="muted">{w['team']['shift']} shift · {w['team']['headcount']} people · report as of {e(as_of)}</div>
<h2>What we found</h2><div class="box">{finding or 'No operating KPI beyond normal variation.'}</div>
<h2>Obstacle and plan</h2>
<p><b>Obstacle to test:</b> {e(plan.get('obstacle', ''))}<br><b>Focus item:</b> {e(plan.get('focus', plan['item']))} · <b>KPI to watch:</b> {e(I.KPI_LABELS[kpi])}<br>
<b>Start:</b> {e(plan['start'])} · <b>Review:</b> {e(plan['review'])} · <b>Status:</b> {e(plan['status'])} (approved by a person)</p>
<table><tr><th>Action</th><th>Owner</th><th>Due</th></tr>{acts}</table>
<h2>Did it work?</h2>{result}
<h2>Read this before acting on it</h2>
<ul class="muted"><li>Directional, not causal: another change at the same time could explain the result. The plan owner should confirm what else changed.</li>
<li>Survey–KPI links are associations across teams, not causes. Teams under 4 people are never shown on their own.</li>
<li>Northline Logistics is fictional and all data is synthetic; the follow-up months (Oct–Nov 2026) are synthetic.</li>
<li>Every number is computed by code from the survey export and operating records. The AI model does not produce numbers.</li></ul>
</body></html>"""
    headers = {"Content-Disposition": f'attachment; filename="friction_finder_{plan_id}.html"'} if download else None
    return HTMLResponse(doc, headers=headers)


# ------------------------------------------------------------------ static app
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
