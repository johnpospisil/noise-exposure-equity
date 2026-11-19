"""Tests for ne.models.complaints_nb (P13)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ne.models import complaints_nb as cnb


def test_tract_years_sums_months_and_drops_partial_year():
    p = pd.DataFrame(
        {
            "tract": ["T1"] * 4,
            "month": pd.to_datetime(["2024-01-01", "2024-02-01", "2025-03-01", "2026-01-01"]),
            "noise_group": ["street"] * 4,
            "complaints": [3, 2, 1, 9],
            "location_days": [2, 2, 1, 9],
        }
    )
    ty = cnb.tract_years(p, years=(2016, 2025))
    assert list(ty["year"]) == [2024, 2025]  # 2026 is incomplete
    assert ty.loc[ty["year"] == 2024, "location_days"].item() == 4


def test_negative_binomial_recovers_rate_ratio_with_offset():
    # log E[y] = log(pop) + log(0.01) + 0.3 * noise_10 + 0.5 * gentrifying
    rng = np.random.default_rng(3)
    n = 4000
    d = pd.DataFrame(
        {
            "pop20": rng.integers(500, 5000, n),
            "noise_10": rng.uniform(0, 8, n),
            "gent": rng.integers(0, 2, n),
            "tract": np.repeat(np.arange(n // 4), 4),
        }
    )
    mu = d["pop20"] * 0.01 * np.exp(0.3 * d["noise_10"] + 0.5 * d["gent"])
    alpha = 0.5
    d["y"] = rng.negative_binomial(1 / alpha, 1 / (1 + alpha * mu))
    res = cnb.fit_nb(d, "y ~ noise_10 + gent")
    irr = res["irr"]
    assert irr["noise_10"] == pytest.approx(np.exp(0.3), rel=0.05)
    assert irr["gent"] == pytest.approx(np.exp(0.5), rel=0.08)
    assert res["alpha"] == pytest.approx(alpha, rel=0.2)
