# Loud and Unequal

**Transportation noise, complaints and who gets heard.**

This project combines the U.S. Bureau of Transportation Statistics' [National Transportation Noise Map](https://www.bts.gov/geospatial/national-transportation-noise-map) (road, rail and aviation, 2016 / 2018 / 2020) with American Community Survey demographics to measure who is exposed to transportation noise in the 20 largest U.S. metro areas. It then uses NYC 311 noise complaints to test a second inequality: whether complaints track modelled noise, or track who complains.

> Status: in progress. The plan and its progress are in [CLAUDE.md](CLAUDE.md); the full spec is in [17-noise-exposure-equity.md](17-noise-exposure-equity.md).

## Quick start

```bash
uv sync                 # install (Python 3.12)
cp .env.example .env    # add a free Census API key
make help               # list pipeline steps
make test
```

## Data

All sources are open. See [DATA.md](DATA.md) for URLs, versions, sizes and licences. Raw data (~100 GB, mostly noise rasters) is downloaded into `data/raw/` and never committed.

## Caveats

The BTS map is a **model**, not measurement, and it leaves out construction, nightlife and industrial noise. Results describe neighbourhoods, not individuals.

## Licence

Code: MIT. Data: see each source's terms in DATA.md.
