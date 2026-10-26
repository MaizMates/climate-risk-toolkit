"""Agreement metrics, the paragraph bootstrap and a naive-Bayes baseline. Pure functions, no I/O."""
import re
import numpy as np

NAN = float("nan")


def counts(y, p):
    y, p = np.asarray(y), np.asarray(p)
    return int(((y == 1) & (p == 1)).sum()), int(((y == 0) & (p == 1)).sum()), int(((y == 1) & (p == 0)).sum()), int(((y == 0) & (p == 0)).sum())


def prf(tp, fp, fn, tn=0):
    """Precision, recall, F1 from counts; NaN when the denominator is empty (never 0, which would read as a result)."""
    pr = tp / (tp + fp) if tp + fp else NAN
    rc = tp / (tp + fn) if tp + fn else NAN
    f1 = 2 * pr * rc / (pr + rc) if pr == pr and rc == rc and pr + rc else NAN
    return pr, rc, f1


def kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    po = (a == b).mean()
    pe = sum((a == k).mean() * (b == k).mean() for k in (0, 1))
    return (po - pe) / (1 - pe) if pe < 1 else NAN


def pooled(y, reps):
    """Confusion counts summed over repeated runs: the expected metric when one run is drawn at random per paragraph."""
    tp = fp = fn = tn = 0
    for p in reps:
        a, b, c, d = counts(y, p)
        tp += a; fp += b; fn += c; tn += d
    return tp, fp, fn, tn


def bootstrap(y, reps, n_boot=4000, seed=0, stat=None):
    """Resample paragraphs (the population the estimate belongs to). In each resample every paragraph
    takes one of the repeated runs at random, so the model's own sampling noise is in the interval,
    drawn independently per call because it is. `stat(y, p)` returns a tuple; default (precision, recall, F1).
    Returns (n_boot, k) array; resamples with an empty denominator carry NaN."""
    y = np.asarray(y); R = np.asarray(reps)
    rng = np.random.default_rng(seed)
    n = len(y)
    stat = stat or (lambda yy, pp: prf(*counts(yy, pp)[:3]))
    out = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        r = rng.integers(0, len(R), n)
        out.append(stat(y[i], R[r, i]))
    return np.array(out, dtype=float)


def interval(x, level=0.95):
    x = x[~np.isnan(x)]
    a = (1 - level) / 2
    return float(np.quantile(x, a)), float(np.quantile(x, 1 - a))


TOKEN = re.compile(r"[a-z][a-z\-]+")


def nb_fit(texts, labels, alpha=1.0, min_df=2):
    """Multinomial naive Bayes on unigram counts with Laplace smoothing; prior = training prevalence."""
    docs = [TOKEN.findall(t.lower()) for t in texts]
    df = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    vocab = {w: i for i, w in enumerate(sorted(w for w, c in df.items() if c >= min_df))}
    labels = np.asarray(labels)
    M = np.zeros((2, len(vocab)))
    for d, l in zip(docs, labels):
        for w in d:
            if w in vocab:
                M[l, vocab[w]] += 1
    logp = np.log((M + alpha) / (M + alpha).sum(1, keepdims=True))
    prior = np.log(np.array([(labels == 0).mean(), (labels == 1).mean()]))
    return vocab, logp, prior


def nb_predict(model, texts):
    vocab, logp, prior = model
    out = []
    for t in texts:
        s = prior.copy()
        for w in TOKEN.findall(t.lower()):
            if w in vocab:
                s += logp[:, vocab[w]]
        out.append(int(s[1] > s[0]))
    return np.array(out)
