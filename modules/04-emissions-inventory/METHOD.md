# Method note — 04, emissions inventory

## Boundary and base year

GHG Protocol Corporate Standard, **operational control**. Reporting year **2024**. The
organisation is illustrative: a mid-sized office-based financial-services firm with offices in
Frankfurt (200 employees), Paris (150) and Milan (100) — 450 employees total. It does not exist.
Every fact used about Germany, France or Italy is fetched from a public endpoint; every fact
about the firm itself is an assumption, labelled as one, in `results/emissions_inventory.json:
assumptions` (value, unit, range, rationale for each).

## Sources and vintages

| Input | Source | Vintage |
|---|---|---|
| Scope 1 gas, Scope 3 travel/WTT factors | UK DESNZ, GHG conversion factors, full set v1.1 | 2024 |
| Scope 2 location-based grid intensity | Eurostat `env_air_gge` (CRF 1.A.1.a) / `nrg_bal_c` (GEP) | 2024 |
| Scope 2 market-based factor | AIB European Residual Mixes, CO2 sheet | 2024 |
| Office energy activity | Eurostat `nrg_bal_c` (FC_OTH_CP_E) / `nama_10_a10_e` (employment) | 2024 |
| Commuting mode share | Eurostat `tran_hv_psmod` | 2024 |

All three source families carry 2024 data — `vintage_check` in the results file confirms no
mismatch, as a checked outcome rather than an assumed one.

## Method, line by line

For each city: national per-employee electricity and gas intensity (Eurostat commercial-services
energy ÷ Eurostat services employment) × the firm's assumed headcount = activity data, in kWh.
Activity × emission factor = tCO2e, one line per source per city, each carrying a data-quality
score (1–5, activity side only — every factor here is a directly published figure). Scope 2 is
reported twice, location-based and market-based, per the GHG Protocol's dual-reporting
requirement; they are not averaged or reconciled into one number.

Scope 3 is limited to the three categories this module can build from public, code-fetched data:
**Category 3** (WTT on Scope 1 gas; T&D losses on Scope 2 electricity, both derived from data
already fetched for Scope 1/2), **Category 6** (business travel, an assumed travel budget split
air/rail) and **Category 7** (commuting, an assumed distance and frequency split by Eurostat's
national modal share). The other twelve categories are excluded, each with a stated reason, in
`results/emissions_inventory.json:completeness` — Category 1 (purchased goods and services) is
the largest likely gap, excluded because no public spend-based emission-factor set is reachable
within this module's library stack (stdlib, numpy, pandas, matplotlib, openpyxl only).

## Assumptions

Ten assumptions drive the firm-specific side of this inventory: headcount per city, commute
distance and frequency, business-travel budget and its air/rail split, and the uncertainty
percentages applied to each activity/factor pair in the Monte Carlo. Every one carries a value, a
unit, a range and a one-line rationale — see `assumptions` in the results file. None is fetched,
because no public source describes a firm that does not exist; the module never disguises an
assumption as a fetched figure.

## Exclusions

Twelve of fifteen GHG Protocol Scope 3 categories are excluded. Nine are structurally not
applicable (a financial-services firm has no physical product to distribute, process, sell, or
retire — Categories 4, 9, 10, 11, 12; no franchise model — Category 14; no assets leased to
others — Category 13; the firm's only leased assets, its offices, are already in Scope 1/2 under
operational control — Category 8). Three are applicable but excluded for a stated data reason:
Category 1 (no reachable spend-based factor set), Category 2 (no capex data for an illustrative
firm), Category 5 (Eurostat publishes waste only at municipal aggregate level, not decomposable
to a commercial-services employee). Category 15 (investments/financed emissions) is excluded by
the roadmap and named as the reason module 05 exists.

## QA/QC, in code

- **Unit and dimension check**: every line asserts its activity unit matches its factor's
  denominator unit before multiplying (`assert_units`); a mismatch raises, it does not silently
  compute a wrong number.
- **Completeness**: all fifteen Scope 3 categories enumerated, each with an included/excluded
  flag and a reason.
- **Location vs market-based reconciliation**: both totals reported, with the delta and its
  cause named (Germany's residual mix), not averaged away.
- **Factor-vintage consistency**: checked, not assumed — see above.
- **Order-of-magnitude check**: Scope 1+2 location-based tCO2e per employee against a wide sanity
  bound [0.3, 6.0] tCO2e/employee/year, meant to catch a unit or scaling error rather than serve
  as a benchmark claim.

## Uncertainty

Every activity figure and every emission factor carries a stated ± percentage range (see
`assumptions`), propagated by Monte Carlo (5,000 uniform draws per line, independent across
lines) to a 95% interval on every scope total and the grand total, location- and market-based
separately. The three lines with the largest variance are reported explicitly, not just the
resulting interval width.

## No backtest

STANDARD.md requires backtesting anything forward-looking. This module contains no projection —
it is one historical reporting year built from data already realised. There is no held-out period
to test a forecast against, because the module makes no forecast.
