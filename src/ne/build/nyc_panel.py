"""NYC tract × month panel of 311 noise complaints, with modelled noise and demographics (P12).

Outputs (``data/processed/``):

* ``nyc_panel.parquet``: every 2020 NYC census tract × month (2016-01 to the last complete
  month) × complaint group, with ``complaints`` (raw) and ``location_days`` (decision P05:
  one location counts at most once per day per group; same-minute app repeats collapse).
* ``nyc_tracts.parquet``: one row per tract: 2020 population, modelled noise (2022 BTS map,
  population-weighted from block groups), ACS 2018-22 demographics, and the gentrification
  typology.

Gentrification typology (own definition, decision P12), ACS 2016-20 -> 2020-24, both on
2020 tracts. City medians are taken over tracts with at least 500 residents.

* **Eligible**: tract median household income (2016-20) at or below the city median.
* **Low-income, gentrifying**: eligible, and both the change in the share of adults 25+
  with a bachelor's degree or more and the percent change in median gross rent exceed the
  city median change.
* **Low-income, not gentrifying**: eligible, not gentrifying.
* **Higher-income**: above the city median income.
* **Too few residents**: under 500 residents (or missing data).

Only tract-level counts leave this module (NYC Open Data terms + project rule). The BTS
rail layer does not include the NYC subway.

Usage::

    uv run python -m ne.build.nyc_panel
"""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd

from ne import config
from ne.build import zonal_stats as zs
from ne.ingest import nyc311
from ne.ingest.http import get_json

NYC_COUNTIES = {"36005": "Bronx", "36047": "Brooklyn", "36061": "Manhattan",
                "36081": "Queens", "36085": "Staten Island"}  # fmt: skip
START, END = "2016-01", "2026-10"  # END = last complete month at build time (2026-11)
PANEL = config.PROCESSED_DIR / "nyc_panel.parquet"
TRACTS = config.PROCESSED_DIR / "nyc_tracts.parquet"
RAW = config.RAW_DIR / "census" / "acs_tract"
MIN_POP = 500
TYPO_BASE, TYPO_END, DEMO_YEAR = 2020, 2024, 2022

BA_PLUS = ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
TRACT_VARS = [
    "B01003_001E", "B19013_001E", "B25064_001E", "B15003_001E", *BA_PLUS,
    "B03002_001E", "B03002_003E", "B03002_004E", "B03002_006E", "B03002_012E",
    "B25003_001E", "B25003_003E",
]  # fmt: skip
TYPOLOGY = ["Low-income, gentrifying", "Low-income, not gentrifying", "Higher-income",
            "Too few residents"]  # fmt: skip


# --- ACS tracts -----------------------------------------------------------------------


def fetch_tracts(end_year: int) -> pd.DataFrame:
    path = RAW / str(end_year) / "36_nyc.json"
    if path.exists():
        rows = json.loads(path.read_text())
    else:
        counties = ",".join(c[2:] for c in NYC_COUNTIES)
        rows = get_json(
            f"https://api.census.gov/data/{end_year}/acs/acs5",
            {"get": ",".join(TRACT_VARS), "for": "tract:*",
             "in": ["state:36", f"county:{counties}"], "key": config.CENSUS_API_KEY},
        )  # fmt: skip
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows))
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["tract"] = df["state"] + df["county"] + df["tract"]
    num = df[TRACT_VARS].apply(pd.to_numeric, errors="coerce")
    num = num.mask(num <= -100_000_000)  # ACS annotation codes
    return pd.concat([df[["tract"]], num], axis=1)


def _share(a, b):
    return (a / b).where(b > 0)


def tract_acs(end_year: int) -> pd.DataFrame:
    r = fetch_tracts(end_year)
    return pd.DataFrame(
        {
            "tract": r["tract"],
            "pop": r["B01003_001E"],
            "income": r["B19013_001E"],
            "rent": r["B25064_001E"],
            "ba_share": _share(r[BA_PLUS].sum(axis=1, min_count=1), r["B15003_001E"]),
            "pct_nh_white": _share(r["B03002_003E"], r["B03002_001E"]),
            "pct_nh_black": _share(r["B03002_004E"], r["B03002_001E"]),
            "pct_nh_asian": _share(r["B03002_006E"], r["B03002_001E"]),
            "pct_hispanic": _share(r["B03002_012E"], r["B03002_001E"]),
            "pct_renter": _share(r["B25003_003E"], r["B25003_001E"]),
        }
    )


def typology(t: pd.DataFrame, growth: str = "rent") -> pd.DataFrame:
    """Classify tracts. Needs ``pop_base``, ``income_base``, ``ba_share_base/_end`` and
    ``rent_base/_end`` (or ``income_end`` with ``growth="income"``, the P15 variant)."""
    t = t.copy()
    t["d_ba"] = t["ba_share_end"] - t["ba_share_base"]
    t["g_growth"] = t[f"{growth}_end"] / t[f"{growth}_base"] - 1
    cols = ["income_base", "d_ba", "g_growth"]
    ok = (t["pop_base"] >= MIN_POP) & t[cols].notna().all(axis=1)
    med = t.loc[ok, cols].median()
    eligible = t["income_base"] <= med["income_base"]
    gent = eligible & (t["d_ba"] > med["d_ba"]) & (t["g_growth"] > med["g_growth"])
    t["typology"] = np.select(
        [~ok, gent, eligible], TYPOLOGY[3:4] + TYPOLOGY[:2], default=TYPOLOGY[2]
    )
    return t


# --- complaints -----------------------------------------------------------------------


def count_complaints(c: pd.DataFrame) -> pd.DataFrame:
    """Tract × month × group: raw complaints and location-days."""
    c = c.assign(month=c["created_date"].dt.to_period("M"), day=c["created_date"].dt.floor("D"))
    keys = ["tract", "month", "noise_group"]
    raw = c.groupby(keys).size().rename("complaints")
    ld = (c.drop_duplicates(["noise_group", "latitude", "longitude", "day"])
          .groupby(keys).size().rename("location_days"))  # fmt: skip
    return pd.concat([raw, ld], axis=1).fillna(0).astype(int).reset_index()


def panel_grid(counts: pd.DataFrame, tracts, start: str, end: str, groups) -> pd.DataFrame:
    """Every tract × month × group, zero where nothing was reported."""
    idx = pd.MultiIndex.from_product(
        [sorted(tracts), pd.period_range(start, end, freq="M"), sorted(groups)],
        names=["tract", "month", "noise_group"],
    )
    p = counts.set_index(["tract", "month", "noise_group"]).reindex(idx, fill_value=0)
    return p.reset_index()


def load_complaints(tracts: gpd.GeoDataFrame) -> tuple[pd.DataFrame, dict]:
    years = range(int(START[:4]), int(END[:4]) + 1)
    c = pd.read_parquet(
        nyc311.OUT,
        columns=["created_date", "noise_group", "latitude", "longitude"],
        filters=[("year", "in", list(years))],
    )
    c = c[c["created_date"].dt.to_period("M").between(pd.Period(START, "M"),
                                                       pd.Period(END, "M"))]  # fmt: skip
    qa = {"complaints_in_window": len(c)}
    c = c.dropna(subset=["latitude", "longitude"])
    qa["with_coordinates"] = len(c)
    pts = gpd.GeoDataFrame(c, geometry=gpd.points_from_xy(c["longitude"], c["latitude"]),
                           crs="EPSG:4326").to_crs(tracts.crs)  # fmt: skip
    j = gpd.sjoin(pts, tracts[["tract", "geometry"]], predicate="within", how="inner")
    j = j[~j.index.duplicated()]
    qa["joined_to_tract"] = len(j)
    return pd.DataFrame(j.drop(columns=["geometry", "index_right"])), qa


# --- tract covariates -----------------------------------------------------------------


def tract_noise(year: int = 2022) -> pd.DataFrame:
    bg = pd.read_parquet(zs.PROCESSED, columns=["bg_geoid", "year", "source", "pop20",
                                                 "pop_share_ge_55", "pop_share_ge_65"])  # fmt: skip
    bg = bg[(bg["year"] == year) & bg["bg_geoid"].str[:5].isin(NYC_COUNTIES)]
    bg = bg.assign(tract=bg["bg_geoid"].str[:11])
    out = {}
    for src in ("all", "road", "aviation", "rail"):
        d = bg[bg["source"] == src]
        g = d.assign(w55=d["pop20"] * d["pop_share_ge_55"], w65=d["pop20"] * d["pop_share_ge_65"])
        g = g.groupby("tract")[["w55", "w65", "pop20"]].sum()
        out[f"{src}_pct_ge_55"] = 100 * g["w55"] / g["pop20"]
        out[f"{src}_pct_ge_65"] = 100 * g["w65"] / g["pop20"]
        out["pop20"] = g["pop20"]
    return pd.DataFrame(out).reset_index()


def build_tracts() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    geo = gpd.read_parquet(zs.CENSUS / "tract_2020.parquet", columns=["geoid", "geometry"])
    geo = geo.rename(columns={"geoid": "tract"})
    geo = geo[geo["tract"].str[:5].isin(NYC_COUNTIES)].reset_index(drop=True)
    base, end, demo = tract_acs(TYPO_BASE), tract_acs(TYPO_END), tract_acs(DEMO_YEAR)
    ty = typology(
        base[["tract", "pop", "income", "ba_share", "rent"]]
        .rename(columns={"pop": "pop_base", "income": "income_base",
                         "ba_share": "ba_share_base", "rent": "rent_base"})  # fmt: skip
        .merge(end[["tract", "ba_share", "rent"]].rename(
            columns={"ba_share": "ba_share_end", "rent": "rent_end"}), on="tract", how="left")
    )  # fmt: skip
    t = (
        geo[["tract"]]
        .merge(tract_noise(), on="tract", how="left")
        .merge(demo.rename(columns={"pop": "acs_pop", "income": "med_hh_income",
                                    "rent": "med_gross_rent"}), on="tract", how="left")
        .merge(ty[["tract", "typology", "d_ba", "g_growth"]].rename(
            columns={"g_growth": "g_rent"}), on="tract", how="left")
    )  # fmt: skip
    t["typology"] = t["typology"].fillna("Too few residents")
    t.insert(1, "borough", t["tract"].str[:5].map(NYC_COUNTIES))
    t["derived_from"] = ("BTS National Transportation Noise Map 2022; Census 2020 blocks; "
                         "ACS 5-year 2016-20, 2018-22, 2020-24 (tracts)")  # fmt: skip
    return geo, t


def run(log=print) -> dict:
    geo, tracts = build_tracts()
    log(f"{len(tracts):,} NYC tracts; typology: {tracts['typology'].value_counts().to_dict()}")
    c, qa = load_complaints(geo)
    counts = count_complaints(c)
    groups = sorted(c["noise_group"].unique())
    p = panel_grid(counts, tracts["tract"], START, END, groups)
    p["month"] = p["month"].dt.to_timestamp()
    p.to_parquet(PANEL, index=False, compression="zstd")
    tracts.to_parquet(TRACTS, index=False)
    qa.update(panel_rows=len(p), complaints_in_panel=int(p["complaints"].sum()),
              location_days_in_panel=int(p["location_days"].sum()))  # fmt: skip
    log(json.dumps(qa, indent=1))
    return {"panel": p, "tracts": tracts, "qa": qa}


def per_1000(p: pd.DataFrame, tracts: pd.DataFrame, value: str = "location_days"):
    """Complaints per 1,000 residents per year, by typology and group (2016-2025)."""
    full = p[(p["month"].dt.year >= 2016) & (p["month"].dt.year <= 2025)]
    years = full["month"].dt.year.nunique()
    t = full.groupby(["tract", "noise_group"])[value].sum().unstack()
    t = t.join(tracts.set_index("tract")[["typology", "pop20"]])
    t = t[t["pop20"] >= MIN_POP]
    g = t.groupby("typology").sum(numeric_only=True)
    rate = g.drop(columns="pop20").div(g["pop20"], axis=0) * 1000 / years
    rate["all_groups"] = rate.sum(axis=1)
    rate.insert(0, "residents_m", g["pop20"] / 1e6)
    return rate.reindex(TYPOLOGY[:3])


if __name__ == "__main__":
    res = run()
    print(per_1000(res["panel"], res["tracts"]).round(1).T.to_string())
