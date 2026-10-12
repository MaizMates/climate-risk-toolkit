# 09 — Financed emissions with PCAF data-quality scores: the total and its score, together

**A simulated bank book of 100 loans to 100 real US corporates (USD 37,957 mn outstanding) carries
10.12 Mt of financed Scope 1 emissions, interval [9.24, 16.12] Mt, at a weighted data-quality score
of 2.39. The same book scored as if no borrower reported (weighted score 4.04) estimates 13.61 Mt,
and the interval taken from the realised error is [5.33, 21.41] Mt. Reported emissions for the
book total 10.27 Mt. The total on its own cannot say which of the two books it came from, which is
why it is published with the score.**

## Estimand

The Scope 1 financed emissions of a loan book to listed US corporates, in tCO2e, under the PCAF
business-loan attribution (outstanding amount divided by borrower equity plus debt), with the PCAF
data-quality score on every line and the aggregate reported together with the score distribution.
If I knew it exactly it would be the sum, over loans, of the share of each borrower's emissions the
bank finances.

## What is real and what is simulated

Real: every borrower, its emissions, its revenue, assets, equity, debt and sector. Simulated, and
labelled so on every page of the deck: the bank. Which 100 borrowers it lends to is a seeded random
draw from the 210 usable parents (seed 2026 for the headline). Each loan is 1% to 5% of the
borrower's debt, drawn uniformly. The data-quality score is assigned by a stated rule, not observed:
the largest 40% of the book by revenue are treated as reporting (score 2), the next 40% as estimated
from revenue (score 4), the rest from assets (score 5). No loan book of this kind is public, and I
did not type one. The simulation is what makes the test possible: reported emissions exist for every
borrower, so an estimate built as if they did not can be compared with them.

## Data, all fetched by code (accessed 12 October 2026)

- **Emissions.** EPA Greenhouse Gas Reporting Program, `data.epa.gov/efservice`, tables
  `pub_dim_facility` (facility, NAICS, parent companies with ownership percentages) and
  `pub_facts_sector_ghg_emission` (tCO2e by facility, gas and sector), filtered to one reporting
  year and to direct-emitter sectors (suppliers of fuels and gases excluded). 11,281 facilities in
  2023, 2,696.8 Mt. Each facility's emissions are split across its parents by the published
  ownership percentage.
- **Financials and sector.** SEC EDGAR, `data.sec.gov/api/xbrl/companyfacts` (revenue, total assets,
  equity, long-term and short-term debt from the 10-K for the fiscal year ending in the reporting
  year) and `data.sec.gov/submissions` (SIC code). No key; a User-Agent header only.
- **Join.** Exact normalised-name match of the GHGRP parent against the titles in
  `sec.gov/files/company_tickers.json`, kept only when the name maps to a single CIK. 257 parents
  match, 216 have the four financial fields in 2023, 210 are usable after dropping non-positive
  equity or debt. They hold 36.8% of reported US direct emissions in 2023. Every match is in
  `results/borrowers.csv`; every dropped parent and the reason is counted in `results/fetch_log.json`.

`src/fetch.py` takes about ten minutes, almost all of it EDGAR.

## Method

For a book line, attribution factor = outstanding / (equity + debt), financed emissions = factor x
borrower emissions. Equity and debt are book values because the roadmap's borrowers are treated as
loan customers (PCAF business loans); market capitalisation is not in either source.

- **Score 2**: the reported GHGRP figure. It is mandatory regulatory reporting checked
  electronically by EPA, not third-party verified, so I score it 2, not 1.
- **Score 4**: sector factor x revenue. **Score 5**: sector factor x total assets. Score 1 and 3
  need verified or physical-activity data that public sources do not give; they do not appear.
- **Sector factor**: the sector's total emissions over its total revenue (or assets), from
  borrowers that are *not in the book*. Sector is the SIC major group (two digits), pooled over all
  borrowers if fewer than five peers exist. The factor never sees the lines it is applied to.

The weighted data-quality score is the outstanding-weighted mean score, as PCAF defines it.

## Uncertainty

The estimate belongs to a given book, so the book is not resampled. Only the peers that set a
line's factor are. In each of 4,000 replicates, each sector's peer group is resampled once and that
draw sets the factor for every score 4 and 5 line in the sector, because they all share it. Each
line then draws its own firm-level departure from the sector average, independently, because a
firm's deviation is its own. Reported lines carry no uncertainty. The first interval, [9.24, 16.12],
is the 2.5th to 97.5th percentile of the book total.

That construction is itself tested. Across 300 random books (a different random 100 each time, the
factor fitted on the other 110), the interval covered the reported total in 97% of books at the
headline mix. At the all-estimated mix it covered 63.7%, and the truth was below the interval in
109 of 300. The estimates run high (median 1.24 times the reported total), and a peer resample
cannot see a bias that every peer shares. For that case I take the interval from the realised error,
estimate divided by the 97.5th and 2.5th percentiles of estimate over reported: [5.33, 21.41] Mt.
The 300 books overlap heavily, so these coverage rates are not 300 independent trials.

## Where the width comes from

Randomising only the score 4 lines gives a width of 4.75 Mt, only the score 5 lines 4.88 Mt, both
6.88 Mt. Score 5 lines are 20% of the lines and 2.6% of the money and widen the interval as much as
the score 4 tier, which holds 15% of the money. Five electric utilities hold 52% of the financed
emissions and are all reported lines, so the headline interval is narrow (half-width 34%) because
the book's largest emitters are scored 2. The all-estimated case has a half-width of 139%.

## Sensitivity

Median estimate over reported total, across 100 books per setting (`results/financed.json`):

| Choice | Settings | Median estimate / reported |
|---|---|---|
| Share of reported lines | 0%, 20%, 40%, 60%, 80% | 1.17, 0.94, 0.95, 0.98, 0.99 |
| Factor estimator | ratio of sums, median intensity | 0.95, 0.87 |
| Method for estimated lines | all revenue-based, all asset-based | 1.17, 1.10 |
| Reference year | 2021, 2022, 2023 | 0.93, 0.93, 0.95 |
| Book size | 50, 100, 150 loans | 0.93, 0.95, 0.95 |
| SIC level | 2, 3, 4 digits | 0.95, 0.95, 0.95 |
| Minimum peers | 3, 5, 10 | 0.94, 0.95, 0.95 |
| Loan size | 1-5%, 5-20% of debt | 0.95, 0.95 |

The share of reported lines moves the aggregate most (swing 0.23), then the factor estimator
(0.08) and the method for estimated lines (0.07). Sector granularity, loan size, year and book size
each move it by less than 0.02. The aggregate hides the line level: the share of estimated lines
within a factor of 2 of the reported figure stays between 26% and 32% in every setting.

## Validation

Estimates against reported emissions, 18,000 line estimates from the 300 books: score 4 median
1.83 times the reported figure, 28% of lines within a factor of 2, 78% within a factor of 10, 90%
range 0.18 to 46. Score 5: median 0.98, 34% within 2, 75% within 10, 90% range 0.04 to 26. This is
the module's validation against something the factors were not fitted on. It is not an independent
measurement of financed emissions; none exists for a simulated book, and the reference itself is
unverified.

## Limits

- **The numerator is US direct emissions, the denominator is the whole company.** For a
  multinational the GHGRP figure is the US facilities only, while equity and debt are global, so the
  attribution factor is not matched to the emissions it multiplies and reported Scope 1 here is a
  floor. It is a second candidate, next to the size effect below, for why the estimates run high:
  the reference may understate the large diversified firms the sector factors overstate, and this
  module cannot separate the two. Scope 2 and 3 are absent.
- **The score rule is an assumption.** That the large firms are the reporters decides how tight the
  headline looks; the 0% and 20% rows above show what happens when it fails.
- **Within a sector, intensity falls with size** (slope -0.32 on log revenue, correlation -0.25
  after removing sector means), which a sector average ignores. This is the first thing a sceptic
  should attack, and it is why the peer-resample interval fails at the all-estimated mix.
- **The book describes no real bank.** The USD figures follow from the random loan sizes.
- **Nothing in this module is forward-looking.** It is a snapshot of one reporting year. The
  held-out test is across borrowers, not across time, so the backtest requirement does not apply;
  the 2021 to 2023 sweep is a robustness check, not a forecast.

## Run it

```bash
python3 src/fetch.py          # EPA GHGRP + SEC EDGAR -> results/borrowers.csv, fetch_log.json (about 10 min)
python3 tests/test_financed.py
python3 tests/test_fetch.py
python3 src/financed.py       # book, intervals, calibration, sweeps -> results/financed.json
python3 src/deck.py           # six pages
```

[`notes.md`](notes.md) has what was tried and dropped: the Wikidata route, the sector label that
put Alphabet in solar power, and the interval that undercovered.
