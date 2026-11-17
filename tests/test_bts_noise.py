"""Tests for ne.ingest.bts_noise.

Unit tests use small synthetic rasters. Tests marked ``data`` check the real COGs and are
skipped until `python -m ne.ingest.bts_noise` has been run.
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from ne.ingest import bts_noise as bn

ALBERS = bn.TARGET_CRS


def _write(path, data, x0, y0, nodata=None, res=30.0):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs=ALBERS,
        transform=from_origin(x0, y0, res, res),
        nodata=nodata,
    ) as dst:
        dst.write(data.astype("float32"), 1)
    return path


# --- clean_block ----------------------------------------------------------------------


def test_clean_block_maps_all_nodata_flavours_to_one_value():
    raw = np.array([[3.4e38, -3.4028230607370965e38, np.nan, 55.5]], dtype="float32")
    out = bn.clean_block(raw)
    assert out.dtype == np.float32
    assert list(out[0, :3]) == [bn.NODATA] * 3
    assert out[0, 3] == pytest.approx(55.5)


def test_clean_block_keeps_valid_decibels_and_flags_impossible_ones():
    raw = np.array([[45.0, 98.2, -5.0, 250.0]], dtype="float32")
    out = bn.clean_block(raw)
    assert out[0, 0] == 45.0 and out[0, 1] == pytest.approx(98.2)
    # negative and > MAX_DB values are not real LAeq values for this map
    assert out[0, 2] == bn.NODATA and out[0, 3] == bn.NODATA


# --- naming ---------------------------------------------------------------------------


def test_source_path_tif_years():
    p = bn.source_path(2020, "road", "NY", zip_dir=bn.Path("/z"))
    assert p == (
        "/vsizip//z/CONUS_road_noise_2020.zip/"
        "CONUS_road_noise_2020/State_rasters/NY_road_noise_2020.tif"
    )


def test_source_path_2022_is_filegdb_subdataset():
    p = bn.source_path(2022, "rail", "DC", zip_dir=bn.Path("/z"))
    assert p == (
        "OpenFileGDB:/vsizip//z/CONUS_rail_noise_2022.zip/"
        "CONUS_rail_noise_2022/CONUS_rail_noise.gdb:DC_rail_noise"
    )


def test_states_in_zip_tif(tmp_path):
    import zipfile

    z = tmp_path / "CONUS_rail_noise_2018.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for name in [
            "CONUS_rail_noise_2018/State_rasters/NY_rail_noise_2018.tif",
            "CONUS_rail_noise_2018/State_rasters/NY_rail_noise_2018.tif.ovr",
            "CONUS_rail_noise_2018/State_rasters/DC_rail_noise_2018.tif",
            "CONUS_rail_noise_2018/CONUS_rail_noise_2018.Overviews/x/Ov_i03_L01_R0_C0.tif",
        ]:
            zf.writestr(name, b"")
    assert bn.states_in_zip(2018, "rail", zip_dir=tmp_path) == ["DC", "NY"]


# --- VRT mosaic -----------------------------------------------------------------------


def test_build_vrt_mosaics_aligned_states(tmp_path):
    a = _write(tmp_path / "A.tif", np.full((2, 2), 50.0), 0, 60, nodata=bn.NODATA)
    b = _write(tmp_path / "B.tif", np.full((2, 2), 70.0), 60, 30, nodata=bn.NODATA)
    vrt = bn.build_vrt([a, b], tmp_path / "m.vrt")
    with rasterio.open(vrt) as src:
        assert (src.width, src.height) == (4, 3)
        assert src.nodata == bn.NODATA
        arr = src.read(1)
    expected = np.array(
        [
            [50, 50, bn.NODATA, bn.NODATA],
            [50, 50, 70, 70],
            [bn.NODATA, bn.NODATA, 70, 70],
        ],
        dtype="float32",
    )
    np.testing.assert_array_equal(arr, expected)


def test_build_vrt_nodata_in_overlap_does_not_overwrite_neighbour(tmp_path):
    """State bounding boxes overlap; one state's nodata must not hide the other's values."""
    nd = bn.NODATA
    a = _write(tmp_path / "A.tif", np.array([[50.0, 60.0]]), 0, 30, nodata=nd)
    b = _write(tmp_path / "B.tif", np.array([[nd, 70.0]]), 30, 30, nodata=nd)  # B listed last
    vrt = bn.build_vrt([a, b], tmp_path / "m.vrt")
    with rasterio.open(vrt) as src:
        np.testing.assert_array_equal(src.read(1), np.array([[50, 60, 70]], dtype="float32"))


def test_build_vrt_rejects_misaligned_grids(tmp_path):
    a = _write(tmp_path / "A.tif", np.full((2, 2), 50.0), 0, 60)
    b = _write(tmp_path / "B.tif", np.full((2, 2), 70.0), 45, 30)  # half-cell shift
    with pytest.raises(ValueError, match="aligned"):
        bn.build_vrt([a, b], tmp_path / "m.vrt")


# --- histogram summary ----------------------------------------------------------------


def test_summarise_histogram():
    hist = np.zeros(bn.N_BINS, dtype="int64")
    for v, n in [(45.0, 2), (55.0, 1), (65.0, 1), (80.0, 1)]:
        hist[bn.bin_index(np.array([v]))[0]] += n
    s = bn.summarise_histogram(hist)
    assert s["valid_px"] == 5
    assert s["min_db"] == pytest.approx(45.0)
    assert s["max_db"] == pytest.approx(80.0, abs=bn.BIN_WIDTH)
    assert s["share_ge_55"] == pytest.approx(3 / 5)
    assert s["share_ge_65"] == pytest.approx(2 / 5)


# --- real outputs (after ingest) ------------------------------------------------------

data = pytest.mark.skipif(not bn.COG_DIR.exists(), reason="BTS COGs not built yet")


@data
@pytest.mark.parametrize(("year", "mode"), bn.LAYERS)
def test_cog_metadata(year, mode):
    cogs = sorted((bn.COG_DIR / str(year) / mode).glob("*.tif"))
    if not cogs:
        pytest.skip(f"{year} {mode} not built")
    expected_states = bn.EXPECTED_STATES.get((year, mode), 49)
    assert len(cogs) == expected_states
    for p in cogs:
        with rasterio.open(p) as src:
            assert src.crs == ALBERS
            assert src.res == pytest.approx((30.0, 30.0), rel=1e-9)
            assert src.dtypes[0] == "float32"
            assert src.nodata == bn.NODATA
            assert src.profile.get("tiled")
            assert src.overviews(1), f"{p.name} has no overviews"


@data
@pytest.mark.parametrize(("year", "mode"), bn.LAYERS)
def test_vrt_opens(year, mode):
    vrt = bn.COG_DIR / f"CONUS_{mode}_{year}.vrt"
    if not vrt.exists():
        pytest.skip(f"{vrt.name} not built")
    with rasterio.open(vrt) as src:
        assert src.crs == ALBERS
        assert src.res == pytest.approx((30.0, 30.0), rel=1e-9)


@data
def test_summary_values_in_range():
    import pandas as pd

    if not bn.SUMMARY_CSV.exists():
        pytest.skip("summary not built")
    s = pd.read_csv(bn.SUMMARY_CSV)
    assert (s["valid_px"] > 0).all()
    # BTS omits cells < 45 dB; allow float rounding just below
    assert (s["min_db"] >= 44.9).all()
    assert (s["max_db"] < bn.MAX_DB).all()
