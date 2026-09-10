# 01 — Heat-stress gradient across euro-area countries

**The ranking by level and the ranking by change are not the same ranking.** Under SSP3-7.0,
Spain leads both. Portugal is 2nd by level (13.3 days per year at or above a 35 °C heat index in
2040–2059) but 3rd by change (+8.2 days on the 1995–2014 baseline); Greece is 3rd by level (10.6)
and 2nd by change (+8.4). Small in absolute days, and I am not going to inflate it. What it
establishes is that level and gradient are separate variables, which is the assumption module 02
needs before it is worth overlaying exposures.

Why that distinction is worth a module: a book concentrated where the level is already high holds
a hazard that should be priced today; a book concentrated where the change is largest holds one
that arrives inside the maturity of loans being written now. Same map, two horizons.

[`deck.pdf`](deck.pdf) is the four-page version: question, method, result, limits.

## Result

SSP3-7.0, 2040–2059, days per year at or above 35 °C:

| Rank | By level |  | By change from baseline |  |
|---|---|---|---|---|
| 1 | ESP | 20.58 | ESP | +13.71 |
| 2 | PRT | 13.29 | GRC | +8.45 |
| 3 | GRC | 10.56 | PRT | +8.16 |
| 4 | ITA | 4.14 | ITA | +3.72 |
| 5 | FRA | 2.00 | FRA | +1.57 |
| 6 | POL | 0.83 | POL | +0.72 |
| 7 | AUT | 0.79 | AUT | +0.71 |
| 8 | DEU | 0.72 | DEU | +0.63 |
| 9 | BEL | 0.21 | BEL | +0.21 |
| 10 | NLD | 0.11 | NLD | +0.11 |
| 11 | IRL | 0.00 | IRL | +0.00 |

Full table including SSP2-4.5 in [`results/heat_gradient.json`](results/heat_gradient.json).

## Data and method

World Bank Climate Change Knowledge Portal, CMIP6 ensemble median, indicator `hd35`, days per
year with a maximum heat index at or above 35 °C. Baseline 1995–2014 historical; projection
2040–2059 under SSP2-4.5 and SSP3-7.0. Public API, no key, no registration, queried live. Change
is projection minus baseline, per country, one request per collection for the whole country list.

## Limits

- **Country means hide the hazard.** Heat stress is urban and local; a national mean over Spain
  averages Seville with Bilbao. Countries are used because exposure data is reported by country,
  not because the hazard is national.
- **`hd35` is one indicator.** It says nothing about drought, flood, wildfire or wind, which
  reach a balance sheet through different channels.
- **Ensemble median only.** No spread, so no view on the tail, which is what a supervisor asks
  about first. An interquartile range in place of the median is the first thing I would add.
- **No exposures.** This is the hazard layer alone. Overlaying it is module 02, and doing that
  honestly needs exposure data at a finer grain than country.

## Run it

```bash
python3 tests/test_hazard.py    # two checks, no framework
python3 src/hazard.py           # queries the API, writes results/heat_gradient.json
python3 src/deck.py             # writes deck.pdf, four pages, figure and numbers from that json
```

[`notes.md`](notes.md) has the decisions: why CCKP and not NGFS, why country level, and the
key-versus-value bug that made every change equal to the projection until the test pinned it.
