# Distribution drafts (P19)

Drafts only; nothing here has been sent or posted. Audiences come from spec §9. Every number
below is in `tests/test_headline_pinned.py`; if that test changes, re-check these drafts.

Links (live once GitHub Pages is on):

- Article: https://johnpospisil.github.io/noise-exposure-equity/report/
- Lookup: https://johnpospisil.github.io/noise-exposure-equity/app/
- Code and data: https://github.com/johnpospisil/noise-exposure-equity

## Checklist

- [ ] GitHub Pages enabled (Settings → Pages → Source: GitHub Actions); workflow run green
- [ ] Article, lookup and map open on phone and desktop from the public URLs
- [ ] Release `v1.0` tagged
- [ ] r/urbanplanning post
- [ ] r/nyc post (NYC angle: complaints vs noise)
- [ ] Two or three city/metro reporters who cover noise, transit or housing
- [ ] NYC Council members on the Environmental Protection committee (noise code)
- [ ] Acoustical Society of America: Noise technical committee / Acoustics Today
- [ ] Reply to questions for the first week; log corrections in the repo

---

## 1. r/urbanplanning

**Title:** Lower-income neighbourhoods are louder in all 20 of the largest US metros. I mapped the BTS noise model against Census data.

I combined the Bureau of Transportation Statistics' 2022 National Transportation Noise Map with Census data for 85,000 block groups in the 20 largest metros (126 million people).

- In each metro's lowest-income fifth of neighbourhoods, 15.2% of residents live with modelled road, rail or aircraft noise of 55 dBA or more (24-hour average). In the highest-income fifth it's 6.5%. The lowest fifth is more exposed in every metro.
- Rail and aircraft noise are the most unequal (about 3.5 times); major roads less so (1.7 times).
- Much of the gap runs through renting and density. Once those are in the model, little separate income gap remains, which says something about where cities put rental housing.

Caveats: it's a model, not measurements; major roads only; no subways; neighbourhood-level, not households. Methods, code and data are all open: [article link]. There's also a lookup for any address in the 20 metros: [app link].

Happy to hear where the method falls short.

## 2. r/nyc

**Title:** NYC 311 noise complaints barely follow modelled traffic, train and plane noise, but they do follow gentrification

I matched 7 million NYC 311 noise complaints (2016–2026) to census tracts and to the federal transportation noise model.

- Complaints hardly rise with modelled transportation noise. Most complaints are about neighbours, parties and car alarms, which the model doesn't cover.
- Gentrifying low-income tracts file about 14% more complaints than other low-income tracts with the same modelled noise and demographics.
- 311 measures who reports noise, not how loud it is. One Bronx building alone filed a quarter of 2025's residential complaints, so I counted each location at most once a day.

This part is exploratory. Full write-up: [article link]. You can look up your own block group: [app link]. Note the model doesn't include the subway, even elevated lines.

## 3. Reporter pitch (email)

**Subject:** Data: lower-income neighbourhoods are louder in all 20 big US metros (with a per-address lookup)

Hi [name],

I've published an open analysis of who lives with transportation noise in the 20 largest US metros, using the federal noise map released this year and Census data. In [their metro], [metro-specific figure from disparity_income.csv] of residents in the lowest-income fifth of neighbourhoods live at 55 dBA or more, against [figure] in the highest-income fifth. Across all 20 metros the figures are 15.2% and 6.5%.

Three things that might be useful for a story:

1. A lookup that shows modelled road, rail and aircraft noise for any address's neighbourhood: [app link]
2. Metro-by-metro tables you can reuse, with sources: [repo link]/tree/main/data/processed
3. A WHO-based estimate of how many extra people are highly annoyed or have disturbed sleep, by metro.

The numbers are modelled, not measured, and describe neighbourhoods, not individual homes. I'm glad to walk through the method or pull figures for your area.

[signature]

## 4. NYC Council (Environmental Protection, Resiliency and Waterfronts committee)

**Subject:** Noise complaints and noise exposure in NYC: who gets heard

Dear Council Member [name],

As the Council considers changes to the noise code, I'd like to share an open analysis that may be useful.

- 311 noise complaints in New York barely track modelled transportation noise (road, rail and aircraft).
- Gentrifying low-income tracts file about 14% more complaints than other low-income tracts with the same modelled noise and demographics.
- Across the metro, lower-income neighbourhoods are more exposed to transportation noise.

If enforcement follows complaints, it may follow who complains rather than where noise is worst. The analysis is exploratory and neighbourhood-level; the full method and tract-level tables are public: [article link].

I'd be happy to brief your staff.

[signature]

## 5. Acoustical Society of America (Noise TC / Acoustics Today)

**Subject:** Open analysis: BTS National Transportation Noise Map × Census, 20 US metros

Hello,

I've published an open-source analysis that links the BTS National Transportation Noise Map (2016–2022) to 2020 Census blocks across the 20 largest US metros, and applies the WHO 2018 exposure-response functions.

The method choices may interest the committee:

- Sources are combined per cell by energy sum.
- Censored cells below 45 dBA are handled with explicit floors.
- LAeq,24h is converted to Lden and Lnight with stated offsets, plus sensitivity ranges.
- Results use population shares rather than area energy means, because track and runway cells dominate those.

I'd welcome review, especially of the metric conversions and of the aircraft estimate. The WHO aircraft guideline is below the map's 45 dBA floor, so that estimate is a lower bound.

Code, tests and method notes: [repo link]. Article: [article link].

[signature]
