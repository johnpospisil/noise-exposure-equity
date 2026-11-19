"""Tests for ne.build.app_data (P18)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from ne.build import app_data as ad


def test_weighted_percentile_counts_residents_in_quieter_places():
    d = pd.DataFrame({"cbsa": ["A"] * 4, "value": [0.0, 0.1, 0.1, 0.5], "pop20": [100] * 4})
    p = ad.weighted_percentile(d, "value")
    # value 0.5: 300 of 400 residents are quieter -> 75; ties count half
    assert p.tolist() == [12.5, 50.0, 50.0, 87.5]


def test_percentile_is_within_metro():
    d = pd.DataFrame({"cbsa": ["A", "A", "B", "B"], "value": [0.0, 1.0, 5.0, 9.0],
                      "pop20": [1, 1, 1, 1]})  # fmt: skip
    assert ad.weighted_percentile(d, "value").tolist() == [25.0, 75.0, 25.0, 75.0]


def test_records_are_compact_and_complete():
    row = {
        "bg_geoid": "360470001001", "metro": "New York", "pop20": 1234,
        "med_hh_income": 55555.4, "pct": 61.26,
        **{f"{s}_{t}": 0.123456 for s in ad.SOURCES for t in ad.THRESHOLDS},
    }  # fmt: skip
    rec = ad.record(pd.Series(row), metro_index={"New York": 0})
    assert len(rec) == len(ad.FIELDS)
    fields = dict(zip(ad.FIELDS, rec, strict=True))
    assert fields["metro"] == 0
    assert fields["income"] == 55555
    assert fields["all_55"] == 12.3  # percent, one decimal
    assert fields["pct"] == 61


@pytest.mark.skipif(not (ad.OUT / "meta.json").exists(), reason="app data not built")
def test_built_files_cover_every_block_group():
    meta = json.loads((ad.OUT / "meta.json").read_text())
    n = 0
    for st in meta["states"]:
        n += len(json.loads((ad.OUT / f"{st}.json").read_text()))
    assert n == 85_392
    assert meta["fields"] == ad.FIELDS
