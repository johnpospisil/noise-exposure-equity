"""Tests for ne.ingest.tiger and ne.ingest.acs (synthetic inputs + checks on real outputs)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ne import config
from ne.ingest import acs, tiger

# --- metros ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "short"),
    [
        ("New York-Newark-Jersey City, NY-NJ-PA", "New York"),
        ("Washington-Arlington-Alexandria, DC-VA-MD-WV", "Washington"),
        ("St. Louis, MO-IL", "St. Louis"),
        ("Minneapolis-St. Paul-Bloomington, MN-WI", "Minneapolis"),
    ],
)
def test_short_name(title, short):
    assert tiger.short_name(title) == short


def test_select_metros_ranks_by_population_and_lists_counties():
    d = pd.DataFrame(
        {
            "cbsa": ["1", "1", "2", "3"],
            "cbsa_title": ["Big, AA-BB", "Big, AA-BB", "Mid, CC", "Small, DD"],
            "state": ["01", "02", "03", "04"],
            "county": ["01001", "02001", "03001", "04001"],
            "county_name": list("abcd"),
            "central": [True] * 4,
        }
    )
    pop = pd.DataFrame({"cbsa": ["1", "2", "3", "9"], "pop2020": [300, 200, 100, 999]})
    m = tiger.select_metros(d, pop, n=2)
    assert [x["cbsa"] for x in m] == ["1", "2"]  # cbsa 9 is not a metro in the delineation
    assert m[0]["states"] == ["01", "02"] and m[0]["counties"] == ["01001", "02001"]
    assert m[0]["short"] == "Big" and m[0]["rank"] == 1


# --- ACS ------------------------------------------------------------------------------


def _raw_row(**overrides):
    base = dict.fromkeys(acs.VARIABLES, "0")
    base.update(
        {
            "B01003_001E": "1000",
            "B01003_001M": "100",
            "B19013_001E": "50000",
            "B19013_001M": "16450",  # CV = (16450/1.645)/50000 = 0.2
            "B03002_001E": "1000",
            "B03002_003E": "500",
            "B03002_004E": "200",
            "B03002_006E": "100",
            "B03002_012E": "150",
            "B25003_001E": "400",
            "B25003_003E": "100",
            "B01001_003E": "100",  # under 18 (male under 5)
            "B01001_027E": "100",  # under 18 (female under 5)
            "B01001_020E": "50",  # 65+ (male 65-66)
        }
    )
    base.update(overrides)
    return base


def _frame(*rows):
    header = [*acs.VARIABLES, "state", "county", "tract", "block group"]
    data = [[r[v] for v in acs.VARIABLES] + ["36", "061", "000100", "1"] for r in rows]
    return acs.to_frame([header, *data])


def test_derive_computes_shares_and_cv():
    d = acs.derive(_frame(_raw_row()), cv_flag=0.30).iloc[0]
    assert d["geoid"] == "360610001001"
    assert d["med_hh_income_cv"] == pytest.approx(0.2)
    assert not d["income_cv_high"] and not d["income_missing"]
    assert d["pct_nh_white"] == 0.5 and d["pct_hispanic"] == 0.15
    assert d["pct_other"] == pytest.approx(0.05)
    assert d["pct_renter"] == 0.25
    assert d["pct_under18"] == 0.2 and d["pct_65plus"] == 0.05


def test_annotation_codes_become_missing_and_flagged():
    row = _raw_row(B19013_001E="-666666666", B19013_001M="-222222222")
    d = acs.derive(_frame(row), cv_flag=0.30).iloc[0]
    assert np.isnan(d["med_hh_income"]) and d["income_missing"]
    assert not d["income_cv_high"]  # missing is its own flag


def test_high_cv_and_topcoding_flags():
    row = _raw_row(B19013_001E="250001", B19013_001M="200000")
    d = acs.derive(_frame(row), cv_flag=0.30).iloc[0]
    assert d["income_topcoded"] and d["income_cv_high"]


def test_zero_population_gives_missing_shares_not_errors():
    row = _raw_row(B01003_001E="0", B03002_001E="0", B25003_001E="0")
    d = acs.derive(_frame(row), cv_flag=0.30).iloc[0]
    assert np.isnan(d["pct_nh_white"]) and np.isnan(d["pct_renter"])
    assert np.isnan(d["pct_under18"])


# --- real outputs ---------------------------------------------------------------------

CENSUS = config.INTERIM_DIR / "census"
needs_tiger = pytest.mark.skipif(
    not (CENSUS / "bg_2020.parquet").exists(), reason="TIGER not ingested"
)
needs_acs = pytest.mark.skipif(not acs.OUT.exists(), reason="ACS not ingested")


def test_metros_yaml_has_20_metros():
    m = config.metros()
    if not m:
        pytest.skip("metros.yaml not written")
    assert len(m) == 20
    assert m[0]["short"] == "New York"
    assert all(len(c) == 5 for x in m for c in x["counties"])


@needs_tiger
def test_block_groups_unique_and_in_metros():
    import geopandas as gpd

    bg = gpd.read_parquet(CENSUS / "bg_2020.parquet")
    assert bg["geoid"].is_unique and bg["geoid"].str.len().eq(12).all()
    assert set(bg["cbsa"]) == {m["cbsa"] for m in config.metros()}


@needs_tiger
def test_block_population_matches_metro_totals():
    """Sum of 2020 block POP20 per metro equals the 2020 Census metro population."""
    blocks = pd.concat(
        pd.read_parquet(p, columns=["cbsa", "pop20"])
        for p in (CENSUS / "blocks_2020").glob("*.parquet")
    )
    got = blocks.groupby("cbsa")["pop20"].sum()
    for m in config.metros():
        assert got[m["cbsa"]] == m["pop2020"], m["short"]


@needs_acs
@needs_tiger
def test_acs_block_groups_match_tiger():
    bg = set(pd.read_parquet(CENSUS / "bg_2020.parquet", columns=["geoid"])["geoid"])
    df = pd.read_parquet(acs.OUT, columns=["geoid", "acs_end_year"])
    for _, g in df.groupby("acs_end_year"):
        assert g["geoid"].is_unique
        assert set(g["geoid"]) == bg
