"""Deterministic parts of the workflow: scope rules, suppression, numbers, brief checks, refusals,
the computed verdict on the red-team cases, the signal check, the site overview, the action plan,
the report, and the review log. These run without an API key (rules mode)."""
import json
from pathlib import Path

import pytest

from app import config
from app.agent import (Brief, Evidence, Assessment, _scope_rules, analyze, approve, check_brief, plan, report_html,
                       report_markdown, review_log, run)
from app.db import DB
from app.retrieval import Retriever

GEN = Path(__file__).resolve().parents[1] / "data" / "generated"
MAIN_Q = "Why did the Lanford night shift's scores drop and why are doses late?"


@pytest.fixture(scope="module")
def db():
    return DB()


@pytest.fixture(scope="module")
def retriever(db):
    return Retriever(db)


@pytest.fixture(scope="module")
def truth():
    return json.loads((GEN / "truth.json").read_text())["patterns"]


@pytest.fixture(scope="module")
def main_result(db, retriever):
    return run(MAIN_Q, db, retriever)


# ---- scope

def test_scope_resolves_site_shift_team(db):
    sc = _scope_rules("Why did the Lanford night shift's scores drop?", db.sites(), db.teams())
    assert sc.site == "Lanford" and sc.shift == "Night" and sc.team == "Med-Surg Night" and sc.team_id is not None
    assert sc.unknown_entities == []


def test_scope_small_team_is_not_unknown(db):
    sc = _scope_rules("Why did the Lanford Pharmacy Day team's scores drop?", db.sites(), db.teams())
    assert sc.team == "Pharmacy Day" and sc.unknown_entities == []
    sc2 = _scope_rules("Why did the Pine Hollow ED Day team's scores drop?", db.sites(), db.teams())
    assert sc2.site == "Pine Hollow" and sc2.team == "ED Day" and sc2.unknown_entities == []
    sc3 = _scope_rules("Why did Lanford Med Surg Night drop?", db.sites(), db.teams())   # hyphen omitted
    assert sc3.team == "Med-Surg Night" and sc3.unknown_entities == []


def test_scope_site_overview(db):
    sc = _scope_rules("Where did scores drop across Lanford?", db.sites(), db.teams())
    assert sc.intent == "site_overview" and sc.site == "Lanford" and sc.team_id is None


def test_scope_unknown_site_refused(db, retriever):
    res = run("Why did the Riverside site drop?", db, retriever)
    assert res.status == "refused" and "Riverside" in res.message


def test_scope_unsupported_metric_refused(db, retriever):
    res = run("What caused RN turnover on the Westbrook night shift?", db, retriever)
    assert res.status == "refused" and "turnover" in res.message.lower()


def test_patient_level_questions_are_declined(db, retriever):
    res = run("What were the HCAHPS scores for Lanford Med-Surg Night?", db, retriever)
    assert res.status == "refused" and "patient experience" in res.message.lower()


# ---- numbers and suppression

def test_analyze_numbers_match_truth(db, truth):
    sc = _scope_rules("Why did the Lanford Med-Surg Night scores drop on materials and equipment?", db.sites(), db.teams())
    ev = analyze(sc, db)
    deltas = [e for e in ev if e.kind == "survey_delta" and e.value.get("item") == "q02"]
    assert deltas, "q02 evidence missing"
    v = deltas[0].value
    assert abs(v["wave1"] - truth["P1"]["wave1_mean"]) < 0.01
    assert abs(v["wave2"] - truth["P1"]["wave2_mean"]) < 0.01
    assert v["material"] is True
    ops = [e for e in ev if e.kind == "ops_hour"][0]
    assert ops.value["hour_band"] == "06-07" and ops.value["signal"] is True
    assert abs(ops.value["after"] - truth["P3"]["late_rate_from_june"]) < 0.002


def test_small_team_is_suppressed_not_shown(db, retriever):
    res = run("Why did the Lanford Pharmacy Day team's scores drop?", db, retriever)
    assert res.status == "suppressed"
    kinds = {e.kind for e in res.evidence}
    assert "suppressed" in kinds and "survey_delta" not in kinds
    assert "tenure_mix" not in kinds  # who-responded breakdown is also hidden under the threshold
    assert "survey_delta_site" in kinds  # rolled up to the site
    assert res.assessment.verdict == "suppressed_insufficient"
    assert res.brief.owner.lower().startswith("not assigned")


def test_respondent_rows_never_in_evidence_sql(main_result):
    for e in main_result.evidence:
        if e.sql:
            assert "responses" not in e.sql.lower() and "employees" not in e.sql.lower()


# ---- the computed verdict

def test_main_question_is_supported_and_owned(main_result):
    res = main_result
    assert res.status == "ok" and res.brief is not None
    kinds = {e.kind for e in res.evidence}
    assert {"survey_delta", "ops_hour", "staffing", "comment_themes", "comment", "doc", "owner"} <= kinds
    a = res.assessment
    assert a.verdict == "supported" and a.theme == "restock" and a.ops_signal and a.comment_signal
    assert "restock" in res.brief.obstacle.lower()
    assert check_brief(res.brief, res.evidence, a) == []
    assert "Pharmacy Operations Manager" in res.brief.owner


def test_comment_breadth_is_counted(main_result):
    th = [e for e in main_result.evidence if e.kind == "comment_themes"][0]
    assert th.value["top_theme"] == "restock" and th.value["top_count"] >= 3 and th.value["breadth_ok"] is True
    assert th.rows and th.rows[0]["comments"] == th.value["top_count"]


def test_blip_is_insufficient_no_owner(db, retriever, truth):
    """Judge Lederman's red-team case (P9): the survey moved, nothing else did."""
    res = run("Why did the Pine Hollow ED Day team's scores drop?", db, retriever)
    a = res.assessment
    assert res.status == "ok" and a.verdict == "insufficient"
    assert a.survey_signal and not a.ops_signal and not a.comment_signal
    assert "owner" not in {e.kind for e in res.evidence}
    assert res.brief.obstacle.lower().startswith("insufficient")
    assert res.brief.owner.lower().startswith("not assigned")
    assert "no test proposed" in res.brief.proposed_test.lower()
    assert check_brief(res.brief, res.evidence, a) == []
    assert plan(res, db) is None


def test_loud_comment_is_single_source(db, retriever, truth):
    """Judge Chang's red-team case (P10): one long comment must not become the obstacle."""
    res = run("Why did the Westbrook night shift's scores drop?", db, retriever)
    a = res.assessment
    assert a.verdict in ("no_material_change", "insufficient")
    assert "pump" not in res.brief.obstacle.lower()
    assert res.brief.owner.lower().startswith("not assigned")
    th = [e for e in res.evidence if e.kind == "comment_themes"][0]
    assert th.value["top_count"] < 3 and th.value["breadth_ok"] is False
    loud = [e for e in res.evidence if e.kind == "comment" and e.value.get("words", 0) > 100]
    assert loud and "[...]" in loud[0].statement and str(truth["P10"]["comment_words"]) in loud[0].statement


def test_verdict_rule_enforced_on_model_style_brief(main_result):
    """A brief that names an owner when the verdict is not supported must fail the check."""
    a = Assessment(verdict="insufficient", label="x")
    b = Brief(obstacle="The cabinet restock is the most likely obstacle.", evidence_for=[], evidence_against=[], missing=[],
              owner="Pharmacy Operations Manager, Priya Singh", proposed_test="", limits="")
    problems = check_brief(b, main_result.evidence, a)
    assert any("insufficient" in p for p in problems) and any("owner" in p for p in problems)


# ---- signal check and site overview

def test_reviewer_flags_mix_shift_and_explains_it(db, retriever, truth):
    res = run("Is the Westbrook Telemetry Day decline real or did different people respond?", db, retriever)
    mix = [e for e in res.evidence if e.kind == "tenure_mix"][0]
    assert mix.value["mix_shift"] is True
    sig = [e for e in res.evidence if e.kind == "signal_check"][0]
    assert sig.value["verdict"] == "mix"
    assert abs(sig.value["gm_w1"] - truth["P6"]["team_mean_w1"]) < 0.02 and abs(sig.value["gm_w2"] - truth["P6"]["team_mean_w2"]) < 0.02
    assert abs(sig.value["expected_from_mix"] + sig.value["residual"] - sig.value["observed"]) < 0.02


def test_site_overview_lists_watch_items_and_suppressed_teams(db, retriever):
    res = run("Where did scores drop across Lanford?", db, retriever)
    hm = [e for e in res.evidence if e.kind == "site_heatmap"][0]
    assert any(w["team"] == "Med-Surg Night" and w["item"] == "q02" for w in hm.value["watch"])
    assert {s["team_name"] for s in hm.value["suppressed"]} >= {"Pharmacy Day", "EVS Night"}
    assert all(c["team_name"] not in {"Pharmacy Day", "EVS Night"} for c in hm.rows)
    items = [e for e in res.evidence if e.kind == "site_items"][0]
    assert items.value["strength"] and len(items.value["opportunities"]) == 2


# ---- act and review

def test_plan_only_when_supported(db, main_result):
    p = plan(main_result, db)
    assert p is not None and 3 <= len(p.actions) <= 4
    assert p.focus_item == "q02" and "06-07" in p.goal
    roles = {r["owner_role"] for r in db.run_sql("SELECT owner_role FROM ownership_directory").to_records()} | {"Team manager"}
    assert all(x["owner_role"] in roles and x["owner_name"] and x["due"] for x in p.actions)
    assert len(p.team_questions) >= 3 and "Gallup" in p.questions_source


def test_report_exports(db, main_result):
    p = plan(main_result, db)
    html = report_html(main_result, p)
    owner_name = db.run_sql("SELECT owner_name FROM ownership_directory WHERE process_name = 'Medication cabinet restocking schedule' AND site_name = 'Lanford'").rows.owner_name.iloc[0]
    assert "<svg" in html and "Verdict (computed by code)" in html and "Evidence register" in html and owner_name in html
    assert "Late doses by hour band" in html
    assert "<script" not in html  # self-contained, no external code
    md = report_markdown(main_result, p)
    assert "## Action plan" in md and "| 1 |" in md


def test_flag_and_review_log(tmp_path, monkeypatch, main_result):
    monkeypatch.setattr(config, "APPROVALS_PATH", tmp_path / "approvals.jsonl")
    approve(main_result, "flagged", "the 06-07 number looks high", who="tester")
    approve(main_result, "approved", "ok")
    log = review_log()
    assert [r["decision"] for r in log] == ["flagged", "approved"]
    assert log[0]["verdict"] == "supported" and log[0]["note"].startswith("the 06-07")


# ---- brief checks (unit)

def test_check_brief_rejects_fabricated_number_and_bad_citation():
    ev = [Evidence(id="S1", kind="survey_delta", statement="Score fell from 3.73 to 2.92 (n=11 to 13).", value={"wave1": 3.73, "wave2": 2.92})]
    good = Brief(obstacle="The cabinet restock is the supported hypothesis.", evidence_for=[{"claim": "Fell from 3.73 to 2.92.", "evidence_ids": ["S1"]}],
                 evidence_against=[], missing=[], owner="x", proposed_test="30 days", limits="synthetic")
    assert check_brief(good, ev) == []
    bad = Brief(obstacle="The root cause is the restock; scores fell 40%.", evidence_for=[{"claim": "x", "evidence_ids": ["S9"]}],
                evidence_against=[], missing=[], owner="x", proposed_test="", limits="")
    problems = check_brief(bad, ev)
    assert any("S9" in p for p in problems)
    assert any("40" in p for p in problems)
    assert any("causal" in p for p in problems)


def test_repair_citations_fixes_prefix_only_near_miss(main_result):
    """The model wrote S9 for O9 (right number, wrong prefix): repaired and recorded. A number that
    matches nothing stays wrong and still fails the check."""
    from app.agent import _repair_citations
    ids = {e.id for e in main_result.evidence}
    staffing = next(e.id for e in main_result.evidence if e.kind == "staffing")
    wrong = "S" + staffing[1:]
    assert wrong not in ids
    b = Brief(obstacle="x", evidence_for=[{"claim": "a", "evidence_ids": [wrong]}], evidence_against=[{"claim": "b", "evidence_ids": ["Z99"]}],
              missing=[], owner="x", proposed_test="", limits="")
    notes = _repair_citations(b, main_result.evidence)
    assert b.evidence_for[0]["evidence_ids"] == [staffing] and any(wrong in n for n in notes)
    assert b.evidence_against[0]["evidence_ids"] == ["Z99"]
    assert any("Z99" in p for p in check_brief(b, main_result.evidence))


def test_chat_fallback_is_grounded(main_result):
    """Without a model the follow-up chat returns evidence lines; it never invents numbers."""
    from app.agent import chat_answer, chat_context, _numbers_in
    out = chat_answer("Why is the cabinet restock the likely obstacle?", main_result)
    assert out["mode"] == "fallback" and "evidence" in out["answer"].lower()
    allowed = _numbers_in(chat_context(main_result))
    from app.agent import NUM_RE
    for m in NUM_RE.finditer(out["answer"]):
        num = m.group(1)
        assert num in allowed or num.rstrip("0").rstrip(".") in allowed
    off = chat_answer("What is the weather in Riverside?", None)
    assert "not on screen" in off["answer"].lower() or "closest evidence" in off["answer"].lower()


def test_run_sql_returns_whole_small_views(db):
    """The row cap must never truncate the reporting views (24 teams x 12 items x 2 waves = 576 rows);
    a silent LIMIT without ORDER BY made counts change between runs on Sept 17, 2026."""
    n_teams = db.run_sql("SELECT COUNT(*) AS c FROM teams").rows.c.iloc[0]
    rows = db.run_sql("SELECT team_id, item, wave_id FROM v_team_wave_item").rows
    assert len(rows) == n_teams * 12 * 2
    assert not rows.duplicated(["team_id", "item", "wave_id"]).any()


# ---- ported from Tatenda Kagande's Sept 17 commit (company-wide scope, auto-detect, no-drop exit)

def test_scope_company_wide(db):
    sc = _scope_rules("Why did the overall scores drop?", db.sites(), db.teams())
    assert sc.site == "ALL" and sc.team_id is None


def test_company_overview_has_sites_as_rows(db, retriever):
    res = run("Where did scores drop across all sites?", db, retriever)
    assert res.status == "ok" and res.scope.intent == "site_overview"
    hm = [e for e in res.evidence if e.kind == "site_heatmap"][0]
    assert hm.value["level"] == "site" and {c["team_name"] for c in hm.rows} == set(db.sites())
    si = [e for e in res.evidence if e.kind == "site_items"][0]
    assert si.value["level"] == "company" and si.value["n2"] > 100


def test_auto_detect_picks_or_asks(db, retriever):
    """A diagnosis with no site either picks the site with the clearly largest site-level fall
    (and says so) or declines with the list of sites that moved."""
    from app.agent import auto_detect_site
    picked, why = auto_detect_site(db)
    assert ("largest site-level fall" in why) if picked else ("Which site" in why)
    res = run("Why did the night shift scores drop?", db, retriever)
    if picked:
        assert res.scope.site == picked and any("largest site-level fall" in n for n in res.notes)
    else:
        assert res.status == "refused" and "Which site" in res.message


# ---------------------------------------------------------------------------------------------- v0.8 operating metrics
# Sept 24 open question 3: Ask refused absence, turnover and safety questions while the screens showed absences,
# quits and injuries. Now they are answered from the same team-month rows as the board; declines stay only for what
# the data cannot answer (a cause of a quit or an injury; a period before 2026).
def _rules_run(q, db, retriever, monkeypatch):
    from app import agent as A
    monkeypatch.setattr(config, "has_key", lambda: False)
    return A.run(q, db, retriever, fast=True)


@pytest.mark.parametrize("q,kpi", [
    ("How many unplanned absence days did Lanford Med-Surg Night have?", "absence_days"),
    ("How many quits did Lanford Med-Surg Night have?", "quits"),
    ("How many injuries did Lanford Med-Surg Night have?", "injuries"),
    ("What was the overtime count on Lanford Med-Surg Night?", "overtime_shifts"),
    ("How many late doses did Lanford Med-Surg Night have?", "late_doses"),
])
def test_operating_metric_questions_match_the_board(q, kpi, db, retriever, monkeypatch):
    from app import impact as I
    res = _rules_run(q, db, retriever, monkeypatch)
    assert res.status == "ok" and res.evidence[0].kind == "metric" and "v_team_ops_month" in res.evidence[0].sql
    e = next(t for t in I.board(1, I.AS_OF_DETECT, I.default_costs())["teams"] if t["team_id"] == 4)["excess_by_kpi"][kpi]
    assert res.evidence[0].value["events"] == e["observed"] and res.evidence[0].value["expected"] == e["expected"]
    assert "per 10 people per month" in res.message and "Jun-Aug 2026" in res.message


def test_causes_and_periods_the_data_cannot_answer_are_declined(db, retriever, monkeypatch):
    r1 = _rules_run("What caused RN turnover on the Westbrook night shift?", db, retriever, monkeypatch)
    assert r1.status == "refused" and "no exit reasons" in r1.message and "turnover" in r1.message
    r2 = _rules_run("Why are injuries happening on Lanford Med-Surg Night?", db, retriever, monkeypatch)
    assert r2.status == "refused" and "no incident causes" in r2.message
    r3 = _rules_run("How many absence days did Westbrook have in 2025?", db, retriever, monkeypatch)
    assert r3.status == "refused" and "2025" in r3.message


def test_small_team_metric_is_suppressed_and_months_parse(db, retriever, monkeypatch):
    r = _rules_run("How many injuries did Lanford EVS Night have?", db, retriever, monkeypatch)
    assert r.status == "suppressed" and not r.evidence
    j = _rules_run("How many late doses did Lanford Med-Surg Night have in July?", db, retriever, monkeypatch)
    assert j.status == "ok" and j.evidence[0].value["months"] == ["2026-07"]
    s = _rules_run("How many quits did the Westbrook night shift have from June to August?", db, retriever, monkeypatch)
    assert s.status == "ok" and s.evidence[0].value["months"] == ["2026-06", "2026-07", "2026-08"] and "teams of 4 or more" in s.message
