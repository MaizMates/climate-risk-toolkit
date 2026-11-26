# 19 — Where does transition risk sit in bank lending?

**60.8% [58.1%, 63.5%] of the EUR 6.2 trillion that 102 EU27 banks lend to non-financial corporations sits in climate-policy-relevant NACE sections (June 2025, EBA transparency exercise). Those sections do not yet perform worse: the non-performing ratio is 3.3% inside them and 3.4% outside, a gap of -0.13 points [-0.44, +0.20], and the interval contains zero.** Both numbers depend on the sector mapping more than on the banks: the share runs from 12.1% to 74.9% across nine mappings, and the gap changes sign with them.

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

The share of EU banks' loans and advances to non-financial corporations (gross carrying amount, FINREP F 06.01, by NACE section) that sits in climate-policy-relevant sections, pooled by the country of the reporting bank, at the June 2025 reference date of the latest EBA transparency exercise; and the gap in the non-performing ratio between those sections and the rest, in percentage points. If I knew them exactly I would know how much of each country's corporate lending sits in sectors whose economics climate policy changes, and whether those sectors already carry more bad loans. Countries and distributions only: no bank is named or ranked, and the committed extract carries a sequence number, not an LEI.

## Data

All fetched by `src/fetch.py`; the access date, endpoint and SHA-256 of each file are in `data/fetch_log.json`, the list of sources in `data/sources.csv`.

- EBA 2025 EU-wide transparency exercise, full database `tr_cre.csv` (the latest edition; the EBA page was checked and links 2025, not only the 2024 file in `sources.csv`), with metadata and dictionary. Sheet `NACE`: gross carrying amount and non-performing amount of loans and advances to non-financial corporations, by NACE section A to S, by bank, for four reference dates.
- EBA 2024 exercise, same files, for the June 2024 date.
- EBA Risk Assessment Report, December 2025, and Risk Dashboard Q2 2025 (PDFs, read with pypdf): the EBA's own aggregates, used only for validation.

The raw downloads (about 250 MB) go to `data/raw/`, which git ignores. `src/prepare.py` writes three small committed files from them: `nace_extract.csv`, `eba_published.csv`, `reconciliation.json`. The tests run on those.

## Method

1. **Mapping.** Battiston et al. (2017) climate-policy-relevant sectors, read at NACE section level as in module 05: A, B, C, D, F, H, L. Manufacturing (C) and real estate (L) are counted whole, because the exercise does not split them. This is coarse and it is the main limit. Eight other mappings are swept.
2. **Share and gap.** Pooled across a country's banks and weighted by loans. NPL ratio is non-performing over gross amount; the gap is the ratio inside minus the ratio outside. A second gap holds the country mix fixed: the loan-weighted mean of the country gaps.
3. **Interval.** Stratified bootstrap, 4,000 draws. Banks are resampled with replacement inside each country, and nothing else is resampled. Every statistic, mapping variant and section is read off the same draw, so differences between variants carry their own intervals. The interval says how much the pooled figure depends on which banks sit in the country's sample. The 102 banks are the exercise's population, not a random draw from it, so it is not a measurement error.
4. **Disclosure.** Countries with fewer than three banks are pooled into one group. Countries with three or four banks are reported and flagged thin, because a bootstrap over three banks is not reliable.

## Result

| | share | NPL inside | NPL outside | gap, points |
|---|---|---|---|---|
| EU27, 102 banks | 60.8% [58.1%, 63.5%] | 3.3% [3.0%, 3.6%] | 3.4% [3.1%, 3.7%] | -0.13 [-0.44, +0.20] |
| EU27, country mix held fixed | | | | +0.05 [-0.24, +0.39] |

- **Real estate is the largest section** at 25.2% of corporate lending, manufacturing next at 15.2%. Construction has the highest NPL ratio of all sections (6.5%) and utilities the lowest of the mapped ones (1.4%). Real estate (2.8%) sits below and manufacturing (3.8%) above the ratio outside the set, and they offset.
- **By country**, the seven countries with at least five banks run from 52.1% (ES) to 77.9% (SE). The intervals separate only 6 of 21 pairs: the ends are supported, the middle ordering is not. Denmark (81.1%, three banks) is higher but thin.
- **The gap by country**: the interval is above zero for DE (+1.57 points [+0.26, +3.06]), AT (+1.74 [+0.77, +2.56]) and IT (+0.45 [+0.13, +0.82]), and below zero for SE (-0.68 [-1.25, -0.14]). At 95% about 0.7 of 13 intervals would exclude zero by chance, so the sign pattern is the evidence, not any one country.
- **Concentration**: the five largest banks hold 30% of the loans; dropping any single bank moves the EU share by at most 0.75 points.

Full tables: `results/country.csv`, `section.csv`, `sweep_mapping.csv`, `sweep_date.json`, `validation_*.csv`, `summary.json`.

## Sensitivity

| mapping | share | gap, points |
|---|---|---|
| base (A, B, C, D, F, H, L) | 60.8% [58.1, 63.5] | -0.13 [-0.44, +0.20] |
| EU benchmark high-impact (A-H, L) | 74.9% [72.2, 77.3] | +0.34 [+0.00, +0.67] |
| B, C, D, H | 27.2% [23.9, 30.2] | -0.43 [-0.76, -0.08] |
| B, D, H | 12.1% [10.5, 13.7] | -1.51 [-1.79, -1.23] |
| base without L | 35.6% [31.8, 39.0] | +0.42 [+0.11, +0.74] |
| base without C | 45.6% [42.2, 49.1] | -0.43 [-0.85, -0.01] |
| base without F and L | 31.0% [27.2, 34.4] | -0.24 [-0.58, +0.12] |
| base without A | 57.0% [54.3, 60.0] | -0.27 [-0.58, +0.08] |
| base, K out of the denominator | 63.8% [61.4, 66.3] | -0.33 [-0.63, -0.01] |

- **The mapping is the dominant choice.** The share varies by 62.8 points across variants; the bank sample moves it by 2.7 points either side. The interval is above zero for the gap in 2 variants and below zero in 4, so its sign is not a finding.
- **Real estate drives the country ranking.** Rank correlation of country shares with the base is 0.88 to 0.98 in every variant that keeps real estate and -0.46 to -0.29 in every variant that drops it.
- **The date barely matters.** The share is 60.2% to 61.3% over five reporting dates (Sep 2024 to Jun 2025, plus Jun 2024 from the 2024 exercise). On the 100 banks present in both, it changed 0.00 points [-0.67, +0.55] between June 2024 and June 2025; the gap changed +0.15 [-0.12, +0.38].

## Validation

- **Reconciliation.** The NACE sheet sums to its own total and to the non-financial-corporation row of the NPE sheet, to rounding. The exercise's total NPL volume is EUR 372.4 bn against EUR 373 bn in the EBA's December 2025 Risk Assessment Report (p. 26), and its ratio with cash balances in the denominator, the EBA's definition, is 1.84% against 1.84%.
- **Against the EBA's published sector tables** (Risk Dashboard Q2 2025, EU/EEA row). From its section shares the base share is 61.3%; mine on the same sample is 61.0% [58.4%, 63.6%]. The gap is -0.14 against my -0.15 [-0.45, +0.17]. All 19 section shares and all 19 section NPL ratios fall inside my intervals (mean absolute differences 0.05 and 0.03 points). This validates the extraction, not the interval: the EBA table is built from nearly the same banks. By country, 12 of 13 EBA shares fall in my interval, mean absolute difference 1.0 points and worst 5.8 (BE); the EBA country rows include subsidiaries of foreign groups and mine count each bank once, in its own country.

## Why nothing is backtested

Nothing here is forward-looking. It is a snapshot of reported balance sheets. The stability of the share and the gap across five reporting dates and two exercises is the nearest thing to an out-of-sample check, and the NPL gap is said to be backward-looking in the limits.

## Limits

**A NACE section is not a unit of climate-policy exposure, and that assumption decides the result.** Section C holds steel and furniture; D holds coal plants and wind farms; L covers all real estate, whatever the building's energy performance. The share is 60.8% largely because C and L are counted whole, and 12.1% to 74.9% across the sets I tried. A reviewer should attack that first.

- Exposure is not risk: a loan in an exposed section may be collateralised, short, or to a firm already transitioning. The NPL gap is backward-looking; low defaults today say nothing about repricing after a carbon price.
- The sample is the large banks of each country, so a country figure is not the country's banking system. Rows for three or four banks are flagged thin.
- Loans to non-financial corporations only: no securities, off-balance-sheet items or household mortgages. Gross carrying amount, so collateral and provisions are not in it.
- Country is the reporting bank's domicile, not the borrower's.
- Several country intervals are read at once; one or two exclusions of zero are expected by chance.

## Run it

```bash
cd modules/19-transition-exposure-banking
python3 src/fetch.py        # about 250 MB into data/raw/ (git ignores it)
python3 src/prepare.py      # raw -> the small committed tables in data/
python3 src/exposure.py     # estimates, intervals, sweeps, validation -> results/
python3 tests/test_exposure.py
python3 src/deck.py         # six pages -> deck.pdf
```

Python 3 with numpy, pandas, matplotlib, openpyxl and pypdf.
