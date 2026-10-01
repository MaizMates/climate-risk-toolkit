# Notes — what was tried, what was dropped, what I got wrong along the way

**Reading a 300MB-per-file raster without downloading it.** The JRC hazard maps are nine GeoTIFFs
at ~260–334MB each, covering the whole of Europe at 90m resolution. The module build instructions
for this toolkit forbid starting a background download and ending the turn — every command runs
in the foreground, however long it takes — so pulling all nine files in full was never really an
option on a reasonable budget, and it would have been wasteful even without that constraint: the
portfolio only needs depth at ~160 points. I fetched the first 16 bytes to get byte order and the
IFD offset, fetched the last ~2MB to get the tag table including the tile offset/byte-count arrays
(these files write tiled, deflate-compressed, and the IFD sits near the end), then for each
portfolio location resolved which 256×256 tile its coordinate falls in and range-requested only
that tile's compressed bytes. Total transferred per return period ended up in the tens of
megabytes rather than ~300MB, across all nine return periods combined. The first version of this
had a bug that cost an hour: I detected byte order from the wrong byte range (the tail buffer's
first two bytes, not the file's first two bytes), which silently flipped every subsequent
`struct.unpack` to the wrong endianness and produced tag values that looked like plausible garbage
(huge array offsets) rather than failing loudly — the kind of bug this toolkit's own
`STANDARD.md` point 9 asks tests to catch, and there is now a `RasterGrid` test built from
hand-set metadata specifically so the tile-index arithmetic never depends on a live fetch again.

**The hydro-siting artifact, which was the actual finding worth almost missing.** The first full
run used the WRI portfolio with no fuel-type filter. Every single flooded location in that run was
an Austrian hydroelectric dam on the Danube or Inn — Wallsee-Mitterkirchen, Melk, Ybbs-Persenbeug,
Aschach, Kaunertal, Rodundwerk II, Greifenstein — with depths up to 14m and EAD fractions over 50%.
That is not a flood-risk finding; it is a coordinate-placement artifact. A hydro plant's
coordinate sits in or immediately beside the river by engineering necessity, and the JRC hazard
raster reports the water level at that point whether or not any "flooding" above normal operation
is happening. The published Huizinga curves are building/infrastructure damage curves — they have
nothing to say about a turbine hall built to operate submerged. Keeping hydro in made Austria's
headline country-level EAD look like the dominant story in the whole module, for a reason that had
nothing to do with the estimand. Hydro and wave/tidal are now excluded from `build_portfolio`, and
`notes.md` records this instead of letting it look like a finding, because it nearly became the
module's headline by accident.

**The permanent-water-bodies patch, same shape of problem, different source.** After dropping
hydro, one remaining flooded site — Eems, a gas plant in the Netherlands sited on the Ems estuary
for cooling water — showed exactly 1.0m of depth at every one of the nine return periods, with no
variation at all. Every other flooded site's depth increases monotonically with return period, as
physically required (that pattern is itself a quiet internal sanity check worth noting: it would
have been a believable way for a tile-decoding bug to hide). A constant value across return
periods is the signature of a hard-coded fill rather than a modelled flood, so I checked JRC's
`Europe_permanent_water_bodies.tif`, from the same dataset release, at that coordinate — it reads
positive there. The "filled_depth" product patches permanent water bodies in at a nominal depth so
the hazard rasters have no gaps along a river's main channel; a plant's intake sitting on that
patch is not evidence of flood exposure. Eems is now screened to zero depth rather than counted
as the most exposed non-hydro site in the portfolio, and the screen is applied generically (any
location flagged by the permanent-water layer), not as a one-off exclusion of this single plant.

**Validation source, tried and not found.** `STANDARD.md` point 6 asks for a comparison against
something the module did not fit, and says explicitly to state it when none exists rather than
skip the section. I looked for a country-level expected-annual-flood-damage figure to compare the
headline against: JRC's own PESETA IV river-floods report states an EU+UK aggregate (river
flooding causes about €7.8bn/year, roughly 0.06% of GDP), but the country-level breakdown is a
table inside a PDF annex, not a downloadable file — using it would mean transcribing a number from
a report, which is exactly what `STANDARD.md` point 2 rules out for an input, and I did not want
to quietly relax that rule for a validation figure just because it would have been convenient. I
used JRC's own two QA layers from the hazard-map release instead (spurious-depth flags,
permanent-water-bodies), which are fetchable and directly relevant to this specific raster's known
failure modes, and said plainly in the README that no independent EAD benchmark was fetched.

**The EAD integral's frequent-end convention — found by sweeping it, not by design.** The roadmap
asks to check whether the hazard or the curve dominates the answer, and curve choice turned out to
move the headline by only 0.15 points. While building the sensitivity sweep for the portfolio-size
and tail-extension choices, I also tried toggling whether the integral assumes zero damage at an
annual probability of 1 (so floods more frequent than RP10 still contribute something by
interpolation) against simply stopping the integral at RP10 and ignoring probability mass above
it. That one choice swung the headline by about 4.5x — far more than curve choice, and more than I
expected going in. It is reported on the sensitivity page precisely because it was the biggest
lever found, not the one the roadmap flagged in advance; a module that only reported the expected
sensitivity (curve choice) and missed the one that actually dominated would have been the more
comfortable report to write and the wrong one.

**Why no backtest.** The JRC hazard maps are LISFLOOD/LISFLOOD-FP fitted to the historical EFAS
reanalysis — a present-day statistical hazard assessment, not a climate-change projection. There
is no forward-looking quantity in this module to hold a year out from and no trend fitted by this
module's own code, so a backtest has nothing to test against. This is different from module 03's
situation (which inherits an unbacktestable projection from module 01): here, nothing in the chain
is a projection at all, which is itself the reason stated on the limits page rather than left
implicit.

**On tooling.** I use AI assistants to write and review code here, the same way the earlier
modules do. Every number in `results/flood_depth_damage.json` comes from code that runs against
public endpoints on demand, and `tests/test_flood_depth_damage.py` exists so a flipped sign, a
wrong tile index, or a dropped nodata check fails loudly instead of producing a plausible wrong
EAD.
