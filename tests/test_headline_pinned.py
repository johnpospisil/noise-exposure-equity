"""Pinned headline numbers (P19).

These are the numbers the article and README lead with. They are rebuilt from the committed
result tables by ``ne.report.build()``; if a pipeline change moves any of them, this test
fails, and the article, README and distribution drafts must be checked before it is updated.
"""

from __future__ import annotations

import pytest

from ne import report

PINNED = {
    # exposure, 2022 map, all 20 metros
    "residents_m": "126.1",
    "block_groups": "85,392",
    "all_ge55": "10.4",
    "q1_55": "15.2",
    "q5_55": "6.5",
    "q_ratio_55": "2.4",
    "q1_65": "1.8",
    "q5_65": "0.9",
    "metros_q1_gt_q5": "20",
    "aviation_ratio_55": "3.5",
    "rail_ratio_55": "3.4",
    "road_ratio_55": "1.7",
    "race_white_55": "8.2",
    "race_black_55": "12.2",
    "race_hispanic_55": "12.8",
    "race_asian_55": "11.8",
    # BTS / UW benchmark
    "ours_ge60_2020": "3.5",
    "uw_ge60": "3.6",
    # regression
    "gap_a": "+8.6",
    "gap_b": "+5.3",
    "gap_c": "−1.2",
    "moran_i": "0.66",
    # health (millions, extra above WHO guideline levels)
    "ha_aviation_m": "2.9",
    "ha_road_m": "0.8",
    "ha_rail_m": "0.7",
    "hsd_rail_m": "0.6",
    # NYC
    "nyc_noise_irr": "0.99",
    "nyc_gent_combined_pct": "14",
    "nyc_gent_combined_ci": "6 to 22",
}


@pytest.fixture(scope="module")
def values() -> dict[str, str]:
    return report.build().values


@pytest.mark.parametrize("key", sorted(PINNED))
def test_headline_number_is_pinned(values, key):
    assert values[key] == PINNED[key]
