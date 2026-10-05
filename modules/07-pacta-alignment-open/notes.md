# Notes — what was tried, what was dropped, what I got wrong along the way

**IEA pathways.** The roadmap names an IEA or NGFS pathway. I opened the IEA data page and found no
open endpoint for the World Energy Outlook scenario tables; I did not search further, so it is
possible one exists. NGFS Phase 5 is published through the IIASA Scenario Explorer with an
anonymous API and carries capacity by technology, so I used that. Net Zero 2050 is the closest NGFS
pathway to a net-zero scenario, which is why it is the headline, and it is the top of the grid,
which the README says.

**Reading the NGFS API without the client.** The Scenario Explorer is normally read with `pyam`,
which is not on the allowed list. I read its source for the anonymous token route and the bulk
query body and wrote the three calls in the standard library. The first attempt returned HTTP 403
for every call: the host rejects the default Python user agent. Setting one fixed it.

**Which Europe.** I expected an EU27 region. It exists only in the downscaled runs, and only for
secondary energy, not capacity. The native models each report their own regions, so I summed the
ones covering the EU plus the UK per model. MESSAGE's Western plus Eastern Europe is wider than the
plant set; I kept it and flagged it rather than drop the model.

**Capacity, not generation.** The roadmap says production-weighted. WRI's generation columns are
filled for roughly a quarter of plants and stop at 2019, so weighting by generation would drop most
of the fleet. PACTA's power sector uses capacity, so I did too.

**Typing the utilities.** The first idea was a list of listed utilities. That is a typed input, and
the standard rules those out. I kept a name-matching table, which is a classification rule, and let
Wikidata decide who is listed. The table is a judgement and is swept (strict against extended).
Wikidata took several attempts. The search endpoint answered 429 and needed retry with backoff.
It returned a power station for "Centrica" and nothing for "EDP" or "Enea" until I changed the
search term to the label Wikidata uses. A SPARQL scan for every entity with a stock-exchange
statement and a matching label ran into a 504. The first full run therefore had EDP, Enea, Edison
and Centrica unlisted by a lookup failure, not by fact. I found it by reading the listing table
against what I know of each company, fixed the terms, and the audit trail now sits in the results.
I dropped Eni and Orlen from the table because they are oil majors, not utilities.

**A roll-up that did nothing.** The extended alias tier first mapped Endesa into Enel, its parent.
Because the first matching rule wins and Endesa comes first, the rule never fired. Both appeared
separately in the set while the label said otherwise. I removed it. Endesa and Enel are separate
groups in every run.

**The interval that was not one.** My first bootstrap returned a renewables gap of -101.1% with a
zero-width interval, and the same figure under every allocation and alias choice. I checked the
algebra: under the market-share approach each company adds the same fraction of its sector, so the
summed build-out gap is the scenario's change over sector size and company data cannot move it.
The code was right and my expectation of an interval was wrong. I kept the structural result in
the README, put a test on it, and added a second interval that draws the scenario model once per
replicate for all companies, which is the only draw that can move that gap.

**Two sweep rows that were identical.** After adding the coverage rescaling, the pace-corrected
sweep printed the same numbers as the rescaled one. I had reused a variable and the second row
reported the first row's results. I found it because two unrelated adjustments cannot agree
exactly. The sweeps now run through one function.

**Re-anchoring to the realised stock.** I considered restarting the scenario from the 2024 realised
capacity, scaling each company by the region's growth. That assigns every company the region's
growth rate, which is untrue for a utility, so I dropped it. The pace correction (the realised
over scenario ratio, carried forward at a constant annual rate) is cruder but needs no assumption
about individual companies, and it is reported as one line in the sweep, not as the headline.

**Why the allocation rule does nothing.** I expected it to move the result, because the roadmap
calls it the part practitioners argue about. It moves 1.0% of attributed MW. The 3,006 MW
that do move show the rule is operating, so a zero is not a bug.
The cause is the register: one owner string per plant, few joint ventures, and most of the fleet
owned outright by one group. A register with stakes would give a different answer, and I could not
fetch one.

**What I could not build.** The plan-based gap. PACTA compares a company's production plan to the
target; this module compares its 2020 fleet. I found no source of company retirements and pipeline
that I could fetch by code without a login. I did not exhaust the options.

**On tooling.** I use AI assistants to write and review code here. Every number in `results/` comes
from code that runs against public endpoints on demand, and `tests/` exists so that a broken target
formula or a per-company model draw fails loudly instead of producing a plausible wrong gap.
