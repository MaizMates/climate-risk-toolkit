# 05 — Portfolio climate risk: a real ETF, no company-level data

**15.3% of the SPDR MSCI EMU UCITS ETF's EUR 353mn (215 holdings, as of 28 September 2026) sits
in climate-policy-relevant sectors. Its weighted average carbon intensity is 142 tCO2e per EUR
million of gross value added, interval [82, 245] from resampling each sector's intensity across
the member states the fund actually holds. The reference year moves that number more than anything
else in the module: from 408 in 2015 to 142 in 2024.**

## Estimand

For a real, fully disclosed Eurozone equity portfolio published without an account: (a) the share
of market value in climate-policy-relevant sectors (Battiston et al. 2017), and (b) the
portfolio's weighted average carbon intensity (WACI), in tCO2e per EUR million of gross value
added, with an interval that reflects proxy uncertainty.

## The fund, and why this one

**SPDR MSCI EMU UCITS ETF** (ISIN `IE00B910VR50`, ticker ZPRE GY), 216 large- and mid-cap Eurozone
equities tracking the MSCI EMU Index. Chosen over a global or US fund for one reason: this
module's two data sources — Eurostat's NACE-level emission accounts and module 01's hazard table —
both stop at the EU border, and a Eurozone-domiciled portfolio is the largest holding set that sits
entirely inside that coverage. It is also large enough (216 names, eleven GICS sectors, ten
countries of domicile) to be a real test of the join, not a toy case.

## Data, all fetched by code

- **Holdings.** SSGA's own daily holdings file for this fund,
  `ssga.com/library-content/.../holdings-daily-emea-en-zpre-gy.xlsx`, fetched by
  `src/portfolio_risk.py`, no key, no account, no transcription. ISIN, sector (MSCI GICS),
  country of domicile and market value per holding.
- **Emission intensity.** Eurostat `env_ac_ainah_r2` (air emissions accounts by NACE Rev.2,
  greenhouse gases, thousand tonnes) divided by Eurostat `nama_10_a64` (gross value added by NACE
  Rev.2, current prices), public dissemination API, no key, across all 27 EU member states, years
  2015–2024.
- **Climate-policy-relevant sector classification.** Battiston, Mandel, Monasterolo, Schuetze &
  Visentin (2017), *"A climate stress-test of the financial system"*, Nature Climate Change 7,
  283–288 — encoded as a category label per NACE code (`CPRS_CATEGORY` in `src/portfolio_risk.py`),
  not a number transcribed from the paper.
- **Physical risk overlay.** `modules/01-heat-stress-gradient/results/heat_gradient.json`, already
  in this repository, by country of domicile.
- **Validation.** State Street's own per-ISIN sustainability report (MSCI-sourced Weighted
  Average Carbon Intensity), fetched from `ssga.com` and read with a minimal stdlib PDF text
  extractor, because that figure is not published anywhere else machine-readable for this fund.

## Method

The holdings file carries an MSCI GICS sector label, not a NACE code. This is a coarse,
many-to-one join: one NACE Rev.2 code stands in for an entire GICS sector, chosen as the single
code that best represents where that sector's value actually sits in *this* portfolio (documented
sector by sector in `notes.md`, e.g. Information Technology → C26, computer & optical products,
because ASML alone is 9% of the fund). Every holding's country and mapped NACE code is joined to
that country's Eurostat intensity for the reference year (2024); where Eurostat does not report
that country/NACE cell — true for several manufacturing divisions in Germany and Spain, a real
statistical-disclosure-control gap, not a bug — the holding falls back to the cross-country
median, flagged in `results/portfolio_risk.json`. This is a sector-average proxy, PCAF data
quality score 5 on every line, and the deck says so on the first page.

## Uncertainty

Each holding is scored with its own country's intensity for its sector, which is the point
estimate. The interval asks how far that national-sector figure could be from the truth, using
the spread of the same sector's intensity across the member states this fund actually holds,
weighted by how much it holds in each, and expressed as a ratio to their weighted median. One
ratio is drawn per sector per resample and applied to every holding in that sector, because they
all share the same national-sector figure: if it is wrong, it is wrong for all of them. 2,000
resamples give [82, 245]. `notes.md` records the two earlier versions of this interval and why
both were wrong.

## Sensitivity

Sweeping the four sectors where this portfolio holds a real mix of sub-industries under one GICS
label moves WACI from 142 (base) to 216 (all four alternates) — a 52% swing from a labelling
choice, about half the width of the interval, and far less than the reference year. The mapping choice moves the
two headline numbers differently: reclassifying Consumer Discretionary from retail trade to
motor-vehicle manufacture barely moves WACI (142 vs 142) but moves the CPRS share from 15.3% to
22.9%, because "transportation" is a Battiston CPRS category and "retail trade" is not. Sweeping
the reference year 2015–2024 (all years Eurostat has) moves WACI from 408 to 142, monotonically —
realised EU decarbonisation and GVA growth, not a projection.

## Validation

State Street's own per-fund sustainability report discloses an MSCI Weighted Average Carbon
Intensity (Scope 1+2+3) of 1,014.5 tCO2e/$M Sales. This is not a like-for-like check: different
currency, a Sales denominator instead of gross value added, and MSCI's figure is over 90% Scope 3
— supply-chain emissions this module's NACE-level, production-based proxy has no analogue for at
all. Both point the same direction; neither confirms the other's number. Where no comparable
metric exists, `STANDARD.md` says to say so rather than force a comparison, and that is the
honest description of this one.

## Physical risk overlay

Weighting module 01's SSP2-4.5 mid-century heat-day change by market value gives a portfolio mean
of 2.32 days [1.50, 3.31], and 22.6% of covered value (Finland is not in module 01's table and is
excluded, 3.5% of the portfolio) sits in a country crossing the k=2 reference used in modules 01
and 03 — mostly Spain, Italy and Portugal.

## Limits

- **A national-sector average is a poor stand-in for exactly the holdings that matter most.**
  ASML, Siemens and SAP are each far from their sector's national average by construction — they
  are large enough to *set* that average, not sit near it. The proxy is most defensible for the
  Financials-heavy middle of the book and least defensible for its largest, most distinctive
  single names, which is the opposite of where a reader's attention goes. This is the assumption
  that would break the headline number if it were wrong.
- **The mapping is many-to-one by design.** One NACE code per GICS sector cannot separate a
  chemicals company from a mining company inside "Materials," or an airline from a machinery maker
  inside "Industrials." The sensitivity section shows it is worth 52% on WACI, the largest swing
  from any modelling choice here — it is the first thing a skeptical reviewer should attack.
- **No backtest.** Nothing in this module is forward-looking: the portfolio is a snapshot of
  today's holdings, the intensity is a realised national statistic, and the CPRS classification is
  a fixed taxonomy. The year sweep is a robustness check on which vintage to use, not a forecast,
  so `STANDARD.md`'s backtest requirement does not apply here.

## Run it

```bash
python3 src/portfolio_risk.py   # fetch holdings + Eurostat + module 01's hazard table -> results/
python3 tests/test_portfolio_risk.py
python3 src/deck.py             # six pages
```

[`notes.md`](notes.md) has what was tried and dropped: the bootstrap bug that recentred the
answer on the wrong distribution, the sector-by-sector reasoning behind every NACE choice, and why
the SSGA/MSCI figure could not be used as a strict validation.
