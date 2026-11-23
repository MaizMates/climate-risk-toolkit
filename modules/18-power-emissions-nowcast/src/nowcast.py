"""Nowcast of calendar-year EU27 power-sector emissions from the first m months, and its measured error.

Three benchmarks, from the simplest up, each using only information available after month m of year y:
  last year      E(y-1)
  share of year  YTD(y, m) divided by the mean share of the year that months 1..m took in earlier years
  regression     YTD(y, m) plus, for months m+1..12, emissions predicted from generation by source:
                 emissions = sum_s b_s * generation_s, b fitted by least squares on the months of earlier years;
                 generation of month t = last year's month t scaled by this year's YTD / last year's YTD, per source

Pseudo out-of-sample backtest on every complete year from 2018 (history: complete years before y, latest Ember
vintage, so revisions are not replayed). The interval on the current-year nowcast is built from the backtest
errors, not from the in-sample fit. The unit of resampling is the backtest year, drawn once for all methods and
horizons, because a year's shock is shared by all of them.

    python3 src/nowcast.py
"""
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA, RES = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")
HORIZONS = (3, 6, 9)
LATEST_H = 10                      # months available for the current year; reported as an extra horizon
BT_FIRST = 2018
METHODS = ("last year", "share of year", "regression")
CLEAN = ["Bioenergy", "Hydro", "Nuclear", "Other renewables", "Solar", "Wind"]
FOSSIL = ["Coal", "Gas", "Other fossil"]
SEED, NBOOT = 18, 4000
BASE = dict(target="Total generation", window=None, exclude=(), share="mean share", regsrc="all", proj="scaled")


# ---------- data

def load(path=None):
    """Ember EU27 monthly table -> {(series, source): DataFrame year x month 1..12}."""
    d = pd.read_csv(path or os.path.join(DATA, "eu_monthly.csv"))
    d["year"], d["month"] = d.Date.str[:4].astype(int), d.Date.str[5:7].astype(int)
    out = {}
    for col, name in (("emis_mt", "emis"), ("gen_twh", "gen")):
        for s, g in d.groupby("source"):
            out[(name, s)] = g.pivot(index="year", columns="month", values=col).reindex(columns=range(1, 13))
    return out


def ytd(T, y, m):
    v = T.loc[y, 1:m].values
    if len(v) != m or np.isnan(v).any():
        raise ValueError(f"year {y} lacks months 1..{m}")
    return float(v.sum())


def annual(T, y):
    return ytd(T, y, 12)


def complete_years(T):
    return [int(y) for y in T.index if T.loc[y].notna().all()]


def train_years(T, y, window=None, exclude=()):
    ys = [yy for yy in complete_years(T) if yy < y and yy not in exclude]
    return ys[-window:] if window else ys


# ---------- the three benchmarks

def m_last_year(T, y, m, **kw):
    return annual(T, y - 1)


def m_share(T, y, m, window=None, exclude=(), share="mean share", **kw):
    ys = train_years(T, y, window, exclude)
    if share == "yoy":              # last year's total scaled by this year's YTD over last year's YTD
        return annual(T, y - 1) * ytd(T, y, m) / ytd(T, y - 1, m)
    s = [ytd(T, yy, m) / annual(T, yy) for yy in ys]
    return ytd(T, y, m) / float(np.mean(s))


def fit_factors(T, G, srcs, years):
    """Least squares, no intercept: emissions of a month on generation by source. Returns (b, n obs)."""
    X = np.array([[G[s].loc[yy, mm] for s in srcs] for yy in years for mm in range(1, 13)])
    t = np.array([T.loc[yy, mm] for yy in years for mm in range(1, 13)])
    b = np.linalg.lstsq(X, t, rcond=None)[0]
    return b, len(t)


def m_regression(T, y, m, G=None, regsrc="all", proj="scaled", window=None, exclude=(), **kw):
    srcs = {"fossil": FOSSIL, "grouped": ["Fossil", "Clean"]}.get(regsrc, FOSSIL + CLEAN)
    ys = train_years(T, y, window, exclude)
    b, _ = fit_factors(T, G, srcs, ys)
    rest = 0.0
    for s, bs in zip(srcs, b):
        sc = ytd(G[s], y, m) / ytd(G[s], y - 1, m) if proj == "scaled" and ytd(G[s], y - 1, m) > 0 else 1.0
        rest += bs * sc * float(G[s].loc[y - 1, m + 1:12].sum())
    return ytd(T, y, m) + rest


def nowcasts(C, y, m, cfg):
    T = C[("emis", cfg["target"])]
    G = {s: C[("gen", s)] for s in FOSSIL + CLEAN + ["Fossil", "Clean"]}
    kw = dict(window=cfg["window"], exclude=cfg["exclude"])
    return {"last year": m_last_year(T, y, m),
            "share of year": m_share(T, y, m, share=cfg["share"], **kw),
            "regression": m_regression(T, y, m, G=G, regsrc=cfg["regsrc"], proj=cfg["proj"], **kw)}


# ---------- backtest, interval

def backtest(C, cfg, years=None, horizons=HORIZONS + (LATEST_H,)):
    T = C[("emis", cfg["target"])]
    years = years or [y for y in complete_years(T) if y >= BT_FIRST]
    rows = []
    for y in years:
        a = annual(T, y)
        for m in horizons:
            for k, n in nowcasts(C, y, m, cfg).items():
                rows.append((y, m, k, n, a, n / a - 1))
    return pd.DataFrame(rows, columns=["year", "horizon", "method", "nowcast", "actual", "rel_err"])


def t_quantile(p, df):
    """Student t quantile by bisection on the CDF (numerical integration of the density), stdlib only."""
    c = math.gamma((df + 1) / 2) / (math.sqrt(df * math.pi) * math.gamma(df / 2))
    f = lambda x: c * (1 + x * x / df) ** (-(df + 1) / 2)

    def cdf(x, n=2000):
        h = x / n
        s = f(0) + f(x) + sum((4 if i % 2 else 2) * f(i * h) for i in range(1, n))
        return 0.5 + s * h / 3
    lo, hi = 0.0, 50.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) < p else (lo, mid)
    return (lo + hi) / 2


def interval(N, errs, level=0.95):
    """Interval for the realised value from the relative errors N/A - 1 of earlier backtests: the scale is their
    root mean square (it includes bias), the quantile is Student t with n degrees of freedom, and the bounds are
    N/(1 + q) and N/(1 - q) because the error is relative to the actual."""
    e = np.asarray(errs, float)
    q = t_quantile(0.5 + level / 2, len(e)) * math.sqrt(np.mean(e ** 2))
    if q >= 1:
        raise ValueError("error scale too large for a relative interval")
    return N / (1 + q), N / (1 - q)


def loo_coverage(bt, level=0.95):
    """For each backtest year, build the interval from the other years' errors and ask whether it holds the actual."""
    rows = []
    for (k, m), g in bt.groupby(["method", "horizon"]):
        g = g.sort_values("year")
        for _, r in g.iterrows():
            lo, hi = interval(r.nowcast, g[g.year != r.year].rel_err.values, level)
            rows.append((k, m, int(r.year), lo, hi, r.actual, bool(lo <= r.actual <= hi)))
    return pd.DataFrame(rows, columns=["method", "horizon", "year", "lo", "hi", "actual", "covered"])


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def err_cube(bt, years=None, horizons=HORIZONS + (LATEST_H,)):
    """array years x methods x horizons of relative errors."""
    years = years or sorted(bt.year.unique())
    cube = np.full((len(years), len(METHODS), len(horizons)), np.nan)
    for i, y in enumerate(years):
        for j, k in enumerate(METHODS):
            for h, m in enumerate(horizons):
                cube[i, j, h] = bt[(bt.year == y) & (bt.method == k) & (bt.horizon == m)].rel_err.iloc[0]
    return years, cube


def bootstrap_rmse(cube, n=NBOOT, seed=SEED):
    """Resample backtest years with replacement; each draw applies to every method and horizon together, so the
    comparison between methods stays paired. Returns draws of RMSE (n x methods x horizons)."""
    rng = np.random.default_rng(seed)
    ny = cube.shape[0]
    idx = rng.integers(0, ny, size=(n, ny))
    return np.sqrt((cube[idx] ** 2).mean(axis=1))


def pct(a, lo=2.5, hi=97.5, axis=0):
    return np.percentile(a, [lo, hi], axis=axis)


def current_year(C, cfg, horizons=HORIZONS + (LATEST_H,)):
    T = C[("emis", cfg["target"])]
    y = max(int(i) for i in T.index if T.loc[i].notna().any())
    return y, {m: nowcasts(C, y, m, cfg) for m in horizons}


# ---------- main

def summarise(bt, cur_y, cur, C, cfg, bt_years=None):
    """One row per method x horizon: RMSE, mean error, current-year nowcast and its interval."""
    rows = []
    b = bt if bt_years is None else bt[bt.year.isin(bt_years)]
    for k in METHODS:
        for m in HORIZONS + (LATEST_H,):
            e = b[(b.method == k) & (b.horizon == m)].rel_err.values
            N = cur[m][k]
            lo, hi = interval(N, e)
            rows.append(dict(method=k, horizon=m, n_years=len(e), rmse=rmse(e), mean_err=float(e.mean()),
                             max_abs_err=float(np.abs(e).max()), nowcast=N, lo=lo, hi=hi))
    return pd.DataFrame(rows)


VARIANTS = [  # (group, label, cfg overrides, backtest years)
    ("target", "Fossil emissions only", dict(target="Fossil"), None),
    ("history window", "last 3 years", dict(window=3), None),
    ("history window", "last 5 years", dict(window=5), None),
    ("training years", "drop 2020 from training", dict(exclude=(2020,)), None),
    ("training years", "drop 2020 and 2022 from training", dict(exclude=(2020, 2022)), None),
    ("share rule", "share of year as year-on-year ratio", dict(share="yoy"), None),
    ("regression", "fossil generation only", dict(regsrc="fossil"), None),
    ("regression", "two groups: fossil and clean generation", dict(regsrc="grouped"), None),
    ("regression", "remaining months not scaled", dict(proj="level"), None),
    ("backtest years", "2019 to 2025", {}, list(range(2019, 2026))),
    ("backtest years", "without 2020", {}, [2018, 2019, 2021, 2022, 2023, 2024, 2025]),
    ("backtest years", "without 2020 and 2022", {}, [2018, 2019, 2021, 2023, 2024, 2025]),
    ("backtest years", "2021 to 2025", {}, list(range(2021, 2026))),
]


def main():
    os.makedirs(RES, exist_ok=True)
    C = load()
    cfg = dict(BASE)
    bt = backtest(C, cfg)
    bt.to_csv(os.path.join(RES, "backtest.csv"), index=False)
    cy, cur = current_year(C, cfg)
    base = summarise(bt, cy, cur, C, cfg)
    base.to_csv(os.path.join(RES, "nowcast_current.csv"), index=False)

    # paired bootstrap over backtest years, all methods and horizons in each draw
    years, cube = err_cube(bt)
    draws = bootstrap_rmse(cube)
    hs = list(HORIZONS + (LATEST_H,))
    rows = []
    for j, k in enumerate(METHODS):
        for h, m in enumerate(hs):
            lo, hi = pct(draws[:, j, h])
            rows.append(dict(method=k, horizon=m, rmse=rmse(cube[:, j, h]), lo=lo, hi=hi))
    pd.DataFrame(rows).to_csv(os.path.join(RES, "rmse_boot.csv"), index=False)
    rows = []
    for (a, b_) in (("regression", "share of year"), ("share of year", "last year"), ("regression", "last year")):
        ja, jb = METHODS.index(a), METHODS.index(b_)
        for h, m in enumerate(hs):
            r = draws[:, ja, h] / draws[:, jb, h]
            lo, hi = pct(r)
            rows.append(dict(a=a, b=b_, horizon=m, ratio=rmse(cube[:, ja, h]) / rmse(cube[:, jb, h]), lo=lo, hi=hi,
                             p_a_better=float((r < 1).mean())))
    pd.DataFrame(rows).to_csv(os.path.join(RES, "rmse_ratio_boot.csv"), index=False)

    # does the interval method hold? leave one backtest year out
    cov = loo_coverage(bt)
    cov.to_csv(os.path.join(RES, "loo_coverage.csv"), index=False)

    # selection: choose the lowest-RMSE method on the other years, score it on the held-out year
    sel = []
    for m in hs:
        errs = []
        for i, y in enumerate(years):
            others = [j for j in range(len(years)) if j != i]
            best = min(range(len(METHODS)), key=lambda j: rmse(cube[others, j, hs.index(m)]))
            errs.append(cube[i, best, hs.index(m)])
        sel.append(dict(horizon=m, rmse_selected=rmse(errs),
                        rmse_best_in_sample=min(rmse(cube[:, j, hs.index(m)]) for j in range(len(METHODS)))))
    pd.DataFrame(sel).to_csv(os.path.join(RES, "selection.csv"), index=False)

    # the series the deck draws, and the share of the year each horizon covers, by year
    T0 = C[("emis", cfg["target"])]
    T0.stack().rename("emis_mt").rename_axis(["year", "month"]).reset_index().to_csv(os.path.join(RES, "monthly_series.csv"), index=False)
    pd.DataFrame([dict(year=y, horizon=m, share=ytd(T0, y, m) / annual(T0, y)) for y in complete_years(T0) for m in hs]) \
        .to_csv(os.path.join(RES, "shares.csv"), index=False)

    # sweep
    rows = []
    for g, lab, ov, byrs in [("base", "base", {}, None)] + VARIANTS:
        c2 = {**cfg, **ov}
        bt2 = bt if not ov else backtest(C, c2)
        cy2, cur2 = current_year(C, c2)
        s = summarise(bt2, cy2, cur2, C, c2, byrs)
        s.insert(0, "group", g); s.insert(1, "variant", lab)
        rows.append(s)
    sw = pd.concat(rows)
    sw.to_csv(os.path.join(RES, "sweep.csv"), index=False)

    # regression diagnostics: implied factors on the latest training window vs Ember's own factor by source
    srcs = FOSSIL + CLEAN
    T = C[("emis", "Total generation")]
    b, n = fit_factors(T, {s: C[("gen", s)] for s in srcs}, srcs, train_years(T, cy))
    b_first, n_first = fit_factors(T, {s: C[("gen", s)] for s in srcs}, srcs, train_years(T, BT_FIRST))
    fac = {s: float((C[("emis", s)].values / C[("gen", s)].values).mean()) for s in srcs}
    fac_rng = {s: [float(np.nanmin(C[("emis", s)].values / C[("gen", s)].values)),
                   float(np.nanmax(C[("emis", s)].values / C[("gen", s)].values))] for s in srcs}

    out = dict(current_year=cy, months_available=max(int(m) for m in range(1, 13) if not np.isnan(T.loc[cy, m])),
               backtest_years=years, horizons=hs, ytd={m: ytd(T, cy, m) for m in hs}, last_year_actual=annual(T, cy - 1),
               actual_by_year={int(y): annual(T, y) for y in complete_years(T)},
               factors_fitted_latest=dict(zip(srcs, map(float, b))), factors_fitted_2018=dict(zip(srcs, map(float, b_first))),
               n_obs_latest=n, n_obs_2018=n_first, factor_mean=fac, factor_range=fac_rng,
               boot=dict(n=NBOOT, seed=SEED), loo_coverage=float(cov.covered.mean()),
               loo_coverage_by=cov.groupby(["method", "horizon"]).covered.mean().reset_index().to_dict("records"))
    json.dump(out, open(os.path.join(RES, "nowcast.json"), "w"), indent=1, default=lambda o: o.item())

    # validation against sources that were not fitted
    ms = pd.read_csv(os.path.join(DATA, "members_sum.csv"))
    eu = pd.read_csv(os.path.join(DATA, "eu_monthly.csv"))
    v = {}
    for s in ("Fossil", "Total generation"):
        a = eu[eu.source == s].set_index("Date").emis_mt
        b2 = ms[(ms.source == s) & (ms.n_states == 27)].set_index("Date").emis_mt
        j = a.index.intersection(b2.index)
        v["members_" + s] = dict(months=len(j), first=j[0], max_abs_rel_diff=float(((b2[j] - a[j]).abs() / a[j]).max()),
                                 mean_rel_diff=float(((b2[j] - a[j]) / a[j]).mean()))
    crf = pd.read_csv(os.path.join(DATA, "crf_annual.csv")).set_index("year").crf_mt
    rows = []
    for s in ("Fossil", "Total generation"):
        Ts = C[("emis", s)]
        for y in crf.index:
            if y in complete_years(Ts):
                rows.append((s, int(y), annual(Ts, y), float(crf[y])))
    cv = pd.DataFrame(rows, columns=["series", "year", "ember_mt", "crf_mt"])
    cv.to_csv(os.path.join(RES, "validation_crf.csv"), index=False)
    for s, g in cv.groupby("series"):
        g = g.sort_values("year")
        d1, d2 = g.ember_mt.pct_change().dropna().values, g.crf_mt.pct_change().dropna().values
        v["crf_" + s] = dict(years=[int(g.year.min()), int(g.year.max())], mean_ratio=float((g.ember_mt / g.crf_mt).mean()),
                             corr_levels=float(np.corrcoef(g.ember_mt, g.crf_mt)[0, 1]),
                             corr_changes=float(np.corrcoef(d1, d2)[0, 1]), same_sign=float((np.sign(d1) == np.sign(d2)).mean()),
                             n_changes=len(d1), rmse_change_pp=rmse(d1 - d2) * 100)
    json.dump(v, open(os.path.join(RES, "validation.json"), "w"), indent=1, default=lambda o: o.item())
    print(base.round(3).to_string())


if __name__ == "__main__":
    main()
