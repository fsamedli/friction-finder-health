"""v0.8: one metric definition behind the dashboards, Ask and the investigation tools.
The board (app/impact.py) and the structured query path (app/metrics.py -> templated SQL on v_team_ops_month)
must give the same numbers for Lanford Med-Surg Night (team 4), for every operating metric the screens show."""
import pytest

from app import impact as I
from app import metrics as M
from app.db import DB


@pytest.fixture(scope="module")
def db():
    return DB()


def test_metric_keys_match_the_board():
    assert set(M.METRICS) == set(I.KPIS) | {"late_rate"}
    assert M.METRICS["late_rate"].numerator == "late_doses" and M.METRICS["late_rate"].denominator == "scheduled_doses"


@pytest.mark.parametrize("as_of", [I.AS_OF_DETECT, I.AS_OF_REVIEW])
@pytest.mark.parametrize("kpi", I.KPIS)
def test_board_and_query_metric_agree_for_med_surg_night(db, kpi, as_of):
    board = I.board(1, as_of, I.default_costs())
    row = next(t for t in board["teams"] if t["team_id"] == 4)
    e = row["excess_by_kpi"][kpi]
    res = M.query_metric(M.MetricQuery(metric=kpi, team_id=4, as_of=as_of, compare_to="comparable"), db)
    assert res.status == "ok"
    assert res.months == board["window"]
    assert res.events == e["observed"]
    assert round(res.rate, 3) == e["rate"]
    assert round(res.comparison["pooled_rate"], 3) == e["baseline"]
    assert round(res.comparison["pooled_rate"] * res.exposure, 1) == e["expected"]
    assert all("v_team_ops_month" in s for s in res.sql)


def test_small_team_is_suppressed_and_kept_out_of_totals(db):
    res = M.query_metric(M.MetricQuery(metric="late_doses", team_id=8), db)   # EVS Night, 2 people
    assert res.status == "suppressed" and res.events is None
    site = M.query_metric(M.MetricQuery(metric="late_doses", site_id=1, shift="Night"), db)
    ids = {int(r["team_id"]) for r in db.run_sql("SELECT DISTINCT team_id FROM v_team_ops_month WHERE site_id = 1 AND shift = 'Night'").to_records()}
    assert 8 not in ids and site.status == "ok"
    # the night-shift total equals the sum of the visible night teams: nothing left over to subtract
    parts = [M.query_metric(M.MetricQuery(metric="late_doses", team_id=t), db).events for t in ids]
    assert site.events == sum(parts)


def test_missing_period_unknown_metric_and_zero_denominator(db):
    assert M.query_metric(M.MetricQuery(metric="late_doses", team_id=4, months=["2025-06"]), db).status == "missing_period"
    assert M.query_metric(M.MetricQuery(metric="throughput", team_id=4), db).status == "unknown_metric"
    assert M.query_metric(M.MetricQuery(metric="late_doses", team_id=999), db).status == "unknown_entity"


def test_late_rate_by_hour_band(db):
    res = M.query_metric(M.MetricQuery(metric="late_rate", site_id=1, shift="Night"), db)
    assert res.status == "ok" and res.rows and {"hour_band", "period", "scheduled_doses", "late_doses", "late_pct"} <= set(res.rows[0])
    band = {(r["hour_band"], r["period"]): r["late_pct"] for r in res.rows}
    assert band[("06-07", "Jun-Sep 2026")] >= 2 * band[("06-07", "Jan-May 2026")]   # P3
    assert "doses" in M.sentence(res)
    assert M.query_metric(M.MetricQuery(metric="late_rate"), db).status == "unknown_entity"


def test_sentence_carries_unit_and_period(db):
    res = M.query_metric(M.MetricQuery(metric="absence_days", team_id=4, compare_to="comparable"), db)
    s = M.sentence(res)
    assert "per 10 people per month" in s and "Jun-Aug 2026" in s and str(int(res.events)) in s


def test_metric_words():
    assert M.metric_in("How many quits did Med-Surg Night have?") == "quits"
    assert M.metric_in("Were there more absences this summer?") == "absence_days"
    assert M.metric_in("Which hour band has the late rate problem?") == "late_rate"
    assert M.metric_in("How many late meds on nights in July?") == "late_doses"
    assert M.metric_in("Did sick calls go up?") == "absence_days"
    assert M.metric_in("How much OT did the unit run?") == "overtime_shifts"
    assert M.metric_in("Any needlestick injuries?") == "injuries"
    assert M.metric_in("Is RN turnover worse here?") == "quits"
    assert M.metric_in("Is it worth noting that both teams moved?") is None   # 'ot' inside 'both' and 'noting' must not fire
