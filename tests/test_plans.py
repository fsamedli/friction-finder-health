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
    seeded = {x["id"] for x in json.loads((config.DATA_DIR / "plans_seed.json").read_text())}   # the demo seeds, however many
    assert len([x for x in I.load_plans() if x["id"] not in seeded]) == 1   # survives reload: read back from plans.jsonl
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


# ---------------------------------------------------------------- Oct 27, 2026 round: the plan as a checklist the manager runs

def test_approval_assigns_owners_schedules_review_sets_watch_and_drafts_notices(scratch):
    """Prof. Hall, Oct 21: tasks with responsible people and due dates, and 'an agent that does something' after approval,
    bounded: assign, schedule, watch, draft. Keyless here, so the notices are templated and say so. Nothing is sent."""
    body = {**BODY, "request_id": "r1", "actions": [{"text": "Restore the 05:00 cabinet restock", "owner": "", "due": "2026-09-28"},
                                                    {"text": "Charge nurse logs stock-outs at 02:00", "owner": "Med-Surg Night charge nurse", "due": "2026-10-05"}]}
    p = c.post("/api/plans", json=body).json()
    assert [a["id"] for a in p["actions"]] == ["a1", "a2"] and all(a["status"] == "todo" and a["done_at"] is None for a in p["actions"])
    assert p["progress"] == {"done": 0, "total": 2}
    ex = p["execution"]
    assert ex["nothing_sent"] is True and ex["mode"] == "rules" and ex["notices_status"] == "ready" and not ex.get("derived")
    # the blank owner was filled from the plan owner the manager typed (BODY has one); the typed owner is kept
    assert ex["assigned"][0] == {"action_id": "a1", "owner": BODY["owner"], "source": "plan owner"}
    assert ex["assigned"][1]["source"] == "manager" and p["actions"][1]["owner"] == "Med-Surg Night charge nurse"
    assert ex["review_scheduled"]["date"] == "2026-11-30" and ex["review_scheduled"]["queue"] == "Due reviews"
    assert ex["kpi_watch"] == {"kpi": "late_doses", "kpi_label": "Late medication doses", "team_id": 4, "team_label": "Lanford Med-Surg Night",
                               "from": "2026-09-21", "until": "2026-11-30", "cadence": "monthly, from the team-month operating records"}
    assert len(ex["notices"]) == 2 and all(n["sent"] is False and n["written_by"] == "rules" for n in ex["notices"])
    n = next(x for x in ex["notices"] if x["to"] == "Med-Surg Night charge nurse")
    assert "Charge nurse logs stock-outs at 02:00" in n["body"] and "Oct 5, 2026" in n["body"] and "Nov 30, 2026" in n["body"] and "late medication doses" in n["body"]
    # idempotent: approving again does not make a second record
    again = c.post(f"/api/plans/{p['id']}/approve", json={"request_id": "x", "edits": []}).json()
    assert again["duplicate"] and again["execution"]["at"] == ex["at"]
    recs = [json.loads(l) for l in (scratch / "approvals.jsonl").read_text().splitlines()]
    assert [r["target"] for r in recs] == ["plan"]


def test_blank_owner_falls_back_to_the_ownership_directory_then_the_team_manager(scratch):
    body = {k: v for k, v in BODY.items() if k != "owner"}
    p = c.post("/api/plans", json={**body, "request_id": "r1", "obstacle": "Cabinet restocked after the 06:00 pass",
                                   "actions": [{"text": "Restore the 05:00 cabinet restock", "owner": "", "due": "2026-09-28"}]}).json()
    assert p["actions"][0]["owner"] == "Priya Singh, Pharmacy Operations Manager" and p["execution"]["assigned"][0]["source"] == "ownership directory"
    p2 = c.post("/api/plans", json={**body, "request_id": "r2", "team_id": 1, "obstacle": "Handover runs late most days",
                                    "actions": [{"text": "Move the huddle to 06:45", "owner": "", "due": "2026-09-28"}]}).json()
    assert p2["actions"][0]["owner"].endswith(", nurse manager") and p2["execution"]["assigned"][0]["source"] == "team manager"


def test_blank_generic_task_goes_to_the_nurse_manager_not_the_plan_owner(scratch):
    """Oct 27 polish: a check-in task with no owner belongs to the approving nurse manager (team 4's manager in teams.csv);
    the plan owner (the pharmacy manager) only gets tasks that name the process they own."""
    import pandas as pd
    manager = str(pd.read_csv(config.DATA_DIR / "teams.csv").set_index("team_id").loc[4, "manager_name"])
    body = {**BODY, "request_id": "r9", "actions": [{"text": "Restore the 05:00 cabinet restock", "owner": "", "due": "2026-09-28"},
                                                    {"text": "Ten-minute team check-in every other Monday: did the actions happen, did they help?", "owner": "", "due": "2026-10-12"}]}
    p = c.post("/api/plans", json=body).json()
    assert p["actions"][0]["owner"] == BODY["owner"] and p["execution"]["assigned"][0]["source"] == "plan owner"
    assert p["actions"][1]["owner"] == f"{manager}, nurse manager" and p["execution"]["assigned"][1]["source"] == "team manager"
    added = c.post(f"/api/plans/{p['id']}/actions", json={"text": "Tell the team what changed because of their answers", "owner": "", "due": "2026-10-19"}).json()
    assert added["actions"][-1]["owner"] == f"{manager}, nurse manager"
    # the notices are signed by the nurse manager, never by the pharmacy owner, and the two names differ
    assert all(n["body"].rstrip().endswith(f"{manager}, nurse manager, Lanford Med-Surg Night") for n in p["execution"]["notices"]) and manager != "Priya Singh"


def test_tick_edit_and_add_tasks_are_saved_and_recorded(scratch):
    p = c.post("/api/plans", json={**BODY, "request_id": "r1"}).json()
    pid = p["id"]
    t = c.patch(f"/api/plans/{pid}/actions/a1", json={"status": "done"}).json()
    assert t["actions"][0]["status"] == "done" and t["actions"][0]["done_at"] and t["progress"] == {"done": 1, "total": 1}
    t = c.patch(f"/api/plans/{pid}/actions/a1", json={"status": "todo"}).json()
    assert t["actions"][0]["status"] == "todo" and t["actions"][0]["done_at"] is None
    t = c.patch(f"/api/plans/{pid}/actions/a1", json={"owner": "Sam Kim, Nurse Manager", "due": "2026-10-01", "text": "Restore the 05:00 restock and log it"}).json()
    assert t["actions"][0]["owner"] == "Sam Kim, Nurse Manager" and t["actions"][0]["due"] == "2026-10-01"
    assert c.patch(f"/api/plans/{pid}/actions/a1", json={"due": "soon"}).status_code == 422
    assert c.patch(f"/api/plans/{pid}/actions/zz", json={"status": "done"}).status_code == 404
    assert c.patch("/api/plans/nope/actions/a1", json={"status": "done"}).status_code == 404
    a = c.post(f"/api/plans/{pid}/actions", json={"text": "Post the new routine on the unit board", "owner": "", "due": "2026-10-12"}).json()
    # Oct 27 polish: a generic task with no owner goes to the approving nurse manager, not the plan owner (the pharmacy manager)
    assert [x["id"] for x in a["actions"]] == ["a1", "a2"] and a["actions"][1]["owner"].endswith(", nurse manager") and a["progress"]["total"] == 2
    assert a["execution"]["assigned"][-1]["action_id"] == "a2" and a["execution"]["assigned"][-1]["owner"].endswith(", nurse manager") and a["execution"]["assigned"][-1]["source"] == "manager"
    assert c.post(f"/api/plans/{pid}/actions", json={"text": "x", "owner": "", "due": "2026-10-12"}).status_code == 422
    # survives a reload and shows on the board; every change is in the record with the time
    g = c.get(f"/api/plans/{pid}").json()
    assert len(g["actions"]) == 2 and g["actions"][0]["text"].startswith("Restore the 05:00 restock and log it")
    board = c.get("/api/plans/board", params={"as_of": "2026-09-15"}).json()
    assert next(x for x in board["plans"] if x["id"] == pid)["progress"] == {"done": 0, "total": 2}
    recs = [json.loads(l) for l in (scratch / "approvals.jsonl").read_text().splitlines()]
    assert [(r["target"], r["decision"]) for r in recs] == [("plan", "approved"), ("action", "updated"), ("action", "updated"), ("action", "updated"), ("action", "added")]
    assert recs[1]["action_id"] == "a1" and recs[1]["changes"] == {"status": "done"} and all("ts" in r for r in recs)


def test_old_plans_load_as_checklists_and_the_seed_can_be_unticked(scratch):
    """Seeded plans carry stable ids and are ticked on their due dates (Oct 27 round: the review-date board reads 3 of 3
    done next to Improved); v0.7/v0.8 records without ids or statuses get them on read; execution is derived, never sent.
    The manager can untick a seeded task, the change persists, and Reset demo restores the seed."""
    seed = c.get(f"/api/plans/{SEED}").json()
    assert [a["id"] for a in seed["actions"]] == ["a1", "a2", "a3"] and all(a["status"] == "done" for a in seed["actions"])
    assert [a["done_at"][:10] for a in seed["actions"]] == ["2026-09-28", "2026-10-05", "2026-10-12"]
    assert seed["execution"]["derived"] is True and seed["execution"]["nothing_sent"] is True and len(seed["execution"]["notices"]) == 3
    assert seed["team_label"] == "Lanford Med-Surg Night" and seed["progress"] == {"done": 3, "total": 3}
    t = c.patch(f"/api/plans/{SEED}/actions/a2", json={"status": "todo"}).json()
    assert t["progress"] == {"done": 2, "total": 3} and t["actions"][1]["done_at"] is None
    assert c.get(f"/api/plans/{SEED}").json()["actions"][1]["status"] == "todo"      # persisted in plans.jsonl
    rows = c.get("/api/plans").json()
    assert all("progress" in r and all("id" in a and "status" in a for a in r["actions"]) for r in rows)
    assert c.delete("/api/demo").json()["ok"] and c.get(f"/api/plans/{SEED}").json()["progress"]["done"] == 3   # Reset demo restores the seed
    assert c.get("/api/plans/nope").status_code == 404


def test_regenerate_actions_from_the_edited_obstacle():
    """The edit-and-regenerate half of the loop: new actions and an owner from the ownership directory for the theme the
    manager typed; rules mode is labelled; nothing is saved."""
    r = c.post("/api/plans/regenerate", json={"team_id": 4, "obstacle": "IV pumps keep failing the pre-shift check", "kpi": "late_doses", "start": "2026-09-21"}).json()
    import pandas as pd
    d = pd.read_csv(config.DATA_DIR / "ownership_directory.csv")
    ce = str(d[(d.site_name == "Lanford") & (d.owner_role == "Clinical Engineering Lead")].owner_name.iloc[0])   # the directory's name, not a literal
    assert r["theme"] == "equipment" and r["owner"] == f"{ce}, Clinical Engineering Lead" and r["mode"] == "rules"
    assert len(r["actions"]) == 3 and r["actions"][0]["owner"] == r["owner"] and [a["due"] for a in r["actions"]] == ["2026-09-28", "2026-10-05", "2026-10-12"]
    r2 = c.post("/api/plans/regenerate", json={"team_id": 4, "obstacle": "Night shift is short staffed", "kpi": "late_doses", "start": "2026-09-21"}).json()
    assert r2["theme"] == "schedule" and r2["owner"] == "Marcus Okafor, Chief Nursing Officer"
    r3 = c.post("/api/plans/regenerate", json={"team_id": 4, "obstacle": "Handover takes too long", "kpi": "late_doses", "start": "2026-09-21"}).json()
    assert r3["theme"] == "generic" and r3["owner"].endswith(", nurse manager")
    assert c.post("/api/plans/regenerate", json={"team_id": 4, "obstacle": "x", "kpi": "late_doses", "start": "2026-09-21"}).status_code == 422
    assert c.post("/api/plans/regenerate", json={"team_id": 4, "obstacle": "Handover", "kpi": "nope", "start": "2026-09-21"}).status_code == 422
    seeded = {x["id"] for x in json.loads((config.DATA_DIR / "plans_seed.json").read_text())}
    assert len([p for p in I.load_plans() if p["id"] not in seeded]) == 0
