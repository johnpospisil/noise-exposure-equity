"""Data for the address lookup app (P18): one small JSON file per state.

``app/data/{state}.json`` maps each 2020 block group to a compact array (see ``FIELDS``);
``app/data/meta.json`` holds field names, metro names, metro averages and the caveats.
Values come from the 2022 BTS map and ACS 2018-22, as in the report. Neighbourhood-level
only: the app never reports a value for an individual address.

Usage::

    uv run python -m ne.build.app_data
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ne import config
from ne.build import analysis_table as at

OUT = config.ROOT / "app" / "data"
SOURCES = ["all", "road", "rail", "aviation"]
THRESHOLDS = [55, 65]
FIELDS = ["metro", "pop", "income", *[f"{s}_{t}" for s in SOURCES for t in THRESHOLDS], "pct"]
YEAR = 2022


def weighted_percentile(d: pd.DataFrame, col: str, by: str = "cbsa") -> pd.Series:
    """Share of the metro's residents (in %) living in block groups with a lower value;
    residents in block groups with an equal value count half."""
    out = pd.Series(np.nan, index=d.index)
    for _, g in d.groupby(by):
        v, w = g[col].to_numpy(float), g["pop20"].to_numpy(float)
        order = np.argsort(v, kind="stable")
        vs, ws = v[order], w[order]
        total = ws.sum()
        uniq, start = np.unique(vs, return_index=True)
        cum = np.concatenate([[0.0], np.cumsum(ws)])
        below = cum[start]  # residents strictly below each unique value
        tie = np.add.reduceat(ws, start)
        pct_u = 100 * (below + tie / 2) / total
        out.loc[g.index] = pct_u[np.searchsorted(uniq, v)]
    return out


def _pct(x) -> float | None:
    return None if pd.isna(x) else round(100 * float(x), 1)


def record(r: pd.Series, metro_index: dict) -> list:
    vals = [metro_index[r["metro"]], int(r["pop20"]),
            None if pd.isna(r["med_hh_income"]) else int(round(r["med_hh_income"]))]  # fmt: skip
    vals += [_pct(r[f"{s}_{t}"]) for s in SOURCES for t in THRESHOLDS]
    vals.append(None if pd.isna(r["pct"]) else int(round(r["pct"])))
    return vals


def build() -> dict:
    df = pd.read_parquet(at.OUT)
    df = df[df["year"] == YEAR]
    # pivot, not pivot_table: keep block groups without residents (all values NaN)
    wide = df.pivot(index="bg_geoid", columns="source",
                    values=[f"pop_share_ge_{t}" for t in THRESHOLDS])  # fmt: skip
    wide.columns = [f"{s}_{c.rsplit('_', 1)[1]}" for c, s in wide.columns]
    base = df[df["source"] == "all"][["bg_geoid", "cbsa", "metro", "pop20", "med_hh_income"]]
    d = base.merge(wide.reset_index(), on="bg_geoid").reset_index(drop=True)
    d["pct"] = weighted_percentile(d, "all_55")
    d.loc[d["pop20"] == 0, "pct"] = np.nan

    metros = [m["short"] for m in config.metros()]
    idx = {m: i for i, m in enumerate(metros)}
    OUT.mkdir(parents=True, exist_ok=True)
    states = sorted(d["bg_geoid"].str[:2].unique())
    for st in states:
        g = d[d["bg_geoid"].str[:2] == st]
        payload = {r["bg_geoid"]: record(r, idx) for _, r in g.iterrows()}
        (OUT / f"{st}.json").write_text(json.dumps(payload, separators=(",", ":")))
    avg = {}
    for m, g in d.groupby("metro"):
        w = g["pop20"]
        avg[m] = round(100 * float((w * g["all_55"]).sum() / w.sum()), 1)
    meta = {
        "fields": FIELDS,
        "metros": metros,
        "metro_all_55": avg,
        "states": states,
        "year": YEAR,
        "sources": ("BTS National Transportation Noise Map (2022); U.S. Census Bureau "
                    "(2020 Census blocks and block groups; ACS 2018-22 via the Census API)"),
        "caveat": ("Modelled, not measured. Values describe the neighbourhood (census block "
                   "group), not an individual address. Road = major roads only; rail excludes "
                   "subways. BTS: the map should not be used to evaluate noise levels at "
                   "individual locations."),
    }  # fmt: skip
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


if __name__ == "__main__":
    meta = build()
    sizes = {p.name: p.stat().st_size for p in OUT.glob("*.json")}
    print(f"{len(sizes)} files, {sum(sizes.values()) / 1e6:.1f} MB; largest "
          f"{max(sizes, key=sizes.get)} {max(sizes.values()) / 1e6:.1f} MB")  # fmt: skip
