"""Operating-metric definitions and the structured query path (v0.8).

One definition per metric the screens show: name, view, numerator, denominator, unit, period, grain. The
dashboards' numbers come from app/impact.py; the same rows sit behind v_team_ops_month (app/db.py), and
tests/test_metrics.py checks that a question about Night A returns the board's figures.

Text-to-SQL here is tier 1 only: a question is read into a structured plan (metric, entity, months,
comparison), the plan is validated, and code compiles it to templated SQL over the views. The model never
writes this SQL. Every query still goes through db.run_sql and its sqlglot guard.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app import config
from app import impact as I
from app.db import DB


@dataclass(frozen=True)
class Metric:
    key: str
    label: str            # what the screens call it
    view: str
    numerator: str
    denominator: str      # what the count is divided by
    unit: str             # how the rate is shown
    scale: float          # rate per denominator unit x scale = the number shown
    period: str
    grain: str
    source: str           # where the client's data would come from


METRICS: dict[str, Metric] = {
    "late_departures": Metric("late_departures", I.KPI_LABELS["late_departures"], "v_team_ops_month", "late_departures", "head-months (people x months)",
                              "per 10 people per month", 10, "calendar month", "team-month", "dispatch / WMS export"),
    "absence_days": Metric("absence_days", I.KPI_LABELS["absence_days"], "v_team_ops_month", "absence_days", "head-months (people x months)",
                           "per 10 people per month", 10, "calendar month", "team-month", "timekeeping and attendance"),
    "quits": Metric("quits", I.KPI_LABELS["quits"], "v_team_ops_month", "quits", "head-months (people x months)",
                    "per 10 people per month", 10, "calendar month", "team-month", "HRIS (voluntary separations)"),
    "injuries": Metric("injuries", I.KPI_LABELS["injuries"], "v_team_ops_month", "injuries", "head-months (people x months)",
                       "per 10 people per month", 10, "calendar month", "team-month", "safety log (days-away cases)"),
    "rework": Metric("rework", I.KPI_LABELS["rework"], "v_team_ops_month", "rework", "head-months (people x months)",
                     "per 10 people per month", 10, "calendar month", "team-month", "WMS (rework events)"),
    "late_rate": Metric("late_rate", "Share of departures that left late", "v_ops_hour", "late_departures", "departures",
                        "% of departures", 100, "Jan-May 2026 vs Jun-Sep 2026", "site-shift-hour band", "dispatch / WMS export (kept per site and shift, not per team)"),
}

# words a manager uses -> metric key (the question reader's vocabulary for operating metrics)
METRIC_WORDS = [
    ("late_rate", ["late rate", "share of departures", "percent of departures", "% of departures", "hour band", "hour bands"]),
    ("late_departures", ["late departure", "late departures", "late trucks", "late truck", "deliveries late", "late deliveries", "delays", "on-time", "on time", "late"]),
    ("absence_days", ["absence", "absences", "absent", "sick", "call-out", "callouts", "call outs", "unplanned absence"]),
    ("quits", ["quit", "quits", "turnover", "attrition", "resignation", "resignations", "leavers", "separations"]),
    ("injuries", ["injury", "injuries", "safety", "incident", "incidents", "days-away", "accident", "accidents"]),
    ("rework", ["rework", "re-work", "errors", "mispicks"]),
]


def metric_in(text: str) -> str | None:
    t = text.lower()
    for key, words in METRIC_WORDS:
        if any(w in t for w in words):
            return key
    return None


def definition(key: str) -> dict:
    m = METRICS[key]
    return {"metric": m.key, "label": m.label, "view": m.view, "numerator": m.numerator, "denominator": m.denominator,
            "unit": m.unit, "period": m.period, "grain": m.grain, "source": m.source}


# ---------------------------------------------------------------------------------------------- plans
@dataclass
class MetricQuery:
    metric: str
    team_id: int | None = None
    site_id: int | None = None
    shift: str | None = None
    months: list[str] = field(default_factory=list)   # empty: the 3 full months before as_of (the board's window)
    as_of: str = I.AS_OF_DETECT
    by: str = "total"            # total | month
    compare_to: str | None = None   # None | 'comparable'


@dataclass
class MetricResult:
    status: str                  # ok | suppressed | missing_period | zero_denominator | unknown_metric | unknown_entity
    message: str
    metric: str
    entity: str = ""
    months: list[str] = field(default_factory=list)
    events: float | None = None
    exposure: float | None = None
    rate: float | None = None            # per denominator unit
    shown: float | None = None           # rate x scale (what the screen shows)
    rows: list[dict] = field(default_factory=list)
    sql: list[str] = field(default_factory=list)
    comparison: dict | None = None
    definition: dict = field(default_factory=dict)


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def available_months() -> list[str]:
    return sorted(I._data()[0]["month"].unique())


def months_label(ms: list[str]) -> str:
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if not ms:
        return ""
    a, b = ms[0], ms[-1]
    return f"{names[int(a[5:7]) - 1]} {a[:4]}" if a == b else f"{names[int(a[5:7]) - 1]}-{names[int(b[5:7]) - 1]} {b[:4]}"


def validate(q: MetricQuery, db: DB) -> MetricResult | None:
    """Return a non-ok result when the plan cannot be run as asked, or None when it can."""
    if q.metric not in METRICS:
        return MetricResult("unknown_metric", f"No definition for '{q.metric}'. Defined metrics: {', '.join(METRICS)}.", q.metric)
    if q.metric == "late_rate":
        return None
    teams = I._data()[1]
    if q.team_id is not None:
        row = teams[teams.team_id == q.team_id]
        if not len(row):
            return MetricResult("unknown_entity", f"No team with id {q.team_id}.", q.metric)
        if int(row.iloc[0].headcount) < config.MIN_N:
            return MetricResult("suppressed", f"{row.iloc[0].team_name} has fewer than {config.MIN_N} people, so its operating counts are not shown on their own; "
                                f"they are included in no team or site figure here either, so they cannot be recovered by subtraction.", q.metric)
    if q.site_id is not None and q.site_id not in set(I._data()[2].site_id):
        return MetricResult("unknown_entity", f"No site with id {q.site_id}.", q.metric)
    if q.shift is not None and q.shift not in ("Day", "Night"):
        return MetricResult("unknown_entity", f"No shift called '{q.shift}'.", q.metric)
    have = available_months()
    asked = q.months or I.window(q.as_of)
    missing = [m for m in asked if m not in have]
    if missing or not asked:
        return MetricResult("missing_period", f"The operating data covers {months_label(have)} ({have[0]} to {have[-1]}); "
                            f"{', '.join(missing) or 'that period'} is not in it.", q.metric, months=missing)
    return None


def _entity(q: MetricQuery) -> tuple[str, str]:
    """(SQL predicate, plain-words label) for the entity in the plan."""
    if q.team_id is not None:
        t = I._team(q.team_id)
        site = I._data()[2].set_index("site_id").loc[int(t["site_id"]), "site_name"]
        return f"team_id = {int(q.team_id)}", f"{site} {t['team_name']}"
    parts, label = [], []
    if q.site_id is not None:
        parts.append(f"site_id = {int(q.site_id)}")
        label.append(I._data()[2].set_index("site_id").loc[int(q.site_id), "site_name"])
    else:
        label.append("All sites")
    if q.shift:
        parts.append(f"shift = {_q(q.shift)}")
        label.append(f"{q.shift.lower()} shift")
    label.append(f"(teams of {config.MIN_N} or more people)")
    return (" AND ".join(parts) or "TRUE"), " ".join(label)


def query_metric(q: MetricQuery, db: DB) -> MetricResult:
    """Compile a validated plan to templated SQL on v_team_ops_month, run it through the guard, compute the rate."""
    db.sync_team_ops()
    bad = validate(q, db)
    if bad:
        bad.definition = definition(q.metric) if q.metric in METRICS else {}
        return bad
    if q.metric == "late_rate":
        return _late_rate(q, db)
    m = METRICS[q.metric]
    months = q.months or I.window(q.as_of)
    where, label = _entity(q)
    mlist = ", ".join(_q(x) for x in months)
    sql = (f"SELECT month, CAST(SUM({m.numerator}) AS BIGINT) AS events, CAST(SUM(headcount) AS BIGINT) AS head_months, COUNT(*) AS team_months "
           f"FROM {m.view} WHERE {where} AND month IN ({mlist}) GROUP BY month ORDER BY month")
    r = db.run_sql(sql)
    rows = [{"month": x["month"], "events": int(x["events"]), "head_months": int(x["head_months"]),
             "per_10": round(int(x["events"]) / int(x["head_months"]) * m.scale, 2) if int(x["head_months"]) else None} for x in r.to_records()]
    events = float(sum(x["events"] for x in rows))
    exposure = float(sum(x["head_months"] for x in rows))
    present = {x["month"] for x in rows}
    gaps = [x for x in months if x not in present]
    if exposure == 0:
        return MetricResult("zero_denominator", f"No head-months recorded for {label} in {months_label(months)}: the rate is undefined, not zero.",
                            q.metric, label, months, events, exposure, None, None, rows, [r.sql], None, definition(q.metric))
    rate = events / exposure
    res = MetricResult("ok", "", q.metric, label, months, events, exposure, rate, round(rate * m.scale, 1), rows, [r.sql], None, definition(q.metric))
    if gaps:
        res.message = f"No rows for {', '.join(gaps)}; the rate uses the months that have data."
    if q.compare_to == "comparable" and q.team_id is not None:
        res.comparison = _comparable(q, m, months, db)
        res.sql += res.comparison.pop("_sql")
    return res


def _comparable(q: MetricQuery, m: Metric, months: list[str], db: DB) -> dict:
    """Comparable teams exactly as app/impact.py defines them: the same shift at every site, 4 or more people,
    not the team itself. Their pooled rate x this team's head-months = the expected count the board shows."""
    t = I._team(q.team_id)
    ids = [int(x) for x in I._comparables(t).team_id]
    mlist = ", ".join(_q(x) for x in months)
    if not ids:
        return {"status": "unavailable", "teams": [], "_sql": []}
    sql = (f"SELECT team_id, site_name, team_name, CAST(SUM({m.numerator}) AS BIGINT) AS events, CAST(SUM(headcount) AS BIGINT) AS head_months "
           f"FROM {m.view} WHERE team_id IN ({', '.join(map(str, ids))}) AND month IN ({mlist}) GROUP BY ALL ORDER BY team_id")
    r = db.run_sql(sql)
    rows = r.to_records()
    ev = float(sum(int(x["events"]) for x in rows))
    ex = float(sum(int(x["head_months"]) for x in rows))
    pooled = ev / ex if ex else 0.0
    team_rows = [{"team_id": int(x["team_id"]), "team": f"{x['site_name']} {x['team_name']}", "events": int(x["events"]),
                  "head_months": int(x["head_months"]), "per_10": round(int(x["events"]) / int(x["head_months"]) * m.scale, 1) if int(x["head_months"]) else None}
                 for x in rows]
    return {"status": "ok", "rule": f"same shift ({t['shift']}) at every site, {config.MIN_N} or more people, excluding the team itself",
            "teams": team_rows, "pooled_rate": pooled, "pooled_shown": round(pooled * m.scale, 1), "events": ev, "exposure": ex, "_sql": [r.sql]}


def _late_rate(q: MetricQuery, db: DB) -> MetricResult:
    """Late-departure share by hour band and period, from dispatch records kept per site and shift."""
    m = METRICS["late_rate"]
    if q.site_id is None:
        return MetricResult("unknown_entity", "Dispatch records are kept per site and shift; name a site (or a team).", q.metric, definition=definition(q.metric))
    shift = q.shift
    if q.team_id is not None:
        t = I._team(q.team_id)
        shift = shift or t["shift"]
    sites = I._data()[2].set_index("site_id")
    label = f"{sites.loc[int(q.site_id), 'site_name']} {(shift or 'all').lower()} shift (all teams on that shift; dispatch is not recorded per team)"
    sql = (f"SELECT hour_band, period, departures, late_departures, late_rate FROM v_ops_hour WHERE site_id = {int(q.site_id)}"
           + (f" AND shift = {_q(shift)}" if shift else "") + " ORDER BY hour_band, period")
    r = db.run_sql(sql)
    rows = r.to_records()
    if not rows:
        return MetricResult("missing_period", f"No dispatch records for {label}.", q.metric, label, sql=[r.sql], definition=definition(q.metric))
    dep = float(sum(x["departures"] for x in rows))
    late = float(sum(x["late_departures"] for x in rows))
    if dep == 0:
        return MetricResult("zero_denominator", f"No departures recorded for {label}: the share is undefined.", q.metric, label, rows=rows, sql=[r.sql], definition=definition(q.metric))
    return MetricResult("ok", "", q.metric, label, ["Jan-May 2026", "Jun-Sep 2026"], late, dep, late / dep, round(late / dep * 100, 1),
                        [{**x, "late_pct": round(float(x["late_rate"]) * 100, 1)} for x in rows], [r.sql], None, definition(q.metric))


def sentence(res: MetricResult) -> str:
    """Rules-mode explanation: one plain-English sentence with the unit and the period."""
    m = METRICS.get(res.metric)
    if res.status != "ok" or not m:
        return res.message
    if res.metric == "late_rate":
        return f"{res.entity}: {int(res.events)} of {int(res.exposure)} departures left late ({res.shown}% of departures) across Jan-Sep 2026."
    period = months_label(res.months)
    s = (f"{res.entity} recorded {int(res.events)} {m.label.lower()} in {period}: {res.shown} {m.unit} "
         f"({int(res.exposure)} head-months).")
    c = res.comparison
    if c and c.get("status") == "ok":
        expected = c["pooled_rate"] * res.exposure
        s += (f" Comparable teams ({len(c['teams'])}, {c['rule']}) ran at {c['pooled_shown']} {m.unit}, "
              f"which predicts {expected:.1f} for a team this size.")
    return s
