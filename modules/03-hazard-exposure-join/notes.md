# Notes — what was tried, what was dropped, what I got wrong along the way

**The grid-cell join, which is what the roadmap actually asked for.** Module 03 was scoped as
plants joined to CCKP hazard grid cells, with plant coordinates matched to the nearest cell under
a stated radius. The CCKP API returned HTTP 502 on every retry during this build, on 21/09/2026.
Module 01's committed output is already at country resolution — it never pulled grid cells,
because the country query was what worked on 21/09 — so there was no fallback dataset in this
repository to build the gridded version from. Waiting for the outage to clear was the wrong call
given the scheduled build cadence, and inventing coordinates or a synthetic grid would be exactly
the fabrication `STANDARD.md` exists to rule out. So the estimand was narrowed to what module 01
actually provides — country-level exposure — and the gridded version is now module 11, to build
when CCKP answers again. The comparison between module 03 and module 11 will itself be a finding:
it will measure what the coarse resolution cost, which is a more honest use of the outage than
pretending it didn't happen.

**Is nuclear thermal?** By engineering definition, yes — a nuclear plant is a steam cycle like
coal or gas, and it is at least as heat-exposed: French reactors have been curtailed in past
heatwaves because river water got too warm to use as coolant, which is arguably a *sharper*
climate risk than a coal plant's. It was left out of the thermal definition anyway, because the
roadmap's own sensitivity instruction only names gas and biomass as the arguable toggles, and
because nuclear's exposure channel (cooling water temperature and river flow) is a different
mechanism from `hd35` (ambient heat-index days) — folding it into the same threshold would silently
mix two hazards under one number. It is 195 plants and excluded from every run in this module. If
this module gets extended, nuclear cooling-water exposure is a separate estimand, not a fourth
toggle on this one.

**Endpoint difference, again.** Module 02's error was using first-minus-last instead of a fitted
slope. There's no equivalent time-series estimator to get wrong here — the join is cross-sectional,
one snapshot of capacity against one hazard table — but the analogous trap was rounding the
threshold: `change_days > k` vs `change_days >= k`. The roadmap's estimand says "rises by more
than *k* days", which is strict. `tests/test_hazard_exposure.py` has
`test_threshold_is_strictly_greater_than_k` because a country landing exactly on a round threshold
(2.0, 5.0) is a real edge case with this data, not a hypothetical one, and `>=` would silently
reclassify it.

**Why no backtest.** I considered treating module 01's SSP2-4.5 vs SSP3-7.0 scenarios as a form of
cross-check, the way module 02 backtests a fitted slope. It isn't one: a backtest compares a
prediction against a *realised outcome*, and there is no realised mid-century outcome to compare
against — both scenarios are equally unrealised projections from the same CMIP6 ensemble. Treating
scenario spread as if it were validation would have been a second, quieter fabrication: presenting
model disagreement as if it were evidence against reality. The honest statement is that this
module inherits module 01's uncertainty (ensemble median only, no spread) rather than adding a
false one of its own. This is recorded on the limits page instead of buried.

**Validation source.** Tried Eurostat's `nrg_inf_epc` (electricity production capacity by fuel
group) as an independent check on WRI's capacity totals, since `STANDARD.md` requires comparing
against something the module did not fit wherever a second source exists — and one does. Combustible
fuels (`siec=CF`) is the closest published analogue to "thermal": it bundles coal, oil, gas and
biofuels/waste under one code, so it isn't a clean fuel-by-fuel match against this module's four
sensitivity combinations, but it's the right level to sanity-check the country totals the join
actually uses. It found real gaps (Austria 37% of the Eurostat figure, Belgium 58%), which is a
finding worth keeping rather than a validation that just confirmed what was already assumed.

**Dropping the top-ten-plants figure.** Considered reporting only the CI and leaving out the
concentration statistic, on the theory that the bootstrap already captures skew. Kept it anyway:
a 6.6-point-wide interval on its own doesn't tell a reader *why* it's that wide, and "ten plants
are 17.9% of the exposed total" is the sentence that answers the question a skeptical reviewer
asks immediately after seeing a wide band on a share statistic.

**On tooling.** I use AI assistants to write and review code here, the same way module 02 does.
Every number in `results/hazard_exposure.json` comes from code that runs against public data on
demand, and `tests/` exists so a broken join or a flipped inequality fails loudly instead of
producing a plausible wrong share.
