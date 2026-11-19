"""Article figures (``make figures``). Reads committed result tables only.

* Hero chart: share of residents at or above 55 dBA by income quintile, 20 metros
  (decision P10); the 65 dBA version is the stricter test.
* Chart 3: disparity by noise source (road / aviation / rail), by income and race.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "noise-exposure-equity"

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from ne import config  # noqa: E402
from ne.models import disparity as dp  # noqa: E402
from ne.viz import theme  # noqa: E402

FIG_DIR = config.FIGURES_DIR
CAVEAT = (
    "Modelled, not measured: BTS National Transportation Noise Map (2022), LAeq,24h. "
    "Road = major roads only. Neighbourhood (block-group) estimates, not individual exposure."
)
SOURCE_NOTE = "Sources: BTS; U.S. Census Bureau (2020 Census blocks, ACS 2018-22)."


def _load(kind: str) -> pd.DataFrame:
    return pd.read_csv(dp.OUT_DIR / f"disparity_{kind}.csv")


def _save(fig, name: str) -> list:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    paths = [FIG_DIR / f"{name}.png", FIG_DIR / f"{name}.svg"]
    for p in paths:
        # fixed metadata and ids so re-rendering does not change files in git
        meta = {"Date": None} if p.suffix == ".svg" else {}
        fig.savefig(p, dpi=150, facecolor=theme.SURFACE, metadata=meta)
    plt.close(fig)
    return paths


def hero(t: int = 55, year: int = 2022, source: str = "all"):
    """Small multiples: one panel per metro, five quintile bars, shared y-axis."""
    d = _load("income")
    d = d[(d["year"] == year) & (d["source"] == source)]
    col = f"pct_ge_{t}"
    metros = [m["short"] for m in config.metros()]
    pooled = d[d["metro"] == dp.POOLED].set_index("group")[col]
    ymax = d.loc[d["metro"] != dp.POOLED, col].max() * 1.18

    fig, axes = plt.subplots(4, 5, figsize=(13, 10.5), sharex=True, sharey=True)
    x = range(5)
    for ax, metro in zip(axes.flat, metros, strict=True):
        v = d[d["metro"] == metro].set_index("group")[col].reindex(dp.INCOME_GROUPS.values())
        ax.bar(x, v.values, width=0.78, color=theme.QUINTILE_COLORS)
        for i in (0, 4):  # selective direct labels: lowest and highest quintile
            ax.text(i, v.iloc[i] + ymax * 0.02, f"{v.iloc[i]:.1f}", ha="center",
                    va="bottom", fontsize=8.5, color=theme.INK)  # fmt: skip
        ratio = v.iloc[0] / v.iloc[4] if v.iloc[4] > 0 else float("nan")
        ax.set_title(f"{metro}", loc="left", fontsize=11, color=theme.INK, pad=4)
        ax.text(1.0, 1.02, f"Q1/Q5 {ratio:.1f}×", transform=ax.transAxes, ha="right",
                va="bottom", fontsize=8.5, color=theme.INK_MUTED)  # fmt: skip
        theme.style_axes(ax)
        ax.set_ylim(0, ymax)
        ax.set_xticks(list(x), theme.QUINTILE_SHORT)
    for ax in axes[:, 0]:
        ax.set_ylabel("% of residents", fontsize=9, color=theme.INK_MUTED)

    handles = [
        Patch(color=c, label=lab)
        for c, lab in zip(theme.QUINTILE_COLORS, dp.INCOME_GROUPS.values(), strict=True)
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.945), ncol=5,
               frameon=False, fontsize=9.5,
               title="Household income quintile within the metro")  # fmt: skip
    fig.suptitle(
        f"In all 20 of the largest metros, the lowest-income fifth of neighbourhoods is more "
        f"exposed to transportation noise than the highest\n"
        f"Share of residents in blocks at or above {t} dBA{' (stricter test)' if t >= 65 else ''} "
        f"(road, rail and aviation combined), {year}",
        x=0.03, y=0.99, ha="left", fontsize=13.5, color=theme.INK,
    )  # fmt: skip
    fig.text(0.03, 0.015,
             f"All 20 metros pooled: Q1 {pooled.iloc[0]:.1f}% vs Q5 {pooled.iloc[4]:.1f}%.\n"
             f"{CAVEAT}\n{SOURCE_NOTE}", fontsize=8.5, color=theme.INK_MUTED)  # fmt: skip
    fig.subplots_adjust(left=0.06, right=0.99, top=0.85, bottom=0.1, hspace=0.38, wspace=0.12)
    return _save(fig, f"hero_income_ge{t}")


def by_source(t: int = 55, year: int = 2022):
    """Chart 3: pooled exposure by source (columns) for income (top) and race (bottom)."""
    sources = ["road", "aviation", "rail"]
    titles = {"road": "Road (major roads)", "aviation": "Aviation", "rail": "Rail (excl. subway)"}
    col = f"pct_ge_{t}"
    rows = [
        ("income", list(dp.INCOME_GROUPS.values()), theme.QUINTILE_COLORS, theme.QUINTILE_SHORT),
        ("race", list(dp.RACE_GROUPS.values()), list(theme.RACE_COLORS.values()),
         list(dp.RACE_GROUPS.values())),
    ]  # fmt: skip
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.5), sharey="row")
    for r, (kind, groups, colors, ticks) in enumerate(rows):
        d = _load(kind)
        d = d[(d["year"] == year) & (d["metro"] == dp.POOLED)]
        ymax = d.loc[d["source"].isin(sources), col].max() * 1.2
        for c, src in enumerate(sources):
            ax = axes[r, c]
            v = d[d["source"] == src].set_index("group")[col].reindex(groups)
            ax.bar(range(len(groups)), v.values, width=0.78, color=colors)
            hi = int(v.values.argmax())
            lo = 0 if kind == "race" else len(groups) - 1  # White, or Q5
            for i in sorted({hi, lo}):
                ax.text(i, v.iloc[i] + ymax * 0.02, f"{v.iloc[i]:.1f}", ha="center",
                        va="bottom", fontsize=9, color=theme.INK)  # fmt: skip
            ax.set_xticks(range(len(groups)), ticks)
            ax.set_ylim(0, ymax)
            theme.style_axes(ax)
            if r == 0:
                ax.set_title(titles[src], loc="left", fontsize=12, color=theme.INK)
            if c == 0:
                label = "Income quintile" if kind == "income" else "Race / ethnicity"
                ax.set_ylabel(f"{label}\n% of residents ≥ {t} dBA", fontsize=9.5,
                              color=theme.INK_MUTED)  # fmt: skip
    fig.suptitle(
        f"Every source falls hardest on lower-income neighbourhoods and on Black, Hispanic and "
        f"Asian residents\nShare of residents in blocks at or above {t} dBA, "
        f"20 largest metros pooled, {year}",
        x=0.03, y=0.985, ha="left", fontsize=13.5, color=theme.INK,
    )  # fmt: skip
    fig.text(0.03, 0.02,
             "Race/ethnicity: White, Black, Asian = non-Hispanic; Other = other races and "
             "multiracial. Pooled figures mix metros of different size and composition; "
             "within-metro comparisons follow in P11.\n" + CAVEAT + " " + SOURCE_NOTE,
             fontsize=8, color=theme.INK_MUTED, wrap=True)  # fmt: skip
    fig.subplots_adjust(left=0.08, right=0.99, top=0.84, bottom=0.15, hspace=0.3, wspace=0.08)
    return _save(fig, f"chart3_by_source_ge{t}")


MODEL_COLORS = {
    "OLS (cluster: tract)": "#2a78d6",
    "Spatial lag (GM)": "#eb6834",
    "Spatial error (GM, het.)": "#1baf7a",
}
MODEL_LABELS = {
    "OLS (cluster: tract)": "OLS, metro-level (95% CI, tract-clustered)",
    "Spatial lag (GM)": "Spatial lag, direct effect (95% CI)",
    "Spatial error (GM, het.)": "Spatial error (95% CI)",
}


def metro_models(term: str = "Q1", outcome: str = "pct_ge_55"):
    """Per-metro coefficient on ``term`` (spec C) under OLS, spatial lag and spatial error."""
    d = pd.read_csv(config.PROCESSED_DIR / "spatial_models_metro.csv")
    d = d[(d["term"] == term) & (d["outcome"] == outcome)]
    order = d[d["model"] == "OLS (cluster: tract)"].sort_values("coef")["metro"].tolist()
    fig, ax = plt.subplots(figsize=(9, 8.5))
    offsets = {m: o for m, o in zip(MODEL_COLORS, (-0.22, 0.0, 0.22), strict=True)}
    for model, color in MODEL_COLORS.items():
        g = d[d["model"] == model].set_index("metro").reindex(order)
        y = [i + offsets[model] for i in range(len(order))]
        # lag: direct effect; beta / (1 - rho) is unstable when rho is near 1
        val = g["coef"]
        ax.hlines(y, g["coef"] - 1.96 * g["se"], g["coef"] + 1.96 * g["se"], color=color,
                  lw=1.5)  # fmt: skip
        ax.plot(val, y, "o", ms=6.5, color=color, mec=theme.SURFACE, mew=1.2,
                label=MODEL_LABELS[model])  # fmt: skip
    ax.axvline(0, color=theme.INK_MUTED, lw=0.8)
    ax.set_yticks(range(len(order)), order)
    theme.style_axes(ax, grid_axis="x")
    ax.set_xlabel(f"Percentage-point difference, lowest vs highest income fifth "
                  f"(% of residents ≥ {outcome[-2:]} dBA)", fontsize=9.5,
                  color=theme.INK_MUTED)  # fmt: skip
    ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, frameon=False, fontsize=8.5)
    fig.suptitle(
        "Once renting and density are accounted for, little separate income gap remains\n"
        "Lowest vs highest income fifth, one model per metro (spec C)",
        x=0.03, y=0.985, ha="left", fontsize=12.5, color=theme.INK,
    )  # fmt: skip
    fig.text(0.03, 0.015,
             "Spec C: income quintile, race/ethnicity shares, renter share, log density; one "
             "model per metro. Spatial models use within-metro Queen contiguity.\n"
             "Associations between neighbourhoods, not causal effects. " + CAVEAT + "\n"
             + SOURCE_NOTE, fontsize=7.5, color=theme.INK_MUTED, wrap=True)  # fmt: skip
    fig.subplots_adjust(left=0.17, right=0.98, top=0.87, bottom=0.17)
    return _save(fig, f"metro_models_{term}_{outcome}")


def spec_steps(outcome: str = "pct_ge_55"):
    """Pooled Q1-vs-Q5 gap as controls are added (A -> B -> C) and under spatial models."""
    d = pd.read_csv(config.PROCESSED_DIR / "spatial_models_pooled.csv")
    d = d[(d["term"] == "Q1") & (d["outcome"] == outcome)]
    steps = [
        ("A", "OLS (cluster: tract)", "Metro fixed effects only"),
        ("B", "OLS (cluster: tract)", "+ race / ethnicity shares"),
        ("C", "OLS (cluster: tract)", "+ renter share, density"),
        ("C", "Spatial error (GM, het.)", "+ spatial error term"),
        ("C", "Spatial lag (GM)", "+ spatial lag (direct effect)"),
    ]
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for i, (spec, model, _label) in enumerate(steps):
        r = d[(d["spec"] == spec) & (d["model"] == model)].iloc[0]
        color = MODEL_COLORS[model]
        ax.hlines(i, r["coef"] - 1.96 * r["se"], r["coef"] + 1.96 * r["se"], color=color, lw=2)
        ax.plot(r["coef"], i, "o", ms=8, color=color, mec=theme.SURFACE, mew=1.2)
        ax.text(r["coef"] + 1.96 * r["se"] + 0.25, i, f"{r['coef']:+.1f}", va="center",
                fontsize=9, color=theme.INK)  # fmt: skip
    ax.axvline(0, color=theme.INK_MUTED, lw=0.8)
    ax.set_yticks(range(len(steps)), [s[2] for s in steps])
    ax.invert_yaxis()
    theme.style_axes(ax, grid_axis="x")
    ax.set_xlabel(f"Lowest vs highest income fifth: percentage-point difference in residents "
                  f"≥ {outcome[-2:]} dBA (95% CI)", fontsize=9, color=theme.INK_MUTED)  # fmt: skip
    fig.suptitle("The income gap is mostly a renting-and-density gap\n"
                 "20 metros pooled, 2022, 78,549 block groups",
                 x=0.03, y=0.98, ha="left", fontsize=12, color=theme.INK)  # fmt: skip
    fig.text(0.03, 0.02, "Associations between neighbourhoods, not causal effects. Renting and "
             "density may be part of how income gaps arise, not alternatives to them.\n"
             "Modelled, not measured (BTS 2022, LAeq,24h); road = major roads only; "
             "block-group estimates.\n" + SOURCE_NOTE, fontsize=7.5,
             color=theme.INK_MUTED)  # fmt: skip
    fig.subplots_adjust(left=0.3, right=0.97, top=0.82, bottom=0.28)
    return _save(fig, f"spec_steps_{outcome}")


def change_box(t: int = 55):
    """Descriptive change over time, road + aviation, pooled (decision P08)."""
    d = pd.read_csv(config.PROCESSED_DIR / "change_over_time.csv")
    col = f"pct_ge_{t}"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, kind, groups, colors in (
        (axes[0], "income", list(dp.INCOME_GROUPS.values()), theme.QUINTILE_COLORS),
        (axes[1], "race", list(dp.RACE_GROUPS.values()), list(theme.RACE_COLORS.values())),
    ):
        g = d[d["kind"] == kind]
        for grp, color in zip(groups, colors, strict=True):
            s = g[g["group"] == grp].sort_values("year")
            ax.plot(s["year"], s[col], "-o", color=color, lw=2, ms=6, mec=theme.SURFACE,
                    label=grp)  # fmt: skip
        ax.axvspan(2019.4, 2020.6, color=theme.GRID, alpha=0.7, lw=0)
        ax.text(2020, 0.02, "COVID", ha="center", fontsize=8, color=theme.INK_MUTED,
                transform=ax.get_xaxis_transform())  # fmt: skip
        ax.set_xticks([2016, 2018, 2020, 2022])
        theme.style_axes(ax)
        ax.set_title("Income quintile" if kind == "income" else "Race / ethnicity",
                     loc="left", fontsize=11, color=theme.INK)  # fmt: skip
        ax.legend(frameon=False, fontsize=8.5, ncol=1, loc="upper left",
                  bbox_to_anchor=(1.0, 1.0))  # fmt: skip
    axes[0].set_ylabel(f"% of residents ≥ {t} dBA", fontsize=9.5, color=theme.INK_MUTED)
    axes[0].set_ylim(bottom=0)
    fig.suptitle(
        f"Road and aviation noise by group, BTS map years (road + aviation, ≥ {t} dBA, "
        "20 metros pooled)",
        x=0.03, y=0.98, ha="left", fontsize=12, color=theme.INK,
    )  # fmt: skip
    fig.text(0.03, 0.02,
             "Descriptive only: BTS changed which roads it models between releases, and 2020 "
             "reflects COVID-era traffic, so differences between years are not trends.\n"
             + CAVEAT, fontsize=7.5, color=theme.INK_MUTED)  # fmt: skip
    fig.subplots_adjust(left=0.07, right=0.88, top=0.84, bottom=0.2, wspace=0.45)
    return _save(fig, f"change_box_ge{t}")


if __name__ == "__main__":
    figs = [*hero(55), *hero(65), *by_source(55)]
    if (config.PROCESSED_DIR / "spatial_models_metro.csv").exists():
        figs += [*spec_steps(), *metro_models(), *change_box()]
    for p in figs:
        print(p)
