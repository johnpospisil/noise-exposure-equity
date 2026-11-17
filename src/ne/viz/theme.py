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
