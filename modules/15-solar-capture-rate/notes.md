# Notes: what I tried, what I threw away, what I got wrong

**The API rate-limits.** Three probe calls in a row returned HTTP 429. The client therefore honours Retry-After, backs
off and pauses 1.5 seconds between calls; the full pull of 188 files takes roughly a quarter of an hour. Files already on
disk are skipped, so an interrupted run resumes, which I used: the first attempt outlasted my command timeout.

**One interval was not enough.** The roadmap specifies a week bootstrap. It gives [-6.6, -4.1] for the solar slope.
Fitting seven annual points by least squares gives [-9.9, -0.8]. The bootstrap resamples weeks inside each year, so it
never sees that seven years scatter around a line. I report both and quote the wider as the headline, and I added the
leave-one-year-out check. I stratified the bootstrap by calendar quarter because unstratified draws change the season mix of
a year, which is variation the estimand does not contain; the unstratified version is in the sweep and is wider.

**Price resolution.** Day-ahead prices become quarter-hourly on 1 October 2025. The roadmap says to average generation
to the hour and join prices. I kept everything on the quarter-hour grid instead, which equals the roadmap for the hourly era,
and ran the literal version as a sweep row (+0.13 points in 2025).

**The first validation was wrong.** I started from the TSOs' MW Solar(a) series, the only per-year published solar value on
the page. It differs from my solar-weighted price by 15% on average, up to 26%, mine lower in six of seven years, and I
found nothing on the page that defines its weighting. Reading the rest of the page I found the annual market
values (JW), which match my baseload price for 2025 to 0.01 EUR/MWh. That became the check. JW is shown for one year only; the
earlier years need a form post and I did not script it. MW Solar(a) stays in `data/` and in the deck as a gap I could not close.

**The backtest went against the method.** I expected the slope model to beat repeating last year. It does not: RMSE 0.25
against 0.15, and 0.17 against 0.15 without 2022. The first test year, 2022, is the worst (fit on three points, price
spike), so I added the result without it, after seeing the first one. I did not change the specification afterwards. The January to October 2026 window
was added before I looked at its result, as a further test the fit had never seen.

**The scenario headline.** I considered "capture rate at X% share in 2030". It needs a share forecast, which is a number I would
have typed, and the backtest interval is [-0.42, 0.98]. I kept a single +5 points scenario in the deck to show that the interval
is empty, and dropped the 2030 framing.

**Gas price control.** The obvious fix for the price regime is a regression with the gas price. It needs a source outside the
sources I had verified and has seven observations. I left it as the first thing to build next rather than fit it badly.

**Commit size.** The raw files are 47 MB. A quarter-hourly or hourly table is above 1 MB even as CSV. I commit weekly sums
instead: they are sufficient statistics for every ratio in the module, 79 KB, and the tests run from them. The cost is that the
quarter-hour data themselves are not in the repository and are rebuilt by `fetch.py`.

**Offshore wind.** The weekly table carries offshore columns I did not analyse. The roadmap fixes onshore as the comparator and I
kept to it.
