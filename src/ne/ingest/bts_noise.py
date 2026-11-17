"""Ingest the BTS National Transportation Noise Map (CONUS) into Cloud-Optimised GeoTIFFs.

Inputs are the zips listed in ``config/bts_sources.yaml``, downloaded by hand into
``data/raw/bts/zips/`` (bts.gov blocks scripted downloads). Nothing is unzipped:

* 2016, 2018, 2020: one GeoTIFF per state in ``State_rasters/``, read through ``/vsizip/``.
* 2022: one raster per state inside an Esri File Geodatabase, read through GDAL's
  OpenFileGDB raster driver. rasterio's bundled GDAL lacks that driver, so each 2022 state is
  first copied to a temporary GeoTIFF with the system ``gdal_translate`` (``brew install gdal``).

We use the per-state rasters, not the ArcGIS mosaic datasets, so BTS's mosaic "repair" steps
are not needed. Neighbouring state rasters never both hold a value in the same cell (checked
in P03), so each block group is measured on its own state's raster. 2016-2020 states share
one 30 m grid snapped to multiples of 30 m; 2022 states each have their own grid origin.

Outputs (all git-ignored):

* ``data/raw/bts/manifest.csv``: file, size, sha256 of every zip.
* ``data/interim/bts/cog/{year}/{mode}/{ST}.tif``: one COG per state, float32 LAeq,24h dB,
  nodata = NODATA. Overviews use nearest-neighbour resampling, never averaging (decibels are
  not averaged arithmetically) and are for display only; analysis reads full resolution.
* ``data/interim/bts/cog/CONUS_{mode}_{year}.vrt``: CONUS mosaic of the state COGs, for maps
  only (see ``build_layer_vrt``).
* ``data/interim/bts/raster_summary.csv``: per-state metadata and value checks.

Usage::

    uv run python -m ne.ingest.bts_noise                      # everything, resumable
    uv run python -m ne.ingest.bts_noise --years 2022 --modes road --states RI
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
import pandas as pd
import rasterio
import rasterio.shutil
from pyproj import CRS as ProjCRS
from rasterio.crs import CRS
from rasterio.windows import Window

from ne import config

# --- constants ------------------------------------------------------------------------

SOURCES = config.load_yaml("bts_sources")
ZIP_DIR = config.ROOT / SOURCES["local_dir"]
MANIFEST_CSV = config.RAW_DIR / "bts" / "manifest.csv"
OUT_DIR = config.INTERIM_DIR / "bts"
COG_DIR = OUT_DIR / "cog"
SUMMARY_CSV = OUT_DIR / "raster_summary.csv"

#: USA Contiguous Albers Equal Area Conic (USGS), NAD83: the CRS of every BTS CONUS raster.
TARGET_CRS = CRS.from_string("ESRI:102039")
RES = 30.0
NODATA = -9999.0
#: Anything above this is not a plausible LAeq,24h value and is treated as nodata.
MAX_DB = 150.0
BINS_PER_DB = 10
BIN_WIDTH = 1 / BINS_PER_DB
N_BINS = int(MAX_DB * BINS_PER_DB) + 1
STRIP_ROWS = 512

#: (year, mode) pairs, in config order.
LAYERS: list[tuple[int, str]] = [
    (int(y), m) for y, modes in SOURCES["layers"].items() for m in modes
]
#: State counts that differ from 48 + DC.
EXPECTED_STATES = {(2018, "rail"): 47}


# --- naming ---------------------------------------------------------------------------


def zip_path(year: int, mode: str, zip_dir: Path = ZIP_DIR) -> Path:
    return Path(zip_dir) / f"CONUS_{mode}_noise_{year}.zip"


def source_path(year: int, mode: str, state: str, zip_dir: Path = ZIP_DIR) -> str:
    """GDAL path of one state's raster inside its zip."""
    z = zip_path(year, mode, zip_dir)
    if year >= 2022:
        gdb = f"CONUS_{mode}_noise_{year}/CONUS_{mode}_noise.gdb"
        return f"OpenFileGDB:/vsizip/{z}/{gdb}:{state}_{mode}_noise"
    tif = f"CONUS_{mode}_noise_{year}/State_rasters/{state}_{mode}_noise_{year}.tif"
    return f"/vsizip/{z}/{tif}"


def states_in_zip(year: int, mode: str, zip_dir: Path = ZIP_DIR) -> list[str]:
    """State codes available for a layer, read from the zip listing or the gdb."""
    z = zip_path(year, mode, zip_dir)
    if year >= 2022:
        gdb = f"/vsizip/{z}/CONUS_{mode}_noise_{year}/CONUS_{mode}_noise.gdb"
        out = subprocess.run(
            [_gdal("gdalinfo"), gdb], capture_output=True, text=True, check=True
        ).stdout
        pat = rf":([A-Z]{{2}})_{mode}_noise\s*$"
        return sorted({m.group(1) for m in re.finditer(pat, out, re.M)})
    pat = re.compile(rf"/State_rasters/([A-Z]{{2}})_{mode}_noise_{year}\.tif$")
    with zipfile.ZipFile(z) as zf:
        return sorted({m.group(1) for n in zf.namelist() if (m := pat.search(n))})


def cog_path(year: int, mode: str, state: str) -> Path:
    return COG_DIR / str(year) / mode / f"{state}.tif"


def _gdal(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise RuntimeError(
            f"`{tool}` not found. 2022 BTS rasters are in a File Geodatabase and need a full "
            "GDAL install (macOS: `brew install gdal`)."
        )
    return path


# --- value handling -------------------------------------------------------------------


def clean_block(raw: np.ndarray) -> np.ndarray:
    """Map every nodata flavour (±3.4e38, NaN, impossible values) to NODATA."""
    out = raw.astype("float32", copy=True)
    bad = ~np.isfinite(out) | (out < 0) | (out > MAX_DB)
    out[bad] = NODATA
    return out


def bin_index(values: np.ndarray) -> np.ndarray:
    """0.1 dB histogram bin of each value (bin i covers [i/10, (i+1)/10))."""
    idx = np.floor(values.astype("float64") * BINS_PER_DB + 1e-6).astype("int64")
    return np.clip(idx, 0, N_BINS - 1)


def summarise_histogram(hist: np.ndarray, thresholds=(45, 55, 65, 70)) -> dict:
    """Pixel-count summary from a 0.1 dB histogram (QA only: shares of cells, not people)."""
    n = int(hist.sum())
    out: dict = {"valid_px": n}
    if n == 0:
        return out | {"min_db": np.nan, "p50_db": np.nan, "max_db": np.nan}
    nz = np.flatnonzero(hist)
    cum = np.cumsum(hist)
    out["min_db"] = nz[0] * BIN_WIDTH
    out["p50_db"] = int(np.searchsorted(cum, n / 2)) * BIN_WIDTH
    out["max_db"] = nz[-1] * BIN_WIDTH
    for t in thresholds:
        out[f"share_ge_{t}"] = hist[bin_index(np.array([t]))[0] :].sum() / n
    return out


def _same_crs(crs: CRS) -> bool:
    a = ProjCRS.from_wkt(crs.to_wkt())
    b = ProjCRS.from_wkt(TARGET_CRS.to_wkt())
    if a.equals(b, ignore_axis_order=True):
        return True
    keys = ("proj", "lat_0", "lon_0", "lat_1", "lat_2", "x_0", "y_0")
    pa, pb = a.to_dict(), b.to_dict()
    return all(pa.get(k) == pb.get(k) for k in keys) and a.datum.name == b.datum.name


# --- conversion -----------------------------------------------------------------------


def convert_state(year: int, mode: str, state: str, overwrite: bool = False) -> dict:
    """Convert one state raster to a COG and return its summary row (cached as JSON)."""
    dst = cog_path(year, mode, state)
    sidecar = dst.with_suffix(".json")
    if dst.exists() and sidecar.exists() and not overwrite:
        return json.loads(sidecar.read_text())

    dst.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src_path = source_path(year, mode, state)
    hist = np.zeros(N_BINS, dtype="int64")
    n_flagged = 0

    with tempfile.TemporaryDirectory(dir=OUT_DIR) as tmp:
        tmp = Path(tmp)
        if year >= 2022:  # FileGDB raster -> plain GeoTIFF with the system GDAL
            staged = tmp / "staged.tif"
            subprocess.run(
                [
                    _gdal("gdal_translate"), "-q", "-of", "GTiff",
                    "-co", "TILED=YES", "-co", "COMPRESS=DEFLATE", "-co", "PREDICTOR=3",
                    "-co", "BIGTIFF=IF_SAFER", src_path, str(staged),
                ],
                check=True,
            )  # fmt: skip
            src_path = str(staged)

        cleaned = tmp / "cleaned.tif"
        with rasterio.open(src_path) as src:
            if not _same_crs(src.crs):
                raise ValueError(f"{year} {mode} {state}: unexpected CRS {src.crs}")
            if tuple(round(r, 6) for r in src.res) != (RES, RES):
                raise ValueError(f"{year} {mode} {state}: unexpected resolution {src.res}")
            src_nodata = src.nodata
            profile = {
                "driver": "GTiff",
                "height": src.height,
                "width": src.width,
                "count": 1,
                "dtype": "float32",
                "crs": TARGET_CRS,
                "transform": src.transform,
                "nodata": NODATA,
                "tiled": True,
                "blockxsize": 512,
                "blockysize": 512,
                "compress": "DEFLATE",
                "predictor": 3,
                "BIGTIFF": "IF_SAFER",
            }
            with rasterio.open(cleaned, "w", **profile) as out:
                for row in range(0, src.height, STRIP_ROWS):
                    win = Window(0, row, src.width, min(STRIP_ROWS, src.height - row))
                    raw = src.read(1, window=win)
                    block = clean_block(raw)
                    valid = block != NODATA
                    # count finite, non-sentinel values we had to drop (should be ~0)
                    sentinel = np.isclose(np.abs(raw), 3.4028e38, rtol=1e-3)
                    if src_nodata is not None and np.isfinite(src_nodata):
                        sentinel |= raw == src_nodata
                    n_flagged += int((~valid & np.isfinite(raw) & ~sentinel).sum())
                    if valid.any():
                        hist += np.bincount(bin_index(block[valid]), minlength=N_BINS)
                    out.write(block, 1, window=win)
            meta = {
                "width": src.width,
                "height": src.height,
                "x0": src.transform.c,
                "y0": src.transform.f,
                "src_nodata": None if src_nodata is None else float(src_nodata),
            }

        tmp_cog = tmp / "out.tif"
        rasterio.shutil.copy(
            cleaned,
            tmp_cog,
            driver="COG",
            COMPRESS="DEFLATE",
            PREDICTOR="YES",
            BLOCKSIZE=512,
            OVERVIEW_RESAMPLING="NEAREST",
            BIGTIFF="IF_SAFER",
            NUM_THREADS=2,
        )
        shutil.move(tmp_cog, dst)

    row = {
        "year": year,
        "mode": mode,
        "state": state,
        **meta,
        "crs": "ESRI:102039",
        "res_m": RES,
        "dtype": "float32",
        "nodata": NODATA,
        **summarise_histogram(hist),
        "n_flagged_invalid": n_flagged,
        "n_below_45": int(hist[: bin_index(np.array([44.95]))[0]].sum()),
        "cog_bytes": dst.stat().st_size,
        "seconds": round(time.time() - t0, 1),
    }
    np.save(dst.with_suffix(".hist.npy"), hist)
    sidecar.write_text(json.dumps(row, default=float))
    return row


# --- VRT mosaic -----------------------------------------------------------------------


def build_vrt(tifs: list[Path], vrt_path: Path) -> Path:
    """Mosaic aligned single-band rasters into a VRT.

    Uses ComplexSource with <NODATA> so one raster's nodata cells never overwrite another's
    values where bounding boxes overlap. All inputs must sit on the same grid.
    """
    tifs = [Path(t) for t in tifs]
    vrt_path = Path(vrt_path)
    infos = []
    for t in tifs:
        with rasterio.open(t) as src:
            infos.append((t, src.transform, src.width, src.height, src.crs, src.nodata))
    ref_t = infos[0][1]
    res_x, res_y = ref_t.a, -ref_t.e
    for t, tr, *_ in infos:
        # BTS pixel sizes carry float noise (e.g. 30.0000000000018 m); 1e-9 is ~nm drift
        if not (np.isclose(tr.a, res_x, rtol=1e-9) and np.isclose(-tr.e, res_y, rtol=1e-9)):
            raise ValueError(f"{t.name}: resolution differs, grids not aligned")
        for off, res in ((tr.c - ref_t.c, res_x), (tr.f - ref_t.f, res_y)):
            if abs(off / res - round(off / res)) > 1e-3:
                raise ValueError(f"{t.name}: grid not aligned with {infos[0][0].name}")

    left = min(tr.c for _, tr, *_ in infos)
    top = max(tr.f for _, tr, *_ in infos)
    right = max(tr.c + w * res_x for _, tr, w, *_ in infos)
    bottom = min(tr.f - h * res_y for _, tr, _, h, *_ in infos)
    width = round((right - left) / res_x)
    height = round((top - bottom) / res_y)
    nodata = infos[0][5] if infos[0][5] is not None else NODATA

    sources = []
    for t, tr, w, h, _, _ in infos:
        xoff = round((tr.c - left) / res_x)
        yoff = round((top - tr.f) / res_y)
        rel = t.resolve().relative_to(vrt_path.parent.resolve())
        sources.append(
            f"""    <ComplexSource>
      <SourceFilename relativeToVRT="1">{escape(str(rel))}</SourceFilename>
      <SourceBand>1</SourceBand>
      <SrcRect xOff="0" yOff="0" xSize="{w}" ySize="{h}"/>
      <DstRect xOff="{xoff}" yOff="{yoff}" xSize="{w}" ySize="{h}"/>
      <NODATA>{nodata}</NODATA>
    </ComplexSource>"""
        )
    xml = f"""<VRTDataset rasterXSize="{width}" rasterYSize="{height}">
  <SRS>{escape(infos[0][4].to_wkt())}</SRS>
  <GeoTransform>{left}, {res_x}, 0.0, {top}, 0.0, {-res_y}</GeoTransform>
  <VRTRasterBand dataType="Float32" band="1">
    <NoDataValue>{nodata}</NoDataValue>
{chr(10).join(sources)}
  </VRTRasterBand>
</VRTDataset>
"""
    vrt_path.parent.mkdir(parents=True, exist_ok=True)
    vrt_path.write_text(xml)
    return vrt_path


def build_layer_vrt(year: int, mode: str) -> Path:
    """CONUS mosaic of a layer's state COGs, for maps and quick looks only.

    2016-2020 states share one grid, so the VRT is an exact mosaic. 2022 states each have
    their own grid origin (offsets of 0-30 m), so their VRT is snapped to a common grid with
    nearest-neighbour resampling by ``gdalbuildvrt -tap``. Analysis never reads these VRTs:
    zonal stats read each block group's own state COG at its native grid.
    """
    tifs = sorted((COG_DIR / str(year) / mode).glob("*.tif"))
    vrt = COG_DIR / f"CONUS_{mode}_{year}.vrt"
    try:
        return build_vrt(tifs, vrt)
    except ValueError:
        subprocess.run(
            [
                _gdal("gdalbuildvrt"), "-q", "-overwrite", "-tap", "-tr", str(RES), str(RES),
                "-r", "nearest", "-srcnodata", str(NODATA), "-vrtnodata", str(NODATA),
                str(vrt), *map(str, tifs),
            ],
            check=True,
        )  # fmt: skip
        return vrt


# --- manifest -------------------------------------------------------------------------


def _sha256(path: Path, chunk: int = 1 << 24) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def write_manifest() -> pd.DataFrame:
    """Size and sha256 of every configured zip; reuses hashes when size and mtime match."""
    old = pd.read_csv(MANIFEST_CSV) if MANIFEST_CSV.exists() else pd.DataFrame()
    rows = []
    for year, mode in LAYERS:
        z = zip_path(year, mode)
        if not z.exists():
            raise FileNotFoundError(f"{z} missing: download it in a browser (see DATA.md §1)")
        st = z.stat()
        prev = old[old["file"] == z.name] if len(old) else old
        if (
            len(prev)
            and prev.iloc[0]["bytes"] == st.st_size
            and prev.iloc[0]["mtime"] == int(st.st_mtime)
        ):
            sha = prev.iloc[0]["sha256"]
        else:
            with zipfile.ZipFile(z) as zf:  # cheap check that the central directory is intact
                zf.namelist()
            sha = _sha256(z)
        rows.append(
            {
                "year": year,
                "mode": mode,
                "file": z.name,
                "bytes": st.st_size,
                "mtime": int(st.st_mtime),
                "sha256": sha,
                "url": SOURCES["base_url"] + z.name,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(MANIFEST_CSV, index=False)
    return df


# --- driver ---------------------------------------------------------------------------


def write_summary() -> pd.DataFrame:
    rows = [json.loads(p.read_text()) for p in sorted(COG_DIR.glob("*/*/*.json"))]
    df = pd.DataFrame(rows).sort_values(["year", "mode", "state"])
    df.to_csv(SUMMARY_CSV, index=False)
    return df


def layer_summary(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-layer roll-up of the state summaries, using the saved histograms."""
    df = write_summary() if df is None else df
    out = []
    for (year, mode), g in df.groupby(["year", "mode"]):
        hist = sum(np.load(cog_path(year, mode, s).with_suffix(".hist.npy")) for s in g["state"])
        out.append(
            {
                "year": year,
                "mode": mode,
                "states": len(g),
                "cog_gb": g["cog_bytes"].sum() / 1e9,
                **summarise_histogram(hist),
                "n_flagged_invalid": int(g["n_flagged_invalid"].sum()),
            }
        )
    return pd.DataFrame(out)


def run(years=None, modes=None, states=None, workers: int = 4, overwrite: bool = False):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("manifest ...")
    print(write_manifest()[["file", "bytes", "sha256"]].to_string(index=False))

    layers = [(y, m) for y, m in LAYERS if (not years or y in years) and (not modes or m in modes)]
    jobs = []
    for y, m in layers:
        for s in states_in_zip(y, m):
            if not states or s in states:
                jobs.append((y, m, s))
    print(f"converting {len(jobs)} state rasters with {workers} workers ...")
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(convert_state, *j, overwrite): j for j in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            print(f"[{i}/{len(jobs)}] {r['year']} {r['mode']:8} {r['state']} {r['seconds']:7.1f}s")

    for y, m in layers:
        build_layer_vrt(y, m)
    summary = layer_summary()
    print(summary.round(4).to_string(index=False))
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--years", type=int, nargs="*")
    p.add_argument("--modes", nargs="*", choices=["road", "aviation", "rail"])
    p.add_argument("--states", nargs="*")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    run(a.years, a.modes, a.states, a.workers, a.overwrite)


if __name__ == "__main__":
    main()
