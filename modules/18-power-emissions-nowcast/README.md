# 18: What will this year's number be, and how wrong has this method been before?

**From the first nine months of 2026, my nowcast of EU27 power-sector emissions for the year is 593 MtCO2e, 95% interval [564, 624], 4.0% above 2025 (570). The interval comes from the method's own errors on the eight complete years 2018 to 2025, not from the fit: the share-of-year method missed by an RMS 2.2% at nine months (bootstrap over years [1.7%, 2.6%]), 3.8% [2.7%, 4.8%] at six and 6.1% [2.5%, 8.8%] at three, against 13.1% [6.8%, 19.1%] for repeating last year. The nine-month interval contains 2025, so nine months cannot separate a rise from no change; with October added, the nowcast is 596 [573, 621] and the interval excludes 2025. A regression on generation by source, the more elaborate benchmark, is worse at every horizon (3.0% at nine months), and it is separable from the share rule at six months only.**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

The calendar-year EU27 power-sector emissions (MtCO2e, Ember's "Total generation" series: all sources, Ember's lifecycle emission factors), estimated from the first 3, 6 and 9 months of monthly data, with the error of each estimate measured on every complete year from 2018 to 2025. If I knew it exactly, I could publish the year's number months before the year ends, and say how far off that kind of number has been. I also report the latest horizon the data allow for the current year (10 months, October 2026), labelled as an extra.

## Data

All fetched by `src/fetch.py` on 23 November 2026. `data/sources.csv` is the list of sources verified by hand before building; `data/fetch_log.json` has the endpoint, filter, access date and counts.

| Source | Content | Used for |
|---|---|---|
| Ember monthly electricity data, global long format (CC BY 4.0), `release_generation_monthly_global.csv`, no filter, 184,503 rows | generation (TWh) and emissions (MtCO2e) by source, month, area | the target and the predictors: Area "EU" (the 27 member states), January 2016 to October 2026 |
| Eurostat API `env_air_gge`, geo `EU27_2020`, airpol GHG, src_crf CRF1A1A, unit MIO_T (updated 2026-06-02) | annual greenhouse gas emissions of public electricity and heat production, 1990 to 2024 | validation only |

The raw files (29 MB, almost all Ember) go to `data/raw/`, which git ignores. `src/prepare.py` writes `data/eu_monthly.csv` (2,080 rows, 67 KB: EU aggregate, month by source), `data/members_sum.csv` and `data/crf_annual.csv`. The tests and the analysis run from the committed tables.

I use Ember's own EU aggregate, not a sum of member states: the member series start in 2015 or 2016 for most states and in 2018 for Luxembourg and Croatia, so a sum would not be complete before 2019 (check below). The aggregate covers January 2016 onward, so the first backtest year, 2018, has two years of history.

Ember's emissions are generation times a near-constant factor per source (coal 1.027 to 1.040 tCO2e per MWh, gas 0.473 to 0.495, most other sources constant to three decimals; `results/nowcast.json`). All the predictive information is in the generation mix and in the calendar.

## Method

For a year *y* and a horizon *m* (months of *y* observed), only complete years before *y* and months 1 to *m* of *y* enter. Three benchmarks, from the simplest up:

1. **Last year**: the previous calendar year's total.
2. **Share of year**: the year-to-date emissions divided by the mean share that months 1 to *m* took of the year in all earlier years.
3. **Regression**: year-to-date emissions plus a prediction for months *m*+1 to 12. Emissions of a month are regressed on generation by source (coal, gas, other fossil, bioenergy, hydro, nuclear, other renewables, solar, wind; least squares, no intercept) on the months of earlier years. A source's generation in a remaining month is last year's value for that month, scaled by this year's year-to-date over last year's.

Backtest: every year from 2018 to 2025 at every horizon, 96 nowcasts, error = nowcast over actual minus one (`results/backtest.csv`). History is the latest Ember vintage.

## Interval

For a method and horizon, the eight backtest errors give a root mean square *r* (it includes the bias, so a method that is biased is penalised). The 95% interval for the realised value is *N*/(1+*q*) to *N*/(1−*q*), *q* = *t*(0.975, 8 df)·*r*, the relative error being defined against the actual. It uses the backtest, not the in-sample fit.

The intervals on the RMSE resample the eight backtest years (4,000 draws, seed 18). One draw of years is applied to every method and horizon at once, because a year's shock is shared by all of them and the comparison between methods must stay paired; `tests/` checks that the years are drawn once. The population is the eight backtest years and nothing else.

**Does the interval hold?** A leave-one-year-out check builds each year's interval from the other seven errors and asks whether it holds the actual. Coverage over 96 cases: last year 88%, share of year 97%, regression 100%. The misses are last year in 2023 (nowcast 28% too high) and the share rule at three months in 2025. This is a coarse check at eight years per cell: it shows the interval is not far too narrow, no more.

## Backtest

| RMSE of the relative error, 95% interval over years | 3 months | 6 months | 9 months |
|---|---|---|---|
| Last year | 13.1% [6.8%, 19.1%] | 13.1% [6.8%, 19.1%] | 13.1% [6.8%, 19.1%] |
| Share of year | 6.1% [2.5%, 8.8%] | 3.8% [2.7%, 4.8%] | 2.2% [1.7%, 2.6%] |
| Regression | 7.0% [4.2%, 9.5%] | 5.5% [4.3%, 6.4%] | 3.0% [1.5%, 4.0%] |

- The share rule has the lowest point RMSE at every horizon. Its RMSE ratio to last year is 0.47 [0.24, 0.94] at three months and 0.17 [0.11, 0.32] at nine; the interval is below 1 at every horizon.
- The regression's ratio to the share rule is 1.14 [0.97, 1.93] at three months, 1.44 [1.005, 2.10] at six and 1.34 [0.75, 1.65] at nine. It is worse than the share rule with an interval that excludes 1 at six months only. Against last year the regression is separable at 6, 9 and 10 months, not at 3 (ratio 0.53 [0.35, 1.11]).
- Last year's worst year is 2023 (28.0% over: emissions fell 21.9% from 795 to 622). The share rule's worst year at three months is 2025 (11.7%): the first quarter of 2025 carried 30.7% of the year, the largest share in the ten years of data.
- **Selection check.** Picking the lowest-RMSE method on the other seven years and scoring it on the held-out year gives the in-sample best RMSE at every horizon: the share rule is picked every time.

## The 2026 nowcast

Year-to-date emissions for January to September are 430.0 MtCO2e; 2025 was 569.8.

| Method | 3 months | 6 months | 9 months | 10 months |
|---|---|---|---|---|
| Last year | 570 [437, 817] | 570 [437, 817] | 570 [437, 817] | 570 [437, 817] |
| Share of year | 618 [542, 721] | 596 [548, 653] | **593 [564, 624]** | 596 [573, 621] |
| Regression | 564 [486, 672] | 580 [515, 664] | 598 [560, 642] | 601 [571, 635] |

2025's value, 570, lies inside every share-of-year interval up to nine months and below the ten-month one. Fossil-only emissions (a different series, so a different level) give 529 [500, 561] at nine months (`results/sweep.csv`), 3.4% above 2025.

## Validation

- **Aggregate against its parts.** Ember's EU aggregate against the sum of the 27 member series, in the months where all 27 exist: largest monthly gap 0.43% for fossil emissions (58 months, from December 2021) and 0.41% for all generation (94 months, from December 2018); the sum is 0.3% lower on average. The aggregate is not an exact sum of what Ember publishes per country; the difference is far below the errors measured here.
- **Against an inventory that Ember does not build on.** Eurostat's annual line for public electricity and heat production (CRF 1.A.1.a), 2016 to 2024: Ember's fossil emissions are 99.3% of it on average, and the year-on-year changes correlate at 0.995 (n = 8; same sign in 7 of 8; RMS difference in the change 1.0 points). Ember's total (lifecycle) is 106.3% of it. The inventory includes heat and uses national rules, so it checks the movement, not the level; it ends in 2024, so it cannot check a 2025 or 2026 nowcast, and it is not a check of the nowcast at all.
- **Synthetic, method only.** `tests/` builds generation by source with known factors and checks that the regression returns them, that the share method is exact when the seasonal shape never changes, and that no nowcast reads anything after month *m* of the nowcast year. Nothing in `results/` comes from these inputs.

## Sensitivity

13 variants beyond the base (`results/sweep.csv`, `results/shares.csv`): history window (last 3 or 5 years), training years (drop 2020, drop 2020 and 2022), the share rule as a year-on-year ratio, the regression's sources (fossil only, fossil and clean groups) and projection (remaining months not scaled), the series (fossil emissions only) and the backtest years (2019 to 2025, without 2020, without 2020 and 2022, 2021 to 2025).

- **The ranking holds.** The share rule has a lower RMSE than the regression in 13 of 14 variants at three months, 13 at six and 14 at nine and ten. The one variant where the regression is ahead, at three and six months, is the share rule written as a year-on-year ratio (7.04% against 6.98% at three months, 5.50% against 5.47% at six); that form is the weaker version of the share rule at every horizon.
- **The level moves little.** The nine-month share-of-year nowcast runs from 592 to 598 across the variants that keep the series; the regression's from 590 to 610. The whole range sits inside the base interval [564, 624].
- **The error moves a little more.** The share rule's nine-month RMSE runs from 2.14% (backtest without 2020 and 2022) to 2.90% (year-on-year ratio form); the last-3-years window gives 2.60%.
- **The regression is the unstable method.** Its nine-month RMSE runs from 2.44% to 3.45%. Fitted on 2016 and 2017 (24 months, nine sources) it gives bioenergy a factor of −0.005 and wind 0.034, where Ember's own factors are 0.230 and 0.013: the sources move together, so the fit cannot separate them.

## Limits

**The assumption that breaks the conclusion: that the seasonal profile of 2016 to 2025 is the profile of 2026.** The share rule works because the first nine months cover a stable 70.6% to 74.5% of the year; if a shock lands in the last quarter (a cold December, a gas supply cut, a hydro shortfall), the nowcast misses by the size of that shock and the interval, built from eight years, knows only about the shocks of those eight years.

A sceptical reviewer would attack first:

- **Eight backtest years.** 2018 has two years of history and 2020 and 2022 are not ordinary years. An interval from eight errors is wide in its own uncertainty, which the t quantile only partly covers; the leave-one-year-out check cannot tell 88% from 97% coverage.
- **Vintage.** History and target are the latest Ember data. A forecaster sees recent months before revision, and I did not check how Ember treats its latest months. The backtest therefore understates the real-time error by an amount I cannot measure from one extraction.
- **The series is Ember's, not an inventory.** Lifecycle factors by source, applied to generation; not the ETS or the national inventory number. The regression recovers Ember's factors, not physical ones.
- **The regression is not shown to help.** I kept it because the method was fixed in advance; the data say a seasonal ratio does as well or better.
- **One series.** The EU27 total. I make no claim for a member state.

## Run it

```bash
python3 src/fetch.py       # download -> data/raw/ (about 30 MB)
python3 src/prepare.py     # raw -> data/eu_monthly.csv, data/members_sum.csv, data/crf_annual.csv
python3 src/nowcast.py     # backtest, intervals, sweep, validation -> results/ (under a minute)
python3 tests/test_nowcast.py
python3 src/deck.py        # six pages -> deck.pdf
```
