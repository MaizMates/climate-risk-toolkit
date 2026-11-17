# Notes: what I tried, what I threw away, what I got wrong

**Seasonal harmonics: in, then out, and I saw the result first.** My first specification had two annual harmonics beside the
weekday and holiday terms. It gave a heating slope of 5.8 GWh per degree-day and weather at 2.3% of load. Without them the slope is
14.9 and weather 7.0%. The harmonics absorb the seasonal cycle of temperature itself, so the slope becomes the response to
deviations from a normal day-of-year temperature. The roadmap lists weekday and holiday effects only, so I removed them from the base
model. That choice came after I had seen both numbers, which is why the README gives both the same space and names the choice as the
assumption that breaks the conclusion. The backtest does not settle it: harmonics predict better in 2023 to 2025 and worse in 2022.
What would settle it is a daylight regressor and a source that separates lighting from heating load, neither of which I have.

**Thresholds by grid, not by eye.** I did not fix 15 and 18 degrees from convention. The grid runs 10 to 20 for heating and 14 to 26
for cooling, selected by least squares inside every bootstrap draw and backtest window. The bootstrap with thresholds held fixed gives
a narrower heating interval ([13.9, 15.8] against [13.3, 15.9]), so reselecting is the more honest of the two. The cost is a
slow bootstrap: the full run takes about five minutes.

**A bootstrap bug.** The block length was a default argument bound when the function was defined, so my loop over block lengths 7, 14
and 28 days produced three identical intervals. I noticed the identical widths, made the length read at call time, and reran. The
reported widths (2.1, 2.6, 3.1) are from the fixed code.

**Year effects and the backtest.** A year effect cannot be estimated for a year the model has not seen. I carry the last training year's
level forward. In 2022 and 2023 that overpredicts the total by 3.7% and 4.9%. I considered a linear trend instead; it gives the same
heating slope in the full sample (14.8) and I did not run it as a backtest predictor, so I cannot say if it forecasts the level better.

**Cooling.** I expected a clear cooling slope. In the base fit it is 7.1 GWh per degree-day with an interval that excludes zero, but
only 0.08% of annual load, and its sign flips when Tc is forced to 18 degrees with Th at 12. I report it as small and unstable and
do not build a result on it.

**Temperature source and weights.** My first idea for the population weights was Eurostat or Destatis tables. Destatis' database needs a
login and Eurostat's city tables use a different city definition, so I used the GeoNames population that the Open-Meteo geocoding API
returns. The Frankfurt value (650,000) is a round figure and probably old; the equal-weight sweep row moves the heating slope by 0.2.
DWD station data became the validation: it is a different instrument network, public, and the list of stations is in DWD's own file.
I picked the station for each city by name, one per city, and did not test others.

**Load validation I could not do.** A second source for daily German load would be ENTSO-E, which needs an API token I do not have, so
the load side has no independent check. The module says so.

**What the interval does not do.** The 1 C scenario interval, [-3.76, -3.21] TWh, looks tight next to the 0.78 to 1.00 TWh the
harmonic specifications give, and next to a level error of 3.7% to 4.9% in two backtest years. It is a sampling interval given a
specification. I kept it as the headline because the roadmap fixes the specification, and I put the range beside it.

**Commit size.** The raw files are 6 MB and git ignores them. The committed `data/daily.csv` (180 KB) is enough to rebuild every
number, bootstrap draw and sweep row; `fetch.py` and `prepare.py` rebuild it from the raw files.

**The deck was checked by rendering.** The first layout overlapped text with a chart on page 5 and ran a line off page 4. I moved both
and read the numbers back from `results/`. The deck asserts its own comparative claims (the model beats both benchmarks in every
test year; the warming effect is negative in every variant) and stops if they are false.
