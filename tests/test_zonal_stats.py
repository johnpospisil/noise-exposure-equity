"""Tests for ne.build.zonal_stats (synthetic rasters and blocks; P07)."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from ne.build import zonal_stats as zs

C = zs.CENSORED
T = (45, 55, 65, 70)

# --- one block from its cells ---------------------------------------------------------


def _one(values, coverage=None):
    values = np.asarray(values, dtype="float64")
    coverage = np.ones_like(values) if coverage is None else np.asarray(coverage, float)
    return zs.summarise_cells([values], [coverage], thresholds=T).iloc[0]


def test_area_shares_count_censored_cells_as_area():
    r = _one([50, C, 70, 60])
    assert r["share_ge_45"] == 0.75
    assert r["share_ge_55"] == 0.5
    assert r["share_ge_65"] == 0.25
    assert r["share_ge_70"] == 0.25
    assert r["cells"] == 4


def test_partial_coverage_weights_cells():
    r = _one([70, 50], coverage=[0.25, 1.0])
    assert r["share_ge_65"] == pytest.approx(0.2)
    assert r["cells"] == 1.25


def test_median_is_coverage_weighted():
    assert _one([50, C, 70, 60])["median_db"] == 50  # cumulative weight hits 50 % at 50
    assert _one([50, 70], coverage=[0.2, 1.0])["median_db"] == 70


def test_censored_median_is_nan():
    assert np.isnan(_one([C, C, 50])["median_db"])


def test_capped_energy_mean_uses_floor_for_censored():
    r = _one([125, C])
    assert r["emean_cap100_db"] == pytest.approx(10 * np.log10((1e10 + 10**4.5) / 2))


def test_block_with_no_cells_is_all_nan():
    r = zs.summarise_cells([np.array([])], [np.array([])], thresholds=T).iloc[0]
    assert r["cells"] == 0 and np.isnan(r["share_ge_55"]) and np.isnan(r["median_db"])


# --- blocks to block groups -----------------------------------------------------------


def _blocks():
    return pd.DataFrame(
        {
            "bg_geoid": ["A", "A", "B"],
            "pop20": [100, 300, 0],
            "cells": [3.0, 1.0, 2.0],
            "share_ge_55": [0.2, 0.6, 1.0],
            "median_db": [50.0, 60.0, 70.0],
            "emean_cap100_db": [50.0, 60.0, 70.0],
        }
    )


def test_bg_population_share_is_population_weighted():
    bg = zs.aggregate_to_bg(_blocks(), thresholds=(55,)).set_index("bg_geoid")
    assert bg.loc["A", "pop_share_ge_55"] == pytest.approx(0.5)
    assert bg.loc["A", "area_share_ge_55"] == pytest.approx((3 * 0.2 + 1 * 0.6) / 4)
    assert bg.loc["A", "pop20"] == 400


def test_bg_median_is_population_weighted_median_of_blocks():
    bg = zs.aggregate_to_bg(_blocks(), thresholds=(55,)).set_index("bg_geoid")
    assert bg.loc["A", "median_db"] == 60  # 300 of 400 residents live in the 60 dB block


def test_bg_energy_mean_is_energy_weighted():
    bg = zs.aggregate_to_bg(_blocks(), thresholds=(55,)).set_index("bg_geoid")
    expect = 10 * np.log10((100 * 1e5 + 300 * 1e6) / 400)
    assert bg.loc["A", "emean_cap100_db"] == pytest.approx(expect)


def test_bg_without_residents_has_area_share_only():
    bg = zs.aggregate_to_bg(_blocks(), thresholds=(55,)).set_index("bg_geoid")
    assert np.isnan(bg.loc["B", "pop_share_ge_55"])
    assert bg.loc["B", "area_share_ge_55"] == 1.0


def test_bg_median_censored_when_most_residents_below_45():
    b = _blocks().assign(median_db=[np.nan, np.nan, 70.0])
    bg = zs.aggregate_to_bg(b, thresholds=(55,)).set_index("bg_geoid")
    assert np.isnan(bg.loc["A", "median_db"])


# --- rasters --------------------------------------------------------------------------


def _write(path, arr, x0, y0):
    with rasterio.open(
        path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
        dtype="float32", crs=zs.CRS, transform=from_origin(x0, y0, 30, 30), nodata=-9999,
    ) as d:  # fmt: skip
        d.write(arr.astype("float32"), 1)
    return path


def test_combine_rasters_energy_sums_on_the_first_grid(tmp_path):
    road = _write(tmp_path / "road.tif", np.array([[60, 60], [-9999, -9999]]), 0, 60)
    # aviation grid shifted 10 m east: nearest neighbour keeps each cell's own value
    avi = _write(tmp_path / "avi.tif", np.array([[60, -9999], [50, -9999]]), 10, 60)
    out = zs.combine_rasters([road, avi], tmp_path / "comb.tif", bounds=(0, 0, 60, 60))
    with rasterio.open(out) as s:
        a = s.read(1)
        assert s.transform.c == 0 and s.res == (30, 30)
    assert a[0, 0] == pytest.approx(63.0103, abs=1e-3)  # 60 + 60
    assert a[0, 1] == pytest.approx(60.0)  # 60 + censored (adds nothing)
    assert a[1, 0] == pytest.approx(50.0)
    assert a[1, 1] == zs.NODATA  # both censored


def test_block_stats_from_raster(tmp_path):
    r = _write(tmp_path / "r.tif", np.array([[50, -9999], [70, 60]]), 0, 60)
    blocks = gpd.GeoDataFrame(
        {"geoid": ["b1", "b2"]},
        geometry=[box(0, 0, 60, 60), box(15, 30, 45, 60)],
        crs=zs.CRS,
    )
    out = zs.block_stats(r, blocks, thresholds=T).set_index("geoid")
    assert out.loc["b1", "share_ge_45"] == 0.75
    assert out.loc["b2", "share_ge_45"] == 0.5  # half on 50 dB, half on a censored cell
    assert out.loc["b2", "cells"] == 1.0


def test_combine_rasters_in_strips_matches_whole(tmp_path):
    rng = np.random.default_rng(0)
    a = np.where(rng.random((7, 5)) < 0.3, -9999, rng.uniform(45, 80, (7, 5)))
    b = np.where(rng.random((7, 5)) < 0.5, -9999, rng.uniform(45, 80, (7, 5)))
    ra = _write(tmp_path / "a.tif", a, 0, 210)
    rb = _write(tmp_path / "b.tif", b, 10, 205)
    bounds = (0, 0, 150, 210)
    whole = zs.combine_rasters([ra, rb], tmp_path / "w.tif", bounds, strip_rows=1000)
    strips = zs.combine_rasters([ra, rb], tmp_path / "s.tif", bounds, strip_rows=2)
    with rasterio.open(whole) as w, rasterio.open(strips) as s:
        np.testing.assert_array_equal(w.read(1), s.read(1))
        assert s.height == 7


def test_pooled_shares_weight_block_groups_by_population():
    bg = pd.DataFrame(
        {
            "year": [2022, 2022],
            "source": ["road", "road"],
            "pop20": [100, 300],
            "pop_share_ge_55": [0.4, 0.0],
        }
    )
    out = zs.pooled_shares(bg)
    assert out.loc[(2022, "road"), 55] == pytest.approx(10.0)


# --- real output ----------------------------------------------------------------------


@pytest.mark.skipif(not zs.PROCESSED.exists(), reason="zonal stats not run")
def test_processed_bg_noise():
    bg = pd.read_parquet(zs.PROCESSED)
    assert not bg.duplicated(["year", "source", "bg_geoid"]).any()
    road = bg[bg["source"] == "road"]
    assert road.groupby("year")["bg_geoid"].nunique().eq(85_392).all()
    shares = bg[[f"pop_share_ge_{t}" for t in zs.THRESHOLDS]]
    assert ((shares >= 0) & (shares <= 1 + 1e-6) | shares.isna()).all().all()
    # higher thresholds never cover more residents
    assert (shares.diff(axis=1).iloc[:, 1:].fillna(0) <= 1e-6).all().all()
    # combining sources never lowers exposure below the loudest single source. Exactly so
    # in 2022 (one grid per state); 2016-2020 aviation is resampled onto the road grid
    # (nearest neighbour, up to half a cell), which moves a few block groups slightly.
    # Blocks reaching past a state raster's edge count that strip as quiet area in the
    # combined raster only (tiny effect, hence the 1e-3 tolerance in 2022).
    w = bg.pivot_table(index=["year", "bg_geoid"], columns="source", values="pop_share_ge_55")
    gap = w[["road", "aviation"]].max(axis=1) - w["road_aviation"]
    ok = gap <= 1e-6
    assert (gap.xs(2022) <= 1e-3).all()
    assert ok.mean() > 0.995
