"""Numbers quoted in the report, computed from the committed result tables (P17).

Every number in ``report/index.qmd`` is a Quarto variable (``{{< var key >}}``) defined in
``report/_variables.yml``, which this module writes. ``report/claims.csv`` lists each
variable with the table it comes from, so every claim can be traced.

Usage::

    uv run python -m ne.report      # then: quarto render report
"""

from __future__ import annotations

import csv

import pandas as pd
import yaml

from ne import config
from ne.build import nyc_panel as npn
from ne.build import zonal_stats as zs
from ne.models import disparity as dp

REPORT = config.ROOT / "report"
P = config.PROCESSED_DIR
Q1, Q5 = dp.INCOME_GROUPS[1], dp.INCOME_GROUPS[5]


class Vars:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.claims: list[dict] = []

    def add(self, key: str, value, source: str, fmt: str = "{:.1f}"):
        text = value if isinstance(value, str) else fmt.format(value).replace("-", "\u2212")
        self.values[key] = text
        self.claims.append({"variable": key, "value": text, "source": source})


def _num(x, fmt):
    return fmt.format(x).replace("-", "\u2212")  # typographic minus


def _ci(lo, hi, fmt="{:.2f}"):
    return f"{_num(lo, fmt)} to {_num(hi, fmt)}"


def build() -> Vars:
    v = Vars()

    # --- scope and benchmark (P08) -------------------------------------------------------
    bg = pd.read_parquet(zs.PROCESSED)
    b22 = bg[(bg["year"] == 2022) & (bg["source"] == "all")]
    v.add("residents_m", b22["pop20"].sum() / 1e6, "bg_noise.parquet: 2022, all; sum pop20")
    v.add("block_groups", f"{b22['bg_geoid'].nunique():,}", "bg_noise.parquet: 2022, all")
    pooled = zs.pooled_shares(bg)
    v.add("all_ge55", pooled.loc[(2022, "all"), 55], "bg_noise.parquet via pooled_shares")
    v.add("all_ge65", pooled.loc[(2022, "all"), 65], "bg_noise.parquet via pooled_shares")
    r = pd.read_csv(P / "bts_reconciliation.csv").set_index(["benchmark", "t"])
    uw = r.loc[("UW DEOHS 2020, all sources", 60)]
    v.add("uw_ge60", uw["published_pct"], "bts_reconciliation.csv: UW DEOHS 2020, 60 dB")
    v.add("ours_ge60_2020", uw["our_20_metros_pct"], "bts_reconciliation.csv: ours, 2020, 60 dB")

    # --- disparities (P10) ---------------------------------------------------------------
    inc = pd.read_csv(P / "disparity_income.csv")
    race = pd.read_csv(P / "disparity_race.csv")
    src_inc = "disparity_income.csv: All 20 metros, 2022"
    pi = inc[(inc["metro"] == dp.POOLED) & (inc["year"] == 2022)].set_index(["source", "group"])
    for t in (55, 65):
        q1, q5 = pi.loc[("all", Q1), f"pct_ge_{t}"], pi.loc[("all", Q5), f"pct_ge_{t}"]
        v.add(f"q1_{t}", q1, f"{src_inc}, all sources, Q1, ≥{t}")
        v.add(f"q5_{t}", q5, f"{src_inc}, all sources, Q5, ≥{t}")
        v.add(f"q_ratio_{t}", q1 / q5, f"{src_inc}, all sources, Q1/Q5, ≥{t}")
    for s in ("road", "rail", "aviation"):
        q1, q5 = pi.loc[(s, Q1), "pct_ge_55"], pi.loc[(s, Q5), "pct_ge_55"]
        v.add(f"{s}_q1_55", q1, f"{src_inc}, {s}, Q1, ≥55")
        v.add(f"{s}_q5_55", q5, f"{src_inc}, {s}, Q5, ≥55")
        v.add(f"{s}_ratio_55", q1 / q5, f"{src_inc}, {s}, Q1/Q5, ≥55")
    per = inc[(inc["metro"] != dp.POOLED) & (inc["year"] == 2022) & (inc["source"] == "all")]
    pm = per.pivot_table(index="metro", columns="group", values="pct_ge_55")
    ratio = (pm[Q1] / pm[Q5]).sort_values()
    v.add("metros_q1_gt_q5", f"{int((ratio > 1).sum())}", "disparity_income.csv: per metro, ≥55")
    v.add("widest_metro", ratio.index[-1], "disparity_income.csv: per metro Q1/Q5, ≥55")
    v.add("widest_ratio", ratio.iloc[-1], "disparity_income.csv: per metro Q1/Q5, ≥55")
    v.add("narrowest_metro", ratio.index[0], "disparity_income.csv: per metro Q1/Q5, ≥55")
    v.add("narrowest_ratio", ratio.iloc[0], "disparity_income.csv: per metro Q1/Q5, ≥55")
    pr = race[(race["metro"] == dp.POOLED) & (race["year"] == 2022)].set_index(["source", "group"])
    for g in ("White", "Black", "Hispanic", "Asian"):
        v.add(f"race_{g.lower()}_55", pr.loc[("all", g), "pct_ge_55"],
              f"disparity_race.csv: All 20 metros, 2022, all, {g}, ≥55")  # fmt: skip
    for s, g in (("rail", "Black"), ("rail", "White"), ("aviation", "Hispanic"),
                 ("aviation", "White")):  # fmt: skip
        v.add(f"race_{s}_{g.lower()}_55", pr.loc[(s, g), "pct_ge_55"],
              f"disparity_race.csv: All 20 metros, 2022, {s}, {g}, ≥55")  # fmt: skip

    # --- models (P11) --------------------------------------------------------------------
    m = pd.read_csv(P / "spatial_models_pooled.csv")
    m = m[(m["outcome"] == "pct_ge_55")]
    src_m = "spatial_models_pooled.csv: pct_ge_55"
    for spec, model, key in (("A", "OLS (cluster: tract)", "a"), ("B", "OLS (cluster: tract)", "b"),
                             ("C", "OLS (cluster: tract)", "c"), ("C", "Spatial lag (GM)", "lag"),
                             ("C", "Spatial error (GM, het.)", "err")):  # fmt: skip
        row = m[(m["spec"] == spec) & (m["model"] == model) & (m["term"] == "Q1")].iloc[0]
        v.add(f"gap_{key}", row["coef"], f"{src_m}, spec {spec}, {model}, Q1", "{:+.1f}")
        lo, hi = row["coef"] - 1.96 * row["se"], row["coef"] + 1.96 * row["se"]
        v.add(f"gap_{key}_ci", _ci(lo, hi, "{:.1f}"), f"{src_m}, spec {spec}, {model}, Q1 CI")
    renter = m[(m["spec"] == "C") & m["model"].str.startswith("OLS") & (m["term"] == "renter_10pp")]
    v.add("renter_coef", renter["coef"].iloc[0], f"{src_m}, spec C, OLS, renter_10pp")
    d = pd.read_csv(P / "spatial_lm_diagnostics.csv")
    dpool = d[(d["scope"] == "pooled") & (d["outcome"] == "pct_ge_55")].iloc[0]
    v.add("moran_i", dpool["moran_i"], "spatial_lm_diagnostics.csv: pooled, pct_ge_55", "{:.2f}")
    v.add("share_gap_race", 100 * (1 - row_val(m, "B") / row_val(m, "A")),
          f"{src_m}: 1 − spec B / spec A, Q1", "{:.0f}")  # fmt: skip

    # --- health (P14, P15) ---------------------------------------------------------------
    h = pd.read_csv(P / "health_estimates.csv")
    hp = h[h["metro"] == dp.POOLED].set_index(["outcome", "source"])
    for (o, s), r_ in hp.iterrows():
        k = f"{o.lower()}_{s}"
        v.add(f"{k}_m", r_["excess"] / 1e6, f"health_estimates.csv: All 20 metros, {o}, {s}")
        v.add(f"{k}_range", _ci(r_["excess_low"] / 1e6, r_["excess_high"] / 1e6, "{:.1f}"),
              f"health_estimates.csv: All 20 metros, {o}, {s}, low–high")  # fmt: skip
    hi = pd.read_csv(P / "health_by_income.csv").set_index(["outcome", "source", "income_quintile"])
    v.add("ha_aviation_q1", hi.loc[("HA", "aviation", Q1), "excess_per_1000"],
          "health_by_income.csv: HA, aviation, Q1, per 1,000")  # fmt: skip
    v.add("ha_aviation_q5", hi.loc[("HA", "aviation", Q5), "excess_per_1000"],
          "health_by_income.csv: HA, aviation, Q5, per 1,000")  # fmt: skip
    g = pd.read_csv(P / "robustness_grid.csv")
    up = g[g["result"].str.contains("HA residents, aviation") & g["variant"].str.contains("at 45")]
    v.add("ha_aviation_floor45_m", up["value"].iloc[0],
          "robustness_grid.csv: aviation HA, residents < 45 dBA at 45 dBA")  # fmt: skip
    dis = g[g["result"].str.startswith("Disparity: Income")]
    lo, hi = dis["value"].min(), dis[["baseline", "value"]].max().max()
    v.add("robust_income_ratio", _ci(lo, hi, "{:.1f}"), "robustness_grid.csv: income ratio")

    # --- NYC (P12, P13) ------------------------------------------------------------------
    t = pd.read_parquet(npn.TRACTS)
    p = pd.read_parquet(npn.PANEL)
    v.add("nyc_tracts", f"{len(t):,}", "nyc_tracts.parquet")
    v.add("nyc_complaints_m", p["complaints"].sum() / 1e6, "nyc_panel.parquet: complaints")
    v.add("nyc_locdays_m", p["location_days"].sum() / 1e6, "nyc_panel.parquet: location_days")
    rates = npn.per_1000(p, t)["all_groups"]
    typos = {"Low-income, gentrifying": "gent", "Low-income, not gentrifying": "notgent",
             "Higher-income": "higher"}  # fmt: skip
    for typ, key in typos.items():
        v.add(f"nyc_rate_{key}", rates[typ], f"nyc_panel × nyc_tracts via per_1000: {typ}")
    c = pd.read_csv(P / "complaints_nb_models.csv")
    ref = c[c["variant"].str.startswith("ref") & (c["term"] == "Low-income, gentrifying")]
    for grp in ("combined", "residential", "street"):
        r_ = ref[ref["group"] == grp].iloc[0]
        v.add(f"nyc_gent_{grp}_pct", 100 * (r_["irr"] - 1),
              f"complaints_nb_models.csv: {grp}, M2, ref not gentrifying", "{:.0f}")  # fmt: skip
        v.add(f"nyc_gent_{grp}_ci", _ci(100 * (r_["lo"] - 1), 100 * (r_["hi"] - 1), "{:.0f}"),
              f"complaints_nb_models.csv: {grp}, M2, 95% CI (%)")  # fmt: skip
    nz = c[(c["group"] == "combined") & (c["model"] == "M2") & (c["variant"] == "location-days")
           & (c["term"] == "noise_10")].iloc[0]  # fmt: skip
    v.add("nyc_noise_irr", nz["irr"], "complaints_nb_models.csv: combined, M2, noise_10", "{:.2f}")
    v.add("nyc_noise_irr_ci", _ci(nz["lo"], nz["hi"]), "complaints_nb_models.csv: 95% CI")
    return v


def row_val(m: pd.DataFrame, spec: str) -> float:
    return m[(m["spec"] == spec) & m["model"].str.startswith("OLS") & (m["term"] == "Q1")][
        "coef"
    ].iloc[0]


def write(v: Vars) -> None:
    REPORT.mkdir(exist_ok=True)
    (REPORT / "_variables.yml").write_text(
        "# Written by `uv run python -m ne.report`. Do not edit by hand.\n"
        + yaml.safe_dump(v.values, allow_unicode=True, sort_keys=True)
    )
    with open(REPORT / "claims.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["variable", "value", "source"])
        w.writeheader()
        w.writerows(v.claims)


if __name__ == "__main__":
    v = build()
    write(v)
    for k, val in sorted(v.values.items()):
        print(f"{k:28s} {val}")
