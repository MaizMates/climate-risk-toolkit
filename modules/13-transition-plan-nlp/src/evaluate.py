"""Score the cached LLM extractions against the expert labels on the 320 test paragraphs.

Headline: Claude Haiku 4.5, prompt A (the dataset card's definition, fixed before any reply was
read), two runs pooled. Interval: 4,000 paragraph resamples, one of the two runs drawn at random
per paragraph. Everything else is a sweep or a comparison. Writes results/eval.json.
"""
import json
import os
import numpy as np
from extract import parse
from metrics import bootstrap, counts, interval, kappa, nb_fit, nb_predict, pooled, prf

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
RES = os.path.join(HERE, "..", "results")
NB = 4000


def load():
    test = [json.loads(l) for l in open(os.path.join(RAW, "test.jsonl"))]
    train = [json.loads(l) for l in open(os.path.join(RAW, "train.jsonl"))]
    raw = [json.loads(l) for l in open(os.path.join(RES, "llm_raw.jsonl"))]
    return train, test, raw


def runs(raw, rows):
    """{(model, prompt, rep): label array over test rows}; an unparsable or errored reply counts as 'no' and is tallied."""
    idx = {r: i for i, r in enumerate(rows)}
    out, bad = {}, {}
    for d in raw:
        k = (d["model"], d["prompt"], d["rep"])
        out.setdefault(k, np.zeros(len(rows), int))
        bad.setdefault(k, 0)
        lab = None if d["reply"].startswith("ERROR") else parse(d["reply"])
        if lab is None:
            bad[k] += 1
        else:
            out[k][idx[d["row"]]] = lab
    for k, a in out.items():
        assert len(a) == len(rows) and sum(1 for d in raw if (d["model"], d["prompt"], d["rep"]) == k) == len(rows), f"incomplete run {k}"
    return out, bad


def summarise(y, reps, seed=0, n_boot=NB):
    tp, fp, fn, tn = pooled(y, reps)
    pr, rc, f1 = prf(tp, fp, fn)
    B = bootstrap(y, reps, n_boot, seed)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": pr, "recall": rc, "f1": f1,
            "accuracy": (tp + tn) / (tp + fp + fn + tn),
            "ci_precision": interval(B[:, 0]), "ci_recall": interval(B[:, 1]), "ci_f1": interval(B[:, 2]),
            "n_nan_resamples": int(np.isnan(B).any(1).sum())}


def main():
    train, test, raw = load()
    rows = [r["row"] for r in test]
    y = np.array([r["label"] for r in test])
    R, bad = runs(raw, rows)
    ytr = np.array([r["label"] for r in train])
    n = len(y)

    A = [R[("haiku", "A", 1)], R[("haiku", "A", 2)]]
    head = summarise(y, A)
    head.update({"n": n, "gold_positive": int(y.sum()), "prevalence": float(y.mean()), "model": "claude-haiku-4-5-20251001", "prompt": "A"})
    per_run = {f"rep{i + 1}": dict(zip(("precision", "recall", "f1"), prf(*counts(y, a)[:3]))) for i, a in enumerate(A)}

    # test-retest of the model against itself
    retest = {"agreement": float((A[0] == A[1]).mean()), "kappa": float(kappa(A[0], A[1])), "n_disagree": int((A[0] != A[1]).sum()),
              "kappa_vs_gold_rep1": float(kappa(A[0], y)), "kappa_vs_gold_rep2": float(kappa(A[1], y))}

    # sweep: prompt and model, one run each (run 1)
    sweep = {}
    for key in (("haiku", "A", 1), ("haiku", "B", 1), ("haiku", "C", 1), ("sonnet", "A", 1)):
        s = summarise(y, [R[key]], seed=1)
        s["kappa_vs_gold"] = float(kappa(R[key], y)); s["yes_rate"] = float(R[key].mean())
        sweep["%s/%s" % key[:2]] = s
    votes = np.array([R[("haiku", "A", 1)], R[("haiku", "B", 1)], R[("haiku", "C", 1)]])
    sweep["haiku vote (2 of 3 prompts)"] = summarise(y, [(votes.sum(0) >= 2).astype(int)], seed=1)
    sweep["haiku any prompt"] = summarise(y, [(votes.sum(0) >= 1).astype(int)], seed=1)
    sweep["haiku all prompts"] = summarise(y, [(votes.sum(0) >= 3).astype(int)], seed=1)
    f1s = {k: v["f1"] for k, v in sweep.items()}
    prs = {k: v["precision"] for k, v in sweep.items()}
    rcs = {k: v["recall"] for k, v in sweep.items()}

    # baselines
    nb = nb_fit([r["text"] for r in train], ytr)
    pnb = nb_predict(nb, [r["text"] for r in test])
    base_nb = summarise(y, [pnb], seed=2)
    base_nb["kappa_vs_gold"] = float(kappa(pnb, y))
    base_all = summarise(y, [np.ones(n, int)], seed=2)   # label everything yes
    # paired difference LLM minus naive Bayes: same paragraph resample for both (shared draw)
    rng = np.random.default_rng(3)
    d_f1, d_pr, d_rc = [], [], []
    A_ = np.array(A)
    for _ in range(NB):
        i = rng.integers(0, n, n); r = rng.integers(0, 2, n)
        a = prf(*counts(y[i], A_[r, i])[:3]); b = prf(*counts(y[i], pnb[i])[:3])
        d_pr.append(a[0] - b[0]); d_rc.append(a[1] - b[1]); d_f1.append(a[2] - b[2])
    diff = {"precision": [float(np.nanmean(d_pr)), *interval(np.array(d_pr))], "recall": [float(np.nanmean(d_rc)), *interval(np.array(d_rc))],
            "f1": [float(np.nanmean(d_f1)), *interval(np.array(d_f1))]}

    # sample size: interval width of precision and recall when only the first m paragraphs are scored
    lc = {}
    for m in (40, 80, 160, 320):
        s = summarise(y[:m], [a[:m] for a in A], seed=4, n_boot=2000)
        lc[m] = {"precision": s["precision"], "ci_precision": s["ci_precision"], "recall": s["recall"], "ci_recall": s["ci_recall"]}

    # prevalence shift: train split has 42.5% positives, test split 30.6%; precision at another prevalence from recall and FPR
    rec, fpr = head["recall"], head["fp"] / (head["fp"] + head["tn"])
    def prec_at(pi, rc_, fp_): return rc_ * pi / (rc_ * pi + fp_ * (1 - pi))
    Bp = bootstrap(y, A, NB, 5, stat=lambda yy, pp: (lambda c: (c[0] / (c[0] + c[2]), c[1] / (c[1] + c[3])))(counts(yy, pp)))
    prev = {}
    for pi in (0.1, float(y.mean()), float(ytr.mean()), 0.6):
        vals = Bp[:, 0] * pi / (Bp[:, 0] * pi + Bp[:, 1] * (1 - pi))
        prev[f"{pi:.3f}"] = {"precision": prec_at(pi, rec, fpr), "ci": interval(vals)}

    # error by paragraph length (terciles of characters)
    L = np.array([len(r["text"]) for r in test])
    cuts = np.quantile(L, [1 / 3, 2 / 3])
    terc = np.digitize(L, cuts)
    bylen = {}
    for t, name in enumerate(("short", "medium", "long")):
        m = terc == t
        c = pooled(y[m], [a[m] for a in A])
        pr, rc, f1 = prf(*c[:3])
        ci_f1 = interval(bootstrap(y[m], [a[m] for a in A], NB, 6)[:, 2])
        bylen[name] = {"n": int(m.sum()), "chars_max": int(L[m].max()), "positives": int(y[m].sum()), "precision": pr, "recall": rc, "f1": f1, "ci_f1": ci_f1,
                       "error_rate": (c[1] + c[2]) / (2 * m.sum())}

    # paragraphs where all five LLM runs agree with each other and disagree with the expert label
    allp = np.array([R[k] for k in sorted(R)])
    unanimous = (allp.min(0) == allp.max(0))
    contested = unanimous & (allp[0] != y)
    errors = {"n_unanimous": int(unanimous.sum()), "n_unanimous_wrong": int(contested.sum()),
              "unanimous_fp": int((contested & (y == 0)).sum()), "unanimous_fn": int((contested & (y == 1)).sum()),
              "rows_unanimous_wrong": [int(rows[i]) for i in np.where(contested)[0]]}

    cost = sum(d["cost_usd"] for d in raw)
    models = sorted({m for d in raw for m in d["resolved_model"]})
    out = {"headline": head, "per_run": per_run, "retest": retest, "sweep": sweep, "baseline_naive_bayes": base_nb,
           "baseline_all_yes": base_all, "diff_llm_minus_nb": diff, "sample_size": lc, "prevalence": prev,
           "by_length": bylen, "errors": errors, "unparsable": {f"{k[0]}/{k[1]}/{k[2]}": v for k, v in bad.items()},
           "train": {"n": len(train), "positive": int(ytr.sum()), "prevalence": float(ytr.mean())},
           "f1_range": [min(f1s.values()), max(f1s.values())], "precision_range": [min(prs.values()), max(prs.values())],
           "recall_range": [min(rcs.values()), max(rcs.values())], "resolved_models": models, "cost_usd": round(cost, 2),
           "n_calls": len(raw), "n_boot": NB}
    json.dump(out, open(os.path.join(RES, "eval.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("headline", "retest", "baseline_naive_bayes", "diff_llm_minus_nb", "by_length", "errors", "prevalence", "cost_usd")}, indent=1, default=str))
    for k, v in sweep.items():
        print(k, *(round(v[x], 3) for x in ("precision", "recall", "f1")), v["ci_f1"])


if __name__ == "__main__":
    main()
