"""WHO health translation: estimated highly annoyed (HA) and highly sleep-disturbed (HSD)
residents from block-group exposure (P14).

Method (decisions P06, P14):

1. Residents of each block group are split into 5-dB LAeq,24h bands (45-50, ..., 70-75)
   from the cumulative shares in the analysis table (2022 map). Residents below 45 dBA are
   censored and get no estimated cases (the curves are not defined there for our levels).
2. Each band is given a level (``SCENARIOS``) and converted to Lden / Lnight with the
   per-source offsets in ``config/thresholds.yaml`` (shifted ±2 dB in the low/high cases).
3. The WHO 2018 curves (``who_erf``) give % HA (Lden) and % HSD (Lnight) per source.
4. **Excess** cases (headline) = residents × (curve at the band level − curve at the WHO
   guideline level), for bands above the guideline. **Total** cases = residents × curve.

Sources are estimated separately and **not added**: someone annoyed by both road and
rail noise would be counted twice. Ranges are **assumption ranges** (band position and
conversion offset), not statistical confidence intervals; the curves' own confidence
intervals are not included. Modelled noise, neighbourhood-level, estimates only.

Usage::

    uv run python -m ne.models.health
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ne import config
from ne.build import analysis_table as at
from ne.models import disparity as dp
from ne.models import who_erf as erf

BAND_EDGES = [45, 50, 55, 60, 65, 70, 75]
SOURCES = ["road", "rail", "aviation"]
OUTCOMES = {"HA": ("to_lden", "pct_ha", "lden_offset"),
            "HSD": ("to_lnight", "pct_hsd", "lnight_offset")}  # fmt: skip
#: WHO 2018 guideline levels (Lden for HA, Lnight for HSD)
WHO_GUIDELINE = {
    "HA": {"road": 53.0, "rail": 54.0, "aviation": 45.0},
    "HSD": {"road": 45.0, "rail": 44.0, "aviation": 40.0},
}
#: scenario -> (level within band, shift of the conversion offset in dB)
SCENARIOS = {"low": ("band_lo", -2.0), "central": ("mid", 0.0), "high": ("band_hi", 2.0)}
OUT = config.PROCESSED_DIR / "health_estimates.csv"
OUT_INCOME = config.PROCESSED_DIR / "health_by_income.csv"
DERIVED_FROM = (dp.DERIVED_FROM + "; WHO 2018 exposure-response functions (Guski et al. 2017; "
                "Basner & McGuire 2018)")  # fmt: skip


def bands(bg: pd.DataFrame) -> pd.DataFrame:
    """Long table: one row per block group × 5-dB band with ``residents``."""
    share_cols = [f"pop_share_ge_{t}" for t in BAND_EDGES[:-1]]
    keep = [c for c in bg.columns if not c.startswith(("pop_share_ge_", "area_share_ge_"))]
    parts = []
    for i, lo in enumerate(BAND_EDGES[:-1]):
        upper = bg[share_cols[i + 1]] if i + 1 < len(share_cols) else 0.0
        share = (bg[share_cols[i]] - upper).clip(lower=0)
        parts.append(bg[keep].assign(band_lo=lo, band_hi=BAND_EDGES[i + 1],
                                     mid=lo + 2.5, residents=bg["pop20"] * share))  # fmt: skip
    return pd.concat(parts, ignore_index=True)


def cases(bg: pd.DataFrame, source: str, outcome: str, scenario: str = "central"):
    """Per block group × band: estimated total and excess cases for one source/outcome."""
    to_metric, curve, offset_key = OUTCOMES[outcome]
    level_col, shift = SCENARIOS[scenario]
    b = bands(bg)
    offset = float(config.thresholds()["metric_offsets_db"][source][offset_key]) + shift
    metric = getattr(erf, to_metric)(b[level_col].to_numpy(float), source, offset=offset)
    pct = np.asarray(getattr(erf, curve)(metric, source))
    guide = WHO_GUIDELINE[outcome][source]
    pct_guide = float(getattr(erf, curve)(guide, source))
    extra = np.where(metric > guide, np.clip(pct - pct_guide, 0, None), 0.0)
    return b.assign(metric_db=metric, total=b["residents"] * pct / 100,
                    excess=b["residents"] * extra / 100)  # fmt: skip


def _summarise(by: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(at.OUT)
    df = df[df["year"] == 2022]
    rows = []
    for source in SOURCES:
        d = df[df["source"] == source]
        for outcome in OUTCOMES:
            res = {}
            for sc in SCENARIOS:
                c = cases(d, source, outcome, sc)
                c = c.assign(_all=dp.POOLED)
                for keys in ([*by], ["_all"]) if by == ["metro"] else ([*by],):
                    g = c.groupby(keys)[["total", "excess"]].sum()
                    g.index = g.index.rename(by[0]) if keys == ["_all"] else g.index
                    res.setdefault(sc, []).append(g)
            pop = d.groupby(by)["pop20"].sum()
            if by == ["metro"]:
                pop = pd.concat([pd.Series({dp.POOLED: d["pop20"].sum()}), pop])
            central = pd.concat(res["central"])
            low, high = pd.concat(res["low"]), pd.concat(res["high"])
            out = pd.DataFrame({
                "residents": pop.reindex(central.index),
                "excess": central["excess"], "excess_low": low["excess"],
                "excess_high": high["excess"],
                "total": central["total"], "total_low": low["total"],
                "total_high": high["total"],
            })  # fmt: skip
            for c in ("excess", "excess_low", "excess_high", "total"):
                out[f"{c}_per_1000"] = out[c] / out["residents"] * 1000
            rows.append(out.reset_index().assign(source=source, outcome=outcome))
    out = pd.concat(rows, ignore_index=True)
    out["derived_from"] = DERIVED_FROM
    return out


def run() -> dict[str, pd.DataFrame]:
    metro = _summarise(["metro"])
    metro.round(2).to_csv(OUT, index=False)
    inc = _summarise(["income_quintile"])
    inc["income_quintile"] = inc["income_quintile"].astype(int).map(dp.INCOME_GROUPS)
    inc.round(3).to_csv(OUT_INCOME, index=False)
    return {"metro": metro, "income": inc}


if __name__ == "__main__":
    r = run()
    m = r["metro"]
    p = m[m["metro"] == dp.POOLED]
    print(p[["source", "outcome", "excess", "excess_low", "excess_high", "total",
             "excess_per_1000"]].round(0).to_string(index=False))  # fmt: skip
    i = r["income"]
    print(i.pivot_table(index="income_quintile", columns=["outcome", "source"],
                        values="excess_per_1000", sort=False).round(1).to_string())  # fmt: skip
