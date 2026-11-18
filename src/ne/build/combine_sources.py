"""Decibel arithmetic. Decibels are never added or averaged arithmetically (CLAUDE.md rule 4).

* **Energy sum** (several sources at one place): ``10·log10(Σ 10^(L/10))``.
* **Energy mean** (one source over several places or times):
  ``10·log10(Σ w·10^(L/10) / Σ w)``.

Censored values: the BTS rasters leave out cells below 45 dBA. Here they are ``NaN``
(see :func:`from_raster`) and mean "below the mapped range". Two policies:

* ``"floor"`` (default): a censored value counts as ``floor`` dB (default 45, the
  ``censor_floor_dba`` setting; 40 is the sensitivity check). This is an upper bound.
* ``"zero"``: a censored value adds no sound energy.

When **every** input is censored the result is ``NaN`` under both policies: the place is
still "below the mapped range", not ``floor`` dB or silent.
"""

from __future__ import annotations

import numpy as np

from ne import config

NODATA = -9999.0
POLICIES = ("floor", "zero")


def default_floor() -> float:
    return float(config.thresholds()["censor_floor_dba"])


def from_raster(arr, nodata: float = NODATA) -> np.ndarray:
    """Raster values as float64 dB, with ``nodata`` (censored, < 45 dBA) as ``NaN``."""
    out = np.asarray(arr, dtype="float64").copy()
    out[out == nodata] = np.nan
    return out


def to_energy(levels) -> np.ndarray:
    """Relative sound energy ``10^(L/10)``; ``NaN`` stays ``NaN``."""
    return np.power(10.0, np.asarray(levels, dtype="float64") / 10.0)


def to_db(energy) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return 10.0 * np.log10(energy)


def _censored_energy(levels: np.ndarray, policy: str, floor: float | None) -> np.ndarray:
    """Energy per value, with censored values replaced according to ``policy``."""
    if policy not in POLICIES:
        raise ValueError(f"policy must be one of {POLICIES}, got {policy!r}")
    floor = default_floor() if floor is None else floor
    fill = to_energy(floor) if policy == "floor" else 0.0
    return np.where(np.isnan(levels), fill, to_energy(levels))


def _scalar(x):
    return float(x) if np.ndim(x) == 0 else x


def energy_sum(levels, axis: int = 0, policy: str = "floor", floor: float | None = None):
    """Combine sources at the same place: ``10·log10(Σ 10^(L/10))`` along ``axis``."""
    levels = np.asarray(levels, dtype="float64")
    e = _censored_energy(levels, policy, floor)
    out = to_db(e.sum(axis=axis))
    all_censored = np.isnan(levels).all(axis=axis)
    return _scalar(np.where(all_censored, np.nan, out))


def energy_mean(
    levels,
    weights=None,
    axis=None,
    policy: str = "floor",
    floor: float | None = None,
    cap: float | None = None,
):
    """Weighted energy mean ``10·log10(Σ w·10^(L/10) / Σ w)``.

    Censored values still count in the denominator (they are real places, just quiet).
    ``cap`` clips levels first (e.g. 100 dB, decision P03: track and runway cells).
    """
    levels = np.asarray(levels, dtype="float64")
    if cap is not None:
        levels = np.minimum(levels, cap)  # NaN stays NaN
    w = (
        np.ones_like(levels)
        if weights is None
        else np.broadcast_to(np.asarray(weights, dtype="float64"), levels.shape)
    )
    e = _censored_energy(levels, policy, floor)
    out = to_db((w * e).sum(axis=axis) / w.sum(axis=axis))
    all_censored = np.isnan(levels).all(axis=axis)
    return _scalar(np.where(all_censored, np.nan, out))
