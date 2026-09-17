"""Friction Finder screen.  Run:  streamlit run app/ui.py

A decision memo, not a dashboard. The business answer comes first (what happened, how sure we
are, who acts on Monday, what the test is); the technical appendix (evidence, queries, checks)
sits underneath for whoever asks. Three features on one screen (instructor, Sept 14, 2026):
diagnose, check the signal, act and review. Every element is labelled computed, retrieved,
generated, or templated (judges Jamshidi and Kaznachey, Sept 16). A person approves, rejects, or
flags every brief."""
from __future__ import annotations

import html as _h
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `streamlit run app/ui.py` can import `app`

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import config
from app.agent import (COMMENT_BREADTH, MIX_EXPLAINS, OPS_SIGNAL_ABS, OPS_SIGNAL_RATIO, STAFFING_LOW, SURVEY_MATERIAL, THEMES, Result,
                       approve, chat_answer, needs_brief, plan, report_html, report_markdown, review_log, run, write_brief)
from app.db import DB
from app.retrieval import Retriever
from evals.run_evals import RESULTS, evaluate

st.set_page_config(page_title="Friction Finder", page_icon="🔎", layout="wide", initial_sidebar_state="expanded")

# Brand: slate ink on warm paper, teal for what the code computed, burnt orange for what needs a
# person's attention. Teal and orange were validated for colour-vision separation.
SLATE, TEAL, ORANGE, LIGHT, MUTED, GRID, PAPER, SURFACE = "#1B3A4B", "#1F8FA8", "#C8553D", "#B9C6CC", "#6E7B85", "#EDEAE2", "#FAF8F3", "#FFFFFF"
ROOT = Path(__file__).resolve().parents[1]
PLOTLY_CONFIG = {"displayModeBar": False}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap');

:root {{ --ink:{SLATE}; --teal:{TEAL}; --orange:{ORANGE}; --muted:{MUTED}; --rule:{GRID}; --paper:{PAPER}; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1180px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}

/* eyebrow labels, pills, chips */
.eyebrow {{ font-family: 'Source Sans 3', Calibri, sans-serif; font-size: 11.5px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--teal); }}
.eyebrow.ink {{ color: var(--ink); opacity:.55; }}
.pill {{ display:inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; letter-spacing:.04em; color:#fff; background: var(--teal); vertical-align: middle; }}
.pill.orange {{ background: var(--orange); }} .pill.grey {{ background: var(--muted); }} .pill.ink {{ background: var(--ink); }}
.chip {{ display:inline-block; padding: 0 7px; border-radius: 6px; font-size: 10px; font-weight: 700; letter-spacing:.08em; vertical-align: middle; margin-left: 6px; border: 1px solid; line-height: 17px; }}
.chip-computed {{ color: var(--teal); border-color: var(--teal); }} .chip-generated {{ color: var(--orange); border-color: var(--orange); }}
.chip-templated {{ color: var(--ink); border-color: var(--ink); }} .chip-retrieved {{ color: var(--muted); border-color: var(--muted); }} .chip-human {{ color:#4F7A21; border-color:#4F7A21; }}
.ev {{ font-family: ui-monospace, Menlo, monospace; font-size: 11px; color: var(--muted); }}
.small {{ font-size: 13px; color: var(--muted); }}

/* masthead */
.masthead {{ display:flex; align-items:flex-end; justify-content:space-between; gap: 24px; padding: 6px 0 18px 0; border-bottom: 1px solid var(--ink); margin-bottom: 22px; }}
.masthead h1 {{ font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: 46px; line-height: 1.0; margin: 0; color: var(--ink); }}
.masthead .promise {{ font-size: 17px; color: var(--ink); max-width: 720px; margin-top: 10px; line-height: 1.45; }}
.masthead .promise b {{ font-weight: 700; }}
.masthead .meta {{ text-align: right; font-size: 12.5px; color: var(--muted); line-height: 1.7; white-space: nowrap; }}
.masthead .meta b {{ color: var(--ink); }}

/* playbook cards */
.card-title {{ font-family: 'Fraunces', Georgia, serif; font-size: 21px; font-weight: 600; color: var(--ink); margin: 2px 0 2px 0; line-height: 1.2; }}
.card-sub {{ font-size: 13.5px; color: var(--muted); margin-bottom: 8px; min-height: 38px; }}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{ background: {SURFACE}; box-shadow: 0 1px 0 rgba(27,58,75,.06), 0 6px 20px -14px rgba(27,58,75,.25); }}

/* buttons */
button[data-testid="stBaseButton-secondary"] {{ border: 1px solid var(--ink) !important; color: var(--ink) !important; background: transparent !important; font-weight: 600 !important; }}
button[data-testid="stBaseButton-secondary"]:hover {{ background: var(--ink) !important; color: #fff !important; }}
button[data-testid="stBaseButton-primary"] {{ font-weight: 700 !important; }}

/* memo */
@keyframes rise {{ from {{ opacity:0; transform: translateY(6px); }} to {{ opacity:1; transform:none; }} }}
.fade {{ animation: rise .45s ease-out both; }}
.memo-head {{ margin: 8px 0 14px 0; }}
.memo-title {{ font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: 34px; line-height: 1.15; color: var(--ink); margin: 6px 0 8px 0; }}
.memo-sub {{ font-size: 16px; color: var(--ink); line-height: 1.5; }}
.kpis {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 6px 0 18px 0; }}
.kpi {{ background: {SURFACE}; border: 1px solid var(--rule); border-radius: 10px; padding: 12px 14px; animation: rise .5s ease-out both; }}
.kpi-label {{ font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing:.02em; margin-bottom: 4px; min-height: 30px; line-height:1.25; }}
.kpi-value {{ font-family: 'Fraunces', Georgia, serif; font-size: 27px; font-weight: 600; color: var(--ink); line-height: 1.1; }}
.kpi-value .arrow {{ color: var(--muted); font-size: 20px; padding: 0 3px; }}
.kpi-tag {{ display:inline-block; margin-top: 7px; font-size: 11.5px; font-weight: 700; padding: 1px 8px; border-radius: 999px; background: #E9F4F7; color: var(--teal); }}
.kpi-tag.warn {{ background: #FBEAE5; color: var(--orange); }} .kpi-tag.grey {{ background: #EEF0F1; color: var(--muted); }}
.section {{ font-family: 'Fraunces', Georgia, serif; font-size: 20px; font-weight: 600; color: var(--ink); margin: 10px 0 6px 0; padding-bottom: 4px; border-bottom: 1px solid var(--rule); }}
.memo p, .memo li {{ font-size: 15.5px; line-height: 1.5; }}
.act {{ background: {SURFACE}; border: 1px solid var(--rule); border-left: 4px solid var(--teal); border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; }}
.act.warn {{ border-left-color: var(--orange); }}
.act .who {{ font-family: 'Fraunces', Georgia, serif; font-size: 19px; font-weight: 600; color: var(--ink); }}
.act .role {{ font-size: 13px; color: var(--muted); margin-bottom: 8px; }}
.declined {{ background: #FBEAE5; border-left: 4px solid var(--orange); padding: 12px 16px; border-radius: 8px; font-size: 15.5px; }}
.answer {{ background: {SURFACE}; border: 1px solid var(--rule); border-left: 4px solid var(--teal); padding: 12px 16px; border-radius: 8px; font-size: 15.5px; line-height: 1.5; }}

/* tabs, expanders, tables */
button[data-baseweb="tab"] p {{ font-weight: 600; font-size: 14.5px; }}
details[data-testid="stExpander"] summary p, details[data-testid="stExpander"] summary span {{ font-weight: 600; color: var(--ink); }}
.stMarkdown table {{ font-size: 14px; }}

/* sidebar (light) */
section[data-testid="stSidebar"] .brand {{ font-family: 'Fraunces', Georgia, serif; font-size: 22px; font-weight: 600; color: var(--ink); line-height:1.1; }}
section[data-testid="stSidebar"] .brand-sub {{ font-size: 11.5px; letter-spacing:.14em; text-transform: uppercase; color: var(--teal); margin: 6px 0 14px 0; }}
section[data-testid="stSidebar"] .stat {{ display:flex; justify-content:space-between; font-size: 13.5px; padding: 5px 0; border-bottom: 1px solid #D6DEE2; }}
section[data-testid="stSidebar"] .stat b {{ color: var(--ink); }}
section[data-testid="stSidebar"] .stat span {{ color: var(--muted); }}
section[data-testid="stSidebar"] .tag {{ display:inline-block; padding: 2px 8px; border-radius: 6px; font-size: 10.5px; font-weight: 700; letter-spacing:.08em; color:#8A3A28; background:#F6DDD4; margin-right: 4px; }}
section[data-testid="stSidebar"] .tag.mid {{ color:#155F70; background:#CDE7EE; }}
section[data-testid="stSidebar"] .small {{ color: var(--muted); }}

/* checklist */
.checks {{ display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; margin: 2px 0 16px 0; }}
.check {{ background: {SURFACE}; border: 1px solid var(--rule); border-radius: 10px; padding: 10px 12px; font-size: 13px; line-height: 1.4; color: var(--ink); }}
.check .ic {{ display:inline-block; width: 20px; height: 20px; border-radius: 50%; text-align:center; line-height: 20px; font-weight: 700; font-size: 12px; color:#fff; margin-right: 6px; }}
.check .ic.on {{ background: var(--teal); }} .check .ic.off {{ background: #C2CBD1; }} .check .ic.warn {{ background: var(--orange); }}
.check .t {{ font-weight: 700; }}
/* company pulse */
.pulse {{ background: {SURFACE}; border: 1px solid var(--rule); border-radius: 12px; padding: 14px 16px 6px 16px; }}
.pulse .site {{ font-family: 'Fraunces', Georgia, serif; font-size: 22px; font-weight: 600; color: var(--ink); }}
.pulse .row {{ display:flex; justify-content:space-between; font-size: 13.5px; padding: 5px 0; border-bottom: 1px solid var(--rule); }}
.pulse .row span {{ color: var(--muted); }} .pulse .row b {{ color: var(--ink); }}
.pulse .row b.warn {{ color: var(--orange); }}
/* workflow flow */
.flow {{ display:flex; gap: 8px; margin: 6px 0 14px 0; }}
.step {{ flex:1; background: {SURFACE}; border: 1px solid var(--rule); border-top: 4px solid var(--teal); border-radius: 8px; padding: 8px 10px; font-size: 12.5px; line-height: 1.35; }}
.step.model {{ border-top-color: var(--orange); }} .step.human {{ border-top-color: #4F7A21; }}
.step b {{ display:block; font-size: 13.5px; color: var(--ink); margin-bottom: 2px; }}
/* follow-up chat */
div[data-testid="stChatMessage"] {{ background: {SURFACE}; border: 1px solid var(--rule); border-radius: 10px; padding: 10px 14px; }}
div[data-testid="stChatInput"] {{ border-radius: 999px; }}
</style>
""", unsafe_allow_html=True)


def chip(kind: str) -> str:
    return f"<span class='chip chip-{kind}'>{kind}</span>"


@st.cache_resource(show_spinner="Loading the synthetic company, views, and documents...")
def _load():
    db = DB()
    retriever = Retriever(db)
    if config.has_key():
        try:  # warm the connection to the GW resource once, so the first click is not 10 seconds slower than the rest
            from app import llm
            llm.chat_json("Return only {\"ok\": true}.", "ok", effort="minimal")
        except Exception:
            pass
    return db, retriever


db, retriever = _load()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("<div class='brand'>Friction Finder</div><div class='brand-sub'>Group 4 · DNSC 6317 · GW</div>", unsafe_allow_html=True)
    st.markdown("<span class='tag'>Synthetic data</span><span class='tag mid'>Fictional company</span>", unsafe_allow_html=True)
    n_ops = db.con.execute("SELECT COUNT(*) FROM ops_daily").fetchone()[0]
    key = config.has_key()
    st.markdown(f"""
<div style='margin-top:12px'>
<div class='stat'><span>Company</span><b>Northline Logistics</b></div>
<div class='stat'><span>Sites · teams · waves</span><b>3 · 24 · 2</b></div>
<div class='stat'><span>Survey responses</span><b>311</b></div>
<div class='stat'><span>Operations rows</span><b>{n_ops:,}{' ↑' if db.uploaded_ops_rows else ''}</b></div>
<div class='stat'><span>Reporting threshold</span><b>n ≥ {config.MIN_N}</b></div>
<div class='stat'><span>Model</span><b>{config.MODEL if key else 'none (rules)'}</b></div>
<div class='stat'><span>Retrieval</span><b>{retriever.mode.split(' ')[0]}</b></div>
</div>""", unsafe_allow_html=True)
    st.markdown("<p class='small' style='margin-top:10px'>Numbers never come from the model. It reads the question and writes text from evidence it is handed; every draft is checked.</p>", unsafe_allow_html=True)
    with st.expander("Bring your own operational records"):
        st.caption("How a client's delay records enter in a pilot: an export from dispatch or the warehouse system, approved by its owner. Columns: date, site_id, shift, hour_band, departures, late_departures, rework_count.")
        template = pd.DataFrame([{"date": "2026-09-11", "site_id": 1, "shift": "Night", "hour_band": "06-07",
                                  "departures": 24, "late_departures": 6, "rework_count": 1}])
        st.download_button("Download the CSV template", template.to_csv(index=False).encode(), "ops_template.csv", "text/csv", width="stretch")
        up = st.file_uploader("Choose a CSV", type=["csv"], label_visibility="collapsed")
        if up is not None and st.session_state.get("last_upload") != up.name + str(up.size):
            try:
                n = db.add_ops_upload(pd.read_csv(up))
                st.session_state["last_upload"] = up.name + str(up.size)
                st.success(f"Added {n} rows. They are in the operational evidence of the next question.")
            except Exception as e:
                st.error(f"Upload rejected: {e}")
    with st.expander("About this prototype"):
        st.caption("Built with the tools we were given: the group's GW Azure OpenAI resource, gpt-5-mini, reasoning effort minimal (scope) and low (writing). "
                   "A stronger model changes the wording of briefs, not the numbers or the verdicts. Northline Logistics does not exist; patterns were planted so the assistant can be scored.")

# ------------------------------------------------------------------ masthead
st.markdown(f"""
<div class='masthead'>
  <div>
    <div class='eyebrow'>Evidence briefs for operations leaders</div>
    <h1>Friction Finder</h1>
    <div class='promise'>When a team's engagement score falls, the <b>site or shift manager</b> gets a one-page brief that says what is behind it,
    how sure we are, <b>who owns the fix</b>, and what to test first. Built from survey results, the operation's own records, its procedures, and what employees wrote.</div>
  </div>
  <div class='meta'><b>Starting segment</b><br>operations-heavy workplaces<br>where daily work is logged<br><b>No autonomous action</b> · a person approves</div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ playbook
PLAYBOOK = [
    ("01", "Diagnose", "Where did we drop, and what is behind it?", [
        ("Where did we drop? (Richmond)", "Where did scores drop across Richmond?"),
        ("Why did the night shift drop?", "Why did the Richmond night shift's scores drop and why are deliveries late?"),
        ("A team under 4 respondents", "Why did the Richmond Dispatch Day team's scores drop?"),
    ]),
    ("02", "Check the signal", "Is the change real, or did different people answer?", [
        ("Is the decline real?", "Is the Norfolk Day B decline real or did different people respond?"),
        ("Scores by tenure", "How do scores vary by tenure?"),
    ]),
    ("03", "Act and review", "Who owns it, and what do we do first?", [
        ("Who owns the handoff?", "Who owns the shift handoff process at Richmond?"),
        ("One team's score and respondents", "What was the Richmond Night A score on materials and equipment in wave 2, and how many people responded?"),
    ]),
]
REDTEAM = [
    ("A blip with no operations signal", "Why did the Roanoke Day C team's scores drop?"),
    ("One loud comment", "Why did the Norfolk night shift's scores drop?"),
    ("Data we do not have", "What caused turnover on the Norfolk night shift?"),
    ("A site we do not have", "Why did the Denver site drop?"),
]


def _ask(q: str):
    with st.spinner("Reading the question, querying the views, retrieving, assessing..."):
        st.session_state["result"] = run(q, db, retriever, fast=True)   # the written brief arrives after the computed part is on screen
    st.session_state["decision"] = None
    st.session_state["plan"] = None
    st.session_state["chat"] = []
    st.session_state["last_asked"] = q


def _on_enter():
    q = st.session_state.get("question", "").strip()
    if q and q != st.session_state.get("last_asked"):
        _ask(q)


def _reset():
    for k in ("result", "decision", "plan", "chat", "last_asked", "note"):
        st.session_state.pop(k, None)
    st.session_state["question"] = ""


def _pulse() -> list[dict]:
    """Company pulse for the landing page: one card per site, all from the reporting views."""
    gm = db.run_sql("SELECT site_name, wave_id, ROUND(AVG(mean_score), 2) AS gm, MIN(n) AS n FROM v_site_wave_item WHERE reportable GROUP BY 1, 2").rows
    hidden = db.run_sql(f"SELECT s.site_name, COUNT(DISTINCT t.team_id) AS hidden FROM v_team_wave_n n JOIN teams t ON t.team_id = n.team_id JOIN sites s ON s.site_id = t.site_id WHERE n.n < {config.MIN_N} GROUP BY 1").rows
    teams = db.run_sql("SELECT s.site_name, COUNT(*) AS teams FROM teams t JOIN sites s ON s.site_id = t.site_id GROUP BY 1").rows
    tw = db.run_sql("SELECT site_name, team_id, item, wave_id, mean_score, reportable FROM v_team_wave_item ORDER BY site_name, team_id, item, wave_id").rows
    ops = db.run_sql("SELECT site_name, period, ROUND(SUM(late_departures) * 1.0 / SUM(departures), 3) AS late_rate FROM v_ops_hour GROUP BY 1, 2").rows
    out = []
    for site in db.sites():
        g = {int(r.wave_id): (float(r.gm), int(r.n)) for r in gm[gm.site_name == site].itertuples()}
        t = tw[tw.site_name == site]
        piv = t.pivot_table(index=["team_id", "item"], columns="wave_id", values="mean_score", aggfunc="first")
        watch = int(((piv.get(2) - piv.get(1)).round(2) <= -SURVEY_MATERIAL).sum()) if 1 in piv.columns and 2 in piv.columns else 0  # same rounding as the site overview
        o = {r.period: float(r.late_rate) for r in ops[ops.site_name == site].itertuples()}
        out.append({"site": site, "gm1": g.get(1, (None, None))[0], "gm2": g.get(2, (None, None))[0], "n1": g.get(1, (None, None))[1], "n2": g.get(2, (None, None))[1],
                    "hidden": int(hidden[hidden.site_name == site].hidden.iloc[0]) if len(hidden[hidden.site_name == site]) else 0,
                    "teams": int(teams[teams.site_name == site].teams.iloc[0]), "watch": watch,
                    "late1": o.get("Jan-May 2026"), "late2": o.get("Jun-Sep 2026")})
    return out


if st.session_state.get("result") is None:
    st.markdown("<div class='eyebrow'>Company pulse · Wave 2 (Sep 2026) vs Wave 1 (Mar 2026)</div>", unsafe_allow_html=True)
    pc = st.columns(3, gap="medium")
    for col, row in zip(pc, _pulse()):
        with col:
            d = (row["gm2"] - row["gm1"]) if row["gm1"] is not None and row["gm2"] is not None else 0.0
            dl = (row["late2"] - row["late1"]) * 100 if row["late1"] is not None and row["late2"] is not None else 0.0
            st.markdown(f"""<div class='pulse'><div class='site'>{row['site']}</div>
<div class='row'><span>Engagement grand mean</span><b class='{'warn' if d <= -0.1 else ''}'>{row['gm1']:.2f} → {row['gm2']:.2f} ({d:+.2f})</b></div>
<div class='row'><span>Respondents</span><b>{row['n1']} → {row['n2']}</b></div>
<div class='row'><span>Teams hidden (n &lt; {config.MIN_N})</span><b>{row['hidden']} of {row['teams']}</b></div>
<div class='row'><span>Team-level watch items</span><b class='{'warn' if row['watch'] >= 8 else ''}'>{row['watch']}</b></div>
<div class='row'><span>Late departures, all shifts</span><b class='{'warn' if dl >= 1 else ''}'>{row['late1'] * 100:.1f}% → {row['late2'] * 100:.1f}%</b></div>
</div>""", unsafe_allow_html=True)
            if st.button(f"Open {row['site']}", key="pulse_" + row["site"], width="stretch"):
                st.session_state["question"] = f"Where did scores drop across {row['site']}?"
                _ask(st.session_state["question"])
                st.rerun()
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

cols = st.columns(3, gap="medium")
for col, (num, title, sub, buttons) in zip(cols, PLAYBOOK):
    with col, st.container(border=True):
        st.markdown(f"<div class='eyebrow'>{num} · {title}</div><div class='card-title'>{sub}</div>", unsafe_allow_html=True)
        for label, q in buttons:
            if st.button(label, key="pb_" + label, width="stretch"):
                st.session_state["question"] = q
                _ask(q)
                st.rerun()   # re-render without the landing pulse; the brief still fills in after the computed part

with st.expander("Red-team cases: what it refuses to do"):
    rc = st.columns(len(REDTEAM))
    for col, (label, q) in zip(rc, REDTEAM):
        if col.button(label, key="rt_" + label, width="stretch"):
            st.session_state["question"] = q
            _ask(q)
            st.rerun()

qcol, bcol, rcol = st.columns([6, 1, 1], vertical_alignment="bottom")
question = qcol.text_input("Or ask in your own words (Enter to ask)", key="question", on_change=_on_enter,
                           placeholder="e.g., Why did the Richmond night shift's scores drop and why are deliveries late?")
if bcol.button("Ask", type="primary", width="stretch") and question.strip():
    _ask(question.strip())
    st.rerun()
rcol.button("Start over", width="stretch", on_click=_reset, help="Clear the result, the plan, and the chat")

res: Result | None = st.session_state.get("result")


# ------------------------------------------------------------------ charts
def _style(fig, height=340, ytitle=None, xtitle=None):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                      font=dict(family="Source Sans 3, Calibri, Arial, sans-serif", color=SLATE, size=13),
                      legend=dict(orientation="h", y=1.12, x=0, font=dict(color=SLATE)), bargap=0.25, bargroupgap=0.08,
                      hoverlabel=dict(bgcolor=SURFACE, font=dict(color=SLATE)))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, title=ytitle, showline=False)
    fig.update_xaxes(showgrid=False, title=xtitle, showline=False)
    return fig


def _chart_survey(res: Result):
    table = [e for e in res.evidence if e.kind == "survey_table"]
    if not table:
        return None
    df = pd.DataFrame(table[0].rows)
    piv = df.pivot_table(index="item", columns="wave_id", values="mean_score", aggfunc="first").reset_index()
    piv.columns = [str(c) for c in piv.columns]
    labels = df.drop_duplicates("item").set_index("item").item_label.to_dict()
    piv["delta"] = piv["2"] - piv["1"]
    worst = set(piv[piv.delta <= -SURVEY_MATERIAL].nsmallest(3, "delta").item)
    fig = go.Figure()
    fig.add_bar(name="Wave 1 (Mar 2026)", x=piv.item, y=piv["1"], marker_color=LIGHT, marker_line_width=0,
                hovertemplate="%{x} · Wave 1: %{y:.2f}<extra></extra>")
    fig.add_bar(name="Wave 2 (Sep 2026)", x=piv.item, y=piv["2"], marker_color=[ORANGE if i in worst else TEAL for i in piv.item], marker_line_width=0,
                text=[f"{d:+.2f}" if i in worst else "" for i, d in zip(piv.item, piv.delta)], textposition="outside", textfont=dict(color=SLATE, size=12),
                customdata=piv.delta, hovertemplate="%{x} · Wave 2: %{y:.2f} (change %{customdata:+.2f})<extra></extra>")
    fig.update_layout(barmode="group", yaxis=dict(range=[1, 5.2]))
    fig.update_xaxes(ticktext=[i.upper() for i in piv.item], tickvals=piv.item)
    return _style(fig, 340, "Mean (1 to 5)", "Survey item"), {i: labels[i] for i in worst}


def _chart_ops(res: Result):
    ops = [e for e in res.evidence if e.kind == "ops_hour"]
    if not ops:
        return None
    df = pd.DataFrame(ops[0].rows)
    piv = df.pivot_table(index="hour_band", columns="period", values="late_rate", aggfunc="first").reset_index()
    order = ["18-22", "22-02", "02-06", "06-07", "07-10", "10-14", "14-18"]
    piv = piv.set_index("hour_band").reindex([o for o in order if o in set(piv.hour_band)]).reset_index()
    hb, sig = ops[0].value.get("hour_band"), ops[0].value.get("signal")
    fig = go.Figure()
    if "Jan-May 2026" in piv:
        fig.add_bar(name="Jan-May 2026", x=piv.hour_band, y=piv["Jan-May 2026"] * 100, marker_color=LIGHT, marker_line_width=0,
                    hovertemplate="%{x} · Jan-May: %{y:.1f}%<extra></extra>")
    if "Jun-Sep 2026" in piv:
        fig.add_bar(name="Jun-Sep 2026", x=piv.hour_band, y=piv["Jun-Sep 2026"] * 100,
                    marker_color=[ORANGE if (sig and b == hb) else TEAL for b in piv.hour_band], marker_line_width=0,
                    text=[f"{v * 100:.1f}%" if (sig and b == hb) else "" for b, v in zip(piv.hour_band, piv["Jun-Sep 2026"])], textposition="outside",
                    hovertemplate="%{x} · Jun-Sep: %{y:.1f}%<extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_xaxes(type="category")
    return _style(fig, 340, "Late departures (%)", "Hour band")


def _chart_tenure(res: Result):
    ev = [e for e in res.evidence if e.kind == "tenure_pattern"]
    if not ev:
        return None
    order = ["under_1", "1_to_3", "3_to_10", "over_10"]
    names = ["Under 1 year", "1 to 3 years", "3 to 10 years", "Over 10 years"]
    vals = [ev[0].value.get(b) for b in order]
    fig = go.Figure(go.Bar(x=names, y=vals, marker_color=[ORANGE, TEAL, TEAL, TEAL], marker_line_width=0,
                           text=[f"{v:.2f}" if v is not None else "" for v in vals], textposition="outside", hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
    fig.update_layout(yaxis=dict(range=[3, 4.6]))
    return _style(fig, 320, "Grand mean (1 to 5)", "Tenure")


def _chart_mix(res: Result):
    ev = [e for e in res.evidence if e.kind == "tenure_mix"]
    if not ev:
        return None
    df = pd.DataFrame(ev[0].rows)
    fig = go.Figure()
    for band, name, color in (("under_1", "Under 1 year", ORANGE), ("1_to_3", "1 to 3 years", TEAL), ("3_to_10", "3 to 10 years", "#5FA9BC"), ("over_10", "Over 10 years", LIGHT)):
        sub = df[df.tenure_band == band].set_index("wave_id").n.reindex([1, 2]).fillna(0)
        fig.add_bar(name=name, x=["Wave 1", "Wave 2"], y=sub.values, marker_color=color, marker_line=dict(color=SURFACE, width=2),
                    hovertemplate=name + ": %{y:.0f} respondents<extra></extra>")
    fig.update_layout(barmode="stack")
    return _style(fig, 320, "Respondents", None)


def _chart_heatmap(res: Result):
    ev = [e for e in res.evidence if e.kind == "site_heatmap"]
    if not ev:
        return None
    df = pd.DataFrame(ev[0].rows)
    if not len(df):
        return None
    items = sorted(df.item.unique())
    teams = list(dict.fromkeys(df.sort_values(["shift", "team_name"]).team_name))
    z = [[float(df[(df.team_name == t) & (df.item == i)].delta.iloc[0]) if len(df[(df.team_name == t) & (df.item == i)]) else None for i in items] for t in teams]
    ns = {t: int(df[df.team_name == t].n.iloc[0]) for t in teams}
    ylab = [f"{t} (n={ns[t]})" for t in teams]
    for s in ev[0].value.get("suppressed", []):
        z.append([None] * len(items))
        ylab.append(f"{s['team_name']} (n<{config.MIN_N}, hidden)")
    fig = go.Figure(go.Heatmap(z=z, x=[i.upper() for i in items], y=ylab, zmin=-1, zmax=1, zmid=0,
                               colorscale=[[0, ORANGE], [0.5, "#F2F1EC"], [1, TEAL]],
                               text=[[f"{v:+.2f}" if v is not None else "" for v in row] for row in z], texttemplate="%{text}", textfont=dict(size=12),
                               xgap=3, ygap=3, hoverongaps=False, hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
                               colorbar=dict(title="Change<br>W1→W2", thickness=10)))
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig = _style(fig, 70 + 30 * len(ylab), None, "Survey item")
    fig.update_layout(margin=dict(l=190))
    return fig


def _chart_site_items(res: Result):
    ev = [e for e in res.evidence if e.kind == "site_items"]
    if not ev:
        return None
    df = pd.DataFrame(ev[0].rows).sort_values("vs_company")
    colors = [ORANGE if i in set(ev[0].value.get("opportunities", [])) else (TEAL if i == ev[0].value.get("strength") else LIGHT) for i in df.item]
    fig = go.Figure(go.Bar(x=[i.upper() for i in df.item], y=df.vs_company, marker_color=colors, marker_line_width=0, text=[f"{v:+.2f}" for v in df.vs_company], textposition="outside",
                           customdata=df.item_label, hovertemplate="%{x} %{customdata}: %{y:+.2f} vs company<extra></extra>"))
    fig.add_hline(y=0, line_color=MUTED, line_width=1)
    return _style(fig, 300, "Wave 2 vs company mean", "Survey item")


# ------------------------------------------------------------------ memo pieces (business layer)
def _by_kind(res: Result) -> dict:
    by = {}
    for e in res.evidence:
        by.setdefault(e.kind, []).append(e)
    return by


def _scope_name(res: Result) -> str:
    sc = res.scope
    if not sc:
        return ""
    return " ".join(x for x in [sc.site, sc.team] if x) or (sc.site or "")


def _headline(res: Result) -> tuple[str, str, str, str]:
    """(eyebrow, title, subline, pill kind) for the memo head."""
    a, sc = res.assessment, res.scope
    where = _scope_name(res)
    if res.status == "refused":
        return "Declined", "We cannot answer that from the data we have.", res.message, "orange"
    if a is None:
        titles = {"site_overview": (f"Where {where} moved between waves", "Team-level changes are watch items; the site level is where comparisons hold."),
                  "review_decline_real": (f"Did {where} really decline?", "The change is checked against who responded in each wave."),
                  "tenure_pattern": ("How scores vary by tenure", "Both waves, respondent-weighted, reportable groups only."),
                  "owner_lookup": ("Who owns the process", "From the ownership directory."),
                  "metric_lookup": ("The number you asked for", "From the reporting views; team figures only where n is 4 or more.")}
        t, s = titles.get(sc.intent if sc else "", ("Answer", ""))
        return "Computed answer", t, s, "teal"
    theme = THEMES[a.theme]["label"] if a.theme else "the process"
    if a.verdict == "supported":
        corr = " and ".join(x for x, ok in (("the operation's own records", a.ops_signal), (f"{[e for e in res.evidence if e.kind == 'comment_themes'][0].value['top_count']} separate employee comments" if a.comment_signal else "", a.comment_signal)) if ok)
        return ("Evidence brief", f"{theme[0].upper() + theme[1:]} is the likely obstacle on {where}.",
                f"A supported hypothesis, not a proven cause: the survey fell and {corr} point the same way. {a.level.capitalize()} level, n = {a.n.get('w1')} to {a.n.get('w2')}.", "teal")
    if a.verdict == "insufficient":
        return ("Evidence brief", f"The survey moved on {where}, but nothing else did.",
                "Not enough evidence to name an obstacle. Treat it as a watch item; no action proposed until the operation's records or more comments corroborate it.", "orange")
    if a.verdict == "no_material_change":
        return ("Evidence brief", f"No material change on {where}.",
                f"No survey item fell {SURVEY_MATERIAL:.2f} or more between waves. Nothing to diagnose; keep on the watch list.", "grey")
    return ("Evidence brief", f"{where} is too small to report on its own.",
            f"Fewer than {config.MIN_N} respondents, so team results stay hidden to protect anonymity. The site-level view is shown instead; the manager reviews it with the Site Operations Manager.", "grey")


def _kpis(res: Result) -> list[tuple[str, str, str, str]]:
    """(label, value html, tag text, tag kind) tiles, computed only."""
    by, a, sc = _by_kind(res), res.assessment, res.scope
    tiles = []
    if a is not None:
        deltas = by.get("survey_delta", []) or by.get("survey_delta_site", [])
        for e in [x for x in deltas if x.value.get("material") and x.value.get("delta", 0) < 0][:2] or deltas[:1]:
            v = e.value
            label = e.statement.split(", ", 1)[1].split(":")[0] if ", " in e.statement else v["item"]
            tiles.append((label, f"{v.get('wave1', float('nan')):.2f}<span class='arrow'>→</span>{v.get('wave2', float('nan')):.2f}",
                          f"{v['delta']:+.2f}, {'material' if v.get('material') else 'within noise'}", "warn" if v.get("material") else "grey"))
        ops = by.get("ops_hour", [None])[0]
        if ops:
            v = ops.value
            tiles.append((f"Late departures, {v['hour_band']} band", f"{v['before'] * 100:.1f}%<span class='arrow'>→</span>{v['after'] * 100:.1f}%",
                          "operational signal" if v.get("signal") else "no signal", "warn" if v.get("signal") else "grey"))
        th = by.get("comment_themes", [None])[0]
        if th and th.value.get("total"):
            v = th.value
            lab = THEMES[v["top_theme"]]["label"] if v.get("top_theme") else "no theme"
            tiles.append((f"Comments on '{lab}'", f"{v['top_count']}<span class='arrow'>of</span>{v['total']}",
                          "corroborating" if v.get("breadth_ok") else "single source", "ok" if v.get("breadth_ok") else "grey"))
        elif th:
            tiles.append(("Wave 2 comments", "0", "none reportable", "grey"))
        if a.n:
            tiles.append((f"Respondents, {a.level} level", f"{a.n.get('w1')}<span class='arrow'>→</span>{a.n.get('w2')}",
                          "watch items at team level" if a.level == "team" else "site roll-up", "grey"))
        return tiles[:4]
    if sc and sc.intent == "site_overview":
        hm = by.get("site_heatmap", [None])[0]
        si = by.get("site_items", [None])[0]
        if hm:
            v = hm.value
            n_rep = len({c["team_id"] for c in hm.rows})
            tiles += [("Teams reportable in both waves", f"{n_rep}<span class='arrow'>of</span>{n_rep + len(v['suppressed'])}", "team level", "grey"),
                      (f"Hidden (fewer than {config.MIN_N} respondents)", f"{len(v['suppressed'])}", "never shown", "grey"),
                      ("Team-level watch items", f"{len(v['watch'])}", f"fell {SURVEY_MATERIAL:.2f} or more", "warn" if v["watch"] else "grey")]
        if si:
            tiles.append(("Site respondents", f"{si.value['n1']}<span class='arrow'>→</span>{si.value['n2']}", "where inference holds", "ok"))
    elif sc and sc.intent == "review_decline_real":
        sig = by.get("signal_check", [None])[0]
        if sig:
            v = sig.value
            tiles += [("Team grand mean", f"{v['gm_w1']:.2f}<span class='arrow'>→</span>{v['gm_w2']:.2f}", f"{v['observed']:+.2f} observed", "warn" if abs(v['observed']) >= SURVEY_MATERIAL else "grey"),
                      ("Expected from who responded", f"{v['expected_from_mix']:+.2f}", "shift-share", "grey"),
                      ("Remaining after adjustment", f"{v['residual']:+.2f}", f"{'within noise' if abs(v['residual']) < MIX_EXPLAINS else 'persists'}", "grey" if abs(v['residual']) < MIX_EXPLAINS else "warn"),
                      ("Verdict", {"mix": "Who responded", "real": "Real change", "no_material_change": "No change"}.get(v["verdict"], v["verdict"]),
                       {"mix": "not a real decline", "real": "persists after adjusting", "no_material_change": "nothing to explain"}.get(v["verdict"], ""), "ok" if v["verdict"] != "real" else "warn")]
    elif sc and sc.intent == "tenure_pattern":
        tp = by.get("tenure_pattern", [None])[0]
        if tp:
            for b, name in (("under_1", "Under 1 year"), ("1_to_3", "1 to 3 years"), ("3_to_10", "3 to 10 years"), ("over_10", "Over 10 years")):
                if b in tp.value:
                    tiles.append((name, f"{tp.value[b]:.2f}", "year-one effect" if b == "under_1" else "grand mean", "warn" if b == "under_1" else "grey"))
    return tiles[:4]


def _render_kpis(tiles):
    if not tiles:
        return
    cells = "".join(f"<div class='kpi' style='animation-delay:{0.06 * i:.2f}s'><div class='kpi-label'>{_h.escape(l)}</div><div class='kpi-value'>{v}</div>"
                    f"<span class='kpi-tag {'' if k == 'ok' else k}'>{_h.escape(t)}</span></div>" for i, (l, v, t, k) in enumerate(tiles))
    st.markdown(f"<div class='kpis'>{cells}</div>", unsafe_allow_html=True)


def _checklist(a):
    """Why the code says so, as four cells: survey, operations, comments, staffing."""
    def reason(prefix):
        return next((r.split(":", 1)[1].strip() for r in a.reasons if r.startswith(prefix)), "")
    cells = [("Survey", a.survey_signal, "material fall" if a.survey_signal else "no material fall", reason("Survey"), "on" if a.survey_signal else "off"),
             ("Operations", a.ops_signal, "signal" if a.ops_signal else "no signal", reason("Operations"), "on" if a.ops_signal else "off"),
             ("Comments", a.comment_signal, "corroborating" if a.comment_signal else "not corroborating", reason("Comments"), "on" if a.comment_signal else "off"),
             ("Staffing", a.staffing_signal, "competing explanation" if a.staffing_signal else "no shortage month", reason("Staffing") or f"No month under {STAFFING_LOW * 100:.0f}% of scheduled.", "warn" if a.staffing_signal else "off")]
    html = "".join(f"<div class='check'><div class='eyebrow ink'>{lab}</div><div><span class='ic {kind}'>{'✓' if kind == 'on' else ('!' if kind == 'warn' else '–')}</span><span class='t'>{_h.escape(short)}</span></div>"
                   f"<div class='small'>{_h.escape(text)}</div></div>" for lab, _, short, text, kind in cells)
    st.markdown(f"<div class='eyebrow ink' style='margin-bottom:6px'>Why the code says so</div><div class='checks'>{html}</div>", unsafe_allow_html=True)


def _claims(items):
    for i in items:
        st.markdown(f"- {i.get('claim')} <span class='ev'>[{', '.join(i.get('evidence_ids', []))}]</span>", unsafe_allow_html=True)


def _memo(res: Result):
    """The business layer: what we found, what to do Monday, and the human decision."""
    b, a = res.brief, res.assessment
    mode = "generated" if b.mode == "llm" else "templated"
    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.markdown("<div class='memo'>", unsafe_allow_html=True)
        st.markdown(f"<div class='section'>What we found {chip(mode)}</div>", unsafe_allow_html=True)
        st.markdown(b.obstacle)
        st.markdown("**Evidence for**")
        _claims(b.evidence_for)
        st.markdown("**Evidence against, and competing explanations**")
        _claims(b.evidence_against)
        st.markdown("**What we still do not know**")
        for m in b.missing:
            st.markdown(f"- {m}")
        st.caption(f"Limits: {b.limits}")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown(f"<div class='section'>What to do on Monday</div>", unsafe_allow_html=True)
        owner = next((e for e in res.evidence if e.kind == "owner"), None)
        if owner and a and a.verdict == "supported":
            st.markdown(f"<div class='act'><div class='eyebrow'>Process owner {chip('computed')}</div><div class='who'>{_h.escape(owner.value['name'])}</div>"
                        f"<div class='role'>{_h.escape(owner.value['role'])} · owns '{_h.escape(owner.value['process'])}' (ownership directory)</div>"
                        f"<div class='eyebrow'>Proposed 30-day test {chip(mode)}</div><div style='font-size:15px;line-height:1.45;margin-top:4px'>{_h.escape(b.proposed_test)}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='act warn'><div class='eyebrow'>No action proposed {chip('computed')}</div><div style='font-size:15px;line-height:1.45;margin-top:4px'>{_h.escape(b.proposed_test)}</div>"
                        f"<div class='role' style='margin-top:8px'>{_h.escape(b.owner)}</div></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='eyebrow' style='margin-top:6px'>Human decision {chip('human')}</div>", unsafe_allow_html=True)
        note = st.text_input("Note (optional)", key="note", placeholder="e.g., checked the 06-07 number against dispatch", label_visibility="collapsed")
        c1, c2, c3 = st.columns(3)
        if c1.button("Approve", type="primary", width="stretch"):
            approve(res, "approved", note)
            st.session_state["decision"] = "approved"
        if c2.button("Reject", width="stretch"):
            approve(res, "rejected", note)
            st.session_state["decision"] = "rejected"
        if c3.button("Flag", width="stretch", help="This does not sound right: logs an objection for the reviewer"):
            approve(res, "flagged", note)
            st.session_state["decision"] = "flagged"
        if st.session_state.get("decision"):
            st.success(f"Recorded: {st.session_state['decision']}, with the evidence ids, in the review log.")
        else:
            st.caption("Nothing happens until a person decides. Flag means 'this does not sound right'.")
        p = st.session_state.get("plan")
        d1, d2 = st.columns(2)
        d1.download_button("One-page report", report_html(res, p).encode(), "friction_finder_brief.html", "text/html", width="stretch")
        d2.download_button("Brief (Markdown)", report_markdown(res, p).encode(), "friction_finder_brief.md", "text/markdown", width="stretch")
        st.caption(f"{'Model-written' if b.mode == 'llm' else 'Templated'} brief · " + " · ".join(b.check_notes))


def _signal_tab(res: Result):
    sig = [e for e in res.evidence if e.kind == "signal_check"]
    mix = [e for e in res.evidence if e.kind == "tenure_mix"]
    if sig:
        st.markdown(f"<div class='answer'><b>Signal check</b> {chip('computed')} &nbsp; {sig[0].statement}</div>", unsafe_allow_html=True)
        st.markdown("")
        st.dataframe(pd.DataFrame(sig[0].rows).rename(columns={"tenure_band": "Tenure band", "share_w1": "Share, Wave 1", "share_w2": "Share, Wave 2",
                                                               "company_band_mean": "Company mean for the band", "n_w1": "n, Wave 1", "n_w2": "n, Wave 2"}),
                     width="stretch", hide_index=True)
    elif mix:
        st.markdown(f"<div class='answer'><b>Who responded</b> {chip('computed')} &nbsp; {mix[0].statement}</div>", unsafe_allow_html=True)
    fig = _chart_mix(res)
    if fig:
        st.markdown("**Who responded, by tenure**")
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
    deltas = [e for e in res.evidence if e.kind == "survey_delta"]
    if deltas:
        st.markdown(f"**Items that moved** {chip('computed')} <span class='small'>team level: watch items, not findings; inference belongs at site level</span>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([r for e in deltas for r in e.rows]).rename(columns={"item": "Item", "label": "Label", "wave1": "Wave 1", "wave2": "Wave 2", "delta": "Change", "n1": "n, W1", "n2": "n, W2", "material": f"≥ {SURVEY_MATERIAL:.2f}"}),
                     width="stretch", hide_index=True)


def _charts_tab(res: Result):
    drawn = False
    out = _chart_survey(res)
    if out:
        fig, worst = out
        st.markdown("**Survey items for this team, Wave 1 vs Wave 2.** " + ("Largest material drops labelled: " + "; ".join(f"{k.upper()} = {v}" for k, v in worst.items()) if worst else "No item moved materially."))
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        drawn = True
    fig = _chart_ops(res)
    if fig:
        ops = [e for e in res.evidence if e.kind == "ops_hour"][0]
        st.markdown("**Late departures by hour band, before and after June 2026.** " + ("The band with the operational signal is labelled." if ops.value.get("signal") else "No band changed materially."))
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        drawn = True
    fig = _chart_heatmap(res)
    if fig:
        st.markdown(f"**Change in each item, by team (Wave 2 minus Wave 1).** Orange fell, teal rose. Teams under n = {config.MIN_N} are listed but never shown.")
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        drawn = True
    fig = _chart_site_items(res)
    if fig:
        st.markdown("**Site level, Wave 2 versus the company mean.** Teal is the strength, orange the two opportunities: the shape of Gallup's 'Interpreting Your Results' worksheet.")
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        drawn = True
    fig = _chart_tenure(res)
    if fig:
        st.markdown("**Grand mean by tenure, both waves.** The year-one effect Gallup described.")
        st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        drawn = True
    if not drawn:
        fig = _chart_mix(res)
        if fig:
            st.markdown("**Who responded, by tenure.**")
            st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        else:
            st.caption("No chart for this question.")


def _plan_tab(res: Result):
    st.caption("Gallup's State of the Team shape: one performance goal, one focus item, three or four immediate actions with owners, a review cadence, "
               "and the item's discussion questions quoted from Gallup's outline. Built only when the verdict is supported.")
    if st.session_state.get("plan") is None:
        if st.button("Build the action plan", type="primary"):
            with st.spinner("Drafting actions from the brief and the ownership directory..."):
                st.session_state["plan"] = plan(res, db)
    p = st.session_state.get("plan")
    if not p:
        return
    mode = "generated" if p.mode == "llm" else "templated"
    if st.session_state.get("decision") == "approved":
        st.success("Brief approved by the reviewer. The plan can go to the process owner.")
    else:
        st.warning("The brief is not yet approved. The plan stays a draft until a person approves the brief.")
    g1, g2 = st.columns(2, gap="large")
    g1.markdown(f"<div class='eyebrow'>Performance goal {chip('computed')}</div><p style='font-size:16px;line-height:1.45'>{_h.escape(p.goal)}</p>", unsafe_allow_html=True)
    g2.markdown(f"<div class='eyebrow'>Focus item {chip('computed')}</div><p style='font-size:16px;line-height:1.45'><b>{p.focus_item.upper()}</b> · {_h.escape(p.focus_label)}<br><span class='small'>the fallen item most relevant to the corroborated theme</span></p>", unsafe_allow_html=True)
    st.markdown(f"<div class='section'>Immediate actions {chip(mode)} <span class='small' style='font-family:Source Sans 3, sans-serif;font-weight:400'>owners from the ownership directory (computed); dates are two-week steps from the wave close</span></div>", unsafe_allow_html=True)
    st.markdown("| # | Action | Owner | Due |\n|---|---|---|---|\n" +
                "\n".join(f"| {i + 1} | {x['action'].replace('|', '/')} | {x['owner_role']}, {x['owner_name']} | {x['due']} |" for i, x in enumerate(p.actions)))
    for n in p.check_notes:
        st.caption(n)
    m1, m2 = st.columns(2, gap="large")
    m1.markdown(f"<div class='eyebrow'>Success measure {chip('computed')}</div><p style='font-size:15px;line-height:1.45'>{_h.escape(p.success_measure)}</p>", unsafe_allow_html=True)
    m2.markdown(f"<div class='eyebrow'>Review and recalibrate {chip('templated')}</div><p style='font-size:15px;line-height:1.45'>{_h.escape(p.review_cadence)}</p>", unsafe_allow_html=True)
    st.markdown(f"<div class='section'>Questions for the team conversation {chip('retrieved')}</div>", unsafe_allow_html=True)
    for q in p.team_questions:
        st.markdown(f"- {q}")
    st.caption(f"Source: {p.questions_source}")
    st.download_button("Download the one-page report with the plan (HTML)", report_html(res, p).encode(), "friction_finder_brief_and_plan.html", "text/html")


def _appendix_tab(res: Result):
    st.caption("Technical appendix. Computed = SQL over suppressed views plus Python. Retrieved = verbatim text found by similarity. Nothing here is written by the model. "
               "Every number in the brief traces to one of the queries below; respondent-level rows are never queried. Run: " + " · ".join(res.notes) + ".")
    st.dataframe(pd.DataFrame([{"id": e.id, "origin": e.origin, "kind": e.kind, "statement": e.statement, "source": e.source} for e in res.evidence]),
                 width="stretch", hide_index=True)
    st.markdown("**Show me the queries**")
    for e in res.evidence:
        if e.sql:
            with st.expander(f"[{e.id}] {e.kind}: {e.statement[:90]}"):
                st.code(e.sql, language="sql")
                if e.rows:
                    st.dataframe(pd.DataFrame(e.rows), width="stretch", hide_index=True)


# ------------------------------------------------------------------ result
if res:
    eyebrow, title, sub, kind = _headline(res)
    pill = {"teal": "Supported hypothesis", "orange": "Insufficient evidence" if res.status != "refused" else "Declined", "grey": "Watch list"}[kind]
    if res.assessment and res.assessment.verdict == "suppressed_insufficient":
        pill = f"Hidden under n = {config.MIN_N}"
    if res.assessment is None and res.status != "refused":
        pill = "Computed"
    where = _scope_name(res)
    st.markdown(f"<div class='memo-head fade'><div class='eyebrow'>{eyebrow}{' · ' + _h.escape(where) if where else ''} · Wave 2, September 2026</div>"
                f"<div class='memo-title'>{_h.escape(title)}</div>"
                f"<div class='memo-sub'><span class='pill {kind if kind != 'teal' else ''}'>{pill}</span> &nbsp;{_h.escape(sub)}</div></div>", unsafe_allow_html=True)
    if res.status != "refused":
        _render_kpis(_kpis(res))
        if res.assessment:
            _checklist(res.assessment)
        if needs_brief(res):
            with st.spinner("Writing the brief from the evidence (about 20 seconds with the model)..."):
                write_brief(res)
        if res.brief:
            _memo(res)
        elif res.message:
            st.markdown(f"<div class='answer'>{_h.escape(res.message)}</div>", unsafe_allow_html=True)
            st.markdown("")
        names = []
        if any(e.kind in ("survey_table", "ops_hour", "site_heatmap", "tenure_pattern", "tenure_mix") for e in res.evidence):
            names.append("Charts")
        if res.assessment and res.assessment.verdict == "supported":
            names.append("Action plan")
        if any(e.kind in ("signal_check", "tenure_mix") for e in res.evidence) and res.scope and res.scope.intent in ("review_decline_real", "diagnose_drop"):
            names.append("Signal check")
        names.append("Evidence and queries")
        tabs = st.tabs(names)
        for name, tab in zip(names, tabs):
            with tab:
                {"Charts": _charts_tab, "Action plan": _plan_tab, "Signal check": _signal_tab, "Evidence and queries": _appendix_tab}[name](res)

# ------------------------------------------------------------------ follow-up chat, grounded in what is on screen
st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown(f"<div class='eyebrow'>Ask about {'this brief' if res else 'the tool'} {chip('generated')}</div>"
                "<div class='small' style='margin:2px 0 8px 0'>Follow-up questions are answered only from what is on screen: the evidence register, the brief, the data specification, and the "
                "rules of the workflow. Every number in an answer is checked against them; anything else gets 'not on screen'.</div>", unsafe_allow_html=True)
    chat = st.session_state.setdefault("chat", [])
    for m in chat:
        with st.chat_message(m["role"], avatar=("🧑‍💼" if m["role"] == "user" else "🔎")):
            st.markdown(m["content"])
            if m.get("notes"):
                st.caption(" · ".join(m["notes"]))
    examples = (["Why is the handoff the likely obstacle and not staffing?", "What does 'material' mean here?", "What would change the verdict?"] if res and res.brief
                else ["How does the tool decide a verdict?", "What data is this built on, and what was planted?", "What happens for a team with fewer than four people?"])
    ec = st.columns(len(examples))
    asked = None
    for col, ex in zip(ec, examples):
        if col.button(ex, key="ex_" + ex, width="stretch"):
            asked = ex
    typed = st.chat_input("Ask a follow-up about the brief, the data, or how the tool works")
    asked = asked or typed
    if asked:
        chat.append({"role": "user", "content": asked})
        with st.spinner("Answering from what is on screen..."):
            out = chat_answer(asked, res, st.session_state.get("plan"), chat)
        chat.append({"role": "assistant", "content": out["answer"], "notes": [("model-written" if out["mode"] == "llm" else "templated")] + out["notes"]})
        st.session_state["chat"] = chat[-12:]
        st.rerun()

# ------------------------------------------------------------------ footer: how it works, evals, review log, data, changes
st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
st.markdown("<div class='eyebrow ink'>Under the hood</div>", unsafe_allow_html=True)
with st.expander("How it works: one workflow, five fixed steps, then a person decides"):
    st.markdown("""<div class='flow'>
<div class='step model'><b>1 Scope</b>the model reads the question into a schema; unknown names are declined</div>
<div class='step'><b>2 Analyze</b>SQL over suppressed views; Python computes every number</div>
<div class='step'><b>3 Retrieve</b>comments and procedures by similarity, quoted verbatim; themes counted</div>
<div class='step'><b>4 Assess</b>thresholds decide the verdict; owner only if supported</div>
<div class='step model'><b>5 Explain</b>the model writes the brief; a checker rejects invented numbers, bad citations, causal words</div>
<div class='step human'><b>Decide</b>a person approves, rejects, or flags; the plan is a draft until then</div>
</div>""", unsafe_allow_html=True)
    st.markdown(f"""
| Step | What happens | Component |
|---|---|---|
| 1 Scope | The model reads the question into a fixed schema (site, team, items, intent). Names are checked against the tables; unknown sites or data we do not have are declined. | textual (model) + checks |
| 2 Analyze | SQL over views that hide teams under n = {config.MIN_N}; Python computes changes, rates, staffing ratios, and the who-responded adjustment. | deterministic |
| 3 Retrieve | Comments and procedures are found by similarity (embeddings) and quoted verbatim; comment themes are counted in code. | deterministic + retrieval |
| 4 Assess | The verdict comes from thresholds: an item fell ≥ {SURVEY_MATERIAL:.2f}; a late-departure band rose ≥ {OPS_SIGNAL_ABS * 100:.0f} points and ≥ {OPS_SIGNAL_RATIO}×; a theme has ≥ {COMMENT_BREADTH} separate comments; staffing under {STAFFING_LOW * 100:.0f}% is a competing explanation. No corroboration = "insufficient". | deterministic |
| 5 Explain | The model writes the brief from the evidence it is handed. A checker rejects unknown citations, numbers not in the evidence, causal words, and any owner when the verdict is not supported; two failures and a templated brief is shown. | textual (model) + checks |
| Decide | A person approves, rejects, or flags. The action plan is built only for supported verdicts. Nothing happens otherwise. | human |

Team-level results are watch items (small n); comparisons and inference belong at site level. There is deliberately no autonomous action: an AI-assisted workflow with a reasoning step and human approval, not an agent that acts.
""")

with st.expander("How we test it: gold questions scored as a confusion matrix over the planted patterns"):
    st.caption("Positive cases = a planted, corroborated problem (found = TP, missed = FN). Negative cases = a blip, one loud comment, a suppressed team, data we do not have "
               "(declined or 'insufficient' with no owner = TN, an obstacle named = FP). Misses are the outcome we weight highest. Lookups are pass or fail.")
    files = sorted(RESULTS.glob("latest_*.json")) if RESULTS.exists() else []
    if files:
        rows = []
        for f in files:
            s = json.loads(f.read_text())
            m = s["matrix"]
            rows.append({"model": s["model"], "retrieval": s["retrieval"], "passed": f"{s['passed']}/{s['total']}", "TP": m["TP"], "FN": m["FN"] + m.get("FN*", 0), "FP": m["FP"], "TN": m["TN"],
                         "lookups": f"{s['lookups_passed']}/{s['lookups_total']}", "briefs regenerated or fallen back": s["briefs_regenerated_or_fallback"],
                         "seconds": s["seconds"], "run": s["ts"][:16].replace("T", " ")})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        pick = st.selectbox("Per-question detail", [f.name for f in files], label_visibility="collapsed")
        s = json.loads((RESULTS / pick).read_text())
        st.dataframe(pd.DataFrame([{"id": r["id"], "class": r["class"], "outcome": r["outcome"], "passed": r["passed"], "status": r["status"], "verdict": r["verdict"],
                                    "brief": r["brief_mode"], "failed checks": ", ".join(k for k, v in r["checks"].items() if not v), "s": r["seconds"], "question": r["question"]} for r in s["rows"]]),
                     width="stretch", hide_index=True)
    else:
        st.caption("No saved run yet.")
    if st.button("Run the evals now" + (" (about two minutes with the model)" if config.has_key() else " (rules mode, seconds)")):
        with st.spinner("Running the gold questions..."):
            s = evaluate(db, retriever)
        st.write(f"{s['passed']}/{s['total']} passed · matrix {s['matrix']} · saved to evals/results/")
        st.rerun()

with st.expander("Review log: every approval, rejection, and flag"):
    log = review_log()
    if log:
        st.dataframe(pd.DataFrame([{"when": r["ts"][:16].replace("T", " "), "who": r.get("who"), "decision": r["decision"], "verdict": r.get("verdict"),
                                    "brief": r.get("brief_mode"), "note": r.get("note"), "question": r["question"]} for r in reversed(log)]),
                     width="stretch", hide_index=True)
        st.caption(f"{len(log)} decisions. Flags are the user feedback loop; the reviewer reads them here.")
    else:
        st.caption("No decisions recorded yet.")

with st.expander("The data: what feeds the tool, and what was planted"):
    spec = ROOT / "DATA_SPEC.md"
    st.markdown(spec.read_text() if spec.exists() else "Run data/generate.py to produce DATA_SPEC.md.")

with st.expander("The business case and the pilot scorecard (hypotheses, to be measured)"):
    st.markdown(f"""
**Who.** The user is the site or shift manager. The buyer is the client's head of operations or of HR. The data owners are operations
(dispatch or warehouse exports) and HR (the survey vendor's team-level export). Adoption is approved by the HR business partner with the site
operations director. Channel hypothesis: sold with the engagement-survey debrief or as an operations-analytics add-on; sponsorship is not a channel.

**What it replaces.** Today the link between a fallen score and a broken process is made by consultants reading signals during executive briefings,
or not at all; comments go unread at scale; action planning stalls on follow-through.

**Pilot entry criterion.** A client where manual reading fails: enough teams, waves, and comments that nobody reads them all, and an operation that
logs daily work (warehouses, logistics, call centers). Knowledge-work firms with only a survey do not qualify.

**Pilot scorecard, measured, not claimed.** Time from results release to an owned action; share of briefs approved, rejected, flagged; share of proposed
tests actually run and re-measured; movement in the operational rate and the focus item at the next wave; manager rating of the State of the Team
conversation. No time-saved claim until the pilot measures it.

**What would rule it out.** No operational records at the client; briefs mostly rejected or flagged; no movement at the next wave.
""")

with st.expander("Assumptions and integration options (what we chose, and why)"):
    st.markdown("""
| Question | Options considered | Chosen for the pilot | Why |
|---|---|---|---|
| How operational records arrive | manual CSV export; scheduled export to a shared folder; API integration with dispatch or the warehouse system | manual CSV export, approved by the business-unit owner | fastest to start; the owner stays in control; integration is a later decision once value is shown |
| How survey results arrive | the vendor's team-level export; a vendor API | team-level export in the vendor's shape | aggregates only, never respondent rows; real data can replace the synthetic tables without code changes |
| Where the reporting threshold lives | in prompts; in code; in the database views | the database views | a prompt cannot bypass it; comments under the threshold are never indexed |
| What the model may do | write numbers; decide verdicts; write text | write text only, checked | numbers and verdicts come from code; the checker rejects invented numbers and causal words |
| Which model | gpt-5 vs gpt-5-mini on the GW resource | gpt-5-mini | same verdicts on the gold set, about half the latency; comparison saved in the evals |
| Who acts | the tool; the manager; the process owner | the manager approves, the process owner acts | no autonomous action by design, tied to the risk tier |
""")

with st.expander("What the judges told us since Sept 14, 2026, and what changed"):
    st.dataframe(pd.DataFrame([
        ("O'Neal Keegan, Gallup (Sept 14)", "What do you do for managers with fewer than four people? How would operational records connect?", "Suppression in the SQL views with site roll-up; CSV upload of delay records; honeymoon effect in the synthetic data", "app/db.py, sidebar, data/generate.py"),
        ("Katie Fullowan, Freddie Mac (Sept 14)", "Show the human in the loop and spot-check outputs with numbers; surveys carry response bias", "Approve / reject / flag log with evidence ids; evals; response bias stated in every brief's limits", "Memo, review log"),
        ("Jeremy Lederman, MITRE (Sept 15)", "What's the data? Don't attribute causation to a blip. Automate a one-pager", "Data specification page; red-team case P9 with an 'insufficient' verdict; one-page HTML report", "DATA_SPEC.md, assess(), report"),
        ("Robert Chang, FI Consulting (Sept 15)", "One employee writing a page will make the model over-index; weight by breadth", "Comment themes counted in code; a theme corroborates only with three or more separate comments; red-team case P10", "retrieve(), assess()"),
        ("Matthew Finan, Mizuho (Sept 15)", "Score test cases as a confusion matrix, weight misses highest; use the model's reasoning over text; test gpt-5 vs gpt-5-mini", "Evals report TP/FN/FP/TN; model writes text only, code computes numbers; saved runs per model", "evals/"),
        ("Dmitri Kaznachey, FI Consulting (Sept 16)", "Offer the playbook questions, not only free text; team n is small; say deterministic vs textual", "Playbook cards for the three features; team-level = watch items, site-level inference; computed / generated labels", "This screen"),
        ("Taher Jamshidi, Promontory AI (Sept 16)", "A flag-this feedback loop, an admin review, transparency about what is AI, a one-sentence idea statement", "Flag button; review log; labels on every element; idea statement in the masthead", "This screen"),
        ("Patrick Hall, instructor (Sept 14)", "A professional UI with about three strong analytics features, more than a chatbot", "Diagnose, check the signal, act and review, on one interface with charts, tables, upload, and report generation", "This screen"),
    ], columns=["Who", "What they said", "What changed", "Where"]), width="stretch", hide_index=True)
