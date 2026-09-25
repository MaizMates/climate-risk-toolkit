# climate-risk-toolkit

Climate and financial risk, worked end to end on public data. I spent two years at the European
Central Bank in climate and nature risk supervision: the internal climate alignment methodology
for significant institutions, and the Pillar 3 ESG data quality assessment across 86 banks. That
work is all transition risk. This repository is where I build the parts I want to be stronger in,
starting with physical risk, carbon accounting and portfolio risk. It is an independent project
on public data: no ECB internal data appears anywhere in it, and nothing here is affiliated with
any employer.

## Modules

| # | Module | What it found |
|---|---|---|
| 01 | [Heat-stress gradient](modules/01-heat-stress-gradient/) · [deck](modules/01-heat-stress-gradient/deck.pdf) | Ranking euro-area countries by the *level* of projected heat stress gives a different order than ranking them by the *change*: Portugal is 2nd by level and 3rd by change, Greece the reverse. Level and gradient are two variables, not one. |
| 02 | [Renewables pace](modules/02-renewables-pace/) · [deck](modules/02-renewables-pace/deck.pdf) | On their realised five-year pace, 19 of 27 member states fall short of the 42.5% yardstick for 2030, 7 reach it, and 1 cannot be called, because the method's own out-of-sample error is 5.5 points. |
| 03 | [Hazard-exposure join](modules/03-hazard-exposure-join/) · [deck](modules/03-hazard-exposure-join/deck.pdf) | 43.2% of 260,626 MW of thermal capacity in eleven countries sits in countries where the yearly count of days above a 35 °C heat index rises by more than two by 2040–2059 under SSP2-4.5 (interval 36.9–49.5%), and ten plants hold 17.9% of it. |

What comes next, and why in that order, is in [`modules/ROADMAP.md`](modules/ROADMAP.md).

## How a module is built

One question per module, held to [`modules/STANDARD.md`](modules/STANDARD.md): the estimand
stated in one sentence, every input fetched by code from a public endpoint, an interval on every
headline number, an out-of-sample test for anything forward-looking, a sweep over the arbitrary
choices, and a limits section that names the assumption which would break the conclusion.
`tests/` holds checks that fail if the logic breaks, `notes.md` the roads not taken, and
`deck.pdf` the short version for someone who will not read the code.

Each module runs from a clean checkout with Python 3 and matplotlib:

```bash
cd modules/02-renewables-pace
python3 tests/test_renewables.py
python3 src/renewables.py
python3 src/deck.py
```

I use AI assistants as a tool in this work, the same way I use a debugger or a profiler. Every
result is produced by the code in the module and checked by its tests.
