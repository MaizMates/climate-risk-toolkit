# 04 — Emissions inventory: an illustrative firm, a real GHG Protocol build

**For an illustrative 450-employee financial-services firm across Frankfurt, Paris and Milan,
2024 emissions are 1,070 tCO2e location-based [950, 1,194] or 1,491 tCO2e market-based
[1,354, 1,630] — a 39% swing from the Scope 2 method alone, driven almost entirely by Germany's
near-fully-fossil residual mix.**

## The organisation is illustrative and says so

It does not exist. Every fact used about Germany, France or Italy — emission factors, grid
intensity, office energy intensity, commuting mode share — is fetched from a public endpoint by
`src/emissions_inventory.py`. Every fact about the firm itself — headcount, commute distance,
business-travel budget — is an assumption, labelled as one, with a value, a range and a
rationale, in `results/emissions_inventory.json:assumptions`. Nothing here is affiliated with, or
draws on the work of, any employer; no ECB internal data appears anywhere in it.

## Estimand

Total greenhouse-gas emissions, in tCO2e, for reporting year 2024, by scope — Scope 1, Scope 2
location-based and market-based, and the Scope 3 categories material for an office-based
services firm — with a 95% interval from activity-data and emission-factor uncertainty.

## Data

- **Emission factors** (Scope 1 gas, Scope 3 travel/WTT): UK DESNZ, *Greenhouse gas reporting:
  conversion factors 2024*, full set v1.1, `assets.publishing.service.gov.uk`, fetched live.
- **Scope 2 location-based grid intensity**: Eurostat `env_air_gge` (GHG emissions, CRF sector
  1.A.1.a, public electricity and heat production) ÷ Eurostat `nrg_bal_c` (gross electricity
  production) — replicates the method EEA states for its own published indicator; EEA's own CSV
  endpoint returned HTTP 410 (Gone) when this build ran, so the ratio is computed here instead of
  transcribed from a chart that no longer serves data.
- **Scope 2 market-based**: AIB *European Residual Mixes 2024*, CO2 sheet, `aib-net.org`.
- **Office energy activity**: Eurostat `nrg_bal_c` (final consumption, commercial and public
  services) ÷ Eurostat `nama_10_a10_e` (services-sector employment), scaled by the firm's assumed
  headcount per city.
- **Commuting mode share**: Eurostat `tran_hv_psmod`, national modal split of passenger-km — the
  public proxy for "commuting patterns by country"; it is national passenger transport, not
  commuting specifically, and the limits section says so.

## Method

GHG Protocol Corporate Standard, operational control boundary. Activity × factor, line by line,
each line carrying a data-quality score. Scope 3 covers the three categories this module can
build from public, fetched data — Category 3 (fuel- and energy-related), 6 (business travel), 7
(commuting) — with the other twelve named and justified, included or excluded, in
`results/emissions_inventory.json:completeness`. Full detail in [`METHOD.md`](METHOD.md).

## Uncertainty

Every activity figure and factor carries a stated ± range, propagated by 5,000-draw Monte Carlo
to a 95% interval on every scope and the total, location- and market-based separately. The
largest variance contributors are Frankfurt's location-based electricity, Frankfurt's
market-based electricity, and Frankfurt's car commuting — Frankfurt carries the most employees
and the widest grid-intensity uncertainty of the three cities.

## Sensitivity

The Scope 2 method (location vs market-based) moves the total by 39% — more than any other
choice in this module. The calorific-value convention on the natural gas factor is a smaller but
real trap: applying the Gross CV factor to Eurostat's net-CV-basis activity data (the wrong
combination) understates Scope 1 by 10%. Headcount is a linear lever, as expected. Scope 3
categories 6 and 7 (business travel, commuting) are 41% of the location-based total — material,
and built on this module's least constrained assumptions.

## Validation

AIB publishes its own "production mix CO2" figure alongside the residual mix this module uses for
Scope 2 market-based — computed by Grexel on Ecoinvent data, independent of the Eurostat
CRF1A1A/GEP ratio this module fits for the location-based figure. Germany: 3% apart, close
agreement. Italy: 31% apart — CRF1A1A excludes autoproducer (industrial CHP) generation, material
in Italy, which this module's own limits section flags. France: both figures are near zero in
absolute terms (French generation is over 90% nuclear and hydro), so a small absolute gap between
two low numbers reads as a large percentage one.

## Limits

- **Every activity-data line is a national sector average scaled by an assumed headcount, not a
  metered bill.** If this firm's actual electricity or gas intensity per employee differs from
  the national commercial-services average by more than the stated uncertainty range, every
  downstream number moves with it. The Monte Carlo interval reflects the assumption's *stated*
  range, not a verified bound on how wrong the assumption could be — this is the assumption that
  would break the headline number if it were wrong.
- **Three of fifteen Scope 3 categories are built.** Category 1 (purchased goods and services) is
  the largest likely gap for a services firm and is excluded for a data reason, not a materiality
  judgement — see `METHOD.md`.
- **No backtest.** Nothing in this module is a projection; it is one historical reporting year.
  STANDARD.md's backtest requirement applies to forward-looking modules, and this is not one.

## Run it

```bash
python3 src/emissions_inventory.py   # fetch DESNZ + Eurostat + AIB, compute -> results/
python3 tests/test_emissions_inventory.py
python3 src/deck.py                  # six pages
```

[`notes.md`](notes.md) has what was tried and dropped: the EEA endpoint that returned HTTP 410,
why floor-area-per-employee became energy-per-employee, and why DESNZ's own overseas-electricity
sheet couldn't be used for validation.
