"""v0.6 synthetic data: team-level monthly operating records, unit costs, and a seeded plan.

Runs after generate.py with its own random generator, so every v0.5 file stays byte-identical.
Everything here is fictional. Planted patterns (added to truth.json):

  P11  Richmond Night A: late departures, absences and quits are elevated Jun-Sep 2026, after the
       shift-handoff obstacle appears (consistent with P3 and P8). The plan starts Sept 21; in
       Oct-Nov the multipliers return to 1.0. Comparison night teams at other sites stay flat.
  P12  Across teams, lower q02 (materials and equipment) goes with more late departures and rework,
       and a lower grand mean goes with more absences and quits. Modest effect, Poisson noise.
  P13  Injuries are generated independently of engagement: the tool must report "no association".
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent / "generated"
SEED = 4242
MONTHS = [f"2026-{m:02d}" for m in range(1, 12)]
WAVE2_FROM = "2026-06"      # engagement state switches to wave 2 when the obstacle appears
CENTER = 3.85               # generator's team-item baseline mean
PLAN_START, PLAN_REVIEW = "2026-09-21", "2026-11-30"

# per head per month, at CENTER engagement
BASE = {"absence_days": 0.55, "late_departures": 1.0, "quits": 0.022, "rework": 0.30, "injuries": 0.00125}
# log-rate change per point of the driving item (negative = better engagement, fewer events)
ELASTICITY = {"absence_days": ("grand", -0.9), "late_departures": ("q02", -1.1), "quits": ("grand", -0.8),
              "rework": ("q02", -0.7), "injuries": (None, 0.0)}
P11_MULT = {"late_departures": 2.0, "absence_days": 1.35, "quits": 1.6}
P11_MONTHS = ["2026-06", "2026-07", "2026-08", "2026-09"]

ITEM_CODES = [f"q{i:02d}" for i in range(1, 13)]


def unit_costs() -> dict:
    hourly = 25.73
    salary = round(hourly * 2080)
    return {
        "quit": {"label": "Replacing one hourly worker", "value": 10704, "unit": "per quit", "kind": "sourced",
                 "source": "Center for American Progress (Boushey & Glynn, 2012): 20% of annual pay for jobs under $50K-$75K; "
                           f"pay = BLS NAICS 493 average ${hourly}/hr x 2,080 = ${salary:,}",
                 "note": "SHRM 2025 cost-per-hire $5,475 is the recruiting-only floor."},
        "injury": {"label": "One days-away injury", "value": 48000, "unit": "per case", "kind": "sourced",
                   "source": "National Safety Council, Injury Facts 2024: cost per medically consulted injury",
                   "note": "Upper bound: includes wage, medical and administrative cost beyond the employer's cash."},
        "absence_day": {"label": "One unplanned absence day", "value": round(hourly * 8, 2), "unit": "per day", "kind": "assumption",
                        "source": f"Assumption: one day's pay (8 x BLS ${hourly}/hr). Ignores overtime premium for backfill.",
                        "note": "Replace with the client's backfill cost."},
        "late_departure": {"label": "One late outbound departure", "value": 0, "unit": "per departure", "kind": "none",
                           "source": "No credible public source found; vendor figures only.",
                           "note": "Shown as a count. The client can enter its own cost (e.g., SLA penalty)."},
    }


def seeded_plan(night_a_id: int) -> list[dict]:
    return [{
        "id": "plan-richmond-night-a",
        "team_id": night_a_id,
        "item": "q02",
        "kpi": "late_departures",
        "obstacle": "Shift handoff: night crews start without knowing what was loaded",
        "focus": "Materials and equipment to do my work right (q02)",
        "actions": [
            {"text": "Day shift completes the load checklist in the handoff log before leaving", "owner": "Priya Singh, Site Operations Manager", "due": "2026-09-28"},
            {"text": "Dispatch posts trailer status by 05:45 for the 06:00 departures", "owner": "Sam Kim, Dispatch Supervisor", "due": "2026-10-05"},
            {"text": "Ten-minute team check-in on q02 every other Monday: did the actions happen, did they help?", "owner": "Night A team manager", "due": "2026-10-12"},
        ],
        "start": PLAN_START,
        "review": PLAN_REVIEW,
        "status": "approved",
        "note": "Seeded for the demo: approved by the site operations manager after wave 2.",
    }]


def run(teams: pd.DataFrame, responses: pd.DataFrame, truth: dict) -> dict:
    r = np.random.default_rng(SEED)
    night_a = int(teams[(teams.site_id == 1) & (teams.team_name == "Night A")].team_id.iloc[0])

    # observed team-wave means (the generator uses all respondents; reporting applies MIN_N later)
    resp = responses.copy()
    resp["grand"] = resp[ITEM_CODES].mean(axis=1)
    tw = resp.groupby(["team_id", "wave_id"])[["grand", "q02"]].mean()
    site_shift = resp.merge(teams[["team_id", "site_id", "shift"]], on="team_id").groupby(
        ["site_id", "shift", "wave_id"])[["grand", "q02"]].mean()

    def state(t, wave):
        if (t.team_id, wave) in tw.index:
            return tw.loc[(t.team_id, wave)]
        return site_shift.loc[(t.site_id, t.shift, wave)]

    rows = []
    for t in teams.itertuples():
        for m in MONTHS:
            wave = 2 if m >= WAVE2_FROM else 1
            if t.team_id == night_a:
                wave = 1  # P11 multipliers carry Night A's operational effect; avoid double counting
            s = state(t, wave)
            rec = {"month": m, "team_id": int(t.team_id), "site_id": int(t.site_id), "shift": t.shift,
                   "headcount": int(t.headcount)}
            for k, base in BASE.items():
                driver, el = ELASTICITY[k]
                lam = t.headcount * base * (np.exp(el * (float(s[driver]) - CENTER)) if driver else 1.0)
                if t.team_id == night_a and m in P11_MONTHS:
                    lam *= P11_MULT.get(k, 1.0)
                rec[k] = int(r.poisson(lam))
            rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "team_ops_monthly.csv", index=False)
    (OUT / "unit_costs.json").write_text(json.dumps(unit_costs(), indent=2))
    (OUT / "plans_seed.json").write_text(json.dumps(seeded_plan(night_a), indent=2))

    comparison = [int(x) for x in teams[(teams["shift"] == "Night") & (teams.site_id != 1) & (teams.headcount >= 4)].team_id]
    x = df[df.team_id == night_a].set_index("month")
    rate = lambda ms, k="late_departures": round(float(x.loc[ms, k].sum() / x.loc[ms, "headcount"].sum()), 3)
    truth["patterns"]["P11"] = {
        "what": "Richmond Night A: late departures, absences, quits elevated Jun-Sep 2026; recover Oct-Nov after the plan (Sept 21)",
        "team_id": night_a, "multipliers": P11_MULT, "months": P11_MONTHS, "plan_start": PLAN_START,
        "plan_review": PLAN_REVIEW, "comparison_team_ids": comparison,
        "late_rate_mar_may": rate(["2026-03", "2026-04", "2026-05"]),
        "late_rate_jun_aug": rate(["2026-06", "2026-07", "2026-08"]),
        "late_rate_oct_nov": rate(["2026-10", "2026-11"]),
    }
    truth["patterns"]["P12"] = {
        "what": "Lower q02 -> more late departures and rework; lower grand mean -> more absences and quits (log-rate elasticities)",
        "elasticity": {k: v for k, v in ELASTICITY.items() if v[0]}, "base_per_head_month": BASE,
    }
    truth["patterns"]["P13"] = {"what": "Injuries independent of engagement (must be 'no association detected')",
                                "base_per_head_month": BASE["injuries"]}
    return truth
