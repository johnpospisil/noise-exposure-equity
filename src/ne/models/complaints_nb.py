"""Negative binomial models: who complains about noise, given modelled noise (P13).

Unit: NYC 2020 census tract × year (2016-2025), tracts with at least 500 residents.
Outcome: 311 **location-days** (decision P05) for residential, street/sidewalk, vehicle and
commercial complaints, separately and combined. Helicopter complaints are left out
(decision P12). Offset: log 2020 population, so coefficients are rate ratios per resident.

Models (NB2, standard errors clustered by tract; year and borough fixed effects):

* **M1**: modelled noise (share of residents ≥ 55 dBA, per 10 points) + typology.
* **M2**: M1 + race/ethnicity shares, renter share (per 10 points), log median income.
* **M3**: M2 + noise × typology.

Robustness: M2 with raw counts, and M2 without the top 1% of tracts by raw complaints.

311 complaints measure *reporting*, not noise. Modelled noise is not measured noise, and
it misses most sources people complain about (neighbours, bars, construction). Tract
associations, not individual behaviour.

Usage::

    uv run python -m ne.models.complaints_nb
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from ne import config
from ne.build import nyc_panel as npn

MODEL_GROUPS = ["residential", "street", "vehicle", "commercial"]
REF = "Higher-income"
TYPO = f"C(typology, Treatment('{REF}'))"
FE = "C(borough) + C(year)"
DEMO = "black_10 + hispanic_10 + asian_10 + renter_10 + log_income"
FORMULAS = {
    "M1": f"y ~ noise_10 + {TYPO} + {FE}",
    "M2": f"y ~ noise_10 + {TYPO} + {DEMO} + {FE}",
    "M3": f"y ~ noise_10 * {TYPO} + {DEMO} + {FE}",
}
YEARS = (2016, 2025)
OUT = config.PROCESSED_DIR / "complaints_nb_models.csv"
MARGINS = config.PROCESSED_DIR / "complaints_nb_margins.csv"
DERIVED_FROM = ("NYC Open Data 311 (tract-level location-days); BTS 2022; Census 2020; "
                "ACS 5-year 2016-20, 2018-22, 2020-24 (tracts)")  # fmt: skip


# --- data -----------------------------------------------------------------------------


def tract_years(p: pd.DataFrame, years=YEARS) -> pd.DataFrame:
    """Monthly panel -> tract × year × group sums, complete years only."""
    p = p.assign(year=p["month"].dt.year)
    p = p[p["year"].between(*years)]
    return p.groupby(["tract", "year", "noise_group"], as_index=False)[
        ["complaints", "location_days"]
    ].sum()


def model_data(value: str = "location_days", group: str = "combined") -> pd.DataFrame:
    p = pd.read_parquet(npn.PANEL)
    t = pd.read_parquet(npn.TRACTS)
    ty = tract_years(p[p["noise_group"].isin(MODEL_GROUPS)])
    if group == "combined":
        ty = ty.groupby(["tract", "year"], as_index=False)[["complaints", "location_days"]].sum()
    else:
        ty = ty[ty["noise_group"] == group]
    t = t[(t["pop20"] >= npn.MIN_POP) & (t["typology"] != "Too few residents")]
    d = ty.merge(t, on="tract", how="inner")
    d = d.assign(
        y=d[value],
        noise_10=d["all_pct_ge_55"] / 10,
        black_10=d["pct_nh_black"] * 10,
        hispanic_10=d["pct_hispanic"] * 10,
        asian_10=d["pct_nh_asian"] * 10,
        renter_10=d["pct_renter"] * 10,
        log_income=np.log(d["med_hh_income"]),
    )
    cols = ["y", "noise_10", "black_10", "hispanic_10", "asian_10", "renter_10", "log_income"]
    return d.dropna(subset=cols).reset_index(drop=True)


# --- model ----------------------------------------------------------------------------


def fit_nb(d: pd.DataFrame, formula: str, cluster: str = "tract") -> dict:
    """NB2 with log-population offset and tract-clustered standard errors."""
    groups = pd.factorize(d[cluster])[0]
    m = smf.negativebinomial(formula, d, offset=np.log(d["pop20"].astype(float)))
    r = m.fit(cov_type="cluster", cov_kwds={"groups": groups}, disp=0, maxiter=300)
    params, ci = r.params, r.conf_int()
    keep = [k for k in params.index if k != "alpha"]
    return {
        "result": r,
        "irr": np.exp(params[keep]),
        "lo": np.exp(ci.loc[keep, 0]),
        "hi": np.exp(ci.loc[keep, 1]),
        "p": r.pvalues[keep],
        "alpha": float(params["alpha"]),
        "n": int(r.nobs),
        "converged": bool(r.mle_retvals.get("converged", True)),
    }


def _rows(res: dict, group: str, model: str, variant: str) -> list[dict]:
    out = []
    for k in res["irr"].index:
        if k.startswith(("C(borough)", "C(year)")) or k == "Intercept":
            continue
        term = k.split("[T.")[-1].rstrip("]") if "[T." in k else k
        if ":" in k:
            term = "noise_10:" + term
        out.append({"group": group, "model": model, "variant": variant, "term": term,
                    "irr": res["irr"][k], "lo": res["lo"][k], "hi": res["hi"][k],
                    "p": res["p"][k], "alpha": res["alpha"], "n": res["n"],
                    "converged": res["converged"]})  # fmt: skip
    return out


NOISE_GRID = tuple(range(0, 81, 5))


def margins(res: dict, d: pd.DataFrame, noise=NOISE_GRID, n_sim: int = 500,
            seed: int = 0) -> pd.DataFrame:  # fmt: skip
    """Average predicted location-days per 1,000 residents per year, by typology and noise.

    Every tract-year is set to the given noise level and typology (other covariates as
    observed); predictions are averaged. 95% bands from simulated coefficient draws.
    """
    r = res["result"]
    from patsy import build_design_matrices

    info = r.model.data.model_spec  # patsy DesignInfo (statsmodels 0.15)
    names = list(r.params.index[:-1])  # without alpha
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(r.params[names], r.cov_params().loc[names, names], n_sim)
    rows = []
    for typ in ["Low-income, gentrifying", "Low-income, not gentrifying", REF]:
        for lvl in noise:
            nd = d.assign(noise_10=lvl / 10, typology=typ)
            X = np.asarray(build_design_matrices([info], nd)[0])
            point = np.exp(X @ r.params[names].to_numpy()).mean() * 1000
            sims = np.exp(X @ draws.T).mean(axis=0) * 1000
            lo, hi = np.percentile(sims, [2.5, 97.5])
            rows.append({"typology": typ, "pct_ge_55": lvl, "rate": point, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def run(log=print) -> dict:
    rows = []
    fits = {}
    for group in ["combined", *MODEL_GROUPS]:
        d = model_data("location_days", group)
        for model, f in FORMULAS.items():
            res = fit_nb(d, f)
            fits[(group, model)] = (res, d)
            rows += _rows(res, group, model, "location-days")
        # robustness on M2
        rows += _rows(fit_nb(model_data("complaints", group), FORMULAS["M2"]), group, "M2",
                      "raw counts")  # fmt: skip
        top = d.groupby("tract")["complaints"].sum()
        drop = top[top >= top.quantile(0.99)].index
        rows += _rows(fit_nb(d[~d["tract"].isin(drop)], FORMULAS["M2"]), group, "M2",
                      "without top 1% tracts")  # fmt: skip
        # direct contrast: gentrifying vs other low-income tracts (M2, re-referenced)
        alt = FORMULAS["M2"].replace(f"Treatment('{REF}')",
                                     "Treatment('Low-income, not gentrifying')")  # fmt: skip
        rows += _rows(fit_nb(d, alt), group, "M2", "ref: low-income, not gentrifying")
        m2 = fits[(group, "M2")][0]
        log(f"{group:12s} n={m2['n']:,} noise IRR={m2['irr']['noise_10']:.3f} "
            f"alpha={m2['alpha']:.2f}")  # fmt: skip
    table = pd.DataFrame(rows)
    table["derived_from"] = DERIVED_FROM
    table.round(4).to_csv(OUT, index=False)
    res3, d3 = fits[("combined", "M3")]
    mg = margins(res3, d3)
    mg["derived_from"] = DERIVED_FROM
    mg.round(3).to_csv(MARGINS, index=False)
    return {"table": table, "margins": mg}


if __name__ == "__main__":
    out = run()
    t = out["table"]
    show = t[(t["variant"] == "location-days") & ~t["term"].str.contains(":")]
    print(show.pivot_table(index=["group", "term"], columns="model", values="irr", sort=False)
          .round(3).to_string())  # fmt: skip
    print(t[t["term"].str.contains(":")][["group", "term", "irr", "lo", "hi", "p"]]
          .round(3).to_string(index=False))  # fmt: skip
    print(t[(t["model"] == "M2") & (t["term"] == "noise_10")]
          [["group", "variant", "irr", "lo", "hi"]].round(3).to_string(index=False))  # fmt: skip
