# Notes: what was tried, what was dropped, what I got wrong along the way

**Wikidata for company emissions.** The roadmap asks for public company emissions, and the first
source I tried was Wikidata's carbon footprint property (P5991). It returns 4,836 statements for
681 items, but products, public agencies and companies share it, many statements carry no year, and
scope is a free qualifier that is often missing (one company lists 612,401 and 52 tCO2e under the
same method with no scope). A total I cannot attribute to Scope 1, 2 or 3 is not a PCAF input.
Dropped.

**The EPA endpoint.** The documented `ghg.pub_dim_facility` form returns a parse error, and
`enviro.epa.gov` blocks the request at the firewall. `data.epa.gov/efservice/pub_dim_facility`
without the schema prefix works. The row ranges are inclusive, so every page boundary repeats a
row: 11,284 facility rows for 11,281 facilities, 26,277 emission rows for the 26,272 the count call
reports. `fetch.py` dedupes on the row key and `test_fetch.py` has a case for it, because the
duplicates would have added emissions without any error showing.

**Which sector label.** My first version took the sector from the dominant NAICS code of the
parent's emitting facilities. Alphabet came out in solar power (221114) because its one reporting
facility is classed that way, with 15.9 kt over USD 307 bn of revenue, and the within-sector spread
was set by facility labels, not by what the borrowers do. I switched to the SIC code in the SEC
submissions, which is the firm's own classification and what a lender would hold. The facility NAICS
stays in `borrowers.csv`.

**EVIC.** PCAF's listed-company attribution divides by enterprise value including cash. Neither
source has market capitalisation. I used equity plus debt at book value, the PCAF business-loan
form, and said so. It makes the factors larger for firms whose market value exceeds book.

**A typed or "illustrative" loan book.** Rejected. The roadmap says "synthetic but realistic", and
the repository's rule is that no input is typed. The loan book is the only simulated element and
it is drawn by seeded code from the fetched borrowers. The cost is that no USD figure here
describes a real bank, and I say so on page 1.

**The first interval was too narrow for the case that matters.** The peer-resample interval covers
97% of random books at the 40/40/20 mix. At the all-estimated mix I expected the same and got
63.7%: the truth sat below the interval in 109 of 300 books. The cause is in `results/`: intensity
falls with size inside a sector (slope -0.32), so the sector average overstates the large firms
that dominate the sum, and a resample of peers reproduces that bias instead of exposing it. I did
not tune the interval until it covered. The headline for that case is the interval from the
realised error, and the peer interval is kept next to it.

**Pool and book from the same population.** Letting the sector factor use the borrower it is
applied to would have flattered every number here. Each book is a random 100; the other 110 set the
factors. The cost is a smaller peer group, and the minimum-peers sweep (3, 5, 10) moves the median
by 0.013.

**Ratio of sums versus median intensity.** The ratio of sums is the sector's own intensity and
is dominated by utilities; the median is what a typical firm looks like and gives 0.87 of the reported total
against 0.95. I kept the ratio of sums as the base because it reproduces the sector total, which is
what a sector emission factor is, and report the median in the sweep.

**Not done.** A log-log fit of intensity on revenue within sector would address the size slope
directly. I left it because it is not PCAF's method, and the module's point is the error of the
method as the standard describes it. Scope 2 is also absent: GHGRP is direct emissions only.

**On tooling.** I use AI assistants to write and review code here. Every number in `results/`
comes from code that runs against the two public endpoints, and `tests/` fails if a boundary row is
double counted, a shared factor error is drawn per line, or the book is resampled.
