# Address lookup app (P18)

A static page: no server and no build step.

1. The address goes to the U.S. Census Geocoder, which returns the 2020 census block. The request uses JSONP, because the API sends no CORS headers.
2. The page reads the block group's values from `data/{state}.json`. That data is built by `make app` (`ne.build.app_data`) from `data/processed/analysis_bg.parquet` (2022 BTS map, ACS 2018–22).

**Data:** 23 files, 5.6 MB in total. Derived from BTS and Census data (public domain); no NHGIS; no 311 data.

**Run locally:** `cd app && python -m http.server 8765`, then open http://localhost:8765. The page has to be served over HTTP because it fetches its data files; opening the file directly won't work.

**Deploy:** `make site` assembles `_site/`:
- `report/`: the article.
- `app/`: this page.
- `map/`: the interactive New York map.

A GitHub Actions workflow publishes `_site/` to GitHub Pages. It is set up in P19.
