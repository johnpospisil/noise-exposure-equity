"""Tests for ne.models.robustness (P15)."""

from __future__ import annotations

from ne.models import robustness as rb


def test_flags_sign_and_significance_changes():
    f = rb.flags(base=2.0, base_lo=1.0, base_hi=3.0, value=-0.5, lo=-1.0, hi=0.2, null=0.0)
    assert f == {"sign_change": True, "significance_change": True}
    f = rb.flags(base=2.0, base_lo=1.0, base_hi=3.0, value=1.5, lo=0.5, hi=2.5, null=0.0)
    assert f == {"sign_change": False, "significance_change": False}


def test_flags_for_ratios_use_one_as_null():
    f = rb.flags(base=1.14, base_lo=1.06, base_hi=1.23, value=1.05, lo=0.97, hi=1.13, null=1.0)
    assert f == {"sign_change": False, "significance_change": True}


def test_flags_without_intervals_only_check_sign():
    f = rb.flags(base=2.4, value=1.8, null=1.0)
    assert f == {"sign_change": False, "significance_change": None}
