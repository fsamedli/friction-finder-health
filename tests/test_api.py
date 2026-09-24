"""v0.6 API: every endpoint the web app uses, plus the Review Focus edge cases."""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from app import config

c = TestClient(app)


@pytest.fixture(autouse=True)
def clean_costs():
    (config.CACHE_DIR / "costs.json").unlink(missing_ok=True)
    yield
    (config.CACHE_DIR / "costs.json").unlink(missing_ok=True)


def test_meta():
    m = c.get("/api/meta").json()
    assert len(m["sites"]) == 3 and len(m["as_of_presets"]) == 2 and m["min_n"] == 4


def test_board_ok():
    r = c.get("/api/board", params={"site_id": 1, "as_of": "2026-09-15"})
    assert r.status_code == 200
    assert r.json()["teams"][0]["status"] == "red"


def test_bad_as_of():
    assert c.get("/api/board", params={"site_id": 1, "as_of": "Sept 15"}).status_code == 422


def test_small_team_no_scores():
    b = c.get("/api/board", params={"site_id": 1, "as_of": "2026-09-15"}).json()
    small = [t for t in b["teams"] if t["status"] == "rolled_up"]
    assert small and all(t["engagement"] is None for t in small)
    w = c.get(f"/api/why/{small[0]['team_id']}", params={"as_of": "2026-09-15"})
    assert w.status_code == 200 and w.json()["suppressed"]


def test_unknown_team_404():
    assert c.get("/api/why/999").status_code == 404


def test_links_and_link():
    assert len(c.get("/api/links").json()) == 5 * 13
    l = c.get("/api/link", params={"kpi": "late_departures", "item": "q02"}).json()
    assert l["association"]["verdict"] == "association" and l["quartile"]["n_cells"] >= 30
    assert c.get("/api/link", params={"kpi": "nope", "item": "q02"}).status_code == 422


def test_costs_validation_and_recompute():
    assert c.put("/api/costs", json={"quit": -5}).status_code == 422
    assert c.put("/api/costs", json={"quit": "abc"}).status_code == 422
    v0 = c.get("/api/value").json()["high"]
    assert c.put("/api/costs", json={"quit": 20000}).status_code == 200
    assert c.get("/api/value").json()["high"] > v0
    assert c.put("/api/costs", json={"late_departure": 0}).status_code == 200


def test_plan_result_states():
    pid = c.get("/api/plans").json()[0]["id"]
    ok = c.get(f"/api/plans/{pid}/result", params={"as_of": "2026-11-30"}).json()
    assert ok["verdict"] == "worked" and len(ok["also"]) == 2
    assert c.get(f"/api/plans/{pid}/result", params={"as_of": "2026-10-15"}).json()["status"] == "not_reached"


def test_create_plan_live_then_insufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    import app.impact as I
    monkeypatch.setattr(I, "CACHE_DIR", tmp_path)
    body = {"team_id": 4, "item": "q02", "kpi": "late_departures", "start": "2026-11-20",
            "actions": [{"text": "Fix the handoff log", "owner": "Priya Singh", "due": "2026-11-27"}]}
    p = c.post("/api/plans", json=body).json()
    assert p["review"] == "2027-01-31"   # end of the second full month after the start
    r = c.get(f"/api/plans/{p['id']}/result", params={"as_of": "2026-11-30"}).json()
    assert r["status"] == "not_reached"
    assert c.post("/api/plans", json={**body, "actions": []}).status_code == 422


def test_report_html():
    pid = c.get("/api/plans").json()[0]["id"]
    r = c.get(f"/api/report/{pid}")
    assert r.status_code == 200 and "Did it work?" in r.text and "worked" in r.text


def test_assumptions_evals_feedback():
    assert len(c.get("/api/assumptions").json()["rows"]) >= 6
    assert c.get("/api/evals/latest").status_code == 200
    assert len(c.get("/api/feedback").json()) >= 4


def test_ask_rules_mode_without_key(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "has_key", lambda: False)
    monkeypatch.setattr(config, "APPROVALS_PATH", tmp_path / "approvals.jsonl")
    r = c.post("/api/ask", json={"question": "Why did the Richmond night shift's scores drop and why are deliveries late?"})
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "rules" and d["status"] == "ok" and d["evidence"]
    assert c.post("/api/approve", json={"result_id": d["id"], "decision": "flagged", "note": "test"}).status_code == 200


def test_ask_reports_grounding_and_trace(monkeypatch):
    monkeypatch.setattr(config, "has_key", lambda: False)
    d = c.post("/api/ask", json={"question": "Why did the Richmond night shift's scores drop and why are deliveries late?"}).json()
    g = d["grounding"]
    assert g["total"] > 0 and g["checked"] == g["total"] and g["unmatched"] == []
    steps = [t["step"] for t in d["trace"]]
    assert steps[0] == "Understand the question" and steps[-1] == "Check the brief"


def test_sources():
    s = c.get("/api/sources").json()
    assert {x["id"] for x in s} >= {"survey", "timekeeping", "wms"} and all(x["rows"] >= 0 for x in s)


def test_live_plan_on_demo_path_is_reviewable(tmp_path, monkeypatch):
    """The demo: approve a Night A plan at Sept 15 (start Sept 21), fast-forward to Nov 30 -> a verdict, not 'insufficient'."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    import app.impact as I
    monkeypatch.setattr(I, "CACHE_DIR", tmp_path)
    body = {"team_id": 4, "item": "q02", "kpi": "late_departures", "start": "2026-09-21",
            "actions": [{"text": "Fix the handoff log", "owner": "Priya Singh", "due": "2026-09-28"}]}
    p = c.post("/api/plans", json=body).json()
    assert p["review"] == "2026-11-30"
    r = c.get(f"/api/plans/{p['id']}/result", params={"as_of": "2026-11-30"}).json()
    assert r["status"] == "ok" and r["verdict"] == "worked"
