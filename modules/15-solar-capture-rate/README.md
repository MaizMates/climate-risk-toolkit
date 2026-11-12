# 15: What is a megawatt-hour of solar worth?

**In Germany and Luxembourg (DE-LU) solar's capture rate, the generation-weighted day-ahead price it earns over the
baseload price, fell from 92.8% in 2019 to 51.4% in 2025 while its share of load rose from 8.4% to 15.1%. The slope is
-5.4 capture-rate points per point of share (95% interval [-9.9, -0.8] across the seven years, [-6.6, -4.1] when only
the weeks of each year are resampled). Onshore wind has no slope (+0.3 [-2.0, +2.5]). As a forecaster the solar
slope fails: fitted on earlier years it misses the next year by 0.25 in capture-rate units (RMSE), against 0.15 for
repeating last year's rate, and it predicted 0.32 for January to October 2026 where the realised value is 0.53.**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

The capture rate of solar in the DE-LU bidding zone, by calendar year 2019 to 2025: the generation-weighted average
day-ahead price solar earns, divided by the time-weighted baseload average price of the same year. Then the slope of
that rate against solar's share of load (annual solar feed-in over annual load, in per cent), by least squares
over the seven years, with onshore wind as the comparator. A rate of 50% means solar earns half of what a flat
profile would earn. 2026 is incomplete and is used once, as a further out-of-sample test.

## Data

All fetched by `src/fetch.py` from the Energy-Charts API (Fraunhofer ISE; data from Bundesnetzagentur SMARD.de,
CC BY 4.0), month by month, on 12 November 2026. `data/sources.csv` is the list of sources I verified by hand before
building; `data/fetch_log.json` has the endpoint, filter, access date and row count of every call.

| Source | Content | Used for |
|---|---|---|
| `/price?bzn=DE-LU` | day-ahead price, EUR/MWh; hourly to 30 Sep 2025, quarter-hourly after | the price |
| `/public_power?country=de` | quarter-hourly Solar, Wind onshore, Wind offshore, Load (MW) | generation and share of load |
| netztransparenz.de, market value overview | the TSOs' annual market values: JW (2025 only) and MW Solar(a) (2012 to 2025) | validation |

Raw JSON (47 MB) goes to `data/raw/`, which git ignores. `src/prepare.py` writes the tables that the analysis and the
tests read: `data/weekly.csv` holds the sufficient statistics of every 7-day block of every year (sums of price,
generation and generation times price, under each treatment), 79 KB, enough to rebuild every figure, bootstrap
draw and sweep row. 274,656 quarter-hours from 2019 to 31 October 2026, none missing, every one matched to a price.

## Method

Everything runs on the quarter-hour grid. An hourly price is held across its four quarter-hours; for the hourly
price era this equals the roadmap's method (generation averaged to the hour, joined to the price). Applying
the roadmap method literally changes 2025, the one year with a quarter-hourly price for three months, by +0.13
points. The calendar year is Berlin local time.

Capture rate = (sum of generation x price / sum of generation) / (mean price). The share of load uses the same
quarter-hours. "Generation" is the published feed-in, net of self-consumption; "load" is grid load.

## Interval

Two intervals, because they answer different questions and I report both.

- **Block bootstrap over weeks**, 2,000 draws, seed 15, 7-day blocks. Weeks are resampled inside each year and each
  calendar quarter, so the season mix of a year is fixed and only which weeks happened varies. One draw of weeks serves
  solar, wind, baseload price and load at once, so the error they share is drawn once; years are never mixed.
  `tests/` fails if a year borrows a week from another, if solar and wind see different draws, or if the
  stratification is lost. What it measures: how much each annual figure depends on which weeks occurred. What
  it does not see: the scatter of the seven years around the line.
- **Least squares over the seven years**, Student t with five degrees of freedom. This is the interval for the
  slope as a relation across years, and the one I quote as the headline.

A leave-one-year-out check agrees on the sign: slopes between -6.1 and -4.4 for solar, between -0.2 and +0.8 for wind.

## What the intervals support, and what they do not

- Solar's slope is below zero on both intervals; its least-squares upper end is -0.8 points, close to zero.
- Wind's slope is not distinguishable from zero.
- The solar slope is steeper than wind's: the difference is -5.6 points, bootstrap [-7.0, -4.0], leave-one-year-out
  [-9.8, -1.5].
- The annual rates are not monotone: 2022 (93.9% [88.5%, 100.2%]) is above 2019 (92.8% [88.9%, 96.6%]) and their intervals overlap. Gas-driven price levels in
  2022 are the likely reason; nothing here tests it.

## Backtest

The slope is forward-looking only if used to predict, so I tested it as a predictor. Slope fitted on years up to t-1
predicts the solar capture rate of year t at its realised share of load (the share itself is not forecast), for
t = 2022 to 2025, against last year's rate and the mean of the years so far.

| RMSE, capture-rate units | slope model | last year | mean so far |
|---|---|---|---|
| solar, 2022 to 2025 | 0.252 | 0.150 | 0.204 |
| solar, without 2022 | 0.166 | 0.149 | 0.228 |
| wind, 2022 to 2025 | 0.080 | 0.084 | 0.066 |

A fifth test uses January to October 2026 against the same window of earlier years: the share of load was 21.1% (17.5%
in the same months of 2025), the line predicted 0.32, last year's window gave 0.49, the realised rate is 0.53. The
capture rate stopped falling while the share kept rising. I did not tune anything after seeing these results.

The scenario in the deck, solar at 20.1% of load (2025's 15.1% plus five points, a value I chose), gives 0.28 on the
line and 0.37 log-linear. The backtest interval, RMSE x 2.776 on four errors, is [-0.42, 0.98]. It carries no
information, and it is a floor: observed shares stop at 15.1%.

## Validation

- The TSOs' published annual market values (JW) for 2025: baseload 89.32 EUR/MWh published, 89.32 mine; solar 45.08
  against 45.95 (+1.9%); onshore wind 74.41 against 77.27 (+3.8%). This checks the price base and the weighting, for one
  year. The page opens on the current year only; earlier years sit behind a form post I did not script.
- A series that does not match: the TSOs' MW Solar(a) (EEG 2012, section 33), which exists for every year. It differs from
  my solar-weighted price by 15% on average and by up to 26% (2025), mine lower in six of seven years, though levels
  correlate at 0.99. I could not establish its weighting from public pages, so I do not use it as a check. The page's
  CSV block and its prose disagree for 2025 (6.17 and 6.127 ct/kWh); `data/market_value_solar.csv` keeps both.
- Within a year, weekly capture rate on weekly share with year effects gives -1.8 points per point. It is a different,
  short-run relation (seasonality and weather), a third of the across-year slope, and I do not treat it as a check on its size.

## Sensitivity

The solar slope is negative in all 11 variants, from -6.0 to -5.1.

- **Negative prices floored at zero** (numerator and baseload both): -5.2. Hours at a negative price rise from 211 in 2019 to 575 in 2025;
  24% of 2025 solar output fell in them.
- **2022 dropped**: -5.5; 2021 and 2022 dropped: -6.0.
- **Start year 2020**: -5.1, and the least-squares interval then reaches +1.3.
- **Log-linear form** (slope at the mean rate): -5.9, interval upper end +0.1.
- **Resolution**: hourly mean generation times hourly mean price: -5.3.
- **Bootstrap block length** moves the interval, not the estimate: [-6.6, -4.1] with one-week blocks, [-7.4, -2.7] with
  four-week blocks, [-7.1, -3.0] unstratified.

The least-squares interval reaches zero or above in two of the 11 variants.

## Limits

The assumption that breaks the conclusion: that the share of load is what moves the capture rate. Seven annual points
span a baseload price of 30 EUR/MWh in 2020, 235 in 2022 and 89 in 2025, and the slope is not separated from the
price regime. Storage build-out, the rules on feed-in at negative prices and the move to quarter-hourly prices are
changes I did not measure and that fall in the same window. The backtest shows the cost: errors of both signs,
up to 0.41, and a line that predicts 2026 too low.

A sceptical reviewer would also attack: seven points; a capture rate is a ratio, so a gas-price shift cancels only if the
whole price curve moves in proportion; one bidding zone and day-ahead only, so intraday and balancing revenues, PPAs and
market-premium payoffs are outside the estimand; validation of the level for one year only.

## Run it

```bash
python3 src/fetch.py       # download -> data/raw/, data/*.csv (about 15 minutes: the API rate-limits)
python3 src/prepare.py     # raw -> data/weekly.csv, data/profile.csv
python3 src/capture.py     # estimates, intervals, backtest, sweep -> results/
python3 tests/test_capture.py
python3 src/deck.py        # six pages -> deck.pdf
```
