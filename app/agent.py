"""One workflow, five fixed steps: scope, analyze, retrieve, assess, explain; then a person
approves. Plain functions, no framework.

The model is used in two places only: understanding the question (scope) and writing text from
evidence it is handed (the brief, the action plan). Every number comes from SQL and Python
("a deterministic component and a textual component", judge Kaznachey, Sept 16, 2026). The
verdict on whether the evidence is sufficient is computed by code, not by the model. If the
model is unavailable, rule-based scope and templated text take over, and the result says so."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from app import config, llm
from app.db import DB
from app.retrieval import Retriever

# ----------------------------------------------------------------------------- thresholds
# All computed rules live here so they can be read out in Q&A. They are screening rules on a
# 5-point scale and on rates, not significance tests: team-level findings are "watch items";
# inference is site-level (judge Kaznachey, Sept 16).
SURVEY_MATERIAL = 0.30   # item mean change treated as material (5-point scale)
OPS_SIGNAL_ABS = 0.05    # late-departure rate change of 5 points or more ...
OPS_SIGNAL_RATIO = 1.5   # ... and at least 1.5x the earlier rate
STAFFING_LOW = 0.90      # actual headcount below 90% of scheduled
COMMENT_BREADTH = 3      # a comment theme corroborates only with 3 or more separate comments
MIX_EXPLAINS = 0.30      # residual change after adjusting for who responded, below this = not real

# ----------------------------------------------------------------------------- data classes

@dataclass
class Evidence:
    id: str
    kind: str                 # survey_delta, survey_delta_site, suppressed, ops_hour, ops_rework, staffing, tenure_mix,
                              # tenure_pattern, signal_check, site_heatmap, site_items, comment_themes, comment, doc, owner
    statement: str            # one sentence, with the numbers the brief may quote
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    source: str = ""
    value: dict = field(default_factory=dict)
    origin: str = "computed"  # computed (SQL + Python) | retrieved (verbatim text)


@dataclass
class Scope:
    intent: str               # diagnose_drop, review_decline_real, tenure_pattern, owner_lookup, metric_lookup, site_overview, unsupported
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
class Assessment:
    """Computed by code from the evidence. The model never decides this."""
    verdict: str              # supported | insufficient | no_material_change | suppressed_insufficient | not_applicable
    label: str
    level: str = "team"       # team | site
    n: dict = field(default_factory=dict)
    survey_signal: bool = False
    ops_signal: bool = False
    staffing_signal: bool = False
    comment_signal: bool = False
    theme: str | None = None
    process: str | None = None
    reasons: list[str] = field(default_factory=list)


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
class ActionPlan:
    """Gallup's State of the Team shape: one performance goal, one focus item, three or four
    actions with owners, a review cadence, and the item's discussion questions."""
    goal: str
    focus_item: str
    focus_label: str
    actions: list[dict]           # {action, owner_role, owner_name, due}
    success_measure: str
    review_cadence: str
    team_questions: list[str]
    questions_source: str
    mode: str = "fallback"
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
    assessment: Assessment | None = None


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
               "I", "We", "A", "An", "And", "Or", "Of", "To", "Our", "Please", "AM", "PM", "Gallup", "Northline", "Across"}

# Comment themes are counted by keyword in code so that breadth (how many separate comments) is a
# number, not a model impression (judge Chang, Sept 15: "weight by breadth, not length").
THEMES = {
    "handoff": {"label": "shift handoff", "process": "Shift handoff procedure",
                "keywords": ["handoff", "hand-off", "hand off", "checklist", "loaded", "last shift", "trailers we finished", "start blind"]},
    "equipment": {"label": "equipment and maintenance", "process": "Forklift and equipment maintenance",
                  "keywords": ["forklift", "maintenance", "scanner", "equipment", "hydraulic", "parts are on order"]},
    "schedule": {"label": "scheduling and staffing", "process": "Shift scheduling policy",
                 "keywords": ["schedule", "shift swap", "overtime", "more notice", "staffing"]},
    "workload": {"label": "workload and priorities", "process": "Engagement survey and action planning",
                 "keywords": ["workload", "priorities", "too many"]},
    "recognition": {"label": "recognition", "process": "Engagement survey and action planning",
                    "keywords": ["recognition", "thank you", "notices good work", "praise"]},
    "communication": {"label": "communication", "process": "Engagement survey and action planning",
                      "keywords": ["huddle", "announced late", "routes", "communicat"]},
    "development": {"label": "development", "process": "Engagement survey and action planning",
                    "keywords": ["lead role", "cross-training", "clearer path", "learn"]},
}
HANDOFF_BANDS = {"06-07", "18-22"}   # departures released at the shift boundary (SOP-OPS-014, step 4)
# The survey item most relevant to each theme, used to pick the focus item for the action plan.
THEME_ITEM = {"handoff": "q02", "equipment": "q02", "schedule": "q01", "workload": "q01", "recognition": "q04",
              "communication": "q07", "development": "q06"}


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
    elif any(w in ql for w in ["overview", "across", "which teams", "all teams", "heatmap", "heat map", "every team", "where did we drop", "where did scores drop"]):
        sc.intent = "site_overview"
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
    _resolve_team(sc, teams)
    return sc


def _resolve_team(sc: Scope, teams: pd.DataFrame) -> None:
    if sc.intent == "site_overview":
        sc.team, sc.team_id = None, None
        return
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


def _scope_llm(q: str, db: DB, sites: list[str], teams: pd.DataFrame) -> Scope:
    items = db.items()
    system = (
        "You extract the scope of a question about a fictional logistics company. "
        "Return ONLY a JSON object with keys: intent, site, team, shift, items, waves, unknown_entities, unsupported_reason.\n\n"
        "DATA THAT EXISTS (questions about these are supported):\n"
        "- Engagement survey results by team, wave, and item, with respondent counts (12 items, 1 to 5 scale).\n"
        "- Operational records by site, shift, hour band, and day: departures, late departures (delays), rework counts.\n"
        "- Monthly staffing by site and shift: scheduled versus actual headcount.\n"
        "- Documents: shift handoff procedure, scheduling policy, action-planning guide, process ownership directory, "
        "Gallup's item-specific team discussion questions.\n"
        "- Employee open-text comments by team and wave.\n"
        "DATA THAT DOES NOT EXIST (questions that need these are unsupported): turnover or attrition, pay or compensation, "
        "revenue or profit, customers, safety incidents, absence or sick leave, individual employees' answers.\n\n"
        f"Known sites: {sites}. Known team names: {sorted(teams.team_name.unique().tolist())}. Shifts: Day, Night. "
        "Waves: 1 (closed March 2026), 2 (closed September 2026). "
        f"Survey items: {[(r.item, r.label) for r in items.itertuples()]}.\n\n"
        "Intents: diagnose_drop (why did scores drop, what is going on, what obstacles, why are deliveries late: SUPPORTED), "
        "site_overview (where did scores drop across a site, which teams moved, overview or heatmap of a site), "
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
    for u in rules.unknown_entities:  # the deterministic check wins: a place we do not have is named in the decline
        if u.lower() not in {x.lower() for x in sc.unknown_entities}:
            sc.unknown_entities.append(u)
    sc.unsupported_reason = out.get("unsupported_reason") or None
    if sc.intent == "unsupported" and rules.intent != "unsupported" and not rules.unknown_entities:
        # the model refused a question the rules can answer from existing data: do not over-refuse
        sc.intent = rules.intent
        sc.unsupported_reason = None
    if sc.intent == "unsupported" and not sc.unsupported_reason:
        sc.unsupported_reason = "The question needs data this prototype does not have."
    if rules.intent == "site_overview":
        sc.intent = "site_overview"
    if sc.site is None and rules.site:
        sc.site = rules.site
    if sc.shift is None and rules.shift:
        sc.shift = rules.shift
    if sc.team is None and rules.team:
        sc.team = rules.team
    if sc.team and not sc.shift:
        sc.shift = teams[teams.team_name == sc.team].iloc[0]["shift"]
    _resolve_team(sc, teams)
    return sc


# ----------------------------------------------------------------------------- step 2: analyze

def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _pivot_waves(df: pd.DataFrame, value: str = "mean_score") -> pd.DataFrame:
    """item x wave -> columns w1, w2, delta (NaN where a wave is missing or suppressed)."""
    piv = df.pivot_table(index=["item", "item_label"], columns="wave_id", values=value, aggfunc="first").reset_index()
    piv.columns = [str(c) for c in piv.columns]
    piv["w1"] = piv["1"] if "1" in piv.columns else float("nan")
    piv["w2"] = piv["2"] if "2" in piv.columns else float("nan")
    piv["delta"] = (piv["w2"] - piv["w1"]).round(2)
    return piv[["item", "item_label", "w1", "w2", "delta"]]


def _company_item_means(db: DB) -> dict:
    """Respondent-weighted company mean per item, both waves, from the site view (never respondent rows)."""
    r = db.run_sql("SELECT item, ROUND(SUM(mean_score * n) / SUM(n), 2) AS company_mean FROM v_site_wave_item WHERE reportable GROUP BY 1")
    return {row["item"]: float(row["company_mean"]) for row in r.to_records()}


def analyze(sc: Scope, db: DB) -> list[Evidence]:
    ev: list[Evidence] = []
    n = 0

    def nid(prefix):
        nonlocal n
        n += 1
        return f"{prefix}{n}"

    if sc.intent == "tenure_pattern":
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

    if sc.intent == "site_overview" and sc.site:
        return _analyze_site_overview(sc, db, nid)

    if sc.intent == "owner_lookup" or (sc.team_id is None and sc.site is None):
        return ev

    # ---- survey: team-level deltas, or suppression + site roll-up
    sc_site_only = True
    if sc.team_id is not None:
        r = db.run_sql(f"SELECT wave_id, wave_name, item, item_label, mean_score, n, reportable FROM v_team_wave_item WHERE team_id = {sc.team_id} ORDER BY item, wave_id")
        df = r.rows
        nmap = {int(k): int(v) for k, v in df.groupby("wave_id").n.first().to_dict().items()} if len(df) else {}
        if len(df) and not bool(df.reportable.all()):
            ev.append(Evidence(id=nid("S"), kind="suppressed",
                               statement=(f"{sc.site} {sc.team} has fewer than {config.MIN_N} respondents in at least one wave "
                                          f"(respondents by wave: {nmap}). Team-level results are not shown, to protect anonymity; "
                                          f"the site-level results are used instead."),
                               sql=r.sql, rows=r.to_records(), source="v_team_wave_item",
                               value={"n_by_wave": nmap}))
        else:
            sc_site_only = False
            piv = _pivot_waves(df).sort_values("delta")
            piv["material"] = piv.delta.abs() >= SURVEY_MATERIAL
            top = piv[piv.item.isin(sc.items)] if sc.items else pd.concat([piv[piv.material & (piv.delta < 0)], piv.head(2)]).drop_duplicates("item").head(3)
            for t in top.itertuples():
                tag = f"material: {SURVEY_MATERIAL:.2f} or more on a 5-point scale" if t.material else "within normal variation for a team this size"
                ev.append(Evidence(id=nid("S"), kind="survey_delta",
                                   statement=(f"{sc.site} {sc.team}, {t.item_label} ({t.item}): {t.w1:.2f} in Wave 1 to {t.w2:.2f} in Wave 2 "
                                              f"(n={nmap.get(1)} to {nmap.get(2)}), change {t.delta:+.2f} ({tag})."),
                                   sql=r.sql, rows=[{"item": t.item, "label": t.item_label, "wave1": t.w1, "wave2": t.w2, "delta": t.delta,
                                                     "n1": nmap.get(1), "n2": nmap.get(2), "material": bool(t.material)}],
                                   source="v_team_wave_item",
                                   value={"item": t.item, "wave1": t.w1, "wave2": t.w2, "delta": t.delta, "material": bool(t.material),
                                          "n1": nmap.get(1), "n2": nmap.get(2)}))
            stable = piv[~piv.material]
            ev.append(Evidence(id=nid("S"), kind="survey_stable",
                               statement=f"{len(stable)} of 12 items on this team moved by less than {SURVEY_MATERIAL:.2f} between waves ({', '.join(stable.item.tolist()) or 'none'}).",
                               sql=r.sql, rows=stable[["item", "delta"]].to_dict(orient="records"), source="v_team_wave_item",
                               value={"stable_count": int(len(stable))}))
            ev.append(Evidence(id=nid("S"), kind="survey_table", statement="All 12 items for this team, both waves (chart data).",
                               sql=r.sql, rows=r.to_records(), source="v_team_wave_item"))

    if sc.site and sc_site_only:
        r = db.run_sql(f"SELECT wave_id, item, item_label, mean_score, n FROM v_site_wave_item WHERE site_name = '{sc.site}' ORDER BY item, wave_id")
        df = r.rows
        piv = _pivot_waves(df)
        nmap = {int(k): int(v) for k, v in df.groupby("wave_id").n.first().to_dict().items()}
        worst = piv.sort_values("delta").head(2)
        for t in worst.itertuples():
            material = abs(t.delta) >= SURVEY_MATERIAL
            tag = "material" if material else "within normal variation"
            ev.append(Evidence(id=nid("S"), kind="survey_delta_site",
                               statement=f"{sc.site} site overall, {t.item_label} ({t.item}): {t.w1:.2f} in Wave 1 to {t.w2:.2f} in Wave 2 (n={nmap.get(1)} to {nmap.get(2)}), change {t.delta:+.2f} ({tag}).",
                               sql=r.sql, rows=[{"item": t.item, "wave1": t.w1, "wave2": t.w2, "delta": t.delta}], source="v_site_wave_item",
                               value={"item": t.item, "delta": t.delta, "material": material, "n1": nmap.get(1), "n2": nmap.get(2)}))

    # ---- reviewer: who responded (mix), and the mix-adjusted signal check
    if sc.team_id is not None and sc.intent in ("review_decline_real", "diagnose_drop"):
        ev += _analyze_mix(sc, db, nid, full=(sc.intent == "review_decline_real"))

    if sc.intent in ("review_decline_real", "tenure_pattern", "metric_lookup", "owner_lookup"):
        return ev

    # ---- operations: late departures by hour band and period
    if sc.site:
        shift_clause = f"AND shift = '{sc.shift}'" if sc.shift else ""
        r = db.run_sql(f"SELECT shift, hour_band, period, departures, late_departures, late_rate FROM v_ops_hour WHERE site_name = '{sc.site}' {shift_clause} ORDER BY shift, hour_band, period")
        df = r.rows
        if len(df):
            piv = df.pivot_table(index=["shift", "hour_band"], columns="period", values="late_rate", aggfunc="first").reset_index()
            if "Jan-May 2026" in piv.columns and "Jun-Sep 2026" in piv.columns:
                piv["change"] = piv["Jun-Sep 2026"] - piv["Jan-May 2026"]
                worst = piv.sort_values("change", ascending=False).iloc[0]
                before, after = float(worst["Jan-May 2026"]), float(worst["Jun-Sep 2026"])
                signal = (after - before) >= OPS_SIGNAL_ABS and after >= OPS_SIGNAL_RATIO * before
                others = piv[piv.hour_band != worst.hour_band]
                if signal:
                    stmt = (f"{sc.site} {worst['shift']} shift, departures in the {worst.hour_band} hour band: late-departure rate "
                            f"{_pct(before)} in Jan-May 2026 to {_pct(after)} in Jun-Sep 2026. "
                            f"Other hour bands stayed between {_pct(others['Jun-Sep 2026'].min())} and {_pct(others['Jun-Sep 2026'].max())} in Jun-Sep. "
                            f"This is an operational signal (rise of {OPS_SIGNAL_ABS * 100:.0f} points or more and at least {OPS_SIGNAL_RATIO}x).")
                else:
                    stmt = (f"No hour band on {sc.site} {worst['shift']} changed materially: late-departure rates stayed between "
                            f"{_pct(piv['Jun-Sep 2026'].min())} and {_pct(piv['Jun-Sep 2026'].max())} in Jun-Sep 2026 "
                            f"(largest change {(after - before) * 100:+.1f} points, in the {worst.hour_band} band). No operational signal.")
                ev.append(Evidence(id=nid("O"), kind="ops_hour", statement=stmt, sql=r.sql, rows=r.to_records(), source="v_ops_hour",
                                   value={"hour_band": worst.hour_band, "before": before, "after": after, "signal": bool(signal),
                                          "shift": worst["shift"], "handoff_band": worst.hour_band in HANDOFF_BANDS}))
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
        low = df[df.ratio < STAFFING_LOW]
        if len(low):
            parts = [f"{x.month}: {int(x.actual_headcount)} of {int(x.scheduled_headcount)} scheduled ({_pct(x.ratio)})" for x in low.itertuples()]
            ev.append(Evidence(id=nid("O"), kind="staffing",
                               statement=f"Staffing on {sc.site} {sc.shift or ''} fell below {STAFFING_LOW * 100:.0f}% of scheduled in: " + "; ".join(parts) + f". Other months were at or above {STAFFING_LOW * 100:.0f}%.",
                               sql=r.sql, rows=r.to_records(), source="staffing", value={"low_months": low.month.tolist()}))
        else:
            ev.append(Evidence(id=nid("O"), kind="staffing", statement=f"Staffing on {sc.site} {sc.shift or ''} stayed at or above {STAFFING_LOW * 100:.0f}% of scheduled in every month.",
                               sql=r.sql, rows=r.to_records(), source="staffing", value={"low_months": []}))
    return ev


def _analyze_mix(sc: Scope, db: DB, nid, full: bool) -> list[Evidence]:
    """Who responded, by tenure band, and (for the signal check) how much of the team's change in
    grand mean is explained by the change in who responded, holding band means at the company level."""
    ev = []
    r = db.run_sql(f"SELECT wave_id, tenure_band, n, grand_mean FROM v_team_tenure_mix WHERE team_id = {sc.team_id} ORDER BY wave_id, tenure_band")
    df = r.rows
    if not len(df):
        return ev
    tot = {int(k): int(v) for k, v in df.groupby("wave_id").n.sum().to_dict().items()}
    if min(tot.values(), default=0) < config.MIN_N:
        return ev  # who-responded breakdowns are not shown for team-waves under the reporting threshold
    u1 = {int(k): int(v) for k, v in df[df.tenure_band == "under_1"].groupby("wave_id").n.sum().to_dict().items()}
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
    if not full:
        return ev
    # signal check: observed change in grand mean vs the change expected from composition alone
    r2 = db.run_sql(f"SELECT wave_id, ROUND(AVG(mean_score), 2) AS grand_mean, MIN(n) AS n FROM v_team_wave_item WHERE team_id = {sc.team_id} AND reportable GROUP BY 1 ORDER BY 1")
    gm = {int(row["wave_id"]): float(row["grand_mean"]) for row in r2.to_records()}
    r3 = db.run_sql("SELECT tenure_band, ROUND(SUM(mean_score * n) / SUM(n), 2) AS band_mean, SUM(n) / 12 AS n FROM v_tenure_wave_item WHERE reportable GROUP BY 1 ORDER BY 1")
    band_mean = {row["tenure_band"]: float(row["band_mean"]) for row in r3.to_records()}
    shares = {}
    for w in (1, 2):
        sub = df[df.wave_id == w]
        shares[w] = {b: int(x) / tot.get(w, 1) for b, x in sub.groupby("tenure_band").n.sum().to_dict().items()}
    bands = ["under_1", "1_to_3", "3_to_10", "over_10"]
    expected = sum((shares[2].get(b, 0) - shares[1].get(b, 0)) * band_mean.get(b, 0) for b in bands)
    observed = gm.get(2, float("nan")) - gm.get(1, float("nan"))
    residual = observed - expected
    if abs(observed) < SURVEY_MATERIAL:
        verdict, text = "no_material_change", f"The team grand mean moved {observed:+.2f}, less than {SURVEY_MATERIAL:.2f}: no material change to explain."
    elif abs(residual) < MIX_EXPLAINS:
        verdict, text = "mix", (f"The team grand mean moved {observed:+.2f} ({gm.get(1):.2f} to {gm.get(2):.2f}). Holding each tenure band at its company-wide mean, "
                                f"the change in who responded alone would move it {expected:+.2f}; the remaining {residual:+.2f} is within normal variation for "
                                f"{tot.get(2)} respondents. Verdict: mostly a change in who responded, not a real decline. Watch item, not a finding.")
    else:
        verdict, text = "real", (f"The team grand mean moved {observed:+.2f} ({gm.get(1):.2f} to {gm.get(2):.2f}). The change in who responded explains "
                                 f"{expected:+.2f} of it; {residual:+.2f} remains after adjusting. Verdict: the change persists after adjusting for who responded.")
    rows = [{"tenure_band": b, "share_w1": round(shares[1].get(b, 0), 2), "share_w2": round(shares[2].get(b, 0), 2),
             "company_band_mean": band_mean.get(b), "n_w1": int(df[(df.wave_id == 1) & (df.tenure_band == b)].n.sum()),
             "n_w2": int(df[(df.wave_id == 2) & (df.tenure_band == b)].n.sum())} for b in bands]
    ev.append(Evidence(id=nid("S"), kind="signal_check", statement=text, sql=r3.sql + ";\n" + r2.sql, rows=rows, source="v_team_tenure_mix, v_tenure_wave_item, v_team_wave_item",
                       value={"observed": round(observed, 2), "expected_from_mix": round(expected, 2), "residual": round(residual, 2),
                              "verdict": verdict, "gm_w1": gm.get(1), "gm_w2": gm.get(2), "n_w1": tot.get(1), "n_w2": tot.get(2)}))
    return ev


def _analyze_site_overview(sc: Scope, db: DB, nid) -> list[Evidence]:
    ev = []
    r = db.run_sql(f"SELECT team_id, team_name, shift, wave_id, item, item_label, mean_score, n, reportable FROM v_team_wave_item WHERE site_name = '{sc.site}' ORDER BY team_id, item, wave_id")
    df = r.rows
    cells, suppressed, watch = [], [], []
    for tid, g in df.groupby("team_id"):
        name = g.team_name.iloc[0]
        if not bool(g.reportable.all()):
            ns = {int(k): int(v) for k, v in g.groupby("wave_id").n.first().to_dict().items()}
            suppressed.append({"team_id": int(tid), "team_name": name, "n_by_wave": ns})
            continue
        piv = _pivot_waves(g)
        for t in piv.itertuples():
            cells.append({"team_id": int(tid), "team_name": name, "shift": g["shift"].iloc[0], "item": t.item, "item_label": t.item_label,
                          "wave1": t.w1, "wave2": t.w2, "delta": t.delta, "n": int(g[g.wave_id == 2].n.iloc[0])})
            if t.delta <= -SURVEY_MATERIAL:
                watch.append((name, t.item, t.item_label, t.delta))
    watch.sort(key=lambda x: x[3])
    ev.append(Evidence(id=nid("S"), kind="site_heatmap",
                       statement=(f"{sc.site}: {len({c['team_id'] for c in cells})} teams reportable in both waves, {len(suppressed)} suppressed (fewer than {config.MIN_N} respondents: "
                                  f"{', '.join(s['team_name'] for s in suppressed) or 'none'}). Team-level watch items (item fell {SURVEY_MATERIAL:.2f} or more): "
                                  + ("; ".join(f"{n} {i} {d:+.2f}" for n, i, _, d in watch[:6]) if watch else "none") + "."),
                       sql=r.sql, rows=cells, source="v_team_wave_item",
                       value={"suppressed": suppressed, "watch": [{"team": n, "item": i, "label": l, "delta": d} for n, i, l, d in watch]}))
    r2 = db.run_sql(f"SELECT wave_id, item, item_label, mean_score, n FROM v_site_wave_item WHERE site_name = '{sc.site}' ORDER BY item, wave_id")
    piv = _pivot_waves(r2.rows)
    nmap = {int(k): int(v) for k, v in r2.rows.groupby("wave_id").n.first().to_dict().items()}
    company = _company_item_means(db)
    piv["company_mean"] = piv.item.map(company)
    piv["vs_company"] = (piv.w2 - piv.company_mean).round(2)
    strength = piv.sort_values("vs_company", ascending=False).iloc[0].to_dict()
    opps = piv.sort_values("vs_company").head(2).to_dict(orient="records")
    material = piv[piv.delta.abs() >= SURVEY_MATERIAL]
    ev.append(Evidence(id=nid("S"), kind="site_items",
                       statement=(f"{sc.site} site level (n={nmap.get(1)} to {nmap.get(2)}, where comparisons are meaningful): strength = {strength['item_label']} ({strength['item']}) at {strength['w2']:.2f}, "
                                  f"{strength['vs_company']:+.2f} vs the company mean; two opportunities = {', '.join(f'{o[chr(105)+chr(116)+chr(101)+chr(109)+chr(95)+chr(108)+chr(97)+chr(98)+chr(101)+chr(108)]} ({o[chr(105)+chr(116)+chr(101)+chr(109)]}) at {o[chr(119)+chr(50)]:.2f}, {o[chr(118)+chr(115)+chr(95)+chr(99)+chr(111)+chr(109)+chr(112)+chr(97)+chr(110)+chr(121)]:+.2f} vs company' for o in opps)}. "
                                  + (f"Items that moved {SURVEY_MATERIAL:.2f} or more at site level: " + ", ".join(f"{m.item} {m.delta:+.2f}" for m in material.itertuples()) + "."
                                     if len(material) else f"No item moved {SURVEY_MATERIAL:.2f} or more at site level.")),
                       sql=r2.sql, rows=piv.to_dict(orient="records"), source="v_site_wave_item",
                       value={"strength": strength["item"], "opportunities": [o["item"] for o in opps], "n1": nmap.get(1), "n2": nmap.get(2)}))
    return ev


# ----------------------------------------------------------------------------- step 3: retrieve

def _theme_of(text: str) -> str | None:
    t = text.lower()
    best, best_hits = None, 0
    for name, spec in THEMES.items():
        hits = sum(1 for k in spec["keywords"] if k in t)
        if hits > best_hits:
            best, best_hits = name, hits
    return best


def retrieve(sc: Scope, question: str, db: DB, retriever: Retriever, evidence: list[Evidence]) -> list[Evidence]:
    ev: list[Evidence] = []
    if sc.intent in ("tenure_pattern", "metric_lookup", "site_overview", "review_decline_real", "owner_lookup"):
        return ev
    if sc.team_id is None and sc.site is None:
        return ev
    # 1. every reportable comment for the scoped team (or site + shift), counted by theme in code
    if sc.team_id is not None:
        where = f"team_id = {sc.team_id}"
        filters = {"team_id": sc.team_id}
    else:
        where = f"site_name = '{sc.site}'" + (f" AND shift = '{sc.shift}'" if sc.shift else "")
        filters = {"site_name": sc.site, "shift": sc.shift}
    r = db.run_sql(f"SELECT comment_id, wave_id, text FROM v_comments_reportable WHERE {where} AND wave_id = 2 ORDER BY comment_id")
    rows = r.to_records()
    counts: dict[str, int] = {}
    for row in rows:
        th = _theme_of(str(row["text"]))
        row["theme"] = th or "other"
        row["words"] = len(str(row["text"]).split())
        counts[row["theme"]] = counts.get(row["theme"], 0) + 1
    total = len(rows)
    ranked = sorted(((k, v) for k, v in counts.items() if k != "other"), key=lambda kv: -kv[1])
    top_theme, top_count = (ranked[0] if ranked else (None, 0))
    theme_rows = [{"theme": THEMES[k]["label"] if k in THEMES else k, "comments": v, "share": round(v / total, 2) if total else 0,
                   "corroborating": v >= COMMENT_BREADTH} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
    if total:
        stmt = (f"Wave 2 comments from {sc.site} {sc.team or sc.shift or ''}: {total} in total. By theme: "
                + "; ".join(f"{t['theme']} {t['comments']}" for t in theme_rows) + ". "
                + (f"'{THEMES[top_theme]['label']}' has {top_count} separate comments, which meets the breadth rule ({COMMENT_BREADTH} or more) and counts as corroborating."
                   if top_theme and top_count >= COMMENT_BREADTH else
                   (f"No theme reaches {COMMENT_BREADTH} separate comments; the most frequent, '{THEMES[top_theme]['label']}', is a single source ({top_count} of {total}) and does not corroborate on its own."
                    if top_theme else f"No theme reaches {COMMENT_BREADTH} separate comments.")))
    else:
        stmt = f"No reportable Wave 2 comments for {sc.site} {sc.team or sc.shift or ''}."
    ev.append(Evidence(id="T1", kind="comment_themes", statement=stmt, sql=r.sql, rows=theme_rows, source="v_comments_reportable",
                       value={"total": total, "top_theme": top_theme, "top_count": top_count, "breadth_ok": bool(top_theme and top_count >= COMMENT_BREADTH),
                              "counts": counts}))
    # 2. the most relevant comments, retrieved by similarity to the question and the items that moved
    item_labels = [e.value.get("item", "") for e in evidence if e.kind == "survey_delta" and e.value.get("material")]
    labels = db.items().set_index("item").label.to_dict()
    query = question + " " + " ".join(labels.get(i, "") for i in item_labels)
    hits = retriever.search(query, k=4, kind="comment", filters=filters)
    for i, (c, s) in enumerate(hits, 1):
        th = _theme_of(c.text)
        words = len(c.text.split())
        quoted = c.text if words <= 60 else c.text[:280].rstrip() + " [...]"
        ev.append(Evidence(id=f"C{i}", kind="comment", origin="retrieved",
                           statement=f"Employee comment ({c.title}; {words} words; theme: {THEMES[th]['label'] if th else 'other'}): \"{quoted}\"",
                           source=c.chunk_id, value={"score": round(s, 3), "words": words, "theme": th, **c.meta}))
    # 3. documents, retrieved by the question, the top theme (and its keywords), and the items that moved.
    #    Gallup's discussion questions are quoted in the action plan for the focus item, not used as diagnostic evidence.
    theme_words = " ".join(THEMES[top_theme]["keywords"] + [THEMES[top_theme]["label"]]) if top_theme else ""
    themes = " ".join(e.statement for e in evidence[:4]) + " " + theme_words + " " + " ".join(labels.get(i, "") for i in item_labels)
    kws = THEMES[top_theme]["keywords"] if top_theme else []
    dhits = [(c, s) for c, s in retriever.search(question + " " + themes[:500], k=8, kind="doc")
             if not c.chunk_id.startswith("doc:gallup_item_discussion_questions")]
    # deterministic re-rank: sections that mention the corroborated theme's own words come first (keeps keyword mode honest)
    dhits.sort(key=lambda cs: (-sum(1 for k in kws if k in cs[0].text.lower()), -cs[1]))
    dhits = dhits[:3]
    for i, (c, s) in enumerate(dhits, 1):
        ev.append(Evidence(id=f"D{i}", kind="doc", origin="retrieved", statement=f"Document ({c.title}): {c.text[:400].strip()}",
                           source=c.chunk_id, value={"score": round(s, 3), **c.meta}))
    return ev


# ----------------------------------------------------------------------------- step 4: assess (computed)

def assess(sc: Scope, evidence: list[Evidence], db: DB) -> Assessment | None:
    """Decide, in code, whether the evidence supports naming an obstacle. Appends the owner
    evidence (W1) only when it does. The model is told the verdict; it cannot change it."""
    if sc.intent != "diagnose_drop":
        return None
    by = {}
    for e in evidence:
        by.setdefault(e.kind, []).append(e)
    a = Assessment(verdict="insufficient", label="")
    suppressed = bool(by.get("suppressed"))
    a.level = "site" if suppressed or sc.team_id is None else "team"
    deltas = by.get("survey_delta", []) if a.level == "team" else by.get("survey_delta_site", [])
    a.n = {"w1": deltas[0].value.get("n1"), "w2": deltas[0].value.get("n2")} if deltas else {}
    a.survey_signal = any(e.value.get("material") and e.value.get("delta", 0) < 0 for e in deltas)
    ops = by.get("ops_hour", [None])[0]
    a.ops_signal = bool(ops and ops.value.get("signal"))
    a.staffing_signal = bool(by.get("staffing") and by["staffing"][0].value.get("low_months"))
    themes = by.get("comment_themes", [None])[0]
    a.comment_signal = bool(themes and themes.value.get("breadth_ok"))
    fell = [f"{e.value['item']} {e.value['delta']:+.2f}" for e in deltas if e.value.get("material") and e.value.get("delta", 0) < 0]
    if a.survey_signal:
        a.reasons.append(f"Survey: material fall on {', '.join(fell)} ({a.level} level, n={a.n.get('w1')} to {a.n.get('w2')}).")
    else:
        a.reasons.append(f"Survey: no item fell {SURVEY_MATERIAL:.2f} or more at {a.level} level.")
    a.reasons.append(("Operations: late departures rose in the " + ops.value["hour_band"] + " band (signal).") if a.ops_signal
                     else ("Operations: no hour band changed materially (no signal)." if ops else "Operations: no records for this scope."))
    if themes and themes.value.get("top_theme"):
        a.reasons.append(f"Comments: top theme '{THEMES[themes.value['top_theme']]['label']}' with {themes.value['top_count']} of {themes.value['total']} comments"
                         + (" (corroborating)." if a.comment_signal else f" (below the breadth rule of {COMMENT_BREADTH}; single source)."))
    elif themes:
        a.reasons.append(f"Comments: {themes.value.get('total', 0)} reportable Wave 2 comments, none on a recognisable theme.")
    if a.staffing_signal:
        a.reasons.append("Staffing: a shortage month exists and is listed as a competing explanation.")
    # theme and process
    if a.comment_signal:
        a.theme = themes.value["top_theme"]
    elif a.ops_signal and ops.value.get("handoff_band"):
        a.theme = "handoff"
    elif a.ops_signal:
        a.theme = "schedule"
    a.process = THEMES[a.theme]["process"] if a.theme else None
    # verdict
    if not a.survey_signal:
        a.verdict = "no_material_change"
        a.label = f"No material change at {a.level} level: nothing to diagnose. Watch list."
    elif a.ops_signal or a.comment_signal:
        a.verdict = "supported"
        a.label = f"Supported hypothesis ({a.level} level): {THEMES[a.theme]['label']}. Corroborated by " + \
                  " and ".join(x for x, ok in (("operational records", a.ops_signal), (f"{themes.value['top_count']} separate comments" if themes else "", a.comment_signal)) if ok) + "."
    else:
        a.verdict = "insufficient"
        a.label = "Insufficient evidence: the survey moved but nothing else did. Watch item, no action proposed."
    if suppressed and a.verdict != "supported":
        a.verdict = "suppressed_insufficient"
        a.label = (f"Team-level results suppressed (fewer than {config.MIN_N} respondents). Site-level evidence "
                   + ("shows no material change." if not a.survey_signal else "is insufficient to name an obstacle.")
                   + " Review the site results with the Site Operations Manager.")
    # owner, only when supported
    if a.verdict == "supported" and a.process:
        site_clause = f"AND (site_name = '{sc.site}' OR site_name = 'ALL')" if sc.site else ""
        r = db.run_sql(f"SELECT process_name, site_name, owner_role, owner_name FROM ownership_directory WHERE process_name = '{a.process}' {site_clause} ORDER BY site_name = 'ALL'")
        if len(r.rows):
            o = r.rows.iloc[0]
            evidence.append(Evidence(id="W1", kind="owner", statement=f"Process owner for '{o.process_name}' at {o.site_name}: {o.owner_role}, {o.owner_name} (ownership directory).",
                                     sql=r.sql, rows=r.to_records(), source="ownership_directory",
                                     value={"process": o.process_name, "role": o.owner_role, "name": o.owner_name}))
    return a


# ----------------------------------------------------------------------------- step 5: explain

NUM_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)")


def _allowed_numbers(evidence: list[Evidence]) -> set[str]:
    allowed = set(str(i) for i in range(0, 32))  # small integers: item numbers, months, days, waves
    allowed |= {f"{SURVEY_MATERIAL:.2f}", f"{SURVEY_MATERIAL:.1f}", "0.3", "0.30", "90", "5", "4", "12", "2026", "30", "60"}
    for e in evidence:
        for m in NUM_RE.finditer(e.statement):
            allowed.add(m.group(1))
        for v in e.value.values():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                allowed.add(f"{v:.2f}".rstrip("0").rstrip("."))
                allowed.add(f"{v:.2f}")
                allowed.add(f"{v * 100:.1f}")
                allowed.add(f"{v * 100:.0f}")
    return allowed


def check_brief(b: Brief, evidence: list[Evidence], assessment: Assessment | None = None) -> list[str]:
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
    if assessment and assessment.verdict != "supported":
        if not re.search(r"insufficient|no material|not enough|cannot name|does not support|suppressed", b.obstacle, re.I):
            problems.append("verdict is not 'supported': the obstacle must say the evidence is insufficient or that nothing changed materially")
        if re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", b.owner) and "not assigned" not in b.owner.lower():
            problems.append("verdict is not 'supported': owner must be 'Not assigned'")
    if assessment and assessment.verdict == "supported":
        owner_ev = next((e for e in evidence if e.kind == "owner"), None)
        if owner_ev and (owner_ev.value["role"] not in b.owner or owner_ev.value["name"] not in b.owner):
            problems.append(f"owner must name the process owner from the directory: {owner_ev.value['role']}, {owner_ev.value['name']}")
    return problems


def fallback_brief(sc: Scope, evidence: list[Evidence], assessment: Assessment | None = None) -> Brief:
    by_kind = {}
    for e in evidence:
        by_kind.setdefault(e.kind, []).append(e)
    for_, against, missing = [], [], []
    a = assessment
    theme_label = THEMES[a.theme]["label"] if a and a.theme else None
    owner = "Not assigned: the evidence does not support naming a process owner."
    if by_kind.get("owner"):
        o = by_kind["owner"][0]
        owner = f"{o.value['role']}, {o.value['name']} ({o.value['process']})"
    # obstacle by verdict (computed)
    if a is None or a.verdict == "supported":
        band = by_kind["ops_hour"][0].value["hour_band"] if by_kind.get("ops_hour") and by_kind["ops_hour"][0].value.get("signal") else None
        obstacle = (f"The {theme_label} process" + (f" (departures in the {band} hour band)" if band else "") +
                    " is the most likely obstacle. This is a supported hypothesis, not a proven cause.")
    elif a.verdict == "no_material_change":
        obstacle = f"No material change: no survey item on this {a.level} fell {SURVEY_MATERIAL:.2f} or more between waves, so there is no decline to diagnose. Keep on the watch list."
    elif a.verdict == "suppressed_insufficient":
        obstacle = (f"Team-level results are suppressed (fewer than {config.MIN_N} respondents) and the site-level evidence is insufficient to name an obstacle. "
                    "Review the site-level results with the Site Operations Manager instead.")
    else:
        obstacle = ("Insufficient evidence: the survey fell but the operational records and comments show nothing that corroborates it. "
                    "Treat it as a watch item; do not act on the survey alone.")
    for e in by_kind.get("suppressed", []):
        for_.insert(0, {"claim": e.statement, "evidence_ids": [e.id]})
    for e in by_kind.get("survey_delta", [])[:2] + by_kind.get("survey_delta_site", [])[:2]:
        (for_ if e.value.get("material") else against).append({"claim": e.statement, "evidence_ids": [e.id]})
    if by_kind.get("ops_hour"):
        e = by_kind["ops_hour"][0]
        (for_ if e.value.get("signal") else against).append({"claim": e.statement, "evidence_ids": [e.id]})
    if by_kind.get("comment_themes"):
        e = by_kind["comment_themes"][0]
        ids = [e.id] + [c.id for c in by_kind.get("comment", []) if c.value.get("theme") == e.value.get("top_theme")]
        (for_ if e.value.get("breadth_ok") else against).append({"claim": e.statement, "evidence_ids": ids})
    if by_kind.get("doc") and a and a.verdict == "supported":
        want = (a.process or "").split()[0].lower() if a.process else ""
        d = next((x for x in by_kind["doc"] if want and want in x.statement.lower()), by_kind["doc"][0])
        title = d.statement.split("):")[0].replace("Document (", "")
        for_.append({"claim": f"The relevant procedure is documented ({title}).", "evidence_ids": [d.id]})
    if by_kind.get("staffing"):
        e = by_kind["staffing"][0]
        against.append({"claim": ("Competing explanation: " if e.value.get("low_months") else "") + e.statement, "evidence_ids": [e.id]})
    if by_kind.get("tenure_mix"):
        e = by_kind["tenure_mix"][0]
        (against if e.value.get("mix_shift") else for_).append({"claim": e.statement, "evidence_ids": [e.id]})
    if by_kind.get("ops_rework"):
        against.append({"claim": by_kind["ops_rework"][0].statement, "evidence_ids": [by_kind["ops_rework"][0].id]})
    if a and a.verdict == "supported" and a.theme == "handoff":
        missing = ["No record of whether the handoff checklist is actually completed each shift.",
                   "No data on which trailers were late and why (dispatch notes)."]
        test = (f"Enforce the handoff checklist and signed log for 30 days on this site and shift; measure the late-departure rate in the "
                f"{by_kind['ops_hour'][0].value['hour_band'] if by_kind.get('ops_hour') else 'handoff'} hour band against Jun-Sep; review with the owner at day 30.")
    elif a and a.verdict == "supported":
        missing = ["No operational log tied to this theme; ask the process owner for the relevant records.",
                   "No follow-up wave yet to confirm whether the change persists."]
        test = f"Agree one change to the {theme_label} process with its owner, run it for 30 days, and re-measure the same items and the operational rate at day 30."
    else:
        missing = ["Operational records that would show whether work broke where the survey fell (delay logs, tickets, dispatch notes).",
                   "More than one wave of decline, or more than one comment on the same theme, before acting."]
        test = "No test proposed. Re-check at the next wave; if the item falls again, or an operational signal appears, diagnose then."
    limits = ("Fictional, synthetic data. Associations, not causes. Team-level figures are watch items shown only where n is 4 or more; "
              "inference belongs at site level. Real surveys carry response bias (only some people answer), which this data does not model.")
    return Brief(obstacle=obstacle, evidence_for=for_, evidence_against=against, missing=missing, owner=owner,
                 proposed_test=test, limits=limits, mode="fallback")


def _repair_citations(b: Brief, evidence: list[Evidence]) -> list[str]:
    """Deterministic repair of a near-miss citation: the model wrote S9 for O9 (right number, wrong
    prefix) and exactly one evidence id carries that number. Recorded in the check notes; anything
    else still fails the check."""
    ids = {e.id for e in evidence}
    by_num = {}
    for i in ids:
        m = re.match(r"^[A-Z]+(\d+)$", i)
        if m:
            by_num.setdefault(m.group(1), []).append(i)
    notes = []
    for section in ("evidence_for", "evidence_against"):
        for item in getattr(b, section):
            fixed = []
            for cid in item.get("evidence_ids", []):
                cid = str(cid).strip().strip("[]")
                m = re.match(r"^[A-Z]+(\d+)$", cid)
                if cid not in ids and m and len(by_num.get(m.group(1), [])) == 1:
                    notes.append(f"citation {cid} corrected to {by_num[m.group(1)][0]}")
                    cid = by_num[m.group(1)][0]
                fixed.append(cid)
            item["evidence_ids"] = fixed
    return notes


def explain(question: str, sc: Scope, evidence: list[Evidence], assessment: Assessment | None = None) -> Brief:
    if not config.has_key():
        return fallback_brief(sc, evidence, assessment)
    ev_text = "\n".join(f"[{e.id}] ({e.kind}, {e.origin}) {e.statement}" for e in evidence)
    verdict_text = (f"VERDICT COMPUTED BY CODE (you cannot change it): {assessment.verdict}. {assessment.label} Reasons: {' '.join(assessment.reasons)}"
                    if assessment else "VERDICT: none (not a diagnosis).")
    owner_ev = next((e for e in evidence if e.kind == "owner"), None)
    rule = (("Because the verdict is 'supported', name the obstacle as a supported hypothesis and cite the corroborating evidence. "
             + (f"owner MUST be exactly '{owner_ev.value['role']}, {owner_ev.value['name']} ({owner_ev.value['process']})' (from [{owner_ev.id}])." if owner_ev else ""))
            if assessment and assessment.verdict == "supported" else
            "Because the verdict is NOT 'supported', the obstacle field MUST begin with 'Insufficient evidence' or 'No material change' or 'Team-level results are suppressed', "
            "owner MUST be exactly 'Not assigned: the evidence does not support naming a process owner.', and proposed_test must say no test is proposed and what to collect instead.")
    system = (
        "You write a one-page evidence brief for a site or shift manager at a logistics company. "
        "Use ONLY the evidence provided. Every claim must cite one or more evidence ids in evidence_ids. "
        "Never introduce a number that does not appear in the evidence text. Never claim a cause; write "
        "'supported hypothesis'. Name competing explanations under evidence_against. List what evidence is missing. "
        "A single long comment is one source: never treat it as a pattern. "
        f"{rule} "
        "Return ONLY a JSON object with keys: obstacle (string), evidence_for (list of {claim, evidence_ids}), "
        "evidence_against (list of {claim, evidence_ids}), missing (list of strings), owner (string), "
        "proposed_test (string: a 30-day experiment with a success measure and a review date), limits (string). "
        "Length: obstacle at most 40 words; each claim at most 30 words; at most 5 claims for and 3 against; "
        "missing at most 4 items of one sentence each; proposed_test at most 60 words; limits at most 40 words. "
        "Plain language for a manager; no headings inside strings."
    )
    user = f"Question: {question}\n\n{verdict_text}\n\nEvidence:\n{ev_text}\n\nScope: {json.dumps(asdict(sc))}"
    notes = []
    for attempt in range(2):
        try:
            out = llm.chat_json(system, user if attempt == 0 else user + "\n\nYour previous draft failed these checks: " + "; ".join(notes) + ". Fix them.")
        except llm.LLMUnavailable as e:
            b = fallback_brief(sc, evidence, assessment)
            b.check_notes = [f"model unavailable ({e}); templated brief shown"]
            return b
        b = Brief(obstacle=str(out.get("obstacle", "")), evidence_for=list(out.get("evidence_for") or []),
                  evidence_against=list(out.get("evidence_against") or []), missing=[str(m) for m in (out.get("missing") or [])],
                  owner=str(out.get("owner", "")), proposed_test=str(out.get("proposed_test", "")), limits=str(out.get("limits", "")),
                  mode="llm")
        corrections = _repair_citations(b, evidence)
        notes = check_brief(b, evidence, assessment)
        if not notes:
            b.check_notes = ["passed: every citation exists, every number appears in the evidence, verdict respected"] + corrections
            return b
    fb = fallback_brief(sc, evidence, assessment)
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
    if sc.intent in ("diagnose_drop", "review_decline_real", "metric_lookup", "owner_lookup", "site_overview") and sc.site is None and sc.team_id is None:
        return Result(status="refused", question=question, scope=sc, evidence=[], brief=None,
                      message="Which site or team do you mean? Known sites: " + ", ".join(db.sites()) + ".", notes=notes)
    if sc.intent == "owner_lookup":
        return _owner_lookup(question, sc, db, [], notes)
    evidence = analyze(sc, db)
    evidence += retrieve(sc, question, db, retriever, evidence)
    if not evidence:
        return Result(status="refused", question=question, scope=sc, evidence=[], brief=None,
                      message="The data cannot answer this question; no evidence was found for that scope.", notes=notes)
    if sc.intent in ("tenure_pattern", "metric_lookup", "review_decline_real", "site_overview"):
        kinds = ("tenure_pattern", "survey_delta", "signal_check", "suppressed", "site_heatmap", "site_items") if sc.intent != "review_decline_real" else ("signal_check", "tenure_mix", "suppressed")
        msg = " ".join(e.statement for e in evidence if e.kind in kinds)
        return Result(status="ok", question=question, scope=sc, evidence=evidence, brief=None, message=msg, notes=notes)
    assessment = assess(sc, evidence, db)
    brief = explain(question, sc, evidence, assessment)
    notes.append(f"brief mode: {brief.mode}")
    status = "suppressed" if any(e.kind == "suppressed" for e in evidence) else "ok"
    return Result(status=status, question=question, scope=sc, evidence=evidence, brief=brief, notes=notes, assessment=assessment)


def _owner_lookup(question: str, sc: Scope, db: DB, evidence: list[Evidence], notes: list[str]) -> Result:
    ql = question.lower()
    process = next((spec["process"] for name, spec in THEMES.items() if any(k in ql for k in spec["keywords"] + [name])), "Shift handoff procedure")
    site_clause = f"AND (site_name = '{sc.site}' OR site_name = 'ALL')" if sc.site else ""
    r = db.run_sql(f"SELECT process_name, site_name, owner_role, owner_name FROM ownership_directory WHERE process_name = '{process}' {site_clause} ORDER BY site_name = 'ALL'")
    if len(r.rows):
        o = r.rows.iloc[0]
        evidence.append(Evidence(id="W1", kind="owner", statement=f"Process owner for '{o.process_name}' at {o.site_name}: {o.owner_role}, {o.owner_name} (ownership directory).",
                                 sql=r.sql, rows=r.to_records(), source="ownership_directory", value={"process": o.process_name, "role": o.owner_role, "name": o.owner_name}))
        msg = evidence[-1].statement
    else:
        msg = "No owner found in the directory for that process."
    return Result(status="ok", question=question, scope=sc, evidence=evidence, brief=None, message=msg, notes=notes)


# ----------------------------------------------------------------------------- act: action plan and report

ACTION_BANK = {
    "handoff": [
        ("Reinstate the signed handoff log and load checklist for every departure at the shift boundary; Dispatch releases no trailer without it.", "Dispatch Supervisor"),
        ("Hold the ten-minute handoff meeting at the dispatch desk with both shift leads present, every shift, for 30 days.", "Site Operations Manager"),
        ("Post the completed-checklist count and the handoff-hour late-departure rate on the shift board every week.", "Site Operations Manager"),
        ("Run the State of the Team conversation on the focus item and record which suggestions the team says have not been acted on.", "Team manager"),
    ],
    "equipment": [
        ("Review every open maintenance ticket older than seven days with the Maintenance Lead and set a closure date for each.", "Maintenance Lead"),
        ("Publish the equipment availability count per shift on the shift board every week.", "Site Operations Manager"),
        ("Agree a borrowing rule between shifts so a down unit does not stall the loading line.", "Site Operations Manager"),
        ("Run the State of the Team conversation on the focus item and list the essentials the team says are missing.", "Team manager"),
    ],
    "schedule": [
        ("Review the staffing report with the Director of Operations and agree a recovery plan for any month under the policy floor.", "Director of Operations"),
        ("Publish schedules 14 days ahead as the policy requires and track the exceptions weekly.", "Dispatch Supervisor"),
        ("Set a shift-swap turnaround target and post it on the shift board.", "Site Operations Manager"),
        ("Run the State of the Team conversation on the focus item and record what notice the team says it needs.", "Team manager"),
    ],
    "generic": [
        ("Hold the State of the Team conversation on the focus item and agree three actions with the team.", "Team manager"),
        ("Record each action with an owner, a success measure, and a review date in the action-planning tracker.", "HR Business Partner"),
        ("Review progress in a five-to-ten-minute check-in every two weeks.", "Team manager"),
    ],
}


def _item_questions(item: str) -> tuple[list[str], str]:
    """Gallup's item-specific discussion questions for one item, quoted verbatim from the doc file."""
    path = config.DOCS_DIR / "gallup_item_discussion_questions.md"
    if not path.exists():
        return [], ""
    text = path.read_text()
    m = re.search(rf"## {item.upper()}\.[^\n]*\n(.*?)(?=\n## |\Z)", text, re.S)
    qs = [line[2:].strip() for line in (m.group(1).splitlines() if m else []) if line.startswith("- ")]
    return qs, "Gallup, State of the Team Conversation Outline, 'Item-Specific Questions to Guide Discussion' (2016, 2023). Quoted verbatim, unaltered."


def plan(result: Result, db: DB) -> ActionPlan | None:
    """Feature 3, act and review, in Gallup's State of the Team shape. Only when the verdict is supported."""
    a = result.assessment
    if not a or a.verdict != "supported" or not result.brief:
        return None
    by = {}
    for e in result.evidence:
        by.setdefault(e.kind, []).append(e)
    deltas = sorted([e for e in by.get("survey_delta", []) + by.get("survey_delta_site", []) if e.value.get("material")], key=lambda e: e.value["delta"])
    # focus item: the fallen item most relevant to the theme (Gallup: "select the engagement item relevant to the goal"),
    # else the largest fall
    fell = [e.value["item"] for e in deltas]
    preferred = THEME_ITEM.get(a.theme or "")
    focus = preferred if preferred in fell else (fell[0] if fell else "q02")
    labels = db.items().set_index("item").label.to_dict()
    ops = by.get("ops_hour", [None])[0]
    wave2 = db.waves().set_index("wave_id").close_date.to_dict().get(2)
    close = pd.Timestamp(wave2).date() if wave2 is not None else date(2026, 9, 10)
    review_date = (close + timedelta(days=60)).isoformat()
    if ops and ops.value.get("signal"):
        goal = (f"Bring the late-departure rate in the {ops.value['hour_band']} band on {result.scope.site} {ops.value['shift']} from "
                f"{_pct(ops.value['after'])} back to the Jan-May level of {_pct(ops.value['before'])} by {review_date}.")
        measure = f"Late-departure rate in the {ops.value['hour_band']} band, weekly, from v_ops_hour; target at or below {_pct(ops.value['before'])}."
    else:
        goal = f"Move {labels.get(focus, focus)} ({focus}) on {result.scope.site} {result.scope.team or ''} back to its Wave 1 level by the next survey wave."
        measure = f"{focus} team mean at the next wave, shown only if n is {config.MIN_N} or more."
    # allowed owners: this site's directory rows plus the team manager
    site_clause = f"WHERE site_name = '{result.scope.site}' OR site_name = 'ALL'" if result.scope.site else ""
    dr = db.run_sql(f"SELECT process_name, owner_role, owner_name FROM ownership_directory {site_clause} ORDER BY owner_role")
    owners = {r["owner_role"]: r["owner_name"] for r in dr.to_records()}
    if result.scope.team_id is not None:
        t = db.teams()
        owners["Team manager"] = t[t.team_id == result.scope.team_id].iloc[0].manager_name
    qs, src = _item_questions(focus)
    cadence = ("Five-to-ten-minute check-in every two weeks on two questions: did we complete the actions we said we would, and did completing them make a difference. "
               f"Re-measure the same items and the operational rate at the next wave; review with the process owner on {review_date}.")
    actions, mode, notes = _plan_actions_llm(result, a, focus, labels.get(focus, focus), owners) if config.has_key() else (None, "fallback", [])
    if not actions:
        bank = ACTION_BANK.get(a.theme or "generic", ACTION_BANK["generic"])
        actions = [{"action": txt, "owner_role": role} for txt, role in bank if role in owners][:4]
        mode = "fallback"
    for i, act in enumerate(actions):
        act["owner_name"] = owners.get(act["owner_role"], "")
        act["due"] = (close + timedelta(days=14 * (i + 1))).isoformat()
    return ActionPlan(goal=goal, focus_item=focus, focus_label=labels.get(focus, focus), actions=actions, success_measure=measure,
                      review_cadence=cadence, team_questions=qs, questions_source=src, mode=mode, check_notes=notes)


def _plan_actions_llm(result: Result, a: Assessment, focus: str, focus_label: str, owners: dict) -> tuple[list[dict] | None, str, list[str]]:
    ev_text = "\n".join(f"[{e.id}] {e.statement}" for e in result.evidence)
    system = ("You draft three or four immediate actions for a site or shift manager, in the shape of a State of the Team plan. "
              "Each action is one sentence of at most 25 words, concrete, and assignable. Use ONLY the evidence and the brief provided; "
              "never introduce a number that is not in the evidence. owner_role MUST be one of the allowed roles exactly. "
              "Return ONLY a JSON object: {\"actions\": [{\"action\": str, \"owner_role\": str}]}.")
    user = (f"Focus item: {focus} ({focus_label}). Theme: {THEMES[a.theme]['label'] if a.theme else 'general'}.\n"
            f"Allowed owner roles: {list(owners)}.\n\nBrief: {json.dumps(asdict(result.brief))}\n\nEvidence:\n{ev_text}")
    notes = []
    for attempt in range(2):
        try:
            out = llm.chat_json(system, user if attempt == 0 else user + "\n\nYour previous draft failed: " + "; ".join(notes))
        except llm.LLMUnavailable as e:
            return None, "fallback", [f"model unavailable ({e}); templated actions shown"]
        acts = [x for x in (out.get("actions") or []) if isinstance(x, dict) and x.get("action")]
        notes = []
        if not 3 <= len(acts) <= 4:
            notes.append(f"{len(acts)} actions; need 3 or 4")
        bad = [x.get("owner_role") for x in acts if x.get("owner_role") not in owners]
        if bad:
            notes.append(f"owner roles not in the directory: {bad}")
        allowed = _allowed_numbers(result.evidence)
        for x in acts:
            for m in NUM_RE.finditer(x["action"]):
                if m.group(1) not in allowed:
                    notes.append(f"number {m.group(1)} not in evidence")
        if not notes:
            return [{"action": x["action"], "owner_role": x["owner_role"]} for x in acts], "llm", ["passed: owners exist in the directory, numbers appear in the evidence"]
    return None, "fallback", ["model actions failed checks twice: " + "; ".join(notes) + "; templated actions shown"]


def report_markdown(result: Result, plan_: ActionPlan | None) -> str:
    b, a = result.brief, result.assessment
    lines = [f"# Friction Finder evidence brief", f"**Question:** {result.question}", "",
             f"**Verdict (computed):** {a.label if a else 'n/a'}", "",
             f"**Likely obstacle:** {b.obstacle}" if b else "", ""]
    if b:
        lines += ["## Evidence for"] + [f"- {i.get('claim')} [{', '.join(i.get('evidence_ids', []))}]" for i in b.evidence_for]
        lines += ["", "## Evidence against, competing explanations"] + [f"- {i.get('claim')} [{', '.join(i.get('evidence_ids', []))}]" for i in b.evidence_against]
        lines += ["", "## What is missing"] + [f"- {m}" for m in b.missing]
        lines += ["", f"**Process owner:** {b.owner}", "", f"**Proposed test:** {b.proposed_test}", "", f"**Limits:** {b.limits}", ""]
    if plan_:
        lines += ["## Action plan (State of the Team shape)", f"**Performance goal:** {plan_.goal}", f"**Focus item:** {plan_.focus_item}, {plan_.focus_label}", "",
                  "| # | Action | Owner | Due |", "|---|---|---|---|"]
        lines += [f"| {i + 1} | {x['action']} | {x['owner_role']}, {x['owner_name']} | {x['due']} |" for i, x in enumerate(plan_.actions)]
        lines += ["", f"**Success measure:** {plan_.success_measure}", f"**Review:** {plan_.review_cadence}", "",
                  "### Questions for the team conversation (quoted)"] + [f"- {q}" for q in plan_.team_questions] + [f"_Source: {plan_.questions_source}_", ""]
    lines += ["## Evidence register"] + [f"- [{e.id}] ({e.origin}) {e.statement}" for e in result.evidence]
    lines += ["", f"_Brief mode: {b.mode if b else 'n/a'}. Plan mode: {plan_.mode if plan_ else 'n/a'}. Synthetic data, fictional company. Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}._"]
    return "\n".join(lines)


def _svg_bars(rows: list[dict], key_x: str, series: list[tuple[str, str, str]], title: str, fmt_pct: bool = True) -> str:
    """Tiny dependency-free grouped bar chart for the HTML report. series = [(column, label, color)]."""
    if not rows:
        return ""
    xs = [r[key_x] for r in rows]
    vals = [float(r.get(col) or 0) for r in rows for col, _, _ in series]
    top = max(vals + [0.01])
    w, h, pad = 620, 220, 36
    gw = (w - 2 * pad) / max(len(xs), 1)
    bw = gw / (len(series) + 1)
    out = [f'<svg viewBox="0 0 {w} {h + 40}" width="100%" style="max-width:{w}px;font-family:Calibri,Arial,sans-serif;font-size:11px">',
           f'<text x="{pad}" y="14" font-weight="700" fill="#1B3A4B">{title}</text>']
    for i, x in enumerate(xs):
        for j, (col, _, color) in enumerate(series):
            v = float(rows[i].get(col) or 0)
            bh = (v / top) * (h - pad - 20)
            x0 = pad + i * gw + (j + 0.5) * bw
            out.append(f'<rect x="{x0:.1f}" y="{h - pad - bh:.1f}" width="{bw * 0.9:.1f}" height="{bh:.1f}" fill="{color}"/>')
            lab = f"{v * 100:.0f}%" if fmt_pct else f"{v:.2f}"
            out.append(f'<text x="{x0 + bw * 0.45:.1f}" y="{h - pad - bh - 3:.1f}" text-anchor="middle" fill="#6E7B85">{lab}</text>')
        out.append(f'<text x="{pad + (i + 0.5) * gw:.1f}" y="{h - pad + 14}" text-anchor="middle" fill="#1B3A4B">{x}</text>')
    for j, (_, label, color) in enumerate(series):
        out.append(f'<rect x="{pad + j * 150}" y="{h + 8}" width="10" height="10" fill="{color}"/><text x="{pad + j * 150 + 14}" y="{h + 17}" fill="#1B3A4B">{label}</text>')
    out.append("</svg>")
    return "\n".join(out)


def report_html(result: Result, plan_: ActionPlan | None) -> str:
    """One-page, self-contained HTML report (no external scripts) for the manager and the reviewer."""
    import html as _h
    b, a = result.brief, result.assessment
    by = {}
    for e in result.evidence:
        by.setdefault(e.kind, []).append(e)
    css = """body{font-family:Calibri,Arial,sans-serif;color:#1B3A4B;max-width:860px;margin:32px auto;padding:0 20px;line-height:1.4}
    h1{font-size:24px;margin:0 0 4px} h2{font-size:15px;text-transform:uppercase;letter-spacing:.6px;color:#3E7C8F;margin:22px 0 6px;border-bottom:1px solid #EAF0F2;padding-bottom:3px}
    .tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;color:#fff;background:#C8553D;margin-right:4px;letter-spacing:.5px}
    .tag.mid{background:#3E7C8F}.tag.grey{background:#6E7B85}.verdict{background:#EAF0F2;border-left:4px solid #3E7C8F;padding:10px 12px;margin:12px 0;font-weight:600}
    table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #EAF0F2;padding:5px 6px;text-align:left;vertical-align:top}th{color:#3E7C8F;font-weight:700}
    .ev{font-family:ui-monospace,Menlo,monospace;font-size:10px;color:#6E7B85}.small{font-size:11px;color:#6E7B85}ul{margin:4px 0 4px 18px;padding:0}li{margin:3px 0}
    @media print{body{margin:10px auto}}"""
    def li(items):
        return "".join(f"<li>{_h.escape(str(i.get('claim')))} <span class='ev'>[{', '.join(i.get('evidence_ids', []))}]</span></li>" for i in items) or "<li class='small'>none</li>"
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>Friction Finder brief</title><style>{css}</style></head><body>",
             "<span class='tag'>SYNTHETIC DATA</span><span class='tag mid'>FICTIONAL COMPANY</span>"
             f"<span class='tag grey'>{'MODEL-WRITTEN TEXT' if b and b.mode == 'llm' else 'TEMPLATED TEXT'}</span>",
             f"<h1>Friction Finder evidence brief</h1><div class='small'>Question: {_h.escape(result.question)} &middot; generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>",
             f"<div class='verdict'>Verdict (computed by code): {_h.escape(a.label if a else 'n/a')}</div>"]
    if b:
        parts += [f"<h2>Likely obstacle <span class='tag grey'>generated</span></h2><p>{_h.escape(b.obstacle)}</p>",
                  f"<h2>Evidence for</h2><ul>{li(b.evidence_for)}</ul>", f"<h2>Evidence against, competing explanations</h2><ul>{li(b.evidence_against)}</ul>",
                  "<h2>What is missing</h2><ul>" + "".join(f"<li>{_h.escape(m)}</li>" for m in b.missing) + "</ul>",
                  f"<h2>Process owner</h2><p>{_h.escape(b.owner)}</p><h2>Proposed test</h2><p>{_h.escape(b.proposed_test)}</p><p class='small'>Limits: {_h.escape(b.limits)}</p>"]
    if by.get("survey_table"):
        rows = by["survey_table"][0].rows
        piv = {}
        for r in rows:
            piv.setdefault(r["item"], {"item": r["item"]})[f"w{int(r['wave_id'])}"] = r.get("mean_score")
        parts.append("<h2>Survey items, Wave 1 vs Wave 2 <span class='tag mid'>computed</span></h2>" +
                     _svg_bars(list(piv.values()), "item", [("w1", "Wave 1 (Mar 2026)", "#CFE0E6"), ("w2", "Wave 2 (Sep 2026)", "#3E7C8F")], "Mean score, 1 to 5", fmt_pct=False))
    if by.get("ops_hour"):
        rows = by["ops_hour"][0].rows
        piv = {}
        for r in rows:
            piv.setdefault(r["hour_band"], {"hour_band": r["hour_band"]})[r["period"]] = r.get("late_rate")
        order = ["18-22", "22-02", "02-06", "06-07", "07-10", "10-14", "14-18"]
        parts.append("<h2>Late departures by hour band <span class='tag mid'>computed</span></h2>" +
                     _svg_bars([piv[k] for k in order if k in piv], "hour_band", [("Jan-May 2026", "Jan-May 2026", "#CFE0E6"), ("Jun-Sep 2026", "Jun-Sep 2026", "#C8553D")], "Late-departure rate"))
    if plan_:
        parts += ["<h2>Action plan, State of the Team shape <span class='tag grey'>" + ("generated" if plan_.mode == "llm" else "templated") + "</span></h2>",
                  f"<p><b>Performance goal:</b> {_h.escape(plan_.goal)}<br><b>Focus item:</b> {plan_.focus_item}, {_h.escape(plan_.focus_label)}</p>",
                  "<table><tr><th>#</th><th>Action</th><th>Owner</th><th>Due</th></tr>" +
                  "".join(f"<tr><td>{i + 1}</td><td>{_h.escape(x['action'])}</td><td>{_h.escape(x['owner_role'])}, {_h.escape(x['owner_name'])}</td><td>{x['due']}</td></tr>" for i, x in enumerate(plan_.actions)) + "</table>",
                  f"<p><b>Success measure:</b> {_h.escape(plan_.success_measure)}<br><b>Review:</b> {_h.escape(plan_.review_cadence)}</p>",
                  "<h2>Questions for the team conversation (quoted)</h2><ul>" + "".join(f"<li>{_h.escape(q)}</li>" for q in plan_.team_questions) + f"</ul><p class='small'>Source: {_h.escape(plan_.questions_source)}</p>"]
    parts.append("<h2>Evidence register</h2><table><tr><th>Id</th><th>Origin</th><th>Statement</th></tr>" +
                 "".join(f"<tr><td class='ev'>{e.id}</td><td class='small'>{e.origin}</td><td>{_h.escape(e.statement)}</td></tr>" for e in result.evidence) + "</table>")
    parts.append("<p class='small'>Every number comes from SQL views over aggregates (team-level shown only where n is 4 or more). Model-written text was checked: "
                 "every citation exists, every number appears in the evidence, no causal claims. A person approves before anything happens.</p></body></html>")
    return "\n".join(parts)


# ----------------------------------------------------------------------------- approve / flag

def approve(result: Result, decision: str, note: str = "", who: str = "reviewer") -> dict:
    """decision: approved | rejected | flagged. Flagged = 'this does not sound right' (judge Jamshidi, Sept 16)."""
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "who": who, "decision": decision, "note": note,
           "question": result.question, "verdict": result.assessment.verdict if result.assessment else None,
           "brief_mode": result.brief.mode if result.brief else None,
           "brief": asdict(result.brief) if result.brief else None,
           "evidence_ids": [e.id for e in result.evidence]}
    with open(config.APPROVALS_PATH, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def review_log() -> list[dict]:
    if not config.APPROVALS_PATH.exists():
        return []
    out = []
    for line in open(config.APPROVALS_PATH):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
