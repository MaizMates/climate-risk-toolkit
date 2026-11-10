# Notes: what I tried, what I threw away, what I got wrong

**Where the intensity effect sits.** My first reading of the result was that efficiency removed 70 Mtoe. The
annual effects say otherwise: 73% of that sits in 2022 and 2023. Before 2022 the same decomposition shows
consumption rising, because activity outran a modest intensity fall. I rewrote the headline around that
instead of the 70.

**Unit of resampling.** A state's three sectors are one observation of that state, so the bootstrap draws
states whole from the start, not the 81 cells independently. Independent cell draws would let a state's
sectors vary against each other and overstate the spread of the sum. A test with two cancelling cells per state
fails if that is undone.

**"Intensity is the largest effect."** On point estimates intensity is bigger than activity, 70.0 against
60.4. In 76% of bootstrap draws it is. I dropped the "largest effect" wording: with the interval it is not a
finding.

**Chained against direct.** Additive LMDI is path dependent. I chose the chain because the estimand asked for
it and because it follows the data year by year. The direct version is in the sweep and differs by 0.5 points.

**Weather.** Heating degree days fell 7.0% between 2015 and 2024, which could have produced a spurious
intensity gain in services. I estimated the elasticity of services energy to heating degree days from a
country fixed-effects regression (0.17, standard error 0.10) rather than assuming a heating share (any share would be typed in, not fetched), and
restated the energy at mean weather. It moves the intensity effect by at most 1.2 points. I kept it as a sweep row and
did not change the headline, because the elasticity is itself an estimate on 27 clusters.

**Finer industry detail.** I wanted industry by branch (`nrg_bal_c` against `nama_10_a64`), which is the real
test of whether the intensity effect is efficiency or a shift between steel and lighter industry. It needs a
branch mapping between two classifications that I could not validate in the time, so the module reports the
granularity sweep and says plainly that finer detail may move more.

**A like-for-like published intensity.** I checked the Eurostat intensity tables for a series that matches final energy per unit of
value added of industry, services and agriculture. None is published in that form. The comparison with
`nrg_ind_ei` is gross available energy per GDP, a different quantity, and I labelled it that way.

**An independent price source.** The first draft said 2022 and 2023 were the energy-price crisis without a
source. I pulled Eurostat's energy HICP against all-items HICP (`prc_hicp_aind`) so the statement rests on a
number: the real energy price index goes from 104 in 2021 to 129 in 2022.

**A wrong sentence in the deck.** The first draft of the limits page said weather correction moved the intensity
effect by "under one point". It moves it by 1.2 at the high end of the elasticity interval. The number is
now computed from `results/` and not typed.

**Stacked annual bars.** The first annual chart stacked the three effects. With effects of both signs in
the same year the stack hid the offsets, so it is grouped bars now.

**On tooling.** I use AI assistants to write and review code here, the same way I use a linter. Every number
comes from code that runs on public data, and the checks in `tests/` exist so that a broken change fails
loudly instead of producing a plausible figure.
