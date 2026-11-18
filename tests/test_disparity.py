"""Tests for ne.models.disparity (P10)."""

from __future__ import annotations

import pandas as pd
import pytest

from ne.models import disparity as dp


def _bg():
    # two block groups in one metro: a poor, mostly Black, loud one and a rich, mostly White,
    # quiet one
    return pd.DataFrame(
        {
            "cbsa": ["A", "A"],
            "metro": ["Alpha", "Alpha"],
            "year": [2022, 2022],
            "source": ["all", "all"],
            "pop20": [1000, 3000],
            "income_quintile": pd.array([1, 5], dtype="Int8"),
            "pct_nh_white": [0.2, 0.8],
            "pct_nh_black": [0.8, 0.0],
            "pct_hispanic": [0.0, 0.1],
            "pct_nh_asian": [0.0, 0.1],
            "pct_other": [0.0, 0.0],
            "pop_share_ge_55": [0.5, 0.1],
            "pop_share_ge_65": [0.2, 0.0],
        }
    )


def test_exposure_by_income_quintile():
    t = dp.exposure(_bg(), "income").set_index("group")
    assert t.loc["Q1 (lowest)", "pct_ge_55"] == pytest.approx(50.0)
    assert t.loc["Q5 (highest)", "pct_ge_55"] == pytest.approx(10.0)
    assert t.loc["Q1 (lowest)", "residents"] == 1000


def test_exposure_by_race_weights_by_group_residents():
    t = dp.exposure(_bg(), "race").set_index("group")
    # White residents: 200 in the loud BG, 2400 in the quiet one
    assert t.loc["White", "pct_ge_55"] == pytest.approx(100 * (200 * 0.5 + 2400 * 0.1) / 2600)
    assert t.loc["Black", "pct_ge_55"] == pytest.approx(50.0)
    assert t.loc["Black", "residents"] == pytest.approx(800)


def test_exposure_keeps_grouping_columns():
    t = dp.exposure(_bg(), "income", by=("metro", "source"))
    assert {"metro", "source", "group"} <= set(t.columns)


def test_ratio_to_reference_group():
    t = dp.exposure(_bg(), "income")
    r = dp.ratios(t, reference="Q5 (highest)", value="pct_ge_55")
    assert r.set_index("group").loc["Q1 (lowest)", "ratio"] == pytest.approx(5.0)


def test_missing_quintile_rows_are_left_out_of_income_table():
    bg = _bg()
    bg.loc[1, "income_quintile"] = pd.NA
    t = dp.exposure(bg, "income")
    assert list(t["group"]) == ["Q1 (lowest)"]
