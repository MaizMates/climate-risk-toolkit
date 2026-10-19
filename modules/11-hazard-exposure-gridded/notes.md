# Notes: what was tried, what was dropped, what I got wrong along the way

**The CCKP API has no cell query.** The roadmap entry assumed I would call the CCKP API and join
plant coordinates to cells. The API was up on 2026-10-19 (module 03's 502 is gone), but it answers
for country codes and for subnational units: `ESP@` returns the country and twenty identifiers such as
`ESP.2292716`. Every coordinate form I tried (`p40.4_-3.7`, `POINT(...)`, `lat`/`lon` parameters,
`-3.7,40.4`) returned `"data": []` with status success, which looks like an answer and is not one.
I considered joining plants to those subnational units, and dropped it: it would need unit polygons
I do not have, and it is not a grid. The cells are in the public S3 bucket `wbg-cckp`, which I
found from a search for the CCKP data download route and then listed.

**Reading HDF5 with numpy.** The files are HDF5, and netCDF4 and h5py are outside the allowed
libraries. I wrote a reader for the layout these files use (superblock v2, links in the root object
header, one chunk per variable, shuffle then deflate, v1 chunk B-tree). The first attempt failed
with a zlib header error because I read the chunk keys with one offset too many. I did not trust the
second attempt until it reproduced the API: area-weighted grid means over the country polygons match
the CCKP country values to 0.15 days in 33 comparisons. That is the check that carries weight, and
it is why the validation page exists.

**France.** The first validation run gave France 1.28 days against the API's 0.43. The polygon
includes French Guiana and the other overseas parts. The API is metropolitan. Keeping only the
polygon parts that sit in Europe fixed it, and the same filter now defines "own country" for the
plant coordinate check.

**Bad coordinates.** WRI has Escombreras at latitude 7.57 (1,199 MW, the largest single plant in
the dropped set) and Garona Verda with latitude and longitude swapped. I found them by listing the plants with
coordinates outside a European box, and wrote a check that does not need me to know which
plants are wrong: distance to the own country's polygon, with a swap repair. I did not fix any
coordinate by hand: that would be typing data. Ceuta and Melilla are dropped by the same rule
because the mainland polygon excludes them; I considered the 1:50m to 1:10m Natural Earth upgrade
(13 MB) to keep them and left it, 107 MW does not move a share of 259,319 MW.

**First hazard interval was wrong.** I first compared the grid share at the ensemble p10 and p90
layers with the country share at the median, and found that the envelope [6.8%, 53.3%] contained
the country-level 42.9%. That comparison moves one measure and holds the other fixed. The hazard
error is common to both, so the country share has to move with it: I fetched the country p10 and p90
values from the API and took the gap at each. It stays negative at p10 and p90.

**Plant bootstrap to site bootstrap.** I first resampled plants one by one, as module 03 does. Units
at one station share a cell and a value and are not independent draws, so the interval resamples
the 617 distinct sites. It changed the interval by less than a tenth of a point at *k* = 2 and I
report both. I kept the site version because the argument for it does not depend on the result.

**The baseline sits at one end of the sweep.** I fixed the cell containing the plant as the baseline
before running the radius sweep, because the roadmap says grid cells. It turned out to be the end
with the largest gap (-25.2 points against -10.4 at 100 km over land cells). A wider radius averages
in the sea and the inland cells, which pulls the plant value back toward the area mean. The README
says so beside the table. Which radius is right depends on how well WRI places a plant and how much
of the cell's value is local, and I cannot tell either from this data.

**Resolution ladder.** Added after the first result, because 17.7% against 42.9% invites the
question of whether 0.25 degrees is information or interpolation. Block means at 0.5, 1 and 2
degrees show 18.6 of the 25.2 points are already gone at 2 degrees. It does not settle the
question: it bounds how much depends on the finest scale.

**Why no backtest.** The only forward-looking quantity is CCKP's projection, which I do not fit.
Comparing SSP2-4.5 with SSP3-7.0 is a sensitivity, not a test: neither scenario has been realised.
I considered scoring the historical layer against an observed climatology and dropped it, because
I have no second gridded source for days above a 35 C heat index that I can fetch and trust.

**Nuclear, again.** Left out, for the reason in module 03's notes: its channel is cooling water,
not ambient heat, and this hazard does not measure that.

**On tooling.** I use AI assistants to write and review code here. Every number in `results/` comes
from code that runs against public data, and `tests/` is there so that a flipped latitude axis, a
wrong shuffle order or a `>=` for a `>` fails loudly.
