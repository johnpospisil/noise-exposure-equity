"""Project paths, environment variables and YAML config."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.environ.get("NE_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
FIGURES_DIR = ROOT / "figures"

CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY")
SOCRATA_APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN")


@cache
def load_yaml(name: str) -> dict:
    """Load ``config/<name>.yaml``."""
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f) or {}


def thresholds() -> dict:
    return load_yaml("thresholds")


def metros() -> list[dict]:
    return load_yaml("metros").get("metros", [])
