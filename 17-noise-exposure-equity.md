# Project 17: Who Lives With the Noise?

**Backlog ID:** AU-6 · **Difficulty:** Medium (geospatial) · **Data access:** Open · **Estimated time:** 6 weeks

**Working title:** *Loud and Unequal: Transportation Noise, Complaints and Who Gets Heard*

**One-sentence pitch:** Combine the federal National Transportation Noise Map with census demographics to measure who is exposed to road, rail and aviation noise across the US, then use NYC's 311 data to test a second inequality: whether complaints track actual noise or track who feels entitled to complain.

---

## 0. Day-one access check
- [ ] Download the BTS National Transportation Noise Map rasters (road, rail, aviation; check which years are available, e.g. 2016, 2018, 2020) from bts.gov.
- [ ] Pull ACS 5-year block-group tables (income, race/ethnicity, tenure) from the Census API (free key, instant) or IPUMS NHGIS.
- [ ] Query NYC Open Data's 311 dataset for noise complaints (Socrata API; an app token is optional and free).
- [ ] Check where EPA EJScreen data can be found now (it was taken offline by EPA in 2025; archived copies exist, e.g. from academic and nonprofit mirrors). **Check the current status.**

## 1. The question

**Primary:** How does exposure to transportation noise above health-relevant thresholds (e.g. ≥ 55 or ≥ 65 dBA LAeq 24h) vary by neighbourhood income and race/ethnicity across US metro areas?

**Secondary:**
- **Which sources?** Is the disparity driven by highways, airports or rail?
- **Change over time:** between noise-map releases, did exposure change, and for whom?
- **Complaints vs exposure (NYC):** controlling for modelled noise exposure, which neighbourhoods complain more about noise? Hypothesis: gentrifying areas file more complaints relative to actual noise.
- **Health relevance:** translate exposure into estimated highly-annoyed and sleep-disturbed populations using WHO exposure-response functions (clearly labelled as estimates).

**A finding that would be wrong if:** noise exposure doesn't differ meaningfully by income or race within metros, or complaints track measured noise equally across neighbourhoods.

## 2. Why now
- WHO's *Environmental Noise Guidelines for the European Region* (2018) set health-based limits (e.g. 53 dB Lden for road traffic). The US has no comparable national standard and rarely publishes exposure statistics.
- Environmental justice data tools have been changing or disappearing at the federal level, so independent analyses matter more.
- Prior work: Casey et al. (*Environmental Health Perspectives*, 2017) found higher noise exposure in lower-income and minority neighbourhoods using modelled noise; Legewie & Schaeffer (*AJS*, 2016) linked 311 complaints to contested neighbourhood boundaries. Your contribution: **source-by-source exposure from the federal map, change over time, and the complaints-vs-exposure test.**

## 3. Data sources

| Source | What it gives you | Grain | Where |
|---|---|---|---|
| **BTS National Transportation Noise Map** | Modelled LAeq 24h noise from road, rail and aviation | 30 m raster, several releases | bts.gov (open) |
| **ACS 5-year** | Income, race/ethnicity, renters, age | block group / tract | Census API (free key) / NHGIS |
| **Census TIGER/Line** | Boundaries | geography | census.gov |
| **NYC 311** | Noise complaints with type (loud music, construction, vehicle, helicopter…), location, timestamp | complaint, 2010–present | NYC Open Data |
| **NYC gentrification typologies** | Neighbourhood change classifications (e.g. NYU Furman Center or academic typologies) | tract | Published sources (cite) |
| **FAA airport noise contours (Part 150)** | Official airport noise maps | airport | FAA / airport sites (where available) |
| **WHO exposure-response functions** | % highly annoyed, % sleep disturbed vs dB | function | WHO 2018 guidelines and systematic reviews |

## 4. Building the dataset

1. **Zonal statistics:** for each block group, the population-weighted share of area above thresholds, by source and release year (use `rasterstats` or `exactextract`; weight by residential land where possible).
2. **Combine sources** on the energy scale (10·log10 of the sum of 10^(L/10)), not by adding decibels arithmetically.
3. **Demographics** joined by GEOID; metro identifiers.
4. **NYC panel:** tract × month noise complaints by type; tract modelled noise; demographics and change typologies.
5. **Checks:** compare with BTS's own summary statistics; validate a handful of tracts near known highways and airports; geocoding accuracy of 311 points.

## 5. Method

### Exposure disparities
- Population-weighted exposure by income quintile and race/ethnicity, within metros (metro fixed effects so you compare neighbourhoods in the same region).
- Spatial regression (spatial lag/error models via PySAL) of exposure on demographics.

### Complaints vs exposure
- Negative binomial models of tract complaints on modelled noise, demographics, change typology and population, with borough fixed effects. Key coefficient: complaints per unit of noise in gentrifying vs non-gentrifying tracts.

### Robustness
- Different thresholds; area- vs population-weighting; excluding Manhattan (very high baseline); separate complaint types (e.g. "loud party" vs "construction").

### What you won't claim
That modelled noise equals measured noise. The BTS map is a model and omits some sources (construction, nightlife, industrial). Say so plainly.

## 6. Charts

| # | Chart | Purpose |
|---|---|---|
| **Hero** | **Share of residents exposed above 65 dBA by neighbourhood income quintile**, small multiples for the 20 largest metros | The headline |
| 2 | Map: noise exposure with demographic overlay for one metro (bivariate choropleth) | Visual |
| 3 | Bar: disparity by source (road / rail / aviation) | What drives it |
| 4 | NYC scatter: complaints per 1,000 residents vs modelled noise, coloured by neighbourhood change | The second inequality |
| 5 | Estimated highly-annoyed population by metro | Health framing |

**Interactive:** enter an address and see modelled noise by source and how the neighbourhood compares with its metro.

## 7. Repo skeleton

```
noise-equity/
  README.md, DATA.md, Makefile, pyproject.toml, uv.lock
  src/ne/
    ingest/bts_noise.py, acs.py, tiger.py, nyc311.py, faa.py
    build/zonal_stats.py, combine_sources.py, nyc_panel.py
    models/disparity.py, spatial_reg.py, complaints_nb.py, who_erf.py
    viz/theme.py, figures.py, maps.py
  tests/          # decibel combination, zonal stats on fixture raster, pinned shares
  report/index.qmd
  app/
```

## 8. Milestones

| Week | Deliverable |
|---|---|
| 1 | Download rasters and ACS; zonal stats on one metro |
| 2 | All metros; source combination; disparity tables |
| 3 | Spatial regression; hero chart v1 |
| 4 | NYC complaints analysis |
| 5 | WHO health translation; robustness |
| 6 | Article + address lookup; publish |

## 9. Distribution
- Urbanist and environmental-justice communities, r/urbanplanning, r/nyc, city reporters (noise is a perennial local story), acoustics societies (ASA).
- City council members working on noise ordinances.

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Modelled noise omits sources | State limits; validate where measured data exist |
| Ecological fallacy | Neighbourhood-level conclusions only |
| 311 reporting bias is the point, but also noise | Model it explicitly; separate complaint types |
| Large rasters | Process by metro tile; cloud-optimised GeoTIFFs |

## 11. Stretch goals
- Measure real noise with a few calibrated sensors (or the NYU SONYC dataset) to validate the model.
- Link exposure to housing prices (hedonic analysis).
- National address lookup as a public tool.
