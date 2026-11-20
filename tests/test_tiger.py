"""Tests for ne.ingest.tiger (clean-clone behaviour found in P19)."""

from __future__ import annotations

import zipfile

import geopandas as gpd
from shapely.geometry import box

from ne.ingest import tiger


def test_build_cbsa_creates_output_folder_on_a_fresh_clone(tmp_path, monkeypatch):
    # a tiny stand-in for tl_2020_us_cbsa.zip
    shp = tmp_path / "shp"
    shp.mkdir()
    gpd.GeoDataFrame(
        {"GEOID": ["35620", "99999"], "NAME": ["New York", "Elsewhere"]},
        geometry=[box(0, 0, 1, 1), box(2, 2, 3, 3)],
        crs="EPSG:4269",
    ).to_file(shp / "cbsa.shp")
    z = tmp_path / "cbsa.zip"
    with zipfile.ZipFile(z, "w") as f:
        for p in shp.iterdir():
            f.write(p, p.name)
    monkeypatch.setattr(tiger, "download", lambda url, dest: z)
    out = tmp_path / "interim" / "census"  # does not exist yet, as in a fresh clone
    monkeypatch.setattr(tiger, "OUT", out)

    g = tiger.build_cbsa([{"cbsa": "35620"}])

    assert (out / "cbsa_2020.parquet").exists()
    assert g["cbsa"].tolist() == ["35620"]
