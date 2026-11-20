# Loud and Unequal

**Transportation noise, complaints and who gets heard.**

- **Read the article:** <https://johnpospisil.github.io/noise-exposure-equity/report/>
- **Look up your neighbourhood:** <https://johnpospisil.github.io/noise-exposure-equity/app/>
- **Interactive New York map:** <https://johnpospisil.github.io/noise-exposure-equity/map/>

This project combines the U.S. Bureau of Transportation Statistics' [National Transportation Noise Map](https://www.bts.gov/geospatial/national-transportation-noise-map) (road, rail and aircraft; 2022 release, with 2016–2020 for comparison) with Census and American Community Survey data. It measures who lives with transportation noise in the 20 largest U.S. metro areas, which together hold 126 million people in 85,392 block groups. It then uses 8.6 million NYC 311 noise complaints to ask a second question: do complaints follow the noise, or do they follow who complains?

## What we found

- **Lower-income neighbourhoods are louder, in every one of the 20 metros.** On the 2022 map, 15.2% of residents in each metro's lowest-income fifth of neighbourhoods live at 55 dBA or more (24-hour average). In the highest-income fifth it is 6.5%, so the lowest fifth is 2.4 times as exposed. At the stricter 65 dBA level the shares are 1.8% and 0.9%.
- **Rail and aircraft noise are the most unequal.** At 55 dBA the lowest-income fifth is 3.5 times as exposed to aircraft noise as the highest fifth, and 3.4 times to rail noise. For major roads the figure is 1.7 times.
- **Black, Hispanic and Asian residents are more exposed than White residents**: 12.2%, 12.8% and 11.8% at 55 dBA, against 8.2%.
- **Much of the income gap runs through renting and density.** With metro fixed effects the lowest-income fifth is 8.6 points more exposed than the highest. Adding race brings this to 5.3 points. After also adding the share of renters and population density, little separate income gap remains. Louder places are renter-heavy, dense places, and those are where lower-income households live.
- **The health burden is large.** Using WHO 2018 exposure-response curves, about 0.8 million more people are highly annoyed by major-road noise than at WHO guideline levels, 0.7 million by rail noise, and at least 2.9 million by aircraft noise. About 0.6 million more are highly sleep-disturbed by rail noise. Every source falls hardest on the lowest-income fifth.
- **In New York, complaints don't track modelled noise.** 311 complaints barely rise with modelled transportation noise (rate ratio 0.99). Gentrifying low-income tracts file 14% more complaints than other low-income tracts with the same modelled noise and demographics (95% CI 6 to 22%). This part of the analysis is exploratory.

All figures are **modelled, not measured**, and describe **neighbourhoods, not individuals**. Details, ranges and robustness checks are in the [article](https://johnpospisil.github.io/noise-exposure-equity/report/).

## What this does not show

- BTS models major roads, rail (no subways) and aircraft only. Construction, nightlife, neighbours and local streets are not in the map.
- BTS warns that the map should not be used to judge noise at an individual location. The lookup app therefore reports the census block group, not the address.
- Results describe neighbourhoods. They do not say any particular low-income household is exposed (the ecological fallacy).
- The 311 data measures who reports noise, not how much noise there is.
- Change over time is descriptive only. BTS changes which roads it models between releases, and the 2020 map reflects COVID-era traffic.

## Reproduce it

You need macOS or Linux, [uv](https://docs.astral.sh/uv/), [Quarto](https://quarto.org) 1.10+, about 30 GB of free disk and a free [Census API key](https://api.census.gov/data/key_signup.html). A NYC Open Data app token is optional but speeds up the 311 download.

```bash
uv sync                  # Python 3.12 environment
cp .env.example .env     # add CENSUS_API_KEY (and SOCRATA_APP_TOKEN)
make help                # list the steps
make test                # 171 tests
make all                 # ingest -> build -> models -> figures -> report -> app
make site                # assemble report + app + map into _site/
```

**One manual step.** The BTS download page blocks scripted access. Download the CONUS road, rail and aviation zips for each year from <https://www.bts.gov/geospatial/national-transportation-noise-map> in a browser into `data/raw/bts/zips/`. `make ingest` checks them against `data/raw/bts/manifest.csv` and does the rest. Census, TIGER and 311 data download automatically.

A full run takes about 2 hours on a laptop (measured from a clean clone: 70 minutes to convert the BTS rasters, 50 minutes for the zonal statistics, a few minutes for everything else). Rasters are read one state at a time, so memory stays under about 8 GB. The most recent two months of 311 data are re-downloaded on each run, so NYC counts can move slightly as late reports arrive.

The site is published by [.github/workflows/pages.yml](.github/workflows/pages.yml). It rebuilds the article from the committed result tables and figures, so no raw data is needed in CI.

## Repository layout

| Path | What it holds |
|---|---|
| `src/ne/ingest/` | Downloads: BTS rasters, TIGER, ACS, NYC 311 |
| `src/ne/build/` | Decibel math, zonal statistics, analysis tables, NYC panel, app data |
| `src/ne/models/` | Disparity tables, spatial regression, complaint models, WHO health translation, robustness |
| `src/ne/viz/` | Every chart and map |
| `src/ne/report.py` | Turns result tables into the article's numbers (`report/claims.csv` traces each one) |
| `data/processed/` | Committed result tables, each with a `derived_from` column ([README](data/processed/README.md)) |
| `report/` | The Quarto article |
| `app/` | The static address lookup ([README](app/README.md)) |
| `docs/` | Method notes and results write-ups |

## Data and licences

All inputs are open. See [DATA.md](DATA.md) for URLs, versions, sizes and citations.

| Source | Terms |
|---|---|
| BTS National Transportation Noise Map (2016, 2018, 2020, 2022) | U.S. government work, public domain |
| U.S. Census Bureau: 2020 Census, ACS 5-year, TIGER/Line | U.S. government work, public domain |
| NYC Open Data, 311 Service Requests | NYC Open Data terms; published here as tract-level counts only |
| WHO 2018 Environmental Noise Guidelines; Guski et al. 2017; Basner & McGuire 2018 | Coefficients from published papers, cited |

Raw data is never committed. No IPUMS NHGIS data is used.

**Code:** MIT ([LICENSE](LICENSE)). **Derived tables and figures:** free to reuse with credit to this project and to the sources above.

## Citation

Pospisil, J. (2026). *Loud and Unequal: Transportation Noise, Complaints and Who Gets Heard.* <https://github.com/johnpospisil/noise-exposure-equity>
