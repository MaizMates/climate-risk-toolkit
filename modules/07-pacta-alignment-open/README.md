# 07 — PACTA alignment on open data: the fleet gap of listed European utilities

**Under NGFS Net Zero 2050 (REMIND, EU28), 22 listed power utilities hold 38.6% of their 220,459 MW
in coal in 2020 against a 2030 target of 2.3%. The coal gap is +36.2% of the set's capacity,
interval [+24.4%, +48.3%] from resampling the utilities; coal, gas and oil together are +59.4%
[+47.5%, +69.9%].** This is a gap between the 2020 fleet and the target, not between company plans
and the target. Read the limits before quoting it.

## Estimand

For a set of listed power utilities, the production-weighted gap between the capacity they hold in
a technology in 2020 and the PACTA market-share-approach target for that technology in 2030, as a
share of the set's total capacity, by technology. Positive means the set holds more than the
target. Capacity in MW is the production metric, as in PACTA's power sector. If I knew it exactly,
it would be the share of the set's fleet that has to be retired, or added, to sit on the pathway.

## Data

All fetched by `src/pacta_alignment.py` on every run; nothing is typed.

- **Plants and owners.** WRI Global Power Plant Database, `output_database/global_power_plant_database.csv`
  from `raw.githubusercontent.com`. 9,519 plants in the EU27 and UK with a mapped technology,
  commissioned by 2020 or with no commissioning year (7,373 plants have none; the latest
  commissioning year in the register is 2018), 700,450 MW.
- **Scenario.** NGFS Phase 5, IIASA Scenario Explorer, anonymous API
  (`api.manager.ece.iiasa.ac.at/legacy/anonym/`, then `db1.ene.iiasa.ac.at/ngfs-phase-5-api/rest/v2.1`),
  variables `Capacity|Electricity|*`, default runs of REMIND-MAgPIE 3.3-4.8, GCAM 6.0 NGFS and
  MESSAGEix-GLOBIOM 2.0, years 2020 to 2035. The three models report different Europe regions
  (REMIND `EU 28`; GCAM `EU-15` plus `EU-12`; MESSAGE `Western Europe` plus `Eastern Europe`), each
  summed as published. The raw rows are in `results/ngfs_eu_capacity.csv`.
- **Listed status.** Wikidata: the group's entity found by name search, then a stock-exchange
  statement (P414) with no end date. The entity, label, description and exchanges per group are in
  `results/pacta_alignment.json`, key `listing`, so a wrong match can be seen.
- **Validation and backtest.** Eurostat `nrg_inf_epc`, net electrical capacity by fuel, EU27,
  2020 and 2024.

## Method

Each WRI owner string is split into owners, and each owner is mapped to a group by a name rule
(`ALIASES` in the source). The set is every group that Wikidata lists and that holds at least
2,000 MW. For each company and technology the target is the PACTA market-share approach as written
in the `r2dii.analysis` source (RMI): for increasing technologies (renewables, hydro, nuclear)
`P0_tech + P0_sector * (S_tech(t) - S_tech(0)) / S_sector(0)`, floored at zero; for decreasing ones
(coal, gas, oil) `P0_tech * S_tech(t) / S_tech(0)`. The set's gap in a technology is held MW minus
target MW, summed over companies, divided by the set's total MW.

Two allocation rules. Ownership splits a plant by stated percentages, the remainder equally.
Control gives the whole plant to the first-named owner, which is my proxy for the operator, since
WRI has none.

## What the number is made of

For the decreasing technologies the aggregate gap equals the held share times the scenario's
proportional fall: coal is 38.6% held times 93.9%. The scenario fixes the size of the demand and
the fleet fixes the mix. For the increasing technologies the aggregate gap is minus the scenario's
change over sector size whichever companies are in the set, so company data cannot move it. This
is how the market-share approach works, and `tests/test_pacta_alignment.py` has a case that fails
if it stops being true.

## Uncertainty

Resample the 22 utilities with replacement, 4,000 times, and recompute the set's gap. The
population the estimate belongs to is the set of utilities, so nothing else is resampled. The
scenario enters through the target array, which is the same for every company in a replicate: a
scenario error is one shared draw, not one per company. Conditional on REMIND Net Zero 2050 the
coal interval is [+24.4%, +48.3%]. A second interval draws one of the three models per replicate,
for all companies at once: coal [+21.9%, +46.1%], and renewables [-101.1%, -54.6%], which is the
only way that gap acquires any width.

The interval does not include the register's coverage error. Rescaling each technology's WRI
capacity to Eurostat's gives a coal gap of 21.6%, outside the interval, because that error is
shared by every company and resampling companies cannot see it.

## Sensitivity

Each choice varied alone, ranked by the span of the coal gap (headline 36.2%):

| Choice | Coal gap range | Span |
|---|---|---|
| scenario and IAM (12 pairs) | 13.3% to 36.2% | 22.9 pts |
| WRI coverage rescaled to Eurostat | 21.6% to 36.2% | 14.7 pts |
| horizon (2025, 2030, 2035) | 25.4% to 38.6% | 13.2 pts |
| IAM at Net Zero 2050 | 30.0% to 36.2% | 6.2 pts |
| scenario pace corrected by the 2020-24 backtest | 32.0% to 36.2% | 4.3 pts |
| listed groups vs all aliased groups | 33.6% to 36.2% | 2.7 pts |
| strict vs extended owner aliases | 36.2% to 38.1% | 1.9 pts |
| minimum fleet, 500 to 5,000 MW | 35.8% to 36.4% | 0.6 pts |
| allocation rule | 36.2% to 36.3% | 0.0 pts |
| direction rule (lookup vs scenario sign) | 36.2% | 0.0 pts |

The headline is the top of the scenario grid: Net Zero 2050 in REMIND is the most demanding
pathway here. Delayed Transition and Current Policies give identical gaps in every model.

**The allocation rule, the part practitioners argue about, moves nothing here.** 1.0% of
attributed MW (3,006 MW) changes owner between the two rules, and the rank correlation of company
coal shares is 0.999. WRI carries one owner string per plant and few joint ventures. That is a
property of this register, and it is no evidence that the rule is unimportant.

## Validation

WRI against Eurostat, EU27, 2020 (WRI MW / Eurostat MW): coal 1.33, gas 0.90, oil 1.11, nuclear
1.06, hydro 0.72, renewables 0.21. Renewables are badly under-covered, so the set's mix is tilted
to fossil. I did not test why coal is over-covered. The set holds 31% of the register's MW.

Backtest of the scenarios' first four years, Eurostat capacity 2024 over 2020 against each
scenario interpolated to 2024. The realised ratio lies inside the range of the 12 scenario-model
pairs for coal (0.72; 0.47 to 0.91), nuclear, hydro and renewables (1.67; 1.49 to 1.80). It lies
outside for gas (1.04; 0.73 to 1.00) and oil (0.88; 0.22 to 0.67). REMIND Net Zero 2050 had coal
at 0.47, faster than the 0.72 observed. Nothing in this module is forecast by me; the
forward-looking object is the scenario, and this tests its start. Carrying the realised pace
forward at a constant annual rate per technology moves the coal gap to 32.0%.

Nothing independent checks the listed status. It is Wikidata against itself.

## Limits

- **The fleet is held at its 2020 level.** If the utilities' announced retirements and build-out
  are what a plan-based PACTA run would use, every gap here shrinks and the company ranking may
  change. WRI has no plans, so this module cannot size that. The coal gap of 36.2% is a statement
  about required change, and a reader who takes it as misalignment of plans overstates it. This is
  the assumption that breaks the conclusion.
- **Coverage.** The share-of-capacity form depends on the register's technology mix. The MW held in
  coal does not depend on the other technologies' coverage.
- **Listing is as of today, owners as of the register's vintage.** EDF's Wikidata record shows
  Euronext Paris until 2023-05-18, so it is counted as unlisted.
- **Alias rules and regions are judgement.** The three models cover different Europe regions, and
  MESSAGE's is wider than the plant set. Eurostat hydro includes pumped storage; NGFS hydro may not.
- **22 companies.** Dropping any one moves the coal gap between 33.1% and 40.6%. The two largest
  hold 24.8% of the set's MW.

## Run it

```bash
python3 src/pacta_alignment.py   # fetch WRI, NGFS, Eurostat, Wikidata -> results/ (about three minutes, Wikidata is rate-limited)
python3 tests/test_pacta_alignment.py
python3 src/deck.py              # six pages
```

[`notes.md`](notes.md) has what was tried and dropped.
