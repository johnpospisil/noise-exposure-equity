"""Tests for ne.build.combine_sources and ne.models.who_erf (written before the code, P06)."""

from __future__ import annotations

import numpy as np
import pytest

from ne.build import combine_sources as cs
from ne.models import who_erf as erf

NAN = np.nan

# --- energy sum -----------------------------------------------------------------------


def test_two_equal_sources_add_3_db():
    assert cs.energy_sum([60.0, 60.0]) == pytest.approx(63.0103, abs=1e-4)


def test_ten_db_quieter_source_adds_0_4_db():
    assert cs.energy_sum([60.0, 50.0]) == pytest.approx(60.4139, abs=1e-4)


def test_energy_sum_over_cells_axis():
    road = np.array([60.0, 70.0, NAN])
    rail = np.array([60.0, NAN, NAN])
    out = cs.energy_sum(np.stack([road, rail]), policy="zero")
    assert out[0] == pytest.approx(63.0103, abs=1e-4)
    assert out[1] == 70.0
    assert np.isnan(out[2])  # every source censored -> still "< floor"


def test_censored_source_uses_floor_by_default():
    # 60 + (censored -> 45) = 10*log10(10^6 + 10^4.5)
    assert cs.energy_sum([60.0, NAN]) == pytest.approx(60.1352, abs=1e-4)
    assert cs.energy_sum([60.0, NAN], floor=40) == pytest.approx(60.0432, abs=1e-4)


def test_censored_source_contributes_nothing_under_zero_policy():
    assert cs.energy_sum([60.0, NAN], policy="zero") == 60.0


def test_all_censored_is_nan_under_any_policy():
    assert np.isnan(cs.energy_sum([NAN, NAN]))
    assert np.isnan(cs.energy_sum([NAN, NAN], policy="zero"))


def test_unknown_policy_raises():
    with pytest.raises(ValueError):
        cs.energy_sum([60.0, NAN], policy="ignore")


# --- energy mean ----------------------------------------------------------------------


def test_energy_mean_is_not_arithmetic():
    # arithmetic mean would be 65; energy mean is 10*log10((10^6 + 10^7) / 2)
    assert cs.energy_mean([60.0, 70.0]) == pytest.approx(67.4036, abs=1e-4)


def test_energy_mean_of_equal_levels_is_that_level():
    assert cs.energy_mean([55.0, 55.0, 55.0]) == pytest.approx(55.0)


def test_energy_mean_weights():
    # weights 3:1 -> 10*log10((3*10^6 + 10^7) / 4)
    assert cs.energy_mean([60.0, 70.0], weights=[3, 1]) == pytest.approx(65.1188, abs=1e-4)


def test_energy_mean_cap_limits_track_cells():
    levels = [125.0] + [50.0] * 999
    assert cs.energy_mean(levels) > 94  # one track cell dominates (decision P03)
    capped = cs.energy_mean(levels, cap=100)
    assert capped == pytest.approx(10 * np.log10((1e10 + 999 * 1e5) / 1000), abs=1e-6)


def test_energy_mean_censored_cells():
    # floor: censored cell counts as 45 dB; zero: it adds no energy but still counts as area
    assert cs.energy_mean([60.0, NAN]) == pytest.approx(
        10 * np.log10((1e6 + 10**4.5) / 2), abs=1e-6
    )
    assert cs.energy_mean([60.0, NAN], policy="zero") == pytest.approx(
        10 * np.log10(1e6 / 2), abs=1e-6
    )
    assert np.isnan(cs.energy_mean([NAN, NAN]))


# --- raster values --------------------------------------------------------------------


def test_from_raster_turns_nodata_into_nan():
    out = cs.from_raster(np.array([-9999.0, 52.5, 45.0], dtype="float32"))
    assert np.isnan(out[0]) and out[1] == 52.5 and out[2] == 45.0
    assert out.dtype == np.float64


# --- metric conversion ----------------------------------------------------------------


def test_offsets_from_flat_profile():
    # equal sound energy in every hour: Lnight = LAeq24, Lden = LAeq24 + 10*log10(...)
    lden, lnight = erf.offsets_from_profile(day=12 / 24, evening=4 / 24, night=8 / 24)
    assert lnight == pytest.approx(0.0, abs=1e-9)
    expected = 10 * np.log10(12 / 24 + 4 / 24 * 10**0.5 + 8 / 24 * 10)
    assert lden == pytest.approx(expected)  # ≈ 6.4 dB


def test_offsets_from_road_like_profile():
    lden, lnight = erf.offsets_from_profile(day=0.78, evening=0.14, night=0.08)
    assert lden == pytest.approx(3.06, abs=0.01)
    assert lnight == pytest.approx(-6.20, abs=0.01)


def test_profile_shares_must_sum_to_one():
    with pytest.raises(ValueError):
        erf.offsets_from_profile(day=0.8, evening=0.1, night=0.2)


def test_to_lden_and_lnight_use_config_offsets():
    assert erf.to_lden(60.0, "road") == pytest.approx(63.0)
    assert erf.to_lnight(60.0, "road") == pytest.approx(53.0)
    assert erf.to_lden(60.0, "road", offset=5.0) == 65.0


# --- exposure-response functions ------------------------------------------------------
# Anchors: the WHO 2018 guideline levels were set where each curve reaches about 10 %HA
# (Lden) or 3 %HSD (Lnight); WHO reports these values in the guideline text.


@pytest.mark.parametrize(
    ("source", "lden", "pct"),
    [("road", 53, 9.84), ("rail", 54, 10.28), ("aviation", 45, 9.37)],
)
def test_pct_ha_at_who_guideline_levels(source, lden, pct):
    assert erf.pct_ha(lden, source) == pytest.approx(pct, abs=0.01)


@pytest.mark.parametrize(
    ("source", "lnight", "pct"),
    [("road", 45, 2.93), ("rail", 44, 3.09), ("aviation", 40, 11.30)],
)
def test_pct_hsd_at_who_guideline_levels(source, lnight, pct):
    assert erf.pct_hsd(lnight, source) == pytest.approx(pct, abs=0.01)


def test_pct_ha_rises_with_level_inside_range():
    levels = np.arange(50, 76)
    for source in ("road", "rail", "aviation"):
        assert np.all(np.diff(erf.pct_ha(levels, source)) > 0), source


def test_below_range_gives_no_cases_and_above_range_is_held():
    lo, hi = erf.HA["road"]["range"]
    assert erf.pct_ha(lo - 5, "road") == 0.0
    assert erf.pct_ha(hi + 20, "road") == pytest.approx(erf.pct_ha(hi, "road"))
    assert np.isnan(erf.pct_ha(lo - 5, "road", below=NAN))


def test_censored_input_gives_no_cases():
    assert erf.pct_ha(NAN, "road") == 0.0


def test_unknown_source_raises():
    with pytest.raises(KeyError):
        erf.pct_ha(60, "subway")


def test_every_erf_has_a_citation():
    for table in (erf.HA, erf.HSD):
        for spec in table.values():
            assert spec["source"]
