"""Five pages. Every number is read from results/, none is typed here."""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.join(HERE, ".."))
INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})


def page(pdf, kicker, title, blocks, draw=None, draw_rect=None):
    fig = plt.figure(figsize=(8.27, 11.69)); fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, kicker, fontsize=8, color=ACC, va="top", fontfamily="monospace")
    fig.text(0.08, 0.932, title, fontsize=16.5, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.908, 0.908], color=RULE, lw=1))
    y = 0.878
    for head, body in blocks:
        if head:
            fig.text(0.08, y, head, fontsize=10, color=INK, weight="bold", va="top"); y -= 0.022
        for line in body:
            fig.text(0.08, y, line, fontsize=9.3, color=MID, va="top"); y -= 0.0185
        y -= 0.012
    if draw:
        draw(fig.add_axes(draw_rect or [0.30, 0.09, 0.62, 0.36]))
    r = fig.canvas.get_renderer()
    for t in fig.texts:
        if t.get_window_extent(r).x1 > 0.94 * fig.bbox.width:
            raise ValueError(f"line runs off the page: {t.get_text()[:60]}")
    pdf.savefig(fig); plt.close(fig)


def pc(x, d=1):
    return f"{100 * x:.{d}f}%"


def main():
    d = json.load(open("results/nature_dependency.json"))
    hd, fin, fund = d["headline"], d["financials"], d["fund"]
    sw = d["sweep"]
    svc = sorted((s for s in d["services"] if s["service"] != "at least one service"), key=lambda s: -s["share"])
    n_svc_pos = sum(1 for s in svc if s["share"] > 0)
    sec = sorted(d["by_sector"].items(), key=lambda kv: -kv[1]["contribution"])
    thr = d["swings"]["threshold"]; var = d["swings"]["variant"]; wt = d["swings"]["weighting"]
    ecb = d["ecb_comparator"]
    lo_c, hi_c = hd["ci_conditional"]; lo_m, hi_m = hd["ci_with_mapping"]
    by_thr = {t: [s["any"] for s in sw if s["threshold"] == t] for t in ("VH", "H+", "M+")}
    ecb_gap = 100 * (ecb["loans_share_pct"] / 100 - hd["share_any"])
    ecb_gap_m = 100 * (ecb["loans_share_pct"] / 100 - max(by_thr["M+"]))
    fin_move = 100 * (fin["nonfinancial_share"] - hd["share_any"])

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 12 / 1 of 5", "How much of a real fund depends on nature", [
            ("The question", [
                "What share of a fund's market value sits in companies whose activity has a High or",
                "Very High ENCORE dependency rating on at least one ecosystem service, and on each",
                f"of the {d['n_services']} services? The fund is the {fund['name']}",
                f"(ISIN {fund['isin']}), {d['n_holdings']} holdings, EUR {d['total_market_value_eur']/1e6:,.0f}mn, as of {fund['holdings_as_of']}."]),
            ("The answer", [
                f"{pc(hd['share_any'])} of market value. Interval {pc(lo_c)} to {pc(hi_c)} for the process mix inside each",
                f"company's industry; {pc(lo_m)} to {pc(hi_m)} when the industry-to-ENCORE crosswalk is also uncertain.",
                f"The cut-off decides more than either: Very High only gives {pc(min(by_thr['VH']))}, Medium and above",
                f"gives {pc(max(by_thr['M+']))}. The {pc(fin['weight'], 0)} of the fund in financials scores {pc(fin['own_share'], 0)}, because ENCORE rates",
                "a bank's own production process, not its borrowers."]),
            ("What it is not", [
                "A direct, equity-side, process-level reading of ENCORE. It is not the ECB's loan-book",
                f"figure ({ecb['loans_share_pct']}% of euro area bank loans, with supply-chain links), and it is not a",
                "company-level measurement: no company reports its own dependency here."])],
            draw=None)

        page(pdf, "MODULE 12 / 2 of 5", "Method: three joins and one draw", [
            ("Inputs, all fetched by src/fetch.py", [
                f"ENCORE knowledge base (JSON served to its public Explore tool): {d['n_ratings']:,} ratings of {d['n_services']}",
                f"ecosystem services over {d['n_processes']} production processes. State Street holdings file for the fund,",
                "with GICS industry. ECB blog page (comparator only). SHA-256 of each file in",
                "results/fetch_log.json."]),
            ("Join 1: holding to industry", [
                f"{d['n_holdings']} holdings in {d['n_industries']} GICS industries. EUR {d['unassigned_market_value_eur']/1e6:,.1f}mn of 'Unassigned' rows is dropped, not scored."]),
            ("Join 2: industry to ENCORE", [
                "Each GICS industry maps to one or more ENCORE sub-industries (my labels, in",
                "GICS_TO_ENCORE). A company is treated as one of that set's production processes,",
                "equal probability. Variants: narrow (first sub-industry), base, broad (whole section)."]),
            ("Rating to flag", [
                "A process is dependent on a service if ENCORE rates it High or Very High (base).",
                "'At least one service' is the OR over all services; per-service shares use one column."]),
            ("Interval", [
                f"{d['n_draw']:,} draws. Each holding draws one process from its industry's mix, independently:",
                "a company's activity mix is its own. The crosswalk variant is drawn once per industry",
                "and shared by every holding in it: a wrong crosswalk is wrong for all of them.",
                "The fund is not resampled; the estimand is this fund. Nothing here is forward-looking,",
                "so there is no backtest."])])

        def fig_services(ax):
            top = svc[:12][::-1]
            y = range(len(top))
            ax.barh(list(y), [100 * s["share"] for s in top], color=ACC, height=0.6)
            for i, s in enumerate(top):
                ax.plot([100 * s["ci_mix"][0], 100 * s["ci_mix"][1]], [i, i], color=INK, lw=1.4)
            ax.set_yticks(list(y)); ax.set_yticklabels([s["service"][:42] for s in top], fontsize=8)
            ax.set_xlabel("% of market value highly dependent (bar: point; line: interval with crosswalk draw)")
            ax.spines[["top", "right"]].set_visible(False)

        page(pdf, "MODULE 12 / 3 of 5", "Result: water, and a few sectors, carry it", [
            ("By service", [
                f"Highest: {svc[0]['service']} {pc(svc[0]['share'])} [{pc(svc[0]['ci_mix'][0])}, {pc(svc[0]['ci_mix'][1])}],",
                f"{svc[1]['service']} {pc(svc[1]['share'])}, {svc[2]['service']} {pc(svc[2]['share'])}.",
                f"{n_svc_pos} of {d['n_services']} services have any exposure at the High-and-above cut-off.",
                "Services are not additive: the same company is dependent on several."]),
            ("By sector, contribution to the headline", [
                *[f"{k}: {pc(v['contribution'])} of the headline (weight {pc(v['weight'], 0)}, own share {pc(v['own_share'], 0)})" for k, v in sec[:3]],
                f"{sec[-1][0]} contributes {pc(sec[-1][1]['contribution'])} from {pc(sec[-1][1]['weight'], 0)} of the fund."])],
            draw=fig_services, draw_rect=[0.36, 0.09, 0.56, 0.5])

        def fig_sweep(ax):
            cols = {"narrow": WARN, "base": ACC, "broad": BAD}
            for i, t in enumerate(("VH", "H+", "M+")):
                for s in sw:
                    if s["threshold"] == t:
                        ax.scatter(i + {"narrow": -0.15, "base": 0, "broad": 0.15}[s["variant"]],
                                   100 * s["any"], color=cols[s["variant"]], s=28,
                                   marker="o" if s["weighting"] == "process" else "x")
            ax.axhspan(100 * lo_m, 100 * hi_m, color=RULE, alpha=0.5, zorder=0)
            ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["Very High only", "High and above (base)", "Medium and above"])
            ax.set_ylabel("% of market value, at least one service")
            for v, c in cols.items():
                ax.scatter([], [], color=c, label=f"crosswalk: {v}")
            ax.scatter([], [], color=MID, marker="o", label="process weighting"); ax.scatter([], [], color=MID, marker="x", label="sub-industry weighting")
            ax.legend(fontsize=7.5, frameon=False, loc="upper left")
            ax.spines[["top", "right"]].set_visible(False)

        page(pdf, "MODULE 12 / 4 of 5", "Sensitivity and validation: the cut-off is the finding", [
            ("What moves the headline (18 combinations)", [
                f"Rating cut-off: {pc(thr['min'])} to {pc(thr['max'])}, a range of {100*thr['range']:.1f} points.",
                f"Crosswalk variant: {pc(var['min'])} to {pc(var['max'])}, {100*var['range']:.1f} points. Weighting rule: {100*wt['range']:.2f} points.",
                f"Across all 18, the headline runs {pc(d['sweep_range'][0])} to {pc(d['sweep_range'][1])}; the rank correlation of the 25 services",
                f"against the base ordering is never below {d['sweep_min_rank_corr']:.2f}. Ordering is steadier than level.",
                "Grey band: interval with crosswalk draw."]),
            ("Validation", [
                f"No independent measure of this fund's dependency exists. The ECB reports {ecb['loans_share_pct']}% of euro area bank",
                f"loans and {ecb['companies_share_pct']}% of companies highly dependent on one service (score above {ecb['score_threshold']}, with supply",
                f"chains, bank loans). My {pc(hd['share_any'])} is {ecb_gap:.1f} points below that; even at Medium and above",
                f"({pc(max(by_thr['M+']))}) it is {ecb_gap_m:.1f} points below. The estimands differ in portfolio, direct vs",
                "indirect links and score scale, so this is context, not a test of my number."])],
            draw=fig_sweep, draw_rect=[0.12, 0.09, 0.8, 0.42])

        page(pdf, "MODULE 12 / 5 of 5", "Limits, and what I would build next", [
            ("The assumption that would break it", [
                "That a listed company's activity is a draw from its GICS industry's ENCORE processes",
                f"and that ENCORE's direct rating is the dependency. Financials are {pc(fin['weight'], 0)} of the fund and score",
                f"{pc(fin['own_share'], 0)}; if they inherited the non-financial share ({pc(fin['nonfinancial_share'])}) the headline would",
                f"rise by {fin_move:.1f} points. The headline is a direct-dependency floor, not a risk estimate."]),
            ("What a sceptic attacks first", [
                f"The cut-off: {100*thr['range']:.0f} points between the strictest and loosest reading, from one rating scale",
                "that ENCORE assigns by expert judgement with no error attached. The interval does not",
                "include that error; the sweep is the only treatment of it.",
                "Also: market-cap weights for a Eurozone large-cap fund say nothing about SMEs or loans."]),
            ("Next", [
                "Company-level activity splits (revenue by NACE) in place of the uniform draw;",
                "supply-chain dependency through an input-output table; a loan-book view for a bank",
                "with a published sector breakdown."])])
    print("wrote deck.pdf")


if __name__ == "__main__":
    main()
