"""Streamlit screen.  Run:  streamlit run app/ui.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `streamlit run app/ui.py` can import `app`

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import config
from app.agent import Result, approve, run
from app.db import DB
from app.retrieval import Retriever
from evals.run_evals import evaluate

st.set_page_config(page_title="Friction Finder (prototype)", page_icon="🔎", layout="wide")

PRIMARY, MID, ACCENT, MUTED = "#1B3A4B", "#3E7C8F", "#C8553D", "#6E7B85"

st.markdown(f"""
<style>
  .stApp h1 {{ color: {PRIMARY}; }}
  .tag {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:700; color:white; background:{ACCENT}; letter-spacing:.5px; }}
  .tag-mid {{ background:{MID}; }}
  .ev {{ font-family: ui-monospace, Menlo, monospace; font-size:11px; color:{MUTED}; }}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Loading synthetic data and documents...")
def _load():
    db = DB()
    return db, Retriever(db)


db, retriever = _load()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown(f"<span class='tag'>SYNTHETIC DATA</span> &nbsp;<span class='tag tag-mid'>FICTIONAL COMPANY</span>", unsafe_allow_html=True)
    st.markdown("**Northline Logistics** (does not exist). Two survey waves, three sites, 24 teams.")
    st.caption(f"Reporting threshold: teams with fewer than {config.MIN_N} respondents are never shown.")
    st.divider()
    st.markdown("**Status**")
    key = config.has_key()
    st.write(("Model: " + config.MODEL) if key else "Model: no key found, running rules + templated brief")
    st.write(f"Retrieval: {retriever.mode}")
    n_ops = db.con.execute("SELECT COUNT(*) FROM ops_daily").fetchone()[0]
    st.write(f"Operational records: {n_ops:,} rows" + (f" (incl. {db.uploaded_ops_rows} uploaded)" if db.uploaded_ops_rows else ""))
    st.divider()
    st.markdown("**Upload operational records (CSV)**")
    st.caption("How a client's own delay records would enter. Columns: date, site_id, shift, hour_band, departures, late_departures, rework_count.")
    template = pd.DataFrame([{"date": "2026-09-11", "site_id": 1, "shift": "Night", "hour_band": "06-07",
                              "departures": 24, "late_departures": 6, "rework_count": 1}])
    st.download_button("Download CSV template", template.to_csv(index=False).encode(), "ops_template.csv", "text/csv")
    up = st.file_uploader("Choose a CSV", type=["csv"], label_visibility="collapsed")
    if up is not None and st.session_state.get("last_upload") != up.name + str(up.size):
        try:
            n = db.add_ops_upload(pd.read_csv(up))
            st.session_state["last_upload"] = up.name + str(up.size)
            st.success(f"Added {n} rows. They are included in the next question's operational evidence.")
        except Exception as e:
            st.error(f"Upload rejected: {e}")

# ------------------------------------------------------------------ main
st.title("Friction Finder")
st.markdown("Ask what is behind a team's engagement score, get a cited brief with the likely obstacle, the evidence for and against, what is missing, and who owns the process. **A person approves it.**")

EXAMPLES = [
    ("Why did the night shift drop?", "Why did the Richmond night shift's scores drop and why are deliveries late?"),
    ("A team under 4 respondents", "Why did the Richmond Dispatch Day team's scores drop?"),
    ("Is the decline real?", "Is the Norfolk Day B decline real or did different people respond?"),
    ("Something we cannot answer", "What caused turnover on the Norfolk night shift?"),
]
def _ask(q: str):
    with st.spinner("Scoping, analyzing, retrieving, writing..."):
        st.session_state["result"] = run(q, db, retriever)
    st.session_state["decision"] = None


cols = st.columns(len(EXAMPLES))
for col, (label, q) in zip(cols, EXAMPLES):
    if col.button(label, use_container_width=True):
        st.session_state["question"] = q   # set before the text box below is created
        _ask(q)

question = st.text_input("Your question", key="question", placeholder="e.g., Why did the Richmond night shift's scores drop and why are deliveries late?")
if st.button("Ask", type="primary") and question.strip():
    _ask(question.strip())

res: Result | None = st.session_state.get("result")


def _chart_survey(res: Result):
    table = [e for e in res.evidence if e.kind == "survey_table"]
    if not table:
        return None
    df = pd.DataFrame(table[0].rows)
    piv = df.pivot_table(index="item", columns="wave_id", values="mean_score").reset_index()
    labels = df.drop_duplicates("item").set_index("item").item_label.to_dict()
    piv["delta"] = piv[2] - piv[1]
    worst = set(piv.nsmallest(2, "delta").item)
    fig = go.Figure()
    fig.add_bar(name="Wave 1 (Mar 2026)", x=piv.item, y=piv[1], marker_color="#CFE0E6")
    fig.add_bar(name="Wave 2 (Sep 2026)", x=piv.item, y=piv[2], marker_color=[ACCENT if i in worst else MID for i in piv.item])
    fig.update_layout(barmode="group", yaxis=dict(range=[1, 5], title="Mean (1 to 5)"), xaxis_title="Survey item",
                      legend=dict(orientation="h", y=1.1), margin=dict(l=10, r=10, t=30, b=10), height=360)
    fig.update_xaxes(ticktext=[f"{i}" for i in piv.item], tickvals=piv.item)
    return fig, {i: labels[i] for i in worst}


def _chart_ops(res: Result):
    ops = [e for e in res.evidence if e.kind == "ops_hour"]
    if not ops:
        return None
    df = pd.DataFrame(ops[0].rows)
    piv = df.pivot_table(index="hour_band", columns="period", values="late_rate").reset_index()
    fig = go.Figure()
    for period, color in (("Jan-May 2026", "#CFE0E6"), ("Jun-Sep 2026", MID)):
        if period in piv:
            fig.add_bar(name=period, x=piv.hour_band, y=piv[period] * 100,
                        marker_color=[ACCENT if (period == "Jun-Sep 2026" and hb == ops[0].value.get("hour_band")) else color for hb in piv.hour_band])
    fig.update_layout(barmode="group", yaxis_title="Late departures (%)", xaxis_title="Hour band",
                      legend=dict(orientation="h", y=1.1), margin=dict(l=10, r=10, t=30, b=10), height=360)
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=["18-22", "22-02", "02-06", "06-07", "07-10", "10-14", "14-18"])
    return fig


def _chart_tenure(res: Result):
    ev = [e for e in res.evidence if e.kind == "tenure_pattern"]
    if not ev:
        return None
    df = pd.DataFrame(ev[0].rows)
    g = df.groupby("tenure_band").grand_mean.mean().reindex(["under_1", "1_to_3", "3_to_10", "over_10"])
    fig = go.Figure(go.Bar(x=g.index, y=g.values, marker_color=[ACCENT, MID, MID, MID]))
    fig.update_layout(yaxis=dict(range=[3, 5], title="Grand mean (1 to 5)"), xaxis_title="Tenure band", height=340,
                      margin=dict(l=10, r=10, t=30, b=10))
    return fig


def _chart_mix(res: Result):
    ev = [e for e in res.evidence if e.kind == "tenure_mix"]
    if not ev:
        return None
    df = pd.DataFrame(ev[0].rows)
    fig = go.Figure()
    for band, color in (("under_1", ACCENT), ("1_to_3", MID), ("3_to_10", "#7FA8B5"), ("over_10", "#CFE0E6")):
        sub = df[df.tenure_band == band].set_index("wave_id").n.reindex([1, 2]).fillna(0)
        fig.add_bar(name=band, x=["Wave 1", "Wave 2"], y=sub.values, marker_color=color)
    fig.update_layout(barmode="stack", yaxis_title="Respondents", height=340, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.1))
    return fig


def _brief_markdown(res: Result) -> str:
    b = res.brief
    lines = [f"# Evidence brief", f"**Question:** {res.question}", "", f"**Likely obstacle (supported hypothesis):** {b.obstacle}", "",
             "## Evidence for"] + [f"- {i.get('claim')} [{', '.join(i.get('evidence_ids', []))}]" for i in b.evidence_for] + \
            ["", "## Evidence against / competing explanations"] + [f"- {i.get('claim')} [{', '.join(i.get('evidence_ids', []))}]" for i in b.evidence_against] + \
            ["", "## What is missing"] + [f"- {m}" for m in b.missing] + \
            ["", f"**Process owner:** {b.owner}", "", f"**Proposed test:** {b.proposed_test}", "", f"**Limits:** {b.limits}", "",
             "## Evidence register"] + [f"- [{e.id}] {e.statement}" for e in res.evidence] + \
            ["", f"_Brief mode: {b.mode}. Synthetic data, fictional company._"]
    return "\n".join(lines)


if res:
    st.caption(" · ".join(res.notes))
    if res.status == "refused":
        st.warning(f"**Declined.** {res.message}")
    elif res.status == "suppressed":
        st.info(f"**Reporting threshold applied.** Team-level results are hidden for teams with fewer than {config.MIN_N} respondents. Site-level evidence is used instead.")
    if res.brief is None and res.status == "ok":
        st.success(res.message)

    if res.evidence:
        tab_brief, tab_ev, tab_chart, tab_sql = st.tabs(["Brief", "Evidence", "Chart", "Show me (SQL)"])
        with tab_brief:
            if res.brief:
                b = res.brief
                left, right = st.columns([3, 1])
                with left:
                    st.markdown(f"### Likely obstacle\n{b.obstacle}")
                    st.markdown("**Evidence for**")
                    for i in b.evidence_for:
                        st.markdown(f"- {i.get('claim')} <span class='ev'>[{', '.join(i.get('evidence_ids', []))}]</span>", unsafe_allow_html=True)
                    st.markdown("**Evidence against, competing explanations**")
                    for i in b.evidence_against:
                        st.markdown(f"- {i.get('claim')} <span class='ev'>[{', '.join(i.get('evidence_ids', []))}]</span>", unsafe_allow_html=True)
                    st.markdown("**What is missing**")
                    for m in b.missing:
                        st.markdown(f"- {m}")
                    st.markdown(f"**Process owner:** {b.owner}")
                    st.markdown(f"**Proposed test:** {b.proposed_test}")
                    st.caption(f"Limits: {b.limits}")
                with right:
                    st.markdown(f"<span class='tag tag-mid'>{'MODEL BRIEF' if b.mode == 'llm' else 'TEMPLATED BRIEF'}</span>", unsafe_allow_html=True)
                    for n in b.check_notes:
                        st.caption(n)
                    st.markdown("**Human decision**")
                    note = st.text_input("Note (optional)", key="note")
                    c1, c2 = st.columns(2)
                    if c1.button("Approve", type="primary", use_container_width=True):
                        approve(res, "approved", note)
                        st.session_state["decision"] = "approved"
                    if c2.button("Reject", use_container_width=True):
                        approve(res, "rejected", note)
                        st.session_state["decision"] = "rejected"
                    if st.session_state.get("decision"):
                        st.success(f"Recorded: {st.session_state['decision']}. Logged to approvals.jsonl.")
                    st.download_button("Download brief (Markdown)", _brief_markdown(res).encode(), "brief.md", "text/markdown", use_container_width=True)
            else:
                st.markdown(res.message)
        with tab_ev:
            st.dataframe(pd.DataFrame([{"id": e.id, "kind": e.kind, "statement": e.statement, "source": e.source} for e in res.evidence]),
                         use_container_width=True, hide_index=True)
        with tab_chart:
            drawn = False
            out = _chart_survey(res)
            if out:
                fig, worst = out
                st.markdown("**Survey items for this team, Wave 1 vs Wave 2.** Largest drops highlighted: " + "; ".join(f"{k} = {v}" for k, v in worst.items()))
                st.plotly_chart(fig, use_container_width=True)
                drawn = True
            fig = _chart_ops(res)
            if fig:
                st.markdown("**Late departures by hour band.** The handoff hour band is highlighted.")
                st.plotly_chart(fig, use_container_width=True)
                drawn = True
            fig = _chart_tenure(res)
            if fig:
                st.markdown("**Grand mean by tenure band, both waves.**")
                st.plotly_chart(fig, use_container_width=True)
                drawn = True
            fig = _chart_mix(res)
            if fig:
                st.markdown("**Who responded, by tenure band.**")
                st.plotly_chart(fig, use_container_width=True)
                drawn = True
            if not drawn:
                st.caption("No chart for this question.")
        with tab_sql:
            st.caption("Every number in the brief traces to one of these queries. Respondent-level rows are never queried; the views apply the reporting threshold.")
            for e in res.evidence:
                if e.sql:
                    with st.expander(f"[{e.id}] {e.kind}: {e.statement[:90]}"):
                        st.code(e.sql, language="sql")
                        if e.rows:
                            st.dataframe(pd.DataFrame(e.rows), use_container_width=True, hide_index=True)

st.divider()
with st.expander("Evals: eight gold questions scored against the planted truth"):
    if st.button("Run evals"):
        with st.spinner("Running..."):
            rows = evaluate(db, retriever)
        df = pd.DataFrame([{"id": r["id"], "passed": r["passed"], "status": r["status"], "brief": r["brief_mode"],
                            "failed checks": ", ".join(k for k, v in r["checks"].items() if not v), "question": r["question"]} for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.write(f"{int(df.passed.sum())}/{len(df)} passed")
    if config.APPROVALS_PATH.exists():
        st.caption(f"Approval log: {sum(1 for _ in open(config.APPROVALS_PATH))} decisions recorded in approvals.jsonl")
