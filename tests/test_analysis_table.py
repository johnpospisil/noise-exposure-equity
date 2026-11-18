"""Tests for ne.build.analysis_table (P09)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ne.build import analysis_table as at


def test_acs_vintage_for_each_map_year():
    assert at.ACS_FOR_MAP == {2016: 2020, 2018: 2020, 2020: 2022, 2022: 2022}


def test_quintiles_split_residents_evenly_within_metro():
    df = pd.DataFrame(
        {
            "cbsa": ["A"] * 10 + ["B"] * 5,
            "med_hh_income": list(range(10, 110, 10)) + [1, 2, 3, 4, 5],
            "pop": [100] * 15,
        }
    )
    q = at.income_quintiles(df)
    assert list(q[:10]) == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert list(q[10:]) == [1, 2, 3, 4, 5]  # ranked inside metro B, not against A


def test_quintiles_are_population_weighted():
    # the poorest block group holds 60 % of residents -> it alone spans quintiles 1-3;
    # its midpoint (30 %) puts it in quintile 2
    df = pd.DataFrame({"cbsa": ["A"] * 3, "med_hh_income": [10, 20, 30], "pop": [600, 200, 200]})
    assert list(at.income_quintiles(df)) == [2, 4, 5]


def test_missing_income_or_population_gets_no_quintile():
    df = pd.DataFrame(
        {"cbsa": ["A"] * 4, "med_hh_income": [10, np.nan, 30, 40], "pop": [100, 100, 0, 100]}
    )
    q = at.income_quintiles(df)
    assert pd.isna(q.iloc[1]) and pd.isna(q.iloc[2])
    assert q.dtype == "Int8"


# --- real output ----------------------------------------------------------------------


@pytest.mark.skipif(not at.OUT.exists(), reason="analysis table not built")
def test_analysis_table():
    df = pd.read_parquet(at.OUT)
    assert not df.duplicated(["year", "source", "bg_geoid"]).any()
    assert set(df["acs_end_year"]) == {2020, 2022}
    assert (df["year"].map(at.ACS_FOR_MAP) == df["acs_end_year"]).all()
    q = df[(df["year"] == 2022) & (df["source"] == "road")]
    # each quintile holds about a fifth of each metro's residents with an income estimate
    share = q.groupby(["cbsa", "income_quintile"])["pop"].sum() / q.groupby("cbsa")["pop"].sum()
    assert share.between(0.15, 0.25).all()
    assert q["metro"].notna().all()
