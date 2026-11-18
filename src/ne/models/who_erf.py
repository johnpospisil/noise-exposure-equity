"""WHO exposure-response functions (ERFs) and LAeq,24h -> Lden / Lnight conversion.

Primary set (decision P06): the curves behind the WHO Environmental Noise Guidelines for
the European Region (2018), as written into Annex III of EU Directive 2015/996 by
Commission Directive (EU) 2020/367:

* **%HA** (highly annoyed) on Lden: Guski, Schreckenberg & Schuemer (2017),
  *Int J Environ Res Public Health* 14(12):1539, doi:10.3390/ijerph14121539.
* **%HSD** (highly sleep-disturbed) on Lnight: Basner & McGuire (2018),
  *Int J Environ Res Public Health* 15(3):519, doi:10.3390/ijerph15030519.

Each curve is ``%  = a + b·L + c·L²``. Outside the evaluation range:

* below ``range[0]`` the function gives ``below`` (default 0: no estimated cases). The
  quadratics turn upward again at low levels, which is an artefact, not a dose-response.
* above ``range[1]`` the level is held at ``range[1]`` (no extrapolation).

The ranges are our choice, kept inside the levels the underlying studies cover.

**Estimates only.** The BTS map gives LAeq,24h; the curves need Lden / Lnight. The
conversion offsets (``metric_offsets_db`` in ``config/thresholds.yaml``) are assumptions,
tested in P15. Results apply to neighbourhoods, not individuals, and the input noise is
modelled, not measured.
"""

from __future__ import annotations

import numpy as np

from ne import config

_GUSKI = "Guski et al. 2017 via WHO 2018 / Directive (EU) 2020/367"
_BASNER = "Basner & McGuire 2018 via WHO 2018 / Directive (EU) 2020/367"

#: %HA = a + b·Lden + c·Lden²
HA = {
    "road": {"coef": (78.9270, -3.1162, 0.0342), "range": (45.0, 75.0), "source": _GUSKI},
    "rail": {"coef": (38.1596, -2.05538, 0.0285), "range": (45.0, 75.0), "source": _GUSKI},
    "aviation": {"coef": (-50.9693, 1.0168, 0.0072), "range": (40.0, 75.0), "source": _GUSKI},
}

#: %HSD = a + b·Lnight + c·Lnight²
HSD = {
    "road": {"coef": (19.4312, -0.9336, 0.0126), "range": (40.0, 65.0), "source": _BASNER},
    "rail": {"coef": (67.5406, -3.1852, 0.0391), "range": (40.0, 65.0), "source": _BASNER},
    "aviation": {"coef": (16.7885, -0.9293, 0.0198), "range": (40.0, 65.0), "source": _BASNER},
}


def _evaluate(spec: dict, level, below: float):
    a, b, c = spec["coef"]
    lo, hi = spec["range"]
    lv = np.asarray(level, dtype="float64")
    held = np.minimum(lv, hi)
    pct = np.clip(a + b * held + c * held**2, 0.0, 100.0)
    out = np.where(np.isnan(lv) | (lv < lo), below, pct)
    return float(out) if out.ndim == 0 else out


def pct_ha(lden, source: str, below: float = 0.0):
    """Percent highly annoyed at ``lden`` (dB) for ``source`` (road / rail / aviation).

    ``NaN`` input (censored, below the mapped range) gives ``below``.
    """
    return _evaluate(HA[source], lden, below)


def pct_hsd(lnight, source: str, below: float = 0.0):
    """Percent highly sleep-disturbed at ``lnight`` (dB) for ``source``."""
    return _evaluate(HSD[source], lnight, below)


# --- metric conversion ----------------------------------------------------------------


def offsets_from_profile(day: float, evening: float, night: float) -> tuple[float, float]:
    """(Lden - LAeq24, Lnight - LAeq24) from the share of 24-hour sound energy per period.

    Periods: day 07-19 (12 h), evening 19-23 (4 h, +5 dB penalty), night 23-07 (8 h,
    +10 dB penalty). Shares must sum to 1. A flat profile gives (+6.4, 0.0).
    """
    if not np.isclose(day + evening + night, 1.0):
        raise ValueError("day + evening + night shares must sum to 1")
    lden = 10 * np.log10(day + evening * 10**0.5 + night * 10)
    lnight = 10 * np.log10(night * 24 / 8)
    return float(lden), float(lnight)


def _offset(source: str, key: str) -> float:
    return float(config.thresholds()["metric_offsets_db"][source][key])


def to_lden(laeq24, source: str, offset: float | None = None):
    """Estimated Lden = LAeq,24h + offset (config default per source)."""
    off = _offset(source, "lden_offset") if offset is None else offset
    return np.asarray(laeq24, dtype="float64") + off if np.ndim(laeq24) else laeq24 + off


def to_lnight(laeq24, source: str, offset: float | None = None):
    """Estimated Lnight = LAeq,24h + offset (config default per source)."""
    off = _offset(source, "lnight_offset") if offset is None else offset
    return np.asarray(laeq24, dtype="float64") + off if np.ndim(laeq24) else laeq24 + off
