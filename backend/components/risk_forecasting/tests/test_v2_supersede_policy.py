"""Pure tests for the supersede policy (no database, no network, no application services)."""

from types import SimpleNamespace

from components.risk_forecasting.pipeline.supersede_policy import (
    REASON_DEPENDENCY_UNKNOWN, REASON_HAS_ADVISORY, REASON_HAS_FOLLOW_UP, REASON_WORKFLOW_STATUS, plan_supersede,
)

NONE = {"advisories": 0, "follow_ups": 0}


def rec(fid, status="GENERATED", key=None):
    return SimpleNamespace(forecast_id=fid, status=status, idempotency_key=key)


def test_unused_generated_records_may_be_superseded():
    plan = plan_supersede([rec("a"), rec("b")], ["new-1"], {"a": NONE, "b": NONE})
    assert plan.to_supersede == ["a", "b"] and plan.protected == [] and plan.kept == []


def test_records_with_advisories_or_follow_ups_are_protected():
    plan = plan_supersede(
        [rec("adv"), rec("fu"), rec("both"), rec("free")], [],
        {"adv": {"advisories": 2, "follow_ups": 0}, "fu": {"advisories": 0, "follow_ups": 1},
         "both": {"advisories": 1, "follow_ups": 1}, "free": NONE})
    assert plan.to_supersede == ["free"]
    by_id = {p["forecast_id"]: p["reasons"] for p in plan.protected}
    assert by_id["adv"] == [REASON_HAS_ADVISORY]
    assert by_id["fu"] == [REASON_HAS_FOLLOW_UP]
    assert by_id["both"] == [REASON_HAS_ADVISORY, REASON_HAS_FOLLOW_UP]


def test_workflow_statuses_are_protected_even_without_dependents():
    plan = plan_supersede([rec("x", "AVAILABLE"), rec("y", "REFERENCED")], [], {"x": NONE, "y": NONE})
    assert plan.to_supersede == []
    assert {p["forecast_id"]: p["reasons"] for p in plan.protected} == {
        "x": [REASON_WORKFLOW_STATUS], "y": [REASON_WORKFLOW_STATUS]}


def test_unknown_dependencies_fail_closed():
    plan = plan_supersede([rec("a"), rec("b")], [], {"a": None})  # b missing from the mapping entirely
    assert plan.to_supersede == []
    assert all(p["reasons"] == [REASON_DEPENDENCY_UNKNOWN] for p in plan.protected)
    assert {p["forecast_id"] for p in plan.protected} == {"a", "b"}


def test_reused_and_already_superseded_records_are_left_alone():
    plan = plan_supersede(
        [rec("reused", key="v2|FMD|Kandy|2026-10|fmd_v2.0"), rec("gone", "SUPERSEDED"), rec("old")],
        ["v2|FMD|Kandy|2026-10|fmd_v2.0"], {"reused": NONE, "gone": NONE, "old": NONE})
    assert plan.kept == ["reused"]
    assert plan.to_supersede == ["old"]
    assert plan.protected == []


def test_summary_counts_and_reasons():
    plan = plan_supersede([rec("a"), rec("b"), rec("c", "AVAILABLE")], [],
                          {"a": NONE, "b": {"advisories": 1, "follow_ups": 0}, "c": {"advisories": 1, "follow_ups": 0}})
    summary = plan.summary()
    assert summary["would_supersede"] == 1 and summary["protected"] == 2
    assert summary["protected_reasons"] == {REASON_HAS_ADVISORY: 2, REASON_WORKFLOW_STATUS: 1}
