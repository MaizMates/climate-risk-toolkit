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
| 04 | [Emissions inventory](modules/04-emissions-inventory/) · [deck](modules/04-emissions-inventory/deck.pdf) | An illustrative 450-employee firm's 2024 inventory comes to 1,070 tCO2e location-based [950, 1,194] versus 1,491 tCO2e market-based [1,354, 1,630] — a 39% swing from the Scope 2 method alone, driven by Germany's near-fully-fossil residual mix. |
| 05 | [Portfolio climate risk](modules/05-portfolio-climate-risk/) · [deck](modules/05-portfolio-climate-risk/deck.pdf) | 15.3% of a real EUR 353mn Eurozone ETF sits in climate-policy-relevant sectors; its carbon-intensity proxy is 142 tCO2e/EUR mn value added [82, 245]; the sector-mapping choice moves it by 52%, and the reference year from 408 (2015) to 142 (2024). |
| 06 | [Flood depth to damage](modules/06-flood-depth-damage/) · [deck](modules/06-flood-depth-damage/deck.pdf) | 167 of Europe's largest gas and nuclear plants carry a capacity-weighted expected annual flood damage of 0.81% of asset value [0.14%, 1.67%]; only 7 sites are exposed at all, and resampling the portfolio moves the number ten times more than switching between published damage curves does. |
| 07 | [PACTA alignment, open](modules/07-pacta-alignment-open/) · [deck](modules/07-pacta-alignment-open/deck.pdf) | 22 listed European utilities hold 38.6% of their 220,459 MW in coal against a 2030 target of 2.3% under NGFS Net Zero 2050: a coal gap of 36.2% of capacity [24.4%, 48.3%]. It is a gap between the 2020 fleet and the target, not between plans and the target, and rescaling the register to Eurostat's coverage moves it to 21.6%. |
| 08 | [Scenario to PD](modules/08-scenario-pd-shift/) · [deck](modules/08-scenario-pd-shift/deck.pdf) | Through the carbon-cost channel, the one-year PD of EU industry in 2040 is 9.5% lower under NGFS Delayed transition than under Net Zero 2050 (2.25% against 2.49% from a 2% base; literature range [-14.2%, -5.5%]), because Delayed transition has the lower carbon price in every year to 2050. The sensitivity from a US equity study fails an out-of-sample test on European bankruptcies, rescaling gives -1.8% [-4.3%, +0.7%], and choosing Below 2°C as the orderly reference flips the sign to +9.3%. |
| 09 | [Financed emissions, PCAF](modules/09-financed-emissions-pcaf/) · [deck](modules/09-financed-emissions-pcaf/deck.pdf) | A simulated 100-loan book to real US corporates carries 10.12 Mt of financed Scope 1 emissions [9.24, 16.12] at a weighted data-quality score of 2.39. Scored as if no borrower reported (score 4.04) the same book estimates 13.61 Mt with a realised-error interval of [5.33, 21.41]; reported emissions are 10.27 Mt. The total says little without the score beside it. |
| 10 | [Disclosure quality index](modules/10-disclosure-quality-index/) · [deck](modules/10-disclosure-quality-index/deck.pdf) | Across 13 banks' Pillar 3 reports the ESG-template completeness index is 76.1% [65.0%, 83.6%]. Twelve banks publish all nine mandatory templates, so presence (96.6%) separates nothing; the cells do, from 44.5% to 99.2%. A blank cell leaves no text in a PDF, so the index is a lower bound on incompleteness. |
| 11 | [Hazard exposure, gridded](modules/11-hazard-exposure-gridded/) · [deck](modules/11-hazard-exposure-gridded/deck.pdf) | Joined to the 0.25 degree cell each plant sits in, 17.7% [13.1%, 22.5%] of 259,319 MW of thermal capacity in eleven countries is exposed to more than two extra days a year above a 35 C heat index by 2040-2059 (SSP2-4.5); joined to the country value, as module 03 does, the same plants give 42.9% [36.6%, 49.3%]. The gap, -25.2 points [-31.4, -19.4], is negative in every variant swept; the matching radius moves it by 14.8 points, the fuel definition by 8.3. |
| 12 | [Nature dependency, ENCORE](modules/12-nature-dependency-encore/) · [deck](modules/12-nature-dependency-encore/deck.pdf) | 25.4% [20.1%, 39.4%] of the EUR 348mn SPDR MSCI EMU ETF sits in companies with a High or Very High ENCORE dependency on at least one ecosystem service; water services lead. The rating cut-off moves it from 16.7% (Very High only) to 67.8% (Medium and above), and the 26.5% held in financials scores zero because ENCORE rates a bank's own processes, not its borrowers. |
| 13 | [Transition-plan NLP](modules/13-transition-plan-nlp/) · [deck](modules/13-transition-plan-nlp/deck.pdf) | Claude Haiku 4.5 agrees with the expert label on whether a climate paragraph states a commitment or action at precision 61.4% [51.7%, 70.3%] and recall 64.8% [54.9%, 74.1%] on 320 held-out paragraphs; a naive Bayes trained on 1,000 labelled paragraphs scores F1 66.1% against 63.0%. The prompt moves precision from 52.5% to 86.5% and F1 only from 60.0% to 65.8%, and precision falls to 28.5% when only one paragraph in ten is a commitment. |
| 14 | [Energy intensity, LMDI](modules/14-energy-intensity-lmdi/) · [deck](modules/14-energy-intensity-lmdi/deck.pdf) | EU27 final energy use of industry, services and agriculture fell 26.1 Mtoe between 2015 and 2024 (-6.7% [-10.7%, -1.3%]). Additive LMDI-I gives activity +60.4 Mtoe, structure -16.5 and intensity -70.0 [-112.3, -37.1], but 73% of the intensity effect falls in 2022 and 2023, the years the real energy price index jumped from 104 to 129, so it is not clean efficiency. |
| 15 | [Solar capture rate](modules/15-solar-capture-rate/) · [deck](modules/15-solar-capture-rate/deck.pdf) | Solar's capture rate in DE-LU fell from 92.8% in 2019 to 51.4% in 2025 as its share of load rose from 8.4% to 15.1%: -5.4 points per point of share [-9.9, -0.8]; onshore wind has no slope (+0.3 [-2.0, +2.5]). As a forecaster the slope fails: backtest RMSE 0.25 against 0.15 for repeating last year, and it predicted 0.32 for January to October 2026 where the rate was 0.53. |
| 16 | [Load and temperature](modules/16-load-temperature/) · [deck](modules/16-load-temperature/deck.pdf) | German daily electricity load rises 14.9 GWh per heating degree-day below 16 C [13.3, 15.9] and 7.1 [3.8, 17.8] per cooling degree-day above 21 C; weather is 7.0% of annual load [6.6%, 8.0%], and a year 1 C warmer uses 3.50 TWh less [3.21, 3.76]. Out of sample (fit 2019 to 2024, predict 2025) the daily error is 55.0 GWh against 111.6 without temperature; adding a seasonal control cuts the heating slope to 5.8 to 7.0, the largest move in the sweep. |
| 17 | [Monthly-annual coherence](modules/17-monthly-annual-coherence/) · [deck](modules/17-monthly-annual-coherence/deck.pdf) | 69.0% of 1,427 EU27 country-flow-years have a monthly electricity sum within 1% of Eurostat's annual figure [66.7%, 71.3%]; imports agree in 84.7%, exports in 87.9%, pumped storage in 55.2%, distribution losses in 6.7%. 31 country-flow pairs diverge persistently, 21 of them distribution losses: monthly distribution losses track the annual total-losses line, annual distribution losses do not, and no break flag marks it. Only 4 of the 31 are explained by a flag in the data. |
| 18 | [Power emissions nowcast](modules/18-power-emissions-nowcast/) · [deck](modules/18-power-emissions-nowcast/deck.pdf) | From nine months of data, EU27 power-sector emissions for 2026 are nowcast at 593 MtCO2e [564, 624], 4.0% above 2025; the interval comes from the method's measured errors on 2018 to 2025 (share-of-year RMSE 2.2% at nine months [1.7%, 2.6%], 6.1% at three, against 13.1% for repeating last year). A regression on generation by source does worse (3.0%) and is separable from the share rule at six months only; the nine-month interval contains 2025, the ten-month one does not. |
| 19 | [Transition exposure, banking](modules/19-transition-exposure-banking/) · [deck](modules/19-transition-exposure-banking/deck.pdf) | 60.8% [58.1%, 63.5%] of the EUR 6.2 trillion that 102 EU27 banks lend to non-financial corporations sits in climate-policy-relevant NACE sections (EBA transparency exercise, June 2025), but those sections do not yet perform worse: the NPL gap is -0.13 points [-0.44, +0.20]. The share runs from 12.1% to 74.9% across nine mappings and the gap changes sign with them; real estate alone is 25.2% of the book, and country shares from 52.1% (ES) to 77.9% (SE) separate only 6 of 21 country pairs. |

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
