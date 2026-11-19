"""Monthly-to-annual coherence of Eurostat electricity statistics.

Estimand: for each member state, flow and year, the relative gap (sum of twelve monthly figures minus the
annual figure) / annual figure, between nrg_cb_em (monthly) and nrg_cb_e (annual). Headline: the share of
EU27 country-flow-years within 1 percent, and the country-flow pairs that diverge persistently.

Intervals resample country-years: a drawn country-year brings all its flows with it, so the error a country
shares across flows is drawn once. A second interval resamples whole countries, because divergence persists
within a country and years are not independent.

    python3 src/coherence.py      # reads data/pairs.csv, writes results/ (about 1 minute)
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA, RES = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")
SEED, B, B_SWEEP = 17, 2000, 400
CORE = ["IMP", "EXP", "DL", "PS"]
TOL = 0.01
WINDOW = (2008, 2025)
PERSIST_SHARE, PERSIST_YEARS = 0.5, 5
PCTS = (0.5, 0.75, 0.9, 0.95)


def load():
    p = pd.read_csv(os.path.join(DATA, "pairs.csv")).fillna({"m_flags": "", "a_flag": ""})
    p["gap"], p["agap"] = gaps(p.monthly_gwh.values, p.annual_gwh.values)
    return p


def gaps(m, a):
    """Relative gap and its absolute value. Annual zero: gap 0 if the monthly sum is also 0, else infinite."""
    m, a = np.asarray(m, float), np.asarray(a, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.where(a != 0, (m - a) / a, np.where(m == 0, 0.0, np.inf * np.sign(m)))
    return g, np.abs(g)


def wquantile(sorted_vals, w_sorted, qs):
    c = np.cumsum(w_sorted)
    return [sorted_vals[min(np.searchsorted(c, q * c[-1]), len(c) - 1)] for q in qs]


def select(p, eu=True, flows=CORE, years=WINDOW, floor=0.0, drop_flagged=False, alt_dl=False, both_zero=False):
    """A pair with both figures zero has an undefined relative gap and is dropped unless both_zero=True."""
    d = p[p.flow.isin(flows) & p.year.between(*years)]
    if not both_zero:
        d = d[(d.monthly_gwh != 0) | (d.annual_gwh != 0)]
    if eu:
        d = d[d.eu27 == 1]
    if floor:
        d = d[d.annual_gwh >= floor]
    if drop_flagged:
        d = d[(d.m_flags == "") & (d.a_flag == "")]
    d = d.copy()
    if alt_dl:
        sw = (d.flow == "DL") & d.alt_annual_gwh.notna()
        d = d[(d.flow != "DL") | sw]
        d.loc[sw, "annual_gwh"] = d.loc[sw, "alt_annual_gwh"]
        d["gap"], d["agap"] = gaps(d.monthly_gwh.values, d.annual_gwh.values)
    return d.reset_index(drop=True)


def persistent(d, tol=TOL, share=PERSIST_SHARE, nmin=PERSIST_YEARS, w=None):
    """Country-flow pairs with at least nmin years of which at least `share` lie outside tol."""
    w = np.ones(len(d)) if w is None else w
    out = pd.DataFrame({"k": d.geo + "|" + d.flow, "w": w, "o": w * (d.agap.values > tol)}).groupby("k").sum()
    return out[(out.w >= nmin) & (out.o / out.w >= share)]


def statistic(d, tol=TOL, w=None):
    w = np.ones(len(d)) if w is None else w
    a = d.agap.values
    o = np.argsort(a, kind="stable")
    q = wquantile(a[o], w[o], PCTS)
    return {"n": float(w.sum()), "share_within": float((w * (a <= tol)).sum() / w.sum()), "median": q[0], "p75": q[1], "p90": q[2], "p95": q[3],
            "n_persistent": int(len(persistent(d, tol, w=w)))}


def draw_weights(d, rng, cluster):
    """Multiplicity of each row under one resample of units: (country, year) or whole countries."""
    key = d.geo if cluster == "country" else d.geo + d.year.astype(str)
    codes, uniq = pd.factorize(key)
    cnt = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
    return cnt[codes].astype(float)


def bootstrap(d, cluster, n=B, seed=SEED, tol=TOL):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        w = draw_weights(d, rng, cluster)
        s = statistic(d, tol, w)
        s["by_flow"] = {f: float((w * (d.agap.values <= tol) * (d.flow.values == f)).sum() / max((w * (d.flow.values == f)).sum(), 1e-9)) for f in CORE}
        rows.append(s)
    return rows


def ci(vals, lo=2.5, hi=97.5):
    v = np.asarray(vals, float)
    return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]


def shares_by(d, col, tol=TOL):
    g = d.groupby(col)
    return pd.DataFrame({"n": g.size(), "share_within": g.agap.apply(lambda x: (x <= tol).mean()), "median_abs_gap": g.agap.median(),
                         "median_signed_gap": g.gap.median()}).reset_index()


def trace(d, tol=TOL):
    """Persistent pairs with the evidence for a cause. A flag is a documented cause; an alternative definition
    that closes the gap is an inference; everything else is unexplained."""
    pers = persistent(d, tol)
    rows = []
    for k in pers.index:
        geo, flow = k.split("|")
        x = d[(d.geo == geo) & (d.flow == flow)]
        out = x[x.agap > tol]
        flagged = out[(out.m_flags.str.contains("[eub]")) | (out.a_flag.str.contains("[ebd]"))]
        row = {"geo": geo, "flow": flow, "years": len(x), "outside": len(out), "median_signed_gap": float(x.gap.replace([np.inf, -np.inf], np.nan).median()),
               "same_sign_share": float(max((out.gap > 0).mean(), (out.gap < 0).mean())),
               "median_abs_gap_gwh": float((out.monthly_gwh - out.annual_gwh).abs().median()),
               "share_flagged": float(len(flagged) / len(out)), "annual_zero_share": float((out.annual_gwh == 0).mean()),
               "monthly_zero_share": float((out.monthly_gwh == 0).mean()), "alt_closes": np.nan}
        if flow == "DL":
            o = out[out.alt_annual_gwh.notna()]
            if len(o):
                row["alt_closes"] = float((((o.monthly_gwh - o.alt_annual_gwh) / o.alt_annual_gwh).abs() <= tol).mean())
        if row["share_flagged"] >= 0.5:
            row["cause"] = "documented: Eurostat flag on the observation"
        elif row["annual_zero_share"] >= 0.5:
            row["cause"] = "pattern, not documented: annual is zero, monthly is not"
        elif row["monthly_zero_share"] >= 0.5:
            row["cause"] = "pattern, not documented: monthly is zero, annual is not"
        elif row["alt_closes"] >= 0.5:
            row["cause"] = "pattern, not documented: monthly matches annual total losses"
        else:
            row["cause"] = "unexplained"
        rows.append(row)
    return pd.DataFrame(rows)


def rounding_noise(seed=SEED, n=20000):
    """SYNTHETIC: the gap that rounding every monthly figure to a whole GWh produces on its own, by size of the annual figure."""
    rng = np.random.default_rng(seed)
    err = rng.uniform(-0.5, 0.5, (n, 12)).sum(axis=1)
    rows = []
    for a in (10, 30, 100, 300, 1000, 10000):
        g = np.abs(err) / a
        rows.append({"annual_gwh": a, "p_outside_1pct": float((g > 0.01).mean()), "p_outside_0.1pct": float((g > 0.001).mean())})
    return pd.DataFrame(rows)


def validate_ember(p, em):
    """Net imports (IMP - EXP): which of the monthly sum and the annual figure is closer to Ember's yearly number."""
    d = select(p, flows=["IMP", "EXP"], years=(2019, 2025))
    w = d.pivot_table(index=["geo", "year"], columns="flow", values=["monthly_gwh", "annual_gwh"]).dropna()
    net = pd.DataFrame({"m": w[("monthly_gwh", "IMP")] - w[("monthly_gwh", "EXP")], "a": w[("annual_gwh", "IMP")] - w[("annual_gwh", "EXP")]}).reset_index()
    net = net.merge(em, on=["geo", "year"])
    net["d_m"], net["d_a"] = (net.ember_net_imports_gwh - net.m).abs(), (net.ember_net_imports_gwh - net.a).abs()
    net["scale"] = (net.a.abs() + net.m.abs()).clip(lower=1) / 2
    return net


def main():
    os.makedirs(RES, exist_ok=True)
    p = load()
    h = select(p)
    rng_base = SEED
    out = {"window": list(WINDOW), "tol": TOL, "flows": CORE, "persist_rule": {"share": PERSIST_SHARE, "min_years": PERSIST_YEARS},
           "seed": SEED, "draws": B, "n_countries": int(h.geo.nunique()), "n_country_years": int((h.geo + h.year.astype(str)).nunique())}
    out["headline"] = statistic(h)
    out["inf_share"] = float(np.isinf(h.agap).mean())
    cy, co = bootstrap(h, "country_year"), bootstrap(h, "country")
    for name, bs in (("country_year", cy), ("country", co)):
        out[f"ci_{name}"] = {k: ci([r[k] for r in bs]) for k in ("share_within", "median", "p90", "n_persistent")}
        out[f"ci_{name}"]["by_flow"] = {f: ci([r["by_flow"][f] for r in bs]) for f in CORE}
    pd.DataFrame([{k: v for k, v in r.items() if k != "by_flow"} | {f"within_{f}": r["by_flow"][f] for f in CORE} for r in cy]).round(5).to_csv(os.path.join(RES, "bootstrap.csv"), index=False)

    bf = shares_by(h, "flow").set_index("flow").loc[CORE].reset_index()
    for f in CORE:
        for nm, bs in (("cy", cy), ("co", co)):
            lo, hi = ci([r["by_flow"][f] for r in bs])
            bf.loc[bf.flow == f, [f"lo_{nm}", f"hi_{nm}"]] = lo, hi
    bf.round(5).to_csv(os.path.join(RES, "by_flow.csv"), index=False)
    shares_by(h, "year").round(5).to_csv(os.path.join(RES, "by_year.csv"), index=False)
    bc = shares_by(h, "geo")
    bc.round(5).to_csv(os.path.join(RES, "by_country.csv"), index=False)
    h.assign(gap=h.gap.replace([np.inf, -np.inf], np.nan)).round(6).drop(columns=["eu27"]).to_csv(os.path.join(RES, "gaps_headline.csv"), index=False)

    tr = trace(h)
    tr.round(4).to_csv(os.path.join(RES, "persistent.csv"), index=False)
    out["persistent_causes"] = tr.cause.value_counts().to_dict()
    out["persistent_by_flow"] = tr.flow.value_counts().to_dict()

    # flagged observations against unflagged ones
    fl = (h.m_flags.str.contains("[eub]") | h.a_flag.str.contains("[ebd]")).values
    out["flagged"] = {"n": int(fl.sum()), "share_within": float((h.agap[fl] <= TOL).mean()), "share_within_unflagged": float((h.agap[~fl] <= TOL).mean())}
    rng = np.random.default_rng(SEED + 1)
    dl = []
    for _ in range(B_SWEEP):
        w = draw_weights(h, rng, "country_year")
        dl.append((w * fl * (h.agap.values <= TOL)).sum() / max((w * fl).sum(), 1e-9) - (w * ~fl * (h.agap.values <= TOL)).sum() / (w * ~fl).sum())
    out["flagged"]["diff"] = out["flagged"]["share_within"] - out["flagged"]["share_within_unflagged"]
    out["flagged"]["diff_ci"] = ci(dl)

    # DL: unflagged break in the annual series, 2024 to 2025
    dd = p[(p.flow == "DL") & (p.eu27 == 1)].pivot(index="geo", columns="year", values=["monthly_gwh", "annual_gwh"])
    both = dd.dropna(subset=[("annual_gwh", 2024), ("annual_gwh", 2025), ("monthly_gwh", 2024), ("monthly_gwh", 2025)])
    ra, rm = both[("annual_gwh", 2025)] / both[("annual_gwh", 2024)], both[("monthly_gwh", 2025)] / both[("monthly_gwh", 2024)]
    out["dl_break"] = {"n": int(len(both)), "median_annual_ratio": float(ra.median()), "median_monthly_ratio": float(rm.median()),
                       "annual_ratio_min": float(ra.min()), "annual_ratio_max": float(ra.max()), "annual_ratio_gt_1_2": int((ra > 1.2).sum())}
    dd2 = p[(p.flow == "DL") & (p.eu27 == 1) & p.alt_annual_gwh.notna()]
    out["dl_over_loss"] = {str(y): {"annual_dl": float((g.annual_gwh / g.alt_annual_gwh).median()), "monthly_dl": float((g.monthly_gwh / g.alt_annual_gwh).median())} for y, g in dd2.groupby("year")}
    dl_y = p[(p.flow == "DL") & (p.eu27 == 1)].groupby("year").agap.agg(lambda x: (x <= TOL).mean())
    out["dl_share_by_year"] = {str(k): float(v) for k, v in dl_y.items()}

    # shared offset between imports and exports
    w = h[h.flow.isin(["IMP", "EXP"])].assign(diff=lambda x: x.monthly_gwh - x.annual_gwh).pivot_table(index=["geo", "year"], columns="flow", values="diff").dropna()
    out["imp_exp"] = {"n": int(len(w)), "corr_gwh_gap": float(np.corrcoef(w.IMP, w.EXP)[0, 1]),
                      "same_sign_share": float((np.sign(w.IMP) == np.sign(w.EXP)).mean())}
    both_out = h[h.flow.isin(["IMP", "EXP"])]
    # sweep
    base_p = select(p)
    variants = [("base", "headline: EU27, IMP EXP DL PS, 2008-2025, tolerance 1%", dict(), TOL, {})]
    for t in (0.001, 0.005, 0.02, 0.05, 0.10):
        variants.append(("tolerance", f"tolerance {t * 100:g}%", dict(), t, {}))
    for fl_, lab in ((["IMP", "EXP"], "IMP EXP"), (["IMP", "EXP", "DL"], "IMP EXP DL"), (["IMP", "EXP", "PS"], "IMP EXP PS"), (["IMP"], "IMP only"), (["EXP"], "EXP only"),
                     (["DL"], "DL only"), (["PS"], "PS only"), (CORE + ["NEP"], "core + NEP (nrg_cb_pem)"), (["NEP"], "NEP only (nrg_cb_pem)")):
        variants.append(("flows", f"flows: {lab}", dict(flows=fl_), TOL, {}))
    variants.append(("flows", "DL against annual LOSS", dict(alt_dl=True), TOL, {}))
    variants.append(("flows", "DL only, against annual LOSS", dict(flows=["DL"], alt_dl=True), TOL, {}))
    for yrs in ((2015, 2025), (2018, 2025), (2008, 2024), (2008, 2019), (2019, 2025)):
        variants.append(("window", f"years {yrs[0]}-{yrs[1]}", dict(years=yrs), TOL, {}))
    variants.append(("zero pairs", "count pairs with both figures zero as coherent", dict(both_zero=True), TOL, {}))
    variants.append(("population", "all countries with data (EU27 + others)", dict(eu=False), TOL, {}))
    for fl_ in (10, 100, 1000):
        variants.append(("size floor", f"annual figure at least {fl_} GWh", dict(floor=fl_), TOL, {}))
    variants.append(("flags", "drop observations with an Eurostat flag", dict(drop_flagged=True), TOL, {}))
    for sh, nm in ((0.75, 5), (1.0, 5), (0.5, 3), (0.5, 8)):
        variants.append(("persistence rule", f"persistent: {int(sh * 100)}% of years outside, at least {nm} years", dict(), TOL, dict(share=sh, nmin=nm)))
    rows = []
    for g, lab, kw, tol, pk in variants:
        d = select(p, **kw)
        pr = persistent(d, tol, **pk) if pk else persistent(d, tol)
        rng = np.random.default_rng(SEED + 7)
        bs = []
        for _ in range(B_SWEEP):
            w = draw_weights(d, rng, "country_year")
            bs.append(float((w * (d.agap.values <= tol)).sum() / w.sum()))
        st = statistic(d, tol)
        rows.append({"group": g, "label": lab, "n": int(len(d)), "share_within": st["share_within"], "lo": ci(bs)[0], "hi": ci(bs)[1], "median_abs_gap": st["median"],
                     "p90": st["p90"], "n_persistent": int(len(pr))})
    sw = pd.DataFrame(rows)
    sw.round(5).to_csv(os.path.join(RES, "sweep.csv"), index=False)

    # rank stability of countries across variants
    rk = {}
    for lab, kw, tol in (("tolerance 1%", {}, 0.01), ("tolerance 0.5%", {}, 0.005), ("tolerance 2%", {}, 0.02), ("flows IMP EXP", dict(flows=["IMP", "EXP"]), 0.01),
                         ("years 2015-2025", dict(years=(2015, 2025)), 0.01), ("size floor 100 GWh", dict(floor=100), 0.01), ("core + NEP", dict(flows=CORE + ["NEP"]), 0.01)):
        d = select(p, **kw)
        rk[lab] = d.groupby("geo").agap.apply(lambda x: (x <= tol).mean())
    rk = pd.DataFrame(rk)
    sp = rk.rank().corr()
    sp.round(3).to_csv(os.path.join(RES, "rank_corr.csv"))
    out["rank_corr_min"] = float(sp.values[np.triu_indices(len(sp), 1)].min())
    out["rank_corr_min_pair"] = [sp.columns[i] for i, j in zip(*np.where(sp.values == out["rank_corr_min"]))][:2]

    # validation against a second publisher, and synthetic rounding check
    net = validate_ember(p, pd.read_csv(os.path.join(DATA, "ember_netimports.csv")))
    net.round(2).to_csv(os.path.join(RES, "validation_ember.csv"), index=False)
    ctrl = (net.d_m - net.d_a)
    rng = np.random.default_rng(SEED + 2)
    boot = [float((ctrl.values[i] > 0).mean()) for i in (rng.integers(0, len(net), len(net)) for _ in range(B_SWEEP))]
    out["ember"] = {"n": int(len(net)), "median_abs_diff_monthly": float(net.d_m.median()), "median_abs_diff_annual": float(net.d_a.median()),
                    "share_closer_to_annual": float((ctrl > 0).mean()), "share_closer_ci": ci(boot),
                    "within_1pct_monthly": float((net.d_m / net.scale <= 0.01).mean()), "within_1pct_annual": float((net.d_a / net.scale <= 0.01).mean())}
    wm, wa = (net.d_m / net.scale <= 0.01).values.astype(float), (net.d_a / net.scale <= 0.01).values.astype(float)
    out["ember"]["within_1pct_diff"] = float(wa.mean() - wm.mean())
    out["ember"]["within_1pct_diff_ci"] = ci([float((wa[i] - wm[i]).mean()) for i in (rng.integers(0, len(net), len(net)) for _ in range(B_SWEEP))])
    rn = rounding_noise()
    rn.round(5).to_csv(os.path.join(RES, "rounding_synthetic.csv"), index=False)
    out["zero_pairs_dropped"] = int(len(select(p, both_zero=True)) - len(h))
    out["small_flows"] = {"share_under_100": float((h.annual_gwh < 100).mean()), "share_within_under_100": float((h[h.annual_gwh < 100].agap <= TOL).mean()),
                          "share_within_100_plus": float((h[h.annual_gwh >= 100].agap <= TOL).mean())}
    out["backtest"] = "none: the module estimates a property of published data and projects nothing"
    json.dump(out, open(os.path.join(RES, "coherence.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("headline", "ci_country_year", "ci_country", "persistent_causes")}, indent=1))


if __name__ == "__main__":
    main()
