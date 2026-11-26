"""Transition-relevant exposure of EU banks' lending to non-financial corporations, from the EBA transparency exercise.

ESTIMAND. The share of EU banks' loans and advances to non-financial corporations (gross carrying amount, FINREP F 06.01
by NACE section) that sits in climate-policy-relevant NACE sections, pooled by the country of the reporting bank, at the
June 2025 reference date of the latest exercise; and the gap in the non-performing ratio (non-performing gross carrying
amount over gross carrying amount) between those sections and the rest. If I knew them exactly I would know, for each
country's reporting banks, how much of the corporate book is in sectors whose profitability climate policy changes, and
whether those sectors already perform worse. Countries and distributions only; no bank is named or ranked.

INTERVALS. Banks are the sampling unit and the only thing resampled: within each country (a stratum) banks are drawn
with replacement, the country's pooled sums are recomputed, and every statistic (share, gap, every mapping variant, every
section) is read off the same draw. The mapping and the reference date are not random; they are swept.

    python3 src/exposure.py
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA, RES = os.path.join(ROOT, "data"), os.path.join(ROOT, "results")
SECTIONS = list("ABCDEFGHIJKLMNOPQRS")
SECTION_NAMES = {"A": "Agriculture, forestry, fishing", "B": "Mining and quarrying", "C": "Manufacturing",
                 "D": "Electricity, gas, steam, air conditioning", "E": "Water supply, waste", "F": "Construction",
                 "G": "Wholesale and retail trade", "H": "Transport and storage", "I": "Accommodation and food",
                 "J": "Information and communication", "K": "Financial and insurance", "L": "Real estate",
                 "M": "Professional, scientific, technical", "N": "Administrative and support",
                 "O": "Public administration", "P": "Education", "Q": "Health and social work",
                 "R": "Arts, entertainment, recreation", "S": "Other services"}
BASE = "base"
B = 4000
SEED = 19
THIN = 5            # fewer banks than this: interval reported but flagged unreliable
ALL = set(SECTIONS)
# Sections-level reading of Battiston et al. (2017) climate-policy-relevant sectors, as in module 05: agriculture,
# fossil fuel, utilities, housing (construction, real estate), transport; manufacturing (C) is taken whole because the
# exercise does not split it, which overstates the energy-intensive part. The other variants are the sweep.
VARIANTS = {
    BASE: (set("ABCDFHL"), ALL),
    "EU benchmark high-impact (A-H, L)": (set("ABCDEFGHL"), ALL),
    "B, C, D, H (no agriculture, no property)": (set("BCDH"), ALL),
    "B, D, H (fossil, power, transport)": (set("BDH"), ALL),
    "base without L (real estate)": (set("ABCDFH"), ALL),
    "base without C (manufacturing)": (set("ABDFHL"), ALL),
    "base without F and L (property)": (set("ABCDH"), ALL),
    "base without A (agriculture)": (set("BCDFHL"), ALL),
    "base, K out of the denominator": (set("ABCDFHL"), ALL - {"K"}),
}
SECTION_VARIANTS = {f"section {s}": ({s}, ALL) for s in SECTIONS}
SPECS = {**VARIANTS, **SECTION_VARIANTS}
NAMES = list(SPECS)


def load():
    return pd.read_csv(os.path.join(DATA, "nace_extract.csv"), dtype={"edition": str, "period": str})


def bank_matrix(df, edition, period, eu27_only=True):
    """Banks x sections arrays of gross and non-performing amounts for one reporting date."""
    s = df[(df.edition == edition) & (df.period == period)]
    if eu27_only:
        s = s[s.eu27 == 1]
    g = s.pivot_table(index="bank", columns="nace", values="gross", aggfunc="sum").reindex(columns=SECTIONS).fillna(0.0)
    n = s.pivot_table(index="bank", columns="nace", values="npe", aggfunc="sum").reindex(columns=SECTIONS).fillna(0.0)
    country = s.groupby("bank").country.first().reindex(g.index)
    return g, n, country


def components(g, n):
    """Per bank, for every spec: numerator gross, numerator NPE, denominator gross, denominator NPE."""
    cols = []
    for num, den in SPECS.values():
        ni, di = [SECTIONS.index(x) for x in sorted(num)], [SECTIONS.index(x) for x in sorted(den)]
        gv, nv = g.values, n.values
        cols += [gv[:, ni].sum(1), nv[:, ni].sum(1), gv[:, di].sum(1), nv[:, di].sum(1)]
    return np.column_stack(cols)


def stats(S, k):
    """Share, NPL ratio inside, NPL ratio outside and gap of spec k from summed components S (any leading shape)."""
    ng, nn, dg, dn = S[..., 4 * k], S[..., 4 * k + 1], S[..., 4 * k + 2], S[..., 4 * k + 3]
    with np.errstate(divide="ignore", invalid="ignore"):
        share, inside = ng / dg, nn / ng
        outside = (dn - nn) / (dg - ng)
    return {"share": share, "npl_in": inside, "npl_out": outside, "gap": inside - outside, "loans": dg}


def within_country_gap(Sc, k, drop=None):
    """Loan-weighted mean of country gaps: the gap with the country mix held out."""
    gaps = np.stack([stats(S, k)["gap"] for S in Sc.values()])
    w = np.stack([stats(S, k)["loans"] for S in Sc.values()])
    return (gaps * w).sum(0) / w.sum(0)


def estimate(C, country, rng, b=B):
    """Point estimates and stratified bootstrap draws. Strata are countries; a draw resamples banks inside each stratum
    once, and all specs and all statistics use that draw."""
    strata = {c: np.flatnonzero(country.values == c) for c in sorted(country.unique())}
    pt = {c: C[ix].sum(0) for c, ix in strata.items()}
    bs = {c: C[ix][rng.integers(0, len(ix), (b, len(ix)))].sum(1) for c, ix in strata.items()}
    pt_eu, bs_eu = sum(pt.values()), sum(bs.values())
    return {"strata": strata, "pt": pt, "bs": bs, "pt_eu": pt_eu, "bs_eu": bs_eu}


def ci(x):
    return [float(np.nanpercentile(x, 2.5)), float(np.nanpercentile(x, 97.5))]


def summarise(est, name, stat):
    k = NAMES.index(name)
    return float(stats(est["pt_eu"], k)[stat]), ci(stats(est["bs_eu"], k)[stat])


def eu_row(est, name):
    k = NAMES.index(name)
    out = {}
    for st in ("share", "npl_in", "npl_out", "gap"):
        v, c = summarise(est, name, st)
        out[st], out[st + "_ci"] = v, c
    wc_pt = float(within_country_gap(est["pt"], k))
    out["gap_within_country"], out["gap_within_country_ci"] = wc_pt, ci(within_country_gap(est["bs"], k))
    out["loans_eur_bn"] = float(stats(est["pt_eu"], k)["loans"] / 1000)
    return out


def spearman(a, b):
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


def main():
    os.makedirs(RES, exist_ok=True)
    df = load()
    rng = np.random.default_rng(SEED)
    out = {"bootstrap_draws": B, "seed": SEED, "min_banks_for_country_row": 3, "thin_below": THIN}

    # ---- headline: EU27, June 2025
    g, n, country = bank_matrix(df, "2025", "202506")
    C = components(g, n)
    est = estimate(C, country, rng)
    out["banks_eu27"] = int(len(g))
    out["countries"] = [c for c in est["strata"] if c != "XX"]
    out["head"] = eu_row(est, BASE)
    out["head"]["banks"] = int(len(g))
    kb0 = NAMES.index(BASE)
    tot_b = C[:, 4 * kb0 + 2]
    out["head"]["top5_banks_loan_share"] = float(np.sort(tot_b)[-5:].sum() / tot_b.sum())
    loo = [stats(est["pt_eu"] - C[i], kb0) for i in range(len(C))]
    out["head"]["leave_one_bank_out_max_share_move_pp"] = float(max(abs(x["share"] - out["head"]["share"]) for x in loo) * 100)
    out["head"]["leave_one_bank_out_max_gap_move_pp"] = float(max(abs(x["gap"] - out["head"]["gap"]) for x in loo) * 100)

    # ---- by country (strata with at least three banks; XX is the pooled group of smaller countries)
    rows = []
    kb = NAMES.index(BASE)
    for c, ix in est["strata"].items():
        st, bst = stats(est["pt"][c], kb), stats(est["bs"][c], kb)
        r = {"country": "other EU (pooled)" if c == "XX" else c, "banks": int(len(ix)),
             "nfc_loans_eur_bn": float(st["loans"] / 1000), "thin": int(len(ix) < THIN)}
        for s in ("share", "npl_in", "npl_out", "gap"):
            r[s] = float(st[s])
            r[s + "_lo"], r[s + "_hi"] = ci(bst[s])
        bs_share = (g.values[ix][:, [SECTIONS.index(x) for x in sorted(VARIANTS[BASE][0])]].sum(1)
                    / g.values[ix].sum(1))
        r["bank_share_q25"], r["bank_share_median"], r["bank_share_q75"] = [float(np.percentile(bs_share, q)) for q in (25, 50, 75)]
        rows.append(r)
    cty = pd.DataFrame(rows).sort_values("share", ascending=False)
    cty.to_csv(os.path.join(RES, "country.csv"), index=False)
    # bank-level shares for the deck's distribution panel: no identifier, countries with at least THIN banks only
    ix_cols = [SECTIONS.index(x) for x in sorted(VARIANTS[BASE][0])]
    bsh = pd.DataFrame({"country": country.values, "share": g.values[:, ix_cols].sum(1) / g.values.sum(1)})
    keep = bsh.country.map(bsh.country.value_counts()) >= THIN
    bsh[keep & (bsh.country != "XX")].sort_values(["country", "share"]).round(5).to_csv(
        os.path.join(RES, "bank_shares.csv"), index=False)
    reported = cty[cty.country != "other EU (pooled)"]
    out["country_summary"] = {
        "countries_reported": int(len(reported)),
        "highest": reported.iloc[0][["country", "share", "share_lo", "share_hi", "banks"]].to_dict(),
        "lowest": reported.iloc[-1][["country", "share", "share_lo", "share_hi", "banks"]].to_dict(),
        "n_ge5": int((reported.banks >= THIN).sum()),
        "gap_positive_countries": int((reported.gap > 0).sum()),
        "gap_interval_excludes_zero": int(((reported.gap_lo > 0) | (reported.gap_hi < 0)).sum()),
    }
    thick = reported[reported.banks >= THIN]
    # pairs of countries with at least five banks whose intervals do not overlap
    sep = tot = 0
    for i, a in thick.iterrows():
        for j, b2 in thick.iterrows():
            if a.country < b2.country:
                tot += 1
                sep += int(a.share_lo > b2.share_hi or b2.share_lo > a.share_hi)
    out["country_summary"]["pairs_ge5"], out["country_summary"]["pairs_ge5_separated"] = tot, sep

    # ---- sections: pooled EU27 share and NPL ratio with intervals
    rows = []
    for s in SECTIONS:
        r = {"section": s, "name": SECTION_NAMES[s], "in_base": int(s in VARIANTS[BASE][0])}
        for st in ("share", "npl_in"):
            v, c = summarise(est, f"section {s}", st)
            r[st], r[st + "_lo"], r[st + "_hi"] = v, c[0], c[1]
        rows.append(r)
    sec = pd.DataFrame(rows).rename(columns={"npl_in": "npl_ratio", "npl_in_lo": "npl_ratio_lo", "npl_in_hi": "npl_ratio_hi"})
    sec.to_csv(os.path.join(RES, "section.csv"), index=False)

    # ---- sweep 1: the mapping (paired draws, so differences have their own intervals)
    rows, base_cty = [], {}
    for name in VARIANTS:
        k = NAMES.index(name)
        r = {"variant": name, "sections": "".join(sorted(VARIANTS[name][0]))}
        r.update(eu_row(est, name))
        d_share = stats(est["bs_eu"], k)["share"] - stats(est["bs_eu"], kb)["share"]
        d_gap = stats(est["bs_eu"], k)["gap"] - stats(est["bs_eu"], kb)["gap"]
        r["share_minus_base"], r["share_minus_base_ci"] = r["share"] - out["head"]["share"], ci(d_share)
        r["gap_minus_base"], r["gap_minus_base_ci"] = r["gap"] - out["head"]["gap"], ci(d_gap)
        cs = [float(stats(est["pt"][c], k)["share"]) for c in est["strata"] if c != "XX" and len(est["strata"][c]) >= 3]
        base_cty.setdefault("base", [float(stats(est["pt"][c], kb)["share"]) for c in est["strata"] if c != "XX" and len(est["strata"][c]) >= 3])
        r["spearman_country_share_vs_base"] = spearman(cs, base_cty["base"])
        cg = [float(stats(est["pt"][c], k)["gap"]) for c in est["strata"] if c != "XX" and len(est["strata"][c]) >= 3]
        cg0 = [float(stats(est["pt"][c], kb)["gap"]) for c in est["strata"] if c != "XX" and len(est["strata"][c]) >= 3]
        r["spearman_country_gap_vs_base"] = spearman(cg, cg0)
        r["countries_gap_positive"] = int(sum(x > 0 for x in cg))
        rows.append(r)
    sw = pd.DataFrame(rows)
    sw.to_json(os.path.join(RES, "sweep_mapping.json"), orient="records", indent=1)
    sw_flat = sw.copy()
    for col in [c for c in sw.columns if c.endswith("_ci")]:
        sw_flat[col + "_lo"] = sw[col].map(lambda x: x[0])
        sw_flat[col + "_hi"] = sw[col].map(lambda x: x[1])
        sw_flat = sw_flat.drop(columns=col)
    sw_flat.to_csv(os.path.join(RES, "sweep_mapping.csv"), index=False)

    # ---- sweep 2: reference date, edition and sample
    rows = []
    for label, ed, per, eu in (("Sep 2024", "2025", "202409", True), ("Dec 2024", "2025", "202412", True),
                                ("Mar 2025", "2025", "202503", True), ("Jun 2025 (headline)", "2025", "202506", True),
                                ("Jun 2025, EU/EEA sample", "2025", "202506", False), ("Jun 2024 (2024 exercise)", "2024", "202406", True)):
        gg, nn_, cc = bank_matrix(df, ed, per, eu)
        e = estimate(components(gg, nn_), cc, np.random.default_rng(SEED))
        r = {"date": label, "banks": int(len(gg))}
        r.update(eu_row(e, BASE))
        rows.append(r)
    per = pd.DataFrame(rows)
    per.to_json(os.path.join(RES, "sweep_date.json"), orient="records", indent=1)

    # ---- year on year: matched banks, Jun 2024 to Jun 2025, one resample for both dates
    g1, n1, c1 = bank_matrix(df, "2025", "202506")
    g0, n0, _ = bank_matrix(df, "2024", "202406")
    common = g1.index.intersection(g0.index)
    C1, C0 = components(g1.loc[common], n1.loc[common]), components(g0.loc[common], n0.loc[common])
    cc = c1.loc[common]
    rng2 = np.random.default_rng(SEED + 1)
    draws, pt1, pt0 = [], C1.sum(0), C0.sum(0)
    ix = {c: np.flatnonzero(cc.values == c) for c in cc.unique()}
    d_share, d_gap = [], []
    pick = {c: rng2.integers(0, len(i), (B, len(i))) for c, i in ix.items()}
    S1 = sum(C1[i][pick[c]].sum(1) for c, i in ix.items())
    S0 = sum(C0[i][pick[c]].sum(1) for c, i in ix.items())
    s1, s0 = stats(S1, kb), stats(S0, kb)
    p1, p0 = stats(pt1, kb), stats(pt0, kb)
    out["yoy"] = {"banks_matched": int(len(common)),
                  "share_2024": float(p0["share"]), "share_2025": float(p1["share"]),
                  "share_change": float(p1["share"] - p0["share"]), "share_change_ci": ci(s1["share"] - s0["share"]),
                  "gap_2024": float(p0["gap"]), "gap_2025": float(p1["gap"]),
                  "gap_change": float(p1["gap"] - p0["gap"]), "gap_change_ci": ci(s1["gap"] - s0["gap"])}

    # ---- validation: against the EBA's own published aggregates
    rec = json.load(open(os.path.join(DATA, "reconciliation.json")))
    r25 = rec["2025_202506"]
    rar = rec["rar_2025"]
    out["validation_totals"] = {
        "nace_sections_vs_nace_total": r25["nace_sum_sections"] / r25["nace_total_nace0"] - 1,
        "nace_total_vs_npe_sheet_nfc": r25["nace_total_nace0"] / r25["npe_sheet_nfc_total"] - 1,
        "npl_volume_all_eur_bn": r25["loans_npl_all"] / 1000, "report_npl_eur_bn": rar["npl_bn"],
        "npl_ratio_incl_cash": r25["npl_ratio_with_cash_in_denominator"], "report_npl_ratio": rar["npl_ratio"],
        "report_page": rar["page"], "report_text": rar["text"]}
    pub = pd.read_csv(os.path.join(DATA, "eba_published.csv"))
    pub = pub[pub.groupby(["measure", "country"]).nace.transform("size") == 19]
    # my sample as the EBA's EU/EEA row: all banks of the exercise (the dashboard's EU/EEA includes NO, LI, IS)
    ga, na, ca = bank_matrix(df, "2025", "202506", eu27_only=False)
    ea = estimate(components(ga, na), ca, np.random.default_rng(SEED + 2))
    P = {m: pub[(pub.measure == m) & (pub.country == "EU/EEA")].set_index("nace").value_jun25.reindex(SECTIONS) for m in ("share", "npl_ratio")}
    rows = []
    for s in SECTIONS:
        r = {"section": s}
        for m, st in (("share", "share"), ("npl_ratio", "npl_in")):
            v, c = summarise(ea, f"section {s}", st)
            r[m], r[m + "_lo"], r[m + "_hi"], r[m + "_eba"] = v, c[0], c[1], float(P[m][s])
            r[m + "_inside"] = int(c[0] <= P[m][s] <= c[1])
        rows.append(r)
    vs = pd.DataFrame(rows)
    vs.to_csv(os.path.join(RES, "validation_section.csv"), index=False)
    num = sorted(VARIANTS[BASE][0])
    pub_share = float(P["share"][num].sum() / P["share"].sum())
    w = P["share"] * P["npl_ratio"]
    in_, out_ = num, [s for s in SECTIONS if s not in num]
    pub_in = float(w[in_].sum() / P["share"][in_].sum())
    pub_out = float(w[out_].sum() / P["share"][out_].sum())
    sh, shc = summarise(ea, BASE, "share")
    gp, gpc = summarise(ea, BASE, "gap")
    out["validation_published"] = {
        "sample": "all banks of the exercise, June 2025 (EU/EEA)", "banks": int(len(ga)),
        "mine_share": sh, "mine_share_ci": shc, "eba_share": pub_share,
        "mine_gap": gp, "mine_gap_ci": gpc, "eba_gap": pub_in - pub_out,
        "eba_npl_in": pub_in, "eba_npl_out": pub_out,
        "sections_share_inside_ci": int(vs.share_inside.sum()), "sections_npl_inside_ci": int(vs.npl_ratio_inside.sum()),
        "share_mae_pp": float((vs.share - vs.share_eba).abs().mean() * 100),
        "share_max_abs_pp": float((vs.share - vs.share_eba).abs().max() * 100),
        "npl_mae_pp": float((vs.npl_ratio - vs.npl_ratio_eba).abs().mean() * 100),
        "share_corr": float(vs.share.corr(vs.share_eba)), "npl_corr": float(vs.npl_ratio.corr(vs.npl_ratio_eba))}
    # country level: base-mapping share from the EBA's section shares against mine, countries with >=3 banks
    rows = []
    for c in out["countries"]:
        ps = pub[(pub.measure == "share") & (pub.country == c)].set_index("nace").value_jun25.reindex(SECTIONS)
        pn = pub[(pub.measure == "npl_ratio") & (pub.country == c)].set_index("nace").value_jun25.reindex(SECTIONS)
        if ps.isna().any() or pn.isna().any():
            continue
        r = cty[cty.country == c].iloc[0]
        e_share = float(ps[num].sum() / ps.sum())
        e_in = float((ps * pn)[in_].sum() / ps[in_].sum())
        e_out = float((ps * pn)[out_].sum() / ps[out_].sum())
        rows.append({"country": c, "banks": int(r.banks), "mine": r.share, "lo": r.share_lo, "hi": r.share_hi,
                     "eba": e_share, "inside": int(r.share_lo <= e_share <= r.share_hi),
                     "mine_gap": r.gap, "gap_lo": r.gap_lo, "gap_hi": r.gap_hi, "eba_gap": e_in - e_out,
                     "gap_inside": int(r.gap_lo <= e_in - e_out <= r.gap_hi)})
    vc = pd.DataFrame(rows)
    vc.to_csv(os.path.join(RES, "validation_country.csv"), index=False)
    out["validation_country"] = {"countries": int(len(vc)), "share_inside": int(vc.inside.sum()),
                                 "share_mae_pp": float((vc.mine - vc.eba).abs().mean() * 100),
                                 "share_max_abs_pp": float((vc.mine - vc.eba).abs().max() * 100),
                                 "share_corr": float(vc.mine.corr(vc.eba)),
                                 "gap_inside": int(vc.gap_inside.sum()),
                                 "gap_corr": float(vc.mine_gap.corr(vc.eba_gap))}
    json.dump(out, open(os.path.join(RES, "summary.json"), "w"), indent=1, default=float)
    print(json.dumps({k: out[k] for k in ("banks_eu27", "head", "country_summary", "yoy", "validation_published", "validation_country", "validation_totals")}, indent=1, default=float))


if __name__ == "__main__":
    main()
