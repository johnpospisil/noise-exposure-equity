# Results notes: health translation (P14)

Draft wording for the report. 2022 BTS map, 20 metros (126 M residents). Tables: `data/processed/health_estimates.csv`, `health_by_income.csv`. Chart 5: `figures/chart5_health.png`.

## Method in one paragraph

Residents of each block group are split into 5-dB bands of modelled LAeq,24h. Each band is converted to Lden or Lnight with assumed per-source offsets:
- road and aviation: +3 / −7 dB;
- rail: +5 / −2 dB.

The converted levels go into the WHO 2018 exposure-response curves for % highly annoyed (Guski et al. 2017) and % highly sleep-disturbed (Basner & McGuire 2018). The headline counts **extra** cases above the WHO guideline level for each source:

| Outcome | Road | Rail | Aircraft |
|---|---|---|---|
| Lden (highly annoyed) | 53 dB | 54 dB | 45 dB |
| Lnight (sleep-disturbed) | 45 dB | 44 dB | 40 dB |

Ranges vary two assumptions: where residents sit within each band (lower edge vs upper edge), and the conversion offsets (±2 dB). They are not confidence intervals; the curves' own uncertainty is not included. Sources are estimated separately and not added.

## Headline numbers (20 metros, extra cases above WHO guideline levels; central estimate and range)

| | Road (major roads) | Rail | Aircraft |
|---|---|---|---|
| Highly annoyed | 0.82 M (0.37–1.55 M) | 0.66 M (0.26–1.58 M) | **2.94 M** (1.28–4.66 M) |
| Highly sleep-disturbed | 0.22 M (0.10–0.44 M) | **0.57 M** (0.24–1.24 M) | 0.52 M (0.17–1.33 M) |

Totals without subtracting the guideline baseline: highly annoyed 2.8 M (road), 2.5 M (rail), 4.9 M (aircraft).

## Equity

Extra cases per 1,000 residents, lowest vs highest income fifth (within-metro quintiles, pooled):

| | Lowest fifth | Highest fifth | Ratio |
|---|---|---|---|
| Aircraft, highly annoyed | 32.0 | 14.2 | 2.3× |
| Rail, highly annoyed | 9.2 | 2.7 | 3.4× |
| Road, highly annoyed | 8.1 | 4.9 | 1.7× |
| Rail, sleep-disturbed | 7.9 | 2.3 | 3.4× |

## Caveats for the text

- These are model-on-model estimates: modelled noise, assumed metric conversions, and population-average curves mostly from European studies.
- The aircraft curve is the steepest, and its guideline level (45 dB Lden) is very low, so aircraft dominate the annoyance numbers. Readers should know this.
- Residents below 45 dBA are not counted, so the numbers are conservative at the low end.
- Rail's night offset (−2 dB) is an assumption: freight runs at night. It drives the rail sleep numbers. P15 tests it.
- Neighbourhood-level estimates; nothing here applies to an individual.
