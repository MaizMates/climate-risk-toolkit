"""PCAF financed emissions for a simulated bank book of real borrowers, with the data-quality score.

Borrowers, their emissions and their balance sheets are real (results/borrowers.csv, from fetch.py).
What is simulated, and labelled so everywhere, is the bank: which borrowers it lends to and how
much. Reported emissions (GHGRP) play the role of the truth that a bank holding only a score 4 or 5
estimate would never see, so the estimate can be tested against it. Sector factors are fitted on
borrowers that are not in the book.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")

BASE = {"year": 2023, "digits": 2, "min_peers": 5, "estimator": "ratio", "n_loans": 100,
        "share_lo": 0.01, "share_hi": 0.05, "mix": (0.4, 0.4, 0.2)}
HEADLINE_SEED = 2026
N_BOOKS = 300
B_CAL, B_HEAD = 400, 4000


def attribution_factor(outstanding, equity, debt):
    """PCAF business-loan attribution: outstanding amount over total equity plus debt."""
    return outstanding / (equity + debt)


def load_population(year, path=None):
    d = pd.read_csv(path or os.path.join(RESULTS, "borrowers.csv"), dtype={"sic": str, "naics": str})
    d = d[d.year == year].reset_index(drop=True)
    n0 = len(d)
    ok = (d.revenue > 0) & (d.assets > 0) & (d.equity > 0) & (d.debt > 0) & (d.scope1_t > 0) & d.sic.notna()
    return d[ok].reset_index(drop=True), n0


def assign_scores(revenue, mix):
    """Largest revenues report (score 2), the next tier is estimated from revenue (4), the rest from assets (5)."""
    n = len(revenue)
    n2, n4 = int(round(mix[0] * n)), int(round(mix[1] * n))
    rank = np.argsort(-np.asarray(revenue), kind="stable")
    s = np.full(n, 5)
    s[rank[:n2]] = 2
    s[rank[n2:n2 + n4]] = 4
    return s


def wdqs(scores, outstanding):
    """PCAF weighted data-quality score: outstanding-weighted mean score."""
    o = np.asarray(outstanding, float)
    return float((np.asarray(scores) * o).sum() / o.sum())


def factor(e, x, estimator):
    r = e / x
    return float(e.sum() / x.sum()) if estimator == "ratio" else float(np.median(r))


def resolve_groups(sic_pool, sic_lines, digits, min_peers):
    """For each line the finest SIC prefix (from `digits` down to 2, then pooled) with enough pool peers."""
    levels = [d for d in (4, 3, 2) if d <= digits]
    out = []
    for s in sic_lines:
        for dg in levels:
            peers = np.flatnonzero(np.char.startswith(sic_pool, s[:dg]))
            if len(peers) >= min_peers:
                out.append((f"{dg}:{s[:dg]}", peers))
                break
        else:
            out.append(("pooled", np.arange(len(sic_pool))))
    return out


def simulate_book(pop, rng, cfg):
    n = cfg["n_loans"]
    idx = rng.permutation(len(pop))
    book, pool = pop.iloc[idx[:n]].reset_index(drop=True), pop.iloc[idx[n:]].reset_index(drop=True)
    book["outstanding"] = rng.uniform(cfg["share_lo"], cfg["share_hi"], n) * book.debt
    book["score"] = assign_scores(book.revenue.values, cfg["mix"])
    book["af"] = attribution_factor(book.outstanding, book.equity, book.debt)
    return book, pool


def point_estimate(book, pool, cfg):
    """Reported lines use the reported figure; the others use a pool sector factor times revenue or assets."""
    groups = resolve_groups(pool.sic.values.astype(str), book.sic.values.astype(str), cfg["digits"], cfg["min_peers"])
    est = book.scope1_t.values.copy()
    for i, (key, peers) in enumerate(groups):
        s = book.score[i]
        if s == 2:
            continue
        col = "revenue" if s == 4 else "assets"
        est[i] = book[col][i] * factor(pool.scope1_t.values[peers], pool[col].values[peers], cfg["estimator"])
    return est, groups


def interval(book, pool, cfg, rng, B, active=(4, 5)):
    """Predictive draws of the book's true financed emissions.

    One peer resample per sector group and replicate sets that sector's factor for every line in it
    (the shared error); each line then draws its own firm-level departure from the sector factor
    (the independent error). Only the pool of the sector the line belongs to is resampled; the book
    itself is the population being estimated and is not resampled.
    """
    est, groups = point_estimate(book, pool, cfg)
    af = book.af.values
    tot = np.full(B, float((af * est)[~book.score.isin(active)].sum()))
    by_group = {}
    for i, (key, peers) in enumerate(groups):
        if book.score[i] in active:
            by_group.setdefault(key, (peers, []))[1].append(i)
    E = pool.scope1_t.values
    for key, (peers, lines) in by_group.items():
        m = len(peers)
        draw = rng.integers(0, m, (B, m))
        for col, sc in (("revenue", 4), ("assets", 5)):
            ls = [i for i in lines if book.score[i] == sc]
            if not ls:
                continue
            X = pool[col].values[peers]
            e = E[peers]
            if cfg["estimator"] == "ratio":
                fb = e[draw].sum(1) / X[draw].sum(1)
            else:
                fb = np.median(e[draw] / X[draw], axis=1)
            rho = (e / X) / factor(e, X, cfg["estimator"])
            own = rng.integers(0, m, (B, len(ls)))
            for k, i in enumerate(ls):
                tot += af[i] * book[col][i] * fb * rho[own[:, k]]
    return tot


def run_book(pop, seed, cfg, B=0, active=(4, 5)):
    rng = np.random.default_rng(seed)
    book, pool = simulate_book(pop, rng, cfg)
    est, _ = point_estimate(book, pool, cfg)
    fe_est = float((book.af * est).sum())
    fe_true = float((book.af * book.scope1_t).sum())
    out = {"book": book, "est": est, "fe_est": fe_est, "fe_true": fe_true}
    if B:
        draws = interval(book, pool, cfg, rng, B, active)
        out["draws"] = draws
        out["lo"], out["hi"] = (float(v) for v in np.percentile(draws, [2.5, 97.5]))
    return out


def score_distribution(book, est):
    fe = book.af.values * est
    rows = []
    for s in (1, 2, 3, 4, 5):
        m = (book.score == s).values
        rows.append({"score": s, "lines": int(m.sum()),
                     "share_outstanding": float(book.outstanding[m].sum() / book.outstanding.sum()),
                     "share_financed": float(fe[m].sum() / fe.sum())})
    return rows


def main():
    pop, n0 = load_population(BASE["year"])
    cfg = dict(BASE)
    res = {"config": {k: list(v) if isinstance(v, tuple) else v for k, v in cfg.items()},
           "population": {"parents_with_filings": n0, "usable": len(pop)}}

    h = run_book(pop, HEADLINE_SEED, cfg, B_HEAD)
    book, est = h["book"], h["est"]
    res["headline"] = {
        "seed": HEADLINE_SEED, "n_loans": len(book), "outstanding_usd_m": float(book.outstanding.sum() / 1e6),
        "financed_t": h["fe_est"], "lo": h["lo"], "hi": h["hi"], "truth_t": h["fe_true"],
        "truth_inside": bool(h["lo"] <= h["fe_true"] <= h["hi"]),
        "intensity_t_per_usd_m": h["fe_est"] / (book.outstanding.sum() / 1e6),
        "intensity_lo": h["lo"] / (book.outstanding.sum() / 1e6),
        "intensity_hi": h["hi"] / (book.outstanding.sum() / 1e6),
        "wdqs": wdqs(book.score, book.outstanding),
        "score_distribution": score_distribution(book, est),
        "top5_share_of_financed": float(np.sort(book.af.values * est)[::-1][:5].sum() / h["fe_est"]),
        "sectors": int(book.sic.str[:2].nunique())}
    res["headline"]["half_width_pct"] = float(100 * (h["hi"] - h["lo"]) / 2 / h["fe_est"])

    # which score class drives the width
    widths = {}
    for name, act in (("score 4", (4,)), ("score 5", (5,)), ("both", (4, 5))):
        d = run_book(pop, HEADLINE_SEED, cfg, B_HEAD, act)
        widths[name] = {"lo": d["lo"], "hi": d["hi"], "width": d["hi"] - d["lo"]}
    res["width_by_score"] = widths

    # line-level error of the estimators against reported emissions, lines never used to fit factors
    errs = []
    for s in range(N_BOOKS):
        b = run_book(pop, 10_000 + s, cfg)
        bk, e = b["book"], b["est"]
        m = (bk.score != 2).values
        errs += [{"score": int(sc), "log_ratio": float(np.log(ei / ti))}
                 for sc, ei, ti in zip(bk.score[m], e[m], bk.scope1_t[m])]
    er = pd.DataFrame(errs)
    res["line_error"] = {str(s): {"n": int(len(g)), "median_ratio": float(np.exp(g.log_ratio.median())),
                                  "q05_ratio": float(np.exp(g.log_ratio.quantile(.05))),
                                  "q95_ratio": float(np.exp(g.log_ratio.quantile(.95))),
                                  "share_within_factor_2": float((g.log_ratio.abs() < np.log(2)).mean()),
                                  "share_within_factor_10": float((g.log_ratio.abs() < np.log(10)).mean()),
                                  "log10_sd": float(g.log_ratio.std() / np.log(10))}
                         for s, g in er.groupby("score")}
    res["line_error_hist"] = {str(s): np.histogram(g.log_ratio / np.log(10), bins=np.linspace(-3, 3, 25))[0].tolist()
                              for s, g in er.groupby("score")}
    res["hist_edges_log10"] = np.linspace(-3, 3, 25).tolist()

    # calibration: does the interval cover the realised total across many random books
    def calibrate(cf):
        cal = []
        for s in range(N_BOOKS):
            b = run_book(pop, 20_000 + s, cf, B_CAL)
            cal.append({"est": b["fe_est"], "truth": b["fe_true"], "lo": b["lo"], "hi": b["hi"]})
        c = pd.DataFrame(cal)
        c["covered"] = (c.lo <= c.truth) & (c.truth <= c.hi)
        c["ratio"] = c.est / c.truth
        out = {"books": N_BOOKS, "coverage": float(c.covered.mean()),
               "truth_above_interval": int((c.truth > c.hi).sum()), "truth_below_interval": int((c.truth < c.lo).sum()),
               "median_est_over_truth": float(c.ratio.median()),
               "q05_est_over_truth": float(c.ratio.quantile(.05)), "q95_est_over_truth": float(c.ratio.quantile(.95)),
               "q025_est_over_truth": float(c.ratio.quantile(.025)), "q975_est_over_truth": float(c.ratio.quantile(.975)),
               "median_halfwidth_pct": float((100 * (c.hi - c.lo) / 2 / c.est).median())}
        return out, c[["est", "truth", "lo", "hi"]].round(1).to_dict("records")
    res["calibration"], res["calibration_points"] = calibrate(cfg)

    # the same book when nothing is reported: every line is a score 4 or 5 estimate
    cfg0 = {**cfg, "mix": (0.0, 2 / 3, 1 / 3)}
    h0 = run_book(pop, HEADLINE_SEED, cfg0, B_HEAD)
    res["no_reported"] = {"financed_t": h0["fe_est"], "lo": h0["lo"], "hi": h0["hi"], "truth_t": h0["fe_true"],
                          "truth_inside": bool(h0["lo"] <= h0["fe_true"] <= h0["hi"]),
                          "wdqs": wdqs(h0["book"].score, h0["book"].outstanding),
                          "half_width_pct": float(100 * (h0["hi"] - h0["lo"]) / 2 / h0["fe_est"])}
    res["no_reported"]["calibration"], res["no_reported"]["calibration_points"] = calibrate(cfg0)
    # interval from the realised error: truth = estimate / (estimate over truth) across the random books
    for blk, cal_ in ((res["headline"], res["calibration"]), (res["no_reported"], res["no_reported"]["calibration"])):
        blk["empirical_lo"] = blk["financed_t"] / cal_["q975_est_over_truth"]
        blk["empirical_hi"] = blk["financed_t"] / cal_["q025_est_over_truth"]
        blk["empirical_truth_inside"] = bool(blk["empirical_lo"] <= blk["truth_t"] <= blk["empirical_hi"])
    # intensity falls with size inside a sector, which the sector average ignores
    lr, li = np.log(pop.revenue), np.log(pop.scope1_t / pop.revenue)
    g = pop.sic.str[:2]
    res["size_slope"] = {"within_sector_slope_log_intensity_on_log_revenue":
                         float(np.polyfit(lr - lr.groupby(g).transform("mean"), li - li.groupby(g).transform("mean"), 1)[0]),
                         "within_sector_correlation":
                         float(np.corrcoef(lr - lr.groupby(g).transform("mean"), li - li.groupby(g).transform("mean"))[0, 1])}

    # sweeps: median est/truth over books and the headline book's estimate
    def sweep(label, **kw):
        cf = {**cfg, **kw}
        p = pop if cf["year"] == cfg["year"] else load_population(cf["year"])[0]
        r = [run_book(p, 30_000 + s, cf) for s in range(100)]
        ratio = np.array([x["fe_est"] / x["fe_true"] for x in r])
        hb = run_book(p, HEADLINE_SEED, cf)
        le = np.concatenate([np.log10(x["est"][(x["book"].score != 2).values] /
                                      x["book"].scope1_t.values[(x["book"].score != 2).values]) for x in r])
        return {"label": label, "line_within_factor_2": float((np.abs(le) < np.log10(2)).mean()),
                "line_median_abs_log10": float(np.median(np.abs(le))), "headline_book_financed_t": hb["fe_est"],
                "headline_book_truth_t": hb["fe_true"],
                "median_est_over_truth": float(np.median(ratio)),
                "q05": float(np.quantile(ratio, .05)), "q95": float(np.quantile(ratio, .95)),
                "mean_financed_t": float(np.mean([x["fe_est"] for x in r])),
                "mean_truth_t": float(np.mean([x["fe_true"] for x in r]))}
    sw = {"base": [sweep("base")]}
    sw["sector_digits"] = [sweep(f"SIC {d} digits", digits=d) for d in (2, 3, 4)]
    sw["min_peers"] = [sweep(f"min peers {m}", min_peers=m) for m in (3, 5, 10)]
    sw["factor"] = [sweep("ratio of sums", estimator="ratio"), sweep("median intensity", estimator="median")]
    sw["reporting_share"] = [sweep(f"{int(100 * a)}% reported", mix=(a, (1 - a) * 2 / 3, (1 - a) / 3))
                             for a in (0.0, 0.2, 0.4, 0.6, 0.8)]
    sw["method_mix"] = [sweep("all revenue-based (4)", mix=(0, 1, 0)), sweep("all asset-based (5)", mix=(0, 0, 1))]
    sw["year"] = [sweep(f"{y}", year=y) for y in (2021, 2022, 2023)]
    sw["book_size"] = [sweep(f"{n} loans", n_loans=n) for n in (50, 100, 150)]
    sw["loan_share"] = [sweep("1-5% of debt (base)"), sweep("5-20% of debt", share_lo=0.05, share_hi=0.20)]
    res["sweeps"] = sw
    res["sweep_swing"] = {k: {"min_ratio": min(r["median_est_over_truth"] for r in v),
                              "max_ratio": max(r["median_est_over_truth"] for r in v),
                              "line_within_2x_min": min(r["line_within_factor_2"] for r in v),
                              "line_within_2x_max": max(r["line_within_factor_2"] for r in v),
                              "swing": max(r["median_est_over_truth"] for r in v) -
                                       min(r["median_est_over_truth"] for r in v)}
                          for k, v in sw.items() if k != "base"}

    # coverage of the match against all reported US direct emissions
    log = json.load(open(os.path.join(RESULTS, "fetch_log.json")))
    tot = log["years"][str(cfg["year"])]["direct_emissions_t"]
    res["match_coverage"] = {"matched_scope1_t": float(pop.scope1_t.sum()), "ghgrp_total_t": tot,
                             "share": float(pop.scope1_t.sum() / tot)}
    res["population"]["by_year"] = {str(y): int(len(load_population(y)[0])) for y in (2021, 2022, 2023)}
    book_out = book.assign(estimate_t=est, financed_t=book.af * est, financed_true_t=book.af * book.scope1_t)
    book_out[["name", "cik", "sic", "score", "outstanding", "af", "revenue", "assets", "scope1_t",
              "estimate_t", "financed_t", "financed_true_t"]].to_csv(os.path.join(RESULTS, "headline_book.csv"), index=False)
    json.dump(res, open(os.path.join(RESULTS, "financed.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("headline", "calibration", "no_reported", "size_slope", "sweep_swing", "width_by_score", "match_coverage")}, indent=1)[:6000])


if __name__ == "__main__":
    main()
