"""Chart 2: bivariate choropleth of modelled noise × household income (P16).

New York metro core, 2022 BTS map (road + rail + aviation), 2020 block groups.

* Noise classes: share of residents at or above 55 dBA: < 5 %, 5-20 %, ≥ 20 % (roughly
  thirds of the metro's block groups).
* Income classes: thirds of the metro's residents by block-group median household income
  (ACS 2018-22), population-weighted.

Darkest corner = loud and lower-income. Static PNG/SVG plus an interactive HTML version
(Leaflet page with a CARTO basemap). Modelled noise, neighbourhood estimates.

Usage::

    uv run python -m ne.viz.maps
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "noise-exposure-equity"

from pathlib import Path  # noqa: E402
from string import Template  # noqa: E402

import geopandas as gpd  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from ne import config  # noqa: E402
from ne.build import analysis_table as at  # noqa: E402
from ne.build import zonal_stats as zs  # noqa: E402
from ne.viz import qa, theme  # noqa: E402

#: 3 × 3 bivariate palette (Stevens blue-pink), index = income_class * 3 + noise_class.
#: Row 0 = higher-income, row 2 = lower-income; column 0 = quiet, column 2 = loud.
BIVARIATE = [
    "#e8e8e8", "#ace4e4", "#5ac8c8",
    "#dfb0d6", "#a5add3", "#5698b9",
    "#be64ac", "#8c62aa", "#3b4994",
]  # fmt: skip
NOISE_BREAKS = (0.05, 0.20)
NOISE_LABELS = ["< 5%", "5–20%", "≥ 20%"]
INCOME_LABELS = ["Higher", "Middle", "Lower"]
NO_DATA = "#ffffff"
FIG_DIR = config.FIGURES_DIR


def weighted_terciles(income: pd.Series, pop: pd.Series) -> tuple[float, float]:
    """Incomes at which a third and two thirds of residents are reached (lowest first)."""
    d = pd.DataFrame({"x": income, "w": pop}).dropna().sort_values("x")
    cum = d["w"].cumsum() / d["w"].sum()
    lo = d.loc[cum >= 1 / 3 - 1e-12, "x"].iloc[0]
    hi = d.loc[cum >= 2 / 3 - 1e-12, "x"].iloc[0]
    return float(lo), float(hi)


def bivariate_class(noise: pd.Series, income: pd.Series, noise_breaks=NOISE_BREAKS,
                    income_breaks=(0.0, 0.0)) -> pd.Series:  # fmt: skip
    """Class index 0-8 (income class * 3 + noise class); NaN where either is missing."""
    x = np.select([noise < noise_breaks[0], noise < noise_breaks[1]], [0, 1], 2)
    y = np.select([income <= income_breaks[0], income <= income_breaks[1]], [2, 1], 0)
    out = pd.Series(y * 3 + x, index=noise.index, dtype="Float64")
    return out.mask(noise.isna() | income.isna()).astype("Int8")


def load(cbsa: str = "35620", year: int = 2022) -> gpd.GeoDataFrame:
    df = pd.read_parquet(at.OUT)
    df = df[(df["cbsa"] == cbsa) & (df["year"] == year) & (df["source"] == "all")]
    lo, hi = weighted_terciles(df["med_hh_income"], df["pop20"])
    df = df.assign(cls=bivariate_class(df["pop_share_ge_55"], df["med_hh_income"],
                                       income_breaks=(lo, hi)))  # fmt: skip
    geo = gpd.read_parquet(zs.CENSUS / "bg_2020.parquet", columns=["geoid", "geometry"])
    g = geo.rename(columns={"geoid": "bg_geoid"}).merge(df, on="bg_geoid")
    g.attrs["income_breaks"] = (lo, hi)
    return g


def _legend(fig, rect, lo, hi):
    ax = fig.add_axes(rect)
    for y in range(3):
        for x in range(3):
            ax.add_patch(Rectangle((x, 2 - y), 0.94, 0.94, color=BIVARIATE[y * 3 + x]))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 3)
    ax.set_xticks([0.47, 1.47, 2.47], NOISE_LABELS, fontsize=7.5)
    ax.set_yticks([2.47, 1.47, 0.47], [f"> ${hi / 1000:.0f}k", f"${lo / 1000:.0f}–{hi / 1000:.0f}k",
                                       f"≤ ${lo / 1000:.0f}k"], fontsize=7.5)  # fmt: skip
    ax.tick_params(length=0, colors=theme.INK_MUTED)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel("Louder →\n% of residents ≥ 55 dBA", fontsize=8, color=theme.INK)
    ax.set_ylabel("Median household income\n← Lower income", fontsize=8, color=theme.INK)
    ax.set_aspect("equal")


def static(window: str = "nyc"):
    g = load()
    lo, hi = g.attrs["income_breaks"]
    title, lonlat = qa.WINDOWS[window]
    g = g.to_crs(zs.CRS)
    x0, y0, x1, y1 = qa._albers_bounds(lonlat)
    g = g.cx[x0:x1, y0:y1]
    fig, ax = plt.subplots(figsize=(10, 10.5))
    colors = [BIVARIATE[int(c)] if pd.notna(c) else NO_DATA for c in g["cls"]]
    g.plot(ax=ax, color=colors, linewidth=0, rasterized=True)  # small SVG; text stays vector
    counties = g.assign(county=g["bg_geoid"].str[:5]).dissolve("county")
    counties.boundary.plot(ax=ax, color="white", linewidth=1.0, rasterized=True)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_axis_off()
    _legend(fig, [0.71, 0.14, 0.15, 0.15], lo, hi)
    dark = g[g["cls"] == 8]
    share = dark["pop20"].sum() / g["pop20"].sum()
    fig.suptitle(
        "Where New York's loud neighbourhoods and lower incomes overlap\n"
        "Modelled road, rail and aircraft noise × median household income, 2022 block groups",
        x=0.03, y=0.985, ha="left", fontsize=13, color=theme.INK,
    )  # fmt: skip
    fig.text(0.03, 0.015,
             f"Darkest blue: ≥ 20% of residents at or above 55 dBA and income in the metro's "
             f"lowest third ({100 * share:.0f}% of residents shown). White: no residents or no "
             "income estimate.\nModelled, not measured (BTS National Transportation Noise Map, "
             "LAeq,24h); road = major roads only; no subway. Income thirds are population-"
             "weighted across the whole metro.\nSources: BTS; U.S. Census Bureau (2020 Census, "
             "ACS 2018-22). Neighbourhood estimates, not individual exposure.",
             fontsize=7.5, color=theme.INK_MUTED)  # fmt: skip
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.08)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = [FIG_DIR / "chart2_bivariate_nyc.png", FIG_DIR / "chart2_bivariate_nyc.svg"]
    for p in out:
        fig.savefig(p, dpi=150, facecolor=theme.SURFACE,
                    metadata={"Date": None} if p.suffix == ".svg" else {})  # fmt: skip
    plt.close(fig)
    return out


LEAFLET_TEMPLATE = Path(__file__).parent / "templates" / "leaflet_bivariate.html"


def interactive(window: str = "nyc", tolerance_m: float = 15.0):
    """Leaflet page (no WebGL; Leaflet from cdnjs) with hover details per block group.

    plotly's MapLibre maps drew a blank canvas here (plotly 7.1 / plotly.js 4.1), so the
    interactive version is a small hand-written Leaflet page with embedded GeoJSON.
    """
    import json

    g = load()
    lo, hi = g.attrs["income_breaks"]
    _, (lon0, lat0, lon1, lat1) = qa.WINDOWS[window]
    g = g.to_crs(zs.CRS)
    g["geometry"] = g.simplify(tolerance_m)
    g = g.to_crs("EPSG:4326").cx[lon0:lon1, lat0:lat1]
    g["geometry"] = shapely.set_precision(g.geometry.values, 1e-5)  # ~1 m; smaller HTML
    g = g[g["cls"].notna()].reset_index(drop=True)
    props = gpd.GeoDataFrame(
        {
            "id": g["bg_geoid"],
            "c": g["cls"].astype(int),
            "s": (100 * g["pop_share_ge_55"]).round().astype(int),
            "i": g["med_hh_income"].round().astype(int),
            "p": g["pop20"].astype(int),
        },
        geometry=g.geometry,
        crs="EPSG:4326",
    )
    inc_ticks = [f"&gt; ${hi / 1000:.0f}k", f"${lo / 1000:.0f}–{hi / 1000:.0f}k",
                 f"&le; ${lo / 1000:.0f}k"]  # fmt: skip
    html = Template(LEAFLET_TEMPLATE.read_text(encoding="utf-8")).substitute(
        colors=json.dumps(BIVARIATE),
        noise=json.dumps(NOISE_LABELS),
        income=json.dumps(INCOME_LABELS),
        inc_ticks=json.dumps(inc_ticks),
        geojson=props.to_json(drop_id=True, separators=(",", ":")),
    )
    out = FIG_DIR / "chart2_bivariate_nyc.html"
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    for p in [*static(), interactive()]:
        print(p, f"{p.stat().st_size / 1e6:.1f} MB")
