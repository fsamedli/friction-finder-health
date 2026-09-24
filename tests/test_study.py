"""Usability kit: SUS scoring follows Brooke (1996); the study log starts empty and validates input."""
from fastapi.testclient import TestClient

from scripts.score_study import score, sus_score


def test_sus_extremes():
    assert sus_score([5, 1] * 5) == 100.0   # best: agree with odd items, disagree with even items
    assert sus_score([1, 5] * 5) == 0.0
    assert sus_score([3] * 10) == 50.0


def test_score_task_times():
    recs = [{"participant": "P1", "event": "task_start", "task": 1, "ts": "2026-09-24T10:00:00.000+00:00"},
            {"participant": "P1", "event": "task_finish", "task": 1, "success": True, "ts": "2026-09-24T10:01:30.500+00:00"},
            {"participant": "P1", "event": "sus", "answers": [4, 2] * 5, "ts": "2026-09-24T10:10:00.000+00:00"}]
    s = score(recs)
    assert s["participants"]["P1"]["tasks"][1]["seconds"] == 90.5 and s["sus_mean"] == 75.0


def test_study_endpoint_validates(monkeypatch, tmp_path):
    import api.main as M
    monkeypatch.setattr(M, "STUDY_PATH", tmp_path / "study.jsonl")
    c = TestClient(M.app)
    assert c.post("/api/study", json={"participant": "Bob", "event": "task_start", "task": 1}).status_code == 422
    assert c.post("/api/study", json={"participant": "P1", "event": "sus", "answers": [3] * 9}).status_code == 422
    assert c.post("/api/study", json={"participant": "P1", "event": "task_start", "task": 1}).status_code == 200
    assert len((tmp_path / "study.jsonl").read_text().splitlines()) == 1
