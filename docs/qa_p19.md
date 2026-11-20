# P19 QA checklist (2026-11-19)

## Clean-clone build

Fresh `git clone` of `main` at 0bc614b (P18). Raw inputs linked or copied in, `data/interim/`
empty, `uv sync` from `uv.lock`, then `make all`. Raw inputs:

- BTS zips (symlinked; must be downloaded by hand);
- TIGER zips (symlinked; would download automatically);
- ACS JSON cache;
- 311 months.

| Run | Result | Running time |
|---|---|---|
| 1 | BTS ingest: 537 state rasters converted, all 11 zips matched the manifest checksums. **Failed** at `ne.ingest.tiger`: wrote `cbsa_2020.parquet` into `data/interim/census/` before the folder existed. | ≈ 70 min (wall clock 4 h 31 min; the laptop slept for about 3¼ h) |
| 2 | Fix applied. TIGER, ACS, 311, zonal statistics (20 metros), analysis table, NYC panel and disparity all ran. **Failed** at `ne.models.spatial_reg`: the Makefile passed `-W ignore` after `-m`. | 50 min |
| 3 | Fix applied. Resumed with `make models figures report app`: all steps ran, exit 0. | 2 min |

**Total:** about 2 hours of computing time.

### Bugs found and fixed

1. `ne.ingest.tiger.build_cbsa` now creates its output folder. Regression test: `tests/test_tiger.py`.
2. Makefile: a new `PYQ` variable puts `-W ignore` before `-m` for `spatial_reg`, `complaints_nb` and `robustness`.
3. `metro_exposure.csv` and `bts_reconciliation.csv` had no code path in `make all`. They were written by hand in P08. Now `ne.build.zonal_stats.summaries()` writes them at the end of the zonal step. Test: `test_summaries_write_metro_and_benchmark_tables`.

### Reproducibility

After the rebuild, `git status` in the clone showed **no changes** to any committed output. Every file below was rewritten during the run (its timestamp updated) and came out byte-for-byte identical:

- **Data:** `bg_noise.parquet`, `nyc_panel.parquet`, `nyc_tracts.parquet` and all 13 result CSVs (including the two above, regenerated with fix 3).
- **Figures:** all 9 SVGs (deterministic; no timestamps).
- **Report:** `report/_variables.yml`, `report/claims.csv`.
- **App:** all 23 JSON files in `app/data/`.

The 311 step re-downloaded the unsettled months (2026-09 to 2026-11). The NYC panel (window ending 2026-10) did not change.

## Key numbers (spot checks)

`tests/test_headline_pinned.py` pins 29 headline numbers from `ne.report.build()`; all pass.

| Number | Pinned value |
|---|---|
| Share ≥ 55 dBA, lowest vs highest income fifth (2022, 20 metros) | 15.2% vs 6.5% (2.4×) |
| Share ≥ 65 dBA, lowest vs highest fifth | 1.8% vs 0.9% |
| Metros where the lowest fifth is more exposed | 20 of 20 |
| Ratio at 55 dBA: aircraft / rail / road | 3.5× / 3.4× / 1.7× |
| White / Black / Hispanic / Asian residents ≥ 55 dBA | 8.2 / 12.2 / 12.8 / 11.8% |
| Our 2020 share ≥ 60 dBA vs UW DEOHS | 3.5% vs 3.6% |
| Income gap, specs A / B / C (points) | +8.6 / +5.3 / −1.2 |
| Highly annoyed above WHO guideline: aircraft / road / rail | ≥ 2.9M / 0.8M / 0.7M |
| NYC: complaints per 10 points of noise; gentrifying vs other low-income tracts | 0.99; +14% (6 to 22) |

## Licence audit

- [x] No NHGIS file in any commit (`git log --all --name-only`), release or the app. NHGIS was never used, so no NHGIS citation or bibliography submission applies (DATA.md §5).
- [x] No `data/raw/` or `data/interim/` content in history (only `.gitkeep`). No `.env` in history.
- [x] NYC 311: only tract × month counts (`nyc_panel`) and tract attributes (`nyc_tracts`) are committed. There are no complaint-level records.
- [x] Every committed table has a `derived_from` column and an entry in `data/processed/README.md`. `app/data/meta.json` names its sources.
- [x] The app and report repeat BTS's caveat ("should not be used to evaluate noise levels at individual locations").
- [x] Code: MIT (`LICENSE`). Inputs: public domain (BTS, Census), NYC Open Data terms (attributed), published ERF coefficients (cited).

## Tests and lint

- `uv run pytest -q`: 171 passed.
- `make lint`: clean.

## Publish

- [x] GitHub Pages enabled; first workflow run green (build 32 s, deploy 11 s); live lookups tested.
- [x] Release `v1.0` tagged.
- [ ] Distribution: see `docs/distribution_drafts.md`.
