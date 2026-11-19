"""Tests for ne.viz.maps (P16)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ne.viz import maps


def test_weighted_terciles_split_residents():
    income = pd.Series([10, 20, 30, 40, 50, 60])
    pop = pd.Series([100] * 6)
    lo, hi = maps.weighted_terciles(income, pop)
    assert 20 <= lo < 30 and 40 <= hi < 50


def test_bivariate_class_index():
    noise = pd.Series([0.01, 0.10, 0.50, 0.50, np.nan])
    income = pd.Series([90, 50, 10, 90, 10])
    c = maps.bivariate_class(noise, income, noise_breaks=(0.05, 0.20), income_breaks=(30, 70))
    # x = noise class (0 low .. 2 high); y = income class (0 higher-income .. 2 lower-income)
    assert list(c[:4]) == [0 * 3 + 0, 1 * 3 + 1, 2 * 3 + 2, 0 * 3 + 2]
    assert pd.isna(c.iloc[4])


def test_palette_is_3_by_3_with_light_origin_and_dark_corner():
    assert len(maps.BIVARIATE) == 9
    assert maps.BIVARIATE[0] == "#e8e8e8"  # quiet, higher-income
    assert maps.BIVARIATE[8] == "#3b4994"  # loud, lower-income
