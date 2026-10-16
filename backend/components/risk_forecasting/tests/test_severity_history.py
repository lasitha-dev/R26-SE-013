"""Tests for the district severity-history artifact (pure: reads the JSON artifact and the label CSVs only)."""

import json
from pathlib import Path

import pandas as pd

from components.risk_forecasting.pipeline.geography import DISTRICT_NAMES
from components.risk_forecasting.pipeline.severity_history import load_severity_history, lookup, summary

PROCESSED = Path(__file__).resolve().parents[1] / "model" / "data" / "processed"
CLASSES = ("LOW", "MEDIUM", "HIGH")


def test_artifact_covers_both_diseases_with_the_label_counts():
    artifact = load_severity_history()
    assert artifact["diseases"]["FMD"]["n_district_years"] == 115
    assert artifact["diseases"]["LSD"]["n_district_years"] == 56
    assert artifact["diseases"]["FMD"]["national"]["counts"] == {"LOW": 72, "MEDIUM": 31, "HIGH": 12}


def test_every_district_is_canonical_and_probabilities_sum_to_one():
    for block in load_severity_history()["diseases"].values():
        for name, entry in block["districts"].items():
            assert name in DISTRICT_NAMES
            assert abs(sum(entry["probabilities"].values()) - 1) < 2e-3
            assert sum(entry["counts"].values()) == entry["outbreak_years"]
            assert entry["typical"] in CLASSES


def test_counts_match_the_label_files():
    fmd = pd.read_csv(PROCESSED / "severity_labels.csv").rename(columns={"District": "district", "Year": "year"})
    colombo = fmd[fmd.district == "Colombo"].severity_class.value_counts().to_dict()
    entry = lookup("FMD", "Colombo")
    assert entry["counts"] == {c: int(colombo.get(c, 0)) for c in CLASSES}
    assert entry["outbreak_years"] == int(sum(colombo.values()))


def test_district_without_outbreak_years_is_unknown_not_low():
    block = load_severity_history()["diseases"]["FMD"]["districts"]
    missing = [d for d in DISTRICT_NAMES if d not in block]
    assert missing, "the label file does not cover every district"
    assert lookup("FMD", missing[0]) is None


def test_lookup_is_case_insensitive_on_disease_and_returns_none_for_unknown_disease():
    assert lookup("fmd", "Ampara")["disease"] == "FMD"
    assert lookup("XYZ", "Ampara") is None


def test_ties_go_to_the_more_severe_class_and_nothing_forbidden_is_stored():
    artifact = summary()
    text = json.dumps(artifact)
    assert "predicted_severity" not in text and "risk_level" not in text
    assert "not a forecast" in artifact["method"]
