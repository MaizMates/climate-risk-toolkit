# 10: Disclosure quality index, Pillar 3 ESG templates

**Across 13 banks' published Pillar 3 reports, the mean ESG-template completeness index is 76.1%
[65.0%, 83.6%]. Twelve of the 13 publish all nine mandatory templates, so presence is 96.6% and
says almost nothing; the differences between banks sit in how many cells carry a value, from
44.5% (de Volksbank, a FY2025 report that drops templates 6 to 10) to 99.2% (Nordea).**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

For each bank, the mean over the nine mandatory EBA Pillar 3 ESG templates (1 to 8 and 10) of the
share of cells that show a value among the cells that show a value or a placeholder ("-", "n/a",
"not available"), scored 0 for a template that is not in the report. The headline is the mean of
that index over the banks scored. If I knew it exactly it would be the average share of the
prescribed ESG table that a bank actually fills in its published report. Template 9 (BTAR) is
reported separately: in 13 reports it appears in none (4 state they omit it, 9 are silent).

## Data

Fourteen PDFs, one report per bank, listed in [`data/sources.csv`](data/sources.csv) with the date
I verified each link by hand. `src/fetch.py` downloads them (it needs a browser User-Agent and a
Referer: UniCredit returns 403 without them); `results/fetch_log.json` records URL, access date,
HTTP status, size and SHA-256 of each. The PDFs are not committed. `src/extract.py` reads the text
with pypdf. Nothing is typed.

Belfius is listed but scored out: its report says templates 1 to 5 sit in an annex on the EBA
Pillar 3 data hub, and its PDF holds none of the data tables. Two reports are FY2025, not the
FY2024 that `sources.csv` lists (de Volksbank and Belfius); the sweep drops documents whose
template pages mostly mention a year other than 2024.

## Method

`src/disclosure.py`. A template starts at a heading line (a label such as "Template 4", "Tabella 4"
or "ESG3", or the full EBA title) and runs over the table pages that follow, until another heading,
a cap of 3 to 20 pages by template, or a page that is not a table. Contents lists, sentences about a
template and "not applicable" lines are not headings. Cells are numeric tokens (years excluded) and
placeholders on table-like lines. The score of a template is numeric over numeric plus placeholder.

## Uncertainty

The bank index is a census of nine templates, so it carries only measurement error, not sampling
error. I measured that error on 200 generated tables with a known fill rate, in five layouts,
rendered to PDF and read back (`src/synth.py`, labelled synthetic wherever it appears): the parser
overstates fill by 3.6 points on average, slope 0.92, residual SD 2.3 points. The headline
interval resamples banks (4,000 resamples of the population the mean belongs to: banks like these) and, per
resample, draws one parser residual per bank, shared by all of that bank's templates. Banks alone give
[67.0%, 85.1%], parser error alone [73.2%, 75.3%]: the spread between banks dominates, with n = 13.
Correcting for the parser bias gives 74.5%.

## Backtest

Nothing in this module is forward-looking. The index describes one published report, so there is no
projection to test against a later year.

## Sensitivity

Fourteen variants in `results/index.json`. The mean index moves between 67.9% (zero counted as
blank) and 96.6% (presence only, fill ignored). Excluding presence-only, the lowest Spearman
correlation of bank ranks with the baseline is 0.78 (fill counted on rows with long labels): bank
order depends on how cells are counted. Presence-only has a rank correlation of -0.09 with the
baseline, because presence is saturated and carries no ranking information. Including template 9
gives 68.5%; dropping templates a bank says it omits gives 78.8%.

## Validation

Banks' own contents lists print a page for each template: 34 of 37 agree with the page I located,
within one page, after a constant printed-to-PDF offset per bank. That offset is estimated from the
same pairs, so the check is not fully out of sample. It validates where a template is, not how
full it is. No second source for the cells was reached; the EBA Pillar 3 data hub is the natural one.

## Limits

- **A blank cell leaves no token in the PDF text.** The index sees placeholders, not empty cells, so
  a bank that leaves cells empty scores as complete, and ABN AMRO, NWB Bank and Nordea at 97% to 99% may
  simply print no dash. The index is a lower bound on incompleteness. This is the assumption that
  would break the conclusion; the test is the data hub, where an empty field is a field.
- **13 hand-picked banks**, not a draw from euro-area banks. The interval covers banks like these.
- **Row codes and footnote digits are counted as values** on some layouts (sweep: excluding leading
  row codes lowers the mean by 5.8 points). The parser test covers five synthetic layouts, fewer
  than the real ones.
- **Periods differ**, and Omnibus relief removed templates 6 to 10 for one bank. Applicability of
  templates 6 to 10 differs by bank; a stated omission is scored 0 in the baseline.

## Run it

```bash
cd modules/10-disclosure-quality-index
python3 src/fetch.py        # download the 14 PDFs -> data/cache/, results/fetch_log.json
python3 src/extract.py      # page text -> data/cache/
python3 src/synth.py        # parser test on synthetic tables -> results/parser_test.json
python3 src/index.py        # locate, score, bootstrap, sweeps -> results/
python3 tests/test_disclosure.py
python3 src/deck.py         # five pages -> deck.pdf
```

[`notes.md`](notes.md) records what I tried and dropped.
