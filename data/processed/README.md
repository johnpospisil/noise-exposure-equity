# Processed data (committed)

Small analysis-ready tables. Each one lists its sources. Raw and interim data are never committed, and no NHGIS-derived file is ever placed here.

| File | Built by | Derived from |
|---|---|---|
| `bg_noise.parquet` | `make build` (`ne.build.zonal_stats`) | BTS National Transportation Noise Map (2016, 2018, 2020, 2022); U.S. Census Bureau 2020 TIGER/Line blocks and block groups (`POP20`) |
| `metro_exposure.csv` | `ne.build.zonal_stats.pooled_shares` | same as above |
| `bts_reconciliation.csv` | `ne.build.zonal_stats.reconcile` | same as above, plus published figures from UW DEOHS (2020 map) and BTS (2014 map) |
| `disparity_income.csv`, `disparity_race.csv` | `make models` (`ne.models.disparity`) | BTS National Transportation Noise Map; Census 2020 blocks (`POP20`); ACS 5-year (B19013 income, B03002 race/ethnicity) via the Census API |
| `spatial_models_pooled.csv`, `spatial_models_metro.csv`, `spatial_lm_diagnostics.csv` | `make models` (`ne.models.spatial_reg`) | as above, plus TIGER/Line 2020 block groups (contiguity, land area) |
| `change_over_time.csv` | `ne.models.spatial_reg.change_over_time` | as the disparity tables (BTS 2016–2022, ACS 2016–20 and 2018–22) |
| `nyc_panel.parquet`, `nyc_tracts.parquet` | `make build` (`ne.build.nyc_panel`) | NYC Open Data 311 (`76ig-c548`, `erm2-nwe9`), tract-level counts only; BTS 2022; Census 2020 blocks and tracts; ACS 5-year 2016–20, 2018–22, 2020–24 (tracts) |
| `complaints_nb_models.csv`, `complaints_nb_margins.csv` | `make models` (`ne.models.complaints_nb`) | as `nyc_panel.parquet` / `nyc_tracts.parquet` |
| `health_estimates.csv`, `health_by_income.csv` | `make models` (`ne.models.health`) | as the disparity tables, plus WHO 2018 exposure-response functions (Guski et al. 2017; Basner & McGuire 2018) |

All values come from **modelled noise, not measured noise**. BTS says the map should not be used to judge noise at individual locations. Results describe neighbourhoods, not individuals.

Citations:
- City of New York, *NYC Open Data: 311 Service Requests*.
- U.S. Department of Transportation, Bureau of Transportation Statistics, *National Transportation Noise Map*.
- U.S. Census Bureau, *2020 TIGER/Line Shapefiles* and *2020 Census Redistricting Data (P.L. 94-171)*.

Column definitions are in [DATA.md](../../DATA.md#derived-datasets).
