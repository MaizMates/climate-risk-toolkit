# Module roadmap

Modules are built in this order, lowest number first. The order encodes which gap in my own
work each one closes, and the sequence is designed so each module reuses the previous one's
output. Every module meets `STANDARD.md`; one that cannot meet it is not published.

Every module is an independent project on public data. None of it is affiliated with, or
draws on the work of, any employer.

| # | Module | The gap it closes |
|---|---|---|
| 01 | `01-heat-stress-gradient` | **built** |
| 02 | `02-renewables-pace` | **built** |
| 03 | `03-hazard-exposure-join` | **built** |
| 04 | `04-emissions-inventory` | **built** |
| 05 | `05-portfolio-climate-risk` | **built** |
| 06 | `06-flood-depth-damage` | **built** |
| 07 | `07-pacta-alignment-open` | **built** |
| 08 | `08-scenario-pd-shift` | **built** |
| 09 | `09-financed-emissions-pcaf` | **built** |
| 10 | `10-disclosure-quality-index` | **built** |
| 11 | `11-hazard-exposure-gridded` | **built** |
| 12 | `12-nature-dependency-encore` | **built** |
| 13 | `13-transition-plan-nlp` | **built** |
| 14 | `14-energy-intensity-lmdi` | **built** |
| 15 | `15-solar-capture-rate` | **built** |
| 16 | `16-load-temperature` | **built** |
| 17 | `17-monthly-annual-coherence` | **built** |
| 18 | `18-power-emissions-nowcast` | nowcasting with a measured error |
| 19 | `19-transition-exposure-banking` | supervisory data: sector exposures from the EBA transparency exercise |
| 20 | `20-bidding-zone-price-convergence` | market coupling: how often neighbouring zones clear at one price |
| 21 | `21-carbon-cost-margin-stress` | credit: the carbon price that erases a sector's operating surplus |
| 22 | `22-residual-load-ramps` | system adequacy: the flexibility that wind and solar demand of the grid |

---

## 03 — `03-hazard-exposure-join`

**Scope narrowed on 21/09/2026, and the reason matters.** The original entry asked for plants
joined to hazard *grid cells*. The World Bank CCKP API returned HTTP 502 when I tried it,
and module 01's committed output is country-level, not gridded — so the gridded version cannot be
built from anything currently in hand. Rather than wait on someone else's outage or quietly swap
in a different hazard source, the estimand drops to the resolution the available data actually
supports, and says so.

**Estimand.** The share of each country's thermal generating capacity, in MW, that sits in
countries whose projected annual count of days above 35 °C rises by more than *k* days by
mid-century under SSP2-4.5 — that is, a capacity-weighted exposure measure at country resolution.

**Data, both real and both already proven reachable.**
- Plants: WRI Global Power Plant Database,
  `https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv`
  — fetched on 21/09, 34,936 rows, with capacity, fuel, country and coordinates.
- Hazard: `modules/01-heat-stress-gradient/results/heat_gradient.json`, already in this
  repository, country-level change in hot days. Module 03 consumes module 01's output rather than re-fetching it.

**Method.** Filter WRI to thermal fuels, aggregate capacity by country, join to the hazard table
by ISO3, and report exposed capacity share at several thresholds of *k*.

**Uncertainty.** Bootstrap over plants for an interval on the exposed share — the capacity
distribution is heavily skewed by a few large plants, and that skew is the point. Report how much
of the exposed total comes from the largest ten plants.

**Sensitivity.** Sweep *k*. Sweep the definition of "thermal" (with and without gas, with and
without biomass), because that choice moves the answer more than the threshold does.

**The limitation to state on the limits page, not bury.** Country resolution attributes a
national average to every plant in the country. For a large country this is close to
meaningless at the asset level, and the module must say which countries it is least defensible
for. The gridded version becomes module 11 when CCKP is back.

**The question it answers.** "Have you joined an asset register to a hazard layer, and do you know
what resolution costs you?"

## 04 — `04-emissions-inventory`

**Estimand.** Total greenhouse-gas emissions, in tCO2e, for one reporting year of an illustrative
organisation, by scope: Scope 1, Scope 2 both location-based and market-based, and the Scope 3
categories material for it, with a 95% interval from activity-data and emission-factor
uncertainty.

**The organisation is illustrative and says so.** A mid-sized, office-based financial services
firm with offices in three euro-area cities. Its activity data are built from public, aggregated
statistics (office energy intensity per square metre, floor area per employee, business travel
and commuting patterns by country) scaled by stated assumptions about the firm. Every assumption
lives in one file, with its value, unit, source or rationale, and a range; a figure attributed to
a source is fetched from it by code, and a figure that is an assumption is labelled as one.

**Emission factors, fetched.** A national government's published conversion factors (the UK
DESNZ greenhouse-gas conversion factors, the most complete public set), location-based grid
intensities for the three countries from a European public source (EEA or Eurostat), and the AIB
European residual mixes for market-based Scope 2. Record the vintage of each; mixing vintages is
a quality finding, not a detail.

**Method.** The GHG Protocol Corporate Standard: organisational boundary (operational control),
activity data times factor, line by line, with a data-quality score on every line.

**Quality checks, in code.** Unit and dimension checks; completeness against the fifteen Scope 3
categories, with every exclusion justified; location- against market-based reconciliation;
factor-vintage consistency; an order-of-magnitude check of intensity per employee against
published sector benchmarks.

**Uncertainty.** Propagate the ranges on activity data and factors by Monte Carlo and report the
interval on each scope and the total. Say which three lines drive it.

**Deliverables.** The inventory table, `METHOD.md` as a two-page methodological note (boundary,
base year, sources and vintages, assumptions, exclusions, QA/QC, uncertainty), and the deck.
Category 15, financed emissions, is excluded here and named as the reason for module 05.

**The question it answers.** "Walk me through a GHG inventory you built, and how you know it is
right."

## 05 — `05-portfolio-climate-risk`

**Estimand.** For a real portfolio whose full holdings are published without an account (a UCITS
equity ETF's holdings file, or a public pension fund's disclosed holdings; record the URL and the
as-of date): (a) the share of market value in climate-policy-relevant sectors, and (b) the
portfolio's weighted average carbon intensity, in tCO2e per EUR million of value added, with an
interval that reflects proxy uncertainty.

**Data, fetched.** The holdings file. Emission intensities by NACE sector from Eurostat's air
emissions accounts divided by Eurostat gross value added by the same NACE breakdown. The
climate-policy-relevant sector classification of Battiston et al. (2017), encoded as a mapping
with the citation; no numbers are transcribed. Module 01's country hazard table for a physical
risk overlay by country of domicile.

**Method.** Map each holding to a sector (the holdings file carries a sector label; the mapping
from it to NACE is coarse, and the module says how coarse), attach the sector intensity, weight
by market value. This is a sector-average proxy, PCAF data-quality score 5 on every line, and the
deck says so on the first page.

**Uncertainty.** Use the spread of the same sector's intensity across EU member states as the
proxy's distribution and resample it for an interval on the portfolio figure. Sweep the reference
year and the sector-mapping choices.

**Validation.** Compare against the fund's own published carbon metric where it discloses one.
Where it does not, say so.

**The question it answers.** "How would you assess the climate risk of a portfolio when you do
not have company-level data?"

## 06 — `06-flood-depth-damage`

**Estimand.** Expected annual damage, as a fraction of asset value, for a portfolio of locations,
under a published depth-damage function.

**Data.** JRC river flood hazard maps for Europe (return-period depth rasters, open), and the JRC
depth-damage curves for the EU.

**Method.** For each return period, read depth at the location, map depth to damage with the
published curve, integrate over the exceedance-probability curve to get expected annual damage.

**Uncertainty.** The curve choice dominates: repeat with at least two published curves and report
the spread. Say which drives the answer, the hazard or the curve.

**The question it answers.** "How does a hazard map become a number a risk manager can use?"

## 07 — `07-pacta-alignment-open`

**Estimand.** The production-weighted alignment gap between a set of listed power utilities and an
IEA scenario trajectory, by technology, at a stated horizon.

**Data.** Company production and capacity from public filings or an open asset-level source; IEA
or NGFS published sector pathways.

**Method.** The PACTA logic I built at the ECB, reproduced on public inputs so it can be shown.

**Uncertainty.** Sensitivity to the scenario chosen and to the allocation rule (ownership versus
operational control) — the allocation rule is the part practitioners argue about.

**The question it answers.** "You say you built an alignment methodology. Show me."

## 08 — `08-scenario-pd-shift`

**Estimand.** The change in a one-year probability of default for a sector under an NGFS
disorderly transition scenario relative to the orderly one, via a stated transmission channel.

**Data.** NGFS scenario variables (public download), and a public sector financial ratio source.

**Method.** A transparent, documented mapping from a scenario variable to a ratio to a PD. The
point is the auditability of each step, not sophistication.

**Uncertainty.** The elasticity is the weak link: report the range from the literature, cite it,
and show the PD range it implies.

**The question it answers.** "Where does climate actually enter a credit model?"

## 09 — `09-financed-emissions-pcaf`

**Estimand.** Financed emissions for a synthetic but realistic loan book, with the PCAF data
quality score attached to every line.

**Data.** Public company emissions, public sector intensity factors.

**Method.** PCAF attribution, then the score, then the aggregate with the score distribution.

**Uncertainty.** The headline number is nearly meaningless without the score distribution: show
both and say so.

## 10 — `10-disclosure-quality-index`

**Estimand.** A reproducible index of Pillar 3 ESG template completeness across a set of banks.

**Data.** Published Pillar 3 disclosures.

**Method.** The assessment I ran at the ECB, on public documents only, with the validation rules in code.

## 11 — `11-hazard-exposure-gridded`

The version of module 03 that was intended: WRI plant coordinates joined to CCKP hazard **grid
cells**, not country averages, with a stated matching radius and a sensitivity sweep over it.
Blocked on 21/09/2026 by a 502 from the CCKP API. Build it when the endpoint answers again; the
comparison against module 03's country-level numbers is itself the finding, because it measures
what the coarse resolution was costing.
## 12 — `12-nature-dependency-encore`

**Estimand.** The share of a portfolio's exposure in sectors with high dependency on a named
ecosystem service, using ENCORE ratings.

## 13 — `13-transition-plan-nlp`

**Estimand.** Agreement between an LLM extraction of stated transition-plan commitments and a
hand-coded sample, reported as precision and recall with an interval.

**Method.** This is the AI module and it must be evaluated, not demonstrated: no extraction
pipeline without a labelled test set and measured error.

**The question it answers.** "You say you use LLMs. How do you know the output is right?"

---

Modules 14 to 18 move from climate risk to energy statistics and power markets: the same
discipline (a fixed estimand, fetched inputs, an interval, a backtest) on the data an energy
agency or a market analyst works with. Module 19 returns to supervisory data.

## 14 — `14-energy-intensity-lmdi`

**Estimand.** The change in EU27 final energy consumption of the productive economy (industry,
services, agriculture) between 2015 and the latest year in the data, split into an activity
effect, a structure effect and an intensity effect, in ktoe, by additive LMDI-I. The three
effects sum to the observed change exactly; the module tests that identity.

**Data.** Eurostat simplified energy balances `nrg_bal_s` (final consumption by sector, KTOE)
and gross value added by industry `nama_10_a10` (chain-linked volumes, `CLV15_MEUR`), both from
the Eurostat dissemination API, for the EU27 and each member state.

**Method.** LMDI-I across sectors and member states, year by year and cumulated. The interval
comes from resampling member states; the sweep covers the base year, the sector mapping between
the energy balance and NACE, and whether 2020 is included. A cross-check against the intensity
figures Eurostat publishes itself.

**The question it answers.** "Energy use fell. Was that efficiency, or did the economy change
shape?"

## 15 — `15-solar-capture-rate`

**Estimand.** The capture rate of solar in the DE-LU bidding zone, by calendar year from 2019:
the generation-weighted average day-ahead price earned by solar divided by the baseload average
price. Then the slope of that rate against solar's share of load, with onshore wind as the
comparator.

**Data.** Energy-Charts API (Fraunhofer ISE, data from Bundesnetzagentur SMARD, CC BY 4.0):
`/price` for hourly day-ahead prices and `/public_power` for quarter-hourly generation and load.

**Method.** Quarter-hourly generation averaged to the hour and joined to prices. Intervals by
block bootstrap over weeks, because hours within a day are not independent. Backtest: the slope
fitted on years up to t-1 predicts the capture rate of year t. Sweep: negative-price hours kept
or floored, and the treatment of the 2022 price spike.

**The question it answers.** "What is a megawatt-hour of solar worth when everyone else's
panels produce in the same hours?"

## 16 — `16-load-temperature`

**Estimand.** The temperature sensitivity of German daily electricity load: GWh per degree-day
of heating and of cooling, net of weekday and holiday effects, on 2019 to the latest full year.

**Data.** Daily load from the Energy-Charts API (`/public_power`, series "Load"). Daily mean
temperature from the Open-Meteo historical weather API for six cities fixed in advance (Berlin,
Hamburg, Munich, Cologne, Frankfurt, Stuttgart), weighted by population.

**Method.** A piecewise-linear regression in heating and cooling degree-days with calendar
controls. The thresholds are swept, not chosen. Block bootstrap for the intervals. Backtest:
fit on all years but the last, predict the last, report the error. One applied result: the
change in annual load implied by a uniformly warmer year, stated with its interval and with the
limit that today's sensitivities need not hold as heat pumps and air conditioning spread.

**The question it answers.** "How much of electricity demand is weather, and how well can it be
predicted out of sample?"

## 17 — `17-monthly-annual-coherence`

**Estimand.** For each member state and year, the relative gap between the sum of Eurostat's
twelve monthly electricity figures (`nrg_cb_em`) and the annual figure for the same flow
(`nrg_cb_e`). Reported as the distribution of gaps, the share within one percent, and the
country-flow pairs that diverge persistently.

**Data.** Both datasets from the Eurostat dissemination API, on the flows and products that
exist in both.

**Method.** The coherence check a statistics office runs before publishing. Intervals by
resampling country-years. The sweep covers the tolerance and the set of flows. Each persistent
divergence is traced to a documented cause where the metadata gives one (provisional monthly
data, different coverage), and reported as unexplained where it does not.

**The question it answers.** "How do you know a dataset is fit for use before you build on it?"

## 18 — `18-power-emissions-nowcast`

**Estimand.** A nowcast of calendar-year EU27 power-sector emissions (MtCO2e) from the first
three, six and nine months of monthly data, with the error of each measured on every complete
year since 2018.

**Data.** Ember's monthly electricity data (generation and emissions by source, CC BY 4.0),
from Ember's public download.

**Method.** Three benchmarks, from the simplest up: last year's value, a seasonal
share-of-year ratio, and a regression on generation by source. Pseudo out-of-sample backtest,
year by year. The interval on the current-year nowcast comes from those backtest errors, not
from the in-sample fit.

**The question it answers.** "What will this year's number be, and how wrong has this method
been before?"

## 19 — `19-transition-exposure-banking`

**Estimand.** The share of EU banks' loans and advances to non-financial corporations that sits
in climate-policy-relevant NACE sections, aggregated by the country of the reporting bank, in
the latest EBA transparency exercise. Then the gap in the non-performing ratio between those
sections and the rest. Country aggregates and distributions only: no bank is ranked or named.

**Data.** EBA EU-wide transparency exercise, full database (`tr_cre.csv`) with its metadata and
data dictionary, from the EBA website.

**Method.** NACE sections mapped to climate-policy-relevant sectors at the resolution the data
allows, which is coarse and stated as the main limit. Intervals by resampling banks within a
country. The mapping is swept. Cross-check of the totals against the aggregates the EBA
publishes in the exercise's own report.

**The question it answers.** "Where does transition risk concentrate in bank lending, read
straight from supervisory disclosures?"

---

Modules 20 to 22 continue the alternation: power markets, credit, power system.

## 20 — `20-bidding-zone-price-convergence`

**Estimand.** For each border between DE-LU and a neighbouring bidding zone (FR, NL, AT, PL,
DK1, BE), the share of hours per calendar year, from 2019, in which the two day-ahead prices
are equal to within 0.01 EUR/MWh. Then the mean absolute price spread in the hours in which
they differ. A shared price means the interconnector was not binding; a spread means it was.

**Data.** Energy-Charts API (Fraunhofer ISE, data from Bundesnetzagentur SMARD, CC BY 4.0):
`/price?bzn=<zone>` for each zone, hourly until the day-ahead market moved to 15-minute
products in October 2025 and quarter-hourly after. The API rate-limits (HTTP 429), so the fetch
pauses between calls and retries, and caches raw responses in the repository.

**Method.** Align on a common time grid (quarter-hours averaged to the hour after the switch,
so every year is on the same unit). Intervals by block bootstrap over weeks, because congestion
persists across hours. Sweep: the equality tolerance (0.01, 0.1, 1 EUR/MWh), the treatment of
the 2022 price crisis, and hourly versus daily aggregation. No forward-looking claim, so no
backtest; the module says so rather than inventing one.

**Validation.** None from a second machine-readable source: the regulator's market monitoring
reports publish convergence figures, but not as an endpoint a script can fetch. The module
states this as a limit and does not transcribe them.

**The question it answers.** "How integrated is the European day-ahead market in practice, and
which borders bind?"

## 21 — `21-carbon-cost-margin-stress`

**Estimand.** For each NACE manufacturing and energy section in the EU27, the break-even carbon
price: the price in EUR per tCO2e at which the sector's gross greenhouse-gas bill, with no
pass-through, equals its gross operating surplus. Then the same figure for 2030 under the
sector's own trend in emission intensity.

**Data.** Eurostat air emissions accounts `env_ac_ainah_r2` (GHG, thousand tonnes CO2e) and
national accounts by industry `nama_10_a64` (current prices, EUR million): gross value added
`B1G`, compensation of employees `D1` and other taxes less subsidies on production `D29X39`.
Gross operating surplus is derived as `B1G - D1 - D29X39`, from the Eurostat API.

**Method.** Break-even price = surplus divided by emissions, by sector and year. Intervals
by resampling member states within the sector. The 2030 figure extrapolates the log trend of
emission intensity per unit of surplus. Backtest: fit on years up to t, predict t+3, and use
the realised errors for the interval on the 2030 figure. Sweep: the emission scope (all GHG or
CO2 only), the pass-through share, and the window of the trend fit.

**Validation.** The NACE-based accounts follow the residence principle and the national
inventory `env_air_gge` the territorial one; the module reconciles the EU27 totals and reports
the gap rather than hiding it.

**The limit to state first.** The accounts cover all emissions of a sector, ETS and non-ETS,
and free allocation is not in the data. The break-even price is a ceiling on exposure, not a
forecast of the bill.

**The question it answers.** "At what carbon price does a sector stop earning its cost of
doing business, and how fast is that moving?"

## 22 — `22-residual-load-ramps`

**Estimand.** The 99th percentile of the three-hour upward ramp in German residual load (load
minus wind and solar generation), in GW, by calendar year from 2019. Reported also as a share of
peak load, and then the change in that ramp per GW of added solar capacity.

**Data.** Energy-Charts API: `/public_power?country=de` (quarter-hourly Load, Wind onshore, Wind
offshore, Solar) and `/installed_power?country=de&time_step=yearly` for capacity by type.
Fetched in monthly requests with pauses, because a year is a 5 MB response and the API rate-limits.

**Method.** Compute the ramp on rolling three-hour windows. Interval on the percentile by block
bootstrap over days. Regress the annual ramp on installed solar and wind capacity. Backtest: fit
up to year t-1, predict the ramp of year t, and report the error of each year; the interval on
the forward figure for a stated solar capacity comes from those errors. Sweep: window length
(1, 3, 6 hours), percentile (95, 99, 99.9) and the treatment of the DST days.

**Validation.** The `Residual load` series the API publishes itself is compared with the one
computed here, and the difference is reported.

**The question it answers.** "How much flexibility does the grid need within three hours, and
how fast is that number growing with solar?"
