# Results notes: exposure disparities and models (P10–P11)

Draft wording for the report. 2022 BTS map (road + rail + aviation), 20 largest metros, 2020 block groups. These figures come from modelled noise, not measured noise, and they describe neighbourhoods, not individuals.

## Descriptive (P10)

- In all 20 metros, the lowest-income fifth of neighbourhoods has a larger share of residents at ≥ 55 dBA than the highest-income fifth. Pooled across metros: **15.2% vs 6.5%**. At the stricter ≥ 65 dBA threshold: 1.8% vs 0.9%.
- Every source shows the same income gradient. The ratio is steepest for aviation (3.5×) and rail (3.4×), and flatter for major roads (1.7×).
- At ≥ 55 dBA, 12–13% of Black, Hispanic and Asian residents live in blocks at or above the threshold, against 8.2% of White residents (pooled; partly reflects which metros each group lives in).

## Models (P11)

Outcome: % of a block group's residents at ≥ 55 dBA. The sample is 78,549 block groups. Coefficients compare the lowest-income fifth (Q1) with the highest (Q5).

| Specification | Q1 vs Q5 (pp, 95% CI) |
|---|---|
| A: metro fixed effects | **+8.6** (8.0 to 9.1) |
| B: + race/ethnicity shares | +5.3 (4.7 to 5.8) |
| C: + renter share, log density | −1.2 (−1.7 to −0.6) |
| C, spatial error model | +0.8 (0.5 to 1.2) |
| C, spatial lag model (direct effect) | +0.1 (−0.2 to 0.3) |

**Interpretation**
- The income gap is real and large on its own terms (spec A). About **40% of it overlaps with race/ethnicity composition** (B). Almost all of what remains overlaps with **renting and density**: lower-income households live in denser, rental-heavy neighbourhoods, and those neighbourhoods sit next to major roads, rail lines and flight paths.
- Renting and density are probably part of *how* the disparity arises (cheaper rental housing is built or left near infrastructure). They are not proof that the disparity is innocent. The article should say this plainly and avoid "income doesn't matter once you control for…".
- Hispanic share stays positive in every spec C model (OLS +0.6, error +0.24, lag +0.08 pp per 10 points). Black share is positive in OLS and in the error model, and about zero in the lag model.
- **Spatial dependence is strong.** Moran's I on the OLS residuals is 0.66 pooled, and 0.25–0.70 within metros. The robust LM tests favour the lag model in all 20 metros. Noise footprints cross block-group borders, so standard errors that ignore space are too small.
- Per metro (spec C, OLS), the Q1 gap is significantly positive in 3 metros (Seattle, Miami, Detroit) and significantly negative in 5 (Boston, Minneapolis, Dallas, Denver, Washington). Under the spatial models almost every metro sits near zero.
- R² is low (0.17 for spec C at 55 dBA; 0.04 at 65 dBA). Most variation in exposure is about where infrastructure runs, not who lives there.

## Change over time (box only, decision P08)

Road + aviation, ≥ 55 dBA, pooled: the Q1 share moves 10.9% (2016) → 11.1% (2018) → 9.1% (2020) → 10.4% (2022); Q5 moves 5.0% → 5.2% → 4.7% → 5.2%. The ordering of groups is the same in every release. The year-to-year changes mix real change with changes in which roads BTS models, plus COVID-era traffic in 2020. Do not read them as trends.
