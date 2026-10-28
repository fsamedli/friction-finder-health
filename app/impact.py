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
import copy
import json
import threading
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from .config import CACHE_DIR, DATA_DIR, MIN_N

AS_OF_DETECT = "2026-09-15"   # wave 2 results are in
AS_OF_REVIEW = "2026-11-30"   # the seeded plan's review date
KPIS = ["absence_days", "late_doses", "quits", "injuries", "overtime_shifts"]
KPI_LABELS = {"absence_days": "Unplanned absence days (sick calls)", "late_doses": "Late medication doses",
              "quits": "Voluntary separations", "injuries": "Staff injuries (days-away)", "overtime_shifts": "Unplanned overtime shifts"}
KPI_COST_KEY = {"absence_days": "absence_day", "late_doses": "late_dose", "quits": "quit",
                "injuries": "injury", "overtime_shifts": "overtime_shift"}
ITEM_CODES = [f"q{i:02d}" for i in range(1, 13)]
WAVE_QUARTER = {1: ["2026-01", "2026-02", "2026-03"], 2: ["2026-07", "2026-08", "2026-09"]}

ITEM_DROP = -0.30       # screening rule on a 5-point scale (same as v0.5) ...
ITEM_P = 0.05 / 12      # ... and pass a Welch t-test, Bonferroni-corrected because we pick the worst of 12 items
MIN_EXPECTED = 3.0      # below 3 expected events in the window a KPI is 'too rare to judge' at team level (quits, injuries)
OPS_P = 0.01            # a KPI counts as elevated only if P(count >= observed | comparable teams' rate) < 1%.
                        # ~16 teams x 5 KPIs per site = 80 tests; at 1% that is under one false flag per site.
Z = 1.96

# value case: sourced sector inputs, each verified by web search on Oct 8, 2026 (healthcare variant spec, docs/specs/)
TURNOVER_RATE = {"value": 0.176, "source": "NSI Nursing Solutions, 2026 National Health Care Retention & RN Staffing Report "
                                            "(survey January 2026, calendar-year 2025 data): staff RN turnover 17.6% "
                                            "(cross-check: BLS JOLTS Aug 2026 health care & social assistance quits 2.0%/month x 12 = 24%, all occupations)"}
INJURY_RATE = {"value": 0.013, "source": "BLS SOII 2024, hospitals (NAICS 622): 1.3 cases involving days away from work per 100 full-time workers "
                                          "(bls.gov/iag/tgs/iag622.htm)"}
SEGMENT = {"establishments": 21037, "employees": 5_797_800,
           "source": "BLS, hospitals (NAICS 622): 21,037 establishments = QCEW 1Q 2026 preliminary, private 17,997 + local government 1,432 "
                     "+ state 1,134 + federal 474 (our sum of the four ownership rows); ~5.80M employees = CES Sep 2026 preliminary, all employees"}


# ---------------------------------------------------------------- data
@lru_cache(maxsize=1)
def _data():
    ops = pd.read_csv(DATA_DIR / "team_ops_monthly.csv")
    up = upload_path()
    if up.exists():  # the client's uploaded team-months replace the demo rows for the same team and month
        new = pd.read_csv(up)
        key = ["month", "team_id"]
        ops = ops.merge(new[key], on=key, how="left", indicator=True)
        ops = ops[ops["_merge"] == "left_only"].drop(columns="_merge")
        teams0 = pd.read_csv(DATA_DIR / "teams.csv")[["team_id", "site_id", "shift", "headcount"]]
        ops = pd.concat([ops, new.merge(teams0, on="team_id")[ops.columns]], ignore_index=True).sort_values(key).reset_index(drop=True)
    teams = pd.read_csv(DATA_DIR / "teams.csv")
    sites = pd.read_csv(DATA_DIR / "sites.csv")
    items = pd.read_csv(DATA_DIR / "q12_items.csv")
    resp = pd.read_csv(DATA_DIR / "responses.csv")
    resp["grand"] = resp[ITEM_CODES].mean(axis=1)
    tw = resp.groupby(["team_id", "wave_id"]).agg(n=("emp_id", "size"), **{c: (c, "mean") for c in ITEM_CODES + ["grand"]})
    return ops, teams, sites, dict(zip(items["item"], items["label"])), tw


UPLOAD_COLUMNS = ["month", "team_id", "absence_days", "late_doses", "quits", "injuries", "overtime_shifts"]


def upload_path():
    return CACHE_DIR / "team_ops_upload.csv"


def reload() -> None:
    """Drop cached data and results after an upload or a return to demo data."""
    global _MEMO_GEN
    for f in (_data, _cells, quartile_link, association):
        f.cache_clear()
    with _MEMO_LOCK:
        _MEMO.clear()
        _MEMO_GEN += 1


# ---------------------------------------------------------------- result memo
# board(), why() and did_all() are pure functions of the data files, the as-of date, the unit costs and (for
# did_all) the plan itself. Each costs 1 to 2 s on a 0.5-CPU host, so results are kept per process and handed
# out as copies. The key carries everything a result depends on; reload() (upload, reset) empties the memo, and
# a result computed across a reload is not kept.
_MEMO: dict = {}
_MEMO_LOCK = threading.Lock()
_MEMO_GEN = 0


def _key(*parts) -> tuple:
    return tuple(json.dumps(x, sort_keys=True, default=str) if isinstance(x, (dict, list)) else x for x in parts)


def _memo(key: tuple, compute):
    with _MEMO_LOCK:
        hit = _MEMO.get(key)
        gen = _MEMO_GEN
    if hit is None:
        hit = compute()
        with _MEMO_LOCK:
            if gen == _MEMO_GEN:
                _MEMO[key] = hit
    return copy.deepcopy(hit)


def validate_upload(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Check an uploaded team-month file. Returns the clean rows and a list of plain-language problems."""
    problems: list[str] = []
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in UPLOAD_COLUMNS if c not in df.columns]
    if missing:
        return df, [f"Missing columns: {', '.join(missing)}. Download the template to see the expected columns."]
    df = df[UPLOAD_COLUMNS].copy()
    if df.empty:
        return df, ["The file has no rows."]
    teams = set(pd.read_csv(DATA_DIR / "teams.csv").team_id)
    months = set(pd.read_csv(DATA_DIR / "team_ops_monthly.csv").month)
    for i, r in df.iterrows():
        row = i + 2  # header is line 1
        if str(r["month"]) not in months:
            problems.append(f"Line {row}: month '{r['month']}' is outside the data range (use YYYY-MM from {min(months)} to {max(months)}).")
        try:
            if int(r["team_id"]) not in teams:
                problems.append(f"Line {row}: team_id {r['team_id']} does not exist.")
        except (TypeError, ValueError):
            problems.append(f"Line {row}: team_id must be a whole number.")
        for c in UPLOAD_COLUMNS[2:]:
            v = pd.to_numeric(r[c], errors="coerce")
            if pd.isna(v) or v < 0 or v != int(v):
                problems.append(f"Line {row}: {c} must be a whole number of 0 or more (got '{r[c]}').")
        if len(problems) >= 8:
            problems.append("Stopped after 8 problems.")
            break
    if not problems:
        df["team_id"] = df["team_id"].astype(int)
        for c in UPLOAD_COLUMNS[2:]:
            df[c] = df[c].astype(int)
        if df.duplicated(["month", "team_id"]).any():
            problems.append("The same team and month appear more than once.")
    return df, problems


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
    return _memo(_key("board", int(site_id), as_of, costs), lambda: _board(int(site_id), as_of, costs))


def _board(site_id: int, as_of: str, costs: dict) -> dict:
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
    return _memo(_key("why", int(team_id), as_of, costs), lambda: _why(int(team_id), as_of, costs))


def _why(team_id: int, as_of: str, costs: dict) -> dict:
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
    kpi = kpi or plan.get("kpi", "late_doses")
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
    return _memo(_key("did_all", plan, as_of, costs), lambda: _did_all(plan, as_of, costs))


def _did_all(plan: dict, as_of: str, costs: dict) -> list[dict]:
    """The plan's KPI first, then the other KPIs the obstacle plausibly touches."""
    main = plan.get("kpi", "late_doses")
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
            "scenario": "Assumption: for a 300-person nursing workforce, voluntary turnover falls 1 point (low) or 3 points (high) and one days-away staff injury is avoided per year. "
                        "Gallup's top-vs-bottom quartile gap (21-51% turnover, 63% safety incidents) is correlational; the pilot tests whether the tool causes any of it.",
            "inputs": [
                {"label": "Voluntary turnover rate", "value": TURNOVER_RATE["value"], "source": TURNOVER_RATE["source"]},
                {"label": "Days-away injury rate", "value": INJURY_RATE["value"], "source": INJURY_RATE["source"]},
                {"label": costs["quit"]["label"], "value": quit_cost, "source": costs["quit"]["source"]},
                {"label": costs["injury"]["label"], "value": injury_cost, "source": costs["injury"]["source"]},
            ]}


# ---------------------------------------------------------------- what a plan is worth (Oct 27, 2026 round)
# Prof. Hall (Oct 21): "$1,700 appeared too small"; "use a larger, credible scenario with clear assumptions about hospital
# size and time period". Three tiers, each with its inputs, so the screen prints the assumption next to the number
# (docs/specs/2026-10-27-prof-hall-round.md). Nothing here changes a verdict or the placebo.
GALLUP_TURNOVER_GAP = {
    "low": 0.21, "high": 0.51,
    # Gallup splits the finding by the organization's own turnover: above 40% annualized ("high-turnover") 21%, 40% or below
    # ("low-turnover") 51%. Staff RN turnover is 17.6% (NSI 2026), so the 51% figure is the one that applies to a hospital.
    "applies": 0.51,
    # Oct 27 polish: the low bound assumes the unit climbs from the bottom quartile only to the median, taken as half the
    # top-vs-bottom gap (a linear assumption); the high bound assumes it reaches the top quartile (the full gap).
    "median_share": 0.5,
    "source": "Gallup, Q12 Meta-Analysis, 11th edition (2024): business units in the top engagement quartile have 21% "
              "(organizations above 40% annualized turnover) to 51% (organizations at 40% or below) lower turnover than units in "
              "the bottom quartile (gallup.com/workplace/321725/q12-meta-analysis-report.aspx). Correlational, across 183,806 "
              "units. Staff RN turnover is 17.6% (NSI 2026), so the 51% figure applies here.",
}
KPI_SINGULAR = {"late_doses": "late medication dose", "absence_days": "unplanned absence day", "quits": "voluntary separation",
                "injuries": "days-away staff injury", "overtime_shifts": "unplanned overtime shift"}   # for "per ..." copy
HOSPITAL_HEADCOUNT = 300          # the Business case page's standing scenario: nursing and support staff per hospital
PROJECTION_SANE_QUITS = (0.3, 3.0)  # avoided quits a year that are plausible for one unit; outside this the UI says so
ILLUSTRATIVE_REASON = ("Illustrative: Lanford Health is fictional and the months after the plan started are synthetic, "
                       "planted so the method can be shown. With a client's data every figure here is recomputed from its records.")


def _unit_cost_row(costs: dict, kpi: str) -> dict:
    c = costs.get(KPI_COST_KEY[kpi]) or {}
    return {"value": float(c.get("value") or 0), "kind": c.get("kind", "none"), "label": c.get("label", KPI_COST_KEY[kpi]),
            "source": c.get("source", ""), "unit": c.get("unit", "")}


def _magnitude(unit_cost: float) -> str:
    """'tens of dollars' / 'a few hundred dollars' / '$60,090' for the plain-words sentence under the measured tier."""
    if not unit_cost:
        return "no unit cost"
    if unit_cost < 100:
        return "tens of dollars"
    if unit_cost < 1000:
        return "a few hundred dollars"
    return f"${unit_cost:,.0f}"


def _quartile_of(x: float | None, quartiles: list[dict]) -> int | None:
    if x is None:
        return None
    for q in quartiles:
        lo, hi = q["x_range"]
        if lo <= x <= hi:
            return int(q["q"])
    return 1 if x < quartiles[0]["x_range"][0] else 4


def value_of_plan(plan: dict, as_of: str, costs: dict, results: list[dict] | None = None,
                  hospital_headcount: int = HOSPITAL_HEADCOUNT) -> dict | None:
    """What the plan is worth, in three labelled tiers. None before the review result exists.

    measured   the established difference-in-differences effects only (95% interval excludes zero), annualised at four
               quarters, at the unit cost shown with its provenance. For a 14-person unit this is small, and says so.
    projected  avoided turnover for this unit if it climbs from the bottom quartile of unit engagement to the median (low,
               half the gap) or the top quartile (high, the full gap): headcount x sector turnover (NSI) x Gallup's published
               quartile gap for organizations at or below 40% turnover (51%) x cost per RN separation.
               A projection from published, correlational evidence; the unit's own follow-up pulse is not in the demo data.
    hospital   the Business case scenario for a hospital of HOSPITAL_HEADCOUNT staff (value_case), the deck's number.
    """
    results = results or did_all(plan, as_of, costs)
    main = results[0]
    if main.get("status") != "ok":
        return None
    team_id = int(plan["team_id"])
    team = _team(team_id)
    headcount = int(team["headcount"])
    sites = _data()[2].set_index("site_id")
    team_label = f'{sites.loc[int(team["site_id"]), "site_name"]} {team["team_name"]}'

    # tier 1: measured
    main_cost = _unit_cost_row(costs, main["kpi"])
    components, excluded = [], []
    for r in results:
        if r.get("status") != "ok":
            excluded.append({"kpi": r["kpi"], "kpi_label": r["kpi_label"], "verdict": None, "why": r.get("reason") or "no result yet"})
            continue
        if r["verdict"] != "worked":
            why = "the 95% interval includes zero (two months is short for this KPI)" if r["verdict"] == "inconclusive" else "the KPI rose relative to comparable teams"
            excluded.append({"kpi": r["kpi"], "kpi_label": r["kpi_label"], "verdict": r["verdict"], "why": why,
                             "estimate": r["estimate"], "ci_low": r["ci_low"], "ci_high": r["ci_high"]})
            continue
        cost = _unit_cost_row(costs, r["kpi"])
        if not cost["value"]:
            excluded.append({"kpi": r["kpi"], "kpi_label": r["kpi_label"], "verdict": r["verdict"], "why": "no unit cost entered"})
            continue
        per_year = float(r["events_avoided_per_quarter"]) * 4
        components.append({"kpi": r["kpi"], "kpi_label": r["kpi_label"], "events_avoided_per_quarter": r["events_avoided_per_quarter"],
                           "events_avoided_per_year": round(per_year, 1), "unit_cost": cost["value"], "unit_kind": cost["kind"],
                           "unit_source": cost["source"], "comparison_teams": len(r["comparison"]["teams"]),
                           "ci_low_per_10": round(r["ci_low"] * 10, 2), "ci_high_per_10": round(r["ci_high"] * 10, 2),
                           "dollars": round(per_year * cost["value"])})
    measured_total = int(sum(c["dollars"] for c in components))
    measured_inputs = []
    for c in components:
        measured_inputs.append({"label": f'{c["kpi_label"]} avoided per quarter', "value": c["events_avoided_per_quarter"],
                                "source": f'Difference-in-differences vs {c["comparison_teams"]} comparable teams; 95% interval excludes zero'})
        measured_inputs.append({"label": f'Cost per {KPI_SINGULAR.get(c["kpi"], c["kpi_label"].lower())}', "value": c["unit_cost"], "kind": c["unit_kind"], "source": c["unit_source"]})
    measured_inputs.append({"label": "Time period", "value": "12 months", "source": "Assumption: the two-month effect holds for four quarters"})
    measured_inputs.append({"label": "Unit size", "value": headcount, "source": f"{team_label} headcount (teams.csv)"})
    measured = {"id": "measured", "kind": "measured", "label": "Measured, this unit, per year", "dollars": measured_total,
                "low": None, "high": None, "components": components, "excluded": excluded, "inputs": measured_inputs,
                "sentence": (f'{", ".join(c["kpi_label"].lower() for c in components)}: the established effect, annualised, at the unit cost shown.'
                             if components else "No established effect yet: every 95% interval includes zero, so nothing is counted here."),
                "small_because": f"A {headcount}-person unit at {_magnitude(main_cost['value'])} per {KPI_SINGULAR.get(main['kpi'], main['kpi_label'].lower())} "
                                 "stays small by construction; the retention value below is where the money is."}

    # tier 2: projected retention value for this unit
    item = plan.get("item") or "grand"
    item_label = item_labels().get(item, item) if item != "grand" else "engagement (grand mean)"
    quit_cost = _unit_cost_row(costs, "quits")
    quits_per_year = headcount * TURNOVER_RATE["value"]
    gap = GALLUP_TURNOVER_GAP["applies"]
    lo_q, hi_q = quits_per_year * gap * GALLUP_TURNOVER_GAP["median_share"], quits_per_year * gap   # to the median; to the top quartile
    tw = _data()[4]
    w1 = float(tw.loc[(team_id, 1), item]) if (team_id, 1) in tw.index and int(tw.loc[(team_id, 1), "n"]) >= MIN_N else None
    w2 = float(tw.loc[(team_id, 2), item]) if (team_id, 2) in tw.index and int(tw.loc[(team_id, 2), "n"]) >= MIN_N else None
    ql = quartile_link("quits", item)
    q1, q2 = _quartile_of(w1, ql["quartiles"]), _quartile_of(w2, ql["quartiles"])
    mech = []
    for kpi in dict.fromkeys([main["kpi"], "quits"]):
        a = association(kpi, item)
        mech.append({k: a[k] for k in ("kpi", "item", "slope", "ci_low", "ci_high", "p", "n_cells", "n_teams", "verdict")})
    in_range = PROJECTION_SANE_QUITS[0] <= lo_q and hi_q <= PROJECTION_SANE_QUITS[1]
    where = (f'after wave 2 it sits in quartile {q2} of {ql["n_cells"]} reportable unit-waves on "{item_label}"'
             + (f", down from quartile {q1} at wave 1" if q1 and q2 and q1 != q2 else "")) if q2 else "its wave-2 position is not reportable"
    projected = {"id": "projected", "kind": "projection", "label": "Projected, this unit, if engagement recovers",
                 "dollars": None, "low": int(round(lo_q * quit_cost["value"])), "high": int(round(hi_q * quit_cost["value"])),
                 "quits_avoided_low": round(lo_q, 2), "quits_avoided_high": round(hi_q, 2), "quits_per_year_now": round(quits_per_year, 2),
                 "in_range": bool(in_range), "sane_range": list(PROJECTION_SANE_QUITS),
                 "recovery": {"low": "median", "high": "top quartile"},
                 "condition": f"Low: {team_label} climbs from the bottom quartile of unit engagement to the median (taken as half the gap, an assumption). "
                              f"High: it reaches the top quartile (the full gap). {where[0].upper() + where[1:]}. "
                              "A two-month follow-up pulse on the focus item would show whether it did; it is not in the demo data.",
                 "focus": {"item": item, "label": item_label, "w1": None if w1 is None else round(w1, 2), "w2": None if w2 is None else round(w2, 2),
                           "quartile_w1": q1, "quartile_w2": q2, "n_cells": ql["n_cells"]},
                 "mechanism": mech,
                 "inputs": [
                     {"label": "Unit size", "value": headcount, "source": f"{team_label} headcount (teams.csv)"},
                     {"label": "Voluntary turnover rate", "value": TURNOVER_RATE["value"], "source": TURNOVER_RATE["source"]},
                     {"label": "Top-vs-bottom quartile turnover gap, applied", "value": gap, "source": GALLUP_TURNOVER_GAP["source"]},
                     {"label": "Gallup's figure for organizations above 40% turnover", "value": GALLUP_TURNOVER_GAP["low"], "source": "Not used: a hospital at 17.6% RN turnover is in Gallup's 40%-or-below group."},
                     {"label": "Recovery assumed", "value": "to the median (low) · to the top quartile (high)",
                      "source": "Assumption: a climb from the bottom quartile to the median captures half the top-vs-bottom gap (linear); the top quartile captures all of it."},
                     {"label": quit_cost["label"], "value": quit_cost["value"], "kind": quit_cost["kind"], "source": quit_cost["source"]},
                     {"label": "Time period", "value": "12 months", "source": "Per year, at the sector turnover rate"},
                 ],
                 "sentence": f"{round(lo_q, 1)} to {round(hi_q, 1)} fewer voluntary separations a year on {headcount} people (to the median, or to the top quartile), "
                             "at the sourced cost per RN separation. Association, not cause: Gallup's gap is correlational and this unit's own follow-up pulse is an assumption."}

    # tier 3: the hospital scenario (the Business case page)
    vc = value_case(costs, hospital_headcount)
    hospital = {"id": "hospital", "kind": "scenario", "label": f"At hospital scale ({hospital_headcount:,} staff), per year",
                "dollars": None, "low": int(vc["low"]), "high": int(vc["high"]), "headcount": hospital_headcount, "link": "/value",
                "condition": vc["scenario"],
                "inputs": [{"label": "Hospital size", "value": hospital_headcount, "source": "Scenario: nursing and support staff per hospital (Business case page slider)"},
                           {"label": "Turnover falls", "value": [0.01, 0.03], "source": "Scenario: 1 point (low) to 3 points (high) of the workforce a year"},
                           {"label": quit_cost["label"], "value": quit_cost["value"], "kind": quit_cost["kind"], "source": quit_cost["source"]},
                           {"label": "One days-away injury avoided", "value": float(costs["injury"]["value"]), "kind": costs["injury"].get("kind"), "source": costs["injury"].get("source", "")},
                           {"label": "Time period", "value": "12 months", "source": "Per hospital per year"}],
                "sentence": f"The Business case figure for a {hospital_headcount:,}-person hospital: turnover falls 1 to 3 points and one days-away injury is avoided a year."}

    return {"illustrative": True, "illustrative_reason": ILLUSTRATIVE_REASON, "team": {"team_id": team_id, "label": team_label, "headcount": headcount},
            "as_of": as_of, "tiers": [measured, projected, hospital]}
