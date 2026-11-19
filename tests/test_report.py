"""Tests for ne.report (P17): every number in the article is a defined variable."""

from __future__ import annotations

import re

import pytest
import yaml

from ne import report

QMD = report.REPORT / "index.qmd"
VARS = report.REPORT / "_variables.yml"


@pytest.mark.skipif(not VARS.exists(), reason="report variables not built")
def test_every_variable_in_the_article_is_defined():
    used = set(re.findall(r"\{\{< var ([a-z0-9_]+) >\}\}", QMD.read_text()))
    defined = set(yaml.safe_load(VARS.read_text()))
    assert used, "no variables found"
    assert not used - defined


def test_negative_numbers_use_a_typographic_minus():
    v = report.Vars()
    v.add("x", -1.25, "test")
    assert v.values["x"] == "−1.2"
    assert report._ci(-1.0, 2.0, "{:.1f}") == "−1.0 to 2.0"
