# Notes: what was tried, what was dropped, what I got wrong

**Heading matching on a fixed zone at the top of the page.** First version looked for template
titles in the first 700 characters of each page. It missed ING, de Volksbank and ABN AMRO, whose
headings sit lower or are spelled "ESG3", and it passed contents pages as data pages. I replaced it
with line-based heading detection: a label at the start of a line, or a short line carrying a full
EBA title. Prose such as "Template 4 shows aggregated exposures..." must not count, and a test
(`test_prose_sentence_is_not_a_heading`) fails if it does. It did fail once: the title fallback
fired on that very sentence, and I only saw it because the test was written.

**Runaway runs.** A template's table pages were first taken until the next heading. After the last
template in a report that meant everything: Danske Bank's template 1 claimed 77 pages and Intesa's
template 10 claimed 19. I added a page cap per template and a stop at non-ESG templates, and the
sweep halves and doubles the caps (the mean moves by at most 0.2 points, so the cap is not driving anything).

**Counting any line with two numbers as a table row.** This let sentences with a year and a count
into the cell tally and pushed fill rates up. I tightened it to rows where cells are at least half
the tokens, which in turn lost rows with long labels (BBVA). Locating tables now uses the lenient
rule and scoring uses the strict one, and the lenient-scoring variant is in the sweep. The bank
order moves with this choice (rank correlation 0.78), which is a finding, not a bug.

**Label "Table N".** I matched "Table 12" as a template label and BTAR (template 9) appeared as
published at Bank of Ireland, off a liquidity table. A contents page with only some entries
ending in page numbers did the same. Fixed by dropping "Table" as a label (it is only stripped when
followed by "Template"/"ESG"), skipping lines that end in a page number or say "not applicable",
and detecting contents pages on the unfiltered count.

**A fill rate from a PDF cannot see an empty cell.** I considered detecting empty cells from the
word positions (pypdf can give them) and dropped it: layouts differ too much to infer a grid
without a table detector, and a table detector is not in the allowed libraries. The limit is on the
limits list instead, as the assumption that would break the conclusion.

**Scoring Belfius.** Its PDF points to an annex on the EBA data hub for templates 1 to 5. Scoring it
0 would say it does not disclose, which is false; excluding it silently would hide it. It is out of
the headline by a rule (no template found in the document), listed on the deck, and scored as zeros
in one sweep variant.

**Reporting date.** `sources.csv` gives 2024-12-31 for every bank. De Volksbank and Belfius are
FY2025 reports (the text says so), and my year detector, which takes the most frequent year on
the template pages, also tags Société Générale as 2025, probably from forward-looking targets. The
FY2024-only variant therefore drops Société Générale for a detector artefact, and I left it in
instead of patching the detector to the answer.

**An independent source for the cells.** I looked for one: the EBA Pillar 3 data hub is the right
one, and I did not reach it with the allowed tools (the hub serves XBRL and a browser interface). The
contents-list check validates template location only. I did not invent a substitute.

**Template 9.** BTAR is in no report, so including it only subtracts one ninth of the index for
everyone. I kept it out of the baseline and in the sweep.

**On tooling.** I use AI assistants to write and review code here. Every number in `results/` comes
from code that runs against the public PDFs, and `tests/` exists so a broken locator fails loudly
instead of giving a plausible wrong share.
