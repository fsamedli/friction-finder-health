"""v0.6 synthetic data (healthcare variant): team-level monthly operating records, unit costs, and a seeded plan.

Runs after generate.py with its own random generator, so every survey file stays byte-identical.
Everything here is fictional; nothing is patient-level. Planted patterns (added to truth.json):

  P11  Lanford Med-Surg Night: late doses, absences and quits are elevated Jun-Sep 2026, after the
       dispensing-cabinet restock obstacle appears (consistent with P3 and P8). The plan starts Sept 21;
       in Oct-Nov the multipliers return to 1.0. Comparison night teams at other sites stay flat.
  P12  Across teams, lower q02 (materials and equipment) goes with more late doses and overtime shifts,
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
CENTER = 3.85               # generator's team-item baseline mean
PLAN_START, PLAN_REVIEW = "2026-09-21", "2026-11-30"
PLANTED_TEAM_NAME = "Med-Surg Night"   # site 1's copy is the planted team (team_id 4)

# per head per month, at CENTER engagement. Same values and the same key order as v0.8 (the second and fourth
# keys were renamed for the hospital story), so the Poisson draws are unchanged.
BASE = {"absence_days": 0.55, "late_doses": 1.0, "quits": 0.022, "overtime_shifts": 0.30, "injuries": 0.00125}
# log-rate change per point of the driving item (negative = better engagement, fewer events)
ELASTICITY = {"absence_days": ("grand", -0.9), "late_doses": ("q02", -1.1), "quits": ("grand", -0.8),
              "overtime_shifts": ("q02", -0.7), "injuries": (None, 0.0)}
P11_MULT = {"late_doses": 2.0, "absence_days": 1.35, "quits": 1.6}
P11_MONTHS = ["2026-06", "2026-07", "2026-08", "2026-09"]

ITEM_CODES = [f"q{i:02d}" for i in range(1, 13)]

# BLS Occupational Outlook Handbook, Registered Nurses (data from OEWS May 2025): median hourly wage $46.90,
# median annual wage $97,550 (bls.gov/ooh/healthcare/registered-nurses.htm, verified Oct 8, 2026). The OEWS
# *mean* hourly wage for 29-1141 could not be retrieved during this build (bls.gov refused the fetch), so the
# median stands in for it and every string below says so.
RN_HOURLY = 46.90
RN_WAGE_SOURCE = "BLS OOH / OEWS May 2025 registered nurses median hourly wage $46.90 (median used as a proxy for the mean)"


def unit_costs() -> dict:
    hourly = RN_HOURLY
    return {
        "quit": {"label": "Replacing one registered nurse", "value": 60090, "unit": "per separation", "kind": "sourced",
                 "source": "NSI Nursing Solutions, 2026 National Health Care Retention & RN Staffing Report (survey January 2026, "
                           "calendar-year 2025 data): average cost of turnover for a staff RN $60,090",
                 "note": "NSI's figure covers recruiting, onboarding, orientation and vacancy coverage for a bedside RN; "
                         "non-RN separations in a unit are costed at the same rate here, which overstates them."},
        "injury": {"label": "One days-away injury", "value": 48000, "unit": "per case", "kind": "sourced",
                   "source": "National Safety Council, Injury Facts 2024: cost per medically consulted injury",
                   "note": "Upper bound: includes wage, medical and administrative cost beyond the employer's cash."},
        "absence_day": {"label": "One unplanned absence day (sick call)", "value": round(hourly * 12, 2), "unit": "per day", "kind": "assumption",
                        "source": f"Assumption: one 12-hour shift at the RN wage (12 x ${hourly}/hr; {RN_WAGE_SOURCE}). "
                                  "Ignores agency or overtime premium for backfill.",
                        "note": "Replace with the client's backfill cost."},
        "late_dose": {"label": "One late medication dose", "value": 40, "unit": "per late dose", "kind": "client_entered",
                      "source": "Client-entered figure: Lanford Health (fictional) pharmacy callback and nurse time per late dose. "
                                "Not a market statistic; no credible public source exists.",
                      "note": "A modest placeholder (tens of dollars) chosen for the demo; in a real deployment the client enters its own number here."},
        "overtime_shift": {"label": "One unplanned overtime shift", "value": round(hourly * 4 * 0.5, 2), "unit": "per shift", "kind": "assumption",
                           "source": f"Assumption: the premium portion of one extended shift, 4 hours x 0.5 x ${hourly}/hr ({RN_WAGE_SOURCE}).",
                           "note": "Replace with the client's overtime report."},
    }


def seeded_plan(team_id: int, pharmacy_owner: str) -> list[dict]:
    return [{
        "id": "plan-lanford-med-surg-night",
        "team_id": team_id,
        "item": "q02",
        "kpi": "late_doses",
        "obstacle": "Medication cabinet restocked after the 06:00 pass: night nurses start the pass with empty bins",
        "focus": "Materials and equipment to do my work right (q02)",
        "actions": [
            {"text": "Pharmacy restores the 05:00 cabinet restock for the Med-Surg unit", "owner": f"{pharmacy_owner}, Pharmacy Operations Manager", "due": "2026-09-28"},
            {"text": "Charge nurse logs stock-outs at 02:00 and sends the list to pharmacy", "owner": "Med-Surg Night charge nurse", "due": "2026-10-05"},
            {"text": "Ten-minute team check-in on q02 every other Monday: did the actions happen, did they help?", "owner": "Med-Surg Night nurse manager", "due": "2026-10-12"},
        ],
        "start": PLAN_START,
        "review": PLAN_REVIEW,
        "status": "approved",
        "note": "Seeded for the demo: approved by the nurse manager after wave 2.",
    }]


def run(teams: pd.DataFrame, responses: pd.DataFrame, truth: dict, ownership: pd.DataFrame) -> dict:
    r = np.random.default_rng(SEED)
    planted = int(teams[(teams.site_id == 1) & (teams.team_name == PLANTED_TEAM_NAME)].team_id.iloc[0])
    pharmacy_owner = str(ownership[(ownership.site_id == 1) & (ownership.owner_role == "Pharmacy Operations Manager")].owner_name.iloc[0])

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
            # Operating outcomes follow each team's underlying engagement, which the generator holds stable:
            # wave 2 survey moves are either planted with their own operating effect (P11, via multipliers)
            # or survey-only artifacts (P6 response mix, P9 blip) that must NOT show up in operations.
            s = state(t, 1)
            rec = {"month": m, "team_id": int(t.team_id), "site_id": int(t.site_id), "shift": t.shift,
                   "headcount": int(t.headcount)}
            for k, base in BASE.items():
                driver, el = ELASTICITY[k]
                lam = t.headcount * base * (np.exp(el * (float(s[driver]) - CENTER)) if driver else 1.0)
                if t.team_id == planted and m in P11_MONTHS:
                    lam *= P11_MULT.get(k, 1.0)
                rec[k] = int(r.poisson(lam))
            rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "team_ops_monthly.csv", index=False)
    (OUT / "unit_costs.json").write_text(json.dumps(unit_costs(), indent=2))
    (OUT / "plans_seed.json").write_text(json.dumps(seeded_plan(planted, pharmacy_owner), indent=2))

    comparison = [int(x) for x in teams[(teams["shift"] == "Night") & (teams.site_id != 1) & (teams.headcount >= 4)].team_id]
    x = df[df.team_id == planted].set_index("month")
    rate = lambda ms, k="late_doses": round(float(x.loc[ms, k].sum() / x.loc[ms, "headcount"].sum()), 3)
    truth["patterns"]["P11"] = {
        "what": "Lanford Med-Surg Night: late doses, absences, quits elevated Jun-Sep 2026; recover Oct-Nov after the plan (Sept 21)",
        "team_id": planted, "multipliers": P11_MULT, "months": P11_MONTHS, "plan_start": PLAN_START,
        "plan_review": PLAN_REVIEW, "comparison_team_ids": comparison,
        "late_rate_mar_may": rate(["2026-03", "2026-04", "2026-05"]),
        "late_rate_jun_aug": rate(["2026-06", "2026-07", "2026-08"]),
        "late_rate_oct_nov": rate(["2026-10", "2026-11"]),
    }
    truth["patterns"]["P12"] = {
        "what": "Lower q02 -> more late doses and overtime shifts; lower grand mean -> more absences and quits (log-rate elasticities)",
        "elasticity": {k: v for k, v in ELASTICITY.items() if v[0]}, "base_per_head_month": BASE,
    }
    truth["patterns"]["P13"] = {"what": "Injuries independent of engagement (must be 'no association detected')",
                                "base_per_head_month": BASE["injuries"]}
    return truth
