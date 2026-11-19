"""Robustness grid (P15): does each key result survive alternative choices?"""

from __future__ import annotations

import numpy as np


def flags(base, value, null=0.0, base_lo=None, base_hi=None, lo=None, hi=None) -> dict:
    """Sign change relative to ``null`` and, when intervals are given, significance change."""
    sign_change = bool(np.sign(base - null) != np.sign(value - null))
    if None in (base_lo, base_hi, lo, hi):
        return {"sign_change": sign_change, "significance_change": None}
    base_sig = not (base_lo <= null <= base_hi)
    sig = not (lo <= null <= hi)
    return {"sign_change": sign_change, "significance_change": bool(base_sig != sig)}


# --- runner ---------------------------------------------------------------------------

import pandas as pd  # noqa: E402

from ne import config  # noqa: E402
from ne.build import analysis_table as at  # noqa: E402
from ne.build import nyc_panel as npn  # noqa: E402
from ne.models import complaints_nb as cnb  # noqa: E402
from ne.models import disparity as dp  # noqa: E402
from ne.models import health as hl  # noqa: E402
from ne.models import spatial_reg as sr  # noqa: E402

OUT = config.PROCESSED_DIR / "robustness_grid.csv"
DERIVED_FROM = cnb.DERIVED_FROM + "; WHO 2018 exposure-response functions"
Q1, Q5 = dp.INCOME_GROUPS[1], dp.INCOME_GROUPS[5]


def _row(result, check, variant, base, value, null=1.0, lo=None, hi=None, base_lo=None,
         base_hi=None):  # fmt: skip
    f = flags(base, value, null, base_lo, base_hi, lo, hi)
    return {"result": result, "check": check, "variant": variant, "baseline": base,
            "value": value, "lo": lo, "hi": hi, "pct_change": 100 * (value / base - 1),
            **f}  # fmt: skip


# A. descriptive disparities ------------------------------------------------------------


def _ratios(df, t=55, share="pop"):
    d = df
    if share == "area":
        d = df.drop(columns=[c for c in df if c.startswith("pop_share_ge_")])
        d = d.rename(columns=lambda c: c.replace("area_share_ge_", "pop_share_ge_"))
    inc = dp.exposure(d, "income", thresholds=[t]).set_index("group")[f"pct_ge_{t}"]
    race = dp.exposure(d, "race", thresholds=[t]).set_index("group")[f"pct_ge_{t}"]
    return {"Income Q1/Q5 ratio": inc[Q1] / inc[Q5],
            "Black/White ratio": race["Black"] / race["White"],
            "Hispanic/White ratio": race["Hispanic"] / race["White"]}  # fmt: skip


def disparity_checks(log=print) -> list[dict]:
    df = pd.read_parquet(at.OUT)
    base_df = df[(df["year"] == 2022) & (df["source"] == "all")]
    base = _ratios(base_df)
    variants = {}
    for t in (45, 50, 60, 65, 70):
        variants[("Threshold", f"{t} dBA")] = _ratios(base_df, t)
    variants[("Weighting", "area-weighted")] = _ratios(base_df, share="area")
    variants[("Map year", "2020 map")] = _ratios(df[(df["year"] == 2020) & (df["source"] == "all")])
    rel = base_df[~(base_df["income_cv_high"] | base_df["income_missing"])]
    variants[("ACS reliability", "drop CV > 0.30 / missing income")] = _ratios(rel)
    variants[("Source", "road + aviation only")] = _ratios(
        df[(df["year"] == 2022) & (df["source"] == "road_aviation")])  # fmt: skip
    rows = []
    for (check, variant), vals in variants.items():
        for k, v in vals.items():
            rows.append(_row(f"Disparity: {k} (≥ 55 dBA, 2022)", check, variant, base[k], v))
    log(f"disparity checks: {len(rows)} rows")
    return rows


# B. regression -------------------------------------------------------------------------


def _ols_q1(d, t=55, share="pop", spec="C"):
    y = 100 * d[f"{share}_share_ge_{t}"].to_numpy(float)
    r = sr.fit_ols(y, sr.design(d, spec), d["tract"])
    b, se = r["coef"]["Q1"], r["se"]["Q1"]
    return b, b - 1.96 * se, b + 1.96 * se


def regression_checks(log=print) -> list[dict]:
    d22 = sr.load_sample(2022, "all")
    rows = []
    for spec in ("A", "C"):
        res = f"Regression: Q1 vs Q5 gap, spec {spec} (pp, OLS)"
        b, blo, bhi = _ols_q1(d22, spec=spec)
        rel = d22[~(d22["income_cv_high"] | d22["income_missing"])]
        variants = {
            ("Threshold", "65 dBA outcome"): _ols_q1(d22, 65, spec=spec),
            ("Weighting", "area-weighted outcome"): _ols_q1(d22, share="area", spec=spec),
            ("ACS reliability", "drop CV > 0.30 / missing income"): _ols_q1(rel, spec=spec),
            ("Map year", "2020 map"): _ols_q1(sr.load_sample(2020, "all"), spec=spec),
        }
        for (check, variant), (v, lo, hi) in variants.items():
            rows.append(_row(res, check, variant, b, v, 0.0, lo, hi, blo, bhi))
    # spatial terms (spec C, from the P11 table)
    p = pd.read_csv(config.PROCESSED_DIR / "spatial_models_pooled.csv")
    p = p[(p["term"] == "Q1") & (p["outcome"] == "pct_ge_55") & (p["spec"] == "C")]
    ols = p[p["model"].str.startswith("OLS")].iloc[0]
    for model in ("Spatial lag (GM)", "Spatial error (GM, het.)"):
        r = p[p["model"] == model].iloc[0]
        rows.append(_row("Regression: Q1 vs Q5 gap, spec C (pp, OLS)", "Spatial terms", model,
                         ols["coef"], r["coef"], 0.0, r["coef"] - 1.96 * r["se"],
                         r["coef"] + 1.96 * r["se"], ols["coef"] - 1.96 * ols["se"],
                         ols["coef"] + 1.96 * ols["se"]))  # fmt: skip
    log(f"regression checks: {len(rows)} rows")
    return rows


# C. NYC complaints ---------------------------------------------------------------------

ALT_REF = cnb.FORMULAS["M2"].replace(f"Treatment('{cnb.REF}')",
                                     "Treatment('Low-income, not gentrifying')")  # fmt: skip


def _nb(d):
    r = cnb.fit_nb(d, ALT_REF)
    k = next(x for x in r["irr"].index if x.endswith("[T.Low-income, gentrifying]"))
    return {"Gentrifying vs other low-income (rate ratio)": (r["irr"][k], r["lo"][k], r["hi"][k]),
            "Modelled noise, per 10 pts (rate ratio)": (r["irr"]["noise_10"],
                                                        r["lo"]["noise_10"],
                                                        r["hi"]["noise_10"])}  # fmt: skip


def alt_typology() -> pd.Series:
    base, end = npn.tract_acs(npn.TYPO_BASE), npn.tract_acs(npn.TYPO_END)
    b = base[["tract", "pop", "income", "ba_share"]].rename(
        columns={"pop": "pop_base", "income": "income_base", "ba_share": "ba_share_base"}
    )
    e = end[["tract", "income", "ba_share"]].rename(
        columns={"income": "income_end", "ba_share": "ba_share_end"}
    )
    t = b.merge(e, on="tract")
    return npn.typology(t, growth="income").set_index("tract")["typology"]


def nyc_checks(log=print) -> list[dict]:
    d = cnb.model_data("location_days", "combined")
    base = _nb(d)
    alt = alt_typology()
    d_alt = d.assign(typology=d["tract"].map(alt))
    d_alt = d_alt[d_alt["typology"] != "Too few residents"]
    top = d.groupby("tract")["complaints"].sum()
    variants = {
        ("Outcome", "raw complaint counts"): _nb(cnb.model_data("complaints", "combined")),
        ("Outliers", "without top 1% tracts"): _nb(
            d[~d["tract"].isin(top[top >= top.quantile(0.99)].index)]
        ),
        ("Geography", "excluding Manhattan"): _nb(d[d["borough"] != "Manhattan"]),
        ("Typology", "income growth instead of rent growth"): _nb(d_alt),
        ("Noise measure", "major roads only"): _nb(d.assign(noise_10=d["road_pct_ge_55"] / 10)),
    }
    for g in cnb.MODEL_GROUPS:
        variants[("Complaint type", g)] = _nb(cnb.model_data("location_days", g))
    rows = []
    for (check, variant), vals in variants.items():
        for k, (v, lo, hi) in vals.items():
            b, blo, bhi = base[k]
            rows.append(_row(f"NYC: {k}", check, variant, b, v, 1.0, lo, hi, blo, bhi))
    log(f"NYC checks: {len(rows)} rows")
    return rows


# D. health -----------------------------------------------------------------------------

HEALTH = [("aviation", "HA"), ("road", "HA"), ("rail", "HSD")]


def _excess(df, source, outcome, **kw):
    return hl.cases(df[df["source"] == source], source, outcome, **kw)["excess"].sum()


def health_checks(log=print) -> list[dict]:
    df = pd.read_parquet(at.OUT)
    d22, d20 = df[df["year"] == 2022], df[df["year"] == 2020]
    rows = []
    for source, outcome in HEALTH:
        res = f"Health: extra {outcome} residents, {source} (millions)"
        b = _excess(d22, source, outcome) / 1e6
        variants = {
            ("Censored floor", "residents < 45 dBA at 42.5 dBA"):
                _excess(d22, source, outcome, below45=42.5),
            ("Censored floor", "residents < 45 dBA at 45 dBA"):
                _excess(d22, source, outcome, below45=45.0),
            ("Band position", "lower band edge, offset −2 dB"):
                _excess(d22, source, outcome, scenario="low"),
            ("Band position", "upper band edge, offset +2 dB"):
                _excess(d22, source, outcome, scenario="high"),
            ("Map year", "2020 map"): _excess(d20, source, outcome),
        }  # fmt: skip
        if source == "rail":
            for s in (-2.0, 2.0):
                variants[("Rail night offset", f"{s:+.0f} dB")] = _excess(
                    d22, source, outcome, extra_shift=s)  # fmt: skip
        for (check, variant), v in variants.items():
            rows.append(_row(res, check, variant, b, v / 1e6, 0.0))
    log(f"health checks: {len(rows)} rows")
    return rows


def run(log=print) -> pd.DataFrame:
    rows = disparity_checks(log) + regression_checks(log) + nyc_checks(log) + health_checks(log)
    grid = pd.DataFrame(rows)
    grid["derived_from"] = DERIVED_FROM
    grid.round(4).to_csv(OUT, index=False)
    return grid


if __name__ == "__main__":
    g = run()
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    cols = ["result", "check", "variant", "baseline", "value", "lo", "hi", "sign_change",
            "significance_change"]  # fmt: skip
    print(g[cols].round(3).to_string(index=False))
