# Notes — what was tried, what was dropped, what I got wrong along the way

**The EEA indicator's own endpoint is gone.** The roadmap named "a European public source (EEA or
Eurostat)" for location-based grid intensity, and my first plan was to fetch EEA's published
"greenhouse gas emission intensity of electricity generation, country level" indicator directly —
it is exactly the figure I need, already computed. Its old daviz chart endpoint
(`eea.europa.eu/data-and-maps/daviz/sds/co2-emission-intensity-from-electricity-generation-6/
download.csv`) returned HTTP 410 Gone, and the redesigned indicator page no longer exposes a
CSV or API link, only a rendered chart. Rather than transcribe numbers off a chart — exactly the
"illustrative extract" `STANDARD.md` rules out — I replicated EEA's own stated method (GHG
emissions from public electricity and heat production, CRF sector 1.A.1.a, divided by gross
electricity production) from two Eurostat series that are directly fetchable:
`env_air_gge` and `nrg_bal_c`. This is not a guess at EEA's method; the description on EEA's own
indicator page states the ratio explicitly, I just compute it instead of reading it off a chart
that no longer serves data. It is also why the validation page compares this module's computed
figure against AIB's independent production-mix figure, since EEA's own number is no longer
reachable to check against.

**Floor area per employee, dropped for energy per employee.** The roadmap's own framing suggested
office energy intensity per square metre times floor area per employee. Eurostat does not publish
floor-area-per-employee by country in a fetchable form — the EU Building Stock Observatory has
building-level data, not a clean national per-employee figure. Rather than invent a floor-area
assumption on top of an energy-intensity assumption (two unfetched numbers instead of one),
I substituted Eurostat's final energy consumption in commercial and public services (`nrg_bal_c`,
`FC_OTH_CP_E`) divided by Eurostat services-sector employment (`nama_10_a10_e`) — a
national energy-per-employee intensity, fully fetched, with one fewer unfetched assumption in the
chain than the floor-area route would have needed. "Services" here is `TOTAL - agriculture -
industry - construction`, a bit broader than a financial-services-specific figure, and the limits
section says so.

**DESNZ no longer publishes overseas electricity factors.** I had planned to use DESNZ's
"Overseas electricity" sheet as a second, independent Scope 2 location-based factor to
cross-check the Eurostat-derived one, since a same-file second country factor would be a clean
validation. The sheet exists but is empty: DESNZ's 2024 guidance notes that international
location-based factors are now sold separately by the IEA and no longer republished for free.
Validation instead uses AIB's own "production mix CO2" column, already present in the same file
already fetched for the market-based residual mix — no extra source needed, and the divergence it
surfaces (Italy's autoproducer gap, France's near-zero-on-near-zero percentage swing) is a more
interesting finding than a clean match would have been.

**AIB's residual mix is CO2, not CO2e.** The GHG Protocol wants CO2e for market-based Scope 2.
AIB's published "Residual mix CO2" column is CO2 only — CH4 and N2O from combustion are a small
enough share of total electricity-sector GHG that this is a standard simplification in market-
based reporting, but it means the market-based total in this module is *slightly* understated
relative to a strict CO2e figure, more so for countries with a coal-heavy residual mix (where
CH4 from mining is a larger share) than for France's near-nuclear one. Not corrected for, because
AIB does not publish the CH4/N2O split needed to correct it, and estimating that split would be
exactly the kind of invented precision `STANDARD.md` rules out.

**Business travel and commuting: the most assumption-heavy lines in this inventory, and the ones
I considered dropping.** Category 6 and 7 together are 41% of the location-based total — too
material to drop as "not material enough to bother with," but built on a firm-wide assumed
travel budget and commute distance, not anything about this (nonexistent) firm's employees.
I kept them because a GHG inventory that silently excludes 41% of its own total to avoid
reporting an uncertain number is a worse inventory than one that reports the number with its
uncertainty attached — `data_quality_score` on every commuting and travel line is 4 or 5 (out of
5, worst), and the Monte Carlo interval on Scope 3 reflects that honestly.

**Why the car-commuting line is as large as it is.** Frankfurt's car-commuting line is the
largest single Scope 3 line in the inventory — driven by Eurostat's national CAR share of
passenger-km (84% for Germany), which is a country-wide modal split across all inland travel, not
an urban-commute-specific one. A firm in central Frankfurt with good transit access would likely
see a lower car share than the national figure; the limits section names this as the module's
least defensible number, not just a caveat.

**On tooling.** I use AI assistants to write and review code here, the same way modules 02 and 03
do. Every number in `results/emissions_inventory.json` comes from code that runs against public
data on demand, and `tests/` exists so a unit mismatch or a broken aggregation fails loudly
instead of producing a plausible wrong inventory.
