"""Temperature sensitivity of German daily electricity load: estimate, intervals, backtest, sweep.

    load_d = year effect + weekday + holiday + Christmas week [+ annual harmonics, sweep only]
             + b_h * HDD_d(Th) + b_c * CDD_d(Tc) + e_d

HDD = max(Th - T, 0), CDD = max(T - Tc, 0), T the population-weighted mean of six cities' daily mean
temperature. Th, Tc are chosen on a grid by least squares inside each fit (so inside each bootstrap
draw and each backtest training window), never by hand. Units: GWh per degree-day.

    python3 src/loadtemp.py
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA, RES = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")
TH_GRID = list(range(10, 21))
TC_GRID = list(range(14, 27))
BLOCK = 14
SEED = 16
DRAWS = 2000
SWEEP_DRAWS = 400
FIT_YEARS = list(range(2019, 2026))
BASE = dict(temp="temp", harm=0, yearfe=True, smooth=1, drop_years=(), grid=None)


def load():
    d = pd.read_csv(os.path.join(DATA, "daily.csv"), parse_dates=["date"])
    d["year"] = d.date.dt.year
    return d


def effective_temp(d, col, smooth):
    """Mean of today's and the previous days' temperature (thermal inertia); smooth=1 is today only."""
    return d[col].rolling(smooth, min_periods=1).mean().values if smooth > 1 else d[col].values


def controls(d, harm, yearfe, ref_year=None, years=None):
    """Calendar controls. ref_year/years: the year effects a prediction uses (last training year)."""
    cols = [np.ones(len(d))]
    yr = d.year.values if ref_year is None else np.full(len(d), ref_year)
    if yearfe:
        for y in years[1:]:
            cols.append((yr == y).astype(float))
    else:
        cols.append(d.date.dt.year.values + d.date.dt.dayofyear.values / 366 - 2019 if ref_year is None else None)
    wd = d.date.dt.weekday.values
    for k in range(6):
        cols.append((wd == k).astype(float))
    cols.append(d.holiday.values.astype(float))
    m, dd = d.date.dt.month.values, d.date.dt.day.values
    cols.append((((m == 12) & (dd >= 24)) | ((m == 1) & (dd == 1))).astype(float))
    doy = d.date.dt.dayofyear.values / 365.25
    for k in range(1, harm + 1):
        cols += [np.sin(2 * np.pi * k * doy), np.cos(2 * np.pi * k * doy)]
    return np.column_stack(cols)


def fit(d, spec=BASE, thresholds=None, years=None):
    """OLS with thresholds chosen by least squares on the grid unless given. Returns dict."""
    y = d.load_gwh.values
    T = effective_temp(d, spec["temp"], spec["smooth"])
    yrs = sorted(d.year.unique()) if years is None else years
    Z = controls(d, spec["harm"], spec["yearfe"], years=yrs)
    q, _ = np.linalg.qr(Z)
    res = lambda v: v - q @ (q.T @ v)
    ry = res(y)
    grid_h = TH_GRID if thresholds is None else [thresholds[0]]
    grid_c = TC_GRID if thresholds is None else [thresholds[1]]
    H = {t: res(np.maximum(t - T, 0)) for t in grid_h}
    C = {t: res(np.maximum(T - t, 0)) for t in grid_c}
    best = None
    surf = []
    for th in grid_h:
        for tc in grid_c:
            if tc < th:
                continue
            A = np.column_stack([H[th], C[tc]])
            b, *_ = np.linalg.lstsq(A, ry, rcond=None)
            rss = float(((ry - A @ b) ** 2).sum())
            surf.append((th, tc, rss, b[0], b[1]))
            if best is None or rss < best[2]:
                best = (th, tc, rss, b[0], b[1])
    th, tc, rss, bh, bc = best
    X = np.column_stack([Z, np.maximum(th - T, 0), np.maximum(T - tc, 0)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"th": th, "tc": tc, "bh": beta[-2], "bc": beta[-1], "beta": beta, "years": yrs, "spec": spec,
            "rss": float(((y - X @ beta) ** 2).sum()), "surface": surf}


def predict(m, d, trend_ref=True):
    spec = m["spec"]
    T = effective_temp(d, spec["temp"], spec["smooth"])
    if spec["yearfe"]:
        Z = controls(d, spec["harm"], True, ref_year=m["years"][-1], years=m["years"])
    else:
        Z = controls(d, spec["harm"], False, years=m["years"])
        Z[:, 1] = d.date.dt.year.values + d.date.dt.dayofyear.values / 366 - 2019
    X = np.column_stack([Z, np.maximum(m["th"] - T, 0), np.maximum(T - m["tc"], 0)])
    return X @ m["beta"]


def weather_part(m, T, bh=None, bc=None):
    return (m["bh"] if bh is None else bh) * np.maximum(m["th"] - T, 0) + (m["bc"] if bc is None else bc) * np.maximum(T - m["tc"], 0)


def calendar_only(d, spec, train, test):
    """Same controls without temperature: how much of the fit is weather."""
    Z = controls(train, spec["harm"], spec["yearfe"], years=sorted(train.year.unique()))
    b, *_ = np.linalg.lstsq(Z, train.load_gwh.values, rcond=None)
    if spec["yearfe"]:
        Zt = controls(test, spec["harm"], True, ref_year=train.year.max(), years=sorted(train.year.unique()))
    else:
        Zt = controls(test, spec["harm"], False, years=sorted(train.year.unique()))
        Zt[:, 1] = test.date.dt.year.values + test.date.dt.dayofyear.values / 366 - 2019
    return Zt @ b, Z @ b


def block_index(n, rng, block=None):
    """Moving blocks of consecutive days, drawn with replacement, trimmed to n rows."""
    block = block or BLOCK
    k = -(-n // block)
    starts = rng.integers(0, n - block + 1, size=k)
    return (starts[:, None] + np.arange(block)[None, :]).ravel()[:n]


def scenario(m, d, dT, bh, bc, th, tc, spec=BASE):
    """Annual load change (GWh per year, mean over the days of d) when every day is dT degrees warmer."""
    T = effective_temp(d, spec["temp"], spec["smooth"])
    f = lambda t: bh * np.maximum(th - t, 0) + bc * np.maximum(t - tc, 0)
    return float((f(T + dT) - f(T)).sum() / (len(d) / 365.25))


def boot(d, spec, draws, seed, fixed=None, dT=1.0):
    """Block bootstrap over days. One draw of days refits all coefficients and thresholds together and
    evaluates the applied scenario with that same fit, so the error they share is drawn once."""
    rng = np.random.default_rng(seed)
    n = len(d)
    out = []
    yrs = sorted(d.year.unique())
    for _ in range(draws):
        ix = block_index(n, rng)
        s = d.iloc[ix].reset_index(drop=True)
        s["year"] = d.year.values[ix]
        s["date"] = d.date.values[ix]
        # the rolling smoother must see the original neighbours, so carry the smoothed column
        if spec["smooth"] > 1:
            s[spec["temp"]] = effective_temp(d, spec["temp"], spec["smooth"])[ix]
            sp = {**spec, "smooth": 1}
        else:
            sp = spec
        m = fit(s, sp, fixed, years=yrs)
        out.append((m["th"], m["tc"], m["bh"], m["bc"], scenario(m, d, dT, m["bh"], m["bc"], m["th"], m["tc"], spec)))
    return np.array(out)


def ci(x, lo=2.5, hi=97.5):
    return [float(np.percentile(x, lo)), float(np.percentile(x, hi))]


def annual_weather(m, d):
    T = effective_temp(d, m["spec"]["temp"], m["spec"]["smooth"])
    w = weather_part(m, T)
    return pd.DataFrame({"year": d.year.values, "w": w, "hdd": np.maximum(m["th"] - T, 0), "cdd": np.maximum(T - m["tc"], 0),
                         "load": d.load_gwh.values}).groupby("year").agg(
        weather_gwh=("w", "sum"), hdd=("hdd", "sum"), cdd=("cdd", "sum"), load_gwh=("load", "sum"), days=("w", "size"))


def backtest(d, spec, test_year, train_years=None, end=None):
    """Fit on years before test_year, predict test_year with realised weather. Year effect: the last training year's."""
    train = d[d.year.isin(train_years)] if train_years else d[d.year < test_year]
    test = d[d.year == test_year]
    m = fit(train, spec)
    p = predict(m, test)
    cal, _ = calendar_only(d, spec, train, test)
    lag = d.set_index("date").load_gwh
    naive = lag.reindex(test.date - pd.Timedelta(days=364)).values
    ok = ~np.isnan(naive)
    y = test.load_gwh.values
    r = {"test": str(test_year), "n_days": len(test), "th": m["th"], "tc": m["tc"], "bh": m["bh"], "bc": m["bc"]}
    for name, pr, msk in (("model", p, np.ones(len(y), bool)), ("calendar_only", cal, np.ones(len(y), bool)), ("naive_364", naive, ok)):
        e = (pr - y)[msk]
        r[f"rmse_{name}"] = float(np.sqrt((e ** 2).mean()))
        r[f"mape_{name}"] = float(np.abs(e / y[msk]).mean() * 100)
        r[f"total_err_pct_{name}"] = float(e.sum() / y[msk].sum() * 100)
    r["_err"] = p - y
    return r


def main():
    os.makedirs(RES, exist_ok=True)
    d_all = load()
    d = d_all[d_all.year.isin(FIT_YEARS)].reset_index(drop=True)
    d26 = d_all[d_all.year == 2026]
    m = fit(d)
    T = d.temp.values
    Z = controls(d, BASE["harm"], True, years=m["years"])
    resid = d.load_gwh.values - np.column_stack([Z, np.maximum(m["th"] - T, 0), np.maximum(T - m["tc"], 0)]) @ m["beta"]
    n = len(d)
    r2 = 1 - (resid ** 2).sum() / ((d.load_gwh - d.load_gwh.mean()) ** 2).sum()
    cal_p, cal_in = calendar_only(d, BASE, d, d)
    r2_cal = 1 - ((d.load_gwh.values - cal_in) ** 2).sum() / ((d.load_gwh - d.load_gwh.mean()) ** 2).sum()
    # weather-explained share of within-calendar variation: gain in R2 from adding temperature
    ss_cal = ((d.load_gwh.values - cal_in) ** 2).sum()
    gain = 1 - m["rss"] / ss_cal

    B = boot(d, BASE, DRAWS, SEED)
    aw = annual_weather(m, d)
    mean_load = float(d.load_gwh.sum() / (len(d) / 365.25))
    share_draw = []
    # annual weather-driven share of load per draw uses the same draws as the coefficients
    for th, tc, bh, bc, _ in B:
        Tt = d.temp.values
        share_draw.append((bh * np.maximum(th - Tt, 0) + bc * np.maximum(Tt - tc, 0)).sum() / d.load_gwh.sum() * 100)
    heat_share = float(((m["bh"] * np.maximum(m["th"] - T, 0)).sum() / d.load_gwh.sum()) * 100)
    cool_share = float(((m["bc"] * np.maximum(T - m["tc"], 0)).sum() / d.load_gwh.sum()) * 100)
    sc1 = scenario(m, d, 1.0, m["bh"], m["bc"], m["th"], m["tc"])
    heat_dT = scenario(m, d, 1.0, m["bh"], 0, m["th"], m["tc"])

    # backtest
    bts = [backtest(d_all, BASE, y) for y in (2022, 2023, 2024, 2025)]
    errs = {b["test"]: b.pop("_err") for b in bts}
    for b in bts:
        b["warm1_gwh"] = scenario(None, d, 1.0, b["bh"], b["bc"], b["th"], b["tc"])
    spec_rows = []
    for k in (0, 1, 2, 4):
        for y in (2022, 2023, 2024, 2025):
            r_ = backtest(d_all, {**BASE, "harm": k}, y)
            spec_rows.append({"harmonics": k, "test": y, "bh": r_["bh"], "rmse_model": r_["rmse_model"], "total_err_pct_model": r_["total_err_pct_model"]})
    pd.DataFrame(spec_rows).to_csv(os.path.join(RES, "backtest_specs.csv"), index=False)
    rng = np.random.default_rng(SEED + 1)
    t25 = d_all[d_all.year == 2025]
    y25 = t25.load_gwh.values
    rm, tot, gap = [], [], []
    e_m = errs["2025"]
    cal25, _ = calendar_only(d_all, BASE, d_all[d_all.year < 2025], t25)
    e_c = cal25 - y25
    for _ in range(DRAWS):
        ix = block_index(len(y25), rng)
        rm.append(np.sqrt((e_m[ix] ** 2).mean()))
        tot.append(e_m[ix].sum() / y25[ix].sum() * 100)
        gap.append(np.sqrt((e_c[ix] ** 2).mean()) - np.sqrt((e_m[ix] ** 2).mean()))
    bt25 = next(b for b in bts if b["test"] == "2025")
    bt25["rmse_model_interval"] = ci(rm)
    bt25["total_err_pct_interval"] = ci(tot)
    bt25["rmse_gain_over_calendar_interval"] = ci(gap)
    # 2026 January to October with the year effect of 2025
    m_full = m
    p26 = predict(m_full, d26)
    y26 = d26.load_gwh.values
    e26 = p26 - y26
    cal26, _ = calendar_only(d_all, BASE, d, d26)
    lag = d_all.set_index("date").load_gwh
    nv = lag.reindex(d26.date - pd.Timedelta(days=364)).values
    t26 = {"n_days": len(d26), "rmse_model": float(np.sqrt((e26 ** 2).mean())), "rmse_calendar_only": float(np.sqrt(((cal26 - y26) ** 2).mean())),
           "rmse_naive_364": float(np.sqrt(((nv - y26) ** 2).mean())), "total_err_pct_model": float(e26.sum() / y26.sum() * 100),
           "mape_model": float(np.abs(e26 / y26).mean() * 100)}
    rr = []
    for _ in range(DRAWS):
        ix = block_index(len(y26), rng)
        rr.append(np.sqrt((e26[ix] ** 2).mean()))
    t26["rmse_model_interval"] = ci(rr)
    pd.DataFrame(bts + [{"test": "2026 Jan-Oct", **{k: v for k, v in t26.items() if not k.endswith("interval")}}]).to_csv(os.path.join(RES, "backtest.csv"), index=False)

    # sweep
    rows = []

    def add(group, label, spec, d_, fixed=None, draws=SWEEP_DRAWS, dT=1.0, **extra):
        mm = fit(d_, spec, fixed)
        Bs = boot(d_, spec, draws, SEED + 100 + len(rows), fixed, dT)
        sc = scenario(mm, d_, dT, mm["bh"], mm["bc"], mm["th"], mm["tc"], spec)
        rows.append({"group": group, "label": label, "th": mm["th"], "tc": mm["tc"], "bh": mm["bh"], "bh_lo": ci(Bs[:, 2])[0], "bh_hi": ci(Bs[:, 2])[1],
                     "bc": mm["bc"], "bc_lo": ci(Bs[:, 3])[0], "bc_hi": ci(Bs[:, 3])[1], "warm1_gwh": sc, "warm1_lo": ci(Bs[:, 4])[0],
                     "warm1_hi": ci(Bs[:, 4])[1], "r2": 1 - mm["rss"] / ((d_.load_gwh - d_.load_gwh.mean()) ** 2).sum(), **extra})

    add("base", "base: grid thresholds, year effects, no seasonal control, population weights", BASE, d)
    for th_, tc_ in ((12, 18), (15, 18), (15, 22), (16, 20), (18, 18), (18, 24)):
        add("thresholds", f"fixed Th={th_}, Tc={tc_}", BASE, d, (th_, tc_))
    for k in (1, 2, 4):
        add("controls", f"{k} annual harmonic{'s' if k > 1 else ''} (seasonal cycle absorbed)", {**BASE, "harm": k}, d)
    add("controls", "linear trend instead of year effects", {**BASE, "yearfe": False}, d)
    add("sample", "2020 dropped (Covid)", BASE, d[d.year != 2020].reset_index(drop=True))
    add("sample", "2022 and 2023 dropped (energy crisis)", BASE, d[~d.year.isin([2022, 2023])].reset_index(drop=True))
    add("sample", "2019 to 2024 (backtest training window)", BASE, d[d.year < 2025].reset_index(drop=True))
    add("temperature", "equal city weights", {**BASE, "temp": "temp_equal"}, d)
    dd = d[d.temp_dwd.notna()].reset_index(drop=True)
    add("temperature", "DWD station temperature (independent source)", {**BASE, "temp": "temp_dwd"}, dd)
    add("temperature", "2-day mean temperature", {**BASE, "smooth": 2}, d)
    add("temperature", "3-day mean temperature", {**BASE, "smooth": 3}, d)
    for c in ("Berlin", "Frankfurt am Main"):
        add("temperature", f"{c} only", {**BASE, "temp": c}, d)
    add("scenario", "uniform +2 degrees", BASE, d, dT=2.0)
    sw = pd.DataFrame(rows)
    sw.to_csv(os.path.join(RES, "sweep.csv"), index=False)
    pd.DataFrame(m["surface"], columns=["th", "tc", "rss", "bh", "bc"]).to_csv(os.path.join(RES, "threshold_surface.csv"), index=False)

    # bootstrap threshold spread and block length
    blk = {}
    for L in (7, 14, 28):
        globals()["BLOCK"] = L
        Bl = boot(d, BASE, 400, SEED + 7)
        blk[str(L)] = {"bh": ci(Bl[:, 2]), "bc": ci(Bl[:, 3]), "warm1_gwh": ci(Bl[:, 4])}
    globals()["BLOCK"] = 14
    # fixed thresholds bootstrap (thresholds not re-selected)
    Bf = boot(d, BASE, 400, SEED + 8, (m["th"], m["tc"]))
    blk["fixed_thresholds"] = {"bh": ci(Bf[:, 2]), "bc": ci(Bf[:, 3]), "warm1_gwh": ci(Bf[:, 4])}

    # annual and profile tables
    aw["weather_pct_of_load"] = aw.weather_gwh / aw.load_gwh * 100
    aw.reset_index().to_csv(os.path.join(RES, "annual.csv"), index=False)
    dd_ = d.assign(fitted=d.load_gwh - resid, resid=resid, weather=weather_part(m, T))
    dd_[["date", "load_gwh", "temp", "fitted", "resid", "weather", "holiday"]].round(3).to_csv(os.path.join(RES, "fit_daily.csv"), index=False)
    # temperature-load curve: binned means of load net of calendar controls
    net = d.load_gwh.values - Z[:, 1:] @ m["beta"][1:Z.shape[1]]
    pd.DataFrame({"temp": T, "load_adj": net}).assign(bin=lambda x: np.floor(x.temp / 2) * 2).groupby("bin").agg(
        temp=("temp", "mean"), load_adj=("load_adj", "mean"), n=("temp", "size")).reset_index().to_csv(os.path.join(RES, "curve.csv"), index=False)
    pd.DataFrame(B, columns=["th", "tc", "bh", "bc", "warm1_gwh"]).to_csv(os.path.join(RES, "bootstrap.csv"), index=False)

    out = {
        "n_days": n, "years": FIT_YEARS, "block_days": BLOCK, "draws": DRAWS, "seed": SEED,
        "thresholds": {"th": m["th"], "tc": m["tc"], "th_interval": ci(B[:, 0]), "tc_interval": ci(B[:, 1]),
                       "th_share_at_selected": float((B[:, 0] == m["th"]).mean())},
        "heating": {"gwh_per_hdd": m["bh"], "interval": ci(B[:, 2]), "share_of_load_pct": heat_share},
        "cooling": {"gwh_per_cdd": m["bc"], "interval": ci(B[:, 3]), "share_of_load_pct": cool_share},
        "weather_share_of_load_pct": heat_share + cool_share, "weather_share_interval": ci(share_draw),
        "mean_annual_load_gwh": mean_load,
        "r2": r2, "r2_calendar_only": r2_cal, "rss_reduction_vs_calendar_only": gain,
        "residual_sd_gwh": float(resid.std(ddof=0)),
        "scenario_plus1": {"gwh_per_year": sc1, "interval": ci(B[:, 4]), "pct_of_load": sc1 / mean_load * 100,
                           "pct_interval": [x / mean_load * 100 for x in ci(B[:, 4])], "heating_part_gwh": heat_dT},
        "annual_weather_range_gwh": [float(aw.weather_gwh.min()), float(aw.weather_gwh.max())],
        "backtest": {"rolling": bts, "target_2025": bt25, "partial_2026": t26},
        "bootstrap_variants": blk,
        "cooling_interval_covers_zero": bool(ci(B[:, 3])[0] <= 0 <= ci(B[:, 3])[1]),
        "temp_mean_by_year": d.groupby("year").temp.mean().round(3).to_dict(),
    }
    json.dump(out, open(os.path.join(RES, "loadtemp.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("thresholds", "heating", "cooling", "weather_share_of_load_pct", "weather_share_interval", "r2", "r2_calendar_only", "scenario_plus1")}, indent=1))
    print(pd.DataFrame(bts + [t26]).drop(columns=[c for c in ("th", "tc", "bh", "bc") if False], errors="ignore").T)
    print(sw[["label", "th", "tc", "bh", "bh_lo", "bh_hi", "bc", "bc_lo", "bc_hi", "warm1_gwh", "warm1_lo", "warm1_hi"]].round(2).to_string())


if __name__ == "__main__":
    main()
