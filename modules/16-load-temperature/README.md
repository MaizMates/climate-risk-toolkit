# 16: How much of German electricity demand is weather?

**German daily electricity load rises by 14.9 GWh for every degree-day of heating below 16 C (95% interval [13.3, 15.9]) and by 7.1 GWh [3.8, 17.8] per degree-day of cooling above 21 C, on 2019 to 2025. Weather accounts for 7.0% of annual load [6.6%, 8.0%], almost all of it heating (6.9%; cooling is 0.08%). A year that is uniformly 1 C warmer uses 3.50 TWh less [3.21, 3.76], 0.73% of load. Fitted on 2019 to 2024 and used on 2025, the model misses the daily load by 55.0 GWh (RMSE, interval [47.0, 59.8]), against 111.6 with no temperature and 72.1 for last year's same weekday. All of this rests on one specification choice: with a seasonal control in the model the heating slope is 5.8 to 7.0 GWh and the 1 C effect 0.78 to 1.00 TWh.**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

The temperature sensitivity of German daily electricity load, in GWh per degree-day of heating (below a threshold Th) and of cooling (above Tc), net of weekday, holiday, Christmas-week and year effects, on the seven full years 2019 to 2025. Temperature is the population-weighted mean of the daily mean temperature of Berlin, Hamburg, Munich, Cologne, Frankfurt and Stuttgart. The thresholds are chosen by least squares, not by me. January to October 2026 is held out and used once, as a further test.

## Data

All fetched by `src/fetch.py` on 17 November 2026. `data/sources.csv` is the list of sources I verified by hand before building; `data/fetch_log.json` has the endpoint, filter, access date and row count of every call.

| Source | Content | Used for |
|---|---|---|
| Energy-Charts `/public_power?country=de`, series Load | quarter-hourly grid load, MW (Fraunhofer ISE; Bundesnetzagentur data, CC BY 4.0), one call per year | the dependent variable |
| Open-Meteo historical weather archive | daily mean 2 m temperature, one call per city and year (free for non-commercial use) | the regressor |
| Open-Meteo geocoding API (GeoNames) | coordinates and population of the six cities | the weights |
| Nager.Date `/PublicHolidays/{year}/DE` | nationwide public holidays | holiday control |
| DWD open data, daily station observations (TMK) | one station per city, ids resolved from DWD's station list | validation only |

Raw files (6 MB) go to `data/raw/`, which git ignores. `src/prepare.py` writes `data/daily.csv`: 2,861 Berlin-calendar days, 2019-01-01 to 2026-10-31, load in GWh (quarter-hourly MW times 0.25 h, summed; a 23- or 25-hour day sums the energy actually used), city temperatures, the weighted temperature, a holiday flag and the DWD temperature. No day lacks load or weather (`data/quality.json`); one day lacks a DWD value. 72 nationwide holidays. The tests and the analysis run from these committed tables.

## Method

load_d = year effect + weekday + holiday + 24 December to 1 January + b_h · HDD_d(Th) + b_c · CDD_d(Tc) + e_d, with HDD = max(Th - T, 0) and CDD = max(T - Tc, 0). Th runs over 10 to 20 C and Tc over 14 to 26 C with Tc not below Th. The pair with the smallest residual sum of squares is used, inside every bootstrap draw and every backtest window. The selected pair is Th = 16, Tc = 21; over bootstrap draws Th lies in [15, 18] and Tc in [20, 24].

The roadmap names weekday and holiday as the controls, so the base model has no seasonal term. I added annual harmonics at first, saw the heating slope fall to 5.8, and moved them to the sweep because they absorb the seasonal cycle of temperature itself. That decision was taken after seeing both results, so I give both the same prominence (Sensitivity).

## Interval

Block bootstrap over days: 2,000 draws, seed 16, blocks of 14 consecutive days, drawn from 2019 to 2025 only, which is the population the estimate belongs to (days of the fitted regime, not other countries or years). One draw of days refits the year effects, both slopes and both thresholds together and evaluates the warming scenario with that same fit, so the error they share is drawn once, never separately per quantity. `tests/` checks that the scenario column of every bootstrap row equals the scenario computed from that row's own coefficients. The interval measures sampling error given the specification; the specification range is in the sweep.

Heating interval width at block lengths 7, 14 and 28 days (400 draws): 2.1, 2.6 and 3.1 GWh per degree-day. With thresholds held fixed instead of re-selected: [13.9, 15.8].

## What the intervals support, and what they do not

- Heating's slope is positive on every interval in the sweep; its base interval [13.3, 15.9] is narrow.
- Cooling's interval [3.8, 17.8] excludes zero in the base fit, but the slope depends on where Tc sits: at Th = 12 and Tc = 18 it is -4.1 [-7.2, -1.3], at Th = 15 and Tc = 18 it is +0.8 [-1.8, 3.2]. Cooling moves load by 0.08% of the annual total; I do not claim more than that it is small.
- The 1 C effect, -3.50 TWh [-3.76, -3.21], is a sampling interval given the specification. It is not a forecast interval: the largest annual-total backtest error (below) is 6.8 times as large.

## Backtest

The model is forward-looking only in the sense that one applies today's sensitivity to another year, so I tested exactly that. Fit on years before t, predict year t with its realised weather and the last training year's level. This tests the sensitivity, not weather forecasting.

| test year | RMSE GWh | MAPE | total error | calendar only (no temperature), RMSE | last year's same weekday, RMSE |
|---|---|---|---|---|---|
| 2022 | 87.3 | 5.7% | +3.7% | 126.2 | 108.7 |
| 2023 | 84.5 | 5.8% | +4.9% | 115.8 | 111.8 |
| 2024 | 57.5 | 3.4% | -1.5% | 101.6 | 76.9 |
| 2025 | 55.0 [47.0, 59.8] | 3.5% | +0.3% [-0.8, +1.5] | 111.6 | 72.1 |
| Jan to Oct 2026 | 60.5 [50.8, 69.3] | 3.7% | +0.1% | 123.8 | 70.7 |

Intervals are block bootstrap over the test year's days. The model beats both benchmarks in every year. In 2025 its gain over calendar-only is [42.0, 72.3] GWh of RMSE. The heating slope fitted on the growing window is stable: 13.6, 14.2, 14.1, 14.4 for the four test years.

The level is the weak point. In 2022 and 2023 the annual total is 3.7% and 4.9% too high, which is consistent with demand falling after the 2022 energy crisis while the model carries the earlier level forward; I did not test that cause. The 4.9% is 6.8 times the 0.73% a 1 C shift moves load. Models with annual harmonics beat the base model in 2023 to 2025 (2025 RMSE 49.3 with two harmonics) and lose in 2022 (92.5 against 87.3); the backtest does not choose between specifications.

## Validation

- Independent temperature source: DWD station observations in place of Open-Meteo, same load and method: heating 14.7 [13.5, 16.1] against 14.9, cooling 6.1 against 7.1, +1 C effect -3.54 TWh against -3.50. This checks the temperature input only.
- No second source of daily German load is in the verified list (ENTSO-E needs a token), so the load series is not checked. Energy-Charts load is grid load, which excludes most self-consumption.

## Sensitivity

The warming effect is negative in all 21 variants.

- **Seasonal control**: 1, 2 or 4 annual harmonics give heating 7.0, 5.8 and 6.5, weather at 0.78 to 1.00 TWh per 1 C instead of 3.50. This is the largest move, 9.1 GWh against at most 3.5 for anything else. The seasonal cycle of load and of temperature are collinear: harmonics remove winter-cold demand as well as lighting and calendar effects, and no regressor here separates the two. The true sensitivity sits between the two cases; I do not know where.
- **Thresholds**, six fixed pairs from (12, 18) to (18, 24): heating 13.4 to 18.4.
- **Sample**: 2020 dropped 14.7; 2022 and 2023 dropped 15.3; 2019 to 2024 14.4. **Year effects as a linear trend**: 14.8.
- **Temperature**: equal city weights 15.1; two- and three-day mean temperature 15.1 and 15.4; Berlin only 13.4; Frankfurt only 14.4.
- **Warming of 2 C**: -6.68 TWh [-7.19, -6.08], not twice 1 C exactly because days cross the thresholds.

Sweep rows use 400 bootstrap draws, so the base row's interval differs slightly from the headline's.

## Limits

The assumption that breaks the conclusion: that the winter-to-summer rise in load is caused by temperature. Daylight, school and holiday calendars and industrial shutdowns follow the same cycle, and with a seasonal control the heating slope is 5.8 to 7.0, not 14.9. The headline is the upper end of the supported range; the roadmap specification, which I kept, has no seasonal term.

A sceptical reviewer would also attack: six cities holding 9.2 million inhabitants, weighted by city population and not by load, so regions are over- or under-represented (the Frankfurt figure in GeoNames, 650,000, is a round number and probably old); nationwide holidays only, so regional holidays and bridge days sit in the error; the sensitivities are those of 2019 to 2025, and heat pumps and air conditioning are spreading, so a 1 C result is a snapshot with no claim for later years; the model is linear between thresholds, so very cold spells are not modelled separately; residuals are autocorrelated, which the 14-day blocks address and the 7 and 28-day results bracket.

## Run it

```bash
python3 src/fetch.py       # download -> data/raw/ (about 2 minutes)
python3 src/prepare.py     # raw -> data/daily.csv, data/cities.csv, data/quality.json
python3 src/loadtemp.py    # estimates, intervals, backtest, sweep -> results/ (about 5 minutes)
python3 tests/test_loadtemp.py
python3 src/deck.py        # six pages -> deck.pdf
```
