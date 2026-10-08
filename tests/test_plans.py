"""v0.8 plans and feedback (Phase 6): the plan the manager edits and approves, the existing-plan check, double
submission, the approvals record, plan states and the review queue, and feedback on investigation answers."""
import json

import pytest
from fastapi.testclient import TestClient

import api.main as M
import app.impact as I
from app import config

c = TestClient(M.app)
BODY = {"team_id": 4, "item": "q02", "kpi": "late_doses", "start": "2026-09-21", "status": "approved",
        "actions": [{"text": "Restore the 05:00 cabinet restock", "owner": "Priya Singh, Pharmacy Operations Manager", "due": "2026-09-28"}],
        "owner": "Priya Singh, Pharmacy Operations Manager", "measure": "Late medication doses per 10 people per month",
        "success": "Back inside the comparable range", "baseline": "19.3 per 10 people per month in Jun-Aug 2026",
        "assumptions": ["Two full months of operating data after the start."], "evidence_ids": ["M1", "K2"], "investigation_id": "inv1",
        "edits": [{"field": "owner", "from": "Owner needed", "to": "Priya Singh, Pharmacy Operations Manager"}]}
SEED = "plan-lanford-med-surg-night"


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(I, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "APPROVALS_PATH", tmp_path / "approvals.jsonl")
    monkeypatch.setattr(M, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    yield tmp_path


def test_check_ignores_seed_then_finds_live_plan():
    chk = c.get("/api/plans/check", params={"team_id": 4, "kpi": "late_doses", "start": "2026-09-21"}).json()
    assert chk["existing"] == [] and "none found" in chk["explanation"]
    p = c.post("/api/plans", json={**BODY, "request_id": "r1"}).json()
    chk = c.get("/api/plans/check", params={"team_id": 4, "kpi": "late_doses", "start": "2026-09-21"}).json()
    assert [x["id"] for x in chk["existing"]] == [p["id"]] and "already cover" in chk["explanation"]


def test_approve_records_edits_and_double_submit_is_explained(scratch):
    p = c.post("/api/plans", json={**BODY, "request_id": "r1"}).json()
    assert p["status"] == "approved" and p["review"] == "2026-11-30" and p["owner"].startswith("Priya Singh") and "decided_at" in p
    again = c.post("/api/plans", json={**BODY, "request_id": "r1"})
    assert again.status_code == 200 and again.json()["duplicate"] and again.json()["id"] == p["id"]
    other = c.post("/api/plans", json={**BODY, "request_id": "r2"})          # a second click with a new id, same team/KPI/period
    assert other.status_code == 200 and other.json()["duplicate"] and other.json()["id"] == p["id"]
    assert len([x for x in I.load_plans() if x["id"] != SEED]) == 1   # survives reload: read back from plans.jsonl
    recs = [json.loads(l) for l in (scratch / "approvals.jsonl").read_text().splitlines()]
    assert len(recs) == 1 and recs[0]["decision"] == "approved" and recs[0]["edits"][0]["field"] == "owner" and recs[0]["plan_id"] == p["id"]


def test_draft_then_approve_endpoint():
    d = c.post("/api/plans", json={**BODY, "status": "draft", "request_id": "d1"}).json()
    assert d["status"] == "draft"
    board = c.get("/api/plans/board", params={"as_of": "2026-09-15"}).json()
    assert next(x for x in board["plans"] if x["id"] == d["id"])["state"] == "draft"
    a = c.post(f"/api/plans/{d['id']}/approve", json={"request_id": "d1-approve", "edits": []}).json()
    assert a["status"] == "approved"
    assert c.post(f"/api/plans/{d['id']}/approve", json={"request_id": "x", "edits": []}).json()["duplicate"]
    assert c.post("/api/plans/nope/approve", json={"request_id": "x"}).status_code == 404


def test_states_and_queue_across_the_demo_clock():
    p = c.post("/api/plans", json={**BODY, "request_id": "r1"}).json()
    before = c.get("/api/plans/board", params={"as_of": "2026-09-15"}).json()
    row = next(x for x in before["plans"] if x["id"] == p["id"])
    assert row["state"] == "approved" and row["result"]["status"] == "not_reached"
    assert all(x["id"] != SEED for x in before["plans"])   # the seed hides behind the live plan
    after = c.get("/api/plans/board", params={"as_of": "2026-11-30"}).json()
    row = next(x for x in after["plans"] if x["id"] == p["id"])
    assert row["state"] == "reviewed" and row["result"]["verdict"] == "worked"
    assert p["id"] in after["queue"]["due_reviews"] and after["queue"]["missing_follow_ups"] == []


def test_investigation_feedback_counts_from_zero():
    q = c.get("/api/quality").json()["feedback"]
    assert q["investigation"] == {"total": 0, "by_reason": {r: 0 for r in M.FEEDBACK_REASONS}}
    assert "never evidence" in q["note"]
    r = c.post("/api/useful", json={"target": "investigation", "target_id": "inv1", "useful": False, "reason": "wrong context", "evidence_ids": ["M1"]})
    assert r.status_code == 200 and r.json()["evidence_ids"] == ["M1"]
    assert c.post("/api/useful", json={"target": "investigation", "target_id": "inv1", "useful": False, "reason": "made up"}).status_code == 422
    q = c.get("/api/quality").json()["feedback"]["investigation"]
    assert q["total"] == 1 and q["by_reason"]["wrong context"] == 1 and q["by_reason"]["wrong number"] == 0


def test_from_feedback_drafts_cases_without_expectations():
    from evals.from_feedback import drafts
    rows = [{"ts": "t", "target": "investigation", "target_id": "inv1", "useful": False, "reason": "wrong number", "evidence_ids": ["M1"]},
            {"ts": "t", "target": "plan", "target_id": "p1", "useful": False, "reason": "wrong owner"}]
    d = drafts(rows)
    assert len(d) == 1 and d[0]["expect"] is None and d[0]["cited_evidence_ids"] == ["M1"] and d[0]["status"].startswith("draft")
