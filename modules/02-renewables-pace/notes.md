# Notes — what I tried and what I threw away

**First idea: renewables share against electricity carbon intensity.** Two Eurostat series, a
scatter, a correlation. I dropped it because the correlation is mechanical — renewables are in the
numerator of one and displace the other — so the chart would have looked like a finding and been
a tautology.

**Second idea: rank countries by distance from their own NECP target.** This is the analysis I
actually wanted. I could not do it honestly: the national contributions are in the NECP documents,
not in a machine-readable Eurostat table, and typing thirty numbers out of PDFs into a script is
exactly the kind of unverifiable input this repository is supposed to avoid. So the module uses
the EU aggregate as a stated yardstick and says so three times, rather than quietly pretending
42.5% is a national target.

**Window length.** Three years put too much weight on the 2022 energy shock; ten years reached
back before the 2018 directive and flattered everyone. Five years is a compromise and it is
arbitrary — the number moves with it, which is worth admitting in an interview rather than
defending.

**Clipping.** My first version took `max(0, pace)`, on the reasoning that a country cannot
de-industrialise its way to a lower renewable share. Slovakia proves it can: its share fell over
the window. The clip would have hidden the single most interesting row in the table, so the test
suite now has a case that fails if anyone puts it back.

**On the tooling.** I use AI assistants to write and review code in this repository, the same way
I use a linter. The numbers come from code that runs on public data, and the check in `tests/` is
there so that a broken change fails loudly rather than producing a plausible figure.
