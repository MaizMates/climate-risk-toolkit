# Module roadmap

Modules are built in this order, lowest number first. The order encodes which gap in my own
work each one closes, and the sequence is designed so each module reuses the previous one's
output. Every module meets `STANDARD.md`; one that cannot meet it is not built, and its row is
marked **blocked** with the reason.

Every module is an independent project on public data. None of it is affiliated with, or
draws on the work of, any employer.

| # | Module | The gap it closes |
|---|---|---|
| 01 | `01-heat-stress-gradient` | **built** |
| 02 | `02-renewables-pace` | **built** |
| 03 | `03-hazard-exposure-join` | **built** |
| 04 | `04-emissions-inventory` | **built** |
| 05 | `05-portfolio-climate-risk` | climate risk of a real, public portfolio |
| 06 | `06-flood-depth-damage` | physical risk, loss not hazard |
| 07 | `07-pacta-alignment-open` | transition alignment, reproducible |
| 08 | `08-scenario-pd-shift` | climate into credit metrics |
| 09 | `09-financed-emissions-pcaf` | financed emissions with data-quality scores |
| 10 | `10-disclosure-quality-index` | data quality at scale |
| 11 | `11-hazard-exposure-gridded` | module 03 at grid-cell resolution |
| 12 | `12-nature-dependency-encore` | nature risk, quantified |
| 13 | `13-transition-plan-nlp` | AI on unstructured regulatory text |

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

