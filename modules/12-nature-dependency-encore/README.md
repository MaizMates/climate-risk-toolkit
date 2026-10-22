# 12 — Nature dependency, ENCORE: a real fund against the ratings

**25.4% of the SPDR MSCI EMU UCITS ETF's EUR 348mn (213 scored holdings, as of 21 October 2026)
sits in companies whose activity carries a High or Very High ENCORE dependency rating on at least
one ecosystem service. Interval [20.1%, 39.4%], which includes uncertainty in my industry-to-ENCORE
crosswalk; [20.3%, 30.9%] if the crosswalk is taken as given. The rating cut-off moves the number
more than anything else: 16.7% if only Very High counts, 67.8% if Medium counts. The 26.5% of the
fund in financials scores zero, because ENCORE rates a bank's own production process and not its
borrowers.**

## Estimand

The share of the fund's market value held in companies whose activity has a High or Very High
ENCORE dependency rating on ecosystem service *s*, for each of the 25 services and for "at least
one". If I knew it exactly, it would be the fund's direct, equity-side dependency on nature at the
process level. It would still not be a loss estimate, and it would not include supply chains.

## Data, all fetched by `src/fetch.py`

- **ENCORE ratings and hierarchy.** `https://encorenature.org/en/ecosystem_services` and
  `/en/sectors`: the JSON that the public Explore tool at encorenature.org serves without a login.
  3,386 ratings (Very High, High, Medium, Low, Very Low) of 25 ecosystem services over 271
  production processes, grouped in ISIC-based sub-industries. ENCORE is published by the Natural
  Capital Finance Alliance, Global Canopy and UNEP-WCMC under CC BY-SA 4.0; credit goes to them.
- **Holdings.** State Street's daily holdings file for the fund (ISIN IE00B910VR50), with GICS
  industry and market value. The same fund as module 05.
- **Comparator.** The ECB blog of 8 June 2023 on bank loans and ecosystem-service dependency. Its
  two figures and its score threshold are read from the page text by code.

`data/sources.csv` lists each source; `results/fetch_log.json` has access date, size and SHA-256
of every file. Raw files go to `data/raw/` and are not committed.

## Method

1. Drop the rows labelled "Unassigned" (EUR 3.2mn, reported in the results, not scored).
2. Map each of the 54 GICS industries to one or more ENCORE sub-industries (`GICS_TO_ENCORE`, my
   labels; the sub-industry names are resolved against the fetched file by unique prefix, so a
   wrong name stops the run).
3. A company is one of its sub-industries' production processes with equal probability. It is
   dependent on a service if ENCORE rates that process High or Very High.
4. The fund share is the market-value-weighted expected share. The point estimate is exact, not
   simulated.

## Uncertainty

5,000 draws. Each holding draws one production process from its industry's set, independently of
other holdings, because a company's activity mix is its own. The crosswalk variant (narrow, base,
broad) is drawn once per industry and shared by every holding in it, because a wrong crosswalk is
wrong for all of them at once. The fund is not resampled: the estimand is this fund, not a
population it was drawn from. The two intervals in the headline are with and without the crosswalk
draw. Uncertainty in ENCORE's own ratings, which are expert judgement, has no distribution here;
the cut-off sweep is the only treatment of it.

## Sensitivity

Eighteen combinations: crosswalk (narrow, base, broad) x rating cut-off (Very High, High and above,
Medium and above) x process weighting (each process equal, or each sub-industry equal).

| Choice | Headline range | Swing |
|---|---|---|
| Rating cut-off | 16.7% to 67.8% | 51.1 points |
| Crosswalk variant | 25.4% to 29.6% | 4.2 points |
| Weighting rule | 25.4% to 25.5% | 0.07 points |

The ordering of the 25 services is steadier than the level: the rank correlation against the base
ordering is never below 0.74. Water flow regulation (11.1%), water supply (10.8%) and water
purification (9.6%) lead in the base case. 20 of 25 services have any exposure at the base cut-off.

## Validation

No independent measure of this fund's dependency exists. The ECB reports that nearly 75% of euro
area bank loans go to companies with a dependency score above 0.7 on at least one service, with
supply chains included. My 25.4% is far below that, and 67.8% at Medium and above is still below
it. The two differ in portfolio (loans against listed equity), in direct against indirect links
and in score scale, so the comparison is context. It is not a test of my number. I cannot tell
from the ECB page how its 0.7 maps onto ENCORE's five letter ratings.

## Limits

- **The assumption that would break the headline.** That ENCORE's direct, process-level rating is
  the company's dependency, and that a company is a draw from its GICS industry's processes. Banks
  and insurers are 26.5% of the fund and score zero; if they inherited the non-financial share of
  34.6%, the headline would rise by 9.2 points. The number is a floor on direct dependency.
- **The cut-off.** Expert-judgement letters turned into a yes or no. The 51-point swing is the
  first thing to attack.
- **Mapping resolution.** A GICS industry is coarser than an ENCORE process. The draw treats a
  company as one process; a diversified company is a mix. Revenue splits would replace the uniform draw.
- **Scope.** A Eurozone large-cap equity fund says nothing about SMEs, loans or other regions.
- **No backtest.** Nothing here is forward-looking. The fund is a snapshot, the ratings are a
  fixed knowledge base, so `STANDARD.md` point 4 does not apply.

## Run it

```bash
python3 src/fetch.py              # inputs -> data/raw/, results/fetch_log.json
python3 tests/test_encore.py
python3 src/encore.py             # -> results/nature_dependency.json, results/holdings_scored.csv
python3 src/deck.py               # five pages -> deck.pdf
```

[`notes.md`](notes.md) has what I tried and dropped.
