# 02 — Renewables: the pace, not the target

**7 of 27 member states reach the EU's 42.5% renewable share by 2030 at the pace they have
actually managed over the last five years.** Slovakia's share is falling. Italy is flat, at
+0.03 points a year against 4.40 required.

## Why I built it

A transition plan that assumes the national grid decarbonises on schedule is assuming something
the data may not support. The target is a statement of intent; the pace is observable. I wanted
the second number.

## What it does

Pulls the Eurostat renewable-share series live (`nrg_ind_ren`, balance REN, public dissemination
API, no key), measures each member state's average annual change over the five years ending at
its latest observation, carries that forward to 2030, and compares it with the pace that would be
required from today.

```bash
python3 src/renewables.py     # writes results/renewables_pace.json and prints the table
python3 tests/test_renewables.py
python3 src/deck.py           # four pages: question, method, result, limits
```

## The honest caveat, up front

42.5% is the **EU aggregate** target in RED III, not a national obligation. I use it as one
common ruler so the countries are comparable. National contributions under the NECPs differ and
are not in this dataset. Treating it as a national target would make the whole comparison a false
premise, so it is stated on the method page of the deck as well as here.

## Files

| Path | What it is |
|---|---|
| `src/renewables.py` | fetch, pace, projection, table |
| `src/deck.py` | the four-page PDF, every number read from `results/` |
| `tests/test_renewables.py` | the arithmetic, on a fixed series, including a falling share |
| `results/renewables_pace.json` | the output the deck is built from |
| `deck.pdf` | four pages |
