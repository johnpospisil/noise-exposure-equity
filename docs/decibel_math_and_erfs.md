# Decibel maths and WHO exposure-response functions

Code: `src/ne/build/combine_sources.py`, `src/ne/models/who_erf.py`. Tests: `tests/test_decibels.py`.

## 1. Combining and averaging levels

Decibels are logarithmic, so they are never added or averaged directly.

| Operation | Formula | Example |
|---|---|---|
| Energy sum (several sources at one place) | L = 10·log10(Σ 10^(Lᵢ/10)) | 60 + 60 dB = **63.01 dB**; 60 + 50 dB = 60.41 dB |
| Energy mean (one source over places or times) | L = 10·log10(Σ wᵢ·10^(Lᵢ/10) / Σ wᵢ) | mean of 60 and 70 dB = **67.40 dB** (not 65) |

**Censored cells.** The BTS rasters leave out values below 45 dBA. In code these cells are `NaN`, meaning "below the mapped range".

- Default policy `floor`: a censored cell counts as 45 dB. This is an upper bound.
- Sensitivity checks:
  - `floor=40`;
  - `policy="zero"`, where a censored cell adds no energy.
- If every input is censored, the result stays `NaN` ("< 45") under every policy.
- In energy means, censored cells still count in the denominator: they are real places, just quiet ones.

**Cap.** `energy_mean(..., cap=100)` clips track and runway cells, which reach up to 125 dB, before averaging. Without the cap, one 125 dB cell among 999 cells at 50 dB gives a mean of 95 dB; with it, 80 dB. This is a sensitivity check only (decision P03).

## 2. LAeq,24h → Lden and Lnight

The BTS map reports LAeq,24h. The WHO curves need Lden (day–evening–night, with +5 dB evening and +10 dB night penalties) or Lnight. Given the share of the 24-hour sound energy in each period, with day d (07–19), evening e (19–23) and night n (23–07):

- Lden − LAeq24 = 10·log10(d + e·10^0.5 + n·10)
- Lnight − LAeq24 = 10·log10(n·3)

| Profile (d / e / n) | Lden offset | Lnight offset |
|---|---|---|
| Flat (every hour equal) | +6.4 | 0.0 |
| Road-like (0.78 / 0.14 / 0.08) | +3.1 | −6.2 |
| Config: road and aviation | +3.0 | −7.0 |
| Config: rail (more night traffic) | +5.0 | −2.0 |

The offsets are **assumptions**, set in `config/thresholds.yaml` (`metric_offsets_db`). They are not measured. Freight rail and some airports carry more traffic at night than roads, so rail uses a flatter assumption (decision P06). P15 tests the results against the offsets.

## 3. Exposure-response functions (primary set)

These are the curves behind the WHO Environmental Noise Guidelines (2018), as written into Annex III of the EU noise directive (Commission Directive (EU) 2020/367). Each curve has the form % = a + b·L + c·L².

| Outcome | Source | a | b | c | Evaluated on | Reference |
|---|---|---|---|---|---|---|
| %HA (Lden) | road | 78.9270 | −3.1162 | 0.0342 | 45–75 dB | Guski et al. 2017 |
| | rail | 38.1596 | −2.05538 | 0.0285 | 45–75 dB | Guski et al. 2017 |
| | aviation | −50.9693 | 1.0168 | 0.0072 | 40–75 dB | Guski et al. 2017 |
| %HSD (Lnight) | road | 19.4312 | −0.9336 | 0.0126 | 40–65 dB | Basner & McGuire 2018 |
| | rail | 67.5406 | −3.1852 | 0.0391 | 40–65 dB | Basner & McGuire 2018 |
| | aviation | 16.7885 | −0.9293 | 0.0198 | 40–65 dB | Basner & McGuire 2018 |

**Checks against WHO.** WHO set its guideline levels where the curves reach about 10% HA or 3% HSD. The tests check our code against these values:

| Outcome | Source | Level | Result |
|---|---|---|---|
| %HA | road | 53 dB Lden | 9.8% |
| %HA | rail | 54 dB Lden | 10.3% |
| %HA | aviation | 45 dB Lden | 9.4% |
| %HSD | road | 45 dB Lnight | 2.9% |
| %HSD | rail | 44 dB Lnight | 3.1% |
| %HSD | aviation | 40 dB Lnight | 11.3% |

**Outside the evaluated range:**
- Below the lower limit, the result is 0 by default, meaning no estimated cases. The quadratic curves turn upward again at low levels, which is a fitting artefact. A censored input also gives 0.
- Above the upper limit, the level is held at the limit; we don't extrapolate.

**Background annoyance.** The road curve never falls below about 8% HA, even at 45 dB. So P14 headlines the *extra* cases above the WHO guideline level (road 53, rail 54, aviation 45 dB Lden; night: road 45, rail 44, aviation 40 dB Lnight), and reports the total alongside (decision P06).

**Uncertainty.** The confidence intervals for the curves are added in P14, taken from the source papers. They are not coded yet.

### References
- WHO Regional Office for Europe (2018). *Environmental Noise Guidelines for the European Region.*
- Guski R., Schreckenberg D., Schuemer R. (2017). WHO Environmental Noise Guidelines for the European Region: a systematic review on environmental noise and annoyance. *IJERPH* 14(12):1539. doi:10.3390/ijerph14121539
- Basner M., McGuire S. (2018). WHO Environmental Noise Guidelines for the European Region: a systematic review on environmental noise and effects on sleep. *IJERPH* 15(3):519. doi:10.3390/ijerph15030519
- Commission Directive (EU) 2020/367 amending Annex III of Directive 2002/49/EC (harmful effects methods).

*Modelled noise, not measured noise. Estimates apply to neighbourhoods, not individuals.*
