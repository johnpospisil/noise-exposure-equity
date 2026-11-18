"""NYC 311 noise complaints (2010-present) from NYC Open Data (Socrata SODA API).

* ``76ig-c548``: 311 Service Requests 2010-2019; ``erm2-nwe9``: 2020-present.
* Filter: ``complaint_type like 'Noise%'``, minus ``Noise Survey`` (not a complaint).
* Fetched one calendar month at a time (resumable). Months more than two months old are
  cached for good; recent months are re-fetched because the city keeps updating them.
* Street addresses are not downloaded. Coordinates stay local; only tract-level counts are
  ever published (NYC Open Data terms + project rule).

Analysis window (decision P05): data are kept from 2010, analysis uses **2016 onward**,
because 311 adoption roughly doubled complaint volume from 2010 to 2016.

Outputs:

* ``data/raw/nyc311/{YYYY-MM}.parquet``: one file per month (cache).
* ``data/interim/nyc311/noise/year=YYYY/*.parquet``: typed, de-duplicated, with ``noise_group``.

Usage::

    uv run python -m ne.ingest.nyc311                 # 2010-01 to the current month
    uv run python -m ne.ingest.nyc311 --start 2024-01 --end 2024-03
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ne import config

BASE = "https://data.cityofnewyork.us/resource"
DATASETS = {"76ig-c548": (2010, 2019), "erm2-nwe9": (2020, 9999)}
RAW = config.RAW_DIR / "nyc311"
OUT = config.INTERIM_DIR / "nyc311" / "noise"
PAGE = 200_000
START = "2010-01"
ANALYSIS_START_YEAR = 2016

COLUMNS = [
    "unique_key", "created_date", "closed_date", "agency", "complaint_type", "descriptor",
    "location_type", "incident_zip", "borough", "community_board", "bbl", "address_type",
    "latitude", "longitude", "status", "open_data_channel_type",
]  # fmt: skip
DATE_COLS = ["created_date", "closed_date"]

#: complaint_type -> analysis group. Helicopter is aviation (decision P05; reported separately
#: because of its post-2019 jump). Generic "Noise" is DEP-handled (construction, alarms, etc.).
NOISE_GROUPS = {
    "Noise - Residential": "residential",
    "Noise - Street/Sidewalk": "street",
    "Noise - Vehicle": "vehicle",
    "Noise - Commercial": "commercial",
    "Noise": "dep_other",
    "Noise - Helicopter": "helicopter",
    "Noise - Park": "park",
    "Noise - House of Worship": "worship",
}
EXCLUDED_TYPES = {"Noise Survey"}

#: generous lon/lat box around the five boroughs, for QA
NYC_BBOX = (-74.27, 40.49, -73.68, 40.92)


# --- months & routing -----------------------------------------------------------------


def months(start: str, end: str) -> list[str]:
    """Inclusive list of 'YYYY-MM' strings."""
    p = pd.period_range(start, end, freq="M")
    return [str(x) for x in p]


def dataset_for(month: str) -> str:
    year = int(month[:4])
    for name, (lo, hi) in DATASETS.items():
        if lo <= year <= hi:
            return name
    raise ValueError(month)


def is_settled(month: str, today: dt.date | None = None) -> bool:
    """True once a month is at least two full months in the past."""
    today = today or dt.date.today()
    return pd.Period(month, "M") <= pd.Period(today, "M") - 2


# --- fetch ----------------------------------------------------------------------------

_session = requests.Session()
if config.SOCRATA_APP_TOKEN:
    _session.headers["X-App-Token"] = config.SOCRATA_APP_TOKEN


@retry(stop=stop_after_attempt(6), wait=wait_exponential(min=4, max=120), reraise=True)
def _get_csv(url: str, params: dict) -> pd.DataFrame:
    r = _session.get(url, params=params, timeout=600)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), dtype=str, keep_default_na=False, na_values=[""])


def fetch_month(month: str) -> pd.DataFrame:
    name = dataset_for(month)
    start = pd.Period(month, "M").start_time
    end = (pd.Period(month, "M") + 1).start_time
    where = (
        "complaint_type like 'Noise%' "
        f"and created_date >= '{start:%Y-%m-%dT%H:%M:%S}' "
        f"and created_date < '{end:%Y-%m-%dT%H:%M:%S}'"
    )
    pages, offset = [], 0
    while True:
        df = _get_csv(
            f"{BASE}/{name}.csv",
            {
                "$select": ",".join(COLUMNS),
                "$where": where,
                "$order": "unique_key",
                "$limit": PAGE,
                "$offset": offset,
            },
        )
        pages.append(df)
        if len(df) < PAGE:
            break
        offset += PAGE
    out = pd.concat(pages, ignore_index=True).reindex(columns=COLUMNS)
    out["source_dataset"] = name
    return out


def month_path(month: str):
    return RAW / f"{month}.parquet"


def fetch_all(start: str, end: str, workers: int = 4, refresh: bool = False) -> list[str]:
    RAW.mkdir(parents=True, exist_ok=True)
    todo = [
        m for m in months(start, end) if refresh or not month_path(m).exists() or not is_settled(m)
    ]
    print(f"fetching {len(todo)} months ({len(months(start, end)) - len(todo)} cached) ...")
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch_month, m): m for m in todo}
        for i, f in enumerate(as_completed(futs), 1):
            m = futs[f]
            df = f.result()
            df.to_parquet(month_path(m), index=False)
            print(f"[{i}/{len(todo)}] {m}: {len(df):,} rows", flush=True)
    return todo


# --- clean ----------------------------------------------------------------------------


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Type columns, drop excluded types, add ``noise_group`` and ``year``."""
    df = raw[~raw["complaint_type"].isin(EXCLUDED_TYPES)].copy()
    df["unique_key"] = pd.to_numeric(df["unique_key"], errors="coerce").astype("Int64")
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ("latitude", "longitude"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["noise_group"] = df["complaint_type"].map(NOISE_GROUPS).fillna("other")
    df["year"] = df["created_date"].dt.year.astype("Int16")
    return df


def build_dataset(start: str, end: str) -> pd.DataFrame:
    files = [month_path(m) for m in months(start, end) if month_path(m).exists()]
    df = clean(pd.concat((pd.read_parquet(f) for f in files), ignore_index=True))
    n0 = len(df)
    df = df.drop_duplicates("unique_key")
    print(f"dropped {n0 - len(df):,} duplicate unique_key rows")
    if OUT.exists():
        import shutil

        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    # drop pandas metadata: it records `year` as Int16, which clashes with the partition
    # column on read (`pd.read_parquet` then returns `year` as a category)
    table = pa.Table.from_pandas(df, preserve_index=False).replace_schema_metadata(None)
    ds.write_dataset(
        table,
        OUT,
        format="parquet",
        partitioning=ds.partitioning(pa.schema([("year", pa.int16())]), flavor="hive"),
    )
    return df


# --- QA -------------------------------------------------------------------------------


def geocode_qa(df: pd.DataFrame) -> pd.DataFrame:
    """Per year: missing coordinates, outside the NYC box, repeat reports."""
    lon0, lat0, lon1, lat1 = NYC_BBOX
    has = df["latitude"].notna() & df["longitude"].notna()
    inside = has & df["longitude"].between(lon0, lon1) & df["latitude"].between(lat0, lat1)
    # same type + descriptor + point within the same minute: likely one event reported twice
    key = ["complaint_type", "descriptor", "latitude", "longitude"]
    minute = df["created_date"].dt.floor("min")
    repeat = has & df.assign(_m=minute).duplicated([*key, "_m"])
    g = pd.DataFrame({"year": df["year"], "has": has, "inside": inside, "repeat": repeat}).groupby(
        "year"
    )
    return pd.DataFrame(
        {
            "complaints": g.size(),
            "pct_missing_coords": 100 * (1 - g["has"].mean()),
            "pct_outside_nyc": 100 * (g["has"].sum() - g["inside"].sum()) / g.size(),
            "pct_same_point_same_minute": 100 * g["repeat"].mean(),
        }
    ).round(2)


def counts_by_year(df: pd.DataFrame) -> pd.DataFrame:
    t = df.pivot_table(index="year", columns="noise_group", values="unique_key", aggfunc="count")
    t = t.fillna(0).astype(int)
    t["total"] = t.sum(axis=1)
    return t


def run(start: str = START, end: str | None = None, workers: int = 4, refresh: bool = False):
    end = end or f"{dt.date.today():%Y-%m}"
    fetch_all(start, end, workers, refresh)
    df = build_dataset(start, end)
    print(f"{OUT.relative_to(config.ROOT)}: {len(df):,} complaints")
    print(counts_by_year(df).to_string())
    print(geocode_qa(df).to_string())
    return df


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", default=START)
    p.add_argument("--end", default=None)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--refresh", action="store_true")
    a = p.parse_args(argv)
    run(a.start, a.end, a.workers, a.refresh)


if __name__ == "__main__":
    main()
