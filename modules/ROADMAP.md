# Module roadmap

One module per scheduled run, Monday and Thursday. **The run builds the lowest-numbered module
that does not yet exist in `modules/`.** It does not choose, improvise, or reorder: the order
encodes which gap blocks Marco most, and the sequence is designed so each module reuses the
previous one's output.

Every module meets `STANDARD.md`. A module that cannot meet it is not built — the run says so and
moves to the next one in the list, recording why.

| # | Module | The gap it closes |
|---|---|---|
| 01 | `01-heat-stress-gradient` | **built** |
| 02 | `02-renewables-pace` | **built** |
| 03 | `03-hazard-exposure-join` | physical risk, asset level |
| 04 | `04-flood-depth-damage` | physical risk, loss not hazard |
| 05 | `05-pacta-alignment-open` | transition alignment, reproducible |
| 06 | `06-scenario-pd-shift` | climate into credit metrics |
| 07 | `07-financed-emissions-pcaf` | carbon accounting end to end |
| 08 | `08-disclosure-quality-index` | data quality at scale |
| 09 | `09-nature-dependency-encore` | nature risk, quantified |
| 10 | `10-transition-plan-nlp` | AI on unstructured regulatory text |

---

## 03 — `03-hazard-exposure-join`

**Estimand.** The share of a country's thermal generating capacity, in MW, located in grid cells
whose projected annual count of days above 35 °C rises by more than *k* days between the current
period and 2050 under a stated scenario.

**Data.** WRI Global Power Plant Database, the real one:
`https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv`
— 34,492 plants with latitude, longitude, capacity, fuel and country. Hazard from the World Bank
CCKP CMIP6 indicators already used in module 01.

**Method.** Join plants to hazard cells by coordinates, aggregate capacity by country and by fuel,
and report exposed share. This is the module the invented-data one pretended to be; do it on the
real database or not at all.

**Uncertainty.** Bootstrap over plants to get an interval on the exposed share. Sensitivity to
*k* and to the cell-matching radius.

**Answers in interview.** "Have you done asset-level physical risk?"

## 04 — `04-flood-depth-damage`

**Estimand.** Expected annual damage, as a fraction of asset value, for a portfolio of locations,
under a published depth-damage function.

**Data.** JRC river flood hazard maps for Europe (return-period depth rasters, open), and the JRC
depth-damage curves for the EU.

**Method.** For each return period, read depth at the location, map depth to damage with the
published curve, integrate over the exceedance-probability curve to get expected annual damage.

**Uncertainty.** The curve choice dominates: repeat with at least two published curves and report
the spread. Say which drives the answer, the hazard or the curve.

**Answers in interview.** "How does a hazard map become a number a risk manager can use?"

## 05 — `05-pacta-alignment-open`

**Estimand.** The production-weighted alignment gap between a set of listed power utilities and an
IEA scenario trajectory, by technology, at a stated horizon.

**Data.** Company production and capacity from public filings or an open asset-level source; IEA
or NGFS published sector pathways.

**Method.** The PACTA logic Marco built at the ECB, reproduced on public inputs so it can be shown.

**Uncertainty.** Sensitivity to the scenario chosen and to the allocation rule (ownership versus
operational control) — the allocation rule is the part practitioners argue about.

**Answers in interview.** "You say you built an alignment methodology. Show me."

## 06 — `06-scenario-pd-shift`

**Estimand.** The change in a one-year probability of default for a sector under an NGFS
disorderly transition scenario relative to the orderly one, via a stated transmission channel.

**Data.** NGFS scenario variables (public download), and a public sector financial ratio source.

**Method.** A transparent, documented mapping from a scenario variable to a ratio to a PD. The
point is the auditability of each step, not sophistication.

**Uncertainty.** The elasticity is the weak link: report the range from the literature, cite it,
and show the PD range it implies.

**Answers in interview.** "Where does climate actually enter a credit model?"

## 07 — `07-financed-emissions-pcaf`

**Estimand.** Financed emissions for a synthetic but realistic loan book, with the PCAF data
quality score attached to every line.

**Data.** Public company emissions, public sector intensity factors.

**Method.** PCAF attribution, then the score, then the aggregate with the score distribution.

**Uncertainty.** The headline number is nearly meaningless without the score distribution: show
both and say so.

## 08 — `08-disclosure-quality-index`

**Estimand.** A reproducible index of Pillar 3 ESG template completeness across a set of banks.

**Data.** Published Pillar 3 disclosures.

**Method.** Marco's ECB work, on public documents, with the validation rules in code.

## 09 — `09-nature-dependency-encore`

**Estimand.** The share of a portfolio's exposure in sectors with high dependency on a named
ecosystem service, using ENCORE ratings.

## 10 — `10-transition-plan-nlp`

**Estimand.** Agreement between an LLM extraction of stated transition-plan commitments and a
hand-coded sample, reported as precision and recall with an interval.

**Method.** This is the AI module and it must be evaluated, not demonstrated: no extraction
pipeline without a labelled test set and measured error.

**Answers in interview.** "You say you use LLMs. How do you know the output is right?"
