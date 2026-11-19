"""Tests for ne.models.health (P14)."""

from __future__ import annotations

import pandas as pd
import pytest

from ne.models import health as h
from ne.models import who_erf as erf


def _bg(**shares):
    base = {f"pop_share_ge_{t}": 0.0 for t in (45, 50, 55, 60, 65, 70)}
    base.update(shares)
    return pd.DataFrame([{"bg_geoid": "X", "pop20": 1000, **base}])


def test_bands_split_residents():
    b = h.bands(_bg(pop_share_ge_45=0.6, pop_share_ge_50=0.5, pop_share_ge_55=0.2,
                    pop_share_ge_60=0.1, pop_share_ge_65=0.05, pop_share_ge_70=0.01))  # fmt: skip
    got = b.set_index("band_lo")["residents"]
    assert got[45] == pytest.approx(100)
    assert got[50] == pytest.approx(300)
    assert got[70] == pytest.approx(10)
    assert b["residents"].sum() == pytest.approx(600)  # the 400 below 45 dBA are not banded
    assert b.set_index("band_lo").loc[70, "band_hi"] == 75


def test_cases_total_and_excess_in_one_band():
    bg = _bg(pop_share_ge_45=1, pop_share_ge_50=1, pop_share_ge_55=1)  # all in 55-60
    c = h.cases(bg, "road", "HA")
    lden = 57.5 + 3.0
    total = 1000 * erf.pct_ha(lden, "road") / 100
    excess = 1000 * (erf.pct_ha(lden, "road") - erf.pct_ha(53, "road")) / 100
    assert c["total"].sum() == pytest.approx(total)
    assert c["excess"].sum() == pytest.approx(excess)


def test_no_excess_below_guideline():
    bg = _bg(pop_share_ge_45=1)  # all in 45-50 -> road Lden 50.5 < 53
    c = h.cases(bg, "road", "HA")
    assert c["excess"].sum() == 0
    assert c["total"].sum() > 0


def test_low_and_high_scenarios_bracket_central():
    bg = _bg(pop_share_ge_45=1, pop_share_ge_50=1, pop_share_ge_55=1, pop_share_ge_60=0.5)
    vals = {s: h.cases(bg, "aviation", "HSD", scenario=s)["excess"].sum() for s in h.SCENARIOS}
    assert vals["low"] <= vals["central"] <= vals["high"]
    assert vals["low"] < vals["high"]


def test_residents_below_45_can_be_placed_at_a_floor():
    bg = _bg()  # everyone below 45 dBA
    assert h.cases(bg, "aviation", "HA")["total"].sum() == 0
    c = h.cases(bg, "aviation", "HA", below45=42.5)
    lden = 42.5 + 3.0  # aviation Lden 45.5 is above the 45 dB guideline
    assert c["total"].sum() == pytest.approx(1000 * erf.pct_ha(lden, "aviation") / 100)
    assert c["excess"].sum() > 0


def test_extra_offset_shift_moves_estimates():
    bg = _bg(pop_share_ge_45=1, pop_share_ge_50=1)
    base = h.cases(bg, "rail", "HSD")["excess"].sum()
    up = h.cases(bg, "rail", "HSD", extra_shift=2.0)["excess"].sum()
    assert up > base
