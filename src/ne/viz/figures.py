"""Article figures (``make figures``). Reads committed result tables only.

* Hero chart: share of residents at or above 55 dBA by income quintile, 20 metros
  (decision P10); the 65 dBA version is the stricter test.
* Chart 3: disparity by noise source (road / aviation / rail), by income and race.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

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
        fig.savefig(p, dpi=150, facecolor=theme.SURFACE)
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


if __name__ == "__main__":
    for p in [*hero(55), *hero(65), *by_source(55)]:
        print(p)
