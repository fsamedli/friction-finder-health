"""The per-process result memo: hits, copies, keys that carry costs and plan content, and reload() clearing it."""
import copy

from app import impact as I


def setup_function(_):
    I.reload()


def test_board_is_memoised_and_handed_out_as_a_copy():
    costs = I.default_costs()
    a = I.board(1, I.AS_OF_DETECT, costs)
    key = I._key("board", 1, I.AS_OF_DETECT, costs)
    assert key in I._MEMO
    a["scratch"] = 1                      # a caller's edit must not leak into the next call
    b = I.board(1, I.AS_OF_DETECT, costs)
    assert "scratch" not in b and b == I._MEMO[key]


def test_key_changes_with_costs_as_of_and_plan_content():
    costs = I.default_costs()
    other = copy.deepcopy(costs)
    other["quit"]["value"] = float(costs["quit"]["value"]) * 2
    assert I._key("why", 4, I.AS_OF_DETECT, costs) != I._key("why", 4, I.AS_OF_DETECT, other)
    assert I._key("why", 4, I.AS_OF_DETECT, costs) != I._key("why", 4, I.AS_OF_REVIEW, costs)
    plan = next(p for p in I.load_plans() if p.get("status") != "draft")
    edited = {**plan, "actions": [{**a, "status": "done"} for a in plan.get("actions", [])] + [{"text": "x", "owner": "y", "due": "2026-12-01"}]}
    assert I._key("did_all", plan, I.AS_OF_REVIEW, costs) != I._key("did_all", edited, I.AS_OF_REVIEW, costs)


def test_why_and_did_all_memoised_results_equal_fresh_ones():
    costs = I.default_costs()
    w1 = I.why(4, I.AS_OF_DETECT, costs)
    w2 = I.why(4, I.AS_OF_DETECT, costs)
    assert w1 == w2 == I._why(4, I.AS_OF_DETECT, costs)
    plan = next(p for p in I.load_plans() if p.get("status") != "draft")
    assert I.did_all(plan, I.AS_OF_REVIEW, costs) == I._did_all(plan, I.AS_OF_REVIEW, costs)


def test_reload_clears_the_memo():
    I.board(1, I.AS_OF_DETECT, I.default_costs())
    assert I._MEMO
    I.reload()
    assert not I._MEMO


def test_result_computed_across_a_reload_is_not_kept():
    def compute():
        I.reload()                        # an upload or reset lands while this result is being computed
        return {"x": 1}
    assert I._memo(("t",), compute) == {"x": 1}
    assert ("t",) not in I._MEMO
