"""Six pages. Every number is read from results/, none is typed here. Claims that compare numbers are
asserted before they are written."""
import json
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})


def page(pdf, kicker, title, blocks, draw=None):
    fig = plt.figure(figsize=(8.27, 11.69)); fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, kicker, fontsize=8, color=ACC, va="top", fontfamily="monospace")
    fig.text(0.08, 0.932, title, fontsize=16.5, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.908, 0.908], color=RULE, lw=1))
    y = 0.878
    for head, body in blocks:
        if head:
            fig.text(0.08, y, head, fontsize=10, color=INK, weight="bold", va="top"); y -= 0.022
        paras = []
        for line in body:   # a line continues the previous one unless that ended a sentence or this one is indented
            if paras and not line.startswith(" ") and not paras[-1].endswith((".", ":")):
                paras[-1] += " " + line
            else:
                paras.append(line)
        for line in paras:
            ind = line[:len(line) - len(line.lstrip())]
            for part in textwrap.wrap(line, 90, initial_indent="", subsequent_indent=ind + "  ", break_long_words=False):
                fig.text(0.08, y, part, fontsize=9.3, color=MID, va="top"); y -= 0.0185
        y -= 0.012
    if draw:
        draw(fig)
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def pc(x, d=1):
    return f"{100 * x:.{d}f}%"


def iv(r, d=1):
    return f"[{100 * r[0]:.{d}f}%, {100 * r[1]:.{d}f}%]"


def main():
    R = lambda f: os.path.join(ROOT, "results", f)
    o = json.load(open(R("coherence.json")))
    bf = pd.read_csv(R("by_flow.csv")).set_index("flow")
    sw = pd.read_csv(R("sweep.csv"))
    pers = pd.read_csv(R("persistent.csv"))
    gaps = pd.read_csv(R("gaps_headline.csv"))
    rk = pd.read_csv(R("rank_corr.csv"), index_col=0)
    log = json.load(open(os.path.join(ROOT, "data", "fetch_log.json")))
    H, CY, CO, EM = o["headline"], o["ci_country_year"], o["ci_country"], o["ember"]
    base = sw[sw.group == "base"].iloc[0]
    assert abs(base.share_within - H["share_within"]) < 1e-4

    # comparative claims, checked before they are written
    assert bf.loc["IMP", "share_within"] > bf.loc["PS", "share_within"] > bf.loc["DL", "share_within"], "flow order in the text"
    assert bf.loc["EXP", "share_within"] > bf.loc["PS", "share_within"] and bf.loc["IMP", "lo_cy"] > bf.loc["PS", "hi_cy"], "IMP and EXP separate from PS"
    assert (CO["share_within"][1] - CO["share_within"][0]) > (CY["share_within"][1] - CY["share_within"][0]), "country interval wider"
    assert o["flagged"]["diff_ci"][1] < 0, "flagged observations agree less"
    rng_ = {g: d.share_within.max() - d.share_within.min() for g, d in sw.groupby("group") if g != "base"}
    top = max(rng_, key=rng_.get)
    assert top == "flows", top
    nonflow = {g: v for g, v in rng_.items() if g != "flows"}
    tol_ = sw[sw.group == "tolerance"]
    tol_sorted = tol_.assign(t=tol_.label.str.extract(r"([\d.]+)%")[0].astype(float)).sort_values("t")
    assert tol_sorted.share_within.is_monotonic_increasing
    dls = sw[sw.label == "DL only, against annual LOSS"].iloc[0]
    dlbase = sw[sw.label == "flows: DL only"].iloc[0]
    assert dls.lo > dlbase.hi, "the LOSS reading is better than the same-code reading"
    assert dls.share_within < 0.5, "the LOSS reading does not close most pairs"
    nonflow_n = sw[~sw.group.isin(["flows", "tolerance", "persistence rule", "base"])]
    n_flag = int(pers.cause.str.startswith("documented").sum())
    n_pat = int(pers.cause.str.startswith("pattern").sum())
    n_un = int((pers.cause == "unexplained").sum())
    assert n_flag + n_pat + n_un == len(pers) == H["n_persistent"]
    dlb = o["dl_break"]; dol = o["dl_over_loss"]
    ys = sorted(dol)
    assert all(dol[y]["annual_dl"] == 0 for y in ys[:5]) and dol[ys[-1]]["annual_dl"] > 0
    outside = gaps[gaps.agap > o["tol"]].fillna({"m_flags": "", "a_flag": ""})
    fl_out = float((outside.m_flags.str.contains("[eub]") | outside.a_flag.str.contains("[ebd]")).mean())
    assert fl_out < 0.5, "text says most divergence carries no flag"
    rc_min = o["rank_corr_min"]
    pers_flow = o["persistent_by_flow"]
    pall = pd.read_csv(os.path.join(ROOT, "data", "pairs.csv"), keep_default_na=False)
    x25 = pall[(pall.year == 2025) & (pall.flow != "NEP")]
    a25, n25 = (x25.a_flag.str.contains("p")).sum(), len(x25)
    assert a25 / n25 > 0.9
    bs = pd.read_csv(R("bootstrap.csv"))
    assert bs.n_persistent.mean() < H["n_persistent"], "text says the persistent-count interval sits low"
    var_cols = [c for c in rk.columns if c not in ("flows IMP EXP", "core + NEP")]
    assert rk.loc[var_cols, var_cols].values.min() > 0.8 and rc_min < 0.5, "text says the rank instability is across the flow set"
    assert pers_flow["DL"] > pers_flow["PS"] > pers_flow.get("IMP", 0)
    gl = gaps

    with PdfPages(os.path.join(ROOT, "deck.pdf")) as pdf:
        def d1(fig):
            ax = fig.add_axes([0.2, 0.1, 0.7, 0.3])
            names = ["IMP", "EXP", "PS", "DL"]
            yy = np.arange(len(names))[::-1]
            for i, f in zip(yy, names):
                r = bf.loc[f]
                ax.plot([r.lo_co, r.hi_co], [i, i], color=RULE, lw=7, solid_capstyle="butt")
                ax.plot([r.lo_cy, r.hi_cy], [i, i], color=ACC, lw=3, solid_capstyle="butt")
                ax.plot(r.share_within, i, "o", color=BAD, ms=6)
            ax.axvline(H["share_within"], color=MID, lw=0.8, ls="--")
            ax.set_yticks(yy); ax.set_yticklabels([f"{f}  (n={int(bf.loc[f, 'n'])})" for f in names])
            ax.set_xlim(0, 1); ax.set_xlabel("share of country-years with monthly sum within 1% of the annual figure")
            ax.set_title("by flow: 95% interval over country-years (dark), over whole countries (light); dashed = all four flows", fontsize=8); clean(ax)
        page(pdf, "MODULE 17 / 1 of 6", "Do monthly and annual electricity figures agree?", [
            ("The estimand", [
                "For each EU27 member state, flow and year: the relative gap (sum of twelve monthly figures minus the annual figure)",
                "divided by the annual figure, nrg_cb_em against nrg_cb_e. Reported as the distribution of gaps, the share within",
                "1%, and the country-flow pairs that diverge persistently."]),
            ("The answer", [
                f"{pc(H['share_within'])} of {int(H['n'])} country-flow-years are within 1%, interval {iv(CY['share_within'])} over country-years",
                f"and {iv(CO['share_within'])} over whole countries (2008 to 2025, imports, exports, distribution losses, pumped storage).",
                f"Median absolute gap {100 * H['median']:.3f}%; 75th percentile {pc(H['p75'])}; 90th percentile {pc(H['p90'], 0)}.",
                f"{H['n_persistent']} country-flow pairs diverge persistently (at least half of five or more years outside 1%), interval [{CY['n_persistent'][0]:.0f}, {CY['n_persistent'][1]:.0f}]."]),
            ("Where it comes from", [
                f"Imports {pc(bf.loc['IMP', 'share_within'])} and exports {pc(bf.loc['EXP', 'share_within'])} agree; pumped storage {pc(bf.loc['PS', 'share_within'])}; distribution losses {pc(bf.loc['DL', 'share_within'])}.",
                f"{pers_flow['DL']} of the {H['n_persistent']} persistent pairs are distribution losses, {pers_flow['PS']} pumped storage, {pers_flow.get('IMP', 0)} imports.",
                "The pooled share depends on the mix of flows, so read it flow by flow."]),
        ], d1)

        def d2(fig):
            ax = fig.add_axes([0.1, 0.08, 0.82, 0.32])
            cols = {"IMP": ACC, "EXP": OK, "PS": WARN, "DL": BAD}
            for f in ("IMP", "EXP", "PS", "DL"):
                a = np.sort(gl[gl.flow == f].agap.values)
                x = np.clip(a, 1e-7, 1e3)
                ax.step(x, np.arange(1, len(a) + 1) / len(a), color=cols[f], label=f, where="post")
            ax.axvline(o["tol"], color=MID, ls="--", lw=0.8)
            ax.set_xscale("log"); ax.set_xlabel("absolute relative gap (right edge: monthly sum zero, or annual zero)"); ax.set_ylabel("share of country-years at or below")
            ax.legend(frameon=False, fontsize=8, loc="lower right"); clean(ax)
        page(pdf, "MODULE 17 / 2 of 6", "Data and method", [
            ("Inputs, all fetched by src/fetch.py from public endpoints", [
                f"Eurostat dissemination API, JSON-stat, electricity (E7000), GWh, no country filter, accessed {log['accessed']}:",
                f"nrg_cb_em monthly ({log['datasets']['nrg_cb_em']['values']} values, to {log['datasets']['nrg_cb_em']['obs_period_latest']}), nrg_cb_e annual ({log['datasets']['nrg_cb_e']['values']} values, to {log['datasets']['nrg_cb_e']['obs_period_latest']}),",
                f"nrg_cb_pem monthly net generation ({log['datasets']['nrg_cb_pem']['values']} values), used only in the sweep. Ember yearly data: validation only.",
                "Only years with all twelve months and an annual figure enter. A pair with both figures zero has no relative gap and is dropped."]),
            ("Flows in both datasets", [
                "IMP, EXP, DL (distribution losses) by identical code; pumped storage: monthly TI_EHG_EPS against annual pure plus mixed plants.",
                f"Annual values for 2025 carry the provisional flag in the API ({int(a25)} of {int(n25)} country-flow-years in the pairs)."]),
            ("Intervals", [
                f"{o['draws']} draws, seed {o['seed']}. A drawn country-year brings all its flows with it, so what a country shares across flows is drawn once.",
                "The headline interval is over country-years (the roadmap's unit). Divergence persists inside a country, so a second",
                "interval resamples whole countries; it is wider, and it is the one I would quote. Nothing here is forward-looking: no backtest."]),
        ], d2)

        def d3(fig):
            ax = fig.add_axes([0.14, 0.08, 0.6, 0.5])
            m = gaps.groupby(["geo", "flow"]).agap.apply(lambda x: (x <= o["tol"]).mean()).unstack().reindex(columns=["IMP", "EXP", "PS", "DL"])
            m = m.loc[m.mean(axis=1).sort_values().index]
            im = ax.imshow(m.values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
            ax.set_xticks(range(4)); ax.set_xticklabels(m.columns); ax.set_yticks(range(len(m))); ax.set_yticklabels(m.index, fontsize=7)
            fig.colorbar(im, ax=ax, shrink=0.6, label="share of years within 1%")
            ax2 = fig.add_axes([0.84, 0.08, 0.1, 0.5]); ax2.axis("off")
        cs = pers.cause.value_counts()
        page(pdf, "MODULE 17 / 3 of 6", "Result: who diverges, and what the metadata says", [
            ("Persistent divergences", [
                f"{H['n_persistent']} pairs (listed in results/persistent.csv). Cause, as far as the data and the metadata I fetched say:",
                f"  documented by an Eurostat flag on the observation (estimated, low reliability, break, definition differs): {n_flag}",
                f"  pattern found, not documented anywhere I could read: {n_pat} ({int(cs.get('pattern, not documented: annual is zero, monthly is not', 0))} annual zero with monthly positive,",
                f"    {int(cs.get('pattern, not documented: monthly is zero, annual is not', 0))} monthly zero with annual positive, {int(cs.get('pattern, not documented: monthly matches annual total losses', 0))} monthly close to annual total losses)",
                f"  unexplained: {n_un}",
                f"Flagged observations are within 1% in {pc(o['flagged']['share_within'], 0)} of {o['flagged']['n']} cases against {pc(o['flagged']['share_within_unflagged'], 0)} unflagged;",
                f"difference {100 * o['flagged']['diff']:.1f} points [{100 * o['flagged']['diff_ci'][0]:.1f}, {100 * o['flagged']['diff_ci'][1]:.1f}]. {pc(1 - fl_out, 0)} of observations outside 1% carry no flag."]),
        ], d3)

        def d4(fig):
            ax = fig.add_axes([0.1, 0.08, 0.82, 0.3])
            yrs = [int(y) for y in ys]
            ax.plot(yrs, [dol[str(y)]["monthly_dl"] for y in yrs], "o-", color=ACC, label="monthly DL sum / annual total losses (LOSS)")
            ax.plot(yrs, [dol[str(y)]["annual_dl"] for y in yrs], "o-", color=BAD, label="annual DL / annual total losses (LOSS)")
            ax.set_ylim(-0.05, 1.15); ax.set_ylabel("median across EU27 countries"); ax.legend(frameon=False, fontsize=8, loc="center left"); clean(ax)
            ax.set_xlabel("year (annual LOSS is not published for 2025)")
        page(pdf, "MODULE 17 / 4 of 6", "Distribution losses mean different things", [
            ("What the numbers show", [
                f"Monthly DL is close to annual total losses (LOSS) every year: median ratio {min(dol[y]['monthly_dl'] for y in ys):.2f} to {max(dol[y]['monthly_dl'] for y in ys):.2f}.",
                f"Annual DL is not: median {dol[ys[0]]['annual_dl']:.2f} of LOSS in {ys[0]} to {ys[4]} (at least half of countries report zero), {min(dol[y]['annual_dl'] for y in ys[5:]):.2f} to {max(dol[y]['annual_dl'] for y in ys[5:]):.2f} in {ys[5]} to {ys[7]}.",
                f"From 2024 to 2025 annual DL rises by a median {100 * (dlb['median_annual_ratio'] - 1):.0f}% (monthly: {100 * (dlb['median_monthly_ratio'] - 1):.1f}%); {dlb['annual_ratio_gt_1_2']} of {dlb['n']} countries rise by more than 20%.",
                "No break flag marks this (annual DL carries only provisional and estimated flags). Reading DL against LOSS lifts the share within 1% on DL from",
                f"{pc(dlbase.share_within)} {iv([dlbase.lo, dlbase.hi])} to {pc(dls.share_within)} {iv([dls.lo, dls.hi])}: better, still under half.",
                "I infer, and cannot confirm from metadata, that monthly DL carries total grid losses while annual DL has meant",
                "distribution losses only, then total losses in the 2025 release."]),
        ], d4)

        def d5(fig):
            ax = fig.add_axes([0.52, 0.05, 0.4, 0.45])
            s = sw[sw.group != "persistence rule"].iloc[::-1]
            yy = np.arange(len(s))
            ax.errorbar(s.share_within, yy, xerr=[s.share_within - s.lo, s.hi - s.share_within], fmt="o", color=ACC, ecolor=RULE, capsize=2, ms=3.5)
            ax.axvline(H["share_within"], color=BAD, lw=0.8)
            ax.set_yticks(yy); ax.set_yticklabels([l.replace("headline: ", "")[:46] for l in s.label], fontsize=6)
            ax.set_xlabel("share within tolerance (country-year 95%)"); clean(ax)
        pr = sw[sw.group == "persistence rule"]
        page(pdf, "MODULE 17 / 5 of 6", "Validation and sensitivity", [
            ("Validation against a second publisher", [
                f"Ember's yearly net imports against Eurostat IMP minus EXP, {EM['n']} country-years 2019 to 2025: within 1% in {pc(EM['within_1pct_annual'])} against the annual",
                f"figure and {pc(EM['within_1pct_monthly'])} against the monthly sum; difference {100 * EM['within_1pct_diff']:.1f} points [{100 * EM['within_1pct_diff_ci'][0]:.1f}, {100 * EM['within_1pct_diff_ci'][1]:.1f}].",
                f"At the median both are within {EM['median_abs_diff_annual']:.1f} and {EM['median_abs_diff_monthly']:.1f} GWh. Ember sits within a few GWh of Eurostat, so it is probably built on it and not independent, and net imports",
                "cancel part of the import and export gaps: it cannot adjudicate distribution losses or pumped storage."]),
            ("Sensitivity: what moves the share", [
                f"The flow set moves it most: {pc(sw[sw.group == 'flows'].share_within.min())} (DL only) to {pc(sw[sw.group == 'flows'].share_within.max())} (EXP only).",
                f"Tolerance {tol_sorted.label.iloc[0].split()[-1]} to {tol_sorted.label.iloc[-1].split()[-1]}: {pc(tol_sorted.share_within.iloc[0])} to {pc(tol_sorted.share_within.iloc[-1])}. Window, size floor, flags, population: {pc(nonflow_n.share_within.min())} to {pc(nonflow_n.share_within.max())}.",
                f"Counting both-zero pairs as coherent: {pc(sw[sw.group == 'zero pairs'].share_within.iloc[0])}. Persistent pairs, by rule: {pr.n_persistent.min()} to {pr.n_persistent.max()}.",
                f"Ranking of countries across variants: rank correlation down to {rc_min:.2f}; it is not stable, mainly across the flow set."]),
        ], d5)
        page(pdf, "MODULE 17 / 6 of 6", "Limits and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "That the annual figure is the benchmark. Monthly and annual data come from separate country questionnaires (Eurostat metadata), so a gap says the",
                "two submissions disagree, not which one is right. For DL the monthly series is the stable one: the annual series",
                "changes level in 2022 and again in 2025."]),
            ("What a reviewer would attack first", [
                f"The pooled {pc(H['share_within'])} mixes flows of very different quality; the by-flow shares are the result.",
                "The flow mapping is mine: pumped storage is a sum of two annual lines, and DL against DL is the pairing by identical code,",
                "not one the metadata confirms. Causes marked 'not documented' are patterns, not explanations.",
                f"Years inside a country are not independent: the whole-country interval is {100 * (CO['share_within'][1] - CO['share_within'][0]):.1f} points wide against",
                f"{100 * (CY['share_within'][1] - CY['share_within'][0]):.1f} over country-years. The persistent count's interval sits low (its point value is near the top): a draw can drop a pair below five years."]),
            ("Not covered", [
                "Revisions over time (one vintage, accessed once), the partner-country detail behind imports and exports,",
                "and a true independent check of losses or pumped storage: none in the sources I could fetch without a token."]),
            ("Next", ["Repeat on gas (nrg_cb_gasm against nrg_cb_gas); track the vintage of each release to measure revisions."]),
        ])


if __name__ == "__main__":
    main()
