# The standard every module has to meet

This file exists because of two failures worth naming. The first: a module whose data file
claimed to be an extract from the WRI Global Power Plant Database and contained five invented
plants. Checked against the real database, 34,492 plants, zero matches. The second, milder but
more common: analyses that compute one number, draw one bar chart, and stop — correct, and
indistinguishable from an undergraduate exercise.

A module is not finished when it produces a number. It is finished when a hostile reviewer who
knows the field cannot dismiss it in one question.

## 1. The estimand comes first

Write, in one sentence, **what quantity you are estimating and what it would mean if you knew it
exactly.** Not "we analyse renewables" — "the average annual change in the renewable share, in
percentage points, over a five-year window, per member state."

If you cannot write that sentence, the analysis has no object and no amount of plotting will give
it one.

## 2. Every input is fetched, never typed

Data comes from a public endpoint, pulled by code, in the repository. No hand-made CSVs, no
numbers transcribed from a PDF, no "illustrative extract". If the only way to get the input is to
type it, the module does not get built — pick another question.

Record the endpoint, the access date, and the exact filter. A reviewer must be able to re-run the
fetch and get your table.

## 3. An estimate without an interval is an opinion

Any quantity fitted from data carries uncertainty, and the module states it:

- **Fit properly.** An endpoint-to-endpoint difference is not a trend; it is a statistic with a
  variance of its own that throws away every point in between. Fit the slope by least squares and
  report its standard error.
- **Report a confidence interval** on every headline number.
- **Say when the interval covers the thing you are comparing against.** "Country X is off track"
  is not a finding if the interval contains the required pace.

## 4. Out-of-sample, or it is curve-fitting

A projection that has never been tested against a year it did not see is an assumption wearing a
number. Every forward-looking module backtests: fit on data up to year *t*, predict year *t+k*,
measure the error against what actually happened, and **use the realised error to put an interval
on the forward projection.** Report the backtest error in the deck, not in a footnote.

## 5. Sensitivity to the arbitrary choices

Every module contains choices nobody can justify from first principles: the window length, the
threshold, the peer group. Vary them and show what moves. If the ranking is stable across
reasonable choices, say so and show the rank correlation. If it is not, that instability **is**
the finding.

## 6. Validation against something you did not fit

Where a second independent source measures the same thing, compare. Where none exists, say so
explicitly — that is a limitation, not an excuse to skip the section.

## 7. The limits section is load-bearing

Name the assumption that, if wrong, breaks the conclusion. Name what a sceptical reviewer would
attack first. A limits section that lists only mild caveats tells the reader you have not looked
for the real one.

## 8. The deck

Four to six pages. Question, method, result, validation and sensitivity, limits, and what you
would build next. A figure earns its place by showing something a sentence cannot: uncertainty,
a distribution, a disagreement between methods. A bar chart of five numbers is a table with
decoration.

Every number on every page traces to a file in `results/`. No number is typed into the deck.

## 9. One runnable check that fails loudly

`tests/` covers the arithmetic on fixed inputs, including the edge case that would silently
produce a plausible wrong answer. Each test's name says what breaks if it fails.

## 10. `notes.md` records what was abandoned

The approaches tried and dropped, and why. This is the part an interviewer probes, because it is
the part that cannot be generated from the result.
