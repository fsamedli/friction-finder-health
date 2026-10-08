"""v0.6 analytics (healthcare variant): excess cost, engagement-KPI link, difference-in-differences, value case."""
from app import impact as I
from app.impact import AS_OF_DETECT, AS_OF_REVIEW

C = I.default_costs()


def team(site_id, name, as_of=AS_OF_DETECT):
    return next(t for t in I.board(site_id, as_of, C)["teams"] if t["team_name"] == name)


def test_window():
    assert I.window("2026-09-15") == ["2026-06", "2026-07", "2026-08"]
    assert I.window("2026-11-30") == ["2026-09", "2026-10", "2026-11"]


def test_kpi_tables_agree():
    assert I.KPIS == ["absence_days", "late_doses", "quits", "injuries", "overtime_shifts"]
    assert set(I.KPI_LABELS) == set(I.KPIS) == set(I.KPI_COST_KEY)
    assert set(I.KPI_COST_KEY.values()) <= set(C)
    assert I.UPLOAD_COLUMNS == ["month", "team_id"] + I.KPIS[:2] + ["quits", "injuries", "overtime_shifts"]


def test_med_surg_night_red_and_first_at_detect():
    b = I.board(1, AS_OF_DETECT, C)
    t = b["teams"][0]
    assert t["team_name"] == "Med-Surg Night" and t["status"] == "red" and "late_doses" in t["elevated"]
    assert t["excess_cost"] > 0 and t["excess_by_kpi"]["late_doses"]["p"] < 0.01
    assert t["engagement"]["biggest_drop"]["item"] in ("q02", "q07")
    assert b["total_excess"] >= t["excess_cost"]


def test_excess_never_negative():
    for s in (1, 2, 3):
        for t in I.board(s, AS_OF_DETECT, C)["teams"]:
            assert t["excess_cost"] >= 0
            assert all(v["dollars"] >= 0 and v["count"] >= 0 for v in t["excess_by_kpi"].values())


def test_small_team_rolled_up_no_numbers():
    t = team(1, "EVS Night")
    assert t["status"] == "rolled_up" and t["engagement"] is None and t["excess_by_kpi"] == {} and t["spark"] == {}


def test_planted_blip_is_not_flagged():
    t = team(3, "ED Day")                          # P9: survey-only blip -> a watch item, never 'look here first'
    assert t["status"] == "amber" and t["elevated"] == []


def test_suppressed_wave_hides_engagement_but_keeps_ops():
    t = team(1, "Pharmacy Day")      # headcount 3 -> rolled up entirely
    assert t["status"] == "rolled_up"
    y = team(1, "Resp Therapy Day")  # headcount 5, wave 2 n=3 -> ops shown, engagement change hidden
    assert y["status"] != "rolled_up" and y["engagement"]["biggest_drop"] is None


def test_why_med_surg_night():
    tid = team(1, "Med-Surg Night")["team_id"]
    w = I.why(tid, AS_OF_DETECT, C)
    assert not w["suppressed"]
    drops = {c["item"] for c in w["item_changes"] if c["delta"] <= -0.3}
    assert {"q02", "q07"} <= drops
    assert w["kpi_trend"][-1]["month"] == "2026-08"


def test_why_suppressed_for_small_team():
    tid = team(1, "EVS Night")["team_id"]
    w = I.why(tid, AS_OF_DETECT, C)
    assert w["suppressed"] and w["item_changes"] == [] and w["kpi_trend"] == []


def test_planted_association_found_and_null_is_null():
    assert I.association("late_doses", "q02")["verdict"] == "association"
    assert I.association("injuries", "q02")["verdict"] == "too rare to test"          # P13
    assert I.association("absence_days", "grand")["verdict"] == "association"         # P12


def test_mix_artifact_is_not_red():
    t = team(2, "Telemetry Day")                   # P6: response-mix change; operations did not move
    assert t["status"] == "amber" and t["elevated"] == []


def test_quartile_link_direction():
    q = I.quartile_link("absence_days", "grand")
    assert q["bottom_q_rate"] > q["top_q_rate"] and q["n_cells"] >= 30


def test_did_worked_for_seeded_plan():
    r = I.did(I.load_plans()[0], AS_OF_REVIEW, C)
    assert r["kpi"] == "late_doses" and r["status"] == "ok" and r["verdict"] == "worked" and r["ci_high"] < 0
    assert r["comparison"]["teams"] and r["post_months"] == ["2026-10", "2026-11"]
    assert r["dollars_per_quarter"] is not None  # late doses now carry a (client-entered) unit cost


def test_did_not_reached_before_review():
    r = I.did(I.load_plans()[0], "2026-10-15", C)
    assert r["status"] == "not_reached" and r["days_to_go"] == 46


def test_did_insufficient_for_new_plan():
    p = dict(I.load_plans()[0], id="x", start="2026-11-20", review="2026-11-25")
    assert I.did(p, AS_OF_REVIEW, C)["status"] == "insufficient"


def test_placebo_smaller_than_treated():
    r = I.did(I.load_plans()[0], AS_OF_REVIEW, C)
    assert all(abs(x["estimate"]) < abs(r["estimate"]) for x in r["placebo"])


def test_value_case_uses_sources():
    v = I.value_case(C)
    assert 0 < v["low"] < v["high"] and all(i["source"] for i in v["inputs"])
    assert "NSI" in I.TURNOVER_RATE["source"] and "NAICS 622" in I.INJURY_RATE["source"] and "NAICS 622" in I.SEGMENT["source"]
    assert "493" not in I.SEGMENT["source"] and "warehous" not in I.INJURY_RATE["source"].lower()


def test_costs_validation():
    assert I.validate_costs({"quit": 0}) == {"quit": 0.0}
    assert I.validate_costs({"overtime_shift": 120}) == {"overtime_shift": 120.0}
    for bad in ({"quit": -1}, {"quit": "abc"}, {"nope": 5}, {"old_v08_key": 150}):
        try:
            I.validate_costs(bad)
            assert False, bad
        except ValueError:
            pass
