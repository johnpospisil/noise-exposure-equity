"""Smoke tests: the environment and config load."""

import numpy as np


def test_package_imports():
    import ne
    from ne import build, ingest, models, viz  # noqa: F401

    assert ne.__version__


def test_geospatial_stack_works(tmp_path):
    """rasterio writes a raster and exactextract reads stats from it."""
    import geopandas as gpd
    import rasterio
    from exactextract import exact_extract
    from rasterio.transform import from_origin
    from shapely.geometry import box

    path = tmp_path / "r.tif"
    data = np.array([[50, 60], [70, 80]], dtype="float32")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="float32",
        crs="EPSG:5070",
        transform=from_origin(0, 60, 30, 30),
    ) as dst:
        dst.write(data, 1)

    poly = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0, 0, 60, 60)], crs="EPSG:5070")
    out = exact_extract(str(path), poly, ["mean", "count"], output="pandas")
    assert out["mean"].iloc[0] == 65
    assert out["count"].iloc[0] == 4


def test_config_loads():
    from ne import config

    t = config.thresholds()
    assert t["headline_threshold_dba"] == 65
    assert t["censor_floor_dba"] == 45
    assert isinstance(config.metros(), list)
