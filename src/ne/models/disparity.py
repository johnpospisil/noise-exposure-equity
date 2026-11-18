"""Exposure disparities: who lives with modelled transportation noise (P10).

For a group (income quintile, or race/ethnicity), the exposure share at threshold T is
the population-weighted share of the group's residents who live in blocks at or above T:

    pct_ge_T = 100 · Σ_bg (residents_g,bg · pop_share_ge_T,bg) / Σ_bg residents_g,bg

* Income: ``residents = pop20`` of block groups in that within-metro quintile.
* Race/ethnicity: ``residents = pop20 · pct_group`` (ACS shares applied to 2020 counts).

"Pooled" rows treat the 20 metros as one population. Neighbourhood-level only
(ecological); modelled, not measured noise; road = major roads (BTS model).

Usage::

    uv run python -m ne.models.disparity
"""

from __future__ import annotations

import pandas as pd

from ne import config
from ne.build import analysis_table as at

RACE_GROUPS = {
    "pct_nh_white": "White",
    "pct_nh_black": "Black",
    "pct_hispanic": "Hispanic",
    "pct_nh_asian": "Asian",
    "pct_other": "Other",
}
INCOME_GROUPS = at.QUINTILE_LABELS
THRESHOLDS = (45, 50, 55, 60, 65, 70)
POOLED = "All 20 metros"
DERIVED_FROM = (
    "BTS National Transportation Noise Map; Census 2020 blocks (POP20); ACS 5-year (B19013, B03002)"
)
OUT_DIR = config.PROCESSED_DIR


def _long(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """One row per block group × group with a ``residents`` weight."""
    if kind == "income":
        d = df[df["income_quintile"].notna()].copy()
        d["group"] = d["income_quintile"].astype(int).map(INCOME_GROUPS)
        d["residents"] = d["pop20"].astype(float)
        return d
    if kind == "race":
        parts = []
        for col, label in RACE_GROUPS.items():
            d = df.copy()
            d["group"] = label
            d["residents"] = d["pop20"] * d[col].fillna(0)
            parts.append(d)
        return pd.concat(parts, ignore_index=True)
    raise ValueError(kind)


def exposure(df: pd.DataFrame, kind: str, by=(), thresholds=None) -> pd.DataFrame:
    """Percent of each group's residents at or above each threshold."""
    thresholds = thresholds or [t for t in THRESHOLDS if f"pop_share_ge_{t}" in df.columns]
    d = _long(df, kind)
    keys = [*by, "group"]
    cols = {f"pct_ge_{t}": d["residents"] * d[f"pop_share_ge_{t}"] for t in thresholds}
    w = pd.DataFrame({**{k: d[k] for k in keys}, "residents": d["residents"], **cols})
    g = w.groupby(keys, sort=False, observed=True).sum()
    out = g[list(cols)].div(g["residents"], axis=0) * 100
    out.insert(0, "residents", g["residents"])
    order = list(INCOME_GROUPS.values()) if kind == "income" else list(RACE_GROUPS.values())
    out = out.reset_index()
    out["group"] = pd.Categorical(out["group"], categories=order, ordered=True)
    return out.sort_values([*by, "group"]).reset_index(drop=True)


def ratios(t: pd.DataFrame, reference: str, value: str = "pct_ge_65", by=()) -> pd.DataFrame:
    """Each group's exposure divided by the reference group's (e.g. Q1 / Q5)."""
    by = list(by)
    ref = t[t["group"] == reference].set_index(by)[value] if by else None
    out = t[[*by, "group", value]].copy()
    if by:
        out["ratio"] = out[value] / out.set_index(by).index.map(ref).to_numpy()
    else:
        out["ratio"] = out[value] / t.loc[t["group"] == reference, value].iloc[0]
    return out


def tables(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Per metro and pooled, every year and source."""
    per = exposure(df, kind, by=("metro", "year", "source"))
    pooled = exposure(df, kind, by=("year", "source")).assign(metro=POOLED)
    out = pd.concat([pooled, per], ignore_index=True)
    out["group"] = out["group"].astype(str)
    out["derived_from"] = DERIVED_FROM
    return out[["metro", "year", "source", "group", "residents",
                *[c for c in out if c.startswith("pct_ge_")], "derived_from"]]  # fmt: skip


def run() -> dict[str, pd.DataFrame]:
    df = pd.read_parquet(at.OUT)
    out = {}
    for kind in ("income", "race"):
        t = tables(df, kind)
        t.round(3).to_csv(OUT_DIR / f"disparity_{kind}.csv", index=False)
        out[kind] = t
    return out


if __name__ == "__main__":
    res = run()
    for kind, t in res.items():
        p = t[(t["metro"] == POOLED) & (t["year"] == 2022)]
        print(f"\n{kind} (pooled, 2022)")
        print(p.pivot_table(index="group", columns="source", values="pct_ge_65", sort=False)
              .round(2).to_string())  # fmt: skip
        print(p.pivot_table(index="group", columns="source", values="pct_ge_55", sort=False)
              .round(2).to_string())  # fmt: skip
