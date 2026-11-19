# CLAUDE.md — Noise Exposure Equity (Project 17 / AU-6)

**Working title:** *Loud and Unequal: Transportation Noise, Complaints and Who Gets Heard*
**Spec:** [17-noise-exposure-equity.md](17-noise-exposure-equity.md) (source of truth for the research question, methods and charts)
**Plan created:** 2026-11-17

---

## How to work in this repo

1. Work through the prompts below **in order**. One prompt = one working session.
2. **At the end of every prompt, Claude must:**
   - **Show the deliverables**: list the files created or changed, show key tables or figures inline (or give their paths), and paste the test / validation output.
   - **Ask the questions** listed under that prompt, plus anything new that came up, before moving to the next prompt.
   - Tick the prompt here: `- [x] ✅ DONE! **Pxx: …** _Done YYYY-MM-DD: one-line result._` Add "✅ DONE" to a phase heading once all its items are done.
3. Raw data never goes in git. `data/raw/` and `data/interim/` are git-ignored; `data/processed/` keeps only small, analysis-ready Parquet/CSV (< 50 MB each).
4. Decibels are **never** averaged or added arithmetically. Use `ne.build.combine_sources` (energy sum: `10·log10(Σ 10^(L/10))`) and energy means.
5. Every figure is made by code in `src/ne/viz/` and can be rebuilt with `make figures`.
6. Conclusions apply to **neighbourhoods only** (ecological fallacy). Modelled noise is not measured noise; say so wherever results are reported.
7. **Licences (see "Data licences" below).** NHGIS files are never committed, released, bundled into the app, or uploaded anywhere. Any table that reaches GitHub, a release or the app must say which sources it derives from.

### Stack
Python 3.12 · `uv` · `rasterio` / `rioxarray` / GDAL · `exactextract` (zonal stats) · `geopandas` · `duckdb` + Parquet · `pysal` (`libpysal`, `spreg`, `esda`) · `statsmodels` (negative binomial) · `matplotlib` + `plotly` · Quarto for the report · `pytest` + `ruff`.

---

## Data inventory: where it comes from and how big it is

Sizes marked † were **measured live on 2026-11-17**. Sizes marked ~ are estimates that P02 must check and correct.

| # | Source | Where | Access | What we take | Raw size | After processing |
|---|---|---|---|---|---|---|
| 1 | **BTS National Transportation Noise Map**, 2016, 2018, 2020, **2022 (new, released May 2026)** | bts.gov/geospatial/national-transportation-noise-map (blocks scripts: zip URLs copied once from a browser); docs v3 doi:10.21949/sysz-2y22; DataLumos archive (2020); UW DEOHS tract-level derivative (validation only) | Open, no key | 30 m FileGDB rasters, LAeq,24h, < 45 dB censored. CONUS road, aviation, rail (2018 passenger prototype; 2020 freight + passenger prototype; 2022 freight + passenger) | †2020 road zip ≈ 855 MB, rail ≈ 605 MB (DataLumos listing); ~0.3–1 GB zipped per layer → **~10–15 GB zipped, ~30–45 GB on disk** for road + aviation + rail × 4 years | Block-group table ~242k rows × years × sources, **< 100 MB** Parquet |
| 2 | **ACS 5-year** (2014–18 for the 2016/2018 maps, 2018–22 for the 2020 map) | Census API (key in `.env`, †works) | Free key | B19013 income, B03002 race/ethnicity, B25003 tenure, B01001 age, population | †vintages 2009–2024 available (latest 2020–24); †≤ 2019 on 2010 BGs, ≥ 2020 on 2020 BGs; ~0.5 GB | < 100 MB |
| 3 | **2020 Decennial P1 block population** (weights inside block groups) | Census API (`2020/dec/pl`, †works) | Free key | ~8.1M blocks, population | ~1 GB | ~150 MB Parquet |
| 4 | **TIGER/Line**: block groups, blocks, tracts, CBSA delineations | census.gov TIGER | Open | Boundaries for 2010 and 2020 geographies | †2020 blocks 10.34 GB zipped nationally (only metro states needed); †2020 BGs 0.69 GB; †tracts 0.41 GB; †2018 BGs 0.67 GB; †CBSA 33 MB | GeoParquet ~1–2 GB |
| 5 | **NHGIS geographic crosswalks** (2010→2020 block groups) | nhgis.org (†login-gated, as expected) | Free account | Only if 2014–18 ACS is used; ACS 2016–20 is already on 2020 BGs | < 1 GB | small |
| 6 | **NYC 311**: `erm2-nwe9` (2020–present) + `76ig-c548` (2010–2019) | NYC Open Data (Socrata SODA API; app token in `.env`, †works) | Open | Noise complaints only, ~12 columns | **†5,259,406 noise rows (2020-01-01 → 2026-11-16) + †3,403,203 (2010–19) = 8.66M rows**; †0.5–0.7% missing coordinates; ~1.5–2 GB as CSV | ~200–300 MB Parquet |
| 7 | **NYC gentrification typology** | Urban Displacement Project (tract) and/or NYU Furman Center; or our own ACS-based typology | Published / open | Tract change class | < 10 MB | < 10 MB |
| 8 | **FAA Part 150 noise contours** | FAA / airport websites (JFK, LGA, EWR, ATL, LAX, ORD…) | Open, patchy | Validation polygons for a handful of airports | < 500 MB | small |
| 9 | **WHO exposure-response functions** | WHO 2018 Environmental Noise Guidelines + Guski et al. 2017 (annoyance) and Basner & McGuire 2018 (sleep) systematic reviews | Published | Coefficients coded by hand into `who_erf.py` | — | — |
| 10 | **EPA EJScreen (archived)** | Public Environmental Data Partners rebuild (v2.3), Yale mirror, Harvard EELP tracker, Wayback | Open mirrors | Optional: cross-check demographic and traffic-proximity indicators | ~2–3 GB | optional |

**Total local disk: about 20 GB** (measured in P03: 5.5 GB BTS zips + 9.9 GB COGs; nothing is unzipped; Census blocks add ~3–5 GB). Rasters are read **one state / metro window at a time** from COGs, so RAM stays under ~8 GB.

### Data caveats (fixed in the analysis design)
- **Rail is not comparable over time.** 2016 has no rail, 2018 has passenger rail only (prototype), 2020 has freight + passenger. Change-over-time results are **road + aviation only**; rail is reported for 2020 only.
- **Values below 45 dBA are not in the rasters** (left-censored). Treat nodata as "< 45 dBA". For energy sums and WHO functions, use a stated floor (default 45; sensitivity at 40 and 0-contribution).
- **Metric mismatch.** BTS uses LAeq,24h; WHO uses Lden / Lnight. Convert with documented offsets (road: Lden ≈ LAeq24 + ~3 dB; Lnight ≈ LAeq24 − ~7 dB), flag the numbers as estimates and run sensitivity checks.
- BTS says the map "should not be used to evaluate noise levels in individual locations", so the address lookup must say this clearly.
- BTS's mosaic **repair steps are not needed**: we read the per-state rasters directly (P03). Each block group is measured on its own state's raster, because 2022 and aviation state rasters do not share one grid.
- **311 complaint counts are dominated by a few locations** (one Bronx building filed 25% of 2025 residential complaints) and include app double-submits. Complaint models must not use raw counts alone; see the P05 question on location-days.
- **The rail layers do not include the NYC subway** (including elevated lines). Say so in the NYC section.
- Rail and aviation values reach ~125 dB on track lines and runways (model ceiling); see the P03 question on capping for energy means.
- **BTS changes which roads it models between releases** (Georgia's road cells fall by a third from 2016 to 2018; Minnesota's halve, then recover). Year-to-year differences are partly model-input changes, not real change (P08).
- The 2020 inputs reflect COVID-era traffic. Note this whenever 2018 and 2020 are compared.

### Data licences

| Source | Terms | What this means here |
|---|---|---|
| **IPUMS NHGIS** (crosswalks) | Agreed 2026-11-17. **(1) No redistribution without permission.** Publishing a subset needed for a particular publication's data-access requirements is allowed; anything else needs written permission from IPUMS. **(2) Cite NHGIS** as given on their citation-and-use page, and **add the publication to the NHGIS bibliography**. Breaking the terms can lead to loss of access and liability for damages. | NHGIS files stay in `data/raw/nhgis/` (git-ignored) and never go into commits, releases, the app or a public bucket. Published outputs are **our own aggregate results** (exposure shares, model estimates), never crosswalk weights or NHGIS extracts. Anyone reproducing the work downloads NHGIS files with their own account (`make ingest` explains how). The exact NHGIS citation goes in DATA.md, the report and the README. After publication, submit the article to the NHGIS bibliography (P19). |
| **Census API** (ACS, Decennial, TIGER) | U.S. government work, public domain | Can be redistributed; cite the Census Bureau. Not covered by the NHGIS terms, which is why ACS comes from the API rather than NHGIS. |
| **BTS Noise Map** | U.S. government work, public domain | Cite BTS. Keep BTS's caveat that the map should not be used to judge individual locations. |
| **NYC Open Data (311)** | NYC Open Data terms of use (free reuse, attribution) | Cite NYC Open Data; publish tract-level counts only, never complaint-level records. |
| **Gentrification typology** | Depends on source (P12) | Check its licence before use; cite it. |
| **WHO / journal ERFs** | Coefficients from published papers | Cite each paper. |

**Keep NHGIS usage small.** Noise is computed from the rasters directly on **2020 block groups for every release year**, so noise change over time needs no crosswalk. NHGIS crosswalks are needed only to bring **2014–18 ACS demographics** onto 2020 boundaries (P09). If that turns out not to be worth it, hold demographics at 2018–22 and drop NHGIS entirely.

---

## Repo layout (target)

```
noise-exposure-equity/
  CLAUDE.md, README.md, DATA.md, Makefile, pyproject.toml, uv.lock, .gitignore
  config/metros.yaml, thresholds.yaml
  data/raw/ interim/ processed/          # raw + interim git-ignored
  src/ne/
    ingest/bts_noise.py, acs.py, tiger.py, nyc311.py, faa.py
    build/combine_sources.py, zonal_stats.py, analysis_table.py, nyc_panel.py
    models/disparity.py, spatial_reg.py, complaints_nb.py, who_erf.py
    viz/theme.py, figures.py, maps.py
  tests/
  notebooks/   # exploration only, never the source of results
  report/index.qmd
  app/
```

---

## Prompts

### Phase 0: Setup and access check (Week 1) ✅ DONE

- [x] ✅ DONE! **P01: Scaffold the repo.** _Done 2026-11-17: uv env (Python 3.12, rasterio 1.5.2 / GDAL 3.12.2, exactextract 0.3.0, spreg 1.9.2), Makefile, config, 3 smoke tests pass, lint clean; public GitHub repo created._
  Create the layout above: `uv` project (Python 3.12), `pyproject.toml` with dependencies, `ruff` and `pytest` config, `.gitignore` (data/raw, data/interim, .env), `Makefile` with stub targets (`ingest`, `build`, `models`, `figures`, `report`, `test`, `all`), `.env.example` (CENSUS_API_KEY, SOCRATA_APP_TOKEN), `config/thresholds.yaml` (45/55/65/70 dBA) and an empty `config/metros.yaml`. Check that GDAL/rasterio and exactextract install on macOS.
  **Deliverables:** directory tree, `uv run pytest` passing (smoke test), `make help` output.
  **Questions:** git init and push to GitHub? Where should raw data live (internal disk vs external drive; ~100 GB needed)? Python 3.12 OK?

- [x] ✅ DONE! **P02: Data access check and DATA.md.** _Done 2026-11-17: DATA.md written; Census/TIGER/311/NHGIS/ERF sources pass; BTS adds a 2022 release, but its download page blocks scripts, so the zip URLs need copying from a browser._
  Probe every source in the inventory: confirm download URLs, **measure actual file sizes** (HTTP HEAD / listings), licences, and the latest ACS vintage. Check EJScreen mirror status. Get Census API key and Socrata token into `.env`. Write `DATA.md` with one section per source (URL, retrieval date, version, size, licence, citation, known issues). Update the inventory table in this file with measured sizes.
  **Deliverables:** `DATA.md`; corrected size table; a short "access check" report (✅ / ⚠️ per source).
  **Questions:** Use the 20 largest metros (spec) or all ~380 metro CBSAs (same code, ~5× compute)? Include EJScreen as a cross-check or skip it? Census API or NHGIS for ACS?

### Phase 1: Ingest (Week 1) ✅ DONE

- [x] ✅ DONE! **P03: Ingest BTS noise rasters.** _Done 2026-11-17: 11 CONUS layers (2016–2022) → 537 state COGs (9.9 GB) + display VRTs, read straight from zips; no mosaic repair needed; 35 tests pass._
  `ingest/bts_noise.py`: download 2016/2018/2020 CONUS road, aviation, rail and combined layers (resumable, checksummed), apply BTS mosaic repair steps, convert to Cloud-Optimised GeoTIFFs with overviews, record CRS / resolution / nodata / dtype. Tests on raster metadata.
  **Deliverables:** `data/raw/bts/` manifest (file, size, sha256), `gdalinfo` summary per layer, quick-look PNG of one metro per layer.
  **Questions:** Download all three years now, or 2020 first and older years later? Include AK/HI (spec is metro-focused, so default to CONUS only)?

- [x] ✅ DONE! **P04: Ingest Census (ACS, block population, TIGER, CBSA, crosswalks).** _Done 2026-11-17: 20 metros (126.1 M people, 22 states) → 85,392 BGs, 30,134 tracts, 1.59 M blocks with POP20 matching census totals exactly; ACS 2016–20 + 2018–22; no NHGIS; 48 tests pass._
  `ingest/acs.py`, `ingest/tiger.py`: ACS 5-yr block-group tables for two vintages; 2020 P1 block population; TIGER block groups, blocks (state by state), tracts; CBSA delineation file; NHGIS 2010→2020 BG crosswalk. Derive variables: median household income, % non-Hispanic White / Black / Hispanic / Asian, % renters, population. Fill `config/metros.yaml` with the chosen metros.
  **Deliverables:** GeoParquet files + row counts; table of the selected metros with population; null/margin-of-error summary.
  **Questions:** Income quintiles within metro (spec) or national? How to handle block groups with high ACS margins of error (drop / flag / keep)?

- [x] ✅ DONE! **P05: Ingest NYC 311 noise complaints.** _Done 2026-11-17: 8,646,306 noise complaints 2010-01→2026-11 (16 cols, partitioned Parquet); geocoding clean; found app double-submits and one Bronx building with 239k complaints; 57 tests pass._
  `ingest/nyc311.py`: page both Socrata datasets for `complaint_type LIKE 'Noise%'` (~8.7M rows), keep ~12 columns (id, created date, complaint type, descriptor, lat/lon, BBL, borough, incident zip, location type, status, channel), write Parquet partitioned by year. Geocoding QA: % missing coordinates, % outside NYC, duplicates.
  **Deliverables:** Parquet dataset, counts by year × type table, geocoding QA table, monthly time-series PNG.
  **Questions:** Study window (2010–present, or a stable post-2015 window since complaint categories changed)? Treat `Noise - Helicopter` as aviation, matching the aviation layer?

### Phase 2: Build the exposure dataset (Weeks 1–2) ✅ DONE

- [x] ✅ DONE! **P06: Decibel math and WHO exposure-response functions (TDD).** _Done 2026-11-17: energy sum/mean with censoring policies and cap; WHO 2018 %HA/%HSD curves pass WHO anchor values; LAeq24→Lden/Lnight offsets; 85 tests pass; note in docs/decibel_math_and_erfs.md._
  `build/combine_sources.py` (energy sum, energy mean, handling of censored < 45 dB cells) and `models/who_erf.py` (%HA road/rail/aircraft, %HSD, LAeq24→Lden/Lnight conversions). Write the tests first: 60 + 60 = 63.01 dB, nodata handling, known ERF values from the literature.
  **Deliverables:** modules + passing tests; a one-page note on the formulas and the sources for each coefficient.
  **Questions:** Which ERF set to treat as primary (WHO 2018 / Guski 2017 or the newer EU END guidance)? Floor for censored cells (default 45 dB)?

- [x] ✅ DONE! **P07: Zonal stats pilot on one metro.** _Done 2026-11-17: New York, 192k blocks → 14,982 BGs × 4 years × 5 sources in 9.4 min (peak 5.3 GB); validation tracts behave as expected; 98 tests pass._
  `build/zonal_stats.py`: for one metro, compute per block the area share ≥ each threshold and the median dB (plus a 100 dB-capped energy mean as a sensitivity), by source and year (see decision log, P03) (exactextract); aggregate to block groups weighted by 2020 block population. Validate: compare 5–10 tracts next to known interstates and the main airport against expectations (and FAA Part 150 contours if available). Time and memory profile.
  **Deliverables:** pilot BG table, validation table, map PNG of the pilot metro, runtime estimate for scaling up.
  **Questions:** Which pilot metro (default: New York, since it feeds the NYC analysis; or a smaller one like Atlanta for speed)? Is block-population weighting enough, or also mask to NLCD developed land?

- [x] ✅ DONE! **P08: Scale to all metros and years.** _Done 2026-11-17: 20 metros × 4 years → bg_noise.parquet (1.53M rows, 45 MB) in 48 min; matches UW's 2020 national ≥ 60 dB share (3.5% vs 3.6%); BTS road coverage changes between releases flagged; 101 tests pass._
  Run P07 for every metro and release year, parallel by metro window, with caching and resume. Compare national totals with BTS's own published exposure statistics (e.g. "share of population exposed ≥ 50/60 dBA").
  **Deliverables:** `data/processed/bg_noise.parquet`; reconciliation table against BTS figures; run log.
  **Questions:** Any metros with odd results to look into before modelling?

- [x] ✅ DONE! **P09: Analysis table.** _Done 2026-11-17: analysis_bg.parquet (1.53M rows, 49.6 MB) joins noise, ACS and metro; income quintiles within metro, population-weighted; data dictionary in DATA.md; 106 tests pass._
  `build/analysis_table.py`: join noise + demographics + metro IDs; income quintiles within metro. Noise for all years is already on 2020 block groups (P07/P08). Use the NHGIS 2010→2020 crosswalk only to bring 2014–18 ACS onto 2020 boundaries; crosswalked outputs stay local (NHGIS licence). Data dictionary with a "derived from" column.
  **Deliverables:** `data/processed/analysis_bg.parquet`, data dictionary in DATA.md, descriptive summary table.
  **Questions:** Race/ethnicity groups to report (default: NH White, NH Black, Hispanic, NH Asian, other)?

### Phase 3: Exposure disparities (Weeks 2–3) ✅ DONE

- [x] ✅ DONE! **P10: Disparity tables and hero chart v1.** _Done 2026-11-17: disparity tables by income quintile and race (per metro + pooled, every year/source); hero chart and Chart 3; lowest-income fifth more exposed than highest in all 20 metros (pooled ≥ 65 dBA: 1.8% vs 0.9%); 111 tests pass._
  `models/disparity.py`: population-weighted share ≥ 55 / 65 dBA by income quintile and race, per metro and pooled; source breakdown (road / rail / aviation). `viz/theme.py` + hero chart (small multiples, 20 metros, share ≥ 55 dBA by income quintile; 65 as the stricter test) + Chart 3 (disparity by source).
  **Deliverables:** disparity tables (CSV), hero chart v1, Chart 3, and a three-bullet "what we see".
  **Questions:** Headline threshold 65 dBA (spec) or 55? Visual style and palette preferences?

- [x] ✅ DONE! **P11: Regression and spatial models; change over time.** _Done 2026-11-17: Q1–Q5 gap +8.6 pp with metro FE, +5.3 with race, ≈ 0 once renting and density are added; strong spatial dependence (Moran's I 0.66; lag model favoured in all 20 metros); change-over-time box; notes in docs/results_p10_p11.md._
  `models/spatial_reg.py`: OLS with metro fixed effects, then spatial lag/error models (PySAL `spreg`, Queen weights within metro), Moran's I on residuals. Change over time (road + aviation) by group, as a **short descriptive box only** (decision P08: BTS model inputs change between releases).
  **Deliverables:** coefficient tables, LM diagnostics, change-over-time table and chart, short interpretation.
  **Questions:** Run spatial models per metro, pooled, or both? How much of the change-over-time analysis goes into the article?

### Phase 4: NYC complaints vs exposure (Week 4)

- [x] ✅ DONE! **P12: NYC tract × month panel.** _Done 2026-11-19: 2,327 tracts × 130 months × 8 groups (6.97M complaints, 5.0M location-days); own ACS gentrification typology (299 gentrifying tracts); gentrifying tracts file the most complaints per resident (64 location-days per 1,000 a year vs 45 in higher-income tracts); 119 tests pass._
  `build/nyc_panel.py`: complaints by tract × month × type (spatial join), tract modelled noise (from P08), ACS demographics, gentrification typology, population, borough.
  **Deliverables:** `data/processed/nyc_panel.parquet`, summary of complaints per 1,000 residents by typology, panel QA.
  **Questions:** Which gentrification typology (Urban Displacement Project, Furman Center, or our own ACS-change definition)? Tract or NTA level?

- [x] ✅ DONE! **P13: Negative binomial models and Chart 4.** _Done 2026-11-19: complaints barely track modelled noise (rate ratio 0.99 per 10 points); gentrifying tracts file 14% more complaints than other low-income tracts with the same noise and demographics (CI 6–23%; residential +13%, street +25%); Chart 4 made; 121 tests pass._
  `models/complaints_nb.py`: NB models of complaints on modelled noise × gentrification, demographics, log population offset, borough FE; separate models by complaint type; cluster-robust SEs. Chart 4: complaints per 1,000 residents vs modelled noise, coloured by typology.
  **Deliverables:** model tables, marginal-effects plot, Chart 4, plain-English statement of the key coefficient.
  **Questions:** Is the result strong enough to lead the NYC section, or should it be framed as exploratory?

### Phase 5: Health translation, robustness, maps (Week 5) ✅ DONE

- [x] ✅ DONE! **P14: WHO health translation and Chart 5.** _Done 2026-11-19: extra cases above WHO guideline levels, 20 metros: highly annoyed 2.9M (aircraft), 0.8M (road), 0.7M (rail); highly sleep-disturbed 0.6M (rail), 0.5M (aircraft), 0.2M (road); every source falls hardest on the lowest income fifth; Chart 5 made; 125 tests pass._
  Apply ERFs to BG exposure: estimated highly-annoyed and highly-sleep-disturbed residents by metro and source, with uncertainty ranges from ERF confidence intervals. Chart 5.
  **Deliverables:** estimates table, Chart 5, caveat text block.
  **Questions:** Show ranges or point estimates in the headline numbers?

- [x] ✅ DONE! **P15: Robustness suite.** _Done 2026-11-19: 72 checks; disparity ratios never flip (income 1.9–2.4×); NYC gentrification result holds except with raw counts; spec C income sign depends on spatial terms; aircraft health estimate is a lower bound (8.3M if residents below 45 dBA sit at 45); 131 tests pass._
  Alternative thresholds; area- vs population-weighting; censoring floor; excluding Manhattan; complaint types separately; ACS MOE filtering; with/without spatial terms. One summary "robustness grid" table.
  **Deliverables:** robustness grid, list of any results that change sign or significance.
  **Questions:** Any robustness checks to add or drop?

- [x] ✅ DONE! **P16: Bivariate choropleth (Chart 2).** _Done 2026-11-19: New York noise × income bivariate map, static PNG/SVG (polygons rasterized, 1.8 MB) and interactive Leaflet page (Esri light-grey basemap, hover details, 2.3 MB; plotly's MapLibre maps drew blank); 19% of residents shown live in loud, lower-income block groups; 134 tests pass._
  `viz/maps.py`: noise × income (or % minority) bivariate map for one metro, static PNG/SVG plus an interactive version.
  **Deliverables:** Chart 2 (static + interactive HTML).
  **Questions:** Which metro to feature? Income or race as the second variable?

### Phase 6: Article, app, publish (Week 6)

- [x] ✅ DONE! **P17: Report / article.** _Done 2026-11-19: Quarto article (about 1,400 words of main text, 2,200 with appendix) built from result tables; all 70 numbers are variables from `ne.report`, traced in `report/claims.csv`; self-contained HTML (5.5 MB); 136 tests pass._
  `report/index.qmd`: Quarto article built from processed data and figures; methods appendix; limitations ("what we won't claim"); data sources and citations section (NHGIS citation in its required form); reproducibility instructions (including getting your own NHGIS account). `make report`.
  **Deliverables:** rendered HTML report, word count, list of claims with the table/figure behind each one.
  **Questions:** Where will it be published (personal site, Medium, Substack, GitHub Pages)? Audience and tone?

- [x] ✅ DONE! **P18: Address lookup app.** _Done 2026-11-19: static page (Census Geocoder via JSONP → 2020 block group → per-state JSON, 5.6 MB) with neighbourhood share ≥ 55/65 dBA by source, within-metro percentile and caveats; tested end to end on desktop and mobile; `make site` assembles report + app + map for GitHub Pages; 140 tests pass._
  `app/`: enter an address → geocode (Census Geocoder, free) → modelled noise by source at that point plus the BG's percentile in its metro. Pre-computed BG lookup + sampled raster values or tiled COG reads; clear "modelled, not measured" disclaimer.
  **Deliverables:** working local app, screenshots, deployment plan.
  **Questions:** Framework and hosting (static site + pre-computed tiles vs Streamlit / FastAPI)? Metros covered only, or national?

- [ ] **P19: Final QA and publish.**
  Run `make all` from a clean clone; validate key numbers (spot checks, a pinned-share test); README with headline findings; DATA.md citations; **licence audit** (no NHGIS files or crosswalk weights in git history, releases or the app; every published table names its sources; NHGIS citation in README, report and DATA.md); tag a release; **submit the article to the NHGIS bibliography**; distribution checklist (spec §9).
  **Deliverables:** clean-build log, QA checklist, release tag, distribution drafts.
  **Questions:** Ready to publish? Who to contact first?

---

## Decision log
_Record answers to the questions above here as they are made (date: decision)._

- 2026-11-17: Use git and push to GitHub.
- 2026-11-17: Raw data lives on the internal disk under `data/raw/` (git-ignored).
- 2026-11-17: Scope is the **20 largest metros** (CBSAs by population), as in the spec.
- 2026-11-17: GitHub repo is **public**. Python 3.12. GDAL comes bundled with rasterio (no system GDAL needed); use `uv run rio info` instead of `gdalinfo`.
- 2026-11-17: Census API key is in `.env`. NHGIS account being set up (used for crosswalks only). ACS tables come from the Census API.
- 2026-11-17: **EJScreen skipped** (not used as a cross-check).
- 2026-11-17: NHGIS usage licence accepted (no redistribution; cite and add to bibliography). Plan: compute noise for every year on 2020 block groups so NHGIS is needed only for 2014–18 ACS; NHGIS files never leave `data/raw/nhgis/`.
- 2026-11-17 (P03): **Homebrew GDAL 3.13** installed (`brew install gdal`), used only for `gdal_translate` (2022 FileGDB rasters) and `gdalbuildvrt` (display mosaics). Everything else uses rasterio's bundled GDAL. Scope is CONUS only (no AK/HI).
- 2026-11-17 (P03): **Block-group noise metrics.** Area energy means are dominated by track/runway/lane cells where nobody lives (one 125 dB cell among 999 at 50 dB gives a 95 dB energy mean). So: (1) headline = **population share ≥ 55 / 65 dBA**; (2) typical level = **median dB per block, population-weighted to the block group** (not an energy mean over area); (3) energy sums only where physics needs them (combining sources at a cell, WHO ERFs in P14); (4) sensitivity: energy mean with values capped at 100 dB. Raw raster values are kept unchanged.
- 2026-11-17 (P04): Metros = 20 largest MSAs by 2020 Census population, **OMB March 2020 delineations** (match 2020 block geography). Block population comes from TIGER `POP20` (no separate API pull).
- 2026-11-17 (P04): **Income quintiles within each metro** (spec), built in P09. **ACS reliability: flag and keep** block groups with missing income or CV > 0.30 (`acs_cv_flag`); drop them as a P15 robustness check.
- 2026-11-17 (P06): **Metric offsets**: road and aviation Lden = LAeq24 + 3, Lnight = LAeq24 − 7; rail +5 / −2 (freight runs at night). Assumptions, tested in P15.
- 2026-11-17 (P06): **Health headline = extra cases above the WHO guideline level**; total cases above the curve's lower limit reported alongside (P14).
- 2026-11-17 (P09): Race/ethnicity groups: NH White, NH Black, Hispanic, NH Asian, other (other races + multiracial). `analysis_bg.parquet` stays local (49.6 MB, rebuilt by `make build`); result tables from P10 on are committed.
- 2026-11-19 (P13): **NYC section is exploratory.** Main point: gentrifying tracts complain 14% more than other low-income tracts with the same modelled noise and demographics; complaints barely follow modelled noise. Caveats: 311 measures reporting; BTS misses most complaint sources.
- 2026-11-19 (P14): **Health ranges stay assumption ranges** (band position, conversion offsets ±2 dB); the curves' published confidence intervals are not coded, and the text says so.
- 2026-11-19 (P17): Report is published on **GitHub Pages**; general-interest data-journalism tone, methods in an appendix.
- 2026-11-19 (P18): App = **static site on GitHub Pages**: Census Geocoder → 2020 block group → precomputed block-group lookup (20 metros only), with the "modelled, not measured" warning. No server.
- 2026-11-19 (P15): Aircraft health headline is worded **"at least 2.9 million"** (the WHO aircraft guideline sits below the map's 45 dBA floor; methods explain why).
- 2026-11-19 (P16): Bivariate map features **New York** with **income**. Interactive version is a hand-written **Leaflet** page (template in `src/ne/viz/templates/`), not plotly: plotly 7.1's MapLibre maps rendered a blank canvas in Chrome. Basemap: Esri World Light Gray (no key; CARTO now needs an API key). Adding `folium` was blocked, so no new dependency.
- 2026-11-19 (P15): Robustness set = spec list + alternative gentrification definition (income growth instead of rent), ±2 dB on the rail night offset, 2020 map instead of 2022.
- 2026-11-19 (P14): Health headline = **point estimates with ranges beside them**, counting extra cases above the WHO guideline levels.
- 2026-11-19 (P12): **Helicopter complaints are left out of the complaint models** (BTS aviation models airports, not helicopter routes; tract ρ = −0.18); reported descriptively. Models cover residential, street, vehicle and commercial complaints.
- 2026-11-19 (P12): **Gentrification typology = our own**, ACS 2016–20 → 2020–24 on 2020 tracts (income ≤ city median; BA+ gain and rent growth above the city median). Tract level, not NTA. Panel window 2016-01 → 2026-10. `nyc_panel.parquet` and `nyc_tracts.parquet` are committed (tract-level counts only).
- 2026-11-17 (P11): **Framing**: lead with the descriptive income and race gaps (P10); present renting and density as part of how the gap arises, not as something that cancels it.
- 2026-11-17 (P11): Spatial models: pooled with metro fixed effects (within-metro demeaning, since lagged metro dummies equal the dummies) as the main result, plus one model per metro. GM estimators (2SLS lag, heteroskedasticity-robust error); Queen contiguity within metros; islands dropped.
- 2026-11-17 (P10): **Headline threshold 55 dBA**; 65 dBA is shown as the stricter test (changed from the spec after seeing the results: 65 dBA shares are 0.3–3%). Palette = `theme.py` blue ramp for quintiles, reference categorical slots 1–5 for race (validator: all checks pass; contrast relief via direct axis labels).
- 2026-11-17 (P09): Map years pair with ACS vintages: 2016/2018 → ACS 2016–20; 2020/2022 → ACS 2018–22. Income quintiles are weighted by ACS population within each metro.
- 2026-11-17 (P08): **2022 cross-section is the headline.** Change over time is cut to a short descriptive box with a caveat on BTS model-input changes (no consistent-footprint analysis).
- 2026-11-17 (P08): `bg_noise.parquet`, `metro_exposure.csv` and `bts_reconciliation.csv` are **committed to GitHub** (BTS + Census only, public domain; sources listed in `data/processed/README.md`). Anything built with ACS or 311 is checked case by case.
- 2026-11-17 (P08): Exposure thresholds extended to **45/50/55/60/65/70 dBA** (50 and 60 for the BTS and UW benchmarks).
- 2026-11-17 (P07): **Road results are "major-road noise"** everywhere they are reported: the BTS road model covers highways and arterials, not local streets (only 27% of New York metro residents are in blocks with any road noise ≥ 45 dBA).
- 2026-11-17 (P07): Pilot metro = **New York**; block-population weighting, no NLCD mask. Sources are combined per cell on each state's road grid (nearest neighbour), and a censored source adds nothing (`policy="zero"`). Sources: road, aviation, rail, `road_aviation` (comparable over time), `all` (years with rail).
- 2026-11-17 (P06): **Primary ERFs = WHO 2018** (Guski 2017 %HA, Basner & McGuire 2018 %HSD, as in Directive (EU) 2020/367). Censored-cell floor 45 dB; sensitivity 40 dB and zero contribution.
- 2026-11-17 (P05): **Complaint outcome = location-days** (a location counted at most once per day per complaint group; same-minute app repeats collapse automatically). Raw counts are a robustness check, plus a sensitivity run without the top locations (cut-off set in P12).
- 2026-11-17 (P05): 311 kept from 2010; **analysis window 2016 onward**. `Noise - Helicopter` = aviation, reported separately. `Noise Survey` dropped.
- 2026-11-17 (P02): **2022 BTS map (released May 2026) is the main "current" year**, paired with ACS 2018–22. 2020 stays as a robustness check (COVID-era traffic). Change over time: 2016 → 2018 → 2022 (road + aviation).
- 2026-11-17 (P02): **NHGIS dropped.** Earlier demographics come from ACS 2016–20, which is already on 2020 block groups, so no crosswalk is needed. Keep the NHGIS licence notes in case this is revisited.
