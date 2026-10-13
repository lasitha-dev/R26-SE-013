"""Focused synthetic tests for the frozen FMD-07B common-support builder."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError

import pytest

from components.geospatial_tracking.services.fmd_model_development_7b import (
    COMMON_SUPPORT_RULE,
    FMD07B_INTERSECTION_OF_STRUCTURALLY_SCOREABLE_ORIGINS_V1,
    CommonSupportFailClosedError,
    apply_frozen_common_support,
    build_frozen_common_support,
)
from components.geospatial_tracking.services.model_development.baseline_scoring import (
    MODEL_INPUT_INCOMPLETE,
    SCORED,
)


_CANDIDATES = {
    "FMD-EXP-01": ("EXP01:C0",),
    "FMD-EXP-02": ("EXP02:C1", "EXP02:C0"),
    "FMD-EXP-04": ("EXP04:C1", "EXP04:C0"),
}
_VALIDATION_IDS = ("O4", "O2", "O1", "O3")
_SCOREABLE = {
    ("FMD-EXP-01", "EXP01:C0"): {"O1", "O2", "O3"},
    ("FMD-EXP-02", "EXP02:C0"): {"O1", "O2", "O4"},
    ("FMD-EXP-02", "EXP02:C1"): {"O1", "O2", "O3"},
    ("FMD-EXP-04", "EXP04:C0"): {"O1", "O2", "O3", "O4"},
    ("FMD-EXP-04", "EXP04:C1"): {"O1", "O2", "O4"},
}


class _MustNotBeRead:
    def __bool__(self):
        raise AssertionError("outcome/label value was read")

    def __eq__(self, other):
        raise AssertionError("outcome/label value was compared")

    def __float__(self):
        raise AssertionError("outcome/label value was converted")


def _availability_rows(*, opaque_outcomes: bool = False) -> list[dict]:
    rows = []
    ignored_value = _MustNotBeRead() if opaque_outcomes else 999
    for (experiment_id, candidate_id), scoreable_ids in reversed(tuple(_SCOREABLE.items())):
        for origin_id in _VALIDATION_IDS:
            rows.append(
                {
                    "experiment_id": experiment_id,
                    "candidate_id": candidate_id,
                    "forecast_origin_id": origin_id,
                    "structurally_scoreable": origin_id in scoreable_ids,
                    "true_label": ignored_value,
                    "target_outcome": ignored_value,
                    "predicted_score": ignored_value,
                }
            )
    return rows


def _build_support(*, rows: list[dict] | None = None):
    return build_frozen_common_support(
        fold_id="FOLD:SYNTHETIC",
        validation_origin_ids=_VALIDATION_IDS,
        candidate_ids_by_experiment=_CANDIDATES,
        structural_availability_rows=_availability_rows() if rows is None else rows,
    )


def _prediction_rows(support) -> list[dict]:
    rows = []
    support_ids = set(support.common_support_origin_ids)
    for experiment_id, candidate_id in support.candidate_keys:
        for origin_id in support.validation_origin_ids:
            rows.append(
                {
                    "experiment_id": experiment_id,
                    "candidate_id": candidate_id,
                    "forecast_origin_id": origin_id,
                    "status": SCORED if origin_id in support_ids else MODEL_INPUT_INCOMPLETE,
                }
            )
    return rows


def test_support_construction_uses_only_structural_availability_and_intersects_every_candidate():
    ordinary = _build_support()
    opaque = _build_support(rows=_availability_rows(opaque_outcomes=True))

    assert ordinary == opaque
    assert ordinary.common_support_origin_ids == ("O1", "O2")
    assert ordinary.common_support_rule == COMMON_SUPPORT_RULE
    assert COMMON_SUPPORT_RULE == FMD07B_INTERSECTION_OF_STRUCTURALLY_SCOREABLE_ORIGINS_V1


def test_support_order_and_sha256_are_deterministic_for_reordered_inputs():
    first = _build_support()
    reordered_candidates = {
        "FMD-EXP-04": tuple(reversed(_CANDIDATES["FMD-EXP-04"])),
        "FMD-EXP-02": tuple(reversed(_CANDIDATES["FMD-EXP-02"])),
        "FMD-EXP-01": _CANDIDATES["FMD-EXP-01"],
    }
    second = build_frozen_common_support(
        fold_id="FOLD:SYNTHETIC",
        validation_origin_ids=tuple(reversed(_VALIDATION_IDS)),
        candidate_ids_by_experiment=reordered_candidates,
        structural_availability_rows=list(reversed(_availability_rows())),
    )

    expected_sha256 = hashlib.sha256(b'["O1","O2"]').hexdigest()
    assert first == second
    assert first.common_support_origin_ids == tuple(sorted(first.common_support_origin_ids))
    assert first.common_support_sha256 == second.common_support_sha256 == expected_sha256


def test_identical_frozen_support_applies_to_every_exp01_exp02_exp04_candidate():
    support = _build_support()
    applied = apply_frozen_common_support(support, prediction_rows=_prediction_rows(support))

    assert tuple(applied) == ("FMD-EXP-01", "FMD-EXP-02", "FMD-EXP-04")
    assert {
        origin_ids
        for candidates in applied.values()
        for origin_ids in candidates.values()
    } == {support.common_support_origin_ids}


@pytest.mark.parametrize("failure_mode", ("missing", "unavailable"))
def test_missing_or_unavailable_prediction_inside_frozen_support_fails_closed(failure_mode):
    support = _build_support()
    rows = _prediction_rows(support)
    target = {
        "experiment_id": "FMD-EXP-04",
        "candidate_id": "EXP04:C1",
        "forecast_origin_id": "O2",
    }
    matching = [
        row
        for row in rows
        if all(row[field] == value for field, value in target.items())
    ]
    assert len(matching) == 1
    if failure_mode == "missing":
        rows.remove(matching[0])
    else:
        matching[0]["status"] = MODEL_INPUT_INCOMPLETE

    with pytest.raises(CommonSupportFailClosedError, match="frozen common support cannot shrink"):
        apply_frozen_common_support(support, prediction_rows=rows)
    assert support.common_support_origin_ids == ("O1", "O2")


def test_frozen_support_cannot_mutate_during_or_after_application():
    support = _build_support()
    identity_before = (support.common_support_origin_ids, support.common_support_sha256)

    applied = apply_frozen_common_support(support, prediction_rows=_prediction_rows(support))
    audit_copy = support.as_dict()
    audit_copy["common_support_origin_ids"].append("O99")

    assert (support.common_support_origin_ids, support.common_support_sha256) == identity_before
    assert all(
        origin_ids is support.common_support_origin_ids
        for candidates in applied.values()
        for origin_ids in candidates.values()
    )
    with pytest.raises(FrozenInstanceError):
        support.common_support_origin_ids = ("O1",)
