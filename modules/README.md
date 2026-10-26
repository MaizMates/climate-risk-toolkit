# modules

- **[`ROADMAP.md`](ROADMAP.md)**: what gets built, in order, with the estimand and the data
  source named in advance.
- **[`STANDARD.md`](STANDARD.md)**: the bar each module has to clear.

| # | Module | The finding |
|---|---|---|
| 01 | [`01-heat-stress-gradient`](01-heat-stress-gradient/) | where heat stress grows fastest in the euro area, and that the ordering by growth is not the ordering by level |
| 02 | [`02-renewables-pace`](02-renewables-pace/) | 19 of 27 member states fall short of the 42.5% yardstick on their realised pace; the method's own five-year error is 5.5 points, so one country cannot be called either way |
| 03 | [`03-hazard-exposure-join`](03-hazard-exposure-join/) | 43.2% of thermal capacity in eleven countries is exposed at a two-day threshold, interval 36.9–49.5%, concentrated in ten plants |
| 04 | [`04-emissions-inventory`](04-emissions-inventory/) | an illustrative firm's Scope 2 method choice (location- vs market-based) swings the 2024 total by 39%, more than any other choice in the inventory |
| 05 | [`05-portfolio-climate-risk`](05-portfolio-climate-risk/) | 15.3% of a real Eurozone ETF sits in climate-policy-relevant sectors; carbon-intensity proxy 142 [82, 245]; the sector mapping moves it by 52%, the reference year by a factor of almost three |
| 06 | [`06-flood-depth-damage`](06-flood-depth-damage/) | expected annual flood damage across 167 large gas and nuclear plants is 0.81% of asset value [0.14%, 1.67%]; resampling the portfolio moves it ten times more than the damage-curve choice does |
| 07 | [`07-pacta-alignment-open`](07-pacta-alignment-open/) | 22 listed utilities hold 38.6% of their capacity in coal against a 2.3% target for 2030 (NGFS Net Zero 2050): gap 36.2% of capacity [24.4%, 48.3%]; the scenario and model choice moves it by 22.9 points, the register's coverage by 14.7, the allocation rule by none |
| 08 | [`08-scenario-pd-shift`](08-scenario-pd-shift/) | through the carbon-cost channel, EU industry PD in 2040 is 9.5% lower under NGFS Delayed transition than Net Zero 2050 (literature range [-14.2%, -5.5%]), because its carbon price is lower in every year to 2050; the sensitivity fails a European out-of-sample test, and the orderly reference moves the sign |
| 09 | [`09-financed-emissions-pcaf`](09-financed-emissions-pcaf/) | a simulated 100-loan book to real US corporates carries 10.12 Mt of financed Scope 1 emissions [9.24, 16.12] at score 2.39; with no reported data the same book estimates 13.61 Mt, realised-error interval [5.33, 21.41], against 10.27 Mt reported; the share of reported lines moves the aggregate most, sector granularity barely |
| 10 | [`10-disclosure-quality-index`](10-disclosure-quality-index/) | ESG-template completeness across 13 banks' Pillar 3 reports is 76.1% [65.0%, 83.6%]; presence is 96.6% and separates nothing, cell fill does; the ranking of banks moves with how cells are counted (rank correlation down to 0.78) |
| 11 | [`11-hazard-exposure-gridded`](11-hazard-exposure-gridded/) | on the 0.25 degree cell each plant sits in, 17.7% [13.1%, 22.5%] of 259,319 MW of thermal capacity is exposed at a two-day threshold, against 42.9% [36.6%, 49.3%] at country resolution; the gap is -25.2 points [-31.4, -19.4], negative in every variant, and the matching radius moves it by 14.8 points |
| 12 | [`12-nature-dependency-encore`](12-nature-dependency-encore/) | 25.4% [20.1%, 39.4%] of a real Eurozone equity ETF sits in companies highly dependent on at least one ecosystem service (ENCORE); the rating cut-off moves it by 51 points, the industry crosswalk by 4, and financials score zero because ENCORE rates their own processes, not their borrowers |
| 13 | [`13-transition-plan-nlp`](13-transition-plan-nlp/) | an LLM's yes/no extraction of climate commitments agrees with the expert label at precision 61.4% [51.7%, 70.3%], recall 64.8% [54.9%, 74.1%] (320 held-out paragraphs); a naive Bayes trained on 1,000 labelled paragraphs scores F1 66.1% against 63.0%, and the prompt moves precision from 52.5% to 86.5% but F1 only from 60.0% to 65.8% |
