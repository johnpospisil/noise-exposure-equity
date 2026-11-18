"""Tests for ne.ingest.nyc311."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from ne.ingest import nyc311 as n

# --- routing --------------------------------------------------------------------------


def test_months_inclusive():
    assert n.months("2019-11", "2020-02") == ["2019-11", "2019-12", "2020-01", "2020-02"]


@pytest.mark.parametrize(
    ("month", "dataset"),
    [("2010-01", "76ig-c548"), ("2019-12", "76ig-c548"), ("2020-01", "erm2-nwe9")],
)
def test_dataset_for(month, dataset):
    assert n.dataset_for(month) == dataset


def test_is_settled():
    today = dt.date(2026, 11, 17)
    assert n.is_settled("2026-09", today)
    assert not n.is_settled("2026-10", today)
    assert not n.is_settled("2026-11", today)


# --- clean ----------------------------------------------------------------------------


def _raw(**cols):
    base = {c: ["x"] for c in n.COLUMNS}
    base.update(
        unique_key=["1"],
        created_date=["2021-07-04T23:10:00.000"],
        closed_date=[""],
        complaint_type=["Noise - Helicopter"],
        latitude=["40.75"],
        longitude=["-73.98"],
    )
    base.update(cols)
    return pd.DataFrame(base).replace("", None)


def test_clean_types_and_groups():
    df = n.clean(_raw())
    r = df.iloc[0]
    assert r["noise_group"] == "helicopter"
    assert r["year"] == 2021
    assert r["created_date"] == pd.Timestamp("2021-07-04 23:10")
    assert pd.isna(r["closed_date"])
    assert r["latitude"] == 40.75


def test_clean_drops_noise_survey_and_marks_unknown_types():
    raw = pd.concat(
        [_raw(complaint_type=["Noise Survey"]), _raw(complaint_type=["Noise - Bagpipes"])]
    )
    df = n.clean(raw)
    assert list(df["noise_group"]) == ["other"]


# --- QA -------------------------------------------------------------------------------


def test_geocode_qa():
    rows = pd.concat(
        [
            _raw(unique_key=["1"]),  # good
            _raw(unique_key=["2"]),  # same type/point/minute as 1 -> repeat
            _raw(unique_key=["3"], latitude=[None], longitude=[None]),  # missing
            _raw(unique_key=["4"], latitude=["34.05"], longitude=["-118.24"]),  # LA
        ],
        ignore_index=True,
    )
    q = n.geocode_qa(n.clean(rows)).loc[2021]
    assert q["complaints"] == 4
    assert q["pct_missing_coords"] == 25
    assert q["pct_outside_nyc"] == 25
    assert q["pct_same_point_same_minute"] == 25


# --- real output ----------------------------------------------------------------------


@pytest.mark.skipif(not n.OUT.exists(), reason="311 not ingested")
def test_ingested_dataset():
    df = pd.read_parquet(n.OUT, columns=["unique_key", "complaint_type", "year"])
    assert df["unique_key"].is_unique
    assert "Noise Survey" not in set(df["complaint_type"])
    assert df["year"].astype(int).min() == 2010
    assert len(df) > 8_000_000
