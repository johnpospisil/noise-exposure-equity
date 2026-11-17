"""ACS 5-year block-group demographics for the study metros, from the Census Data API.

Vintages (decision log, P02): **2018-2022** pairs with the 2022 noise map (main year) and
**2016-2020** is the earlier snapshot. Both are tabulated on 2020 block groups, so no
crosswalk (and no NHGIS) is needed.

Derived variables per block group: population, median household income (+ MOE, CV, top/bottom
coding), race/ethnicity shares (NH White, NH Black, Hispanic, NH Asian, other), renter share,
shares under 18 and 65+. Block groups are flagged, not dropped (decision P04):
``income_missing`` and ``income_cv_high`` (CV above ``acs_cv_flag`` in thresholds.yaml).

Outputs:

* ``data/raw/census/acs/{end_year}/{state}.json``: raw API responses (cache).
* ``data/processed/acs_bg.parquet``: one row per block group x vintage, metro counties only.
  Source: U.S. Census Bureau, ACS 5-year estimates (public domain).

Usage::

    uv run python -m ne.ingest.acs
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from ne import config
from ne.ingest.http import get_json

VINTAGES = {2020: "2016-2020", 2022: "2018-2022"}
RAW = config.RAW_DIR / "census" / "acs"
OUT = config.PROCESSED_DIR / "acs_bg.parquet"

UNDER18 = [f"B01001_{i:03d}E" for i in [*range(3, 7), *range(27, 31)]]
OVER65 = [f"B01001_{i:03d}E" for i in [*range(20, 26), *range(44, 50)]]
VARIABLES = [
    "B01003_001E", "B01003_001M",            # total population
    "B19013_001E", "B19013_001M",            # median household income (inflation-adj.)
    "B03002_001E", "B03002_003E", "B03002_004E", "B03002_006E", "B03002_012E",
    "B25003_001E", "B25003_003E",            # occupied units, renter-occupied
    *UNDER18, *OVER65,
]  # fmt: skip

#: ACS "annotation" values: estimate/MOE not available, controlled, etc.
#: (https://www.census.gov/data/developers/data-sets/acs-1year/notes-on-acs-estimate-and-annotation-values.html)
ANNOTATION_MAX = -100_000_000
INCOME_TOP = 250_001
INCOME_BOTTOM = 2_499
Z90 = 1.645  # ACS MOEs are 90% intervals


def fetch_state(end_year: int, state: str, refresh: bool = False) -> list[list[str]]:
    path = RAW / str(end_year) / f"{state}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    rows = get_json(
        f"https://api.census.gov/data/{end_year}/acs/acs5",
        {
            "get": ",".join(VARIABLES),
            "for": "block group:*",
            "in": [f"state:{state}", "county:*", "tract:*"],
            "key": config.CENSUS_API_KEY,
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows))
    return rows


def to_frame(rows: list[list[str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["geoid"] = df["state"] + df["county"] + df["tract"] + df["block group"]
    num = df[VARIABLES].apply(pd.to_numeric, errors="coerce")
    num = num.mask(num <= ANNOTATION_MAX)  # annotation codes -> NaN
    return pd.concat([df[["geoid"]], num], axis=1)


def _share(num: pd.Series, den: pd.Series) -> pd.Series:
    return (num / den).where(den > 0)


def derive(raw: pd.DataFrame, cv_flag: float) -> pd.DataFrame:
    """Analysis variables from raw ACS columns (see module docstring)."""
    r = raw
    inc = r["B19013_001E"]
    inc_moe = r["B19013_001M"]
    race_tot = r["B03002_001E"]
    out = pd.DataFrame(
        {
            "geoid": r["geoid"],
            "pop": r["B01003_001E"],
            "pop_moe": r["B01003_001M"],
            "med_hh_income": inc,
            "med_hh_income_moe": inc_moe,
            "med_hh_income_cv": (inc_moe / Z90) / inc,
            "income_topcoded": inc >= INCOME_TOP,
            "income_bottomcoded": inc <= INCOME_BOTTOM,
            "pct_nh_white": _share(r["B03002_003E"], race_tot),
            "pct_nh_black": _share(r["B03002_004E"], race_tot),
            "pct_nh_asian": _share(r["B03002_006E"], race_tot),
            "pct_hispanic": _share(r["B03002_012E"], race_tot),
            "households": r["B25003_001E"],
            "pct_renter": _share(r["B25003_003E"], r["B25003_001E"]),
            "pct_under18": _share(r[UNDER18].sum(axis=1, min_count=1), r["B01003_001E"]),
            "pct_65plus": _share(r[OVER65].sum(axis=1, min_count=1), r["B01003_001E"]),
        }
    )
    named = out[["pct_nh_white", "pct_nh_black", "pct_nh_asian", "pct_hispanic"]].sum(
        axis=1, min_count=4
    )
    out["pct_other"] = (1 - named).clip(lower=0)
    out["income_missing"] = inc.isna()
    out["income_cv_high"] = out["med_hh_income_cv"] > cv_flag
    return out


def run(workers: int = 6, refresh: bool = False) -> pd.DataFrame:
    metros = config.metros()
    if not metros:
        raise RuntimeError("config/metros.yaml is empty: run `python -m ne.ingest.tiger` first")
    c2m = {c: m["cbsa"] for m in metros for c in m["counties"]}
    states = sorted({s for m in metros for s in m["states"]})
    cv_flag = config.thresholds()["acs_cv_flag"]

    frames = []
    for end_year, label in VINTAGES.items():
        with ThreadPoolExecutor(workers) as ex:
            raws = list(ex.map(lambda s, y=end_year: fetch_state(y, s, refresh), states))
        raw = pd.concat([to_frame(r) for r in raws], ignore_index=True)
        raw = raw[raw["geoid"].str[:5].isin(c2m)]
        d = derive(raw, cv_flag)
        d.insert(1, "cbsa", d["geoid"].str[:5].map(c2m))
        d.insert(2, "acs_end_year", end_year)
        d.insert(3, "acs_period", label)
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    return df


def quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Missing-value and margin-of-error summary per vintage."""
    rows = []
    for (period,), g in df.groupby(["acs_period"]):
        popd = g["pop"].fillna(0)
        rows.append(
            {
                "acs_period": period,
                "block_groups": len(g),
                "zero_pop": int((popd == 0).sum()),
                "population": int(popd.sum()),
                "income_missing_bg": int(g["income_missing"].sum()),
                "income_missing_pop_share": popd[g["income_missing"]].sum() / popd.sum(),
                "income_cv_high_bg": int(g["income_cv_high"].sum()),
                "income_cv_high_pop_share": popd[g["income_cv_high"]].sum() / popd.sum(),
                "median_income_cv": g["med_hh_income_cv"].median(),
                "topcoded_bg": int(g["income_topcoded"].sum()),
                "race_missing_bg": int(g["pct_nh_white"].isna().sum()),
            }
        )
    return pd.DataFrame(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--refresh", action="store_true", help="re-download cached API responses")
    a = p.parse_args(argv)
    df = run(refresh=a.refresh)
    print(f"{OUT.relative_to(config.ROOT)}: {len(df):,} rows")
    print(quality_summary(df).round(3).T.to_string())


if __name__ == "__main__":
    main()
