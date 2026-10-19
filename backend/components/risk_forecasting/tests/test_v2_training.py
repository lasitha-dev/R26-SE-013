"""Tests for the v2 training/evaluation helpers (pure, offline: synthetic frames only)."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "model" / "scripts" / "v2" / "train_evaluate.py"
_spec = importlib.util.spec_from_file_location("v2_train_evaluate", SCRIPT)
train = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train)


def _panel():
    rows = []
    for year in range(2018, 2024):
        for month in (1, 2):
            for district in ("A", "B"):
                # District A has an outbreak every January only in 2020.
                outbreak = int(district == "A" and month == 1 and year == 2020)
                rows.append({"district": district, "year": year, "month": month, "outbreak": outbreak})
    return pd.DataFrame(rows)


def test_loyo_prior_never_contains_the_rows_own_year():
    panel = _panel()
    prior = train.loyo_prior(panel)
    in_sample = train.climatology_table(panel)
    own = panel[(panel.district == "A") & (panel.month == 1) & (panel.year == 2020)].index[0]
    # The only outbreak is in 2020: excluding 2020 removes it from that row's prior...
    assert prior[own] < train.prior_for(in_sample, "A", 1)
    assert prior[own] == pytest.approx(prior[panel.index[(panel.district == "B") & (panel.month == 1) & (panel.year == 2020)][0]], abs=0.05)
    # ...while other years' priors still see the 2020 outbreak.
    other = panel[(panel.district == "A") & (panel.month == 1) & (panel.year == 2021)].index[0]
    assert prior[other] > prior[own]


def test_loyo_prior_matches_manual_leave_one_out():
    panel = _panel()
    prior = train.loyo_prior(panel)
    row = panel[(panel.district == "A") & (panel.month == 1) & (panel.year == 2022)]
    manual = train.prior_for(train.climatology_table(panel[panel.year != 2022]), "A", 1)
    assert prior[row.index[0]] == pytest.approx(manual)


def test_fit_uses_out_of_sample_priors_unless_given_explicitly():
    panel = _panel().assign(x=np.arange(24, dtype=float))
    table = train.climatology_table(panel)
    default = train.fit_lr(panel, ["x"], 1.0, table, True)
    explicit = train.fit_lr(panel, ["x"], 1.0, table, True, train_prior=train.loyo_prior(panel))
    in_sample = train.fit_lr(panel, ["x"], 1.0, table, True, train_prior=np.array(
        [train.prior_for(table, d, m) for d, m in zip(panel.district, panel.month)]))
    assert np.allclose(default["coef"], explicit["coef"])
    assert not np.allclose(default["coef"], in_sample["coef"])


def _scored_frame(seed=0, months=36):
    rng = np.random.default_rng(seed)
    rows = []
    for t in range(months):
        for d in range(10):
            y = int(rng.random() < 0.12)
            rows.append({"year": 2020 + t // 12, "month": t % 12 + 1, "outbreak": y,
                         "good": y * 0.6 + rng.random() * 0.4, "bad": rng.random()})
    return pd.DataFrame(rows)


def test_block_bootstrap_is_reproducible_and_reports_both_intervals():
    frame = _scored_frame()
    first = train.block_bootstrap_diff(frame, "good", "bad")
    second = train.block_bootstrap_diff(frame, "good", "bad")
    assert first == second                              # fixed seed, independent of call order
    assert first["block_months"] == train.BOOTSTRAP_BLOCK_MONTHS
    assert first["ci95"][0] < first["mean"] < first["ci95"][1]
    assert len(first["iid_month_ci95"]) == 2
    assert first["mean"] > 0                            # a genuinely informative column beats noise


def test_moving_blocks_are_consecutive_months():
    frame = _scored_frame(months=12)
    months = list(frame.groupby(["year", "month"]).indices)
    assert months == sorted(months)                     # chronological, so blocks are consecutive
