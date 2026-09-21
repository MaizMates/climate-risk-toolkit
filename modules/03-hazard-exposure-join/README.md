# 03 — Hazard-exposure join: plants, not grid cells

**At k=2 days, 43.2% of 260,626 MW of thermal generating capacity across the eleven countries in
module 01's hazard table sits in a country projected to cross that threshold — interval [36.9%,
49.5%] from resampling plants, with 17.9% of the exposed total held by just ten plants.**

## Scope, narrowed on 21/09/2026

The roadmap originally asked for plants joined to hazard *grid cells*. The World Bank CCKP API
returned HTTP 502 when that build ran, and module 01's committed output is country-level, not
gridded, so the gridded version cannot be built from anything currently in hand. This module
joins at country resolution and says so on every page rather than waiting on someone else's
outage. The gridded version becomes module 11 when CCKP is back — see `modules/ROADMAP.md`.

## Estimand

The share of total thermal generating capacity, in MW, across the countries in module 01's hazard
table, that sits in a country whose projected annual count of days at or above a 35°C heat index
rises by more than *k* days from baseline (1995–2014) to mid-century (2040–2059) under SSP2-4.5.

## Data

- **Plants.** WRI Global Power Plant Database, `output_database/global_power_plant_database.csv`,
  fetched live from `raw.githubusercontent.com` by `src/hazard_exposure.py`. No key, no
  transcription, 34,936 rows, 676 thermal plants matched to the eleven countries in scope.
- **Hazard.** `modules/01-heat-stress-gradient/results/heat_gradient.json`, already in this
  repository. This is the reuse the roadmap intends — module 03 consumes module 01's output
  rather than re-fetching the hazard layer, so the module only covers the eleven countries module
  01 covers.
- **Validation.** Eurostat `nrg_inf_epc`, combustible-fuel net electrical capacity, public
  dissemination API, no key — an asset-total figure independent of WRI's plant-level compilation.

## Method

Filter WRI to thermal fuels (coal, oil, petcoke always; gas by default; see sensitivity), sum
capacity by ISO3, join to the hazard table by ISO3. Every plant in a country inherits that
country's national hazard figure — there is no finer join available at this resolution.

## Uncertainty

Bootstrap over plants (2,000 resamples with replacement) for an interval on the exposed share at
each *k*, because the capacity distribution is heavily skewed by a few large plants. At k=2, the
top ten exposed plants hold 17.9% of the exposed total — `tests/test_hazard_exposure.py` has a
case that fails if the interval stops widening with that concentration.

## Sensitivity

Sweeping *k* from 0 to 8 moves the exposed share from 97.8% to 15.2%, as expected. But the fuel
definition moves it more than the threshold does at a fixed k: at k=2, including gas gives 43.2%
exposed on 260,626 MW; excluding it gives 28.4% exposed on 136,693 MW — a 14.8-point swing, larger
than moving k from 1 to 3 (48.2% to 43.2%, 5.0 points). Biomass and waste barely move either
figure — both are a small share of installed MW in this country set.

## Validation

Eurostat's combustible-fuel capacity is the closest published independent analogue to this
module's thermal definition. Spain, Greece, Poland, Portugal and Italy — the countries that decide
the headline number — sit within 10% of the Eurostat figure. Austria (WRI/Eurostat ratio 0.37) and
Belgium (0.58) are the worst outliers: WRI is missing or under-recording thermal capacity there.
Neither crosses k=2, so this does not move the headline, but it is exactly the kind of gap that
would matter for a country nearer the threshold.

## Limits

- **Country resolution attributes a national average to every plant in the country.** Close to
  defensible for Spain — one country, one climate zone dominating its thermal fleet. Close to
  meaningless for Germany or France: a plant on the Mediterranean coast and one on the North Sea
  get the same number. DEU (28.8% of total thermal MW) and FRA (5.0%) are the countries where this
  matters most, because they are large and climatically diverse, not because they are small.
- **No backtest.** STANDARD.md requires backtesting anything forward-looking. The forward-looking
  quantity here is CCKP's CMIP6 projection of `change_days`, produced by module 01 and consumed
  unchanged — there is no held-out year to test it against, because mid-century has not happened
  and the projection was never fitted by this module. Module 01's own limitation carries forward:
  ensemble median only, no spread, so this module has no view on the tail of the hazard estimate.
- **The asset register itself has gaps.** The Eurostat validation shows WRI under-records thermal
  capacity in at least two of the eleven countries, which compounds the resolution problem rather
  than being independent of it.

## Run it

```bash
python3 src/hazard_exposure.py   # fetch WRI + Eurostat, join to module 01's hazard table -> results/
python3 tests/test_hazard_exposure.py
python3 src/deck.py              # six pages
```

[`notes.md`](notes.md) has what was tried and dropped: the grid-cell join that couldn't be built,
the nuclear question, and why the threshold is `>` and not `>=`.
