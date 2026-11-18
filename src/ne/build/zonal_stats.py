"""Zonal statistics: BTS noise rasters -> 2020 blocks -> 2020 block groups.

Per block, source and year (decision P03):

* ``share_ge_T``: share of the block's area at or above each threshold (45/55/65/70 dBA).
  Censored cells (< 45 dBA) count as area. Partial cells are weighted by coverage.
* ``median_db``: coverage-weighted median level; ``NaN`` when it is below 45 dBA.
* ``emean_cap100_db``: energy mean with values capped at 100 dB and censored cells at
  the 45 dB floor (sensitivity only).

Block groups (2020 boundaries, every year) take the block values weighted by 2020
block population: ``pop_share_ge_T`` (headline), a population-weighted median of block
medians, and a population-weighted energy mean. ``area_share_ge_T`` (weighted by block
area) is kept for the P15 robustness check.

Each block is measured on its own state's raster: the 2022 and aviation state rasters do
not share one grid (P03). Sources are combined at the cell level on the road grid of the
state (``combine_rasters``: nearest-neighbour onto that grid, then an energy sum where a
censored source adds nothing), giving ``road_aviation`` (comparable over time) and
``all`` (years with rail).

Usage::

    uv run python -m ne.build.zonal_stats                        # every metro, 2 workers
    uv run python -m ne.build.zonal_stats --metro 35620          # New York only
"""

from __future__ import annotations

import argparse
import json
import time
from contextlib import ExitStack
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling
from rasterio.windows import Window, from_bounds

from ne import config
from ne.build import combine_sources as cs
from ne.ingest import bts_noise as bn

CRS = bn.TARGET_CRS
NODATA = bn.NODATA
CENSORED = -1.0  # placeholder exactextract writes for censored (< 45 dBA) cells
CAP_DB = 100.0
THRESHOLDS = tuple(config.thresholds()["exposure_thresholds_dba"])
OUT_DIR = config.INTERIM_DIR / "zonal"
COMBINED_DIR = config.INTERIM_DIR / "bts" / "combined"
CENSUS = config.INTERIM_DIR / "census"
COMBOS = {"road_aviation": ("road", "aviation"), "all": ("road", "aviation", "rail")}


# --- grouped helpers ------------------------------------------------------------------


def _grouped_weighted_median(gid, values, weights, n):
    """Weighted median per group. ``-inf`` values rank lowest; empty groups give NaN."""
    out = np.full(n, np.nan)
    if len(values) == 0:
        return out
    order = np.lexsort((values, gid))
    g, v, w = gid[order], values[order], weights[order]
    total = np.bincount(g, w, n)
    cw = np.cumsum(w)
    start = np.concatenate([[0.0], np.cumsum(total)[:-1]])
    target = start + 0.5 * total
    idx = np.searchsorted(cw, target * (1 - 1e-12) - 1e-12, side="left")
    idx = np.clip(idx, 0, len(v) - 1)
    ok = total > 0
    out[ok] = v[idx[ok]]
    out[np.isneginf(out)] = np.nan
    return out


# --- blocks ---------------------------------------------------------------------------


def summarise_cells(values, coverage, thresholds=THRESHOLDS, cap=CAP_DB, floor=None):
    """One row per block from exactextract's per-cell ``values`` and ``coverage`` arrays."""
    floor = cs.default_floor() if floor is None else floor
    n = len(values)
    lengths = np.fromiter((len(v) for v in values), dtype=int, count=n)
    gid = np.repeat(np.arange(n), lengths)
    v = np.concatenate([np.asarray(x, float) for x in values]) if n else np.array([])
    w = np.concatenate([np.asarray(x, float) for x in coverage]) if n else np.array([])
    censored = v <= CENSORED

    cells = np.bincount(gid, w, n)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = {"cells": cells}
        for t in thresholds:
            out[f"share_ge_{t}"] = np.bincount(gid, w * (~censored & (v >= t)), n) / cells
        out["median_db"] = _grouped_weighted_median(gid, np.where(censored, -np.inf, v), w, n)
        e = np.where(censored, cs.to_energy(floor), cs.to_energy(np.minimum(v, cap)))
        out["emean_cap100_db"] = cs.to_db(np.bincount(gid, w * e, n) / cells)
    df = pd.DataFrame(out)
    df.loc[df["cells"] == 0, df.columns != "cells"] = np.nan
    return df


def block_stats(
    raster, blocks: gpd.GeoDataFrame, thresholds=THRESHOLDS, batch: int = 20_000
) -> pd.DataFrame:
    """Block-level stats from one raster. Returns ``blocks`` columns (no geometry) + stats.

    Blocks go through exactextract in batches so that per-cell arrays for large rural
    blocks never pile up in memory.
    """
    from exactextract import exact_extract

    geoms = blocks[["geometry"]].to_crs(CRS) if blocks.crs != CRS else blocks[["geometry"]]
    geoms = geoms.reset_index(drop=True)
    parts = []
    with rasterio.open(raster) as src:
        for i in range(0, len(geoms), batch):
            ee = exact_extract(
                src,
                geoms.iloc[i : i + batch],
                ["values(default_value=-1)", "coverage(default_value=-1)"],
                output="pandas",
            )
            parts.append(summarise_cells(list(ee["values"]), list(ee["coverage"]), thresholds))
    stats = pd.concat(parts, ignore_index=True)
    return pd.concat([blocks.drop(columns="geometry").reset_index(drop=True), stats], axis=1)


# --- block groups ---------------------------------------------------------------------


def aggregate_to_bg(blocks: pd.DataFrame, thresholds=THRESHOLDS, keys=()) -> pd.DataFrame:
    """Block stats -> block groups (population-weighted, plus area-weighted shares)."""
    keys = [*keys, "bg_geoid"]
    b = blocks[blocks["cells"] > 0].copy()
    gid, uniq = pd.factorize(pd.MultiIndex.from_frame(b[keys]))
    n = len(uniq)
    pop = b["pop20"].to_numpy(float)
    area = b["cells"].to_numpy(float)
    psum, asum = np.bincount(gid, pop, n), np.bincount(gid, area, n)
    out = pd.DataFrame(list(uniq), columns=keys)
    out["pop20"] = psum.astype(int)
    out["cells"] = asum
    with np.errstate(invalid="ignore", divide="ignore"):
        for t in thresholds:
            s = b[f"share_ge_{t}"].to_numpy(float)
            out[f"pop_share_ge_{t}"] = np.bincount(gid, pop * s, n) / psum
            out[f"area_share_ge_{t}"] = np.bincount(gid, area * s, n) / asum
        med = b["median_db"].to_numpy(float)
        out["median_db"] = _grouped_weighted_median(
            gid, np.where(np.isnan(med), -np.inf, med), pop, n
        )
        e = cs.to_energy(b["emean_cap100_db"].to_numpy(float))
        out["emean_cap100_db"] = cs.to_db(np.bincount(gid, pop * e, n) / psum)
    out.loc[psum == 0, "median_db"] = np.nan
    return out


# --- rasters --------------------------------------------------------------------------


def combine_rasters(paths, out: Path, bounds, strip_rows: int = 1024) -> Path:
    """Energy-sum several source rasters onto the first raster's grid, clipped to ``bounds``.

    Nearest-neighbour resampling (no dB values are interpolated); a censored source adds no
    energy; a cell censored in every source stays NODATA.
    """
    with rasterio.open(paths[0]) as ref:
        # snap the bounds outward to the reference grid
        win = from_bounds(*bounds, transform=ref.transform)
        col0, row0 = int(np.floor(win.col_off)), int(np.floor(win.row_off))
        width = int(np.ceil(win.col_off + win.width)) - col0
        height = int(np.ceil(win.row_off + win.height)) - row0
        transform = ref.transform @ Affine.translation(col0, row0)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part.tif")
    profile = dict(
        driver="GTiff", width=width, height=height, count=1, dtype="float32", crs=CRS,
        transform=transform, nodata=NODATA, tiled=True, blockxsize=512, blockysize=512,
        compress="deflate",
    )  # fmt: skip
    with ExitStack() as stack:
        vrts = [
            stack.enter_context(WarpedVRT(
                stack.enter_context(rasterio.open(p)), crs=CRS, transform=transform,
                width=width, height=height, resampling=Resampling.nearest,
                nodata=NODATA, src_nodata=NODATA,
            ))
            for p in paths
        ]  # fmt: skip
        dst = stack.enter_context(rasterio.open(tmp, "w", **profile))
        for r0 in range(0, height, strip_rows):
            win = Window(0, r0, width, min(strip_rows, height - r0))
            layers = np.stack([cs.from_raster(v.read(1, window=win)) for v in vrts])
            total = cs.energy_sum(layers, policy="zero")
            dst.write(np.where(np.isnan(total), NODATA, total).astype("float32"), 1, window=win)
    tmp.replace(out)
    return out


def sources_for(year: int) -> list[str]:
    modes = [m for (y, m) in bn.LAYERS if y == year]
    out = [m for m in ("road", "aviation", "rail") if m in modes]
    out.append("road_aviation")
    if "rail" in modes:
        out.append("all")
    return out


def raster_for(year: int, source: str, state_abbr: str, cbsa: str, bounds) -> Path:
    if source not in COMBOS:
        return bn.cog_path(year, source, state_abbr)
    out = COMBINED_DIR / str(year) / source / f"{cbsa}_{state_abbr}.tif"
    if not out.exists():
        combine_rasters([bn.cog_path(year, m, state_abbr) for m in COMBOS[source]], out, bounds)
    return out


# --- pipeline -------------------------------------------------------------------------

STATE_ABBR = {
    "04": "AZ", "06": "CA", "08": "CO", "10": "DE", "11": "DC", "12": "FL", "13": "GA",
    "17": "IL", "18": "IN", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "33": "NH",
    "34": "NJ", "36": "NY", "42": "PA", "48": "TX", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI",
}  # fmt: skip


def load_blocks(state: str, cbsa: str) -> gpd.GeoDataFrame:
    cols = ["geoid", "bg_geoid", "cbsa", "pop20", "geometry"]
    b = gpd.read_parquet(CENSUS / "blocks_2020" / f"{state}.parquet", columns=cols)
    return b[b["cbsa"] == cbsa].to_crs(CRS).reset_index(drop=True)


def run_metro(cbsa: str, years=None, log=print) -> dict:
    metro = next(m for m in config.metros() if m["cbsa"] == cbsa)
    years = years or sorted({y for y, _ in bn.LAYERS})
    out_dir = OUT_DIR / cbsa
    out_dir.mkdir(parents=True, exist_ok=True)
    timings, parts = [], []
    for state in metro["states"]:
        st = STATE_ABBR[state]
        t0 = time.time()
        blocks = load_blocks(state, cbsa)
        if blocks.empty:
            continue
        x0, y0, x1, y1 = blocks.total_bounds
        bounds = (x0 - 60, y0 - 60, x1 + 60, y1 + 60)
        log(f"{metro['short']} {st}: {len(blocks):,} blocks ({time.time() - t0:.0f}s load)")
        for year in years:
            for source in sources_for(year):
                t1 = time.time()
                r = raster_for(year, source, st, cbsa, bounds)
                s = block_stats(r, blocks)
                s.insert(0, "source", source)
                s.insert(0, "year", year)
                parts.append(s)
                dt_ = time.time() - t1
                timings.append({"state": st, "year": year, "source": source,
                                "blocks": len(blocks), "seconds": round(dt_, 1)})  # fmt: skip
                log(f"  {year} {source:13s} {dt_:6.1f}s")
    blk = pd.concat(parts, ignore_index=True)
    blk.to_parquet(out_dir / "blocks.parquet", index=False)
    bg = aggregate_to_bg(blk, keys=("year", "source"))
    bg.insert(0, "cbsa", cbsa)
    bg.to_parquet(out_dir / "bg_noise.parquet", index=False)
    pd.DataFrame(timings).to_csv(out_dir / "timings.csv", index=False)
    (out_dir / "meta.json").write_text(json.dumps({"cbsa": cbsa, "years": years}, indent=1))
    return {"blocks": blk, "bg": bg, "timings": pd.DataFrame(timings)}


# --- validation -----------------------------------------------------------------------

#: (label, lon, lat, expectation) for the New York pilot (P07)
NYC_CHECKS = [
    ("Cross Bronx Expwy, Tremont", -73.8990, 40.8435, "road high"),
    ("Gowanus Expwy, Sunset Park", -74.0080, 40.6530, "road high"),
    ("Van Wyck Expwy, Jamaica", -73.8070, 40.6960, "road high"),
    ("NJ Turnpike, Elizabeth", -74.1890, 40.6650, "road + aviation high (EWR)"),
    ("JFK approach, Rosedale", -73.7500, 40.6600, "aviation high"),
    ("JFK, Howard Beach", -73.8400, 40.6580, "aviation high"),
    ("LGA, East Elmhurst", -73.8770, 40.7640, "aviation high"),
    ("Hudson Line / freight, Mott Haven", -73.9250, 40.8080, "rail elevated"),
    ("Todt Hill, Staten Island", -74.1100, 40.6040, "quiet control"),
    ("Upper Montclair, NJ", -74.2000, 40.8400, "quiet control"),
]


def tract_table(bg: pd.DataFrame, year: int = 2022, t: int = 65) -> pd.DataFrame:
    """Population-weighted tract shares >= ``t`` dBA by source (from block-group rows)."""
    d = bg[bg["year"] == year].assign(tract=lambda x: x["bg_geoid"].str[:11])
    d = d.assign(w=d["pop20"] * d[f"pop_share_ge_{t}"])
    g = d.groupby(["tract", "source"])[["w", "pop20"]].sum()
    return (g["w"] / g["pop20"]).unstack("source")


def validate_points(bg: pd.DataFrame, checks=NYC_CHECKS, year: int = 2022) -> pd.DataFrame:
    tracts = gpd.read_parquet(CENSUS / "tract_2020.parquet", columns=["geoid", "geometry"])
    pts = gpd.GeoDataFrame(
        pd.DataFrame(checks, columns=["place", "lon", "lat", "expect"]),
        geometry=gpd.points_from_xy([c[1] for c in checks], [c[2] for c in checks]),
        crs="EPSG:4326",
    ).to_crs(tracts.crs)
    j = gpd.sjoin(pts, tracts, predicate="within", how="left")
    shares = {t: tract_table(bg, year, t) for t in (55, 65)}
    rows = []
    for _, r in j.iterrows():
        row = {"place": r["place"], "tract": r["geoid"], "expect": r["expect"]}
        for t, tab in shares.items():
            for s in ("road", "aviation", "rail", "all"):
                v = tab.at[r["geoid"], s] if r["geoid"] in tab.index and s in tab else np.nan
                row[f"{s}_ge{t}"] = round(100 * v, 1)
        rows.append(row)
    return pd.DataFrame(rows)


# --- all metros -----------------------------------------------------------------------

PROCESSED = config.PROCESSED_DIR / "bg_noise.parquet"


def is_done(cbsa: str, years) -> bool:
    meta = OUT_DIR / cbsa / "meta.json"
    if not (meta.exists() and (OUT_DIR / cbsa / "bg_noise.parquet").exists()):
        return False
    return json.loads(meta.read_text())["years"] == list(years)


def _run_logged(cbsa: str, years) -> tuple[str, float]:
    log_path = OUT_DIR / cbsa / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with open(log_path, "w") as f:

        def log(msg):
            print(msg, file=f, flush=True)

        run_metro(cbsa, years, log=log)
    return cbsa, time.time() - t0


def run_all(workers: int = 2, overwrite: bool = False, years=None, log=print) -> pd.DataFrame:
    """Every metro in ``config/metros.yaml``, largest first, skipping finished ones."""
    from concurrent.futures import ProcessPoolExecutor, as_completed

    years = years or sorted({y for y, _ in bn.LAYERS})
    metros = config.metros()
    todo = [m["cbsa"] for m in metros if overwrite or not is_done(m["cbsa"], years)]
    names = {m["cbsa"]: m["short"] for m in metros}
    log(f"{len(todo)} metros to run, {len(metros) - len(todo)} already done")
    with ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(_run_logged, c, years): c for c in todo}
        for i, f in enumerate(as_completed(futs), 1):
            cbsa, secs = f.result()
            log(f"[{i}/{len(todo)}] {names[cbsa]} ({cbsa}) {secs / 60:.1f} min")
    return assemble()


def assemble() -> pd.DataFrame:
    """Stack every metro's block-group table into ``data/processed/bg_noise.parquet``."""
    parts = [pd.read_parquet(OUT_DIR / m["cbsa"] / "bg_noise.parquet") for m in config.metros()]
    bg = pd.concat(parts, ignore_index=True)
    floats = bg.select_dtypes("float64").columns
    bg[floats] = bg[floats].astype("float32")  # < 50 MB rule for data/processed
    bg["year"] = bg["year"].astype("int16")
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    bg.to_parquet(PROCESSED, index=False, compression="zstd")
    return bg


# --- reconciliation -------------------------------------------------------------------

#: Published national figures (percent of U.S. population at or above the level).
#: UW DEOHS: BTS 2020 map, road + rail + aviation, block groups -> tracts, ACS 2016-20.
#: BTS 2017 release: 2014 map, aviation and Interstate highways separately (sums of bands).
BENCHMARKS = [
    {"benchmark": "UW DEOHS 2020, all sources", "year": 2020, "source": "all", "t": 45,
     "published_pct": 29.1},
    {"benchmark": "UW DEOHS 2020, all sources", "year": 2020, "source": "all", "t": 60,
     "published_pct": 3.6},
    {"benchmark": "BTS 2014 map, aviation", "year": 2016, "source": "aviation", "t": 50,
     "published_pct": 2.88},
    {"benchmark": "BTS 2014 map, aviation", "year": 2016, "source": "aviation", "t": 60,
     "published_pct": 0.23},
    {"benchmark": "BTS 2014 map, Interstates only", "year": 2016, "source": "road", "t": 50,
     "published_pct": 2.05},
    {"benchmark": "BTS 2014 map, Interstates only", "year": 2016, "source": "road", "t": 60,
     "published_pct": 0.75},
]  # fmt: skip


def pooled_shares(bg: pd.DataFrame, by=("year", "source")) -> pd.DataFrame:
    """Population-weighted percent of residents at or above each threshold."""
    by = list(by)
    cols = [c for c in bg.columns if c.startswith("pop_share_ge_")]
    w = bg[cols].mul(bg["pop20"], axis=0).assign(pop20=bg["pop20"], **{k: bg[k] for k in by})
    g = w.groupby(by).sum()
    out = 100 * g[cols].div(g["pop20"], axis=0)
    out.columns = [int(c.rsplit("_", 1)[1]) for c in cols]
    return out


def reconcile(bg: pd.DataFrame) -> pd.DataFrame:
    ours = pooled_shares(bg)
    rows = []
    for b in BENCHMARKS:
        v = ours.loc[(b["year"], b["source"]), b["t"]]
        rows.append({**b, "our_20_metros_pct": round(float(v), 2)})
    return pd.DataFrame(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--metro", help="one CBSA code (default: every metro)")
    p.add_argument("--years", type=int, nargs="*")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args(argv)
    if a.metro:
        run_metro(a.metro, a.years)
    else:
        bg = run_all(a.workers, a.overwrite, a.years)
        print(f"{PROCESSED.relative_to(config.ROOT)}: {len(bg):,} rows")


if __name__ == "__main__":
    main()
