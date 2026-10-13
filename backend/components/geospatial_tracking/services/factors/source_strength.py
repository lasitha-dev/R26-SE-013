"""Checkpoint 6D Part 18: source strength remains undefined.

`source_strength_factor` is NEVER derived from `affected_animals`, case
count, deaths, DQS, GPS quality, ST cluster role, cluster size, or
report frequency — this module has no such parameter to derive it
from. A future equal-source baseline may be evaluated explicitly in a
later checkpoint, but 6D must not present a fixture value as a learned
or biological source strength.
"""

from __future__ import annotations

from .contracts import NOT_YET_SCIENTIFICALLY_DEFINED, TransformedFactorProvenance


def build_source_strength_status(*, source_id: str) -> TransformedFactorProvenance:
    return TransformedFactorProvenance(
        factor_or_component_name="source_strength_factor", raw_feature_names=(), raw_values=(), raw_units=(),
        raw_feature_statuses=(), source_dataset_versions=(), feature_snapshot_id=None, transform_id=None,
        transform_config_hash=None, reference_profile_hash=None, transformed_value=None,
        candidate_status=NOT_YET_SCIENTIFICALLY_DEFINED, clipping=None,
        notes=f"real source_strength_factor for {source_id!r} is not scientifically defined -- never derived "
              "from affected_animals/case count/deaths/DQS/GPS quality/ST cluster role/cluster size/report "
              "frequency (6D Part 18)",
    )
