"""The five steps: scope, analyze, retrieve, explain, approve. Plain functions.

The model is used in two places only: extracting the scope of a question, and writing the
brief from evidence it is handed. Every number comes from SQL and Python. If the model is
unavailable, rule-based scope and a templated brief take over, and the result says so."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

import pandas as pd

from app import config, llm
from app.db import DB
from app.retrieval import Retriever

# ----------------------------------------------------------------------------- data classes

@dataclass
class Evidence:
    id: str
    kind: str                 # survey_delta, suppressed, ops_hour, staffing, tenure_mix, tenure_pattern, doc, comment, owner
    statement: str            # one sentence, with the numbers the brief may quote
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    source: str = ""
    value: dict = field(default_factory=dict)


@dataclass
class Scope:
    intent: str               # diagnose_drop, review_decline_real, tenure_pattern, owner_lookup, metric_lookup, unsupported
    site: str | None = None
    team: str | None = None
    shift: str | None = None
    team_id: int | None = None
    items: list[str] = field(default_factory=list)
    waves: list[int] = field(default_factory=lambda: [1, 2])
    unknown_entities: list[str] = field(default_factory=list)
    unsupported_reason: str | None = None
    mode: str = "rules"


@dataclass
class Brief:
    obstacle: str
    evidence_for: list[dict]
    evidence_against: list[dict]
    missing: list[str]
    owner: str
    proposed_test: str
    limits: str
    mode: str = "fallback"     # "llm" or "fallback"
    check_notes: list[str] = field(default_factory=list)


@dataclass
class Result:
    status: str               # ok, refused, suppressed
    question: str
    scope: Scope | None
    evidence: list[Evidence]
    brief: Brief | None
    message: str = ""
    notes: list[str] = field(default_factory=list)


UNSUPPORTED_TERMS = {
    "turnover": "turnover or attrition data", "attrition": "turnover or attrition data",
    "salary": "compensation data", "pay": "compensation data", "wages": "compensation data",
    "revenue": "financial data", "profit": "financial data", "customer": "customer data",
    "safety": "safety incident data", "injury": "safety incident data", "absence": "absence data",
    "sick": "absence data",
}

ITEM_KEYWORDS = {
    "q02": ["materials", "equipment", "tools"], "q07": ["opinion", "opinions", "count"],
    "q01": ["expected", "expectations"], "q04": ["recognition", "praise"], "q12": ["learn", "grow"],
    "q11": ["progress"], "q06": ["development"], "q05": ["cares"], "q03": ["best"],
}

COMMON_CAPS = {"Why", "What", "How", "Which", "Who", "Where", "When", "Is", "Are", "Did", "Does", "Do", "Can",
               "Show", "Give", "Tell", "Compare", "The", "In", "At", "For", "On", "Q12", "Wave", "Day", "Night",
               "March", "September", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
               "I", "We", "A", "An", "And", "Or", "Of", "To", "Our", "Please", "AM", "PM", "Gallup", "Northline"}


# ----------------------------------------------------------------------------- step 1: scope

def scope(question: str, db: DB) -> Scope:
    q = question.strip()
    sites = db.sites()
    teams = db.teams()
    if config.has_key():
        try:
            return _scope_llm(q, db, sites, teams)
        except llm.LLMUnavailable:
            pass
    return _scope_rules(q, sites, teams)


def _scope_rules(q: str, sites: list[str], teams: pd.DataFrame) -> Scope:
    ql = q.lower()
    sc = Scope(intent="diagnose_drop")
    for s in sites:
        if s.lower() in ql:
            sc.site = s
    if "night" in ql:
        sc.shift = "Night"
    elif "day shift" in ql or " day " in f" {ql} ":
        sc.shift = "Day"
    # team names like "Night A", "Day B", "Dispatch Day", "Maintenance Night", "Yard Day"
    for name in sorted(teams.team_name.unique(), key=len, reverse=True):
        if name.lower() in ql:
            sc.team = name
            sc.shift = teams[teams.team_name == name].iloc[0]["shift"]
            break
    for item, kws in ITEM_KEYWORDS.items():
        if any(k in ql for k in kws):
            sc.items.append(item)
    # intent
    if any(w in ql for w in ["who owns", "owner", "responsible for", "who is in charge"]):
        sc.intent = "owner_lookup"
    elif any(w in ql for w in ["tenure", "honeymoon", "new hire", "first year", "years of service"]):
        sc.intent = "tenure_pattern"
    elif any(w in ql for w in ["real", "who responded", "response mix", "mix", "same people", "actually decline", "actually drop"]):
        sc.intent = "review_decline_real"
    elif any(w in ql for w in ["what was", "how many", "what is the", "mean", "score for", "how much"]):
        sc.intent = "metric_lookup"
    # unsupported data types
    for term, reason in UNSUPPORTED_TERMS.items():
        if re.search(rf"\b{term}\w*\b", ql):
            sc.intent = "unsupported"
            sc.unsupported_reason = f"We do not have {reason}."
            break
    # unknown proper nouns (a site we do not have, e.g., Denver)
    known = {s.lower() for s in sites} | {w.lower() for w in COMMON_CAPS}
    for t in teams.team_name.unique():
        known |= {w.lower() for w in t.split()}
    for w in re.findall(r"\b[A-Z][a-z]{2,}\b", q):
        if w.lower() not in known and not q.startswith(w):
            sc.unknown_entities.append(w)
    # resolve team_id
    if sc.team and sc.site:
        row = teams[(teams.team_name == sc.team) & (teams.site_name == sc.site)]
        if len(row):
            sc.team_id = int(row.iloc[0].team_id)
    elif sc.site and sc.shift and not sc.team:
        # default to the largest team on that site and shift (the "A" team)
        row = teams[(teams.site_name == sc.site) & (teams["shift"] == sc.shift) & (teams.team_name.str.endswith(" A"))]
        if len(row):
            sc.team = row.iloc[0].team_name
            sc.team_id = int(row.iloc[0].team_id)
    return sc


def _scope_llm(q: str, db: DB, sites: list[str], teams: pd.DataFrame) -> Scope:
    items = db.items()
    system = (
        "You extract the scope of a question about a fictional logistics company. "
        "Return ONLY a JSON object with keys: intent, site, team, shift, items, waves, unknown_entities, unsupported_reason.\n\n"
        "DATA THAT EXISTS (questions about these are supported):\n"
        "- Engagement survey results by team, wave, and item, with respondent counts (12 items, 1 to 5 scale).\n"
        "- Operational records by site, shift, hour band, and day: departures, late departures (delays), rework counts.\n"
        "- Monthly staffing by site and shift: scheduled versus actual headcount.\n"
        "- Documents: shift handoff procedure, scheduling policy, action-planning guide, process ownership directory.\n"
        "- Employee open-text comments by team and wave.\n"
        "DATA THAT DOES NOT EXIST (questions that need these are unsupported): turnover or attrition, pay or compensation, "
        "revenue or profit, customers, safety incidents, absence or sick leave, individual employees' answers.\n\n"
        f"Known sites: {sites}. Known team names: {sorted(teams.team_name.unique().tolist())}. Shifts: Day, Night. "
        "Waves: 1 (closed March 2026), 2 (closed September 2026). "
        f"Survey items: {[(r.item, r.label) for r in items.itertuples()]}.\n\n"
        "Intents: diagnose_drop (why did scores drop, what is going on, what obstacles, why are deliveries late: SUPPORTED), "
        "review_decline_real (is the decline real or a change in who responded), tenure_pattern (scores by tenure, honeymoon effect), "
        "owner_lookup (who owns a process), metric_lookup (a specific number), unsupported (ONLY when the question needs a data type "
        "from the does-not-exist list, or names a site or team not in the known lists).\n"
        "Rules: never guess a site or team that is not in the known lists; put such names in unknown_entities. "
        "site, team, and shift may be null. items: ONLY item codes the question explicitly refers to (e.g., 'materials' -> ['q02']); "
        "otherwise []. waves default to [1, 2]. Do not explain; return the JSON object only."
    )
    out = llm.chat_json(system, q, effort="minimal")
    rules = _scope_rules(q, sites, teams)  # deterministic safety net
    sc = Scope(intent=str(out.get("intent") or "diagnose_drop"), mode="llm")
    sc.site = out.get("site") if out.get("site") in sites else None
    team = out.get("team")
    sc.team = team if team in set(teams.team_name) else None
    sc.shift = out.get("shift") if out.get("shift") in ("Day", "Night") else None
    sc.items = [i for i in (out.get("items") or []) if i in set(items.item)]
    if len(sc.items) >= 6:
        sc.items = rules.items  # the model listed everything; fall back to what the question names
    sc.waves = [w for w in (out.get("waves") or [1, 2]) if w in (1, 2)] or [1, 2]
    known_words = {s.lower() for s in sites} | {w.lower() for t in teams.team_name.unique() for w in t.split()}
    sc.unknown_entities = [str(u) for u in (out.get("unknown_entities") or []) if str(u).lower() not in known_words]
    sc.unsupported_reason = out.get("unsupported_reason") or None
    if sc.intent == "unsupported" and rules.intent != "unsupported" and not rules.unknown_entities:
        # the model refused a question the rules can answer from existing data: do not over-refuse
        sc.intent = rules.intent
        sc.unsupported_reason = None
    if sc.intent == "unsupported" and not sc.unsupported_reason:
        sc.unsupported_reason = "The question needs data this prototype does not have."
    if sc.site is None and rules.site:
        sc.site = rules.site
    if sc.shift is None and rules.shift:
        sc.shift = rules.shift
    if sc.team is None and rules.team:
        sc.team = rules.team
    if sc.team and not sc.shift:
        sc.shift = teams[teams.team_name == sc.team].iloc[0]["shift"]
    if sc.team and sc.site:
        row = teams[(teams.team_name == sc.team) & (teams.site_name == sc.site)]
        if len(row):
            sc.team_id = int(row.iloc[0].team_id)
    elif sc.site and sc.shift:
        row = teams[(teams.site_name == sc.site) & (teams["shift"] == sc.shift) & (teams.team_name.str.endswith(" A"))]
        if len(row):
            sc.team = row.iloc[0].team_name
            sc.team_id = int(row.iloc[0].team_id)
    return sc


# ----------------------------------------------------------------------------- step 2: analyze

def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def analyze(sc: Scope, db: DB) -> list[Evidence]:
    ev: list[Evidence] = []
    n = 0

    def nid(prefix):
        nonlocal n
        n += 1
        return f"{prefix}{n}"

    if sc.intent == "tenure_pattern":
        # respondent-weighted grand mean: every item in a band-wave shares the same n
        r = db.run_sql("SELECT tenure_band, wave_id, ROUND(SUM(mean_score * n) / SUM(n), 2) AS grand_mean, MIN(n) AS n FROM v_tenure_wave_item WHERE reportable GROUP BY 1, 2 ORDER BY 1, 2")
        rows = r.to_records()
        acc = {}
        for row in rows:
            a = acc.setdefault(row["tenure_band"], [0.0, 0])
            a[0] += float(row["grand_mean"]) * int(row["n"])
            a[1] += int(row["n"])
        order = ["under_1", "1_to_3", "3_to_10", "over_10"]
        parts = [f"{b}: {acc[b][0] / acc[b][1]:.2f} (n={acc[b][1]})" for b in order if b in acc and acc[b][1]]
        ev.append(Evidence(id=nid("S"), kind="tenure_pattern",
                           statement="Grand mean by tenure band across both waves, respondent-weighted, reportable groups only: " + "; ".join(parts) + ".",
                           sql=r.sql, rows=rows, source="v_tenure_wave_item",
                           value={b: round(acc[b][0] / acc[b][1], 2) for b in acc if acc[b][1]}))
        return ev

    if sc.intent == "owner_lookup" or (sc.team_id is None and sc.site is None):
        return ev

    # ---- survey: team-level deltas, or suppression + site roll-up
    if sc.team_id is not None:
        r = db.run_sql(f"SELECT wave_id, wave_name, item, item_label, mean_score, n, reportable FROM v_team_wave_item WHERE team_id = {sc.team_id} ORDER BY item, wave_id")
        df = r.rows
        if len(df) and not bool(df.reportable.all()):
            ns = df.groupby("wave_id").n.first().to_dict()
            ev.append(Evidence(id=nid("S"), kind="suppressed",
                               statement=(f"{sc.site} {sc.team} has fewer than {config.MIN_N} respondents in at least one wave "
                                          f"(respondents by wave: {ns}). Team-level results are not shown, to protect anonymity; "
                                          f"the site-level results are used instead."),
                               sql=r.sql, rows=r.to_records(), source="v_team_wave_item",
                               value={"n_by_wave": ns}))
            sc_site_only = True
        else:
            sc_site_only = False
            piv = df.pivot_table(index=["item", "item_label"], columns="wave_id", values="mean_score").reset_index()
            nmap = df.groupby("wave_id").n.first().to_dict()
            piv["delta"] = (piv.get(2) - piv.get(1)).round(2)
            piv = piv.sort_values("delta")
            top = piv[piv.item.isin(sc.items)] if sc.items else piv.head(3)
            for t in top.itertuples():
                w1, w2 = getattr(t, "_3"), getattr(t, "_4")  # pivot columns 1 and 2 land at positions 3, 4
                ev.append(Evidence(id=nid("S"), kind="survey_delta",
                                   statement=(f"{sc.site} {sc.team}, {t.item_label} ({t.item}): {w1:.2f} in Wave 1 to {w2:.2f} in Wave 2 "
                                              f"(n={nmap.get(1)} to {nmap.get(2)}), change {t.delta:+.2f}."),
                                   sql=r.sql, rows=[{"item": t.item, "label": t.item_label, "wave1": w1, "wave2": w2, "delta": t.delta,
                                                     "n1": nmap.get(1), "n2": nmap.get(2)}],
                                   source="v_team_wave_item",
                                   value={"item": t.item, "wave1": w1, "wave2": w2, "delta": t.delta}))
            stable = piv[piv.delta.abs() <= 0.15]
            if len(stable):
                ev.append(Evidence(id=nid("S"), kind="survey_stable",
                                   statement=f"{len(stable)} of 12 items on this team moved by 0.15 or less between waves ({', '.join(stable.item.tolist())}).",
                                   sql=r.sql, rows=stable[["item", "delta"]].to_dict(orient="records"), source="v_team_wave_item"))
            # full table for the chart
            ev.append(Evidence(id=nid("S"), kind="survey_table", statement="All 12 items for this team, both waves (chart data).",
                               sql=r.sql, rows=r.to_records(), source="v_team_wave_item"))
    else:
        sc_site_only = True

    if sc.site and (sc_site_only or sc.team_id is None):
        r = db.run_sql(f"SELECT wave_id, item, item_label, mean_score, n FROM v_site_wave_item WHERE site_name = '{sc.site}' ORDER BY item, wave_id")
        df = r.rows
        piv = df.pivot_table(index=["item", "item_label"], columns="wave_id", values="mean_score").reset_index()
        piv["delta"] = (piv.get(2) - piv.get(1)).round(2)
        worst = piv.sort_values("delta").head(2)
        nmap = df.groupby("wave_id").n.first().to_dict()
        for t in worst.itertuples():
            w1, w2 = getattr(t, "_3"), getattr(t, "_4")
            ev.append(Evidence(id=nid("S"), kind="survey_delta_site",
                               statement=f"{sc.site} site overall, {t.item_label} ({t.item}): {w1:.2f} in Wave 1 to {w2:.2f} in Wave 2 (n={nmap.get(1)} to {nmap.get(2)}), change {t.delta:+.2f}.",
                               sql=r.sql, rows=[{"item": t.item, "wave1": w1, "wave2": w2, "delta": t.delta}], source="v_site_wave_item"))

    # ---- reviewer: who responded
    if sc.team_id is not None and sc.intent in ("review_decline_real", "diagnose_drop"):
        r = db.run_sql(f"SELECT wave_id, tenure_band, n, grand_mean FROM v_team_tenure_mix WHERE team_id = {sc.team_id} ORDER BY wave_id, tenure_band")
        df = r.rows
        if len(df):
            tot = df.groupby("wave_id").n.sum().to_dict()
            u1 = df[df.tenure_band == "under_1"].groupby("wave_id").n.sum().to_dict()
            share1 = u1.get(1, 0) / tot.get(1, 1)
            share2 = u1.get(2, 0) / tot.get(2, 1)
            stmt = (f"Who responded on {sc.site} {sc.team}: under-one-year employees were {_pct(share1)} of respondents in Wave 1 "
                    f"and {_pct(share2)} in Wave 2 (respondents {tot.get(1)} and {tot.get(2)}).")
            flag = abs(share1 - share2) >= 0.25
            if flag:
                stmt += " That is a large change in who answered, so part of any movement in the team mean can be a response-mix effect rather than a real change."
            else:
                stmt += " The mix of who answered is similar across waves, so the change is not explained by who responded."
            ev.append(Evidence(id=nid("S"), kind="tenure_mix", statement=stmt, sql=r.sql, rows=r.to_records(),
                               source="v_team_tenure_mix", value={"share_w1": round(share1, 2), "share_w2": round(share2, 2), "mix_shift": flag}))

    if sc.intent in ("review_decline_real", "tenure_pattern", "metric_lookup", "owner_lookup"):
        return ev

    # ---- operations: late departures by hour band and period
    if sc.site:
        shift_clause = f"AND shift = '{sc.shift}'" if sc.shift else ""
        r = db.run_sql(f"SELECT shift, hour_band, period, departures, late_departures, late_rate FROM v_ops_hour WHERE site_name = '{sc.site}' {shift_clause} ORDER BY shift, hour_band, period")
        df = r.rows
        if len(df):
            piv = df.pivot_table(index=["shift", "hour_band"], columns="period", values="late_rate").reset_index()
            if "Jan-May 2026" in piv.columns and "Jun-Sep 2026" in piv.columns:
                piv["change"] = piv["Jun-Sep 2026"] - piv["Jan-May 2026"]
                worst = piv.sort_values("change", ascending=False).iloc[0]
                others = piv[piv.hour_band != worst.hour_band]
                ev.append(Evidence(id=nid("O"), kind="ops_hour",
                                   statement=(f"{sc.site} {worst['shift']} shift, departures in the {worst.hour_band} hour band: late-departure rate "
                                              f"{_pct(worst['Jan-May 2026'])} in Jan-May 2026 to {_pct(worst['Jun-Sep 2026'])} in Jun-Sep 2026. "
                                              f"Other hour bands stayed between {_pct(others['Jun-Sep 2026'].min())} and {_pct(others['Jun-Sep 2026'].max())} in Jun-Sep."),
                                   sql=r.sql, rows=r.to_records(), source="v_ops_hour",
                                   value={"hour_band": worst.hour_band, "before": float(worst['Jan-May 2026']), "after": float(worst['Jun-Sep 2026'])}))
        r2 = db.run_sql(f"SELECT shift, month, SUM(rework) AS rework FROM v_ops_month WHERE site_name = '{sc.site}' {shift_clause} GROUP BY 1, 2 ORDER BY 1, 2")
        rw = r2.rows
        if len(rw):
            first, last = rw.iloc[0], rw.iloc[-1]
            ev.append(Evidence(id=nid("O"), kind="ops_rework",
                               statement=f"Rework counts on {sc.site} {sc.shift or ''} show no trend: {int(first.rework)} in {first.month} and {int(last.rework)} in {last.month}.",
                               sql=r2.sql, rows=r2.to_records(), source="v_ops_month"))

    # ---- staffing: competing explanation
    if sc.site:
        shift_clause = f"AND shift = '{sc.shift}'" if sc.shift else ""
        r = db.run_sql(f"SELECT month, shift, scheduled_headcount, actual_headcount, ROUND(actual_headcount * 1.0 / scheduled_headcount, 2) AS ratio FROM staffing WHERE site_id = (SELECT site_id FROM sites WHERE site_name = '{sc.site}') {shift_clause} ORDER BY month")
        df = r.rows
        low = df[df.ratio < 0.9]
        if len(low):
            parts = [f"{x.month}: {int(x.actual_headcount)} of {int(x.scheduled_headcount)} scheduled ({_pct(x.ratio)})" for x in low.itertuples()]
            ev.append(Evidence(id=nid("O"), kind="staffing",
                               statement=f"Staffing on {sc.site} {sc.shift or ''} fell below 90% of scheduled in: " + "; ".join(parts) + ". Other months were at or above 90%.",
                               sql=r.sql, rows=r.to_records(), source="staffing", value={"low_months": low.month.tolist()}))
        else:
            ev.append(Evidence(id=nid("O"), kind="staffing", statement=f"Staffing on {sc.site} {sc.shift or ''} stayed at or above 90% of scheduled in every month.",
                               sql=r.sql, rows=r.to_records(), source="staffing"))
    return ev


# ----------------------------------------------------------------------------- step 3: retrieve

def retrieve(sc: Scope, question: str, db: DB, retriever: Retriever, evidence: list[Evidence]) -> list[Evidence]:
    ev: list[Evidence] = []
    if sc.intent in ("tenure_pattern", "metric_lookup"):
        return ev
    # comments from the scoped team (reportable only, enforced by the view)
    filters = {"team_id": sc.team_id} if sc.team_id is not None else {"site_name": sc.site, "shift": sc.shift}
    hits = retriever.search(question + " shift handoff information loaded checklist delays", k=4, kind="comment", filters=filters)
    for i, (c, s) in enumerate(hits, 1):
        ev.append(Evidence(id=f"C{i}", kind="comment", statement=f"Employee comment ({c.title}): \"{c.text}\"",
                           source=c.chunk_id, value={"score": round(s, 3), **c.meta}))
    # documents
    themes = " ".join(e.statement for e in evidence[:4]) + " " + " ".join(c.text for c, _ in hits)
    dhits = retriever.search(question + " " + themes[:500], k=3, kind="doc")
    for i, (c, s) in enumerate(dhits, 1):
        ev.append(Evidence(id=f"D{i}", kind="doc", statement=f"Document ({c.title}): {c.text[:400].strip()}",
                           source=c.chunk_id, value={"score": round(s, 3), **c.meta}))
    # owner
    text = (themes + " " + " ".join(c.text for c, _ in dhits)).lower()
    if "handoff" in text or "checklist" in text:
        process = "Shift handoff procedure"
    elif "schedul" in text or "staffing" in text:
        process = "Shift scheduling policy"
    elif "forklift" in text or "maintenance" in text:
        process = "Forklift and equipment maintenance"
    else:
        process = "Shift handoff procedure"
    site_clause = f"AND (site_name = '{sc.site}' OR site_name = 'ALL')" if sc.site else ""
    r = db.run_sql(f"SELECT process_name, site_name, owner_role, owner_name FROM ownership_directory WHERE process_name = '{process}' {site_clause} ORDER BY site_name = 'ALL'")
    if len(r.rows):
        o = r.rows.iloc[0]
        ev.append(Evidence(id="W1", kind="owner", statement=f"Process owner for '{o.process_name}' at {o.site_name}: {o.owner_role}, {o.owner_name} (ownership directory).",
                           sql=r.sql, rows=r.to_records(), source="ownership_directory",
                           value={"process": o.process_name, "role": o.owner_role, "name": o.owner_name}))
    return ev


# ----------------------------------------------------------------------------- step 4: explain

NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)")


def _allowed_numbers(evidence: list[Evidence]) -> set[str]:
    allowed = set(str(i) for i in range(0, 32))  # small integers: item numbers, months, days, waves
    for e in evidence:
        for m in NUM_RE.finditer(e.statement):
            allowed.add(m.group(1))
        for v in e.value.values():
            if isinstance(v, (int, float)):
                allowed.add(f"{v:.2f}".rstrip("0").rstrip("."))
                allowed.add(f"{v:.2f}")
                allowed.add(f"{v * 100:.1f}")
                allowed.add(f"{v * 100:.0f}")
    return allowed


def check_brief(b: Brief, evidence: list[Evidence]) -> list[str]:
    """Return a list of problems. Empty list means the brief passed."""
    problems = []
    ids = {e.id for e in evidence}
    for section in ("evidence_for", "evidence_against"):
        for item in getattr(b, section):
            for cid in item.get("evidence_ids", []):
                if cid not in ids:
                    problems.append(f"{section}: cites unknown evidence id {cid}")
            if not item.get("evidence_ids"):
                problems.append(f"{section}: a claim has no evidence id")
    allowed = _allowed_numbers(evidence)
    text = " ".join([b.obstacle, b.proposed_test, b.limits] + [i.get("claim", "") for i in b.evidence_for + b.evidence_against] + b.missing)
    for m in NUM_RE.finditer(text):
        num = m.group(1)
        alt = num.rstrip("0").rstrip(".") if "." in num else num  # 3.70 -> 3.7, but 40 stays 40
        if num not in allowed and alt not in allowed:
            problems.append(f"number {num}{m.group(2)} does not appear in the evidence")
    if re.search(r"\b(root cause|the cause is|caused by|proves)\b", text, re.I):
        problems.append("causal language: say 'supported hypothesis'")
    return problems


def fallback_brief(sc: Scope, evidence: list[Evidence]) -> Brief:
    by_kind = {}
    for e in evidence:
        by_kind.setdefault(e.kind, []).append(e)
    for_, against, missing = [], [], []
    obstacle = "Not enough evidence to name a likely obstacle."
    owner = "Not identified."
    if by_kind.get("owner"):
        o = by_kind["owner"][0]
        owner = f"{o.value['role']}, {o.value['name']} ({o.value['process']})"
    if by_kind.get("survey_delta"):
        for e in by_kind["survey_delta"][:2]:
            for_.append({"claim": e.statement, "evidence_ids": [e.id]})
    if by_kind.get("ops_hour"):
        e = by_kind["ops_hour"][0]
        for_.append({"claim": e.statement, "evidence_ids": [e.id]})
        obstacle = f"The shift handoff process (departures in the {e.value['hour_band']} hour band) is the most likely obstacle. This is a supported hypothesis, not a proven cause."
    if by_kind.get("comment"):
        ids = [e.id for e in by_kind["comment"]]
        for_.append({"claim": f"{len(ids)} employee comments describe missing information at the shift handoff.", "evidence_ids": ids})
    if by_kind.get("doc"):
        d = by_kind["doc"][0]
        for_.append({"claim": "The handoff procedure requires a completed load checklist and a signed handoff log before departures are released.", "evidence_ids": [d.id]})
    if by_kind.get("staffing"):
        e = by_kind["staffing"][0]
        if e.value.get("low_months"):
            against.append({"claim": "Competing explanation: " + e.statement, "evidence_ids": [e.id]})
        else:
            against.append({"claim": e.statement, "evidence_ids": [e.id]})
    if by_kind.get("tenure_mix"):
        e = by_kind["tenure_mix"][0]
        (against if e.value.get("mix_shift") else for_).append({"claim": e.statement, "evidence_ids": [e.id]})
    if by_kind.get("ops_rework"):
        against.append({"claim": by_kind["ops_rework"][0].statement, "evidence_ids": [by_kind["ops_rework"][0].id]})
    if by_kind.get("suppressed"):
        e = by_kind["suppressed"][0]
        for_.insert(0, {"claim": e.statement, "evidence_ids": [e.id]})
        obstacle = "Team-level results are suppressed (fewer than 4 respondents). The site-level pattern is shown instead; ask the Site Operations Manager to review with the manager."
    missing = ["No record of whether the handoff checklist is actually completed each shift.",
               "No data on which trailers were late and why (dispatch notes)."]
    if not by_kind.get("ops_hour"):
        missing.append("No operational records for this scope; upload delay records to test the operational link.")
    test = "Enforce the handoff checklist and signed log for 30 days on this site and shift; measure the late-departure rate in the handoff hour band against Jun-Sep; review with the owner at day 30."
    limits = "Fictional, synthetic data. Associations, not causes. Team-level figures shown only where n is 4 or more."
    return Brief(obstacle=obstacle, evidence_for=for_, evidence_against=against, missing=missing, owner=owner,
                 proposed_test=test, limits=limits, mode="fallback")


def explain(question: str, sc: Scope, evidence: list[Evidence]) -> Brief:
    if not config.has_key():
        return fallback_brief(sc, evidence)
    ev_text = "\n".join(f"[{e.id}] ({e.kind}) {e.statement}" for e in evidence)
    system = (
        "You write a one-page evidence brief for an HR or operations leader at a logistics company. "
        "Use ONLY the evidence provided. Every claim must cite one or more evidence ids in evidence_ids. "
        "Never introduce a number that does not appear in the evidence text. Never claim a cause; write "
        "'supported hypothesis'. Name competing explanations under evidence_against. List what evidence is missing. "
        "Return ONLY a JSON object with keys: obstacle (string), evidence_for (list of {claim, evidence_ids}), "
        "evidence_against (list of {claim, evidence_ids}), missing (list of strings), owner (string), "
        "proposed_test (string: a 30-day experiment with a success measure and a review date), limits (string). "
        "Length: obstacle at most 35 words; each claim at most 30 words; at most 5 claims for and 3 against; "
        "missing at most 4 items of one sentence each; proposed_test at most 60 words; limits at most 35 words. "
        "Plain language for a manager; no headings inside strings."
    )
    user = f"Question: {question}\n\nEvidence:\n{ev_text}\n\nScope: {json.dumps(asdict(sc))}"
    notes = []
    for attempt in range(2):
        try:
            out = llm.chat_json(system, user if attempt == 0 else user + "\n\nYour previous draft failed these checks: " + "; ".join(notes) + ". Fix them.")
        except llm.LLMUnavailable as e:
            b = fallback_brief(sc, evidence)
            b.check_notes = [f"model unavailable ({e}); templated brief shown"]
            return b
        b = Brief(obstacle=str(out.get("obstacle", "")), evidence_for=list(out.get("evidence_for") or []),
                  evidence_against=list(out.get("evidence_against") or []), missing=[str(m) for m in (out.get("missing") or [])],
                  owner=str(out.get("owner", "")), proposed_test=str(out.get("proposed_test", "")), limits=str(out.get("limits", "")),
                  mode="llm")
        notes = check_brief(b, evidence)
        if not notes:
            b.check_notes = ["passed: every citation exists and every number appears in the evidence"]
            return b
    fb = fallback_brief(sc, evidence)
    fb.check_notes = ["model brief failed checks twice: " + "; ".join(notes) + "; templated brief shown"]
    return fb


# ----------------------------------------------------------------------------- orchestration

def run(question: str, db: DB, retriever: Retriever) -> Result:
    sc = scope(question, db)
    notes = [f"scope mode: {sc.mode}", f"retrieval mode: {retriever.mode}"]
    if sc.intent == "unsupported":
        return Result(status="refused", question=question, scope=sc, evidence=[], brief=None,
                      message=f"I cannot answer this from the data available. {sc.unsupported_reason or ''} "
                              "Available: survey results by team and wave, operational records, staffing, and process documents.",
                      notes=notes)
    if sc.unknown_entities:
        return Result(status="refused", question=question, scope=sc, evidence=[], brief=None,
                      message=f"I do not have data for {', '.join(sc.unknown_entities)}. Known sites: {', '.join(db.sites())}.",
                      notes=notes)
    if sc.intent in ("diagnose_drop", "review_decline_real", "metric_lookup", "owner_lookup") and sc.site is None and sc.team_id is None:
        return Result(status="refused", question=question, scope=sc, evidence=[], brief=None,
                      message="Which site or team do you mean? Known sites: " + ", ".join(db.sites()) + ".", notes=notes)
    evidence = analyze(sc, db)
    evidence += retrieve(sc, question, db, retriever, evidence)
    if not evidence:
        return Result(status="refused", question=question, scope=sc, evidence=[], brief=None,
                      message="The data cannot answer this question; no evidence was found for that scope.", notes=notes)
    if sc.intent == "owner_lookup":
        owners = [e for e in evidence if e.kind == "owner"]
        msg = owners[0].statement if owners else "No owner found in the directory for that process."
        return Result(status="ok", question=question, scope=sc, evidence=evidence, brief=None, message=msg, notes=notes)
    if sc.intent in ("tenure_pattern", "metric_lookup", "review_decline_real"):
        msg = " ".join(e.statement for e in evidence if e.kind in ("tenure_pattern", "survey_delta", "tenure_mix", "suppressed"))
        return Result(status="ok", question=question, scope=sc, evidence=evidence, brief=None, message=msg, notes=notes)
    brief = explain(question, sc, evidence)
    notes.append(f"brief mode: {brief.mode}")
    status = "suppressed" if any(e.kind == "suppressed" for e in evidence) else "ok"
    return Result(status=status, question=question, scope=sc, evidence=evidence, brief=brief, notes=notes)


# ----------------------------------------------------------------------------- step 5: approve

def approve(result: Result, decision: str, note: str = "", who: str = "reviewer") -> dict:
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "who": who, "decision": decision, "note": note,
           "question": result.question, "brief": asdict(result.brief) if result.brief else None,
           "evidence_ids": [e.id for e in result.evidence]}
    with open(config.APPROVALS_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
