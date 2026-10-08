# Notes: what was tried, what was dropped, what I got wrong along the way

**A sector PD series.** The roadmap asks for a PD, and the first thing I looked for was a public
sector default rate. Eurostat has none: `sts_rb_a` carries bankruptcy declarations as an index, so
it gives changes and no levels, and its sectors are nine coarse NACE groups. Rating-agency default
studies have sector tables, but only as PDFs of figures I would have to type. The EBA transparency
data carry non-performing loans by NACE sector; I did not look for a stable URL, so that route is
open and untested. I used the baseline PD as a stated parameter (2%) and report the relative change
as the result.

**Estimating the elasticity myself, as the headline.** My first plan was to fit the profit-to-default
slope on Eurostat and use it. The slope is -0.003 per point of profit share with country and year
effects, and the interval from resampling countries spans zero in the two specifications I bootstrapped. A
headline built on it would be a number whose interval contains no change. I kept it as the second
interval and took the elasticity range from the literature, as the roadmap says, then used the
European data to test the literature mapping out of sample.

**Reading the literature coefficient by code.** I did not want a typed -20.26. The NBER PDF is
fetchable, and its text streams are readable with `zlib` and a regular expression for the TJ
operators, the same route module 05 took for a fund report. The first parse returned kerned
fragments; a gap wider than 150 units has to count as a space. The parser now fails loudly if the
`NIMTAAVG` row is missing or if its coefficients are not negative.

**The units of the coefficient.** I first applied -20.26 to an annual change in net income over
assets. The paper's regressors are quarterly: its text gives the median NIMTA as 0.6% per quarter
or 2.4% at an annual rate. The annual change is therefore divided by four. Without that the
headline is four times larger and looks perfectly reasonable, so there is a test with the hand
calculation.

**Gross operating surplus.** I expected `nama_10_a64` to carry `B2A3G`. It does not; it has the net
`B2A3N`. A request naming an item the table lacks returns the items it has, silently, and my profit
share panel came out empty. I use value added minus compensation of employees, which includes
depreciation and mixed income, and say so.

**Below 2°C went missing.** The first run printed empty price lists for Below 2°C in all three
models. The bulk endpoint returns the scenario name with a question mark where the run list has the
degree sign, so my name match dropped the rows. Matching on run id fixed it. I found it only because
I printed the price table before using it.

**A sweep row that repeated the headline.** The horizon sweep showed the 0-month coefficient giving
exactly the headline, which cannot be. I had written `lag or default`, and lag 0 is falsy. The
0-month row is the largest effect in the sweep (-13.6%), and the sweep summary was understating the
span by 2.5 points until I fixed it.

**An interval that was too narrow.** The sampling error of the 12-month coefficient gives
[-10.5%, -8.5%], from a z statistic of 18. That is the uncertainty of a US estimate and says nothing
about transfer to Europe. I replaced it as the main interval with a draw over the five horizons the
paper reports and kept the narrow one beside it, so the gap between the two is visible.

**The sign.** I expected a disorderly scenario to carry the higher PD. Against Net Zero 2050 it does
not: the Delayed transition price is lower in every year to 2050 in all three models. I considered
switching the orderly reference to Below 2°C, which gives +9.3%, and rejected it. I had fixed the
pair before running, and picking the reference that gives the expected sign is the choice a reviewer
should distrust. The six pairs are in the sweep.

**A backtest window that was too late.** I first tested on 2022 to 2025. Bankruptcy and national
accounts data for 2024 and 2025 are too sparse to give groups of three, so only two test years
survived. Moving the window to 2019 to 2023 gives 736 observations, at the price of including the
insolvency moratorium years 2020 and 2021, which I report separately.

**A calibration slope for the panel's own prediction.** I also computed the slope of realised on my
own fitted prediction. It came out at 3.8 with an interval from -3.1 to 12.3. The prediction is
almost zero, so the ratio is noise, and I dropped it. The comparison that carries information is the
slope on the literature-implied prediction, and the skill scores.

**Abatement.** I first left it out as too crude. Without it, 2040 under Net Zero 2050 charges industry
a bill of 34.8% of value added, which is not a scenario anyone would run a bank against. I added it
as a sweep, scaling intensity by the region's emissions over their 2020 value, floored at zero. It
flips the sign, and I did not promote it to the headline because it ignores abatement cost and uses
economy-wide emissions for one sector.

**Pass-through.** The 0.7 is from the abstract of Ganapati, Shapiro and Walker, found by search. I did
not read the paper, the setting is US manufacturing energy costs, and the share for a carbon price on
EU producers facing imports is probably lower. It is an assumption, labelled one, and it is the
largest single span in the sweep.

**What I could not build.** A PD level by sector, a direct test of the elasticity on default data, and a
demand-side response. I did not exhaust the options for the first two.

**On tooling.** I use AI assistants to write and review code here. Every number in `results/` comes
from code that runs against public endpoints on demand, and `tests/` exists so that a dropped
division by four, a swapped scenario sign or a per-sector coefficient draw fails loudly instead of
producing a plausible wrong PD.
