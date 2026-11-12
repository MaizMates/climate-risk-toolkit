"""Capture rate of solar and onshore wind in DE-LU, its slope against the share of load, intervals,
backtest, validation and sweep. Reads the committed tables in data/, writes results/.

    python3 src/capture.py
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA, RES = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")
YEARS = list(range(2019, 2026))          # complete calendar years
PARTIAL_YEAR, PARTIAL_LAST_BLOCK = 2026, 42   # Jan to late Oct 2026: blocks 0..42 are complete
TECHS = ("SOLAR", "WIND")
SEED, DRAWS = 15, 2000
T975 = {2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447}   # two-sided 95% Student t by df
SHIFT = 5.0                              # scenario: solar share of load, percentage points above 2025


def cr_of(s, tech, floor=False, hourly=False):
    """Capture rate from summed columns s (mapping or row): solar-weighted mean price over baseload."""
    gp = s[f"{tech}_GPh"] if hourly else (s[f"{tech}_GPf"] if floor else s[f"{tech}_GP"])
    base = (s["Pf"] if floor else s["P"]) / s["n"]
    return gp / s[f"{tech}_G"] / base


def share_of(s, tech):
    return 100.0 * s[f"{tech}_G"] / s["L"]


def ols(x, y):
    """Least squares of y on x: intercept, slope, standard error of the slope, n."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    b = ((x - xm) * (y - ym)).sum() / sxx
    a = ym - b * xm
    se = np.sqrt(((y - a - b * x) ** 2).sum() / (n - 2) / sxx) if n > 2 else float("nan")
    return a, b, se, n


def t_interval(b, se, n):
    h = T975[n - 2] * se
    return [b - h, b + h]


def annual_table(W, years, floor=False, hourly=False):
    """One row per year and technology: capture rate, share of load, baseload price."""
    rows = []
    for y in years:
        s = W[W["year"] == y].sum(numeric_only=True)
        for t in TECHS:
            rows.append({"year": y, "tech": t, "cr": cr_of(s, t, floor, hourly), "share": share_of(s, t),
                         "baseload": (s["Pf"] if floor else s["P"]) / s["n"],
                         "captured": cr_of(s, t, floor, hourly) * ((s["Pf"] if floor else s["P"]) / s["n"])})
    return pd.DataFrame(rows)


def chunks(W, block_len, stratify):
    """Index arrays of resampling units. A unit is block_len consecutive 7-day blocks of one stratum
    (year, or year and calendar quarter), so a whole run of weeks moves together."""
    out = []
    keys = ["year", "quarter"] if stratify else ["year"]
    for _, g in W.groupby(keys):
        idx = g.sort_values("block").index.values
        out.append([idx[i:i + block_len] for i in range(0, len(idx), block_len)])
    return out


def bootstrap(W, years, floor=False, hourly=False, block_len=1, stratify=True, draws=DRAWS, seed=SEED):
    """Resample weeks inside each year (and quarter), recompute every annual capture rate and share
    for solar and wind from the same drawn weeks. Returns arrays (draws, years, techs) of cr, share.

    One draw of weeks serves both technologies, the baseload price and the load, so the error they
    share is drawn once. Only the weeks of the year are resampled, never other years."""
    rng = np.random.default_rng(seed)
    strata = {y: chunks(W[W["year"] == y], block_len, stratify) for y in years}
    cols = [c for c in W.columns if c not in ("year", "block", "quarter")]
    A = W[cols].values
    pos = {c: i for i, c in enumerate(cols)}
    CR = np.empty((draws, len(years), len(TECHS)))
    SH = np.empty_like(CR)
    for d in range(draws):
        for j, y in enumerate(years):
            idx = np.concatenate([np.concatenate([st[k] for k in rng.integers(0, len(st), len(st))])
                                  for st in strata[y]])
            s = dict(zip(cols, A[idx].sum(axis=0)))
            for k, t in enumerate(TECHS):
                CR[d, j, k], SH[d, j, k] = cr_of(s, t, floor, hourly), share_of(s, t)
    return CR, SH


def slopes_vec(SH, CR, mask):
    """Slope of cr on share per draw and technology, over the years where mask is True."""
    x, y = SH[:, mask, :], CR[:, mask, :]
    xm, ym = x.mean(axis=1, keepdims=True), y.mean(axis=1, keepdims=True)
    return ((x - xm) * (y - ym)).sum(axis=1) / ((x - xm) ** 2).sum(axis=1)


def pct(a, lo=2.5, hi=97.5):
    return [float(np.percentile(a, lo)), float(np.percentile(a, hi))]


def predict(tr_years, tab, tech, yr, log=False):
    """Fit cr on share over tr_years, predict year yr at its realised share."""
    d = tab[tab["tech"] == tech].set_index("year")
    x, y = d.loc[tr_years, "share"].values, d.loc[tr_years, "cr"].values
    if log:
        a, b, _, _ = ols(x, np.log(y))
        return float(np.exp(a + b * d.loc[yr, "share"]))
    a, b, _, _ = ols(x, y)
    return float(a + b * d.loc[yr, "share"])


def backtest(tab, tech, first_test=2022):
    """Slope fitted on years up to t-1 predicts the capture rate of year t at its realised share.
    Benchmarks: last year's rate, and the mean of the years so far."""
    d = tab[tab["tech"] == tech].set_index("year")
    rows = []
    for t in range(first_test, YEARS[-1] + 1):
        tr = [y for y in YEARS if y < t]
        rows.append({"tech": tech, "year": t, "actual": d.loc[t, "cr"], "slope_model": predict(tr, tab, tech, t),
                     "last_year": d.loc[t - 1, "cr"], "mean_so_far": d.loc[tr, "cr"].mean(), "n_train": len(tr)})
    b = pd.DataFrame(rows)
    for m in ("slope_model", "last_year", "mean_so_far"):
        b["err_" + m] = b[m] - b["actual"]
    return b


def rmse(e):
    return float(np.sqrt(np.mean(np.square(e))))


def window_table(W, last_block):
    """Annual-like table on blocks 0..last_block only, for all years including the partial one."""
    return annual_table(W[W["block"] <= last_block], YEARS + [PARTIAL_YEAR])


def within_year_slope(W, tech, draws=DRAWS, seed=SEED, years=YEARS):
    """Weekly capture rate on weekly share with year fixed effects, weighted by solar or wind generation.
    A short-run, within-year relation, used only as a cross-check on the sign of the annual slope."""
    d = W[W["year"].isin(years)].copy()
    d["cr"] = (d[f"{tech}_GP"] / d[f"{tech}_G"]) / (d["P"] / d["n"])
    d["sh"] = 100 * d[f"{tech}_G"] / d["L"]
    d["w"] = d[f"{tech}_G"]

    def fe(g):
        out = []
        for _, h in g.groupby("year"):
            w = h["w"] / h["w"].sum()
            out.append(pd.DataFrame({"x": h["sh"] - (w * h["sh"]).sum(), "y": h["cr"] - (w * h["cr"]).sum(), "w": h["w"]}))
        o = pd.concat(out)
        return (o.w * o.x * o.y).sum() / (o.w * o.x ** 2).sum()
    rng = np.random.default_rng(seed)
    b0 = fe(d)
    groups = [g.index.values for _, g in d.groupby(["year", "quarter"])]
    bs = []
    for _ in range(draws):
        idx = np.concatenate([rng.choice(ix, len(ix)) for ix in groups])
        bs.append(fe(d.loc[idx].reset_index(drop=True).assign(year=d.loc[idx, "year"].values)))
    return float(b0), pct(bs)


def fit_summary(tab, mask_years, tech):
    d = tab[(tab["tech"] == tech) & tab["year"].isin(mask_years)]
    a, b, se, n = ols(d["share"], d["cr"])
    return {"intercept": a, "slope": b, "se": se, "n": n, "ols_interval": t_interval(b, se, n)}


def main():
    W = pd.read_csv(os.path.join(DATA, "weekly.csv"))
    os.makedirs(RES, exist_ok=True)
    out = {"years": YEARS, "draws": DRAWS, "seed": SEED, "shift_points": SHIFT}
    tab = annual_table(W, YEARS)
    CR, SH = bootstrap(W, YEARS)
    mask = np.ones(len(YEARS), bool)
    sl = slopes_vec(SH, CR, mask)
    for k, t in enumerate(TECHS):
        tab.loc[tab["tech"] == t, "cr_lo"] = np.percentile(CR[:, :, k], 2.5, axis=0)
        tab.loc[tab["tech"] == t, "cr_hi"] = np.percentile(CR[:, :, k], 97.5, axis=0)
        tab.loc[tab["tech"] == t, "share_lo"] = np.percentile(SH[:, :, k], 2.5, axis=0)
        tab.loc[tab["tech"] == t, "share_hi"] = np.percentile(SH[:, :, k], 97.5, axis=0)
    tab.round(6).to_csv(os.path.join(RES, "annual.csv"), index=False)

    # headline slope (capture-rate points per percentage point of load share)
    out["slope"] = {}
    for k, t in enumerate(TECHS):
        f = fit_summary(tab, YEARS, t)
        f["boot_interval"] = pct(sl[:, k])
        f["boot_se"] = float(sl[:, k].std(ddof=1))
        f["share_draws_negative"] = float((sl[:, k] < 0).mean())
        out["slope"][t] = f
    diff = sl[:, 0] - sl[:, 1]
    out["slope_difference"] = {"point": out["slope"]["SOLAR"]["slope"] - out["slope"]["WIND"]["slope"],
                               "boot_interval": pct(diff), "share_draws_negative": float((diff < 0).mean())}

    # leave one year out: the 7 annual points are the sample, so this is the across-year check
    loo = {}
    for t in TECHS:
        d = tab[tab["tech"] == t]
        loo[t] = {int(y): float(ols(d[d.year != y]["share"], d[d.year != y]["cr"])[1]) for y in YEARS}
    loo["difference"] = {y: loo["SOLAR"][y] - loo["WIND"][y] for y in loo["SOLAR"]}
    n = len(YEARS)
    jk = {}
    for k in ("SOLAR", "WIND", "difference"):
        v_ = np.array(list(loo[k].values()))
        se = float(np.sqrt((n - 1) / n * ((v_ - v_.mean()) ** 2).sum()))
        pt = out["slope_difference"]["point"] if k == "difference" else out["slope"][k]["slope"]
        jk[k] = {"se": se, "interval": [pt - T975[n - 1] * se, pt + T975[n - 1] * se], "range": [float(v_.min()), float(v_.max())],
                 "loo": loo[k]}
    out["jackknife_years"] = jk

    # backtest
    bt = pd.concat([backtest(tab, t) for t in TECHS])
    bt.round(6).to_csv(os.path.join(RES, "backtest.csv"), index=False)
    out["backtest"] = {}
    for t in TECHS:
        b = bt[bt["tech"] == t]
        out["backtest"][t] = {m: {"rmse": rmse(b["err_" + m]), "mae": float(np.abs(b["err_" + m]).mean()),
                                  "bias": float(b["err_" + m].mean())} for m in ("slope_model", "last_year", "mean_so_far")}
        out["backtest"][t]["test_years"] = [int(y) for y in b["year"]]
        b3 = b[b["year"] != 2022]
        out["backtest"][t]["rmse_ex2022"] = {m: rmse(b3["err_" + m]) for m in ("slope_model", "last_year", "mean_so_far")}
    wtab = window_table(W, PARTIAL_LAST_BLOCK)
    pw = {}
    for t in TECHS:
        d = wtab[wtab["tech"] == t].set_index("year")
        tr = YEARS
        a, b_, _, _ = ols(d.loc[tr, "share"], d.loc[tr, "cr"])
        pw[t] = {"actual": float(d.loc[PARTIAL_YEAR, "cr"]), "share": float(d.loc[PARTIAL_YEAR, "share"]),
                 "slope_model": float(a + b_ * d.loc[PARTIAL_YEAR, "share"]), "last_year": float(d.loc[YEARS[-1], "cr"]),
                 "mean_so_far": float(d.loc[tr, "cr"].mean()), "share_2025_window": float(d.loc[YEARS[-1], "share"])}
    out["partial_window_test"] = {"blocks": f"0..{PARTIAL_LAST_BLOCK}", **pw}

    # forward-looking scenario with the backtest-based interval
    s25 = float(tab[(tab.tech == "SOLAR") & (tab.year == YEARS[-1])]["share"].iloc[0])
    f = out["slope"]["SOLAR"]
    x_new = s25 + SHIFT
    yhat = f["intercept"] + f["slope"] * x_new
    r = out["backtest"]["SOLAR"]["slope_model"]["rmse"]
    h = T975[len(out["backtest"]["SOLAR"]["test_years"])] * r
    # parameter-only interval: refit per draw
    xs, ys = SH[:, :, 0], CR[:, :, 0]
    xm, ym = xs.mean(1), ys.mean(1)
    bb = ((xs - xm[:, None]) * (ys - ym[:, None])).sum(1) / ((xs - xm[:, None]) ** 2).sum(1)
    pred_boot = ym + bb * (x_new - xm)
    out["scenario"] = {"share_2025": s25, "share_new": x_new, "cr_2025": float(tab[(tab.tech == "SOLAR") & (tab.year == YEARS[-1])]["cr"].iloc[0]),
                       "cr_pred": float(yhat), "backtest_rmse": r, "backtest_interval": [float(yhat - h), float(yhat + h)],
                       "param_boot_interval": pct(pred_boot),
                       "observed_share_range": [float(tab[tab.tech == "SOLAR"]["share"].min()), float(tab[tab.tech == "SOLAR"]["share"].max())]}
    dl = tab[tab.tech == "SOLAR"]
    al, bl, _, _ = ols(dl["share"], np.log(dl["cr"]))
    out["scenario"]["cr_pred_loglinear"] = float(np.exp(al + bl * x_new))

    # validation: published solar market value (TSO, ct/kWh) against my solar-weighted price
    mv = pd.read_csv(os.path.join(DATA, "market_value_solar.csv")).set_index("year")
    v = []
    for y in YEARS:
        r_ = tab[(tab.tech == "SOLAR") & (tab.year == y)].iloc[0]
        mine = float(r_["captured"])
        pub = float(mv.loc[y, "mw_solar_ct_kwh_csv_block"]) * 10
        v.append({"year": y, "mine_eur_mwh": mine, "published_eur_mwh": pub, "diff_pct": 100 * (mine / pub - 1),
                  "published_prose_eur_mwh": float(mv.loc[y, "mw_solar_ct_kwh_prose"]) * 10,
                  "baseload": float(r_["baseload"]), "published_cr": pub / float(r_["baseload"])})
    v = pd.DataFrame(v)
    v.round(4).to_csv(os.path.join(RES, "validation.csv"), index=False)
    out["validation"] = {"mean_abs_diff_pct": float(v["diff_pct"].abs().mean()), "max_abs_diff_pct": float(v["diff_pct"].abs().max()),
                         "corr_levels": float(np.corrcoef(v["mine_eur_mwh"], v["published_eur_mwh"])[0, 1]),
                         "max_abs_cr_diff": float((v["mine_eur_mwh"] / v["baseload"] - v["published_cr"]).abs().max()),
                         "slope_published_cr": ols(tab[tab.tech == "SOLAR"]["share"], v["published_cr"])[1]}
    jw = pd.read_csv(os.path.join(DATA, "market_value_jw.csv"))
    jwy = int(jw["year"].iloc[0])
    jwv = {r.series: r.ct_kwh * 10 for r in jw.itertuples()}
    ty = tab[tab.year == jwy].set_index("tech")
    out["validation"]["jw"] = {"year": jwy, "baseload": {"mine": float(ty.loc["SOLAR", "baseload"]), "published": jwv["baseload"]},
                               "solar": {"mine": float(ty.loc["SOLAR", "captured"]), "published": jwv["solar"]},
                               "wind_onshore": {"mine": float(ty.loc["WIND", "captured"]), "published": jwv["wind_onshore"]}}
    for k_, d_ in out["validation"]["jw"].items():
        if isinstance(d_, dict):
            d_["diff_pct"] = 100 * (d_["mine"] / d_["published"] - 1)
    wb, wi = within_year_slope(W, "SOLAR")
    out["within_year"] = {"slope": wb, "boot_interval": wi}

    # sweep: every variant reports the solar and wind slope and the solar-minus-wind difference
    sweep = []

    def add(group, name, floor=False, hourly=False, block_len=1, stratify=True, years_fit=YEARS, log=False, boot=True):
        tb = annual_table(W, YEARS, floor, hourly)
        row = {"group": group, "variant": name}
        if boot:
            C, S = bootstrap(W, YEARS, floor, hourly, block_len, stratify, draws=1000)
        m = np.array([y in years_fit for y in YEARS])
        for k, t in enumerate(TECHS):
            d = tb[tb["tech"] == t]
            dd = d[d["year"].isin(years_fit)]
            if log:
                a, b, se, n = ols(dd["share"], np.log(dd["cr"]))
                b = b * float(dd["cr"].mean())   # elasticity-to-slope at the mean rate, for comparability
            else:
                a, b, se, n = ols(dd["share"], dd["cr"])
            row[f"{t.lower()}_slope"] = float(b)
            row[f"{t.lower()}_ols_lo"], row[f"{t.lower()}_ols_hi"] = t_interval(b, se, n)
            if boot and not log:
                lo, hi = pct(slopes_vec(S, C, m)[:, k])
                row[f"{t.lower()}_boot_lo"], row[f"{t.lower()}_boot_hi"] = lo, hi
        s = tb[tb["tech"] == "SOLAR"]
        row["cr_2025"] = float(s[s.year == 2025]["cr"].iloc[0])
        sweep.append(row)

    add("base", "negative prices kept, 2022 kept, one-week blocks")
    add("negative prices", "price floored at zero (generation weights and baseload)", floor=True)
    add("price resolution", "hourly mean generation times hourly mean price", hourly=True)
    add("2022 spike", "drop 2022 from the fit", years_fit=[y for y in YEARS if y != 2022])
    add("2022 spike", "drop 2021 and 2022 from the fit", years_fit=[y for y in YEARS if y not in (2021, 2022)])
    add("2022 spike", "drop 2022 and floor negative prices", floor=True, years_fit=[y for y in YEARS if y != 2022])
    add("start year", "fit on 2020 to 2025 only", years_fit=YEARS[1:])
    add("functional form", "log capture rate on share (slope at the mean rate)", log=True, boot=False)
    for L in (2, 4):
        add("block length", f"bootstrap blocks of {L} weeks", block_len=L)
    add("block length", "bootstrap not stratified by quarter", stratify=False)
    sw = pd.DataFrame(sweep)
    sw.round(6).to_csv(os.path.join(RES, "sweep.csv"), index=False)
    out["sweep_summary"] = {"solar_slope_range": [float(sw["solar_slope"].min()), float(sw["solar_slope"].max())],
                            "wind_slope_range": [float(sw["wind_slope"].min()), float(sw["wind_slope"].max())],
                            "n_variants": int(len(sw)),
                            "solar_negative_in_all": bool((sw["solar_slope"] < 0).all())}

    # descriptive facts the text uses
    s = W.groupby("year").sum(numeric_only=True)
    out["facts"] = {"neg_hours": {int(y): float(s.loc[y, "nneg"] / 4) for y in YEARS + [PARTIAL_YEAR]},
                    "solar_gen_at_neg_price_share": {int(y): float(s.loc[y, "SOLAR_Gneg"] / s.loc[y, "SOLAR_G"]) for y in YEARS},
                    "baseload": {int(y): float(s.loc[y, "P"] / s.loc[y, "n"]) for y in YEARS + [PARTIAL_YEAR]},
                    "hourly_vs_quarter_cr_gap_2025": float(cr_of(s.loc[2025], "SOLAR", hourly=True) - cr_of(s.loc[2025], "SOLAR")),
                    "partial_year_rows": int(W[W.year == PARTIAL_YEAR]["n"].sum())}
    prof = pd.read_csv(os.path.join(DATA, "profile.csv"))
    prof.to_csv(os.path.join(RES, "profile.csv"), index=False)
    json.dump(out, open(os.path.join(RES, "capture.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("slope", "slope_difference", "backtest", "partial_window_test", "scenario", "validation", "within_year", "sweep_summary")}, indent=1))


if __name__ == "__main__":
    main()
