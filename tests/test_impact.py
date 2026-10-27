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


# ---- Oct 27, 2026 round: what a plan is worth, three labelled tiers (docs/specs/2026-10-27-prof-hall-round.md)
def _seed():
    return next(p for p in I.load_plans() if p["id"] == "plan-lanford-med-surg-night")


def test_value_of_plan_none_before_the_result():
    assert I.value_of_plan(_seed(), "2026-10-15", C) is None


def test_value_measured_counts_only_established_effects():
    v = I.value_of_plan(_seed(), AS_OF_REVIEW, C)
    assert v["illustrative"] is True and "synthetic" in v["illustrative_reason"]
    m, p, h = v["tiers"]
    assert [t["id"] for t in (m, p, h)] == ["measured", "projected", "hospital"]
    res = {r["kpi"]: r for r in I.did_all(_seed(), AS_OF_REVIEW, C)}
    counted = {c["kpi"] for c in m["components"]}
    assert counted == {k for k, r in res.items() if r["status"] == "ok" and r["verdict"] == "worked"}
    assert {e["kpi"] for e in m["excluded"]} == set(res) - counted
    for c in m["components"]:
        assert c["dollars"] == round(c["events_avoided_per_quarter"] * 4 * c["unit_cost"]) and c["unit_kind"] in ("sourced", "assumption", "client_entered")
    assert m["dollars"] == sum(c["dollars"] for c in m["components"]) > 0
    assert any(i["label"] == "Time period" for i in m["inputs"]) and any(i["label"] == "Unit size" for i in m["inputs"])


def test_value_projection_is_sourced_and_in_range():
    v = I.value_of_plan(_seed(), AS_OF_REVIEW, C)
    p = v["tiers"][1]
    head = v["team"]["headcount"]
    gap = I.GALLUP_TURNOVER_GAP["applies"]   # Oct 27 polish: the 51% figure (organizations at or below 40% turnover); low = half of it (to the median)
    assert gap == I.GALLUP_TURNOVER_GAP["high"] and I.GALLUP_TURNOVER_GAP["median_share"] == 0.5
    assert p["low"] == round(head * I.TURNOVER_RATE["value"] * gap * I.GALLUP_TURNOVER_GAP["median_share"] * C["quit"]["value"])
    assert p["high"] == round(head * I.TURNOVER_RATE["value"] * gap * C["quit"]["value"])
    assert p["recovery"] == {"low": "median", "high": "top quartile"} and abs(p["high"] - 2 * p["low"]) <= 1   # half the gap, to the dollar
    assert "per late medication dose" in v["tiers"][0]["small_because"] and "late dose" not in v["tiers"][0]["small_because"]
    assert 0 < p["low"] < p["high"] and p["in_range"] is True
    assert I.PROJECTION_SANE_QUITS[0] <= p["quits_avoided_low"] <= p["quits_avoided_high"] <= I.PROJECTION_SANE_QUITS[1]
    assert all(i["source"] for i in p["inputs"]) and "gallup.com" in I.GALLUP_TURNOVER_GAP["source"]
    assert p["focus"]["item"] == "q02" and p["focus"]["quartile_w2"] == 1 and "to the median" in p["condition"] and "top quartile" in p["condition"]
    assert any(i["label"] == "Recovery assumed" for i in p["inputs"]) and any("above 40%" in i["label"] for i in p["inputs"])
    assert {m["kpi"] for m in p["mechanism"]} == {"late_doses", "quits"}
    assert "not cause" in p["sentence"]


def test_value_hospital_tier_matches_business_case():
    v = I.value_of_plan(_seed(), AS_OF_REVIEW, C)
    h = v["tiers"][2]
    vc = I.value_case(C, I.HOSPITAL_HEADCOUNT)
    assert (h["low"], h["high"]) == (vc["low"], vc["high"]) and h["low"] >= 10000  # the five-digit figure he asked for
    assert h["link"] == "/value" and h["headcount"] == I.HOSPITAL_HEADCOUNT
    assert any(i["label"] == "Hospital size" for i in h["inputs"]) and any(i["label"] == "Time period" for i in h["inputs"])


def test_value_follows_edited_unit_costs():
    costs = {k: dict(v) for k, v in C.items()}
    costs["late_dose"]["value"] = 400.0
    base = I.value_of_plan(_seed(), AS_OF_REVIEW, C)["tiers"][0]["dollars"]
    assert I.value_of_plan(_seed(), AS_OF_REVIEW, costs)["tiers"][0]["dollars"] == base * 10
