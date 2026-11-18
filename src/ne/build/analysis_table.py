"""Analysis table: block-group noise + ACS demographics + metro, on 2020 block groups.

* Noise: ``data/processed/bg_noise.parquet`` (P08), every map year and source.
* Demographics: ACS 5-year from the Census API (P04), both vintages on 2020 block groups,
  so no crosswalk (and no NHGIS) is needed. Pairing (``ACS_FOR_MAP``): the 2016 and 2018
  maps take ACS 2016-20; the 2020 and 2022 maps take ACS 2018-22.
* ``income_quintile``: 1 (lowest) to 5, **within each metro**, weighted by ACS population
  so each quintile holds about a fifth of the metro's residents (decision P04). Block
  groups without an income estimate or without residents get no quintile.
* ACS reliability flags are kept (``income_cv_high``, ``income_missing``); P15 drops them.

Usage::

    uv run python -m ne.build.analysis_table
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ne import config
from ne.build import zonal_stats as zs
from ne.ingest import acs

OUT = config.PROCESSED_DIR / "analysis_bg.parquet"
ACS_FOR_MAP = {2016: 2020, 2018: 2020, 2020: 2022, 2022: 2022}
QUINTILE_LABELS = {1: "Q1 (lowest)", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5 (highest)"}

ACS_COLS = [
    "pop", "med_hh_income", "med_hh_income_cv", "income_missing", "income_cv_high",
    "income_topcoded", "pct_nh_white", "pct_nh_black", "pct_hispanic", "pct_nh_asian",
    "pct_other", "pct_renter", "pct_under18", "pct_65plus", "households",
]  # fmt: skip


def income_quintiles(df: pd.DataFrame, by: str = "cbsa") -> pd.Series:
    """Population-weighted income quintile (1-5) of each row within its ``by`` group.

    Rows are ranked by income; a row's quintile is set by the population midpoint of its
    position in the cumulative distribution.
    """
    ok = df["med_hh_income"].notna() & (df["pop"] > 0)
    d = df.loc[ok, [by, "med_hh_income", "pop"]].sort_values([by, "med_hh_income"])
    w = d["pop"].astype(float)
    cum = w.groupby(d[by]).cumsum()
    total = w.groupby(d[by]).transform("sum")
    mid = (cum - w / 2) / total
    q = np.clip(np.floor(mid * 5).astype(int) + 1, 1, 5)
    return pd.Series(q, index=d.index).reindex(df.index).astype("Int8")


def build() -> pd.DataFrame:
    noise = pd.read_parquet(zs.PROCESSED)
    demo = pd.read_parquet(acs.OUT).rename(columns={"geoid": "bg_geoid"})
    demo["income_quintile"] = demo.groupby("acs_end_year", group_keys=False).apply(
        lambda g: income_quintiles(g)
    )
    demo = demo[["bg_geoid", "acs_end_year", *ACS_COLS, "income_quintile"]]

    noise["acs_end_year"] = noise["year"].map(ACS_FOR_MAP).astype("int16")
    demo["acs_end_year"] = demo["acs_end_year"].astype("int16")
    df = noise.merge(demo, on=["bg_geoid", "acs_end_year"], how="left", validate="m:1")
    names = {m["cbsa"]: m["short"] for m in config.metros()}
    df.insert(1, "metro", df["cbsa"].map(names))
    floats = df.select_dtypes("float64").columns
    df[floats] = df[floats].astype("float32")
    # rows of one block group sit together, so repeated ACS values compress well (< 50 MB)
    df = df.sort_values(["cbsa", "bg_geoid", "year", "source"], ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False, compression="zstd", compression_level=9)
    return df


def describe(df: pd.DataFrame, year: int = 2022, source: str = "all") -> pd.DataFrame:
    """Per metro: block groups, residents, income cut-offs, flags, and headline shares."""
    d = df[(df["year"] == year) & (df["source"] == source)]

    def one(g):
        w = g["pop20"]
        return pd.Series(
            {
                "block_groups": len(g),
                "pop20_m": w.sum() / 1e6,
                "median_income_q1": g.loc[g["income_quintile"] == 1, "med_hh_income"].median(),
                "median_income_q5": g.loc[g["income_quintile"] == 5, "med_hh_income"].median(),
                "pct_pop_income_missing": 100 * w[g["income_missing"]].sum() / w.sum(),
                "pct_pop_cv_high": 100 * w[g["income_cv_high"]].sum() / w.sum(),
                "pct_ge_55": 100 * (w * g["pop_share_ge_55"]).sum() / w.sum(),
                "pct_ge_65": 100 * (w * g["pop_share_ge_65"]).sum() / w.sum(),
            }
        )

    return d.groupby("metro").apply(one).sort_values("pop20_m", ascending=False)


if __name__ == "__main__":
    t = build()
    print(f"{OUT.relative_to(config.ROOT)}: {len(t):,} rows, {OUT.stat().st_size / 1e6:.1f} MB")
    print(describe(t).round(1).to_string())
