# Results notes: robustness (P15)

The full grid is in `data/processed/robustness_grid.csv` (72 checks, built by `ne.models.robustness`, `make models`). Each row gives the baseline, the value under the alternative, its 95% CI where one exists, and flags for a change of sign or of statistical significance.

## What holds

- **Descriptive disparities never flip.** Ratios at ≥ 55 dBA unless stated, across thresholds 45–70 dBA, area weighting, the 2020 map, dropping unreliable ACS income, and road + aviation only:
  - Lowest/highest income fifth: always 1.86–2.36× (baseline 2.36).
  - Black/White: 1.26–1.49× (baseline 1.48).
  - Hispanic/White: 1.30–1.55× (baseline 1.55).
- **The raw income gap in regressions** (spec A, metro fixed effects) stays positive and significant in every variant:
  - 6.4–9.8 percentage points at ≥ 55 dBA;
  - 0.8 points at ≥ 65 dBA, where shares are small.
- **NYC: gentrifying vs other low-income tracts** stays positive and significant without the top 1% of tracts (1.16×), excluding Manhattan (1.12×), with an income-growth typology instead of rent growth (1.11×), and with a major-roads-only noise measure (1.14×).
- **NYC: modelled noise never predicts complaints in any meaningful way.** The rate ratio per 10 points stays within 0.98–1.02 in every variant.

## What changes sign or significance

| Result | Variant | Baseline | Variant value | Note |
|---|---|---|---|---|
| Income gap, spec C (renting + density controls) | spatial lag model | −1.2 pp (sig.) | +0.06 (n.s.) | sign flips; already reported as "little separate income gap" |
| Income gap, spec C | spatial error model | −1.2 pp (sig.) | +0.8 (sig.) | sign flips: the spec C sign is not robust, only its small size is |
| NYC gentrifying vs other low-income | raw complaint counts | 1.14 (sig.) | 1.04 (0.92–1.19, n.s.) | the two Bronx super-complainer buildings (P05) swamp raw counts; location-days is the right outcome |
| NYC gentrifying vs other low-income | vehicle / commercial complaints only | 1.14 (sig.) | 1.10 / 1.10 (n.s.) | same direction, smaller samples |
| NYC modelled noise | residential complaints only | 0.99 (n.s.) | 0.98 (0.97–0.99, sig.) | slightly *fewer* residential complaints where transportation noise is higher |
| NYC modelled noise | raw counts; roads only; street / vehicle / commercial | 0.99 | 1.00–1.02 | flagged sign "changes" are around 1.0 and not significant: no association either way |

## Health estimates: what moves them most

| Estimate (millions, extra above WHO guideline) | Baseline | Range across checks | Biggest driver |
|---|---|---|---|
| Aircraft, highly annoyed | 2.94 | 1.28 – 8.25 | **Censored residents.** Placing residents below 45 dBA at 45 dBA gives 8.3 M (at 42.5 dBA: 3.8 M). The aircraft guideline (45 dB Lden ≈ 42 dBA LAeq,24h) sits below the map's 45 dBA floor, so the headline is a lower bound. |
| Road, highly annoyed | 0.82 | 0.37 – 1.55 | band position and offsets; floor has no effect (the road guideline is well above 45 dBA) |
| Rail, highly sleep-disturbed | 0.57 | 0.24 – 1.24 | band position; rail night offset ±2 dB gives 0.38–0.83 |

The 2020 map gives lower aircraft numbers (2.1 M, COVID-era flights) and similar road numbers.

## Not run, and why

- **Censoring floor for exposure shares.** The headline shares count residents *at or above* 45–70 dBA, which never uses the floor. The floor matters only for the health estimates (above) and for the capped energy-mean sensitivity metric.
