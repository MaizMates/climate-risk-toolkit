"""Share of a real equity fund's market value in companies with a high ENCORE dependency on
ecosystem services, with an interval and a sweep of the choices that cannot be justified.

    python3 src/encore.py     # reads data/raw/ (run src/fetch.py first), writes results/

Estimand: the share of the fund's market value held in companies whose activity carries a High
or Very High ENCORE dependency rating on ecosystem service s (and on at least one of the 25),
where a company's activity is the set of ENCORE production processes its GICS industry maps to.
"""
import html
import io
import json
import os
import re
import warnings

import numpy as np
import openpyxl
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
RES = os.path.join(HERE, "..", "results")

N_DRAW = 5000
SEED = 12
THRESHOLDS = {"VH": {"VH"}, "H+": {"VH", "H"}, "M+": {"VH", "H", "M"}}
BASE = {"variant": "base", "threshold": "H+", "weighting": "process"}

# GICS industry (as printed in the holdings file) -> ENCORE sub-industry names, by unique prefix.
# The first entry is the dominant activity and defines the "narrow" variant. Reasoning per
# industry is in notes.md; the labels are mine, the names are resolved against the fetched file.
GICS_TO_ENCORE = {
    "Banks": ["Financial service activities, except"],
    "Semiconductors & Semiconductor Equipment": ["Manufacture of computer, electronic"],
    "Insurance": ["Insurance, reinsurance"],
    "Aerospace & Defense": ["Manufacture of other transport", "Manufacture of fabricated metal"],
    "Electrical Equipment": ["Manufacture of electrical equipment"],
    "Electric Utilities": ["Electricity, gas, steam"],
    "Oil Gas & Consumable Fuels": ["Extraction of crude petroleum", "Manufacture of coke"],
    "Software": ["Publishing activities", "Computer programming"],
    "Chemicals": ["Manufacture of chemicals"],
    "Textiles Apparel & Luxury Goods": ["Manufacture of wearing apparel", "Manufacture of leather",
                                        "Manufacture of textiles"],
    "Industrial Conglomerates": ["Manufacture of machinery", "Manufacture of electrical equipment"],
    "Pharmaceuticals": ["Manufacture of basic pharmaceutical"],
    "Diversified Telecommunication Services": ["Telecommunications"],
    "Beverages": ["Manufacture of beverages"],
    "Capital Markets": ["Financial service activities, except", "Activities auxiliary to financial"],
    "Automobiles": ["Manufacture of motor vehicles"],
    "Construction & Engineering": ["Construction of buildings", "Civil engineering",
                                   "Specialized construction"],
    "Personal Care Products": ["Manufacture of chemicals"],
    "Multi-Utilities": ["Electricity, gas, steam", "Water collection"],
    "Health Care Equipment & Supplies": ["Other manufacturing", "Manufacture of computer, electronic"],
    "Machinery": ["Manufacture of machinery"],
    "Specialty Retail": ["Retail trade, except"],
    "Food Products": ["Manufacture of food products"],
    "Financial Services": ["Financial service activities, except", "Activities auxiliary to financial"],
    "Biotechnology": ["Manufacture of basic pharmaceutical"],
    "Air Freight & Logistics": ["Air transport", "Warehousing and support", "Postal and courier"],
    "Consumer Staples Distribution & Retail": ["Retail trade, except"],
    "Building Products": ["Manufacture of other non-metallic", "Manufacture of fabricated metal"],
    "Hotels Restaurants & Leisure": ["Accommodation", "Food and beverage service"],
    "Communications Equipment": ["Manufacture of computer, electronic"],
    "Broadline Retail": ["Retail trade, except"],
    "Independent Power And Renewable Electricity Producers": ["Electricity, gas, steam"],
    "Trading Companies & Distributors": ["Wholesale trade, except"],
    "Life Sciences Tools & Services": ["Manufacture of basic pharmaceutical", "Scientific research"],
    "Gas Utilities": ["Electricity, gas, steam"],
    "Transportation Infrastructure": ["Warehousing and support", "Land transport"],
    "Professional Services": ["Activities of head offices", "Employment activities"],
    "Automobile Components": ["Manufacture of motor vehicles"],
    "Health Care Providers & Services": ["Human health activities"],
    "It Services": ["Computer programming"],
    "Metals & Mining": ["Mining of metal ores", "Manufacture of basic metals"],
    "Media": ["Programming and broadcasting", "Publishing activities"],
    "Construction Materials": ["Manufacture of other non-metallic"],
    "Passenger Airlines": ["Air transport"],
    "Household Products": ["Manufacture of chemicals"],
    "Paper & Forest Products": ["Manufacture of paper", "Manufacture of wood", "Forestry and logging"],
    "Retail Reits": ["Real estate activities"],
    "Office Reits": ["Real estate activities"],
    "Diversified Reits": ["Real estate activities"],
    "Real Estate Management & Development": ["Real estate activities"],
    "Entertainment": ["Creative, arts", "Motion picture"],
    "Energy Equipment & Services": ["Mining support"],
    "Distributors": ["Wholesale trade, except"],
    "Ground Transportation": ["Land transport"],
}
FINANCIAL_INDUSTRIES = {"Banks", "Insurance", "Capital Markets", "Financial Services"}


def load_encore(raw=RAW):
    """-> (services, processes, ratings). processes: id -> dict(name, sub, section, subs);
    ratings: (service index, process id) -> rating letter(s)."""
    sectors = json.load(open(os.path.join(raw, "sectors.json")))
    services_raw = json.load(open(os.path.join(raw, "ecosystem_services.json")))
    processes, subs = {}, {}
    for sec in sectors:
        for sub in sec["sub_industries"]:
            subs[sub["name"]] = {"section": sec["name"], "pids": [p["id"] for p in sub["production_processes"]]}
            for p in sub["production_processes"]:
                processes[p["id"]] = {"name": p["name"], "sub": sub["name"], "section": sec["name"]}
    services = [g["name"] for g in services_raw]
    ratings = {}
    for si, g in enumerate(services_raw):
        for m in g["sorted_materialities"]:
            key = (si, m["production_process"]["id"])
            assert key not in ratings, f"duplicate rating {key}"
            assert m["rag"] in {"VH", "H", "M", "L", "VL"}, m["rag"]
            assert m["production_process"]["id"] in processes, m["production_process"]
            ratings[key] = m["rag"]
    return services, processes, subs, ratings


def flag_matrix(services, processes, ratings, threshold):
    """-> (pids, bool array [process, service + 1]); the last column is 'at least one service'."""
    pids = sorted(processes)
    col = {p: i for i, p in enumerate(pids)}
    ok = THRESHOLDS[threshold]
    m = np.zeros((len(pids), len(services) + 1), dtype=bool)
    for (si, pid), r in ratings.items():
        if r in ok:
            m[col[pid], si] = True
    m[:, -1] = m[:, :-1].any(axis=1)
    return pids, m


def resolve(prefix, subs):
    hits = [n for n in subs if n.startswith(prefix)]
    if len(hits) != 1:
        raise ValueError(f"'{prefix}' matches {hits}")
    return hits[0]


def process_weights(industry, variant, weighting, subs, mapping=GICS_TO_ENCORE):
    """-> {process id: weight}, weights sum to 1. variant: narrow = dominant sub-industry only,
    base = every listed sub-industry, broad = every sub-industry of the sections they sit in.
    weighting: 'process' = each process equal; 'sub' = each sub-industry equal, then its processes."""
    names = [resolve(p, subs) for p in mapping[industry]]
    if variant == "narrow":
        names = names[:1]
    elif variant == "broad":
        secs = {subs[n]["section"] for n in names}
        names = [n for n in subs if subs[n]["section"] in secs]
    elif variant != "base":
        raise ValueError(variant)
    w = {}
    if weighting == "process":
        pids = [p for n in names for p in subs[n]["pids"]]
        for p in pids:
            w[p] = w.get(p, 0) + 1.0 / len(pids)
    elif weighting == "sub":
        for n in names:
            for p in subs[n]["pids"]:
                w[p] = w.get(p, 0) + 1.0 / (len(names) * len(subs[n]["pids"]))
    else:
        raise ValueError(weighting)
    return w


def parse_holdings(raw_bytes):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    meta = {r[0]: r[1] for r in rows[:5] if r and r[0]}
    hi = next(i for i, r in enumerate(rows) if r and r[0] == "ISIN")
    expected = ("ISIN", "SEDOL", "Security Name", "Currency", "Number of Shares", "Percent of Fund",
                "Trade Country Name", "Local Price", "Sector Classification",
                "Industry Classification", "Base Market Value")
    if tuple(rows[hi][:11]) != expected:
        raise ValueError(f"holdings header changed: {rows[hi]}")
    out, unassigned = [], 0.0
    for r in rows[hi + 1:]:
        if not r or not r[0] or not isinstance(r[10], (int, float)) or r[10] <= 0:
            continue
        if r[9] == "Unassigned":
            unassigned += float(r[10])
            continue
        out.append({"isin": r[0], "name": r[2], "sector": r[8], "industry": r[9], "mv": float(r[10])})
    return pd.DataFrame(out), unassigned, meta


def point_share(h, matrix, pid_col, subs, variant="base", weighting="process", mapping=GICS_TO_ENCORE):
    """Expected flagged share of market value for every column of `matrix` (services + any)."""
    cache = {}
    num = np.zeros(matrix.shape[1])
    for ind, g in h.groupby("industry"):
        w = process_weights(ind, variant, weighting, subs, mapping)
        idx = np.array([pid_col[p] for p in w])
        cache[ind] = (matrix[idx] * np.array(list(w.values()))[:, None]).sum(axis=0)
        num += g["mv"].sum() * cache[ind]
    return num / h["mv"].sum(), cache


def draw_shares(h, matrix, pid_col, subs, mix_variants, n=N_DRAW, seed=SEED, weighting="process",
                mapping=GICS_TO_ENCORE):
    """Monte Carlo of the flagged share. Each holding draws ONE process from its industry's
    process distribution: a company's own activity mix is its own, so holdings are independent.
    With mix_variants, each industry also draws one mapping variant per resample, shared by every
    holding in that industry, because a wrong crosswalk is wrong for all of them at once.
    The fund is not resampled: the estimand is this fund."""
    rng = np.random.default_rng(seed)
    total = h["mv"].sum()
    variants = ["narrow", "base", "broad"] if mix_variants else ["base"]
    acc = np.zeros((n, matrix.shape[1]))
    for ind, g in h.groupby("industry"):
        pick = rng.integers(len(variants), size=n) if mix_variants else np.zeros(n, dtype=int)
        for mv in g["mv"]:
            res = np.zeros((n, matrix.shape[1]))
            for k, v in enumerate(variants):
                w = process_weights(ind, v, weighting, subs, mapping)
                idx = np.array([pid_col[p] for p in w])
                draw = idx[rng.choice(len(idx), size=n, p=np.array(list(w.values())))]
                sel = pick == k
                res[sel] = matrix[draw[sel]]
            acc += mv * res
    return acc / total


def spearman(a, b):
    """Rank correlation with average ranks for ties (no scipy)."""
    return float(np.corrcoef(pd.Series(a).rank().values, pd.Series(b).rank().values)[0, 1])


def ci(x, lo=2.5, hi=97.5):
    return float(np.percentile(x, lo)), float(np.percentile(x, hi))


def ecb_comparator(raw=RAW):
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", open(os.path.join(raw, "ecb_blog.html"), encoding="utf-8").read())))
    loans = re.search(r"nearly (\d+) per cent of all bank loans", t)
    comps = re.search(r"approximately (\d+) per cent of companies", t)
    thr = re.search(r"dependency score \(greater than ([\d.]+)\)", t)
    return {"loans_share_pct": int(loans.group(1)) if loans else None,
            "companies_share_pct": int(comps.group(1)) if comps else None,
            "score_threshold": float(thr.group(1)) if thr else None}


def build():
    services, processes, subs, ratings = load_encore()
    h, unassigned, meta = parse_holdings(open(os.path.join(RAW, "zpre_holdings.xlsx"), "rb").read())
    unmapped = sorted(set(h["industry"]) - set(GICS_TO_ENCORE))
    assert not unmapped, f"industries without a mapping: {unmapped}"
    total = float(h["mv"].sum())
    mats = {t: flag_matrix(services, processes, ratings, t) for t in THRESHOLDS}
    pids = mats["H+"][0]
    pid_col = {p: i for i, p in enumerate(pids)}
    names = services + ["at least one service"]

    base_pt, per_ind = point_share(h, mats["H+"][1], pid_col, subs)
    d_cond = draw_shares(h, mats["H+"][1], pid_col, subs, mix_variants=False)
    d_mix = draw_shares(h, mats["H+"][1], pid_col, subs, mix_variants=True)
    any_i = len(services)

    svc = []
    for i, n in enumerate(names):
        svc.append({"service": n, "share": float(base_pt[i]), "ci_cond": ci(d_cond[:, i]),
                    "ci_mix": ci(d_mix[:, i])})

    # sweep: mapping x threshold x weighting, headline and per-service ranking
    sweep = []
    for v in ("narrow", "base", "broad"):
        for t in THRESHOLDS:
            for wt in ("process", "sub"):
                pt, _ = point_share(h, mats[t][1], pid_col, subs, v, wt)
                rho = spearman(pt[:any_i], base_pt[:any_i])
                sweep.append({"variant": v, "threshold": t, "weighting": wt,
                              "any": float(pt[any_i]), "rank_corr_services": rho})
    sw = pd.DataFrame(sweep)
    base_any = float(base_pt[any_i])

    def swing(col):
        m = sw[(sw[[c for c in ("variant", "threshold", "weighting") if c != col]] ==
                pd.Series({c: BASE[c] for c in ("variant", "threshold", "weighting") if c != col})).all(axis=1)]
        return {"min": float(m["any"].min()), "max": float(m["any"].max()),
                "range": float(m["any"].max() - m["any"].min())}
    swings = {c: swing(c) for c in ("variant", "threshold", "weighting")}

    # by GICS sector and by financial / non-financial
    h["frac_any"] = h["industry"].map(lambda i: per_ind[i][any_i])
    h["flagged_mv"] = h["frac_any"] * h["mv"]
    by_sector = (h.groupby("sector")[["mv", "flagged_mv"]].sum().assign(
        weight=lambda d: d["mv"] / total, contribution=lambda d: d["flagged_mv"] / total,
        own_share=lambda d: d["flagged_mv"] / d["mv"]).sort_values("contribution", ascending=False))
    fin = h["industry"].isin(FINANCIAL_INDUSTRIES)
    fin_w = float(h.loc[fin, "mv"].sum() / total)
    nonfin_share = float(h.loc[~fin, "flagged_mv"].sum() / h.loc[~fin, "mv"].sum())
    fin_share = float(h.loc[fin, "flagged_mv"].sum() / h.loc[fin, "mv"].sum())

    top = h.sort_values("flagged_mv", ascending=False).head(10)
    h.to_csv(os.path.join(RES, "holdings_scored.csv"), index=False)

    res = {
        "fund": {"name": meta.get("Fund Name:"), "isin": meta.get("ISIN:"), "holdings_as_of": str(meta.get("Holdings As Of:"))},
        "n_holdings": int(len(h)), "n_industries": int(h["industry"].nunique()),
        "total_market_value_eur": total, "unassigned_market_value_eur": unassigned,
        "n_services": len(services), "n_processes": len(processes), "n_ratings": len(ratings),
        "n_draw": N_DRAW,
        "headline": {"share_any": base_any, "ci_conditional": ci(d_cond[:, any_i]),
                     "ci_with_mapping": ci(d_mix[:, any_i])},
        "services": svc,
        "sweep": sweep, "swings": swings,
        "sweep_range": [float(sw["any"].min()), float(sw["any"].max())],
        "sweep_min_rank_corr": float(sw["rank_corr_services"].min()),
        "by_sector": {k: {c: float(v[c]) for c in v.index} for k, v in by_sector.iterrows()},
        "financials": {"weight": fin_w, "own_share": fin_share, "nonfinancial_share": nonfin_share},
        "top_holdings": [{"name": r["name"], "industry": r["industry"], "weight": float(r["mv"] / total),
                          "frac_any": float(r["frac_any"])} for _, r in top.iterrows()],
        "ecb_comparator": ecb_comparator(),
        "rating_counts": pd.Series(list(ratings.values())).value_counts().to_dict(),
    }
    with open(os.path.join(RES, "nature_dependency.json"), "w") as f:
        json.dump(res, f, indent=1)
    return res


if __name__ == "__main__":
    r = build()
    hd = r["headline"]
    print(f"{r['n_holdings']} holdings, EUR {r['total_market_value_eur']/1e6:,.0f}mn, as of {r['fund']['holdings_as_of']}")
    print(f"share with H/VH dependency on >=1 service: {hd['share_any']:.1%} "
          f"cond {hd['ci_conditional']} mix {hd['ci_with_mapping']}")
    print("sweep range", r["sweep_range"], "swings", r["swings"])
    print("financials", r["financials"])
    for s in sorted(r["services"], key=lambda s: -s["share"])[:8]:
        print(f"{s['service'][:50]:50s} {s['share']:.1%} {s['ci_mix']}")
