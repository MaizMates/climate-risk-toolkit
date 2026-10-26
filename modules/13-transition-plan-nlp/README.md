# 13: Transition-plan NLP, how right is the LLM

**Claude Haiku 4.5, asked whether a climate paragraph from a corporate report states a climate commitment
or action, agrees with the expert label at precision 61.4% [51.7%, 70.3%] and recall 64.8% [54.9%, 74.1%]
(F1 63.0% [54.5%, 70.2%], 320 held-out paragraphs). A naive Bayes trained on 1,000 labelled paragraphs
scores F1 66.1%: the zero-shot model is no better. Changing the prompt moves precision from 52.5% to 86.5% and
recall from 45.9% to 84.7%, and F1 only between 60.0% and 65.8%.**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

Precision and recall of an LLM's yes/no extraction of "climate commitments and actions" from a
paragraph, measured against the expert label, on paragraphs from corporate annual and sustainability
reports. If I knew it exactly it would be the share of the model's "commitment" calls that experts also
call a commitment, and the share of expert-labelled commitments the model finds, for paragraphs drawn like
these.

`ROADMAP.md` asks for agreement with a hand-coded sample. The labels used here are not mine: they are the
public ClimateBERT expert annotations. Labelling a sample myself and then publishing the model's score
against it would be a second module (see Next); the labels here are independent of me and of the model, which
is the property that matters for evaluating the model. The label is binary and per paragraph, a proxy for
"stated transition-plan commitments": it is not the extraction of a target with a year and a scope.

## Data

`climatebert/climate_commitments_actions` (Webersinke et al., ClimateBERT; CC-BY-NC-SA-4.0): 1,000 training
and 320 test paragraphs, each labelled by experts as about climate commitments and actions or not, listed in
[`data/sources.csv`](data/sources.csv). `src/fetch.py` pulls both splits from the Hugging Face
datasets-server REST endpoint; `results/fetch_log.json` records the access date, row counts, label counts
and the SHA-256 of each split. The paragraphs are written to `data/raw/` and not committed, because of the
licence; the committed `results/llm_raw.jsonl` holds the model's replies keyed by row number. Test
prevalence is 30.6% positives (98 of 320), training 42.5%. Nothing is typed.

## Method

`src/extract.py` calls the model through the Claude Code CLI in print mode, tools, settings, skills and
session persistence off, one paragraph per call, 1,600 calls in all (USD 7.07, as logged by the CLI). The
resolved model IDs are in `results/eval.json`: `claude-haiku-4-5-20251001` and `claude-sonnet-5-5`. Three
prompts, written before any reply was read: A is the dataset card's own task definition (primary); B is terse
and has no definition; C is strict (a specific target, a pledge or a concrete action by the company itself).
Haiku on A ran twice, Haiku on B and C once, Sonnet on A once. The CLI exposes no temperature setting, so
sampling noise is measured, not controlled.

Replies are parsed as yes or no. Prompt B asks for "a commitment or an action" and the model sometimes
answers "Action" or "Commitment"; those are read as yes. No reply was unparsable after that (the count per
run is in `results/eval.json`).

## Uncertainty

Headline: 4,000 resamples of the 320 test paragraphs, the population the estimate belongs to. In each
resample every paragraph takes one of the two Haiku runs at random, so the model's own sampling noise is in
the interval, drawn per call because that is how it arises. The prompt is one choice for every paragraph and
is swept, not drawn. Labelling error is not in the interval and cannot be put there without an
inter-annotator figure for this dataset, which I did not find. The paragraphs carry no company identifier, so
paragraphs from one report are resampled as if independent; that makes the interval narrower than it should
be, by an amount I cannot measure.

At 320 paragraphs the precision interval is 18 points wide; at 80 it is 37 (`results/eval.json`,
`sample_size`).

## Backtest

Nothing in this module is forward-looking. The held-out test split, never used to choose a prompt or to
train the baseline, is the out-of-sample test; the prompts were fixed before any reply was read.

## Sensitivity

Seven variants (`results/eval.json`, `sweep`). Precision runs from 52.5% (any of three prompts says yes) to
86.5% (all three say yes), recall from 45.9% to 84.7%, F1 from 60.0% to 65.8%: the arbitrary choice
trades precision against recall; F1 moves by 5.8 points, less than half the width of any variant's F1 interval. Prompt B is the least
precise single run (53.2%, recall 83.7%), prompt C the most (84.2%, recall 49.0%). Sonnet 5.5 on prompt A
reaches F1 65.8% [58.2%, 72.6%] against 63.3% [55.1%, 70.6%] for Haiku on the same single run: not separable.
Labelling every paragraph yes scores F1 46.9%.

Precision depends on how many paragraphs are commitments: at the test mix (30.6%) it is 61.4%, at the
training mix (42.5%) 72.7% [66.3%, 79.1%], at 10% it is 28.5% [22.8%, 36.2%]. These come from the measured
recall and false-positive rate, which do not depend on the mix. A real report with few commitments gets mostly
false alarms. F1 by paragraph length tercile is 62.0%, 67.6% and 59.0%; the three intervals overlap, so I
claim no length effect.

## Validation

Against something I fitted and the model did not see: naive Bayes (unigram counts, Laplace smoothing) trained
on the 1,000 training paragraphs and scored on the same 320. F1 66.1% [58.7%, 73.0%]; precision 57.6%, recall
77.6%. On paired resamples, LLM minus naive Bayes is precision +3.8 points [-4.9, +12.9], recall -12.6
[-24.1, -0.9], F1 -3.0 [-11.4, +5.8]. Precision and F1 cannot be separated; the LLM finds fewer commitments.

Test-retest: the two Haiku runs on prompt A disagree on 19 of 320 paragraphs (kappa between them 0.86), while
their kappa against the experts is 0.47 and 0.45. The model is far more consistent with itself than with the
experts, so most of the error is systematic, not sampling noise.

Nineteen test paragraphs get the same answer from all five runs (two models, three prompts) and the opposite
of the expert label: 12 the experts call commitments and the model never does, 7 the reverse. Row numbers are
in `results/eval.json`. I did not adjudicate them.

## Limits

- **The expert label is taken as the truth.** If what experts call a commitment or action differs from what a
  supervisor means by a stated transition-plan commitment, the score measures agreement with a convention. A
  portion of the 19 unanimous disagreements may be label error, in which case the model is better than F1 63.0%;
  if they are a definition gap it is not. That cannot be settled with the same model, and it is the first
  thing a sceptic should attack.
- **Pre-selected paragraphs.** The dataset's paragraphs are already climate-related. A transition-plan PDF has
  to be cut into paragraphs and filtered first; that step is not measured here, and the precision figures
  at lower prevalence suggest it would matter.
- **Binary, not extraction.** No target, year, baseline or scope is extracted or scored.
- **One dataset, one family of models**, and aliases move: replies are cached so the numbers re-compute, but a
  re-run of `extract.py` will not reproduce them exactly.
- **Clustering** within company is unmodelled (above).

## Run it

```bash
cd modules/13-transition-plan-nlp
python3 src/fetch.py        # dataset -> data/raw/, results/fetch_log.json
python3 src/extract.py      # 1,600 LLM calls -> results/llm_raw.jsonl (needs the claude CLI; ~25 min; rerun until 0 left)
python3 src/evaluate.py     # metrics, intervals, sweeps -> results/eval.json
python3 tests/test_extraction.py
python3 src/deck.py         # five pages -> deck.pdf
```

`evaluate.py`, the tests and `deck.py` run from the committed replies without the CLI. [`notes.md`](notes.md)
records what I tried and dropped.
