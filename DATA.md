# Data

One section per source: URL, retrieval date, version, size, licence, citation and known issues. Filled in during P02 (access check, 2026-11-17) and updated by every ingest prompt. Sizes marked † were measured on 2026-11-17 (HTTP HEAD, directory listings or API counts). Sizes marked ~ are estimates.

| Source | Licence | Access check (2026-11-17) |
|---|---|---|
| BTS National Transportation Noise Map | Public domain (U.S. government), CC0 | ⚠️ Download page blocks scripts; zip URLs must be copied from a browser |
| ACS 5-year (Census API) | Public domain | ✅ |
| 2020 Decennial block population (TIGER `POP20`) | Public domain | ✅ |
| TIGER/Line + CBSA delineations | Public domain | ✅ |
| IPUMS NHGIS crosswalks | **IPUMS NHGIS terms: no redistribution; citation required** | ✅ (login required, as expected); possibly not needed (see §5) |
| NYC 311 noise complaints | NYC Open Data terms of use | ✅ |
| NYC gentrification typology | TBD | Deferred to P12 |
| FAA Part 150 noise contours | Public | ⚠️ Mostly PDF maps, few GIS files |
| WHO / journal exposure-response functions | Published papers; cite | ✅ |
| EPA EJScreen | — | Skipped (decision 2026-11-17) |

---

## 1. BTS National Transportation Noise Map

- **Landing / download page:** <https://www.bts.gov/geospatial/national-transportation-noise-map>
- **Documentation:** BTS, *National Transportation Noise Map Documentation, Version 3* (2026), <https://doi.org/10.21949/sysz-2y22> (ROSA P dot:90910).
- **Per-year metadata:** `https://transtats.bts.gov/NTADmetadata/USDOT_BTS_NTAD_Noise_{2016,2018,2020,2022}.xml`
- **Dataset DOIs:** 2020: <https://doi.org/10.21949/1522201>; 2022: <https://doi.org/10.21949/wyfb-0888>. Archive of 2020: DataLumos, <https://doi.org/10.3886/E240641V1>.
- **Display-only web services** (rendered tiles, not values; not usable for analysis): `https://tiles.arcgis.com/tiles/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Noise_{year}_{CONUS|Alaska|Hawaii}_{layer}/MapServer`.
- **Retrieved:** metadata and documentation 2026-11-17; rasters not yet downloaded (P03).

**Releases and layers (from Documentation v3, Table 1-1):**

| Release | Data year | Layers | Notes |
|---|---|---|---|
| Alpha (2017) | 2014 | Aviation, road | Deprecated prototype; not comparable |
| 1 (2020) | 2016 | Aviation, road, aviation+road | |
| 1 (2020) | 2018 | Aviation, road, passenger rail (prototype), combinations | |
| 2 (2022) | 2020 | Aviation, road, freight+passenger rail (prototype), combinations | COVID-era traffic |
| **3 (May 2026)** | **2022/2023** | Aviation (2022), road (2023 HPMS/ARNOLD), freight+passenger rail (2022), combinations | **New since the spec was written** |

**Format:** 30 m grid of receptors at 1.5 m height, LAeq,24h in dB(A). Results **below 45 dB(A) are not included** (left-censored). As of v3, **all years are now distributed as Esri File Geodatabase rasters** (earlier releases were TIF). GDAL's OpenFileGDB driver reads FileGDB rasters (GDAL ≥ 3.7; our env has GDAL 3.12.2), so P03 converts them to COGs.

**Modelling assumptions that matter for us:** no shielding by barriers, buildings or terrain (over-predicts behind barriers and in dense cities); all ground treated as soft (under-predicts over water and pavement); only transportation sources. 2016 aviation excludes airports without PDARS radar tracks (Doc. Table 10-1). Road 2022 release uses 2023 HPMS because of HPMS v9 data-quality problems.

**What the zips contain (P03, 2026-11-17):**

- **2016, 2018, 2020:** `State_rasters/{ST}_{mode}_noise_{year}.tif` (LZW GeoTIFF, one per state; 48 + DC, 47 for 2018 rail) plus an ArcGIS mosaic dataset in a `.gdb`. We read the state GeoTIFFs directly, so **BTS's mosaic repair steps are not needed**.
- **2022:** one File Geodatabase per layer holding a raster per state (`{ST}_{mode}_noise`). Read with GDAL's OpenFileGDB raster driver, which rasterio's bundled GDAL lacks; we use Homebrew GDAL 3.13.3 `gdal_translate` for this one step.
- All layers: ESRI:102039 (USA Contiguous Albers Equal Area Conic, USGS, NAD83), 30 m, float32, values 45–125 dB. Nodata is −3.4e38 in 2016–2020 and +3.4e38 in 2022; our COGs use −9999.
- Neighbouring state rasters never both hold a value in one cell. **Grids:** 2016–2020 road and 2018/2020 rail are snapped to multiples of 30 m; aviation (all years) and every 2022 layer have a different grid origin per state (0–30 m offsets, identical across modes in 2022). Analysis therefore reads each block group's own state raster; CONUS VRTs are for maps only.
- **Upper tail:** rail and aviation reach ~125 dB (apparent model ceiling) on track lines and runways. Cells ≥ 100 dB: 0.017% of 2020 rail cells, 0.002% of 2020 aviation cells; road never exceeds ~97 dB.
- **No subway.** The rail layers follow commuter and freight lines; NYC subway (including elevated lines) is not modelled.
- 2018 road has ~9% fewer valid cells than 2016 or 2020 (110.9 M vs 124.2 M / 121.3 M); to be checked in P08.

**Measured zip sizes (†, `data/raw/bts/manifest.csv` has sha256):** road 0.88 / 0.79 / 0.90 / 1.11 GB (2016/18/20/22); aviation 0.25 / 0.28 / 0.25 / 0.23 GB; rail – / 0.07 / 0.63 / 0.55 GB. **Total 5.47 GB zipped.** Uncompressed 46 GB (2022 road alone 26.8 GB, mostly empty FileGDB space), but nothing is unzipped: COGs are written straight from the zips. **COGs: 9.9 GB** in `data/interim/bts/cog/`.

**Original estimate:** †Search-indexed DataLumos listing gives `CONUS_road_noise_2020.zip` ≈ 855 MB and `CONUS_rail_noise_2020.zip` ≈ 605 MB (not re-measured; DataLumos also blocks scripted access). ~Estimate: 0.3–1 GB zipped per CONUS layer per year → ~10–15 GB zipped for road + aviation + rail across 4 years, ~30–45 GB on disk after unzip + COG. Much less than the 30–60 GB first planned.

**Access problem:** bts.gov and DataLumos return HTTP 403 to non-browser clients. Zip URLs were taken from a browser-saved copy of the page (2026-11-17) and recorded in `config/bts_sources.yaml`, in the pattern `https://www.bts.gov/bts-net-storage/CONUS_{mode}_noise_{year}.zip`. †The zip files themselves also return 403 to scripts, so they are **downloaded manually in a browser** into `data/raw/bts/zips/`; `ingest/bts_noise.py` (P03) verifies, checksums and converts them from there.

**Mosaic repair:** BTS publishes repair steps for the 2016/2018 CONUS mosaics (broken paths to state rasters, ArcGIS-only tooling): <https://www.bts.gov/explore-topics-and-geography/geography/national-transportation-noise-map-repairing-continental-us>. Not needed here: P03 reads the state rasters directly.

**National exposure figures for reconciliation (P08):** BTS, 18 Nov 2020, 2018 data, aviation + road, LAeq,24h: 23.1% of the population (74.7 M) at ≥ 45 dBA; 10.2% at 45–49, 6.5% at 50–54, 3.5% at 55–59, 2.3% at 60–69, 0.5% at 70–79, 0.1% at ≥ 80. Source: <https://content.govdelivery.com/accounts/USDOT/bulletins/2ad18fa>.

**Alternative / validation source:** Seto & Huang (2023), National Transportation Noise Exposure Map, tract-level population in LAeq bins (≥45–50 … ≥90), built from the BTS 2020 map with ACS 2016–20. <https://deohs.washington.edu/national-transportation-noise-exposure-map-download>. †`conus_shp.zip` 63.0 MB, †`conus_rda.zip` 62.1 MB. Useful as an independent cross-check of our tract aggregates.

**Licence:** U.S. government work, CC0. **Citation:** U.S. Department of Transportation, Bureau of Transportation Statistics, *National Transportation Noise Map* (NTAD), {year} data, accessed {date}. **Required caveat:** the map "should not be used to evaluate noise levels in individual locations and/or at specific times" and "should not be used for regulatory purposes".

---

## 2. ACS 5-year estimates (Census API)

- **API:** `https://api.census.gov/data/{vintage}/acs/acs5` (key in `.env`).
- **Available vintages (†checked):** 2009–2024. **Latest is 2020–2024.**
- **Geography (†checked on Manhattan block groups):** vintages ≤ 2019 use **2010** block groups (1,170 in New York County); vintages **≥ 2020 use 2020 block groups** (1,292). So the 2016–2020 ACS is already on 2020 boundaries.
- **Test call:** B19013, B03002, B25003, B01003 at block-group level returned HTTP 200 for 2018, 2022 and 2024. Suppressed values come back as `-666666666` (must be set to null).
- **Tables:** B19013 (median household income), B03002 (Hispanic origin by race), B25003 (tenure), B01001 (sex by age), B01003 (total population), plus MOE columns (`…M`).
- **Ingested (P04, `ne.ingest.acs`):** vintages **2016–2020** and **2018–2022**, all block groups in the 20 metros' counties: `data/processed/acs_bg.parquet` (170,784 rows = 85,392 BGs × 2, 14.5 MB; matches TIGER exactly). Raw responses cached in `data/raw/census/acs/`.
- **Quality (†):**

| | 2016–2020 | 2018–2022 |
|---|---|---|
| Block groups | 85,392 | 85,392 |
| Zero population | 1,268 | 1,225 |
| Population | 123.9 M | 125.6 M |
| Income missing (BGs / share of population) | 6,271 / 4.4% | 6,820 / 4.8% |
| Income CV > 0.30 (BGs / share of population) | 18,771 / 19.7% | 19,756 / 20.9% |
| Median income CV | 0.196 | 0.203 |
| Income top-coded at $250,001 | 943 | 1,885 |

  Flagged, not dropped (`income_missing`, `income_cv_high`); P15 drops them as a robustness check. Income is in each vintage's own dollars (2020 vs 2022); adjust before comparing levels across vintages.
- **Size:** ~0.5 GB as JSON for all states × two vintages; < 100 MB as Parquet.
- **Licence:** public domain. **Citation:** U.S. Census Bureau, American Community Survey 5-Year Estimates, {period}, via the Census Data API.

## 3. 2020 Decennial Census block population

- **Source used (P04):** the `POP20` field of the TIGER/Line 2020 block shapefiles (§4), which is the 2020 Census P.L. 94-171 count, so no separate API pull is needed. The API (`2020/dec/pl`, `P1_001N`) is used only to rank metros.
- **Check (†):** block `POP20` summed by metro equals the 2020 Census population of every one of the 20 metros exactly (test `test_block_population_matches_metro_totals`).
- **Ingested:** 1,593,667 blocks in the 20 metros, `data/interim/census/blocks_2020/{state}.parquet` (964 MB).
- **Licence / citation:** public domain; U.S. Census Bureau, 2020 Census Redistricting Data (P.L. 94-171).

## 4. TIGER/Line boundaries and CBSA delineations

All under <https://www2.census.gov/geo/tiger/>, one zip per state (56 files). †Measured totals:

| Layer | Zipped |
|---|---|
| `TIGER2020/BG/` block groups 2020 | 0.69 GB |
| `TIGER2020/TRACT/` tracts 2020 | 0.41 GB |
| `TIGER2020/TABBLOCK20/` blocks 2020 | **10.34 GB** (download only the states in our metros) |
| `TIGER2018/BG/` block groups 2010-vintage | 0.67 GB (only needed if NHGIS route is used) |
| `TIGER2020/CBSA/tl_2020_us_cbsa.zip` | 33.1 MB |

**Ingested (P04, `ne.ingest.tiger`):** metro counties only, GeoParquet in `data/interim/census/`: `bg_2020.parquet` 85,392 block groups (167 MB), `tract_2020.parquet` 30,134 tracts (98 MB), `blocks_2020/` 1,593,667 blocks in 22 states (964 MB; 5.19 GB of zips downloaded), `cbsa_2020.parquet` (3 MB).

**Metro definitions:** we use the **March 2020** delineations (`list1_2020.xls`), not 2023, because they match 2020 block geography (2023 replaces Connecticut counties with planning regions). None of the 20 metros is in Connecticut.

CBSA delineation file (county → CBSA): `…/metro-micro/geographies/reference-files/2023/delineation-files/list1_2023.xlsx` (†0.14 MB, July 2023 delineations). The 2020 version (`list1_2020.xls`) is also available. **Licence:** public domain. **Citation:** U.S. Census Bureau, TIGER/Line Shapefiles, 2020.

## 5. IPUMS NHGIS geographic crosswalks

- **Page:** <https://www.nhgis.org/geographic-crosswalks>
- **Files:** `https://secure-assets.ipums.org/nhgis/crosswalks/nhgis_bg2010_bg2020.zip` and `nhgis_blk2010_bg2020.zip` (national; state files also exist). †Both redirect to the IPUMS login, as expected, so size is not measurable without signing in.
- **Method:** weights are the expected share of a source zone's population and housing units in each target zone, from target-density weighting on blocks (Schroeder 2007).
- **Licence:** IPUMS NHGIS terms, accepted 2026-11-17:
  - **No redistribution.** NHGIS files are not included in this repository, its releases or its app. To reproduce, create a free account at <https://www.nhgis.org> and download the crosswalks yourself.
  - **Bibliography.** After publication, submit the article at <http://bibliography.ipums.org/>.
  - Published outputs are our own aggregate statistics, not NHGIS data.
- **Citation (Version 21.0, retrieved 2026-11-17 from <https://www.nhgis.org/citation-and-use-nhgis-data>):**

  > Jonathan Schroeder, David Van Riper, Steven Manson, Grace Cooper, Zachary Krause, Tracy Kugler, Tsu Zhu, and Steven Ruggles. IPUMS National Historical Geographic Information System: Version 21.0 [dataset]. Minneapolis, MN: IPUMS. 2026. http://doi.org/10.18128/D050.V21.0

- **May not be needed:** because ACS 2016–2020 is already on 2020 block groups (§2), it can stand in for 2014–18 as the "earlier" demographic snapshot with no crosswalk. Decision pending (P02 question).

## 6. NYC 311 noise complaints

- **Datasets:** `erm2-nwe9` "311 Service Requests from 2020 to Present" (rows updated †2026-11-16) and `76ig-c548` "311 Service Requests from 2010 to 2019" (†2025-12-24). SODA API `https://data.cityofnewyork.us/resource/{id}.json`; app token in `.env` (†works).
- **Filter:** `complaint_type like 'Noise%'`. †Counts:

| Dataset | Noise rows | Missing latitude | Date range |
|---|---|---|---|
| erm2-nwe9 | 5,259,406 | 24,179 (0.46%) | 2020-01-01 → 2026-11-16 |
| 76ig-c548 | 3,403,203 | 24,776 (0.73%) | 2010-01-01 → 2019-12-31 |
| **Total** | **8,662,609** | | |

- **By type (2010–19 / 2020+):** Residential 1.81 M / 2.62 M; Street/Sidewalk 0.47 M / 1.19 M; Commercial 0.35 M / 0.41 M; Vehicle 0.22 M / 0.42 M; generic "Noise" (DEP: construction, alarms, etc.) 0.48 M / 0.36 M; Park 35 k / 60 k; **Helicopter 12 k / 179 k**; House of Worship 10 k / 12 k; `Noise Survey` 16 k (2010–19 only; **exclude**, not a complaint).
- **By year (†):** 202 k (2010) rising to 479 k (2019); 802 k (2020), 768 k, 740 k, 686 k, 753 k, 833 k (2025), 676 k (2026 to date).
- **Known issues:** strong upward trend in 2010–2016 reflects 311 adoption and app/online channels, not more noise; Helicopter complaints jump ~15× after 2019 (new online form and advocacy campaigns); 2020 spike in Residential/Street complaints during COVID.
- **Size:** ~1.5–2 GB as CSV; ~200–300 MB Parquet with ~12 columns.
- **Ingested (P05, `ne.ingest.nyc311`):** 203 months (2010-01 → 2026-11), 16 columns (no street address text), `Noise Survey` removed: **8,646,306 complaints** (= 8,662,609 − 16,303), no duplicate `unique_key`. Raw monthly cache `data/raw/nyc311/` (370 MB); typed dataset `data/interim/nyc311/noise/year=YYYY/` (341 MB, `noise_group` column). Months less than two months old are re-fetched on each run.
- **Geocoding QA (†):** 0.3–1.6% missing coordinates per year; 0% outside the NYC box.
- **Repeat reports (†):** complaints sharing type, descriptor, point and minute with another: < 0.5%/yr before 2020, **2–6%/yr in 2020–2025**, almost all from the **mobile app** (8.2% of app complaints vs 0.1–0.5% phone/web), i.e. likely double submissions.
- **Super-complainer locations (†):** one Bronx building (BBL 2048330028, ZIP 10466) logged **239,276** residential complaints, 115,364 of them in 2025 (25% of all residential noise complaints citywide that year), almost all via the app; its neighbour (BBL 2048330080) logged 118,403. The 10 busiest locations make up 10–18% of all noise complaints in 2020, 2022, 2024 and 2025. Counting each location at most once per day per group ("location-days") gives a much steadier series: ~480–550 k per year since 2020 vs 670–830 k raw.
- **Helicopter:** ~1 k/yr in 2016–2018, 3.3 k in 2019, 10–26 k in 2020–2022, **59 k in 2023**, then 20–29 k.
- **Licence:** NYC Open Data Terms of Use (free reuse with attribution). Publish tract-level counts only. **Citation:** City of New York, NYC Open Data, *311 Service Requests* (erm2-nwe9, 76ig-c548), accessed {date}.

## 7. NYC gentrification typology

Deferred to P12. Candidates: Urban Displacement Project (tract typology), NYU Furman Center, or our own ACS-change typology. Licence to be checked then.

## 8. FAA Part 150 noise contours

- **FAA listing:** <https://www.faa.gov/airports/environmental/airport_noise/noise_exposure_maps> (†HTTP 200).
- **Finding:** Noise Exposure Maps are mostly published as PDF figures; GIS files are not generally posted (ATL's NEM is a PDF with a 2018 FAA determination; JFK/LGA have no recent Part 150 NEM). Some airports (e.g. LAX via LAWA, Centennial) post contour documents.
- **Plan:** use as a qualitative validation for 1–3 airports in P07 (overlay a georeferenced 65 DNL contour), or skip. Not on the critical path.
- **Licence:** public documents. Cite the airport sponsor's NEM report.

## 9. Exposure-response functions

- WHO Regional Office for Europe (2018), *Environmental Noise Guidelines for the European Region*, <https://www.who.int/europe/publications/i/item/9789289053563> (†HTTP 200).
- Guski, Schreckenberg & Schuemer (2017), "WHO Environmental Noise Guidelines for the European Region: A Systematic Review on Environmental Noise and Annoyance", *IJERPH* 14(12):1539, <https://doi.org/10.3390/ijerph14121539>.
- Basner & McGuire (2018), "WHO Environmental Noise Guidelines for the European Region: A Systematic Review on Environmental Noise and Effects on Sleep", *IJERPH* 15(3):519, <https://doi.org/10.3390/ijerph15030519>.
- (MDPI returns 403 to scripts; DOIs resolve in a browser.) Coefficients coded by hand in P06.

## 10. EPA EJScreen

Skipped (decision 2026-11-17).
