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
    l = c.get("/api/link", params={"kpi": "late_doses", "item": "q02"}).json()
    assert l["association"]["verdict"] == "association" and l["quartile"]["n_cells"] >= 30
    assert c.get("/api/link", params={"kpi": "nope", "item": "q02"}).status_code == 422


def test_costs_validation_and_recompute():
    assert c.put("/api/costs", json={"quit": -5}).status_code == 422
    assert c.put("/api/costs", json={"quit": "abc"}).status_code == 422
    v0 = c.get("/api/value").json()["high"]
    quit_cost = c.get("/api/costs").json()["quit"]["value"]
    assert c.put("/api/costs", json={"quit": quit_cost * 2}).status_code == 200   # above the sourced default, whatever it is
    assert c.get("/api/value").json()["high"] > v0
    assert c.put("/api/costs", json={"late_dose": 0}).status_code == 200


def test_plan_result_states():
    pid = c.get("/api/plans").json()[0]["id"]
    ok = c.get(f"/api/plans/{pid}/result", params={"as_of": "2026-11-30"}).json()
    assert ok["verdict"] == "worked" and len(ok["also"]) == 2
    assert c.get(f"/api/plans/{pid}/result", params={"as_of": "2026-10-15"}).json()["status"] == "not_reached"


def test_create_plan_live_then_insufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    import app.impact as I
    monkeypatch.setattr(I, "CACHE_DIR", tmp_path)
    body = {"team_id": 4, "item": "q02", "kpi": "late_doses", "start": "2026-11-20",
            "actions": [{"text": "Restore the 05:00 cabinet restock", "owner": "Priya Singh", "due": "2026-11-27"}]}
    p = c.post("/api/plans", json=body).json()
    assert p["review"] == "2027-01-31"   # end of the second full month after the start
    r = c.get(f"/api/plans/{p['id']}/result", params={"as_of": "2026-11-30"}).json()
    assert r["status"] == "not_reached"
    assert c.post("/api/plans", json={**body, "actions": []}).status_code == 422


def test_report_html():
    pid = c.get("/api/plans").json()[0]["id"]
    r = c.get(f"/api/report/{pid}")
    assert r.status_code == 200 and "Did it work?" in r.text and "worked" in r.text
    # Oct 27 round: the report is the printable checklist (task, responsible, due, status) plus what happened at approval.
    # Seeded plans may have every task done by the review date, so either the open or the ticked box glyph counts.
    assert "Checklist" in r.text and "Responsible" in r.text and ("&#9744;" in r.text or "&#9745;" in r.text)
    assert "What happened when the plan was approved" in r.text and "Nothing is sent" in r.text


def test_assumptions_evals_feedback():
    assert len(c.get("/api/assumptions").json()["rows"]) >= 6
    assert c.get("/api/evals/latest").status_code == 200
    assert len(c.get("/api/feedback").json()) >= 4


def test_ask_rules_mode_without_key(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "has_key", lambda: False)
    monkeypatch.setattr(config, "APPROVALS_PATH", tmp_path / "approvals.jsonl")
    # live=True: a live run (the scripted question otherwise returns its labelled prepared answer)
    r = c.post("/api/ask", json={"question": "Why did the Lanford night shift's scores drop and why are doses late?", "live": True})
    assert r.status_code == 200
    d = r.json()
    assert d["mode"] == "rules" and d["status"] == "ok" and d["evidence"]
    assert c.post("/api/approve", json={"result_id": d["id"], "decision": "flagged", "note": "test"}).status_code == 200


def test_ask_reports_grounding_and_trace(monkeypatch):
    monkeypatch.setattr(config, "has_key", lambda: False)
    d = c.post("/api/ask", json={"question": "Why did the Lanford night shift's scores drop and why are doses late?", "live": True}).json()
    g = d["grounding"]
    assert g["total"] > 0 and g["checked"] == g["total"] and g["unmatched"] == []
    steps = [t["step"] for t in d["trace"]]
    assert steps[0] == "Understand the question" and steps[-1] == "Check the brief"


def test_sources():
    s = c.get("/api/sources").json()
    assert {x["id"] for x in s} >= {"survey", "timekeeping", "emar"} and all(x["rows"] >= 0 for x in s)
    # never claim a live connection to a vendor system (overnight rule 6)
    assert all(x["status"] in ("demo_csv", "not_connected") for x in s)
    assert all(x["vendor"].startswith("Would") for x in s)


def test_live_plan_on_demo_path_is_reviewable(tmp_path, monkeypatch):
    """The demo: approve a Med-Surg Night plan at Sept 15 (start Sept 21), fast-forward to Nov 30 -> a verdict, not 'insufficient'."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    import app.impact as I
    monkeypatch.setattr(I, "CACHE_DIR", tmp_path)
    body = {"team_id": 4, "item": "q02", "kpi": "late_doses", "start": "2026-09-21",
            "actions": [{"text": "Restore the 05:00 cabinet restock", "owner": "Priya Singh", "due": "2026-09-28"}]}
    p = c.post("/api/plans", json=body).json()
    assert p["review"] == "2026-11-30"
    r = c.get(f"/api/plans/{p['id']}/result", params={"as_of": "2026-11-30"}).json()
    assert r["status"] == "ok" and r["verdict"] == "worked"


def test_prepared_answer_is_labelled_and_live_bypasses_it(monkeypatch, tmp_path):
    import api.main as M
    q = "Why did the Lanford night shift's scores drop and why are doses late?"
    monkeypatch.setattr(config, "has_key", lambda: False)
    monkeypatch.setattr(config, "APPROVALS_PATH", tmp_path / "approvals.jsonl")
    live = c.post("/api/ask", json={"question": q, "live": True}).json()
    assert live["prepared"] is None and live["mode"] == "rules"
    fake = {M._norm(q): {"generated_at": "2026-09-24T01:40:00+00:00", "model": "gpt-5-mini",
                         "response": {k: v for k, v in live.items() if k not in ("id", "prepared")},
                         "approval": {"question": q, "verdict": "supported", "brief_mode": "llm", "brief": None, "evidence_ids": []}}}
    path = tmp_path / "answers.json"
    path.write_text(__import__("json").dumps(fake))
    monkeypatch.setattr(M, "PREPARED_PATH", path)
    p = c.post("/api/ask", json={"question": q + " "}).json()
    assert p["prepared"] == {"generated_at": "2026-09-24T01:40:00+00:00", "model": "gpt-5-mini"}
    assert c.post("/api/approve", json={"result_id": p["id"], "decision": "approved"}).json()["prepared"] is True
    assert c.post("/api/ask", json={"question": q, "live": True}).json()["prepared"] is None


def test_quality_reads_saved_files_and_feedback_starts_empty(monkeypatch, tmp_path):
    import api.main as M
    monkeypatch.setattr(M, "FEEDBACK_PATH", tmp_path / "feedback.jsonl")
    q = c.get("/api/quality").json()
    assert all(p["now"] is None or p["now"]["file"].startswith("evals/") for p in q["packs"])
    assert any(p["pack"] == "Holdout" for p in q["packs"])
    assert q["feedback"]["total"] == 0
    assert c.post("/api/useful", json={"target": "ask", "target_id": "x", "useful": False}).status_code == 422  # a reason is required
    assert c.post("/api/useful", json={"target": "plan", "target_id": "p1", "useful": False, "reason": "wrong owner"}).status_code == 200
    zero = {r: 0 for r in M.FEEDBACK_REASONS}
    assert c.get("/api/quality").json()["feedback"] == {"file": "feedback.jsonl", "total": 1, "useful": 0, "not_useful": 1, "reasons": {"wrong owner": 1},
                                                        "investigation": {"total": 0, "by_reason": zero},
                                                        "note": "Approvals are never evidence that an answer was correct: a person approves an action, not the analysis behind it."}


def test_ops_upload_validates_updates_board_and_resets(monkeypatch, tmp_path):
    import app.impact as I
    monkeypatch.setattr(I, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    I.reload()
    try:
        before = c.get("/api/board", params={"site_id": 1, "as_of": "2026-09-15"}).json()
        msn = next(t for t in before["teams"] if t["team_name"] == "Med-Surg Night")
        assert msn["status"] == "red"
        tpl = c.get("/api/ops-upload/template").text
        assert tpl.splitlines()[0] == "month,team_id,absence_days,late_doses,quits,injuries,overtime_shifts"
        bad = "month,team_id,absence_days,late_doses,quits,injuries,overtime_shifts\n2031-01,4,1,1,0,0,0\n2026-06,999,1,1,0,0,0\n2026-07,4,-2,1,0,0,0\n"
        r = c.post("/api/ops-upload", files={"file": ("x.csv", bad, "text/csv")})
        assert r.status_code == 422 and len(r.json()["detail"]["problems"]) == 3
        assert c.post("/api/ops-upload", files={"file": ("x.csv", "a,b\n1,2\n", "text/csv")}).status_code == 422
        # the client's own records say Med-Surg Night's late doses were normal in Jun-Aug
        good = "month,team_id,absence_days,late_doses,quits,injuries,overtime_shifts\n" + "".join(
            f"2026-0{m},4,8,14,0,0,4\n" for m in (6, 7, 8))
        r = c.post("/api/ops-upload", files={"file": ("ops.csv", good, "text/csv")})
        assert r.status_code == 200 and r.json()["rows"] == 3
        after = c.get("/api/board", params={"site_id": 1, "as_of": "2026-09-15"}).json()
        na = next(t for t in after["teams"] if t["team_name"] == "Med-Surg Night")
        assert na["excess_by_kpi"]["late_doses"]["observed"] == 42 and not na["excess_by_kpi"]["late_doses"]["flagged"]
        assert c.delete("/api/ops-upload").json() == {"active": False}
        back = c.get("/api/board", params={"site_id": 1, "as_of": "2026-09-15"}).json()
        assert next(t for t in back["teams"] if t["team_name"] == "Med-Surg Night")["status"] == "red"
    finally:
        I.reload()


# ---- Oct 27, 2026 round: the result carries the value tiers; /api/value carries benchmarks when the research file exists
def test_plan_result_carries_value_tiers():
    pid = "plan-lanford-med-surg-night"
    ok = c.get(f"/api/plans/{pid}/result", params={"as_of": "2026-11-30"}).json()
    assert ok["value"]["illustrative"] is True and [t["id"] for t in ok["value"]["tiers"]] == ["measured", "projected", "hospital"]
    assert ok["value"]["tiers"][2]["low"] >= 10000 and all(t["inputs"] for t in ok["value"]["tiers"])
    assert c.get(f"/api/plans/{pid}/result", params={"as_of": "2026-10-15"}).json()["value"] is None


def test_value_endpoint_has_benchmarks_field():
    v = c.get("/api/value", params={"headcount": 300}).json()
    assert "benchmarks" in v and v["low"] == 228270 and v["high"] == 588810
    assert v["benchmarks"] is None or isinstance(v["benchmarks"], list)
    assert v["benchmarks"] or v["benchmarks_note"]
