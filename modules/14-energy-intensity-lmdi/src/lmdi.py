"""What moved EU27 final energy use of the productive economy: activity, structure or intensity.

ESTIMAND. The change in EU27 final energy consumption of industry, services and agriculture
between 2015 and the latest year in the data, in ktoe, split into an activity effect (growth of
total gross value added), a structure effect (shifts of value added between sector-by-member-state
cells) and an intensity effect (change in energy per unit of value added inside a cell), by
additive LMDI-I, chained year by year. The three effects sum to the observed change exactly.

Data: Eurostat nrg_bal_s (final consumption by sector, KTOE) and nama_10_a10 (gross value added,
chain-linked volumes, 2015 prices), fetched by src/fetch.py. Households and transport are outside
the estimand: they have no value-added denominator.

    python3 src/lmdi.py
"""
import csv
import json
import math
import os

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA, RESULTS = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")

BASE_YEAR = 2015
N_BOOT = 2000
SEED = 14

# sector -> (energy balance code, NACE rev. 2 A*10 codes whose value added it is divided by)
SERV_ALL = ["G-I", "J", "K", "L", "M_N", "O-Q", "R-U"]
MAPPINGS = {
    "base: industry B-E+F, services G-U, agriculture A": {
        "industry": ("FC_IND_E", ["B-E", "F"]), "services": ("FC_OTH_CP_E", SERV_ALL),
        "agriculture": ("FC_OTH_AF_E", ["A"])},
    "industry = B-E only (F dropped)": {
        "industry": ("FC_IND_E", ["B-E"]), "services": ("FC_OTH_CP_E", SERV_ALL),
        "agriculture": ("FC_OTH_AF_E", ["A"])},
    "industry = manufacturing C + F": {
        "industry": ("FC_IND_E", ["C", "F"]), "services": ("FC_OTH_CP_E", SERV_ALL),
        "agriculture": ("FC_OTH_AF_E", ["A"])},
    "services = J to O-Q (G-I and R-U out)": {
        "industry": ("FC_IND_E", ["B-E", "F"]),
        "services": ("FC_OTH_CP_E", ["J", "K", "L", "M_N", "O-Q"]),
        "agriculture": ("FC_OTH_AF_E", ["A"])},
    "services = G-I to M_N (O-Q and R-U out)": {
        "industry": ("FC_IND_E", ["B-E", "F"]),
        "services": ("FC_OTH_CP_E", ["G-I", "J", "K", "L", "M_N"]),
        "agriculture": ("FC_OTH_AF_E", ["A"])},
}
BASE_MAPPING = next(iter(MAPPINGS))


# ----------------------------------------------------------------------------- loading
def _read(name):
    with open(os.path.join(DATA, name + ".csv")) as f:
        return list(csv.DictReader(f))


def load():
    energy, gva, hdd, ei, hicp = {}, {}, {}, {}, {}
    for r in _read("energy"):
        energy.setdefault((r["geo"], r["nrg_bal"]), {})[int(r["time"])] = float(r["value"])
    for r in _read("gva"):
        gva.setdefault((r["geo"], r["nace_r2"]), {})[int(r["time"])] = float(r["value"])
    for r in _read("hdd"):
        hdd.setdefault(r["geo"], {})[int(r["time"])] = float(r["value"])
    for r in _read("hicp"):
        hicp.setdefault(r["coicop"], {})[int(r["time"])] = float(r["value"])
    for r in _read("ei"):
        ei[int(r["time"])] = float(r["value"])
    return {"energy": energy, "gva": gva, "hdd": hdd, "ei": ei, "hicp": hicp}


def members(panel):
    return sorted({g for g, _ in panel["energy"] if g != "EU27_2020"})


def last_year(panel, geos=None):
    geos = geos or members(panel)
    return min(max(panel["energy"][(g, "FC_IND_E")]) for g in geos)


def build(panel, mapping, years, geos=None, adjust=None):
    """Cell arrays E, V of shape (cells, years) and the cell labels (geo, sector).

    adjust: optional {(geo, sector): multiplier array over years} applied to energy.
    """
    geos = geos or members(panel)
    E, V, lab = [], [], []
    for g in geos:
        for s, (bal, naces) in mapping.items():
            e = np.array([panel["energy"][(g, bal)][y] for y in years])
            v = np.array([sum(panel["gva"][(g, n)][y] for n in naces) for y in years])
            if adjust and (g, s) in adjust:
                e = e * adjust[(g, s)]
            E.append(e); V.append(v); lab.append((g, s))
    return np.array(E), np.array(V), lab


# ----------------------------------------------------------------------------- LMDI-I
def logmean(a, b):
    """L(a, b) = (a - b) / (ln a - ln b), L(a, a) = a. Both must be positive."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if (a <= 0).any() or (b <= 0).any():
        raise ValueError("logarithmic mean needs strictly positive energy in every cell")
    same = np.isclose(a, b, rtol=1e-12, atol=0)
    out = np.where(same, a, 0.0)
    d = ~same
    out[d] = (a[d] - b[d]) / (np.log(a[d]) - np.log(b[d]))
    return out


def step(E0, V0, E1, V1):
    """Additive LMDI-I between two years. Returns per-cell effects and their sums."""
    w = logmean(E1, E0)
    Q0, Q1 = V0.sum(), V1.sum()
    act = w * math.log(Q1 / Q0)
    stc = w * np.log((V1 / Q1) / (V0 / Q0))
    inten = w * np.log((E1 / V1) / (E0 / V0))
    return {"act_i": act, "str_i": stc, "int_i": inten,
            "act": act.sum(), "str": stc.sum(), "int": inten.sum(), "dE": E1.sum() - E0.sum()}


def chain(E, V, idx):
    """Sum of the year-to-year effects along idx (column indices); direct = idx of two entries."""
    tot = {"act": 0.0, "str": 0.0, "int": 0.0, "dE": 0.0}
    tot["int_steps"] = []
    cells = {k: np.zeros(E.shape[0]) for k in ("act_i", "str_i", "int_i")}
    for a, b in zip(idx[:-1], idx[1:]):
        s = step(E[:, a], V[:, a], E[:, b], V[:, b])
        for k in ("act", "str", "int", "dE"):
            tot[k] += s[k]
        tot["int_steps"].append(float(s["int"]))
        for k in cells:
            cells[k] += s[k]
    tot.update(cells)
    return tot


def annual(E, V, years):
    out = []
    for a in range(len(years) - 1):
        s = step(E[:, a], V[:, a], E[:, a + 1], V[:, a + 1])
        out.append({"year": years[a + 1], **{k: float(s[k]) for k in ("act", "str", "int", "dE")}})
    return out


# ----------------------------------------------------------------------------- interval
def bootstrap(E, V, lab, geos, idx, late_cols=(), n=N_BOOT, seed=SEED):
    """Cluster bootstrap over member states. A drawn state brings all its sector cells with it,
    so the sectors of one country are never resampled independently. The EU27 total, activity
    and structure are recomputed on every draw: the draw is a different EU, not the same EU with
    noisy effects."""
    rng = np.random.default_rng(seed)
    late_cols = set(late_cols)
    cell_of = {g: [i for i, (gg, _) in enumerate(lab) if gg == g] for g in geos}
    draws, worst = [], 0.0
    for _ in range(n):
        pick = rng.integers(0, len(geos), len(geos))
        ix = [i for p in pick for i in cell_of[geos[p]]]
        t = chain(E[ix], V[ix], idx)
        worst = max(worst, abs(t["act"] + t["str"] + t["int"] - t["dE"]))
        late = sum(x for x, y in zip(t["int_steps"], idx[1:]) if y in late_cols)
        draws.append((t["act"], t["str"], t["int"], t["dE"], E[ix][:, idx[0]].sum(), late))
    d = np.array(draws)
    return d, worst


def ci(x, level=0.95):
    lo, hi = np.percentile(x, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return [float(lo), float(hi)]


def jackknife(E, V, lab, geos, idx):
    out = {}
    for g in geos:
        ix = [i for i, (gg, _) in enumerate(lab) if gg != g]
        t = chain(E[ix], V[ix], idx)
        out[g] = {k: float(t[k]) for k in ("act", "str", "int", "dE")}
    return out


# ----------------------------------------------------------------------------- weather
def weather_elasticity(panel, mapping):
    """Elasticity of services energy to heating degree days, from a country fixed-effects
    regression of ln E on ln HDD, ln GVA and a linear trend, 2005 to the last year, with
    standard errors clustered by member state."""
    geos = members(panel)
    bal, naces = mapping["services"]
    years = list(range(2005, last_year(panel) + 1))
    y, X, cl = [], [], []
    for gi, g in enumerate(geos):
        for t in years:
            e = panel["energy"][(g, bal)][t]
            v = sum(panel["gva"][(g, n)][t] for n in naces)
            row = [0.0] * len(geos)
            row[gi] = 1.0
            X.append(row + [math.log(panel["hdd"][g][t]), math.log(v), t - 2015])
            y.append(math.log(e)); cl.append(gi)
    X, y, cl = np.array(X), np.array(y), np.array(cl)
    XtXi = np.linalg.inv(X.T @ X)
    b = XtXi @ X.T @ y
    u = y - X @ b
    meat = sum(np.outer(X[cl == c].T @ u[cl == c], X[cl == c].T @ u[cl == c])
               for c in range(len(geos)))
    k = len(geos)
    G, n, p = len(geos), len(y), X.shape[1]
    V = XtXi @ meat @ XtXi * (G / (G - 1)) * ((n - 1) / (n - p))
    se = np.sqrt(np.diag(V))
    return {"elasticity_hdd": float(b[k]), "se": float(se[k]),
            "elasticity_gva": float(b[k + 1]), "trend_per_year": float(b[k + 2]),
            "n_obs": int(n), "clusters": G}


def weather_adjust(panel, mapping, years, beta):
    """Services energy restated at each country's own 2005-to-last-year mean HDD."""
    adj = {}
    for g in members(panel):
        h = panel["hdd"][g]
        mean = np.mean([h[t] for t in range(2005, last_year(panel) + 1)])
        adj[(g, "services")] = np.array([(mean / h[t]) ** beta for t in years])
    return adj


# ----------------------------------------------------------------------------- analysis
def pct(x, base):
    return 100.0 * x / base


def summarise(t, base):
    return {"act": t["act"], "str": t["str"], "int": t["int"], "dE": t["dE"],
            "act_pct": pct(t["act"], base), "str_pct": pct(t["str"], base),
            "int_pct": pct(t["int"], base), "dE_pct": pct(t["dE"], base)}


def run_variant(panel, mapping, years, idx=None, geos=None, adjust=None):
    E, V, lab = build(panel, mapping, years, geos, adjust)
    idx = idx or list(range(len(years)))
    t = chain(E, V, idx)
    return summarise(t, E[:, idx[0]].sum()), (E, V, lab, t)


def analyse():
    panel = load()
    geos = members(panel)
    last = last_year(panel)
    years = list(range(BASE_YEAR, last + 1))
    mapping = MAPPINGS[BASE_MAPPING]
    E, V, lab = build(panel, mapping, years)
    idx = list(range(len(years)))
    head = chain(E, V, idx)
    base_E = E[:, 0].sum()
    res = {"estimand": ("change in EU27 final energy consumption of industry, services and "
                        "agriculture, base year to latest year, ktoe, additive LMDI-I chained "
                        "year by year: activity + structure + intensity = observed change"),
           "base_year": BASE_YEAR, "last_year": last, "member_states": len(geos),
           "cells": len(lab), "mapping": BASE_MAPPING,
           "energy_base_ktoe": float(base_E), "energy_last_ktoe": float(E[:, -1].sum()),
           "gva_base_meur": float(V[:, 0].sum()), "gva_last_meur": float(V[:, -1].sum())}

    # headline with interval
    late = [years.index(y) for y in (2022, 2023)]
    d, worst = bootstrap(E, V, lab, geos, idx, late)
    res["headline"] = summarise(head, base_E)
    res["identity_residual_ktoe"] = float(abs(head["act"] + head["str"] + head["int"] - head["dE"]))
    res["bootstrap"] = {"n": N_BOOT, "seed": SEED, "unit": "member state (all its sector cells)",
                        "max_identity_residual_ktoe": float(worst),
                        "act": ci(d[:, 0]), "str": ci(d[:, 1]), "int": ci(d[:, 2]),
                        "dE": ci(d[:, 3]),
                        "act_pct": ci(100 * d[:, 0] / d[:, 4]), "str_pct": ci(100 * d[:, 1] / d[:, 4]),
                        "int_pct": ci(100 * d[:, 2] / d[:, 4]), "dE_pct": ci(100 * d[:, 3] / d[:, 4]),
                        "share_draws_intensity_negative": float((d[:, 2] < 0).mean()),
                        "share_draws_structure_negative": float((d[:, 1] < 0).mean()),
                        "share_draws_intensity_offsets_activity": float((d[:, 0] + d[:, 2] < 0).mean()),
                        "intensity_share_of_offset": ci(d[:, 2] / (d[:, 1] + d[:, 2])),
                        "intensity_2022_23_share": ci(d[:, 5] / d[:, 2])}
    res["intensity_share_of_offset"] = float(head["int"] / (head["str"] + head["int"]))
    res["intensity_2022_23_share"] = float(sum(head["int_steps"][i - 1] for i in late) / head["int"])
    res["intensity_2016_19_share"] = float(sum(head["int_steps"][:4]) / head["int"])
    res["annual"] = annual(E, V, years)

    # by sector and by country
    sectors = list(mapping)
    res["by_sector"] = {s: {k: float(sum(head[k + "_i"][i] for i, (g, ss) in enumerate(lab) if ss == s))
                            for k in ("act", "str", "int")} for s in sectors}
    for s in sectors:
        i0 = [i for i, (g, ss) in enumerate(lab) if ss == s]
        res["by_sector"][s]["energy_base_ktoe"] = float(E[i0, 0].sum())
        res["by_sector"][s]["energy_last_ktoe"] = float(E[i0, -1].sum())
        res["by_sector"][s]["gva_share_base"] = float(V[i0, 0].sum() / V[:, 0].sum())
        res["by_sector"][s]["gva_share_last"] = float(V[i0, -1].sum() / V[:, -1].sum())
        res["by_sector"][s]["intensity_base"] = float(E[i0, 0].sum() / V[i0, 0].sum())
        res["by_sector"][s]["intensity_last"] = float(E[i0, -1].sum() / V[i0, -1].sum())
    byc = {}
    for g in geos:
        i0 = [i for i, (gg, _) in enumerate(lab) if gg == g]
        byc[g] = {k: float(sum(head[k + "_i"][i] for i in i0)) for k in ("act", "str", "int")}
        byc[g]["dE"] = float(E[i0, -1].sum() - E[i0, 0].sum())
        byc[g]["energy_base_ktoe"] = float(E[i0, 0].sum())
    res["by_country"] = byc

    # leave-one-out
    jk = jackknife(E, V, lab, geos, idx)
    res["jackknife"] = {g: jk[g] for g in geos}
    infl = max(geos, key=lambda g: abs(jk[g]["int"] - head["int"]))
    res["jackknife_most_influential"] = {"geo": infl, "int_without": jk[infl]["int"],
                                         "int_with": float(head["int"])}

    # ---- sweeps
    sweep = []

    def add(group, name, summ):
        sweep.append({"group": group, "variant": name, **summ})

    s, _ = run_variant(panel, mapping, years)
    add("base", "base case", s)
    for name, m in MAPPINGS.items():
        if name != BASE_MAPPING:
            s, _ = run_variant(panel, m, years)
            add("sector mapping", name, s)
    for b in (2010, 2013, 2018):
        yrs = list(range(b, last + 1))
        s, _ = run_variant(panel, mapping, yrs)
        add("base year", f"{b} to {last}", s)
    yrs19 = list(range(BASE_YEAR, 2020))
    s, _ = run_variant(panel, mapping, yrs19)
    add("end year", f"{BASE_YEAR} to 2019 (before COVID and the crisis)", s)
    s, _ = run_variant(panel, mapping, list(range(BASE_YEAR, last)))
    add("end year", f"{BASE_YEAR} to {last - 1}", s)
    no20 = [y for y in years if y != 2020]
    s, _ = run_variant(panel, mapping, no20)
    add("2020", "2020 left out of the chain", s)
    s, _ = run_variant(panel, mapping, years, idx=[0, len(years) - 1])
    add("path", "direct endpoints, no chain", s)
    s, _ = run_variant(panel, mapping, list(range(2021, last + 1)))
    add("2020", f"2021 to {last} only", s)

    # granularity: one cell per country; EU27 official aggregates by sector
    Ep = np.array([[E[[i for i, (gg, _) in enumerate(lab) if gg == g], t].sum() for t in range(len(years))]
                   for g in geos])
    Vp = np.array([[V[[i for i, (gg, _) in enumerate(lab) if gg == g], t].sum() for t in range(len(years))]
                   for g in geos])
    t = chain(Ep, Vp, idx)
    add("granularity", "one cell per state (no sector detail)", summarise(t, Ep[:, 0].sum()))
    Ee, Ve, _ = build(panel, mapping, years, geos=["EU27_2020"])
    t = chain(Ee, Ve, idx)
    add("granularity", "EU27 aggregates, 3 sectors (no state detail)",
        summarise(t, Ee[:, 0].sum()))
    Ea, Va = Ee.sum(0, keepdims=True), Ve.sum(0, keepdims=True)
    t = chain(Ea, Va, idx)
    add("granularity", "one EU27 cell (activity and intensity only)", summarise(t, Ea[:, 0].sum()))

    # weather
    wx = weather_elasticity(panel, mapping)
    res["weather_model"] = wx
    adj = weather_adjust(panel, mapping, years, wx["elasticity_hdd"])
    s, (Ew, Vw, labw, tw) = run_variant(panel, mapping, years, adjust=adj)
    add("weather", f"services energy at mean HDD (elasticity {wx['elasticity_hdd']:.2f})", s)
    for beta, name in ((wx["elasticity_hdd"] - 1.96 * wx["se"], "HDD elasticity, low end"),
                       (wx["elasticity_hdd"] + 1.96 * wx["se"], "HDD elasticity, high end")):
        adj_b = weather_adjust(panel, mapping, years, beta)
        s, _ = run_variant(panel, mapping, years, adjust=adj_b)
        add("weather", f"{name} ({beta:.2f})", s)
    hdd_eu = panel["hdd"]["EU27_2020"]
    res["hdd_eu27"] = {"base": hdd_eu[BASE_YEAR], "last": hdd_eu[last],
                       "change_pct": pct(hdd_eu[last] - hdd_eu[BASE_YEAR], hdd_eu[BASE_YEAR]),
                       "mean_2005_last": float(np.mean([hdd_eu[t] for t in range(2005, last + 1)]))}
    hp = panel["hicp"]
    res["energy_price"] = {"source": "prc_hicp_aind, EU27, annual average index 2015=100",
                           "energy_hicp": {str(y): hp["NRG"][y] for y in years},
                           "all_items_hicp": {str(y): hp["CP00"][y] for y in years},
                           "real_energy_price": {str(y): 100 * hp["NRG"][y] / hp["CP00"][y] for y in years}}
    res["sweep"] = sweep
    ints = [r["int"] for r in sweep]
    intp = [r["int_pct"] for r in sweep]
    res["sweep_range"] = {"int_ktoe": [min(ints), max(ints)], "int_pct": [min(intp), max(intp)],
                          "all_negative": all(x < 0 for x in ints),
                          "by_group": {g: [min(r["int_pct"] for r in sweep if r["group"] == g),
                                           max(r["int_pct"] for r in sweep if r["group"] == g)]
                                       for g in dict.fromkeys(r["group"] for r in sweep)}}

    # ---- validation against what Eurostat publishes
    val = {}
    chk = {}
    for s, (bal, naces) in mapping.items():
        for y in (BASE_YEAR, last):
            e_sum = sum(panel["energy"][(g, bal)][y] for g in geos)
            e_pub = panel["energy"][("EU27_2020", bal)][y]
            v_sum = sum(sum(panel["gva"][(g, n)][y] for n in naces) for g in geos)
            v_pub = sum(panel["gva"][("EU27_2020", n)][y] for n in naces)
            chk[f"{s} {y}"] = {"energy_sum_over_states": e_sum, "energy_eu27": e_pub,
                               "energy_diff_pct": pct(e_sum - e_pub, e_pub),
                               "gva_sum_over_states": v_sum, "gva_eu27": v_pub,
                               "gva_diff_pct": pct(v_sum - v_pub, v_pub)}
    val["additivity"] = chk
    val["max_abs_energy_diff_pct"] = max(abs(c["energy_diff_pct"]) for c in chk.values())
    val["max_abs_gva_diff_pct"] = max(abs(c["gva_diff_pct"]) for c in chk.values())
    own = (E[:, -1].sum() / V[:, -1].sum()) / (E[:, 0].sum() / V[:, 0].sum()) - 1
    ei = panel["ei"]
    val["intensity_change_pct"] = {
        "productive_economy_final_energy_per_gva": 100 * own,
        "eurostat_nrg_ind_ei_gross_available_energy_per_gdp_clv15": 100 * (ei[last] / ei[BASE_YEAR] - 1)}
    val["lmdi_intensity_plus_structure_pct"] = res["headline"]["int_pct"] + res["headline"]["str_pct"]
    res["validation"] = val
    return res, panel


def write(res):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "lmdi.json"), "w") as f:
        json.dump(res, f, indent=1)
    with open(os.path.join(RESULTS, "sweep.csv"), "w", newline="") as f:
        w = csv.writer(f)
        cols = ["group", "variant", "act", "str", "int", "dE", "act_pct", "str_pct", "int_pct", "dE_pct"]
        w.writerow(cols)
        for r in res["sweep"]:
            w.writerow([r[c] if isinstance(r[c], str) else round(r[c], 4) for c in cols])
    with open(os.path.join(RESULTS, "annual.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "act", "str", "int", "dE"])
        for r in res["annual"]:
            w.writerow([r["year"]] + [round(r[k], 3) for k in ("act", "str", "int", "dE")])


def main():
    res, _ = analyse()
    write(res)
    h, b = res["headline"], res["bootstrap"]
    print(f"{res['base_year']} to {res['last_year']}: {res['member_states']} states, {res['cells']} cells, "
          f"base energy {res['energy_base_ktoe']:.0f} ktoe")
    for k, n in (("dE", "observed change"), ("act", "activity"), ("str", "structure"), ("int", "intensity")):
        print(f"  {n:16s} {h[k]:10.0f} ktoe  {h[k + '_pct']:+6.1f}%  95% CI [{b[k][0]:.0f}, {b[k][1]:.0f}]"
              f"  ({b[k + '_pct'][0]:+.1f}%, {b[k + '_pct'][1]:+.1f}%)")
    print(f"intensity share of offset {res['intensity_share_of_offset']:.3f} {b['intensity_share_of_offset']}; "
          f"2022-23 share {res['intensity_2022_23_share']:.3f} {b['intensity_2022_23_share']}; "
          f"2016-19 {res['intensity_2016_19_share']:.3f}; P(int+act<0)={b['share_draws_intensity_offsets_activity']:.3f}")
    print(f"identity residual {res['identity_residual_ktoe']:.2e} ktoe")
    print("\nsweep (intensity effect, % of base energy):")
    for r in res["sweep"]:
        print(f"  {r['group']:15s} {r['int_pct']:+7.1f}%  act {r['act_pct']:+6.1f} str {r['str_pct']:+6.1f}  {r['variant']}")
    print("\nweather", res["weather_model"])
    print("validation", json.dumps(res["validation"]["intensity_change_pct"]),
          res["validation"]["max_abs_energy_diff_pct"], res["validation"]["max_abs_gva_diff_pct"])
    print("jackknife", res["jackknife_most_influential"])


if __name__ == "__main__":
    main()
