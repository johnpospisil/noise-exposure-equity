"""Quality-check figures (not for publication).

``bts_quicklook``: one metro window, every BTS layer (rows = mode, columns = year), banded
LAeq,24h. Reads the display VRTs at reduced resolution with nearest-neighbour sampling, so
no decibel values are averaged.

    uv run python -m ne.viz.qa
"""

from __future__ import annotations

import matplotlib

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


if __name__ == "__main__":
    print(bts_quicklook())
