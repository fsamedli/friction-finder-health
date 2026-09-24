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
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import agent, config
from app import impact as I
from app.db import DB

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"

app = FastAPI(title="Friction Finder", version="0.6")

_state: dict = {"db": None, "retriever": None, "results": {}}


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
    plan["review"] = p.review or (start + timedelta(days=60)).isoformat()
    plan["id"] = f"plan-{uuid.uuid4().hex[:8]}"
    return I.save_plan(plan)


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
    return [
        {"id": "survey", "name": "Engagement survey export", "vendor": "Gallup Access (Q12-style CSV)", "owner": "HR / People analytics",
         "status": "connected", "method": "CSV export, each wave", "rows": int(len(resp)), "detail": f"{resp.wave_id.nunique()} waves · {resp.team_id.nunique()} teams · respondent rows stay inside the database",
         "last": "2026-09-10"},
        {"id": "comments", "name": "Survey comments", "vendor": "Gallup Access (open text)", "owner": "HR / People analytics",
         "status": "connected", "method": "CSV export, each wave", "rows": int(len(com)), "detail": "Indexed for retrieval; teams under 4 respondents never indexed", "last": "2026-09-10"},
        {"id": "timekeeping", "name": "Timekeeping & attendance", "vendor": "e.g. UKG / Kronos", "owner": "Operations",
         "status": "connected", "method": "Monthly CSV (team template)", "rows": int(len(tom)), "detail": "Absences, quits, injuries, late departures, rework by team-month", "last": "2026-11-30"},
        {"id": "wms", "name": "Dispatch / WMS", "vendor": "e.g. Manhattan, Blue Yonder", "owner": "Operations",
         "status": "connected", "method": "Daily CSV by shift and hour", "rows": int(len(ops)) + int(up), "detail": f"Departures and late departures by hour band{f' · {up} rows uploaded this session' if up else ''}", "last": "2026-09-10"},
        {"id": "docs", "name": "Procedures & ownership directory", "vendor": "SharePoint / policy library", "owner": "Site operations",
         "status": "connected", "method": "Document folder", "rows": len(docs), "detail": ", ".join(docs[:4]), "last": "2026-09-01"},
        {"id": "hris", "name": "HRIS (tenure bands)", "vendor": "e.g. Workday", "owner": "HR",
         "status": "available", "method": "Not connected in the demo", "rows": 0, "detail": "Tenure bands come with the survey export in this demo", "last": None},
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


_rules_lock = threading.Lock()


def _brief_mode(res) -> str:
    b = res.brief
    return "model" if (b and b.mode == "llm") or (res.scope and res.scope.mode == "llm") else "rules"


@app.post("/api/ask")
def ask(q: AskIn):
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
                      "grounding": _grounding(res), "trace": _trace(res, retriever),
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
def report(plan_id: str, as_of: str = I.AS_OF_REVIEW):
    plan = next((p for p in I.load_plans() if p["id"] == plan_id), None)
    if not plan:
        raise HTTPException(404, "unknown plan")
    w = I.why(int(plan["team_id"]), I.AS_OF_DETECT, _costs())
    r = I.did(plan, _check_as_of(as_of), _costs())
    e = html.escape
    acts = "".join(f"<tr><td>{e(a['text'])}</td><td>{e(a['owner'])}</td><td>{e(a['due'])}</td></tr>" for a in plan["actions"])
    if r["status"] == "ok":
        result = (f"<p><b>{e(r['kpi_label'])}:</b> {r['estimate']:+.2f} per person per month vs comparable teams "
                  f"(95% CI {r['ci_low']:+.2f} to {r['ci_high']:+.2f}). Verdict: <b>{e(r['verdict'])}</b>. "
                  f"Directional, not causal; follow-up months are synthetic.</p>")
    else:
        result = f"<p>Review on {e(plan['review'])}: {e(r.get('reason') or str(r.get('days_to_go', '')) + ' days to go')}.</p>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Friction Finder plan</title>
<style>body{{font-family:'Source Sans 3',Calibri,sans-serif;color:#1B3A4B;background:#FAF8F3;max-width:760px;margin:32px auto;padding:0 16px}}
h1,h2{{font-family:Fraunces,Georgia,serif}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #E3DFD5;padding:6px;text-align:left}}
.tag{{display:inline-block;background:#1F8FA8;color:#fff;border-radius:999px;padding:2px 10px;font-size:12px}}</style></head><body>
<p class="tag">Friction Finder · Northline Logistics (fictional)</p>
<h1>{e(w['team']['site'])} {e(w['team']['team_name'])}: plan and review</h1>
<p><b>Obstacle:</b> {e(plan.get('obstacle', ''))}<br><b>Focus item:</b> {e(plan.get('focus', plan['item']))}<br>
<b>Start:</b> {e(plan['start'])} · <b>Review:</b> {e(plan['review'])} · <b>Status:</b> {e(plan['status'])}</p>
<h2>Actions</h2><table><tr><th>Action</th><th>Owner</th><th>Due</th></tr>{acts}</table>
<h2>Did it work?</h2>{result}
<p style="font-size:12px;color:#5b6b75">Every number is computed by code from the client's survey export and operating records. The model does not produce numbers. A person approved this plan.</p>
</body></html>"""


# ------------------------------------------------------------------ static app
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
