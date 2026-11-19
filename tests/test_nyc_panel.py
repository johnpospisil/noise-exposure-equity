"""Tests for ne.build.nyc_panel (P12)."""

from __future__ import annotations

import pandas as pd
import pytest

from ne.build import nyc_panel as npn

# --- gentrification typology -----------------------------------------------------------


def _tracts():
    # city medians (pop >= 500): income 40; change in BA+ share +2 points; rent growth 10 %
    return pd.DataFrame(
        {
            "tract": list("ABCDEF"),
            "pop_base": [1000, 1000, 1000, 1000, 1000, 100],
            "income_base": [30, 30, 40, 80, 50, 20],
            "ba_share_base": [0.10, 0.10, 0.10, 0.50, 0.30, 0.10],
            "ba_share_end": [0.20, 0.11, 0.20, 0.52, 0.32, 0.30],
            "rent_base": [1000, 1000, 1000, 2000, 1500, 1000],
            "rent_end": [1300, 1050, 1050, 2200, 1650, 1500],
        }
    )


def test_typology_classes():
    t = npn.typology(_tracts()).set_index("tract")["typology"]
    assert t["A"] == "Low-income, gentrifying"  # BA +10 pts and rent +30 %
    assert t["B"] == "Low-income, not gentrifying"  # neither grows faster than the city
    assert t["C"] == "Low-income, not gentrifying"  # at the median (eligible); rent not up
    assert t["D"] == "Higher-income"
    assert t["E"] == "Higher-income"
    assert t["F"] == "Too few residents"


# --- complaints -----------------------------------------------------------------------


def _complaints():
    ts = pd.to_datetime
    return pd.DataFrame(
        {
            "tract": ["T1", "T1", "T1", "T1", "T2"],
            "noise_group": ["residential", "residential", "residential", "street", "street"],
            "latitude": [40.1, 40.1, 40.1, 40.1, 40.2],
            "longitude": [-73.9, -73.9, -73.9, -73.9, -73.8],
            "created_date": ts(
                [
                    "2024-01-05 01:00",
                    "2024-01-05 23:00",
                    "2024-01-06 01:00",
                    "2024-01-05 02:00",
                    "2024-02-01 12:00",
                ]
            ),  # fmt: skip
        }
    )


def test_counts_and_location_days():
    c = npn.count_complaints(_complaints()).set_index(["tract", "month", "noise_group"])
    r = c.loc[("T1", pd.Period("2024-01", "M"), "residential")]
    assert r["complaints"] == 3
    assert r["location_days"] == 2  # same point twice on 5 Jan counts once
    assert c.loc[("T1", pd.Period("2024-01", "M"), "street"), "location_days"] == 1


def test_panel_grid_fills_zeros():
    c = npn.count_complaints(_complaints())
    p = npn.panel_grid(c, tracts=["T1", "T2", "T3"], start="2024-01", end="2024-02",
                       groups=["residential", "street"])  # fmt: skip
    assert len(p) == 3 * 2 * 2
    z = p.set_index(["tract", "month", "noise_group"])
    assert z.loc[("T3", pd.Period("2024-02", "M"), "street"), "complaints"] == 0
    assert z.loc[("T2", pd.Period("2024-02", "M"), "street"), "location_days"] == 1
    assert p["complaints"].sum() == 5


# --- real output ----------------------------------------------------------------------


@pytest.mark.skipif(not npn.PANEL.exists(), reason="NYC panel not built")
def test_panel_output():
    p = pd.read_parquet(npn.PANEL)
    tr = pd.read_parquet(npn.TRACTS)
    assert not p.duplicated(["tract", "month", "noise_group"]).any()
    assert (p["location_days"] <= p["complaints"]).all()
    assert set(p["tract"]) == set(tr["tract"])
    assert tr["tract"].str[:5].isin(npn.NYC_COUNTIES).all()
