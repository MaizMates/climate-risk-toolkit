# 08 Scenario to PD: where a carbon price enters a credit model

**Through the carbon-cost channel, the one-year PD of the EU industry sector in 2040 is 9.5% lower
under NGFS Delayed transition than under Net Zero 2050 (REMIND, EU region): 2.25% against 2.49% from
a 2% baseline, a difference of 23.7 bp. The literature range for the sensitivity gives [-14.2%,
-5.5%]. The sign is negative because Delayed transition has the lower carbon price in every year
from 2025 to 2050, in all three models. The magnitude is not established: the sensitivity comes
from a US equity study and fails an out-of-sample test on European data. Rescaled by that test
the change is -1.8% [-4.3%, +0.7%].** Read the limits before quoting any of these.

## Estimand

The change in the one-year probability of default of the EU industry sector (NACE B-E, industry
except construction) in 2040 under the NGFS Delayed transition scenario (disorderly) relative to
Net Zero 2050 (orderly), through one stated channel: carbon price times CO2 intensity of value
added gives carbon cost as a share of value added; the part not passed on lowers the sector's
profit share; lower profitability raises the log-odds of default by a published sensitivity.
Sector structure is held at its 2022 level. Positive means the disorderly scenario carries the
higher PD. If I knew it exactly, it would be the PD difference a bank should see between the two
scenarios from this channel alone.

I fixed the pair, the year, the sector, the model and the pass-through before looking at results.
Delayed transition against Net Zero 2050 is the pair I read as disorderly against orderly. The
other five pairs are in the sweep, and they change the sign.

## Data

All fetched by `src/scenario_pd.py` on every run, access date 2026-10-08; nothing is typed. Each
Eurostat URL is in `results/scenario_pd.json`, key `meta.urls`.

- **Scenario.** NGFS Phase 5, IIASA Scenario Explorer anonymous API
  (`api.manager.ece.iiasa.ac.at/legacy/anonym/`, then `db1.ene.iiasa.ac.at/ngfs-phase-5-api/rest/v2.1`),
  default runs, variables `Price|Carbon` and `Emissions|CO2|Energy and Industrial Processes`,
  2020 to 2050 in five-year steps, seven scenarios, three models, one EU region each (REMIND `EU 28`,
  GCAM `EU-15`, MESSAGE `Western Europe`). 294 rows in `results/ngfs_eu_carbon.csv`. The bulk
  endpoint spells "Below 2°C" with a question mark, so rows are matched to the run list by run id.
- **Sector ratios.** Eurostat `nama_10_a64` (gross value added `B1G`, compensation of employees
  `D1`), `env_ac_ainah_r2` (CO2 and total greenhouse gases, tonnes), `nama_10_nfa_st` (net fixed
  assets at current replacement cost, `N11N`), by NACE A64 code, EU27. A sector is summed from its
  A64 codes and a country enters a year only if every series is present. Industry in 2022 has 26
  countries (Malta is missing); 2022 is the latest year with at least 26, a rule coded in
  `reference_year`. Profit share is 1 minus compensation over value added, so it includes mixed income
  and depreciation.
- **Prices in euro.** Eurostat `ert_bil_eur_a` (USD per EUR, 2010 average, 1.3257) and
  `prc_hicp_aind` (euro-area HICP) restate NGFS US$2010 in euro of 2022 (factor 1.254 on the
  euro price).
- **Sensitivity of default to profit.** Table 3 of Campbell, Hilscher and Szilagyi (2008), "In
  Search of Distress Risk", NBER w12362 (`nber.org/papers/w12362.pdf`). The PDF is downloaded and the
  `NIMTAAVG` row is parsed by code: logit coefficients on quarterly net income over market total
  assets of -29.67, -23.92, -20.26, -13.23 and -14.06 at lags of 0, 6, 12, 24 and 36 months, with
  z statistics. The parser raises if the row is not found.
- **Check on the mapping.** Eurostat `sts_rb_a`, bankruptcy declarations, index 2015=100, by
  country and NACE section. 1,176 country-sector-year changes, 2016 to 2023, 21 countries.
- **Assumptions that are not data.** Pass-through 0.7, from the 70% that Ganapati, Shapiro and
  Walker (2020, AEJ: Applied, NBER w22281) report for US manufacturing energy costs; I read their
  abstract and not the paper, and carbon is not energy. Baseline PD 2%: no public source gives
  sector PDs, so this is a parameter, and the relative change hardly depends on it.

## Method

Six steps, each one line, with the headline values (`deck.pdf` page 2 carries them):

| Step | Net Zero 2050 | Delayed transition |
|---|---|---|
| NGFS price 2040, REMIND EU, US$2010/t | 711 | 386 |
| Euro of 2022 per t | 673 | 365 |
| Carbon cost, share of value added (518 t CO2 per EUR mn) | 34.8% | 18.9% |
| Change in profit share, (1 - 0.7) of that; today 51.5% | -10.5 pp | -5.7 pp |
| Log-odds change: -20.26 x that x (GVA/assets 0.423) / 4 | +0.224 | +0.122 |
| PD from 2% | 2.49% | 2.25% |

The division by four is because the coefficient is on quarterly net income; the paper's own text
gives the median NIMTA as 0.6% per quarter. Net fixed assets stand in for total assets. The log-odds
slope of a monthly failure hazard is applied to a one-year PD, which is exact only for rare events.

Against today's PD the channel gives +24.5% under Net Zero 2050 and +12.6% under Delayed
transition. Every number is a function of the static structure: no abatement, no demand
response, no second-round effect.

## Uncertainty

The sensitivity is the weak link, so the interval is built on it. I draw one of the five reported
horizons uniformly, then a normal error from that horizon's standard error (coefficient over z).
The draw is one per replicate and shared by every sector, since it is one transferable sensitivity;
`tests/` checks that the ratio of two sectors' log-shifts is the same in every replicate. 4,000
replicates give **[-14.2%, -5.5%]**. The sampling error of the 12-month fit alone gives
[-10.5%, -8.5%], which is the interval one would quote if the US result transferred without error.
Nothing else is resampled: the sector's intensity and profit share are the EU27 population for
2022, not a sample. Pass-through, the model and the scenario pair are choices, not draws, and are
in the sweep.

A second interval uses my own fit on European data. I regress the one-year log change in
bankruptcy declarations on the one-year change in profit share (percentage points) with country
and sector-year effects, 1,176 observations. The slope is -0.0016 per point, 95% interval
[-0.0121, +0.0079] from 1,000 resamples of the 21 countries with replacement, one slope shared by
every sector. It includes zero. Through it the headline is -0.7% [-5.5%, +3.8%].

## Sensitivity

Each choice varied alone; headline -9.5%. Ranked by span of the PD change:

| Choice | Range | Span |
|---|---|---|
| pass-through, 0 to 1 | -28.1% to 0.0% | 28.1 pts |
| scenario pair (six) | -17.6% to +9.3% | 26.8 pts |
| industry abates with regional emissions | -9.5% to +2.1% | 11.6 pts |
| sensitivity source (CHS, EU panel in four specifications, CHS rescaled) | -9.5% to +0.1% | 9.6 pts |
| CHS horizon, 0 to 36 months | -13.6% to -6.3% | 7.3 pts |
| total assets 1 to 3 times net fixed assets | -9.5% to -3.3% | 6.2 pts |
| reference year of the ratios, 2015 to 2023 | -12.6% to -8.1% | 4.5 pts |
| IAM (REMIND, GCAM, MESSAGE) | -9.5% to -5.7% | 3.8 pts |
| year, 2030 to 2050 | -10.8% to -7.6% | 3.3 pts |
| leave one country out of the sector | -9.8% to -8.5% | 1.3 pts |
| CO2 or all greenhouse gases | -10.7% to -9.5% | 1.1 pts |
| baseline PD, 0.5% to 10% | -9.7% to -8.6% | 1.0 pts |

**The sign depends on the orderly reference, and the sign is the finding.** Delayed transition has a
lower carbon price than Net Zero 2050 in every year from 2025 to 2050 in REMIND, GCAM and MESSAGE. It
is above Below 2°C in REMIND and MESSAGE at 2040 and below it in GCAM. Against Below 2°C the
REMIND change is +9.3%, against Low demand +1.8%. If industry abates with the region, Net Zero
2050 has regional emissions of -95 Mt CO2 in 2040 against 3,325 in 2020, its bill is zero, and the
headline becomes +2.1%. The scenario pair moves the headline by 26.8 points; the elasticity choices
(source, horizon, asset scaling) by at most 9.6.

**Which sectors.** Transport has the higher intensity (580 against 518 t CO2 per EUR mn) and the
smaller shift (-6.6% against -9.5%), because it is more capital-heavy (GVA over fixed assets 0.256
against 0.423). Every other section has an intensity of 67 or less. Within industry the largest
shifts against today under Net Zero 2050 are coke and refined petroleum (+209%, 14 countries),
non-metallic minerals (+153%, 9) and basic metals (+149%, 9); the industry aggregate of +24.5% is an
average over a distribution that starts near zero. The ordering of the eight sections is stable
across reference years: the lowest rank correlation with the 2022 ordering is 0.95.

## Validation

Nothing independent measures a PD change under a scenario, so I test the mapping on years it did
not see. For each test year from 2019 to 2023 I fit the profit slope on earlier years only and
predict that year's sector-year-demeaned log change in bankruptcy declarations from the demeaned
change in profit share. 736 country-sector-years. Against a no-change forecast (RMSE 0.348) the
fitted slope has skill -0.009 and the CHS-implied slope -0.100: neither beats predicting nothing.
The calibration slope of realised on CHS-implied is **0.18 [-0.07, 0.44]**, so the mapping over-predicts
by a factor of about five and 1 is outside the interval. Excluding the moratorium years 2020 and 2021
it is 0.31 [-0.01, 0.71]. Rescaling the headline by the slope gives -1.8% [-4.3%, +0.7%]; by the
ex-moratorium slope, -3.1%.

Two reasons this does not refute the mapping. Bankruptcy declarations are legal events that depend
on insolvency regimes and moratoria; they are not PDs. And sector profit share from national
accounts measures firm profit with error, which pulls any slope toward zero. So the CHS range is
a plausible upper bound and the rescaled figure a plausible lower one.

Nothing in this module is a forecast by me. The forward-looking inputs are the NGFS paths, taken as
given. I did not check them against observed carbon prices.

## Limits

- **The mapping.** The headline rests on a sensitivity estimated on US listed firms from 1963 to
  2003 and applied to a European sector aggregate. On European bankruptcy data it carries no
  out-of-sample skill, and my own slope is indistinguishable from zero. If the true sensitivity is
  nearer the data than the paper, every PD change here shrinks by about 80% and the question of
  sign is no longer worth asking. This is the assumption that breaks the conclusion.
- **Static structure.** The bill is price times today's intensity. A 2040 price of EUR 673 on
  industry is 34.8% of value added, which no sector would carry unchanged. With abatement the sign
  of the headline reverses. Abatement cost and demand response are not modelled.
- **What is disorderly about the scenario is not here.** The channel reads the price level. The
  abruptness of a delayed transition acts through demand, asset values and funding costs.
- **Pass-through.** 0.7 is borrowed from US energy costs and moves the headline across 28 points.
  EU firms exposed to non-EU competitors may pass on less.
- **Regions and models.** One EU region per model; the three models differ by 3.8 points here.
- **Coverage.** Branch figures rest on 9 to 26 countries; K-N and P-S on 5 and 10.

## Run it

```bash
python3 src/scenario_pd.py   # fetch NGFS, Eurostat, the CHS paper -> results/ (about 40 seconds)
python3 tests/test_scenario_pd.py
python3 src/deck.py          # six pages
```

[`notes.md`](notes.md) has what was tried and dropped.
