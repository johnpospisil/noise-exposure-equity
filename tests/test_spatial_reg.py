"""Tests for ne.models.spatial_reg (P11)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from ne.models import spatial_reg as sr


def _grid(n=3, metros=("A", "B")):
    """n x n unit squares per metro, metros side by side (they touch along one edge)."""
    rows = []
    for m, metro in enumerate(metros):
        for i in range(n):
            for j in range(n):
                x0 = m * n + i
                rows.append({"bg_geoid": f"{metro}{i}{j}", "cbsa": metro,
                             "geometry": box(x0, j, x0 + 1, j + 1)})  # fmt: skip
    return gpd.GeoDataFrame(rows, crs="EPSG:3857")


def test_queen_weights_stay_within_metro():
    g = _grid()
    w = sr.within_metro_weights(g)
    ids = list(g["bg_geoid"])
    for i, nbrs in w.neighbors.items():
        assert all(g.loc[j, "cbsa"] == g.loc[i, "cbsa"] for j in nbrs)
    # the corner square of metro A that touches metro B keeps only its 3 A-neighbours
    assert len(w.neighbors[ids.index("A20")]) == 3
    assert w.transform == "R"


def test_design_matrix_specs():
    df = pd.DataFrame(
        {
            "income_quintile": pd.array([1, 2, 3, 4, 5, 1], dtype="Int8"),
            "cbsa": ["A", "A", "A", "B", "B", "B"],
            "pct_nh_black": [0.1] * 6,
            "pct_hispanic": [0.2] * 6,
            "pct_nh_asian": [0.0] * 6,
            "pct_other": [0.0] * 6,
            "pct_renter": [0.5] * 6,
            "density": [1000.0] * 6,
        }
    )
    xa = sr.design(df, "A")
    assert list(xa.columns) == ["Q1", "Q2", "Q3", "Q4", "metro_B"]  # Q5 and metro A omitted
    xc = sr.design(df, "C")
    assert {"black_10pp", "hispanic_10pp", "renter_10pp", "log_density"} <= set(xc.columns)
    assert xc["black_10pp"].iloc[0] == pytest.approx(1.0)  # 10 % -> one 10-point step


def test_spatial_lag_model_recovers_rho():
    # y = rho W y + 2 x + e on a 20 x 20 lattice with rho = 0.5
    rng = np.random.default_rng(1)
    g = _grid(n=20, metros=("A",))
    w = sr.within_metro_weights(g)
    n = len(g)
    W = w.sparse.toarray()
    x = rng.normal(size=(n, 1))
    y = np.linalg.solve(np.eye(n) - 0.5 * W, 2 * x[:, 0] + rng.normal(scale=0.5, size=n))
    res = sr.fit_lag(y.reshape(-1, 1), x, w, ["x"])
    assert res["rho"] == pytest.approx(0.5, abs=0.1)
    assert res["coef"]["x"] == pytest.approx(2.0, abs=0.15)


def test_pooled_lag_with_metro_fixed_effects_recovers_rho():
    # two metros with very different intercepts; FE by within-metro demeaning
    rng = np.random.default_rng(2)
    g = _grid(n=15, metros=("A", "B"))
    w = sr.within_metro_weights(g)
    n = len(g)
    W = w.sparse.toarray()
    x = rng.normal(size=n)
    alpha = np.where(g["cbsa"] == "A", 0.0, 10.0)
    y = np.linalg.solve(np.eye(n) - 0.4 * W, alpha * (1 - 0.4) + 1.5 * x
                        + rng.normal(scale=0.5, size=n))  # fmt: skip
    xdf = pd.DataFrame({"x": x, "metro_B": (g["cbsa"] == "B").astype(float)})
    res = sr.fit_lag_fe(y, xdf, w, g["cbsa"])
    assert res["rho"] == pytest.approx(0.4, abs=0.1)
    assert res["coef"]["x"] == pytest.approx(1.5, abs=0.15)
    assert "metro_B" not in res["coef"]
