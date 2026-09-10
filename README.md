# climate-risk-toolkit

Climate and financial risk, worked end to end on public data. I spent two years at the European
Central Bank in climate and nature risk supervision: the internal climate alignment methodology
for significant institutions, and the Pillar 3 ESG data quality assessment across 86 banks. That
work is all transition risk. This repository is where I build the parts I want to be stronger in,
starting with physical risk. No ECB internal data appears anywhere in it.

**What the one finished module found.** Ranking euro-area countries by the *level* of heat stress
in 2040–2059 gives a different order than ranking them by the *change* from the 1995–2014
baseline. Spain leads both. Portugal is 2nd by level (13.3 days per year above a 35 °C heat
index) but 3rd by change (+8.2 days); Greece is the reverse (10.6 days, +8.4). The gap is small
in absolute days and I have not inflated it. It is enough to show that level and gradient have to
be carried as two variables, not one, before any exposure is laid over them.
→ [module 01](modules/01-heat-stress-gradient/) · [deck.pdf](modules/01-heat-stress-gradient/deck.pdf) (4 pages)

## What's here

| Path | What it is | State |
|---|---|---|
| [`modules/01-heat-stress-gradient/`](modules/01-heat-stress-gradient/) | Heat-stress gradient across 11 euro-area countries. World Bank CCKP, CMIP6 ensemble median, indicator `hd35`, 1995–2014 against 2040–2059 under SSP2-4.5 and SSP3-7.0. | Done: code, test, results, 4-page deck |
| [`modules/`](modules/) | The queue behind module 01, ordered by the gaps that actually block me: investor view, PCAF financed emissions, data engineering, energy statistics, nature, climate into PD and LGD. | Planned |
| [`tools/`](tools/) | `monitor.py`, the crawler that runs my job search: 56 employers in the ledger, 22 of them wired to a live ATS adapter, and it prints only what changed since the last run. Not climate work; it is what keeps the search cheap. | In use |

## How a module is built

One question per module. It runs end to end from a clean checkout, on data anyone can download
without an account. Every figure comes from code in that module, so no number is typed twice.
`tests/` holds at least one check that fails if the logic breaks. `notes.md` records the roads not
taken. `deck.pdf` is the four-page version for someone who will not read the code.

## Run module 01

```bash
cd modules/01-heat-stress-gradient
python3 tests/test_hazard.py    # two checks, no framework
python3 src/hazard.py           # queries the CCKP API, writes results/heat_gradient.json
python3 src/deck.py             # writes deck.pdf from that json
```

Python 3 and matplotlib. Nothing else.

I use AI assistants as a tool in this work, the same way I use a debugger or a profiler.
