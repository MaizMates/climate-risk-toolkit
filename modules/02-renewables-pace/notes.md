# Notes — what I tried, what I threw away, what I got wrong

**I published a wrong number and this is where it is recorded.** The first version measured the
pace as the difference between the first and last value of the window. On that basis Italy looked
flat, +0.03 points a year, and I wrote that in the deck and in the dashboard. Fitting the slope
properly gives +0.38 with a standard error of 0.12. The
country is not flat; my estimator was bad. An endpoint difference throws away every point in
between, which is exactly what happened here.

**Renewables share against electricity carbon intensity.** Dropped: renewables sit in the
numerator of one series and displace the other, so the correlation is mechanical. It would have
looked like a finding and been a tautology.

**Distance from each country's own NECP target.** This is the analysis I actually wanted. The
national contributions live in NECP documents, not in a machine-readable table, and typing thirty
numbers out of PDFs is the failure mode this repository exists to avoid. So the module uses the EU
aggregate as a stated yardstick and says so on three separate pages.

**Clipping negative paces.** My first version took max(0, pace), reasoning that a country cannot
de-industrialise its way backwards. Slovakia can: its fitted slope is negative. The clip would
have hidden the single most interesting row, so there is now a test that fails if it returns.

**Window length.** Three years overweights the 2022 energy shock, ten reaches back before the
directive changed the incentives. Five is a compromise with no deeper justification, which is why
the module reports the sensitivity rather than defending the choice.

**Why the backtest changed the conclusions.** Before it, every country got a verdict. After it,
1 of 27 do not, because the projection band straddles the yardstick. Losing
verdicts is the correct outcome: they were never supported.

**On tooling.** I use AI assistants to write and review code here, the same way I use a linter.
Every number comes from code that runs on public data, and the checks in `tests/` exist so a
broken change fails loudly instead of producing a plausible figure.
