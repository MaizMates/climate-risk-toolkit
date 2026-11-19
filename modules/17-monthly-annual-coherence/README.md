# 17: How do you know a dataset is fit for use before you build on it?

**For EU27 member states, 2008 to 2025, 69.0% of 1,427 country-flow-years have a monthly sum within 1% of the annual figure in Eurostat's electricity statistics (95% interval [66.7%, 71.3%] resampling country-years, [63.3%, 74.7%] resampling whole countries). The pooled number hides the result: imports agree in 84.7% of country-years and exports in 87.9%, pumped storage in 55.2%, distribution losses in 6.7% [3.1%, 10.6%]. 31 country-flow pairs diverge persistently, interval [25, 33]; 21 are distribution losses. Monthly distribution losses are close to the annual total losses line in every year (median ratio 0.96 to 1.00), while annual distribution losses are zero for at least half of countries in 2017 to 2021, 0.72 to 0.73 of total losses in 2022 to 2024, and 37% higher in 2025 than in 2024 (monthly: 1.5%), with no break flag. Only 4 of the 31 persistent pairs are explained by a flag in the data; 15 show a pattern that no metadata page I could read documents; 12 are unexplained.**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

For each EU27 member state, flow and calendar year, the relative gap (sum of the twelve monthly figures from `nrg_cb_em` minus the annual figure from `nrg_cb_e`) divided by the annual figure, for the flows that exist in both datasets. Reported as the distribution of absolute gaps, the share within 1%, and the country-flow pairs that diverge persistently (at least half of at least five years outside 1%). If I knew it exactly, it would say how often one Eurostat table can be used to check the other, and where it cannot.

The flows are imports (`IMP`), exports (`EXP`), distribution losses (`DL`), each under the same code in both datasets, and pumped storage: monthly `TI_EHG_EPS` against the annual `TI_EHG_EPS_PURE` plus `TI_EHG_EPS_MIX`, because the annual table splits it by plant type. A pair needs all twelve months and an annual figure. A pair with both figures zero has no relative gap and is dropped (214 pairs); the sweep reports the share if they count as coherent.

## Data

All fetched by `src/fetch.py` on 19 November 2026. `data/sources.csv` is the list of sources I verified by hand before building; `data/fetch_log.json` has the endpoint, filter, access date, the dataset's own update timestamp and the counts of every call.

| Source | Content | Used for |
|---|---|---|
| Eurostat API `nrg_cb_em`, siec E7000, unit GWH | electricity supply, transformation and consumption, monthly, 7 flows, 2008-01 to 2026-09 | the monthly side |
| Eurostat API `nrg_cb_e`, siec E7000, unit GWH | the same, annual, 63 flows, 1990 to 2025 | the annual side |
| Eurostat API `nrg_cb_pem`, siec TOTAL, unit GWH | net electricity generation, monthly | the sweep only (against annual `NEP`) |
| Ember yearly electricity data (CC BY 4.0) | net imports by country | validation only |
| Eurostat metadata page `nrg_prd_esms` | questionnaires, rounding, revision policy | the quality notes |

Raw files (18 MB, mostly Ember) go to `data/raw/`, which git ignores. `src/prepare.py` writes `data/pairs.csv` (2,705 country-flow-years, 88 KB), `data/ember_netimports.csv` and `data/quality.json`. Of 2,994 monthly country-flow-years, 226 are dropped because fewer than twelve months exist (mostly 2026, a partial year). The tests and the analysis run from the committed tables.

## Method

gap = (monthly sum - annual) / annual. If the annual figure is zero, the gap is zero when the monthly sum is also zero and infinite otherwise; a NaN would drop out of every share silently. Headline: EU27, `IMP`, `EXP`, `DL`, `PS`, 2008 to 2025, tolerance 1%. The tolerance is inclusive.

A persistent pair has at least five years and at least half of them outside the tolerance. For each, `results/persistent.csv` records the same-sign share, the median gap in GWh, the share of divergent years carrying an Eurostat flag, and the share where one figure is zero. The cause is then assigned in a fixed order. **Documented**: at least half of the divergent observations carry an estimated, low-reliability, break or definition-differs flag. **Pattern, not documented**: the annual figure is zero while the monthly is not, the reverse, or (for `DL`) the monthly sum matches annual total losses (`LOSS`) within 1%. **Unexplained**: none of these. A provisional flag is not counted as a cause: the annual 2025 values carry it (141 of 143 country-flow-years in the pairs, all geographies), and 2025 agrees in 75.3% of country-years, inside the 56.7% to 75.7% range of the other years.

## Interval

2,000 draws, seed 17. The headline interval resamples country-years, the roadmap's unit, from the EU27 country-years of the window and no other population. A drawn country-year brings all its flows with it, so an error a country shares across flows is drawn once, never once per flow; `tests/` checks that every flow of a drawn country-year gets one multiplicity. Divergence persists inside a country, so years are not independent, and I added an interval that resamples whole countries. It is wider for the pooled share (11.4 points against 4.6), for imports, exports and pumped storage, and for the median and the 90th percentile; for distribution losses it is not (6.5 points against 7.5). It is the one I would quote for the pooled share. A second check in `tests/` builds a synthetic population where a country is either always or never coherent and requires the whole-country interval to be more than twice as wide.

The interval on the persistent count, [25, 33] against a point value of 31, is biased low: a draw can leave a pair with fewer than five years, and the mean of the draws is below 31. Read it as a lower band. The whole-country interval is [16, 26].

## What the intervals support, and what they do not

- Imports and exports separate from pumped storage and from distribution losses on both intervals' scale (the imports interval [81.4%, 88.0%] lies above the pumped storage interval [50.0%, 60.5%]); distribution losses are below all three.
- The whole-country intervals keep the same order: pumped storage [38.6%, 70.3%] lies below imports [76.8%, 90.9%], and distribution losses [3.7%, 10.2%] lie below pumped storage. Imports and exports [83.3%, 91.6%] cannot be told apart on either interval.
- The pooled 69.0% depends on the flow mix: it is a weighted average of four very different shares. The flows are the result.

## Backtest

Nothing in this module is forward-looking. It measures a property of two published tables as of one extraction date and projects nothing, so there is no out-of-sample test to run. The one thing a later extraction would change is the vintage: both tables are revised, and I fetched them once (the `updated` timestamps in `data/fetch_log.json`, 16 November 2026 for the monthly tables and 22 October 2026 for the annual one, are the vintage).

## Validation

- Ember's yearly net imports against Eurostat's `IMP` minus `EXP`, 182 country-years in 2019 to 2025: within 1% in 97.8% against the annual figure and 89.6% against the monthly sum, a difference of 8.2 points [3.8, 12.1]. At the median both are within 2.4 and 3.0 GWh. This is a weak check: Ember's figures sit within a few GWh of Eurostat's, which suggests it is built on them (I did not verify its methodology), so it is not independent, and net imports cancel part of the import and export gaps. It cannot adjudicate distribution losses or pumped storage.
- No second public source of annual distribution losses or pumped storage is in the verified list, and ENTSO-E needs a token I do not have. The two flows with the most divergence are the two with no external check.
- **Synthetic, method only.** Rounding every monthly figure to a whole GWh produces on its own a gap above 1% with probability 0.33 for an annual figure of 100 GWh, 0.002 at 300 GWh and 0 at 1,000 GWh (`results/rounding_synthetic.csv`, 20,000 draws, labelled synthetic in the file and nowhere used in a headline). Only 6.0% of the pairs are below 100 GWh, and those agree less (10.6% within 1%) than the larger ones (72.7%), so rounding does not drive the result.

## Sensitivity

Share within tolerance, base 69.0% [66.7, 71.3] (400 draws in the sweep, so the base interval differs slightly from the headline's).

- **Flow set, the largest move**: 6.7% (distribution losses only) to 87.9% (exports only). Imports, exports and pumped storage together: 77.9%. Adding net generation `NEP` from `nrg_cb_pem` against annual `NEP`: 61.8%; `NEP` alone 40.6% [35.6, 44.5], with 18 persistent pairs.
- **Tolerance** 0.1%, 0.5%, 2%, 5%, 10%: 55.2%, 64.1%, 73.2%, 78.2%, 81.8%. Persistent pairs: 46, 33, 29, 24, 23.
- **Window**: 2015 to 2025 67.7%; 2018 to 2025 65.8%; 2008 to 2024 68.6%; 2008 to 2019 71.5%; 2019 to 2025 65.1%. **Population**, all countries with data: 67.6%. **Size floor** 10, 100, 1,000 GWh: 71.8%, 72.7%, 76.1%. **Drop flagged observations**: 69.7%. **Both-zero pairs counted as coherent**: 73.1%.
- **Persistence rule** (share of years outside, minimum years): 75% and 5: 26 pairs; 100% and 5: 13; 50% and 3: 36; 50% and 8: 23; base 31.
- **Ranking of countries** by their share within 1%: rank correlation across the seven variants (tolerance, imports and exports only, window, size floor, adding `NEP`) falls to 0.41. Among the variants that do not change the flow set it is at least 0.83. The country ranking is a property of the flow set, so I do not rank countries.
- **Reading `DL` against annual `LOSS`**: the share within 1% on `DL` rises from 6.7% [3.4, 10.7] to 33.6% [25.7, 40.8]; 10 persistent pairs remain. It explains part of the gap and not most of it.

## Limits

The assumption that breaks the conclusion: that the annual figure is the benchmark. Eurostat's metadata says the monthly and annual data come from separate country questionnaires, so a gap shows that two submissions disagree, not which one is wrong. For distribution losses the monthly series is the stable one, and the annual series changes level in 2022 and again in 2025. A reader who treats the annual table as truth would conclude that the monthly table is unfit for losses, when the evidence points the other way for that flow.

A sceptical reviewer would also attack:

- **The flow mapping is mine.** Distribution losses against distribution losses is the pairing by identical code; the metadata I could read does not confirm that both mean the same, and the data say they do not. Pumped storage is a sum of two annual lines. I tried the monthly "available to internal market" against annual inland demand and final-consumption lines, and dropped it for lack of any statement that they are the same quantity.
- **The metadata I read is generic.** The electricity-specific monthly metadata page returned HTTP 404 (`nrg_cb_em_esms`); the API's own link goes to an oil page. I read the page for annual energy statistics (`nrg_prd_esms`). So "not documented" means not documented in what I could read, not that no documentation exists.
- **One vintage.** Part of the gap may be revision timing, which one extraction cannot separate.
- **Divergence is concentrated.** 21 of 31 persistent pairs are one flow, so the headline is mainly a statement about distribution losses and pumped storage; imports and exports are close to coherent.
- **Interval scope.** The 27 member states are the whole population, not a sample from a larger one. The intervals say how stable the share is to which country-years are present, not how it would move in another set of countries.

## Run it

```bash
python3 src/fetch.py       # download -> data/raw/ (about 1 minute, 18 MB)
python3 src/prepare.py     # raw -> data/pairs.csv, data/ember_netimports.csv, data/quality.json
python3 src/coherence.py   # shares, intervals, tracing, sweep, validation -> results/ (about 1 minute)
python3 tests/test_coherence.py
python3 src/deck.py        # six pages -> deck.pdf
```
