"""The generated data must contain the planted patterns strongly enough to be found."""
import json
from pathlib import Path

import pandas as pd
import pytest

GEN = Path(__file__).resolve().parents[1] / "data" / "generated"


@pytest.fixture(scope="module")
def truth():
    return json.loads((GEN / "truth.json").read_text())["patterns"]


@pytest.fixture(scope="module")
def tables():
    return {n: pd.read_csv(GEN / f"{n}.csv") for n in
            ["teams", "employees", "responses", "comments", "ops_daily", "staffing", "ownership_directory"]}


def test_p1_p2_richmond_night_drop(truth):
    assert truth["P1"]["wave1_mean"] - truth["P1"]["wave2_mean"] >= 0.45
    assert truth["P2"]["wave1_mean"] - truth["P2"]["wave2_mean"] >= 0.35
    assert truth["P1"]["n_wave1"] >= 10 and truth["P1"]["n_wave2"] >= 10


def test_p3_late_departures_double_after_june(truth):
    p = truth["P3"]
    assert p["late_rate_from_june"] >= 2 * p["late_rate_before_june"]


def test_p4_march_staffing_shortage(truth):
    p = truth["P4"]
    assert p["actual"] / p["scheduled"] <= 0.82


def test_p5_honeymoon(truth):
    g = truth["P5"]["grand_mean_by_tenure"]
    others = [g["1_to_3"], g["3_to_10"], g["over_10"]]
    assert g["under_1"] - max(others) >= 0.15


def test_p6_mix_shift_not_real_decline(truth):
    p = truth["P6"]
    assert p["under_1_share_w1"] >= 0.4 and p["under_1_share_w2"] <= 0.15
    assert p["team_mean_w1"] - p["team_mean_w2"] >= 0.15
    # within each band that has data in both waves, scores are stable (small-n noise allowed)
    for band, m1 in p["by_band_w1"].items():
        if band in p["by_band_w2"] and band != "under_1":
            assert abs(m1 - p["by_band_w2"][band]) <= 0.45


def test_p7_small_teams_exist(truth, tables):
    rows = truth["P7"]["rows"]
    names = {r["team_name"] for r in rows}
    assert {"Dispatch Day", "Maintenance Night"} <= names
    assert all(r["n"] < 4 for r in rows)


def test_p8_handoff_comments(truth, tables):
    ids = truth["P8"]["comment_ids"]
    assert len(ids) >= 3
    c = tables["comments"]
    assert (c[c.comment_id.isin(ids)].text.str.contains("handoff|checklist|loaded", case=False)).all()


def test_no_comments_from_suppressed_team_waves(truth, tables):
    c = tables["comments"]
    small = {(r["team_id"], r["wave_id"]) for r in truth["P7"]["rows"]}
    offending = [(r.team_id, r.wave_id) for r in c.itertuples() if (r.team_id, r.wave_id) in small]
    assert offending == []


def test_owner_exists_for_richmond_handoff(tables):
    o = tables["ownership_directory"]
    row = o[(o.process_name == "Shift handoff procedure") & (o.site_name == "Richmond")]
    assert len(row) == 1 and row.iloc[0].owner_role == "Site Operations Manager"
