# 14: Energy use fell. Was it efficiency?

**EU27 final energy consumption of industry, services and agriculture fell 26.1 Mtoe between 2015 and
2024 (-6.7%, 95% interval [-10.7%, -1.3%]). Activity added 60.4 Mtoe [39.9, 84.9], structure removed 16.5
[-27.7, -7.5] and intensity removed 70.0 [-112.3, -37.1], which is -18.1% of 2015 use [-20.7%, -15.1%].
Intensity is 81% of what offset activity growth [70%, 89%], but 73% of it falls in 2022 and 2023 [62%, 88%],
the two years in which the real energy price index rose from 104 to 129 and fell back to 121, so a fall in energy per
euro of value added is not the same thing as efficiency.**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

The change in EU27 final energy consumption of industry, services and agriculture between 2015 and the latest
year in the data (2024), in ktoe, split by additive LMDI-I into an activity effect (growth of total gross
value added), a structure effect (shifts of value added between the 81 sector-by-member-state cells) and
an intensity effect (change in energy per unit of value added inside a cell). The three effects sum to the
observed change exactly; `tests/` checks the identity on fixed inputs and on the real data.

Households and transport are outside the estimand: they have no value-added denominator.

## Data

All fetched by `src/fetch.py` from the Eurostat dissemination API, no key. The endpoint, filter, row count
and access date of every table are in `data/fetch_log.json`; `data/sources.csv` is the list of sources I
verified by hand before building.

| Table | Content | Used for |
|---|---|---|
| `nrg_bal_s` | final consumption by sector, KTOE, all fuels: `FC_IND_E`, `FC_OTH_CP_E`, `FC_OTH_AF_E` | energy, 27 states |
| `nama_10_a10` | gross value added, chain-linked volumes, 2015 prices | activity, structure |
| `nrg_chdd_a` | heating degree days | weather adjustment |
| `prc_hicp_aind` | HICP, energy and all items, EU27 | the price context of 2022 and 2023 |
| `nrg_ind_ei` | energy intensity of the economy, `EI_GDP_CLV15` | validation |

Raw downloads go to `data/raw/` (not committed); the tidy tables the analysis and the tests read are committed
in `data/`.

## Method

For each cell *i* (member state by sector), energy is `E = Q x S_i x I_i`, with `Q` total value added, `S_i`
the cell's share and `I_i` its energy per unit of value added. Additive LMDI-I weights each log ratio by the
logarithmic mean of the cell's energy in the two years, which leaves no residual. I compute the effects year by
year and sum them (chain). The direct 2015 to 2024 version is in the sweep: additive LMDI is path dependent,
and the two differ by 0.5 points of 2015 energy.

## Interval

Cluster bootstrap over member states, 2,000 draws, seed 14. A state is drawn with all three of its sectors,
and the EU27 total, activity and structure are recomputed on each draw, so a draw is a different EU, not the
same EU with noisy effects. `tests/` fails if the sectors of one state are resampled separately.

What this interval is: how much the headline depends on which states make up the EU. It is wide because
Germany alone carries a quarter of the intensity effect (without it: -51.7 Mtoe). What it is not: a measure of
error in Eurostat's figures. The decomposition itself is an accounting identity on a census of 27 states, and
I know of no public error estimate for the balances.

## What the intervals support, and what they do not

- The net fall, the activity rise, the structure effect and the intensity effect all exclude zero.
- Intensity exceeds activity growth in 76% of draws. The point estimates say it does (70.0 against 60.4);
  the interval does not settle it, and I do not rank the two.
- The timing matters more than the size: 2016 to 2019 intensity sums to -24.2 Mtoe against +34.6 of activity
  (consumption rose); the fall comes in 2022 and 2023.

## Nothing here is forward-looking

The decomposition accounts for a change that has already happened. It projects nothing, so there is no
backtest. The checks are the identity, the sweep, and Eurostat's own series.

## Validation

- Energy summed over member states equals the published EU27 total in every sector and year; value added
  differs by at most 0.75% (chain-linked volumes are not strictly additive).
- Final energy per unit of value added of the productive economy changes by -20.1% between 2015 and 2024.
  Eurostat's own energy intensity of the economy (`nrg_ind_ei`, gross available energy per unit of GDP, 2015
  prices) changes by -22.2%. The numerators and denominators differ, so this is a check of direction and order
  of magnitude. I found no public series that matches like for like.

## Sensitivity

The intensity effect, as % of base-year energy, is negative in all 19 variants, from -26.1% to -6.3%.

- **Sector mapping** (four alternatives): -20.0% to -18.3%.
- **Base year** (2010, 2013, 2018): -26.1% to -14.4%.
- **End year**: -6.3% to 2019, -17.9% to 2023; 2021 to 2024 alone gives -12.9%.
- **2020 in or out of the chain**: -18.1% either way.
- **Weather** (services energy restated at mean heating degree days, elasticity 0.17, standard error 0.10): -18.1% to -16.9%.
- **Granularity** moves structure, not intensity alone: +0.4% with one cell per state, -3.5% with EU27 aggregates
  by sector, -4.3% with both dimensions.

## Limits

The assumption that breaks the conclusion: that a fall in energy per unit of value added is efficiency. It is an
accounting residual. Fuel switching, price-driven curtailment, and lower output of energy-intensive products
inside a sector all land in it. 73% of it sits in 2022 and 2023, which is consistent with curtailment, and
nothing in this module can separate the cases. Moving from one cell per state to three sectors shifted 4.6
points from intensity to structure; finer industry detail may shift more, and I have not tested it.

A sceptical reviewer would also attack: value added is a volume index, so price effects are not modelled; the
services cell includes trade and transport-related activity whose energy is partly in the transport balance
(the sector-mapping sweep tests this and moves the result by under two points); the interval covers the choice
of states and not revisions to Eurostat's figures.

## Run it

```bash
python3 src/fetch.py           # download -> data/
python3 src/lmdi.py            # decomposition, interval, sweep -> results/
python3 tests/test_lmdi.py
python3 src/deck.py            # six pages -> deck.pdf
```
