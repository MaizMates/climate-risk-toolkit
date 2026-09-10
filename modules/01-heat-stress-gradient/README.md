# 01 — Heat-stress gradient across euro-area countries

**The question.** Between now and mid-century, where does heat stress grow fastest, and is the
ranking by *change* the same as the ranking by *level*? If the two orderings agree, a supervisor
can keep using today's map. If they disagree, then a portfolio concentrated where the level is
already high is exposed now, while a portfolio concentrated where the change is largest is
exposed to repricing later, and those are two different conversations.

**Why I started here.** Both my ECB years were transition risk: PACTA alignment over AnaCredit
exposures, transition trajectories, Pillar 3 disclosure quality. The physical half is the part I
have read about and not built. This is the smallest honest piece of it.

## Data

World Bank Climate Change Knowledge Portal, CMIP6 ensemble median, indicator `hd35`, days per
year with a maximum heat index at or above 35 °C. Baseline 1995–2014 historical; projection
2040–2059 under SSP2-4.5 and SSP3-7.0. Public API, no key, no registration. Queried live.

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

**The two orderings differ.** Greece and Portugal swap: Portugal is second by level and third by
change, Greece the reverse. The effect is small in absolute days, and I am not going to inflate
it. What it establishes is that level and gradient are separate variables, which is the
assumption module 02 needs before it is worth overlaying exposures.

## Limits, stated plainly

- **Country means hide everything that matters.** Heat stress is an urban and a local
  phenomenon; a national average over Spain averages Seville with Bilbao. This ranks countries
  because exposure data is reported by country, not because the hazard is national.
- **`hd35` is one indicator.** It says nothing about drought, flood or wind, and those drive
  different losses through different channels.
- **Ensemble median only.** No spread, so no view on tail risk, which is the part a supervisor
  actually asks about.
- **No exposures.** This is the hazard layer alone. Overlaying it on lending is module 02, and
  doing it properly needs exposure data at a finer grain than country.

## Run it

```bash
python3 tests/test_hazard.py    # two checks, no framework
python3 src/hazard.py           # queries the API, writes results/heat_gradient.json
python3 src/deck.py             # writes deck.pdf, four pages, figure from that json
```

[`deck.pdf`](deck.pdf) is the four-page version: question, method, result, limits. The figure is
drawn from `results/heat_gradient.json`, so the deck cannot drift away from the numbers.
