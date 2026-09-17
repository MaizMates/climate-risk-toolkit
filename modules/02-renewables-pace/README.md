# 02 — Renewables: the pace, not the target

**Of 27 member states, 19 fall short of the EU's 42.5% yardstick on their own
realised pace, 7 reach it, and for 1 the method cannot tell.** That last
category is the point: the procedure's own out-of-sample error is 5.5 percentage
points at a five-year horizon, and a verdict narrower than the method's error is false precision.

## Estimand

For each member state, the average annual change in the renewable share of gross final energy
consumption, in percentage points per year, estimated as the least-squares slope over the five
years ending at the latest observation, and projected to 2030.

## Why the estimator matters

The first version of this module used the difference between the first and last value of the
window. That is not a trend: it discards every observation in between and carries no uncertainty.
On Italy the two disagree materially — the endpoint method gives +0.03 points a year, the fitted
slope gives +0.38 with a standard error of 0.12. The
published headline was wrong, and `tests/test_renewables.py` now has a case that fails if anyone
reintroduces the endpoint method.

## Out-of-sample test

Fit as at 2020, predict five years forward, compare with the outcome.
n = 27, bias -0.09 points, RMSE 5.54, MAE 4.18, 90% of
errors within 9.08 points. The realised error sets the band on the 2030 projection
and therefore decides which countries get a verdict at all.

## Sensitivity

The five-year window is arbitrary. Across 3, 5, 7 and 10 years the country ordering holds
(Spearman +0.933 to
+1.000), but the projected levels move
by more than the gap between neighbouring countries. Use it for who, not for how much.

## The yardstick, stated plainly

42.5% is the **EU aggregate** target in RED III, not a national obligation. It is used as one
common ruler so member states are comparable. National contributions under the NECPs differ and
are not in this dataset.

## Run it

```bash
python3 src/renewables.py      # fetch, fit, backtest, sensitivity -> results/
python3 tests/test_renewables.py
python3 src/deck.py            # six pages
```
