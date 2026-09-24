"""v0.6 analytics: detect, explain, prove. Pure functions over the generated CSVs; no model calls.

Every method here is deliberately simple enough to explain in one sentence to a judge:

- Excess cost (detect): a team's rate per head-month above the median of comparable teams on the same
  shift, times headcount, months, and a sourced unit cost. Only the excess counts, never a credit.
- Quartile link (explain): the same presentation as Gallup's Q12 meta-analysis. Split reportable
  team-waves into quartiles by an engagement item and compare the median KPI rate of the top and
  bottom quartile.
- Association (explain): OLS of the KPI rate on the item mean over team-waves, standard errors
  clustered by team because each team appears twice. Association, not cause.
- Did it work (prove): difference-in-differences of the KPI rate, the team that acted vs comparable
  teams that did not, before vs after the plan start. Standard error from Poisson counts. A placebo
  run treats each comparison team as if it had acted. Directional, not causal.

Privacy: survey values need n >= MIN_N respondents in that team-wave; teams with headcount < MIN_N
show no team-level numbers at all (rolled up to the site), because operating counts on a team of
two identify people as surely as survey scores do.
"""
from __future__ import annotations

import calendar
import json
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from .config import CACHE_DIR, DATA_DIR, MIN_N

AS_OF_DETECT = "2026-09-15"   # wave 2 results are in
AS_OF_REVIEW = "2026-11-30"   # the seeded plan's review date
KPIS = ["absence_days", "late_departures", "quits", "injuries", "rework"]
KPI_LABELS = {"absence_days": "Unplanned absence days", "late_departures": "Late outbound departures",
              "quits": "Voluntary quits", "injuries": "Days-away injuries", "rework": "Rework events"}
KPI_COST_KEY = {"absence_days": "absence_day", "late_departures": "late_departure", "quits": "quit",
                "injuries": "injury", "rework": None}
ITEM_CODES = [f"q{i:02d}" for i in range(1, 13)]
WAVE_QUARTER = {1: ["2026-01", "2026-02", "2026-03"], 2: ["2026-07", "2026-08", "2026-09"]}

ITEM_DROP = -0.30       # screening rule on a 5-point scale (same as v0.5) ...
ITEM_P = 0.05 / 12      # ... and pass a Welch t-test, Bonferroni-corrected because we pick the worst of 12 items
MIN_EXPECTED = 3.0      # below 3 expected events in the window a KPI is 'too rare to judge' at team level (quits, injuries)
OPS_P = 0.01            # a KPI counts as elevated only if P(count >= observed | comparable teams' rate) < 1%.
                        # ~16 teams x 5 KPIs per site = 80 tests; at 1% that is under one false flag per site.
Z = 1.96

# value case: sourced sector inputs (see My Notes/2026-09-23_Product_Edge_Research.md)
TURNOVER_RATE = {"value": 0.26, "source": "BLS JOLTS 2025, transportation & warehousing: quits 2.2%/month x 12 (sector proxy, not NAICS 493 alone)"}
INJURY_RATE = {"value": 0.015, "source": "BLS SOII 2024, warehousing (NAICS 493): 1.5 days-away cases per 100 FTE"}
SEGMENT = {"establishments": 23848, "employees": 1_840_000,
           "source": "BLS, NAICS 493 warehousing & storage: 23,848 private establishments (Q1 2026), ~1.84M employees (Jul 2026)"}


# ---------------------------------------------------------------- data
@lru_cache(maxsize=1)
def _data():
    ops = pd.read_csv(DATA_DIR / "team_ops_monthly.csv")
    teams = pd.read_csv(DATA_DIR / "teams.csv")
    sites = pd.read_csv(DATA_DIR / "sites.csv")
    items = pd.read_csv(DATA_DIR / "q12_items.csv")
    resp = pd.read_csv(DATA_DIR / "responses.csv")
    resp["grand"] = resp[ITEM_CODES].mean(axis=1)
    tw = resp.groupby(["team_id", "wave_id"]).agg(n=("emp_id", "size"), **{c: (c, "mean") for c in ITEM_CODES + ["grand"]})
    return ops, teams, sites, dict(zip(items["item"], items["label"])), tw


def item_labels() -> dict:
    return {"grand": "Overall engagement (mean of 12 items)", **_data()[3]}


def default_costs() -> dict:
    costs = json.loads((DATA_DIR / "unit_costs.json").read_text())
    override = CACHE_DIR / "costs.json"
    if override.exists():
        for k, v in json.loads(override.read_text()).items():
            if k in costs:
                costs[k]["value"] = v
    return costs


def validate_costs(update: dict) -> dict:
    """Numbers >= 0 for known keys only. Raises ValueError otherwise."""
    known = json.loads((DATA_DIR / "unit_costs.json").read_text())
    out = {}
    for k, v in update.items():
        if k not in known:
            raise ValueError(f"unknown cost '{k}'")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or v < 0:
            raise ValueError(f"cost '{k}' must be a number >= 0")
        out[k] = float(v)
    return out


def _cost(costs: dict, kpi: str) -> float:
    key = KPI_COST_KEY[kpi]
    return float(costs[key]["value"]) if key else 0.0


# ---------------------------------------------------------------- time
def _month_end(m: str) -> date:
    y, mo = int(m[:4]), int(m[5:7])
    return date(y, mo, calendar.monthrange(y, mo)[1])


def full_months_through(as_of: str) -> list[str]:
    """Data months that are complete on as_of."""
    d = date.fromisoformat(as_of)
    return [m for m in sorted(_data()[0]["month"].unique()) if _month_end(m) <= d]


def window(as_of: str, months: int = 3) -> list[str]:
    return full_months_through(as_of)[-months:]


# ---------------------------------------------------------------- helpers
def _team(team_id: int) -> pd.Series:
    teams = _data()[1]
    return teams[teams.team_id == team_id].iloc[0]


def _comparables(team) -> pd.DataFrame:
    teams = _data()[1]
    return teams[(teams["shift"] == team["shift"]) & (teams.team_id != team["team_id"]) & (teams.headcount >= MIN_N)]


def _rate(team_ids, months, kpi) -> tuple[float, float, float]:
    """(rate per head-month, count, exposure in head-months)."""
    ops = _data()[0]
    x = ops[ops.team_id.isin(list(team_ids)) & ops.month.isin(months)]
    exposure = float(x.headcount.sum())
    count = float(x[kpi].sum())
    return (count / exposure if exposure else 0.0), count, exposure


def _baseline(team, months, kpi) -> float:
    """Pooled rate of comparable teams (same shift, all sites, headcount >= MIN_N): their events / their head-months.
    Pooled rather than a median of team rates, so rare events (quits) do not get a baseline of zero."""
    ids = list(_comparables(team).team_id)
    return _rate(ids, months, kpi)[0] if ids else 0.0


def _engagement(team_id: int) -> dict | None:
    """Wave 1 vs wave 2 for one team. The change that counts is adjusted for who responded: each answer is
    compared with the company-wide mean for that respondent's tenure band (both waves pooled), so a wave in
    which new hires stopped responding does not look like a decline (the v0.5 signal check, same idea)."""
    tw = _data()[4]
    n1 = int(tw.loc[(team_id, 1), "n"]) if (team_id, 1) in tw.index else 0
    n2 = int(tw.loc[(team_id, 2), "n"]) if (team_id, 2) in tw.index else 0
    out = {"n_w1": n1, "n_w2": n2, "grand_w1": None, "grand_w2": None, "biggest_drop": None}
    if n1 >= MIN_N:
        out["grand_w1"] = round(float(tw.loc[(team_id, 1), "grand"]), 2)
    if n2 >= MIN_N:
        out["grand_w2"] = round(float(tw.loc[(team_id, 2), "grand"]), 2)
    if n1 >= MIN_N and n2 >= MIN_N:
        res = _residuals()
        a, b = res[(res.team_id == team_id) & (res.wave_id == 1)], res[(res.team_id == team_id) & (res.wave_id == 2)]
        adj = {c: float(b[c].mean() - a[c].mean()) for c in ITEM_CODES}
        worst = min(adj, key=adj.get)
        p = float(stats.ttest_ind(a[worst], b[worst], equal_var=False).pvalue)
        raw = float(tw.loc[(team_id, 2), worst] - tw.loc[(team_id, 1), worst])
        out["biggest_drop"] = {"item": worst, "label": item_labels()[worst], "delta": round(adj[worst], 2), "raw_delta": round(raw, 2),
                               "p": round(p, 4), "significant": bool(adj[worst] <= ITEM_DROP and p < ITEM_P)}
    return out


@lru_cache(maxsize=1)
def _residuals() -> pd.DataFrame:
    """Respondent answers minus the company-wide mean for their tenure band. Respondent rows never leave this module."""
    resp = _responses().merge(pd.read_csv(DATA_DIR / "employees.csv")[["emp_id", "tenure_band"]], on="emp_id")
    band = resp.groupby("tenure_band")[ITEM_CODES].transform("mean")
    out = resp[["team_id", "wave_id"]].copy()
    out[ITEM_CODES] = resp[ITEM_CODES] - band
    return out


@lru_cache(maxsize=1)
def _responses() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "responses.csv")


def _elevation(team_id: int, team, months: list[str], kpi: str) -> dict:
    """Observed count vs the count comparable teams' pooled rate predicts; Poisson upper tail."""
    r, count, exposure = _rate([team_id], months, kpi)
    b = _baseline(team, months, kpi)
    expected = b * exposure
    judgeable = expected >= MIN_EXPECTED
    p = float(stats.poisson.sf(count - 1, expected)) if judgeable else None
    flagged = bool(judgeable and count > expected and p < OPS_P)
    return {"observed": count, "expected": round(expected, 1), "p": None if p is None else round(p, 4),
            "judgeable": judgeable, "flagged": flagged,
            "count": round(count - expected, 1) if flagged else 0.0, "rate": round(r, 3), "baseline": round(b, 3)}


# ---------------------------------------------------------------- detect
def board(site_id: int, as_of: str, costs: dict) -> dict:
    ops, teams, sites, _, _ = _data()
    months = window(as_of)
    shown_months = full_months_through(as_of)
    rows = []
    for t in teams[teams.site_id == site_id].itertuples():
        team = _team(t.team_id)
        base = {"team_id": int(t.team_id), "team_name": t.team_name, "shift": t.shift, "headcount": int(t.headcount)}
        if t.headcount < MIN_N:
            rows.append({**base, "status": "rolled_up", "excess_cost": 0.0, "excess_by_kpi": {}, "spark": {}, "engagement": None})
            continue
        excess, spark = {}, {}
        for k in KPIS:
            e = _elevation(int(t.team_id), team, months, k)
            excess[k] = {**e, "dollars": round(e["count"] * _cost(costs, k), 0)}
            spark[k] = [{"month": m, "rate": round(_rate([t.team_id], [m], k)[0], 3),
                         "baseline": round(_baseline(team, [m], k), 3)} for m in shown_months]
        total = float(sum(v["dollars"] for v in excess.values()))
        eng = _engagement(int(t.team_id))
        dropped = bool(eng["biggest_drop"] and eng["biggest_drop"]["significant"])
        elevated = [k for k, v in excess.items() if v["flagged"]]
        status = "red" if (elevated and dropped) else "amber" if (elevated or dropped) else "green"
        signal = ("operations and engagement both moved" if status == "red" else
                  "operations moved; engagement did not" if elevated else
                  "engagement moved; operations did not" if dropped else "within normal variation")
        rows.append({**base, "status": status, "signal": signal, "elevated": elevated, "excess_cost": total,
                     "excess_by_kpi": excess, "spark": spark, "engagement": eng})
    order = {"red": 0, "amber": 1, "green": 2, "rolled_up": 3}
    rows.sort(key=lambda x: (order[x["status"]], -len(x.get("elevated", [])), -x["excess_cost"]))
    by_kpi = {k: float(sum(r["excess_by_kpi"].get(k, {}).get("dollars", 0) for r in rows)) for k in KPIS}
    counts = {k: float(sum(r["excess_by_kpi"].get(k, {}).get("count", 0) for r in rows)) for k in KPIS}
    return {"site_id": site_id, "site": sites.set_index("site_id").loc[site_id, "site_name"], "as_of": as_of,
            "window": months, "total_excess": float(sum(by_kpi.values())), "by_kpi": by_kpi, "counts_by_kpi": counts,
            "annualized": float(sum(by_kpi.values())) * 12 / max(1, len(months)), "teams": rows,
            "rules": {"ops_p": OPS_P, "item_drop": ITEM_DROP, "item_p": round(ITEM_P, 4), "min_expected": MIN_EXPECTED, "min_n": MIN_N}}


# ---------------------------------------------------------------- explain
@lru_cache(maxsize=None)
def _cells(kpi: str, item: str) -> pd.DataFrame:
    """Reportable team-waves: item mean vs the KPI rate in the quarter the wave closed."""
    tw = _data()[4]
    rows = []
    for (tid, wave), r in tw.iterrows():
        if r["n"] < MIN_N or _team(tid)["headcount"] < MIN_N:
            continue
        rate, count, exposure = _rate([tid], WAVE_QUARTER[wave], kpi)
        rows.append({"team_id": int(tid), "wave": int(wave), "x": float(r[item]), "rate": rate, "n": int(r["n"])})
    return pd.DataFrame(rows)


@lru_cache(maxsize=None)
def quartile_link(kpi: str, item: str = "grand") -> dict:
    c = _cells(kpi, item).sort_values("x").reset_index(drop=True)
    q = pd.qcut(c["x"].rank(method="first"), 4, labels=[1, 2, 3, 4])
    bottom, top = c[q == 1], c[q == 4]
    b, t = float(bottom.rate.median()), float(top.rate.median())
    return {"kpi": kpi, "item": item, "top_q_rate": round(t, 3), "bottom_q_rate": round(b, 3),
            "pct_diff": round((b - t) / b * 100, 0) if b else None, "n_cells": int(len(c)),
            "n_per_quartile": int(len(top)), "quartiles": [
                {"q": int(k), "median_rate": round(float(c[q == k].rate.median()), 3),
                 "x_range": [round(float(c[q == k].x.min()), 2), round(float(c[q == k].x.max()), 2)]} for k in (1, 2, 3, 4)]}


@lru_cache(maxsize=None)
def association(kpi: str, item: str = "grand") -> dict:
    c = _cells(kpi, item)
    if (c.rate > 0).sum() < 10:  # rare events (injuries): most cells are zero, a slope would be meaningless
        return {"kpi": kpi, "item": item, "slope": None, "ci_low": None, "ci_high": None, "p": None,
                "n_cells": int(len(c)), "n_teams": int(c.team_id.nunique()), "points": [], "verdict": "too rare to test"}
    fit = smf.ols("rate ~ x", data=c).fit(cov_type="cluster", cov_kwds={"groups": c["team_id"]})
    lo, hi = (float(v) for v in fit.conf_int().loc["x"])
    return {"kpi": kpi, "item": item, "slope": round(float(fit.params["x"]), 3), "ci_low": round(lo, 3),
            "ci_high": round(hi, 3), "p": round(float(fit.pvalues["x"]), 4), "n_cells": int(len(c)),
            "n_teams": int(c.team_id.nunique()), "points": c[["team_id", "wave", "x", "rate"]].round(3).to_dict("records"),
            "verdict": "association" if (lo > 0 or hi < 0) else "no association detected"}


def link_matrix() -> list[dict]:
    out = []
    for k in KPIS:
        for it in ["grand"] + ITEM_CODES:
            a = association(k, it)
            out.append({k2: a[k2] for k2 in ("kpi", "item", "slope", "ci_low", "ci_high", "p", "n_cells", "verdict")})
    return out


def why(team_id: int, as_of: str, costs: dict) -> dict:
    team = _team(team_id)
    sites = _data()[2].set_index("site_id")
    head = {"team_id": int(team_id), "team_name": team["team_name"], "shift": team["shift"],
            "site": sites.loc[int(team["site_id"]), "site_name"], "site_id": int(team["site_id"]),
            "headcount": int(team["headcount"])}
    if team["headcount"] < MIN_N:
        return {"team": head, "suppressed": True, "reason": f"Fewer than {MIN_N} people: included in site totals only.",
                "kpi_trend": [], "item_changes": [], "links": [], "engagement": None}
    months = full_months_through(as_of)
    trend = []
    for m in months:
        row = {"month": m}
        for k in KPIS:
            row[k] = round(_rate([team_id], [m], k)[0], 3)
            row["baseline_" + k] = round(_baseline(team, [m], k), 3)
        trend.append(row)
    eng = _engagement(team_id)
    tw = _data()[4]
    changes = []
    if eng["n_w1"] >= MIN_N and eng["n_w2"] >= MIN_N:
        for c in ITEM_CODES:
            w1, w2 = float(tw.loc[(team_id, 1), c]), float(tw.loc[(team_id, 2), c])
            changes.append({"item": c, "label": item_labels()[c], "w1": round(w1, 2), "w2": round(w2, 2), "delta": round(w2 - w1, 2)})
        changes.sort(key=lambda x: x["delta"])
    b = board(int(team["site_id"]), as_of, costs)
    mine = next(r for r in b["teams"] if r["team_id"] == team_id)
    focus_items = [c["item"] for c in changes if c["delta"] <= ITEM_DROP][:2] or ["grand"]
    links = [association(k, it) for it in focus_items for k in KPIS]
    return {"team": head, "suppressed": False, "reason": None if changes else f"A wave has fewer than {MIN_N} respondents: item changes hidden.",
            "kpi_trend": trend, "item_changes": changes, "engagement": eng, "excess": mine["excess_by_kpi"],
            "excess_cost": mine["excess_cost"], "status": mine["status"], "window": b["window"],
            "links": [{k: v for k, v in l.items() if k != "points"} for l in links]}


# ---------------------------------------------------------------- act
def load_plans() -> list[dict]:
    plans = json.loads((DATA_DIR / "plans_seed.json").read_text())
    path = CACHE_DIR / "plans.jsonl"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                p = json.loads(line)
                plans = [x for x in plans if x["id"] != p["id"]] + [p]
    return plans


def save_plan(plan: dict) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with (CACHE_DIR / "plans.jsonl").open("a") as f:
        f.write(json.dumps(plan) + "\n")
    return plan


# ---------------------------------------------------------------- prove
def _did_once(treated: list[int], comparison: list[int], pre: list[str], post: list[str], kpi: str) -> dict:
    tp, tpc, tpe = _rate(treated, pre, kpi)
    tq, tqc, tqe = _rate(treated, post, kpi)
    cp, cpc, cpe = _rate(comparison, pre, kpi)
    cq, cqc, cqe = _rate(comparison, post, kpi)
    est = (tq - tp) - (cq - cp)
    var = sum(c / e ** 2 for c, e in ((tpc, tpe), (tqc, tqe), (cpc, cpe), (cqc, cqe)) if e)
    se = float(np.sqrt(var))
    return {"estimate": round(est, 3), "se": round(se, 3), "ci_low": round(est - Z * se, 3), "ci_high": round(est + Z * se, 3),
            "treated": {"pre": round(tp, 3), "post": round(tq, 3)}, "comparison": {"pre": round(cp, 3), "post": round(cq, 3)}}


def did(plan: dict, as_of: str, costs: dict, kpi: str | None = None) -> dict:
    kpi = kpi or plan.get("kpi", "late_departures")
    team = _team(int(plan["team_id"]))
    review, start = date.fromisoformat(plan["review"]), date.fromisoformat(plan["start"])
    today = date.fromisoformat(as_of)
    base = {"plan_id": plan["id"], "kpi": kpi, "kpi_label": KPI_LABELS[kpi], "start": plan["start"], "review": plan["review"]}
    if today < review:
        return {**base, "status": "not_reached", "days_to_go": (review - today).days}
    all_months = sorted(_data()[0]["month"].unique())
    start_m = plan["start"][:7]
    pre = [m for m in all_months if m < start_m][-3:]
    post = [m for m in full_months_through(min(plan["review"], as_of)) if m > start_m]
    if len(post) < 2 or len(pre) < 3:
        return {**base, "status": "insufficient", "reason": "Fewer than two full months of follow-up data after the plan start.",
                "pre_months": pre, "post_months": post}
    comp = [int(t) for t in _comparables(team).team_id if _team(int(t))["site_id"] != team["site_id"]]
    r = _did_once([int(plan["team_id"])], comp, pre, post, kpi)
    placebo = []
    for c in comp:
        others = [x for x in comp if x != c]
        p = _did_once([c], others, pre, post, kpi)
        placebo.append({"team_id": c, "team": f'{_data()[2].set_index("site_id").loc[int(_team(c)["site_id"]), "site_name"]} {_team(c)["team_name"]}',
                        "estimate": p["estimate"]})
    verdict = "worked" if r["ci_high"] < 0 else "no effect" if r["ci_low"] > 0 else "inconclusive"
    per_quarter = -r["estimate"] * float(team["headcount"]) * 3
    unit = _cost(costs, kpi)
    series = [{"month": m, "treated": round(_rate([int(plan["team_id"])], [m], kpi)[0], 3),
               "comparison": round(_rate(comp, [m], kpi)[0], 3)} for m in full_months_through(as_of)]
    sites = _data()[2].set_index("site_id")
    return {**base, "status": "ok", **r, "verdict": verdict, "pre_months": pre, "post_months": post,
            "comparison": {**r["comparison"], "teams": [f'{sites.loc[int(_team(c)["site_id"]), "site_name"]} {_team(c)["team_name"]}' for c in comp]},
            "placebo": placebo, "events_avoided_per_quarter": round(per_quarter, 1),
            "dollars_per_quarter": round(per_quarter * unit, 0) if unit else None, "unit_cost": unit, "series": series}


def did_all(plan: dict, as_of: str, costs: dict) -> list[dict]:
    """The plan's KPI first, then the other KPIs the obstacle plausibly touches."""
    main = plan.get("kpi", "late_departures")
    return [did(plan, as_of, costs, k) for k in [main] + [k for k in ("absence_days", "quits") if k != main]]


# ---------------------------------------------------------------- business case
def value_case(costs: dict, headcount: int = 300) -> dict:
    quit_cost = float(costs["quit"]["value"])
    injury_cost = float(costs["injury"]["value"])
    quits = headcount * TURNOVER_RATE["value"]
    injuries = headcount * INJURY_RATE["value"]
    low = 0.01 * headcount * quit_cost + injury_cost
    high = 0.03 * headcount * quit_cost + injury_cost
    return {"headcount": headcount, "baseline_turnover_cost": round(quits * quit_cost), "baseline_injury_cost": round(injuries * injury_cost),
            "low": round(low), "high": round(high), "segment": SEGMENT,
            "scenario": "Assumption: voluntary turnover falls 1 point (low) or 3 points (high) and one days-away injury is avoided per year. "
                        "Gallup's top-vs-bottom quartile gap (21-51% turnover, 63% safety incidents) is correlational; the pilot tests whether the tool causes any of it.",
            "inputs": [
                {"label": "Voluntary turnover rate", "value": TURNOVER_RATE["value"], "source": TURNOVER_RATE["source"]},
                {"label": "Days-away injury rate", "value": INJURY_RATE["value"], "source": INJURY_RATE["source"]},
                {"label": costs["quit"]["label"], "value": quit_cost, "source": costs["quit"]["source"]},
                {"label": costs["injury"]["label"], "value": injury_cost, "source": costs["injury"]["source"]},
            ]}
