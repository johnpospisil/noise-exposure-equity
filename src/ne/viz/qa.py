"""Quality-check figures (not for publication).

``bts_quicklook``: one metro window, every BTS layer (rows = mode, columns = year), banded
LAeq,24h. Reads the display VRTs at reduced resolution with nearest-neighbour sampling, so
no decibel values are averaged.

    uv run python -m ne.viz.qa
"""

from __future__ import annotations

import matplotlib
import matplotlib.dates

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from pyproj import Transformer  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

from ne import config  # noqa: E402
from ne.ingest import bts_noise as bn  # noqa: E402
from ne.viz import theme  # noqa: E402

QA_DIR = config.FIGURES_DIR / "qa"

#: lon/lat boxes for quick looks
WINDOWS = {
    "nyc": ("New York City core", (-74.26, 40.49, -73.70, 40.92)),
}


def _albers_bounds(lonlat):
    t = Transformer.from_crs("EPSG:4326", bn.TARGET_CRS.to_wkt(), always_xy=True)
    xs, ys = t.transform([lonlat[0], lonlat[2], lonlat[0], lonlat[2]],
                         [lonlat[1], lonlat[1], lonlat[3], lonlat[3]])  # fmt: skip
    return min(xs), min(ys), max(xs), max(ys)


def read_window(vrt, bounds, width_px=700):
    with rasterio.open(vrt) as src:
        win = from_bounds(*bounds, transform=src.transform)
        h = round(width_px * win.height / win.width)
        arr = src.read(1, window=win, out_shape=(h, width_px), resampling=Resampling.nearest,
                       boundless=True, fill_value=bn.NODATA)  # fmt: skip
    return np.ma.masked_equal(arr, bn.NODATA)


def bts_quicklook(window: str = "nyc", out=None):
    title, lonlat = WINDOWS[window]
    bounds = _albers_bounds(lonlat)
    years = sorted({y for y, _ in bn.LAYERS})
    modes = ["road", "aviation", "rail"]

    edges = theme.NOISE_BANDS + [bn.MAX_DB]
    cmap = ListedColormap(theme.NOISE_COLORS)
    cmap.set_bad(theme.BELOW_COLOR)
    norm = BoundaryNorm(edges, cmap.N)

    fig, axes = plt.subplots(len(modes), len(years), figsize=(3.2 * len(years), 3.6 * len(modes)))
    for i, mode in enumerate(modes):
        for j, year in enumerate(years):
            ax = axes[i, j]
            ax.set_xticks([])
            ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
            vrt = bn.COG_DIR / f"CONUS_{mode}_{year}.vrt"
            if i == 0:
                ax.set_title(str(year), fontsize=12, color=theme.INK)
            if j == 0:
                ax.set_ylabel(mode, fontsize=12, color=theme.INK)
            if not vrt.exists():
                ax.set_facecolor("white")
                ax.text(0.5, 0.5, "no layer", ha="center", va="center",
                        color=theme.INK_MUTED, transform=ax.transAxes)  # fmt: skip
                continue
            ax.imshow(read_window(vrt, bounds), cmap=cmap, norm=norm, interpolation="nearest")

    handles = [
        Patch(color=c, label=lab)
        for c, lab in zip(theme.NOISE_COLORS, theme.NOISE_BAND_LABELS, strict=True)
    ]
    handles.append(Patch(facecolor=theme.BELOW_COLOR, edgecolor="#cfcdc8", label="< 45 / none"))
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False,
               title="Modelled LAeq,24h (dBA)", fontsize=10)  # fmt: skip
    fig.suptitle(f"BTS National Transportation Noise Map: {title} (QA quick look)",
                 fontsize=13, color=theme.INK)  # fmt: skip
    fig.text(0.5, 0.055, "Modelled, not measured. 2022 road uses 2023 traffic data. "
             "2018 rail is passenger only; 2020 rail is a prototype.",
             ha="center", fontsize=9, color=theme.INK_MUTED)  # fmt: skip
    fig.tight_layout(rect=(0, 0.08, 1, 0.96))
    out = out or QA_DIR / f"bts_quicklook_{window}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def nyc311_monthly(out=None):
    """Monthly NYC 311 noise complaints, one small multiple per complaint group."""
    import pandas as pd

    from ne.ingest import nyc311

    if not nyc311.OUT.exists():
        return None
    df = pd.read_parquet(nyc311.OUT, columns=["created_date", "noise_group"])
    df["month"] = df["created_date"].dt.to_period("M").dt.to_timestamp()
    t = df.groupby(["noise_group", "month"]).size().unstack(0).fillna(0)
    t = t.iloc[:-1]  # drop the current, incomplete month
    order = t.sum().sort_values(ascending=False).index

    ncol = 4
    nrow = -(-len(order) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(14, 3.0 * nrow), sharex=True)
    for ax, g in zip(axes.flat, order, strict=False):
        ax.plot(t.index, t[g] / 1000, color=theme.NOISE_COLORS[2], lw=1.5)
        ax.axvline(pd.Timestamp(f"{nyc311.ANALYSIS_START_YEAR}-01-01"), color=theme.INK_MUTED,
                   lw=0.8, ls="--")  # fmt: skip
        ax.set_title(g.replace("_", " "), fontsize=11, color=theme.INK, loc="left")
        ax.set_ylim(bottom=0)
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(4))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
        ax.grid(axis="y", color="#e4e2dd", lw=0.6)
        ax.tick_params(colors=theme.INK_MUTED, labelsize=9)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color("#cfcdc8")
    for ax in list(axes.flat)[len(order) :]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel("complaints / month (k)", fontsize=9, color=theme.INK_MUTED)
    fig.suptitle("NYC 311 noise complaints per month, by complaint group (QA)", fontsize=13,
                 color=theme.INK)  # fmt: skip
    fig.text(0.5, 0.01, "Each panel has its own scale. Dashed line: analysis window starts "
             f"{nyc311.ANALYSIS_START_YEAR}. Source: NYC Open Data 311 (76ig-c548, erm2-nwe9).",
             ha="center", fontsize=9, color=theme.INK_MUTED)  # fmt: skip
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    out = out or QA_DIR / "nyc311_monthly.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


if __name__ == "__main__":
    print(bts_quicklook())
    print(nyc311_monthly())
