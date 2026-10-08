"""v0.6 data (healthcare variant): team-level monthly operating records, unit costs, seeded plan (P11-P13)."""
import json

import pandas as pd

from app.config import DATA_DIR


def load():
    return (pd.read_csv(DATA_DIR / "team_ops_monthly.csv"),
            json.loads((DATA_DIR / "truth.json").read_text()),
            json.loads((DATA_DIR / "unit_costs.json").read_text()))


def test_shape_and_months():
    t, _, _ = load()
    assert set(t.columns) >= {"month", "team_id", "site_id", "shift", "headcount", "absence_days",
                              "late_doses", "quits", "injuries", "overtime_shifts"}
    assert t.month.min() == "2026-01" and t.month.max() == "2026-11"
    assert len(t) == 24 * 11


def test_p11_med_surg_night_elevated_then_recovers():
    t, truth, _ = load()
    p = truth["patterns"]["P11"]
    tid = p["team_id"]
    assert tid == 4 and "late_doses" in p["multipliers"]
    x = t[t.team_id == tid].set_index("month")

    def rate(ms):
        return x.loc[ms, "late_doses"].sum() / x.loc[ms, "headcount"].sum()

    pre, bad, post = ["2026-03", "2026-04", "2026-05"], ["2026-06", "2026-07", "2026-08"], ["2026-10", "2026-11"]
    assert rate(bad) > 1.4 * rate(pre)
    assert rate(post) < 0.8 * rate(bad)
    assert round(rate(bad), 3) == p["late_rate_jun_aug"]


def test_unit_costs_have_sources():
    _, _, c = load()
    assert set(c) == {"quit", "injury", "absence_day", "late_dose", "overtime_shift"}
    assert c["quit"]["value"] == 60090 and c["quit"]["kind"] == "sourced" and "NSI" in c["quit"]["source"]
    assert c["injury"]["value"] == 48000 and c["injury"]["kind"] == "sourced"
    assert c["absence_day"]["kind"] == "assumption" and "12 x" in c["absence_day"]["source"]
    assert c["late_dose"]["kind"] == "client_entered" and "fictional" in c["late_dose"]["source"]
    assert 0 < c["late_dose"]["value"] < 100
    assert c["overtime_shift"]["kind"] == "assumption" and "0.5" in c["overtime_shift"]["source"]
    assert all(v["source"] for v in c.values())


def test_seeded_plan():
    plans = json.loads((DATA_DIR / "plans_seed.json").read_text())
    p = plans[0]
    assert p["id"] == "plan-lanford-med-surg-night" and p["team_id"] == 4 and p["kpi"] == "late_doses"
    assert p["start"] == "2026-09-21" and p["review"] == "2026-11-30" and p["status"] == "approved"
    assert len(p["actions"]) >= 3 and all(a["owner"] for a in p["actions"])
    assert "Pharmacy Operations Manager" in p["actions"][0]["owner"]


def test_survey_files_unchanged_row_counts():
    assert len(pd.read_csv(DATA_DIR / "responses.csv")) == 311
    assert len(pd.read_csv(DATA_DIR / "ops_daily.csv")) == 5313
