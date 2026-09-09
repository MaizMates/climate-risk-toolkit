# climate-risk-toolkit

Working code from my own practice in climate and financial risk. I spent two years at the
European Central Bank in climate and nature risk supervision, designing the internal climate
alignment methodology for significant institutions and leading the Pillar 3 ESG data quality
assessment across 86 banks. That work is all transition risk. This repository is where I build
out the parts I want to be stronger in, starting with physical risk, using public data only.

Each module answers one question, runs end to end, and carries its own notes on what I tried and
what I abandoned. Every figure in a module comes from code in that module. Nothing here is
illustrative.

I use AI assistants as a tool in this work, the same way I use a debugger or a profiler.

## Layout

```
modules/            one question each, self-contained, runnable
  NN-name/
    README.md       the question, the data, the method, the result, the limits
    notes.md        decisions taken, roads not taken, what I would redo
    src/            code
    data/fetch.sh   downloads the public inputs, does not version them
    tests/          at minimum one check that fails if the logic breaks
    results/        figures and tables the code produced
    deck.pdf        four pages: question, method, results, limits
integrations/       projects that compose several modules
tools/              the job-market crawler that feeds my search (see tools/README.md)
```

## Data sources

NGFS scenarios, Copernicus and JRC hazard data, EDGAR emissions, EBA Pillar 3 disclosure
templates, and public registers. No ECB internal data appears anywhere in this repository.
