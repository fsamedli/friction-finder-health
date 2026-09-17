"""Deterministic parts of the agent: scope rules, suppression, numbers, brief checks, refusals.
These run without an API key (rules mode)."""
import json
from pathlib import Path

import pytest

from app import config
from app.agent import Brief, Evidence, _scope_rules, analyze, check_brief, run
from app.db import DB
from app.retrieval import Retriever

GEN = Path(__file__).resolve().parents[1] / "data" / "generated"


@pytest.fixture(scope="module")
def db():
    return DB()


@pytest.fixture(scope="module")
def retriever(db):
    return Retriever(db)


@pytest.fixture(scope="module")
def truth():
    return json.loads((GEN / "truth.json").read_text())["patterns"]


def test_scope_resolves_site_shift_team(db):
    sc = _scope_rules("Why did the Richmond night shift's scores drop?", db.sites(), db.teams())
    assert sc.site == "Richmond" and sc.shift == "Night" and sc.team == "Night A" and sc.team_id is not None
    assert sc.unknown_entities == []


def test_scope_small_team_is_not_unknown(db):
    sc = _scope_rules("Why did the Richmond Dispatch Day team's scores drop?", db.sites(), db.teams())
    assert sc.team == "Dispatch Day" and sc.unknown_entities == []


def test_scope_unknown_site_refused(db, retriever):
    res = run("Why did the Denver site drop?", db, retriever)
    assert res.status == "refused" and "Denver" in res.message


def test_scope_unsupported_metric_refused(db, retriever):
    res = run("What caused turnover on the Norfolk night shift?", db, retriever)
    assert res.status == "refused" and "turnover" in res.message.lower()


def test_analyze_numbers_match_truth(db, truth):
    sc = _scope_rules("Why did the Richmond Night A scores drop on materials and equipment?", db.sites(), db.teams())
    ev = analyze(sc, db)
    deltas = [e for e in ev if e.kind == "survey_delta" and e.value.get("item") == "q02"]
    assert deltas, "q02 evidence missing"
    v = deltas[0].value
    assert abs(v["wave1"] - truth["P1"]["wave1_mean"]) < 0.01
    assert abs(v["wave2"] - truth["P1"]["wave2_mean"]) < 0.01
    ops = [e for e in ev if e.kind == "ops_hour"][0]
    assert ops.value["hour_band"] == "06-07"
    assert abs(ops.value["after"] - truth["P3"]["late_rate_from_june"]) < 0.002


def test_small_team_is_suppressed_not_shown(db, retriever):
    res = run("Why did the Richmond Dispatch Day team's scores drop?", db, retriever)
    assert res.status == "suppressed"
    kinds = {e.kind for e in res.evidence}
    assert "suppressed" in kinds and "survey_delta" not in kinds
    assert "survey_delta_site" in kinds  # rolled up to the site


def test_reviewer_flags_mix_shift(db, retriever):
    res = run("Is the Norfolk Day B decline real or did different people respond?", db, retriever)
    mix = [e for e in res.evidence if e.kind == "tenure_mix"][0]
    assert mix.value["mix_shift"] is True


def test_check_brief_rejects_fabricated_number_and_bad_citation():
    ev = [Evidence(id="S1", kind="survey_delta", statement="Score fell from 3.73 to 2.92 (n=11 to 13).", value={"wave1": 3.73, "wave2": 2.92})]
    good = Brief(obstacle="Handoff is the supported hypothesis.", evidence_for=[{"claim": "Fell from 3.73 to 2.92.", "evidence_ids": ["S1"]}],
                 evidence_against=[], missing=[], owner="x", proposed_test="30 days", limits="synthetic")
    assert check_brief(good, ev) == []
    bad = Brief(obstacle="The root cause is the handoff; scores fell 40%.", evidence_for=[{"claim": "x", "evidence_ids": ["S9"]}],
                evidence_against=[], missing=[], owner="x", proposed_test="", limits="")
    problems = check_brief(bad, ev)
    assert any("S9" in p for p in problems)
    assert any("40" in p for p in problems)
    assert any("causal" in p for p in problems)


def test_main_question_end_to_end_fallback(db, retriever):
    res = run("Why did the Richmond night shift's scores drop and why are deliveries late?", db, retriever)
    assert res.status == "ok" and res.brief is not None
    kinds = {e.kind for e in res.evidence}
    assert {"survey_delta", "ops_hour", "staffing", "comment", "doc", "owner"} <= kinds
    assert "handoff" in res.brief.obstacle.lower()
    assert check_brief(res.brief, res.evidence) == []
    assert "Site Operations Manager" in res.brief.owner


def test_respondent_rows_never_in_evidence_sql(db, retriever):
    res = run("Why did the Richmond night shift's scores drop and why are deliveries late?", db, retriever)
    for e in res.evidence:
        if e.sql:
            assert "responses" not in e.sql.lower() and "employees" not in e.sql.lower()
