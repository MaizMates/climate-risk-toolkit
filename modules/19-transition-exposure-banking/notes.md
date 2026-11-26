# Notes — what I tried, what I threw away, what I got wrong

**I started from the wrong edition.** The source list I had pointed at the 2024 transparency exercise (June 2024 reference date). The EBA page links a 2025 exercise, published with the December 2025 Risk Assessment Report. The estimand says "latest", so the headline is June 2025, and the 2024 file stays only as a year-on-year check. `fetch.py` now reads the EBA page and stops if it no longer links the 2025 database, so a later edition cannot go unnoticed.

**A country row for every country.** Eleven of the 25 countries have one or two banks in the exercise. A row for them is a row for one bank, which breaks the rule that no bank is named, and a bootstrap over one or two banks has no spread to resample. They are pooled into one group. Countries with three or four banks stay, flagged thin, and the README and deck make their claims on the seven with five or more. Three or four banks is still too few for a percentile bootstrap to be trusted; I did not test its coverage, and the flag is my only protection.

**One bootstrap over all banks.** The simplest interval resamples the 102 banks as one pool. I rejected it before writing code: a draw could hold five German banks and no Italian one, so the interval would include variation in country composition, which is not what the estimand varies. The interval resamples inside each country and keeps each country's bank count. This is the mistake module 05 made with fund holdings, and `test_a_stratum_of_identical_banks_has_no_sampling_variance` fails if the draw crosses countries.

**The test for the shared draw was wrong.** I first asserted that two mapping variants are positively correlated across replicates. With the banks I built they are negatively correlated, because the same draw raises one share and lowers the other. The check that holds is that a replicate takes one of only three values for two banks. A per-variant draw would give up to nine.

**19 of 19 is not calibration.** All 19 EBA section shares and 19 section NPL ratios fall inside my intervals. That reads like a calibration result, and it is not: the EBA table covers nearly the same banks, the correlation is 0.9999, and the mean difference is 0.05 points. It confirms that I extracted the right sheet and columns. It says nothing about whether a 95% bootstrap interval covers 95% of the time. The country comparison is the more informative one (12 of 13, with the largest miss at 5.8 points because the EBA counts foreign subsidiaries in the host country).

**Which non-performing column.** The NACE sheet has three: non-performing (`Perf_Status` 2), non-performing and defaulted (4), and subject to impairment (5). I use 2, which is the definition in the EBA's own NPL ratio. Column 4 totals EUR 210.5 bn against 212.5 bn, so it would not move the gap by anything visible. I did not carry it as a sweep dimension.

**Unweighted mean of bank shares.** I considered it as a second estimator and dropped it. A country's pooled share and its mean bank share differ a lot (Germany: pooled 64.9%, median bank 76.2%), which is a finding about the distribution and not a second estimate of the same thing. It stays as the tick marks on page 3 and is not reported as a headline.

**Stage 2, coverage and collateral.** The same database has them and they would say more about forward risk than the NPL stock does. They would also turn a module about where exposure sits into a module about credit quality. Left out.

**Sector divisions.** What I wanted was C20 (chemicals), C24 (basic metals) and the other energy-intensive manufacturing divisions, as in module 05. The exercise stops at sections. Banks' own Pillar 3 climate templates (template 1, by NACE division, with financed emissions) have them, but only as per-bank PDFs, and parsing 100 layouts is a module of its own (module 10 does this for the ESG templates). So the mapping stays coarse and says so.

**A rounding failure in my own test.** The first run of `test_extract_is_small_pseudonymous_and_complete` failed on two rows where the non-performing amount is EUR 0.0001 m above the gross amount, in the source. Tolerance set to 0.001 m. The data is as published; I did not correct it.

**On tooling.** I use AI assistants to write and review code here, the same way I use a linter. Every number comes from code that runs on public data, and the checks in `tests/` exist so a broken change fails loudly instead of producing a plausible figure.
