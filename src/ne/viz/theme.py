"""Shared chart styling. Extended in P10; P03 only needs the noise-band ramp."""

from __future__ import annotations

#: LAeq,24h bands (dB) for maps. Cells below 45 dB are not in the BTS rasters.
NOISE_BANDS = [45, 50, 55, 60, 65, 70]
NOISE_BAND_LABELS = ["45–50", "50–55", "55–60", "60–65", "65–70", "≥ 70"]
#: One-hue (blue) ordinal ramp, light -> dark, one step per band.
NOISE_COLORS = ["#86b6ef", "#5598e7", "#2a78d6", "#256abf", "#184f95", "#0d366b"]
#: "< 45 dB / not modelled" background.
BELOW_COLOR = "#f0efec"

INK = "#1f1f1e"
INK_MUTED = "#6b6a66"

# --- P10: groups ----------------------------------------------------------------------

#: Income quintiles, one-hue ordinal ramp (dataviz reference ramp, steps 700 -> 250).
#: Q1 (lowest income) is darkest.
QUINTILE_COLORS = ["#0d366b", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef"]
QUINTILE_SHORT = ["Q1", "Q2", "Q3", "Q4", "Q5"]
#: Race/ethnicity, categorical slots 1-5 of the reference palette, fixed order.
RACE_COLORS = {
    "White": "#2a78d6",
    "Black": "#eb6834",
    "Hispanic": "#1baf7a",
    "Asian": "#eda100",
    "Other": "#e87ba4",
}
GRID = "#e4e2dd"
AXIS = "#cfcdc8"
SURFACE = "#ffffff"


def style_axes(ax, grid_axis: str = "y") -> None:
    """Recessive axes: no top/right spines, light grid, muted ticks."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
    ax.grid(axis=grid_axis, color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
