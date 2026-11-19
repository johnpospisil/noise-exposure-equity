"""Regression and spatial models of block-group noise exposure (P11).

Outcome: percent of a block group's residents in blocks at or above 55 dBA (65 as the
stricter test), 2022 map, road + rail + aviation. Units: 2020 block groups with residents
and an ACS income estimate.

Specifications (metro fixed effects in pooled models):

* **A**: income quintile dummies (Q1-Q4; reference Q5, the highest-income fifth).
* **B**: A + race/ethnicity shares, per 10 percentage points (reference: NH White).
* **C**: B + renter share (per 10 points) + log population density (residents per km²).

Estimators: OLS with standard errors clustered by tract; then, because neighbouring block
groups share roads and flight paths, spatial models on Queen contiguity weights built
**within each metro** (row-standardised): a spatial lag model (``GM_Lag``, 2SLS) and a
spatial error model (``GM_Error_Het``, heteroskedasticity-robust). LM diagnostics and
Moran's I come from ``spreg.OLS``. In the lag model a coefficient is a direct effect
before spillovers; ``total`` = beta / (1 - rho).

Neighbourhood-level associations, not individual effects and not causal estimates.
Modelled noise, not measured.

Usage::

    uv run python -m ne.models.spatial_reg
"""

from __future__ import annotations

import time

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.api as sm
from libpysal.weights import Queen, W

from ne import config
from ne.build import analysis_table as at
from ne.models import disparity as dp

OUT_DIR = config.PROCESSED_DIR
CENSUS = config.INTERIM_DIR / "census"
RACE_10PP = {
    "pct_nh_black": "black_10pp",
    "pct_hispanic": "hispanic_10pp",
    "pct_nh_asian": "asian_10pp",
    "pct_other": "other_10pp",
}
DERIVED_FROM = dp.DERIVED_FROM + "; TIGER/Line 2020 block groups (contiguity, land area)"


# --- weights and design ---------------------------------------------------------------


def within_metro_weights(gdf: gpd.GeoDataFrame) -> W:
    """Queen contiguity on positional ids, with links across metro borders removed."""
    q = Queen.from_dataframe(gdf, use_index=False, silence_warnings=True)
    cbsa = gdf["cbsa"].to_numpy()
    neighbors = {i: [j for j in nb if cbsa[j] == cbsa[i]] for i, nb in q.neighbors.items()}
    w = W(neighbors, silence_warnings=True)
    w.transform = "R"
    return w


def design(df: pd.DataFrame, spec: str) -> pd.DataFrame:
    """Regressors for spec A, B or C (no constant)."""
    q = df["income_quintile"].astype("Int64")
    x = pd.DataFrame({f"Q{k}": (q == k).astype(float).to_numpy() for k in (1, 2, 3, 4)},
                     index=df.index)  # fmt: skip
    if spec in ("B", "C"):
        for col, name in RACE_10PP.items():
            x[name] = df[col].astype(float) * 10
    if spec == "C":
        x["renter_10pp"] = df["pct_renter"].astype(float) * 10
        x["log_density"] = np.log(df["density"].astype(float))
    metros = sorted(df["cbsa"].unique())
    for m in metros[1:]:
        x[f"metro_{m}"] = (df["cbsa"] == m).astype(float)
    return x


# --- estimators -----------------------------------------------------------------------


def _pack(names, betas, ses, extra=None):
    out = {"coef": dict(zip(names, betas, strict=True)), "se": dict(zip(names, ses, strict=True))}
    out.update(extra or {})
    return out


def fit_ols(y: np.ndarray, x: pd.DataFrame, clusters) -> dict:
    X = sm.add_constant(x, has_constant="add")
    m = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(clusters)[0]})
    return _pack(list(X.columns), m.params.to_numpy(), m.bse.to_numpy(),
                 {"n": int(m.nobs), "r2": m.rsquared, "resid": m.resid.to_numpy()})  # fmt: skip


def fit_lag(y: np.ndarray, x, w: W, names) -> dict:
    from spreg import GM_Lag

    m = GM_Lag(y, np.asarray(x, float), w=w, w_lags=2, robust="white")
    b, se = m.betas.ravel(), np.sqrt(np.diag(m.vm))
    rho = float(b[-1])
    out = _pack(["CONSTANT", *names], b[:-1], se[:-1], {"rho": rho, "rho_se": float(se[-1])})
    out["total"] = {k: v / (1 - rho) for k, v in out["coef"].items()}
    return out


def fit_error(y: np.ndarray, x, w: W, names) -> dict:
    from spreg import GM_Error_Het

    m = GM_Error_Het(y, np.asarray(x, float), w=w)
    b, se = m.betas.ravel(), np.sqrt(np.diag(m.vm))
    return _pack(["CONSTANT", *names], b[:-1], se[:-1],
                 {"lambda": float(b[-1]), "lambda_se": float(se[-1])})  # fmt: skip


def _within(y, x: pd.DataFrame, groups):
    """Metro fixed effects by within-metro demeaning (drops the ``metro_*`` dummies).

    Spatial lags of metro dummies equal the dummies themselves (weights never cross metros),
    which makes the GM_Lag instruments collinear; demeaning avoids that. With row-
    standardised within-metro weights, W·(metro mean) = metro mean, so the lag model on
    demeaned data has the same rho and beta.
    """
    x = x[[c for c in x.columns if not c.startswith("metro_")]]
    g = pd.Series(np.asarray(groups)).to_numpy()
    yd = pd.Series(np.ravel(y)).groupby(g).transform(lambda v: v - v.mean()).to_numpy()
    xd = x.reset_index(drop=True).groupby(g).transform(lambda v: v - v.mean())
    return yd.reshape(-1, 1), xd


def fit_lag_fe(y, x: pd.DataFrame, w: W, groups) -> dict:
    yd, xd = _within(y, x, groups)
    return fit_lag(yd, xd, w, list(xd.columns))


def fit_error_fe(y, x: pd.DataFrame, w: W, groups) -> dict:
    yd, xd = _within(y, x, groups)
    return fit_error(yd, xd, w, list(xd.columns))


def lm_diagnostics(y: np.ndarray, x, w: W) -> dict:
    from spreg import OLS

    m = OLS(y, np.asarray(x, float), w=w, spat_diag=True, moran=True)
    return {
        "moran_i": m.moran_res[0], "moran_z": m.moran_res[1], "moran_p": m.moran_res[2],
        "lm_lag": m.lm_lag[0], "lm_lag_p": m.lm_lag[1],
        "lm_error": m.lm_error[0], "lm_error_p": m.lm_error[1],
        "rlm_lag": m.rlm_lag[0], "rlm_lag_p": m.rlm_lag[1],
        "rlm_error": m.rlm_error[0], "rlm_error_p": m.rlm_error[1],
    }  # fmt: skip


# --- data -----------------------------------------------------------------------------


def load_sample(year: int = 2022, source: str = "all") -> gpd.GeoDataFrame:
    """Block groups with residents, income, race and renter data, plus geometry."""
    df = pd.read_parquet(at.OUT)
    df = df[(df["year"] == year) & (df["source"] == source)]
    geo = gpd.read_parquet(CENSUS / "bg_2020.parquet", columns=["geoid", "aland", "geometry"])
    geo = geo.rename(columns={"geoid": "bg_geoid"})
    d = geo.merge(df, on="bg_geoid")
    d["density"] = d["pop20"] / (d["aland"] / 1e6)
    keep = (
        (d["pop20"] > 0) & (d["aland"] > 0) & d["income_quintile"].notna()
        & d[[*RACE_10PP, "pct_renter"]].notna().all(axis=1)
    )  # fmt: skip
    d = d[keep].sort_values(["cbsa", "bg_geoid"]).reset_index(drop=True)
    d["tract"] = d["bg_geoid"].str[:11]
    return d


def drop_islands(d: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, W]:
    w = within_metro_weights(d)
    if w.islands:
        d = d.drop(index=w.islands).reset_index(drop=True)
        w = within_metro_weights(d)
    return d, w


# --- run ------------------------------------------------------------------------------


def _rows(model, spec, outcome, res, scope="pooled", metro=None):
    rows = []
    for k, v in res["coef"].items():
        if k.startswith("metro_") or k in ("const", "CONSTANT"):  # FE / intercepts
            continue
        rows.append({"scope": scope, "metro": metro, "outcome": outcome, "spec": spec,
                     "model": model, "term": k, "coef": v, "se": res["se"][k],
                     "total": res.get("total", {}).get(k, np.nan),
                     "rho": res.get("rho", np.nan),
                     "lambda": res.get("lambda", np.nan)})  # fmt: skip
    return rows


def run(log=print) -> dict[str, pd.DataFrame]:
    t0 = time.time()
    d = load_sample()
    d, w = drop_islands(d)
    log(f"sample: {len(d):,} block groups, {d['cbsa'].nunique()} metros "
        f"({time.time() - t0:.0f}s incl. weights)")  # fmt: skip
    names = {m["cbsa"]: m["short"] for m in config.metros()}
    coefs, diags, per_metro = [], [], []

    for t in (55, 65):
        outcome = f"pct_ge_{t}"
        y = 100 * d[f"pop_share_ge_{t}"].to_numpy(float)
        for spec in ("A", "B", "C"):
            x = design(d, spec)
            ols = fit_ols(y, x, d["tract"])
            coefs += _rows("OLS (cluster: tract)", spec, outcome, ols)
            log(f"{outcome} {spec} OLS  R2={ols['r2']:.3f}")
        x = design(d, "C")
        yy = y.reshape(-1, 1)
        diags.append({"scope": "pooled", "metro": None, "outcome": outcome,
                      **lm_diagnostics(yy, x, w)})  # fmt: skip
        lag = fit_lag_fe(y, x, w, d["cbsa"])
        err = fit_error_fe(y, x, w, d["cbsa"])
        coefs += _rows("Spatial lag (GM)", "C", outcome, lag)
        coefs += _rows("Spatial error (GM, het.)", "C", outcome, err)
        log(f"{outcome} C lag rho={lag['rho']:.3f}  error lambda={err['lambda']:.3f} "
            f"({time.time() - t0:.0f}s)")  # fmt: skip

        for cbsa, g in d.groupby("cbsa", sort=False):
            g = g.reset_index(drop=True)
            gw = within_metro_weights(g)
            if gw.islands:
                g = g.drop(index=gw.islands).reset_index(drop=True)
                gw = within_metro_weights(g)
            gy = 100 * g[f"pop_share_ge_{t}"].to_numpy(float)
            gx = design(g, "C")
            m = names[cbsa]
            gy2, cols = gy.reshape(-1, 1), list(gx.columns)
            fits = {
                "OLS (cluster: tract)": fit_ols(gy, gx, g["tract"]),
                "Spatial lag (GM)": fit_lag(gy2, gx, gw, cols),
                "Spatial error (GM, het.)": fit_error(gy2, gx, gw, cols),
            }
            for model, res in fits.items():
                per_metro += _rows(model, "C", outcome, res, "metro", m)
            diags.append({"scope": "metro", "metro": m, "outcome": outcome,
                          **lm_diagnostics(gy.reshape(-1, 1), gx, gw)})  # fmt: skip
        log(f"{outcome} per-metro models done ({time.time() - t0:.0f}s)")

    out = {
        "spatial_models_pooled": pd.DataFrame(coefs),
        "spatial_models_metro": pd.DataFrame(per_metro),
        "spatial_lm_diagnostics": pd.DataFrame(diags),
        "change_over_time": change_over_time(),
    }
    for name, t in out.items():
        t = t.copy()
        t["derived_from"] = DERIVED_FROM
        t.round(4).to_csv(OUT_DIR / f"{name}.csv", index=False)
    return out


def change_over_time() -> pd.DataFrame:
    """Descriptive only (decision P08): road + aviation, pooled, by group and map year."""
    parts = []
    for kind in ("income", "race"):
        t = pd.read_csv(dp.OUT_DIR / f"disparity_{kind}.csv")
        t = t[(t["metro"] == dp.POOLED) & (t["source"] == "road_aviation")]
        parts.append(t[["year", "group", "pct_ge_55", "pct_ge_65"]].assign(kind=kind))
    return pd.concat(parts, ignore_index=True)[["kind", "group", "year", "pct_ge_55", "pct_ge_65"]]


if __name__ == "__main__":
    res = run()
    p = res["spatial_models_pooled"]
    show = p[(p["outcome"] == "pct_ge_55")].pivot_table(
        index="term", columns=["spec", "model"], values="coef", sort=False
    )
    print(show.round(2).to_string())
    print(res["spatial_lm_diagnostics"].query("scope == 'pooled'").round(3).T.to_string())
