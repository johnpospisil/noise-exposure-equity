# Processed data (committed)

Small analysis-ready tables. Each one lists its sources. Raw and interim data are never committed, and no NHGIS-derived file is ever placed here.

| File | Built by | Derived from |
|---|---|---|
| `bg_noise.parquet` | `make build` (`ne.build.zonal_stats`) | BTS National Transportation Noise Map (2016, 2018, 2020, 2022); U.S. Census Bureau 2020 TIGER/Line blocks and block groups (`POP20`) |
| `metro_exposure.csv` | `ne.build.zonal_stats.pooled_shares` | same as above |
| `bts_reconciliation.csv` | `ne.build.zonal_stats.reconcile` | same as above, plus published figures from UW DEOHS (2020 map) and BTS (2014 map) |
| `disparity_income.csv`, `disparity_race.csv` | `make models` (`ne.models.disparity`) | BTS National Transportation Noise Map; Census 2020 blocks (`POP20`); ACS 5-year (B19013 income, B03002 race/ethnicity) via the Census API |

All values come from **modelled noise, not measured noise**. BTS says the map should not be used to judge noise at individual locations. Results describe neighbourhoods, not individuals.

Citations:
- U.S. Department of Transportation, Bureau of Transportation Statistics, *National Transportation Noise Map*.
- U.S. Census Bureau, *2020 TIGER/Line Shapefiles* and *2020 Census Redistricting Data (P.L. 94-171)*.

Column definitions are in [DATA.md](../../DATA.md#derived-datasets).
