# Results notes: NYC complaints vs modelled noise (P13)

Draft wording for the report. Unit: 2,134 NYC census tracts × year, 2016–2025 (21,340 tract-years; tracts with ≥ 500 residents and a typology class). Outcome: 311 location-days for residential, street/sidewalk, vehicle and commercial complaints. Offset: 2020 population. Negative binomial (NB2); year and borough fixed effects; standard errors clustered by tract. Tables: `data/processed/complaints_nb_models.csv`, `complaints_nb_margins.csv`. Chart 4: `figures/chart4_nyc_complaints.png`.

## Key results

- **Complaints barely follow modelled transportation noise.**
  - Rate ratio per 10 more percentage points of residents at ≥ 55 dBA:
    - all four types, with controls (M2): **0.99** (95% CI 0.98–1.00);
    - without controls (M1): 1.01;
    - street complaints: 1.03 (M1) and 1.01 (M2).
  - The result holds with raw counts (1.02, CI 0.98–1.06) and without the top 1% of tracts (0.99).
- **Gentrifying tracts complain more.** They file **14% more** complaints than other low-income tracts with the same modelled noise, race/ethnicity, renter share and income (rate ratio 1.14, CI 1.06–1.23).
  - Residential complaints: +13% (1.06–1.21).
  - Street complaints: +25% (1.12–1.39).
  - Vehicle and commercial: no clear difference (+10%, CIs include 0).
- **Interaction (M3).** Modelled noise has a slightly stronger link to complaints in low-income, not-gentrifying tracts than in higher-income ones: rate-ratio multiplier 1.04 per 10 points (1.02–1.06). In practical terms, the predicted lines in Chart 4 stay within about 37–47 location-days per 1,000 residents per year across the whole noise range.
- **Other covariates (M2, all types).** Renter share +15% per 10 points; Hispanic share +14% per 10 points; Black share +7% per 10 points; Asian share −2%.

## Plain-English statement of the key coefficient

> Holding modelled transportation noise and neighbourhood demographics fixed, census tracts that were low-income and gentrifying between 2016–20 and 2020–24 generated about 14% more noise-complaint location-days per resident than low-income tracts that were not gentrifying. How much modelled road, rail and aviation noise a tract gets tells us almost nothing about how often it complains.

## Caveats for the text

- 311 measures **reporting**, which depends on who notices noise, who knows about 311, who expects a response, and possibly who is new to a neighbourhood. It does not measure noise.
- The BTS map does not model the sources most 311 complaints are about (neighbours, parties, bars, construction, car alarms). Nor does it include the subway. A weak link between complaints and modelled noise is therefore expected, and it is not evidence that people don't notice traffic noise.
- The typology is our own definition. P15 checks sensitivity to it.
- These are associations between tracts. They do not show that newcomers complain more than long-time residents.

**Recommendation on framing:** the NYC section should be framed as **exploratory**, not as the lead. The gentrification difference is robust and clearly significant, but the comparison it rests on (complaints vs modelled transportation noise) is weak by design.
