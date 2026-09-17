"""Friction Finder screen.  Run:  streamlit run app/ui.py

Three features on one interface (instructor, Sept 14, 2026): diagnose, check the signal, act and
review. Every element is labelled computed, retrieved, generated, or templated (judges Jamshidi
and Kaznachey, Sept 16). A person approves, rejects, or flags every brief."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `streamlit run app/ui.py` can import `app`

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import config
from app.agent import (COMMENT_BREADTH, MIX_EXPLAINS, OPS_SIGNAL_ABS, OPS_SIGNAL_RATIO, STAFFING_LOW, SURVEY_MATERIAL, Result,
                       approve, plan, report_html, report_markdown, review_log, run)
from app.db import DB
from app.retrieval import Retriever
from evals.run_evals import RESULTS, evaluate

st.set_page_config(page_title="Friction Finder", page_icon="🔎", layout="wide", initial_sidebar_state="expanded")

SLATE, TEAL, ORANGE, LIGHT, MUTED, GRID, SURFACE = "#1B3A4B", "#1F8FA8", "#C8553D", "#B9C6CC", "#6E7B85", "#E8ECEF", "#FFFFFF"  # teal+orange validated (dataviz); LIGHT = neutral reference series
ROOT = Path(__file__).resolve().parents[1]

st.markdown(f"""
<style>
  .stApp h1 {{ color: {SLATE}; margin-bottom: 0; }}
  .tag {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; color:white; background:{ORANGE}; letter-spacing:.5px; margin-right:4px; }}
  .tag-mid {{ background:{TEAL}; }} .tag-grey {{ background:{MUTED}; }} .tag-slate {{ background:{SLATE}; }}
  .chip {{ display:inline-block; padding:1px 7px; border-radius:9px; font-size:10px; font-weight:700; letter-spacing:.5px; color:white; vertical-align:middle; margin-left:6px; }}
  .chip-computed {{ background:{TEAL}; }} .chip-generated {{ background:{ORANGE}; }} .chip-templated {{ background:{SLATE}; }} .chip-retrieved {{ background:{MUTED}; }} .chip-human {{ background:#5B7A2F; }}
  .ev {{ font-family: ui-monospace, Menlo, monospace; font-size:11px; color:{MUTED}; }}
  .verdict {{ border-left:5px solid {TEAL}; background:#EAF0F2; padding:10px 14px; border-radius:4px; margin:6px 0 10px 0; }}
  .verdict.warn {{ border-left-color:{ORANGE}; }}
  .verdict b {{ color:{SLATE}; }}
  .lead {{ font-size:16px; color:{SLATE}; }}
  .small {{ font-size:12px; color:{MUTED}; }}
  div[data-testid="stExpander"] summary p {{ font-weight:600; color:{SLATE}; }}
</style>
""", unsafe_allow_html=True)


def chip(kind: str) -> str:
    return f"<span class='chip chip-{kind}'>{kind.upper()}</span>"


@st.cache_resource(show_spinner="Loading synthetic data, views, and documents...")
def _load():
    db = DB()
    return db, Retriever(db)


db, retriever = _load()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("<span class='tag'>SYNTHETIC DATA</span><span class='tag tag-mid'>FICTIONAL COMPANY</span>", unsafe_allow_html=True)
    st.markdown("**Northline Logistics** (does not exist). 3 sites, 24 teams, 2 survey waves, 189 employees.")
    n_ops = db.con.execute("SELECT COUNT(*) FROM ops_daily").fetchone()[0]
    st.caption(f"{n_ops:,} daily operations rows" + (f" (incl. {db.uploaded_ops_rows:,} uploaded)" if db.uploaded_ops_rows else "") +
               f" · 311 survey responses · 55 comments · reporting threshold n ≥ {config.MIN_N}")
    st.divider()
    st.markdown("**Status**")
    key = config.has_key()
    st.write(("Model: " + config.MODEL + " (GW Azure OpenAI)") if key else "Model: no key, rules + templated text")
    st.write(f"Retrieval: {retriever.mode}")
    st.caption("Numbers never come from the model. The model reads the question and writes text from evidence it is handed; every draft is checked.")
    st.divider()
    st.markdown("**Upload operational records (CSV)**")
    st.caption("How a client's own delay records enter in a pilot: an export from dispatch or the warehouse system, approved by its owner. Columns: date, site_id, shift, hour_band, departures, late_departures, rework_count.")
    template = pd.DataFrame([{"date": "2026-09-11", "site_id": 1, "shift": "Night", "hour_band": "06-07",
                              "departures": 24, "late_departures": 6, "rework_count": 1}])
    st.download_button("Download CSV template", template.to_csv(index=False).encode(), "ops_template.csv", "text/csv", width="stretch")
    up = st.file_uploader("Choose a CSV", type=["csv"], label_visibility="collapsed")
    if up is not None and st.session_state.get("last_upload") != up.name + str(up.size):
        try:
            n = db.add_ops_upload(pd.read_csv(up))
            st.session_state["last_upload"] = up.name + str(up.size)
            st.success(f"Added {n} rows. They are in the operational evidence of the next question.")
        except Exception as e:
            st.error(f"Upload rejected: {e}")
    st.divider()
    st.caption("Built with the tools we were given: the group's GW Azure OpenAI resource, gpt-5-mini, reasoning effort minimal (scope) and low (writing). "
               "A stronger model would change the wording of briefs, not the numbers or the verdicts.")

# ------------------------------------------------------------------ header
st.title("Friction Finder")
st.markdown("<p class='lead'>Helps a <b>site or shift manager</b> decide <b>which obstacle to test first</b> after an engagement score falls, "
            "by answering <b>where did we drop, is it real, what is behind it, who owns it, what do we do</b> from "
            "<b>survey aggregates, operational records, procedures, and open-text comments</b>.</p>", unsafe_allow_html=True)
st.caption("Starting segment: operations-heavy workplaces where daily work is logged (warehouses, logistics, call centers). "
           "One workflow, five fixed steps. A person approves every brief; the tool takes no action on its own.")

# ------------------------------------------------------------------ playbook
PLAYBOOK = {
    "1 · Diagnose": ("Where did we drop, and what is behind it?", [
        ("Where did we drop? (Richmond)", "Where did scores drop across Richmond?"),
        ("Why did the night shift drop?", "Why did the Richmond night shift's scores drop and why are deliveries late?"),
        ("A team under 4 respondents", "Why did the Richmond Dispatch Day team's scores drop?"),
    ]),
    "2 · Check the signal": ("Is the change real, or a change in who responded?", [
        ("Is the decline real?", "Is the Norfolk Day B decline real or did different people respond?"),
        ("Scores by tenure", "How do scores vary by tenure?"),
    ]),
    "3 · Act and review": ("Who owns it, and what do we do first?", [
        ("Who owns the handoff?", "Who owns the shift handoff process at Richmond?"),
        ("Score and respondents, one team", "What was the Richmond Night A score on materials and equipment in wave 2, and how many people responded?"),
    ]),
}
REDTEAM = [
    ("A blip with no operations signal", "Why did the Roanoke Day C team's scores drop?"),
    ("One loud comment", "Why did the Norfolk night shift's scores drop?"),
    ("Data we do not have", "What caused turnover on the Norfolk night shift?"),
    ("A site we do not have", "Why did the Denver site drop?"),
]


def _ask(q: str):
    with st.spinner("Scoping, analyzing, retrieving, assessing, writing..."):
        st.session_state["result"] = run(q, db, retriever)
    st.session_state["decision"] = None
    st.session_state["plan"] = None


cols = st.columns(3, gap="medium")
for col, (title, (caption, buttons)) in zip(cols, PLAYBOOK.items()):
    with col:
        st.markdown(f"**{title}**")
        st.caption(caption)
        for label, q in buttons:
            if st.button(label, key="pb_" + label, width="stretch"):
                st.session_state["question"] = q
                _ask(q)
with st.expander("Red-team cases: what it refuses to do"):
    rc = st.columns(len(REDTEAM))
    for col, (label, q) in zip(rc, REDTEAM):
        if col.button(label, key="rt_" + label, width="stretch"):
            st.session_state["question"] = q
            _ask(q)

qcol, bcol = st.columns([6, 1], vertical_alignment="bottom")
question = qcol.text_input("Or ask in your own words", key="question", placeholder="e.g., Why did the Richmond night shift's scores drop and why are deliveries late?")
if bcol.button("Ask", type="primary", width="stretch") and question.strip():
    _ask(question.strip())

res: Result | None = st.session_state.get("result")


# ------------------------------------------------------------------ charts
def _style(fig, height=340, ytitle=None, xtitle=None):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                      font=dict(family="Calibri, Arial, sans-serif", color=SLATE, size=12),
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
                text=[f"{d:+.2f}" if i in worst else "" for i, d in zip(piv.item, piv.delta)], textposition="outside", textfont=dict(color=SLATE, size=11),
                customdata=piv.delta, hovertemplate="%{x} · Wave 2: %{y:.2f} (change %{customdata:+.2f})<extra></extra>")
    fig.update_layout(barmode="group", yaxis=dict(range=[1, 5.2]))
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
    vals = [ev[0].value.get(b) for b in order]
    fig = go.Figure(go.Bar(x=order, y=vals, marker_color=[ORANGE, TEAL, TEAL, TEAL], marker_line_width=0,
                           text=[f"{v:.2f}" if v is not None else "" for v in vals], textposition="outside", hovertemplate="%{x}: %{y:.2f}<extra></extra>"))
    fig.update_layout(yaxis=dict(range=[3, 4.6]))
    return _style(fig, 320, "Grand mean (1 to 5)", "Tenure band")


def _chart_mix(res: Result):
    ev = [e for e in res.evidence if e.kind == "tenure_mix"]
    if not ev:
        return None
    df = pd.DataFrame(ev[0].rows)
    fig = go.Figure()
    for band, color in (("under_1", ORANGE), ("1_to_3", TEAL), ("3_to_10", "#5FA9BC"), ("over_10", LIGHT)):
        sub = df[df.tenure_band == band].set_index("wave_id").n.reindex([1, 2]).fillna(0)
        fig.add_bar(name=band, x=["Wave 1", "Wave 2"], y=sub.values, marker_color=color, marker_line=dict(color=SURFACE, width=2),
                    hovertemplate=band + ": %{y:.0f} respondents<extra></extra>")
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
    fig = go.Figure(go.Heatmap(z=z, x=items, y=ylab, zmin=-1, zmax=1, zmid=0,
                               colorscale=[[0, ORANGE], [0.5, "#F2F4F5"], [1, TEAL]],
                               text=[[f"{v:+.2f}" if v is not None else "" for v in row] for row in z], texttemplate="%{text}", textfont=dict(size=11),
                               xgap=2, ygap=2, hoverongaps=False, hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
                               colorbar=dict(title="Change<br>W1→W2", thickness=10)))
    fig.update_yaxes(autorange="reversed")
    return _style(fig, 60 + 28 * len(ylab), None, "Survey item")


def _chart_site_items(res: Result):
    ev = [e for e in res.evidence if e.kind == "site_items"]
    if not ev:
        return None
    df = pd.DataFrame(ev[0].rows).sort_values("vs_company")
    colors = [ORANGE if i in set(ev[0].value.get("opportunities", [])) else (TEAL if i == ev[0].value.get("strength") else LIGHT) for i in df.item]
    fig = go.Figure(go.Bar(x=df.item, y=df.vs_company, marker_color=colors, marker_line_width=0, text=[f"{v:+.2f}" for v in df.vs_company], textposition="outside",
                           customdata=df.item_label, hovertemplate="%{x} %{customdata}: %{y:+.2f} vs company<extra></extra>"))
    fig.add_hline(y=0, line_color=MUTED, line_width=1)
    return _style(fig, 300, "Wave 2 vs company mean", "Survey item")


# ------------------------------------------------------------------ result
def _verdict_box(res: Result):
    a = res.assessment
    if not a:
        return
    ok = a.verdict == "supported"
    reasons = "".join(f"<li>{r}</li>" for r in a.reasons)
    st.markdown(f"<div class='verdict {'ok' if ok else 'warn'}'><b>{'Verdict' if ok else 'Verdict'}</b> {chip('computed')} &nbsp; {a.label}"
                f"<ul class='small' style='margin:6px 0 0 16px'>{reasons}</ul></div>", unsafe_allow_html=True)


def _claims(items):
    for i in items:
        st.markdown(f"- {i.get('claim')} <span class='ev'>[{', '.join(i.get('evidence_ids', []))}]</span>", unsafe_allow_html=True)


def _brief_tab(res: Result):
    b = res.brief
    mode = "generated" if b.mode == "llm" else "templated"
    left, right = st.columns([3, 1.15], gap="large")
    with left:
        st.markdown(f"#### Likely obstacle {chip(mode)}", unsafe_allow_html=True)
        st.markdown(b.obstacle)
        st.markdown(f"**Evidence for** {chip(mode)} <span class='small'>each claim cites computed or retrieved evidence ids</span>", unsafe_allow_html=True)
        _claims(b.evidence_for)
        st.markdown(f"**Evidence against, competing explanations** {chip(mode)}", unsafe_allow_html=True)
        _claims(b.evidence_against)
        st.markdown(f"**What is missing** {chip(mode)}", unsafe_allow_html=True)
        for m in b.missing:
            st.markdown(f"- {m}")
        has_owner = any(e.kind == "owner" for e in res.evidence)
        st.markdown(f"**Process owner** {chip('computed') if has_owner else chip(mode)}<br>{b.owner}", unsafe_allow_html=True)
        st.markdown(f"**Proposed test** {chip(mode)}<br>{b.proposed_test}", unsafe_allow_html=True)
        st.caption(f"Limits: {b.limits}")
    with right:
        st.markdown(f"<span class='tag {'tag-mid' if b.mode == 'llm' else 'tag-slate'}'>{'MODEL-WRITTEN BRIEF' if b.mode == 'llm' else 'TEMPLATED BRIEF'}</span>", unsafe_allow_html=True)
        for n in b.check_notes:
            st.caption(n)
        st.markdown(f"**Human decision** {chip('human')}", unsafe_allow_html=True)
        note = st.text_input("Note (optional)", key="note", placeholder="e.g., checked the 06-07 number against dispatch")
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
            st.success(f"Recorded: {st.session_state['decision']}. Logged with the evidence ids to approvals.jsonl.")
        else:
            st.caption("Nothing happens until a person decides. Flag = 'this does not sound right'.")
        p = st.session_state.get("plan")
        st.download_button("Download one-page report (HTML)", report_html(res, p).encode(), "friction_finder_brief.html", "text/html", width="stretch")
        st.download_button("Download brief (Markdown)", report_markdown(res, p).encode(), "friction_finder_brief.md", "text/markdown", width="stretch")


def _signal_tab(res: Result):
    sig = [e for e in res.evidence if e.kind == "signal_check"]
    mix = [e for e in res.evidence if e.kind == "tenure_mix"]
    if sig:
        v = sig[0].value
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Grand mean, Wave 1", f"{v['gm_w1']:.2f}", help=f"n={v['n_w1']}")
        m2.metric("Grand mean, Wave 2", f"{v['gm_w2']:.2f}", f"{v['observed']:+.2f}", delta_color="normal", help=f"n={v['n_w2']}")
        m3.metric("Expected from who responded", f"{v['expected_from_mix']:+.2f}", help="Change in tenure mix × company-wide band means (shift-share)")
        m4.metric("Remaining after adjustment", f"{v['residual']:+.2f}", help=f"Below {MIX_EXPLAINS:.2f} = within normal variation")
        st.markdown(f"<div class='verdict {'warn' if v['verdict'] != 'real' else 'ok'}'><b>Signal check</b> {chip('computed')} &nbsp; {sig[0].statement}</div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(sig[0].rows).rename(columns={"tenure_band": "Tenure band", "share_w1": "Share W1", "share_w2": "Share W2",
                                                               "company_band_mean": "Company mean (band)", "n_w1": "n W1", "n_w2": "n W2"}),
                     width="stretch", hide_index=True)
    elif mix:
        st.markdown(f"<div class='verdict'><b>Who responded</b> {chip('computed')} &nbsp; {mix[0].statement}</div>", unsafe_allow_html=True)
    fig = _chart_mix(res)
    if fig:
        st.markdown("**Who responded, by tenure band**")
        st.plotly_chart(fig, width="stretch")
    deltas = [e for e in res.evidence if e.kind == "survey_delta"]
    if deltas:
        st.markdown(f"**Items that moved** {chip('computed')} <span class='small'>team level: watch items, not findings; inference belongs at site level</span>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([r for e in deltas for r in e.rows]).rename(columns={"item": "Item", "label": "Label", "wave1": "W1", "wave2": "W2", "delta": "Change", "n1": "n W1", "n2": "n W2", "material": f"≥ {SURVEY_MATERIAL:.2f}"}),
                     width="stretch", hide_index=True)


def _charts_tab(res: Result):
    drawn = False
    out = _chart_survey(res)
    if out:
        fig, worst = out
        st.markdown("**Survey items for this team, Wave 1 vs Wave 2.** " + ("Largest material drops labelled: " + "; ".join(f"{k} = {v}" for k, v in worst.items()) if worst else "No item moved materially."))
        st.plotly_chart(fig, width="stretch")
        drawn = True
    fig = _chart_ops(res)
    if fig:
        ops = [e for e in res.evidence if e.kind == "ops_hour"][0]
        st.markdown("**Late departures by hour band, before and after June 2026.** " + ("The band with the operational signal is labelled." if ops.value.get("signal") else "No band changed materially."))
        st.plotly_chart(fig, width="stretch")
        drawn = True
    fig = _chart_heatmap(res)
    if fig:
        st.markdown(f"**Change in each item, by team (Wave 2 minus Wave 1).** Orange = fell, teal = rose. Teams under n={config.MIN_N} are listed but never shown.")
        st.plotly_chart(fig, width="stretch")
        drawn = True
    fig = _chart_site_items(res)
    if fig:
        st.markdown("**Site level, Wave 2 versus the company mean.** Teal = strength, orange = the two opportunities (the shape of Gallup's 'Interpreting Your Results' worksheet).")
        st.plotly_chart(fig, width="stretch")
        drawn = True
    fig = _chart_tenure(res)
    if fig:
        st.markdown("**Grand mean by tenure band, both waves.** The year-one effect Gallup described.")
        st.plotly_chart(fig, width="stretch")
        drawn = True
    if not drawn and not any(e.kind == "tenure_mix" for e in res.evidence):
        st.caption("No chart for this question.")
    elif not drawn:
        fig = _chart_mix(res)
        st.markdown("**Who responded, by tenure band.**")
        st.plotly_chart(fig, width="stretch")


def _plan_tab(res: Result):
    st.caption("Feature 3. Gallup's State of the Team shape: one performance goal, one focus item, three or four immediate actions with owners, "
               "a review cadence, and the item's discussion questions quoted from Gallup's outline. Built only when the verdict is supported.")
    if st.session_state.get("plan") is None:
        if st.button("Build the action plan", type="primary"):
            with st.spinner("Drafting actions from the brief and the ownership directory..."):
                st.session_state["plan"] = plan(res, db)
    p = st.session_state.get("plan")
    if not p:
        return
    mode = "generated" if p.mode == "llm" else "templated"
    dec = st.session_state.get("decision")
    if dec == "approved":
        st.success("Brief approved by the reviewer. The plan can go to the process owner.")
    else:
        st.warning("The brief is not yet approved. The plan stays a draft until a person approves the brief.")
    st.markdown(f"**Performance goal** {chip('computed')}<br>{p.goal}", unsafe_allow_html=True)
    st.markdown(f"**Focus item** {chip('computed')}<br>{p.focus_item.upper()}: {p.focus_label} (the fallen item most relevant to the corroborated theme)", unsafe_allow_html=True)
    st.markdown(f"**Immediate actions** {chip(mode)} <span class='small'>owners come from the ownership directory (computed); dates are two-week steps from the wave close</span>", unsafe_allow_html=True)
    st.markdown("| # | Action | Owner | Due |\n|---|---|---|---|\n" +
                "\n".join(f"| {i + 1} | {x['action'].replace('|', '/')} | {x['owner_role']}, {x['owner_name']} | {x['due']} |" for i, x in enumerate(p.actions)))
    for n in p.check_notes:
        st.caption(n)
    st.markdown(f"**Success measure** {chip('computed')}<br>{p.success_measure}", unsafe_allow_html=True)
    st.markdown(f"**Review and recalibrate** {chip('templated')}<br>{p.review_cadence}", unsafe_allow_html=True)
    st.markdown(f"**Questions for the team conversation** {chip('retrieved')}", unsafe_allow_html=True)
    for q in p.team_questions:
        st.markdown(f"- {q}")
    st.caption(f"Source: {p.questions_source}")
    st.download_button("Download one-page report with the plan (HTML)", report_html(res, p).encode(), "friction_finder_brief_and_plan.html", "text/html")


def _evidence_tab(res: Result):
    st.caption("Computed = SQL over suppressed views plus Python. Retrieved = verbatim text found by similarity. Nothing here is written by the model.")
    st.dataframe(pd.DataFrame([{"id": e.id, "origin": e.origin, "kind": e.kind, "statement": e.statement, "source": e.source} for e in res.evidence]),
                 width="stretch", hide_index=True)


def _sql_tab(res: Result):
    st.caption("Every number in the brief traces to one of these queries. Respondent-level rows are never queried; the views apply the reporting threshold before any model call.")
    for e in res.evidence:
        if e.sql:
            with st.expander(f"[{e.id}] {e.kind}: {e.statement[:90]}"):
                st.code(e.sql, language="sql")
                if e.rows:
                    st.dataframe(pd.DataFrame(e.rows), width="stretch", hide_index=True)


if res:
    st.caption(" · ".join(res.notes))
    if res.status == "refused":
        st.warning(f"**Declined.** {res.message}")
    elif res.status == "suppressed":
        st.info(f"**Reporting threshold applied.** Team-level results are hidden for teams with fewer than {config.MIN_N} respondents. Site-level evidence is used instead.")
    _verdict_box(res)
    if res.brief is None and res.status == "ok" and res.message:
        st.markdown(f"<div class='verdict'><b>Answer</b> {chip('computed')}<br>{res.message}</div>", unsafe_allow_html=True)

    if res.evidence:
        names = []
        if res.brief:
            names.append("Brief")
        if any(e.kind in ("signal_check", "tenure_mix") for e in res.evidence):
            names.append("Signal check")
        names += ["Charts", "Evidence", "Show me (SQL)"]
        if res.assessment and res.assessment.verdict == "supported":
            names.append("Action plan")
        tabs = st.tabs(names)
        for name, tab in zip(names, tabs):
            with tab:
                {"Brief": _brief_tab, "Signal check": _signal_tab, "Charts": _charts_tab, "Evidence": _evidence_tab,
                 "Show me (SQL)": _sql_tab, "Action plan": _plan_tab}[name](res)

# ------------------------------------------------------------------ footer: how it works, evals, review log, data, changes
st.divider()
with st.expander("How it works: one workflow, five fixed steps, then a person decides"):
    st.markdown(f"""
| Step | What happens | Component |
|---|---|---|
| 1 Scope | The model reads the question into a fixed schema (site, team, items, intent). Names are checked against the tables; unknown sites or data we do not have are declined. | textual (model) + checks |
| 2 Analyze | SQL over views that hide teams under n={config.MIN_N}; Python computes changes, rates, staffing ratios, and the who-responded adjustment. | deterministic |
| 3 Retrieve | Comments and procedures are found by similarity (embeddings) and quoted verbatim; comment themes are counted in code. | deterministic + retrieval |
| 4 Assess | The verdict comes from thresholds: an item fell ≥ {SURVEY_MATERIAL:.2f}; a late-departure band rose ≥ {OPS_SIGNAL_ABS * 100:.0f} points and ≥ {OPS_SIGNAL_RATIO}×; a theme has ≥ {COMMENT_BREADTH} separate comments; staffing under {STAFFING_LOW * 100:.0f}% is a competing explanation. No corroboration = "insufficient". | deterministic |
| 5 Explain | The model writes the brief from the evidence it is handed. A checker rejects unknown citations, numbers not in the evidence, causal words, and any owner when the verdict is not supported; two failures and a templated brief is shown. | textual (model) + checks |
| Decide | A person approves, rejects, or flags. The action plan is built only for supported verdicts. Nothing happens otherwise. | human |

Team-level results are watch items (small n); comparisons and inference belong at site level. There is deliberately no autonomous action: this is an AI-assisted workflow with a reasoning step and human approval, not an agent that acts.
""")

with st.expander("Evals: gold questions scored as a confusion matrix over the planted patterns"):
    st.caption("Positive cases = a planted, corroborated problem (found = TP, missed = FN). Negative cases = a blip, one loud comment, a suppressed team, data we do not have "
               "(declined or 'insufficient' with no owner = TN, an obstacle named = FP). Misses are the outcome we weight highest. Lookups are pass/fail.")
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
    if st.button("Run the evals now" + (" (about three minutes with the model)" if config.has_key() else " (rules mode, seconds)")):
        with st.spinner("Running the gold questions..."):
            s = evaluate(db, retriever)
        st.write(f"{s['passed']}/{s['total']} passed · matrix {s['matrix']} · saved to evals/results/")
        st.rerun()

with st.expander("Review log: every approval, rejection, and flag (admin view)"):
    log = review_log()
    if log:
        st.dataframe(pd.DataFrame([{"when": r["ts"][:16].replace("T", " "), "who": r.get("who"), "decision": r["decision"], "verdict": r.get("verdict"),
                                    "brief": r.get("brief_mode"), "note": r.get("note"), "question": r["question"]} for r in reversed(log)]),
                     width="stretch", hide_index=True)
        st.caption(f"{len(log)} decisions in approvals.jsonl. Flags are the user feedback loop; the reviewer reads them here.")
    else:
        st.caption("No decisions recorded yet.")

with st.expander("Data specification: what feeds the tool, and what was planted"):
    spec = ROOT / "DATA_SPEC.md"
    st.markdown(spec.read_text() if spec.exists() else "Run data/generate.py to produce DATA_SPEC.md.")

with st.expander("What changed since Sept 14, 2026, and who asked for it"):
    st.dataframe(pd.DataFrame([
        ("O'Neal Keegan, Gallup (Sept 14)", "What do you do for managers with fewer than four people? How would operational records connect?", "Suppression in the SQL views with site roll-up; CSV upload of delay records; honeymoon effect in the synthetic data", "app/db.py, sidebar, data/generate.py"),
        ("Katie Fullowan, Freddie Mac (Sept 14)", "Show the human in the loop and spot-check outputs with numbers; surveys carry response bias", "Approve / reject / flag log with evidence ids; evals; response bias stated in every brief's limits", "Brief tab, review log"),
        ("Jeremy Lederman, MITRE (Sept 15)", "What's the data? Don't attribute causation to a blip. Automate a one-pager", "Data specification page; red-team case P9 with an 'insufficient' verdict; one-page HTML report", "DATA_SPEC.md, assess(), report"),
        ("Robert Chang, FI Consulting (Sept 15)", "One employee writing a page will make the model over-index; weight by breadth", "Comment themes counted in code; a theme corroborates only with three or more separate comments; red-team case P10", "retrieve(), assess()"),
        ("Matthew Finan, Mizuho (Sept 15)", "Score test cases as a confusion matrix, weight misses highest; use the model's reasoning over text; test gpt-5 vs gpt-5-mini", "Evals report TP/FN/FP/TN; model writes text only, code computes numbers; saved runs per model", "evals/"),
        ("Dmitri Kaznachey, FI Consulting (Sept 16)", "Offer the playbook questions, not only free text; team n is small; say deterministic vs textual", "Playbook buttons for the three features; team-level = watch items, site-level inference; computed / generated chips", "This screen"),
        ("Taher Jamshidi, Promontory AI (Sept 16)", "A flag-this feedback loop, an admin review, transparency about what is AI, a one-sentence idea statement", "Flag button; review log; chips on every element; idea statement in the header", "This screen"),
        ("Patrick Hall, instructor (Sept 14)", "A professional UI with about three strong analytics features, more than a chatbot", "Diagnose, check the signal, act and review, on one interface with charts, tables, upload, and report generation", "This screen"),
    ], columns=["Who", "What they said", "What changed", "Where"]), width="stretch", hide_index=True)
