# Notes — what I tried, what I threw away, what I got wrong

**The bootstrap that recentred the answer on the wrong distribution.** My first version of
`bootstrap_waci_ci` resampled each holding's intensity by drawing directly from the *absolute*
cross-country levels for its NACE code — the same style as module 03's plant bootstrap. It ran
without error and produced a CI of [172, 395] around a point estimate of 142: the point estimate
sat *outside* its own interval. The bug was structural, not numerical. Module 03 resamples which
*plants* are in the sample, so the resampled statistic is built from the same underlying data as
the point estimate. Here, drawing the absolute cross-country level replaces the holding's actual
(mostly Western European, mostly lower-intensity) country with a uniformly random EU27 country —
which for sectors like utilities and mining is dominated by Poland- and Bulgaria-level intensity.
The bootstrap wasn't measuring uncertainty around the estimate; it was computing a different
estimate (the EU27-average portfolio) and calling it an interval. The fix resamples the *ratio* of
each cross-country value to its own median, and multiplies that ratio onto the holding's actual
value — same dispersion, centred on the number actually being reported. `test_bootstrap_ci_
brackets_the_point_estimate` exists because this is exactly the kind of error that runs clean and
produces a plausible, wrong-shaped number.

**The interval that was still wrong after the fix.** The corrected version above still had two
defects, found on review after the first commit. It drew the ratio from all 27 member states with
equal weight, so Poland and Bulgaria set the upper bound of a fund that holds nothing domiciled
there. And it drew each holding independently, although every holding in a sector is scored with
the same national-sector figure: 215 independent errors cancel, and the interval came out far too
narrow on the low side ([139, 309] around 142). The interval now draws one ratio per sector per
resample, from the member states the fund holds, weighted by its country mix: [82, 245].
`test_bootstrap_ignores_member_states_the_fund_does_not_hold` and
`test_bootstrap_shares_one_draw_across_a_sector` pin both.

**Which fund.** I looked at iShares first — the obvious choice, and the one with the most public
name recognition — but iShares' site has moved to a new front end and the old
`?fileType=csv&fileName=...` ajax endpoint that used to return a raw holdings CSV now returns the
product page's HTML instead. SPDR (State Street) still serves a real `.xlsx` per fund at a
predictable URL by ticker, so I switched providers rather than trying to reverse-engineer a
JavaScript-rendered page. Whether iShares' endpoint is fixable is a question for whenever a future
module needs an iShares fund specifically; it wasn't worth solving for this one.

**Which iShares/SPDR fund, once picked.** I deliberately did not choose a global or US equity ETF.
Eurostat's `env_ac_ainah_r2` and `nama_10_a64` only report EU member states, and module 01's
hazard table only covers eleven of them. A global fund would have left most of its holdings with
no intensity data and no physical overlay at all, and the module would spend its limits section
apologising for coverage instead of reporting a finding. A Eurozone fund (MSCI EMU) puts nearly
all of the portfolio inside both datasets' coverage, which is itself named on the limits page as a
reason to be skeptical of how well this method would generalise to a global book.

**The GICS → NACE mapping, sector by sector, and why each one.** The holdings file gives an MSCI
GICS sector, not a NACE code, so every mapping choice below is "which single NACE code is the
least-bad representative of this GICS sector, given what this specific portfolio actually holds
under that label" — not an abstract crosswalk.
- **Energy → B** (mining and quarrying). The fund's Energy names are oil & gas and energy
  equipment; B covers extraction. Refining (NACE C19) is excluded — a real coarseness, since an
  integrated oil major does both.
- **Utilities → D** (electricity, gas, steam, air conditioning supply). A clean match; every
  Utilities sub-industry here (electric, gas, multi-utility, independent power) sits inside D.
- **Materials → C20** (chemicals). The Materials names include chemicals, construction materials,
  metals & mining, paper — chemicals is the largest sub-industry by value here, so it is the base
  case; C24 (basic metals) is the swept alternative, and it moves WACI up (metals run hotter per
  unit of value added than chemicals in most member states).
- **Industrials → C28** (machinery and equipment n.e.c.). Aerospace, machinery, electrical
  equipment, construction and engineering, air/ground transport all sit under "Industrials" here.
  C28 (machinery) is the modal single division; the swept alternative is the whole NACE section C
  (all manufacturing), which is meaningfully more carbon-intensive on average and is the single
  biggest driver of the "all alternates" WACI figure.
- **Consumer Discretionary → G** (wholesale/retail trade, incl. of motor vehicles). Retail and
  distribution dominate this GICS bucket by sub-industry count, and G's own definition explicitly
  includes vehicle repair and trade. The swept alternative, C29 (motor vehicle manufacture),
  barely moves WACI but moves the CPRS share by 7.6 points — see the sensitivity section, this is
  the finding I almost missed by only looking at WACI.
- **Consumer Staples → C10-C12** (food, beverages, tobacco manufacture). Beverages and food
  products dominate; household/personal care products (more properly a chemicals-adjacent
  activity) are the coarseness cost here, unswept because the base case already fits most of the
  category's value.
- **Health Care → C21** (pharmaceutical manufacturing), not Q (human health activities). This
  fund's Health Care names are pharma, biotech and med-tech manufacturers, not hospital operators
  — Q would be the wrong economic activity entirely, not just a coarser one. Swept as the
  alternative anyway, because it is the more "obvious" (and wrong) reading of the GICS label, and
  showing it is wrong is itself informative.
- **Financials → K** (financial and insurance activities). Unambiguous.
- **Information Technology → C26** (computer, electronic and optical products). ASML alone is
  ~9% of the entire fund and is a semiconductor-equipment manufacturer; C26 is the correct
  activity for it and for most of the rest of the sector's software/hardware/semiconductor mix.
  Software and IT services are more properly NACE J62_J63, but ASML's weight dominates the
  sector's true composition here.
- **Communication Services → J** (information and communication). Telecom and media both sit
  inside J; no better single division exists that covers both without over-splitting a small
  sector (3.3% of the fund).
- **Real Estate → L** (real estate activities). Unambiguous, and the smallest sector in the fund
  (0.5%).

**The CPRS categories are a reconstruction of Battiston et al. (2017)'s published groupings, not a
transcription of a number from the paper.** The paper defines Climate Policy Relevant Sectors —
fossil-fuel, utilities, energy-intensive, buildings/housing, transportation, agriculture — as NACE
activity groupings; I encoded the category *labels* against NACE codes (`CPRS_CATEGORY` in
`src/portfolio_risk.py`), which is categorical, not numeric. No figure, weight or threshold from
the paper appears anywhere in this module.

**Eurostat's own gap: Germany and Spain don't report NACE-division GVA for several manufacturing
codes.** I found this by accident, checking coverage before committing to the fetch list: `nama_
10_a64` reports section-level (`C`, whole manufacturing) GVA for Germany and Spain but not the
divisions inside it (C20, C21, C24, C26, C28, C29) — most likely statistical disclosure control
(too few reporting units at that level of detail to publish without risking firm identification).
Ireland has a version of the same gap for C20/C21/C26, which is a striking one given how much of
Ireland's real economy is a handful of multinational pharma and tech manufacturers — exactly the
kind of concentration that triggers disclosure suppression. I considered silently falling back to
the section-level figure for these cells and decided against it: that would understate the
proxy's precision without saying so. The module instead falls back to the *cross-country median*
for the missing NACE code and flags every affected holding — 16.1% of portfolio value here — so
the number is honest about how much of it is not really country-specific.

**Why the physical overlay excludes Finland rather than approximating it.** 3.5% of this
portfolio's value is Finnish. Module 01's hazard table covers eleven countries and Finland is not
one of them (it wasn't in the original module 01 build's scope). I could have assigned Finland the
EU average or the nearest-latitude country's figure, but that is exactly the kind of invented
number `STANDARD.md` exists to prevent. The overlay reports the share of the portfolio it actually
covers (96.5%) and excludes the rest, rather than manufacturing a number for it.

**Validation candidates I tried before the sustainability report.** I first checked the fund's
fact sheet PDF for a disclosed carbon metric — it has a sector and country breakdown (useful for
sanity-checking the holdings parse, but I did not use it, since any number I read off it and typed
into code would be exactly the hand-transcription `STANDARD.md` rules out) but no carbon figure.
State Street's SFDR PAI disclosures for other SPDR funds turned up in a web search, which led me
to try the per-ISIN URL pattern `ssga-sustainability-report/etfs/<isin>-ssga-sustainability-
report.pdf` against this fund's own ISIN, and it resolved. That report is machine-readable enough
(FlateDecode streams with literal ASCII `Tj` text operators, no CID-font glyph indices) that a
40-line stdlib PDF text extractor — decompress each stream with `zlib`, regex out `(...)Tj`
operators — gets the number out reliably, which is why the module fetches and parses this PDF by
code instead of treating the figure as unobtainable.

**On tooling.** I use AI assistants to write and review code here, the same way I use a linter.
Every number in `results/portfolio_risk.json` comes from code that runs against public data on
demand, and `tests/` exists so a broken join, a flipped weighting, or a mis-parsed PDF fails
loudly instead of producing a plausible wrong number.
