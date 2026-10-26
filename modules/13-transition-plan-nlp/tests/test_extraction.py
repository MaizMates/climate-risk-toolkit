"""Checks that fail loudly if the scoring, the bootstrap or the reply parser breaks.

Fixed inputs, no network and no model call.

    python3 tests/test_extraction.py
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import metrics as M
import extract as E


def test_precision_recall_known_counts():
    pr, rc, f1 = M.prf(8, 2, 8)
    assert (pr, rc) == (0.8, 0.5) and abs(f1 - 2 * 0.8 * 0.5 / 1.3) < 1e-12, "precision, recall or F1 formula is wrong"


def test_empty_denominator_is_nan_not_zero():
    pr, rc, f1 = M.prf(0, 0, 5)
    assert pr != pr and rc == 0 and f1 != f1, "a model that says 'no' to everything has undefined precision, not 0"


def test_counts_order_is_tp_fp_fn_tn():
    assert M.counts([1, 1, 0, 0], [1, 0, 1, 0]) == (1, 1, 1, 1)
    assert M.counts([1, 1, 0, 0], [1, 1, 1, 0]) == (2, 1, 0, 1), "fp and fn swapped would flip precision and recall"


def test_kappa_perfect_chance_and_constant():
    assert M.kappa([0, 1, 0, 1], [0, 1, 0, 1]) == 1
    assert abs(M.kappa([0, 0, 1, 1], [0, 1, 0, 1])) < 1e-12, "agreement at chance level must give kappa 0"
    assert M.kappa([1, 1, 1], [1, 1, 1]) != M.kappa([1, 1, 1], [1, 1, 1]), "both raters constant is undefined, not 1"


def test_pooled_sums_runs():
    y = [1, 0, 1, 0]
    assert M.pooled(y, [[1, 0, 1, 0], [0, 0, 0, 0]]) == (2, 0, 2, 4), "pooling must add the confusion counts of every run"


def test_bootstrap_perfect_model_has_degenerate_interval():
    y = np.array([1, 0] * 50)
    B = M.bootstrap(y, [y], n_boot=300, seed=1)
    assert M.interval(B[:, 0]) == (1.0, 1.0) and M.interval(B[:, 1]) == (1.0, 1.0), "a perfect model cannot get a wide interval"


def test_bootstrap_draws_one_run_per_paragraph():
    y = np.array([1] * 200)
    good, bad = y.copy(), 1 - y
    B = M.bootstrap(y, [good, bad], n_boot=400, seed=2, stat=lambda yy, pp: (pp.mean(),))
    m = B[:, 0]
    assert abs(m.mean() - 0.5) < 0.02, "runs must be mixed per paragraph"
    assert 0.03 < m.std() < 0.06, "per-paragraph run draws give SD about sqrt(.25/200)=0.035; a single run drawn for all would give 0.5"


def test_bootstrap_resamples_paragraphs_not_labels():
    y = np.array([1] * 30 + [0] * 70)
    p = y.copy()
    B = M.bootstrap(y, [p], n_boot=200, seed=3, stat=lambda yy, pp: (yy.mean(),))
    assert abs(B[:, 0].mean() - 0.3) < 0.02 and B[:, 0].std() > 0.03, "prevalence must vary across resamples like a binomial"


def test_parse_reply_variants():
    assert E.parse("Yes") == 1 and E.parse("no.") == 0 and E.parse("**Yes**") == 1 and E.parse("No, because it is background") == 0
    assert E.parse("Action") == 1 and E.parse("Commitment.") == 1 and E.parse("# Answer\n\nNo\n\nThis paragraph") == 0
    assert E.parse("Unclear") is None and E.parse("") is None, "an off-format reply must be counted as unparsable, not as no"


def test_naive_bayes_learns_a_separable_word():
    texts = ["we commit to net zero by 2040", "we pledge net zero targets", "the board met in march", "audit committee met twice"] * 3
    y = [1, 1, 0, 0] * 3
    m = M.nb_fit(texts, y)
    assert list(M.nb_predict(m, ["net zero pledge", "the committee met"])) == [1, 0]


def test_naive_bayes_ignores_words_outside_training_vocabulary():
    m = M.nb_fit(["alpha beta", "alpha beta", "gamma delta", "gamma delta"], [1, 1, 0, 0])
    assert list(M.nb_predict(m, ["zzz qqq"])) in ([0], [1]) and M.nb_predict(m, ["alpha zzz"])[0] == 1


def test_committed_headline_matches_recomputation():
    raw, test = os.path.join(HERE, "..", "results", "llm_raw.jsonl"), os.path.join(HERE, "..", "data", "raw", "test.jsonl")
    ev = os.path.join(HERE, "..", "results", "eval.json")
    if not (os.path.exists(raw) and os.path.exists(test) and os.path.exists(ev)):
        print("  skipped (run fetch.py, extract.py and evaluate.py first)")
        return
    gold = {d["row"]: d["label"] for d in map(json.loads, open(test))}
    reps = [[], []]
    for d in map(json.loads, open(raw)):
        if (d["model"], d["prompt"]) == ("haiku", "A"):
            reps[d["rep"] - 1].append((d["row"], E.parse(d["reply"])))
    tp = fp = fn = 0
    for r in reps:
        assert len(r) == len(gold) == 320, "each run must cover every test paragraph"
        for row, l in r:
            tp += l == 1 and gold[row] == 1; fp += l == 1 and gold[row] == 0; fn += l == 0 and gold[row] == 1
    h = json.load(open(ev))["headline"]
    assert (tp, fp, fn) == (h["tp"], h["fp"], h["fn"]), "results/eval.json does not match the cached replies"


if __name__ == "__main__":
    names = [n for n in sorted(globals()) if n.startswith("test_")]
    for n in names:
        globals()[n]()
        print("ok  ", n)
    print(f"{len(names)} tests passed")
