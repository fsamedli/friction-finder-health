"""P14 (Oct 27, 2026 round): the plan that needed revision, shown next to the one that worked.

Pine Hollow Med-Surg Day runs about 3.5x its own unplanned overtime Feb-Aug 2026. Plan 1 (June 21, a float RN) misses
the obstacle and reviews as inconclusive on Aug 31; plan 2 (Sept 1, IV pump par level) is followed by the base rate
and reviews as improved on Nov 30. The excess is an independent Poisson draw added on top of the existing draw, so
every other team-month, and every Med-Surg Night number, is unchanged."""
import json

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from app import impact as I
from app.config import DATA_DIR

c = TestClient(app)
P1, P2 = "plan-pine-hollow-med-surg-day-1", "plan-pine-hollow-med-surg-day-2"


def truth():
    return json.loads((DATA_DIR / "truth.json").read_text())["patterns"]["P14"]


def plan(pid):
    return next(p for p in I.load_plans() if p["id"] == pid)


def test_p14_overtime_elevated_feb_aug_then_base_rate():
    p = truth()
    t = pd.read_csv(DATA_DIR / "team_ops_monthly.csv")
    x = t[t.team_id == p["team_id"]].set_index("month")
    rate = lambda ms: x.loc[ms, p["kpi"]].sum() / x.loc[ms, "headcount"].sum()
    assert p["kpi"] == "overtime_shifts" and p["team_id"] == 17
    assert rate(["2026-06", "2026-07", "2026-08"]) > 2.5 * rate(["2026-10", "2026-11"])
    assert round(rate(["2026-06", "2026-07", "2026-08"]), 3) == p["overtime_rate_jun_aug"]
    # the excess is added, never re-drawn: no other team-month carries P14 months' multiplier (Night team P11 unchanged)
    y = t[t.team_id == 4].set_index("month")
    assert round(y.loc[["2026-06", "2026-07", "2026-08"], "late_doses"].sum() / y.loc[["2026-06", "2026-07", "2026-08"], "headcount"].sum(), 3) == 1.929


def test_first_plan_inconclusive_and_revised_plan_worked():
    costs = I.default_costs()
    r1 = I.did(plan(P1), "2026-11-30", costs)
    r2 = I.did(plan(P2), "2026-11-30", costs)
    assert r1["status"] == "ok" and r1["verdict"] == "inconclusive" and r1["ci_low"] < 0 < r1["ci_high"]
    assert r2["status"] == "ok" and r2["verdict"] == "worked" and r2["ci_high"] < 0
    assert r1["pre_months"] == ["2026-03", "2026-04", "2026-05"] and r1["post_months"] == ["2026-07", "2026-08"]
    assert r2["pre_months"] == ["2026-06", "2026-07", "2026-08"] and r2["post_months"] == ["2026-10", "2026-11"]
    # at the detect clock plan 1 is already judged and plan 2 is not yet due
    assert I.did(plan(P1), "2026-09-15", costs)["status"] == "ok"
    assert I.did(plan(P2), "2026-09-15", costs)["status"] == "not_reached"


def test_med_surg_night_numbers_unchanged():
    costs = I.default_costs()
    r = I.did(plan("plan-lanford-med-surg-night"), "2026-11-30", costs)
    assert (r["verdict"], r["estimate"], r["ci_low"], r["ci_high"]) == ("worked", -1.056, -1.674, -0.437)
    b = I.board(1, "2026-09-15", costs)
    flagged = [t["team_name"] for t in b["teams"] if t["status"] in ("red", "amber")]
    assert flagged == ["Med-Surg Night"]
    t4 = next(t for t in b["teams"] if t["team_id"] == 4)["excess_by_kpi"]["late_doses"]
    assert (t4["observed"], t4["expected"]) == (81.0, 51.4)


def test_revised_plans_load_through_the_api_with_links_both_ways():
    p1 = c.get(f"/api/plans/{P1}").json()
    p2 = c.get(f"/api/plans/{P2}").json()
    assert p1["superseded_by"] == P2 and p2["revised_from"] == P1 and p2["revision_reason"]
    for p in (p1, p2):   # seeded as approved with every task ticked; the execution record is derived on read
        assert p["status"] == "approved" and p["progress"] == {"done": 3, "total": 3}
        assert all(a["status"] == "done" and a["id"] for a in p["actions"])
        assert p["execution"] and p["execution"]["nothing_sent"] is True
    board = c.get("/api/plans/board", params={"as_of": "2026-11-30"}).json()
    by_id = {p["id"]: p for p in board["plans"]}
    assert by_id[P1]["state"] == "reviewed" and by_id[P1]["result"]["verdict"] == "inconclusive"
    assert by_id[P2]["state"] == "reviewed" and by_id[P2]["result"]["verdict"] == "worked"
    assert P1 in board["queue"]["inconclusive"]
    sept = c.get("/api/plans/board", params={"as_of": "2026-09-15"}).json()
    assert {p["id"]: p["state"] for p in sept["plans"]}[P2] == "approved"
    # the revised plan's report is the manager's record: it names the first plan's dates
    html = c.get(f"/api/report/{P2}", params={"as_of": "2026-11-30"}).text
    assert "Med-Surg Day" in html and "Checklist" in html


def test_seeded_med_surg_night_plan_reads_three_of_three_done_at_review():
    """The seed's tasks carry stable ids and were ticked on their due dates, so the review-date board does not show an
    Improved plan with nothing done. _norm_plan keeps seeded ids and statuses rather than overwriting them."""
    p = c.get("/api/plans/plan-lanford-med-surg-night").json()
    assert [a["id"] for a in p["actions"]] == ["a1", "a2", "a3"]
    assert [a["status"] for a in p["actions"]] == ["done"] * 3
    assert [a["done_at"][:10] for a in p["actions"]] == ["2026-09-28", "2026-10-05", "2026-10-12"]
    assert p["progress"] == {"done": 3, "total": 3}
    board = c.get("/api/plans/board", params={"as_of": "2026-11-30"}).json()
    seed = next(x for x in board["plans"] if x["id"] == "plan-lanford-med-surg-night")
    assert seed["progress"] == {"done": 3, "total": 3} and seed["result"]["verdict"] == "worked"
