"""Metro selection and TIGER/Line 2020 boundaries for the study metros.

* Metro definitions: OMB March 2020 CBSA delineations (``list1_2020.xls``). We use the 2020
  delineations, not 2023, because they match 2020 Census block/block-group geography (the 2023
  delineations replace Connecticut counties with planning regions).
* Ranking: 2020 Census P.L. 94-171 total population of each Metropolitan Statistical Area.
* Boundaries: TIGER/Line 2020 block groups, tracts and blocks (blocks carry ``POP20``, the
  2020 Census block population used as weights inside block groups), kept for metro counties
  only, written as GeoParquet in EPSG:4269 (as published).

Outputs:

* ``config/metros.yaml``: the selected metros, their states and counties.
* ``data/interim/census/{bg,tract}_2020.parquet``: GeoParquet with a ``cbsa`` column.
* ``data/interim/census/blocks_2020/{state_fips}.parquet``: blocks with POP20, HOUSING20.
* ``data/interim/census/cbsa_2020.parquet``: metro boundaries.

Usage::

    uv run python -m ne.ingest.tiger            # select metros + all boundaries
    uv run python -m ne.ingest.tiger --n 20 --layers bg tract
"""

from __future__ import annotations

import argparse
import re
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import pandas as pd
import yaml

from ne import config
from ne.ingest.http import download, get_json

RAW = config.RAW_DIR / "census"
OUT = config.INTERIM_DIR / "census"
TIGER = "https://www2.census.gov/geo/tiger/TIGER2020"
DELINEATION_URL = (
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/"
    "2020/delineation-files/list1_2020.xls"
)
CBSA_POP_URL = "https://api.census.gov/data/2020/dec/pl"


# --- metros ---------------------------------------------------------------------------


def load_delineation() -> pd.DataFrame:
    """County -> CBSA table (metropolitan areas only)."""
    p = download(DELINEATION_URL, RAW / "list1_2020.xls")
    df = pd.read_excel(p, header=2, dtype=str, engine="calamine")
    df = df[df["CBSA Code"].str.fullmatch(r"\d{5}", na=False)]
    df = df[df["Metropolitan/Micropolitan Statistical Area"] == "Metropolitan Statistical Area"]
    return pd.DataFrame(
        {
            "cbsa": df["CBSA Code"],
            "cbsa_title": df["CBSA Title"],
            "state": df["FIPS State Code"],
            "county": df["FIPS State Code"] + df["FIPS County Code"],
            "county_name": df["County/County Equivalent"],
            "central": df["Central/Outlying County"].eq("Central"),
        }
    ).reset_index(drop=True)


def short_name(title: str) -> str:
    """'Washington-Arlington-Alexandria, DC-VA-MD-WV' -> 'Washington'."""
    return re.split(r"[-,]", title, maxsplit=1)[0].strip()


def cbsa_population() -> pd.DataFrame:
    rows = get_json(
        CBSA_POP_URL,
        {
            "get": "NAME,P1_001N",
            "for": "metropolitan statistical area/micropolitan statistical area:*",
            "key": config.CENSUS_API_KEY,
        },
    )
    df = pd.DataFrame(rows[1:], columns=rows[0])
    return pd.DataFrame(
        {
            "cbsa": df["metropolitan statistical area/micropolitan statistical area"],
            "pop2020": df["P1_001N"].astype(int),
        }
    )


def select_metros(delineation: pd.DataFrame, pop: pd.DataFrame, n: int = 20) -> list[dict]:
    """The ``n`` most populous metropolitan areas, with their states and counties."""
    titles = delineation.drop_duplicates("cbsa")[["cbsa", "cbsa_title"]]
    ranked = titles.merge(pop, on="cbsa").sort_values("pop2020", ascending=False).head(n)
    metros = []
    for rank, r in enumerate(ranked.itertuples(), 1):
        c = delineation[delineation["cbsa"] == r.cbsa]
        metros.append(
            {
                "rank": rank,
                "cbsa": r.cbsa,
                "short": short_name(r.cbsa_title),
                "name": r.cbsa_title,
                "pop2020": int(r.pop2020),
                "states": sorted(c["state"].unique().tolist()),
                "counties": sorted(c["county"].tolist()),
            }
        )
    return metros


def write_metros_yaml(metros: list[dict]) -> None:
    header = (
        "# Study metros: the largest Metropolitan Statistical Areas by 2020 Census population,\n"
        "# OMB March 2020 delineations. Written by `python -m ne.ingest.tiger`; do not edit.\n"
    )
    body = yaml.safe_dump({"metros": metros}, sort_keys=False, default_flow_style=None)
    (config.CONFIG_DIR / "metros.yaml").write_text(header + body)
    config.load_yaml.cache_clear()


# --- boundaries -----------------------------------------------------------------------


def _state_layer(layer: str, state: str) -> gpd.GeoDataFrame:
    name = {
        "bg": f"tl_2020_{state}_bg.zip",
        "tract": f"tl_2020_{state}_tract.zip",
        "block": f"tl_2020_{state}_tabblock20.zip",
    }[layer]
    folder = {"bg": "BG", "tract": "TRACT", "block": "TABBLOCK20"}[layer]
    z = download(f"{TIGER}/{folder}/{name}", RAW / "tiger" / folder / name)
    return gpd.read_file(f"zip://{z}")


def county_to_cbsa(metros: list[dict]) -> dict[str, str]:
    return {c: m["cbsa"] for m in metros for c in m["counties"]}


def build_layer(layer: str, metros: list[dict], workers: int = 4) -> list:
    """Download one TIGER layer for every metro state and keep metro counties only."""
    c2m = county_to_cbsa(metros)
    states = sorted({s for m in metros for s in m["states"]})
    OUT.mkdir(parents=True, exist_ok=True)

    def one(state):
        g = _state_layer(layer, state)
        if layer == "block":
            g = g.rename(
                columns={"GEOID20": "GEOID", "STATEFP20": "STATEFP", "COUNTYFP20": "COUNTYFP"}
            )
        county = g["STATEFP"] + g["COUNTYFP"]
        g = g[county.isin(c2m)].copy()
        g["cbsa"] = (g["STATEFP"] + g["COUNTYFP"]).map(c2m)
        if layer == "block":
            keep = ["GEOID", "cbsa", "POP20", "HOUSING20", "ALAND20", "AWATER20", "geometry"]
            g = g[keep].rename(columns=str.lower)
            g["bg_geoid"] = g["geoid"].str[:12]
            path = OUT / "blocks_2020" / f"{state}.parquet"
            path.parent.mkdir(exist_ok=True)
            g.to_parquet(path)
            return path, len(g), int(g["pop20"].sum())
        return g, len(g), None

    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(one, states))
    if layer == "block":
        return results
    keep = ["GEOID", "cbsa", "ALAND", "AWATER", "geometry"]
    g = pd.concat([r[0][keep] for r in results], ignore_index=True)
    g = gpd.GeoDataFrame(g.rename(columns=str.lower), crs=results[0][0].crs)
    g.to_parquet(OUT / f"{layer}_2020.parquet")
    return [(OUT / f"{layer}_2020.parquet", len(g), None)]


def build_cbsa(metros: list[dict]):
    z = download(
        f"{TIGER}/CBSA/tl_2020_us_cbsa.zip", RAW / "tiger" / "CBSA" / "tl_2020_us_cbsa.zip"
    )
    g = gpd.read_file(f"zip://{z}")
    g = g[g["GEOID"].isin([m["cbsa"] for m in metros])][["GEOID", "NAME", "geometry"]]
    g = g.rename(columns={"GEOID": "cbsa", "NAME": "name"})
    g.to_parquet(OUT / "cbsa_2020.parquet")
    return g


def run(n: int = 20, layers=("bg", "tract", "block")):
    metros = select_metros(load_delineation(), cbsa_population(), n)
    write_metros_yaml(metros)
    print(pd.DataFrame(metros)[["rank", "cbsa", "short", "pop2020"]].to_string(index=False))
    build_cbsa(metros)
    for layer in layers:
        for path, rows, pop in build_layer(layer, metros):
            extra = f", pop20 {pop:,}" if pop is not None else ""
            print(f"{layer}: {path.relative_to(config.ROOT)} {rows:,} rows{extra}")
    return metros


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--layers", nargs="*", default=["bg", "tract", "block"])
    a = p.parse_args(argv)
    run(a.n, a.layers)


if __name__ == "__main__":
    main()
