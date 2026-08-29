"""Checkpoint FMD-09: freeze-verification smoke check.

Not a pytest suite. Re-reads the real, already-persisted
`local_data/processed/fmd/model_development/fmd10a_corrected_selection/fmd07b_frozen_model_spec.json`
and `local_data/processed/fmd/model_evaluation/fmd10b_corrected_heldout/fmd08_manifest.json`
and confirms they still match the literal constants promoted into
`services/model_development/fmd_frozen_model_9.py`. The runtime API path
never performs this re-read itself (10A-FIREWALL-01-equivalent); this
script is how a human/CI re-verifies the promoted constants have not
drifted from the tracked evaluation evidence.

FMD-10B: re-pointed at the corrected (post fold-retention-fix) evidence
directories. The original `fmd07b_frozen_model_spec.json` /
`local_data/processed/fmd/model_evaluation/fmd08/fmd08_manifest.json`
remain preserved, unmodified, as PRE_CORRECTION_HELDOUT_EVALUATION
historical evidence -- they are simply no longer what this freeze check
verifies against. Run directly:

    python -m components.geospatial_tracking.smoke_tests.run_fmd09_freeze_verification
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

from ..services.model_development.fmd_frozen_model_9 import (
    FROZEN_MODEL_SPEC_SHA256_FMD09,
    FROZEN_THRESHOLD_FMD09,
    HELD_OUT_PREDICTIONS_SHA256_FMD08,
    SELECTED_CANDIDATE_ID_FMD09,
)


class Fmd09FreezeDriftError(RuntimeError):
    """The tracked `fmd_frozen_model_9.py` constants no longer match the
    real, on-disk FMD-07B/FMD-08 evaluation evidence."""


def main() -> int:
    spec_path = REPO_ROOT / "local_data/processed/fmd/model_development/fmd10a_corrected_selection/fmd07b_frozen_model_spec.json"
    manifest_path = REPO_ROOT / "local_data/processed/fmd/model_evaluation/fmd10b_corrected_heldout/fmd08_manifest.json"

    spec_bytes = spec_path.read_bytes()
    spec = json.loads(spec_bytes.decode("utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    observed_spec_sha256 = hashlib.sha256(spec_bytes).hexdigest()

    checks = {
        "selected_candidate_id": (spec.get("selected_candidate_id"), SELECTED_CANDIDATE_ID_FMD09),
        "threshold": (spec.get("threshold"), FROZEN_THRESHOLD_FMD09),
        "frozen_model_spec_sha256 (manifest-recorded)": (manifest.get("frozen_model_spec_sha256"), FROZEN_MODEL_SPEC_SHA256_FMD09),
        "frozen_model_spec_sha256 (observed, recomputed)": (observed_spec_sha256, FROZEN_MODEL_SPEC_SHA256_FMD09),
        "predictions_sha256": (manifest.get("predictions_sha256"), HELD_OUT_PREDICTIONS_SHA256_FMD08),
    }

    drift = {name: (real, frozen) for name, (real, frozen) in checks.items() if real != frozen}
    if drift:
        raise Fmd09FreezeDriftError(f"fmd_frozen_model_9.py has drifted from on-disk evidence: {drift}")

    print("FMD-09 freeze verification: PASS -- all promoted constants match on-disk FMD-07B/FMD-08 evidence.")
    for name, (real, _frozen) in checks.items():
        print(f"  {name}: {real}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
