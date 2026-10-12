"""Six pages. Every number is read from results/, none is typed here."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})
mt = lambda v: f"{v / 1e6:.2f} Mt"


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
            t = fig.text(0.08, y, line, fontsize=9.3, color=MID, va="top"); y -= 0.0185
            fig.canvas.draw()
            assert t.get_window_extent().x1 <= 0.93 * fig.bbox.width, f"line overflows page: {line}"
        y -= 0.012
    assert not draw or y > 0.45, f"text runs into the figure on: {title}"
    if draw:
        draw(fig.add_axes(draw_rect or [0.10, 0.09, 0.82, 0.34]))
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def main():
    d = json.load(open("results/financed.json"))
    log = json.load(open("results/fetch_log.json"))
    h, n0, cal, le = d["headline"], d["no_reported"], d["calibration"], d["line_error"]
    sd = {r["score"]: r for r in h["score_distribution"]}
    sw, sws = d["sweeps"], d["sweep_swing"]
    ss = d["size_slope"]["within_sector_slope_log_intensity_on_log_revenue"]
    mc = d["match_coverage"]
    book = pd.read_csv("results/headline_book.csv")
    top5 = book.sort_values("financed_t", ascending=False).head(5)
    ranked = sorted(sws.items(), key=lambda kv: -kv[1]["swing"])

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 09 / 1 of 6", "A financed-emissions number is its score distribution", [
            ("The estimand", [
                "Scope 1 financed emissions, in tCO2e, of a loan book to US corporates under the PCAF",
                "business-loan attribution (outstanding amount over equity plus debt), with the PCAF",
                "data-quality score on every line. The borrowers, their emissions and their balance",
                "sheets are real. The bank is simulated: which borrowers it lends to, and how much."]),
            ("The answer", [
                f"{h['n_loans']} loans, USD {h['outstanding_usd_m']:,.0f} mn outstanding, {mt(h['financed_t'])} financed",
                f"[{mt(h['lo'])}, {mt(h['hi'])}], {h['intensity_t_per_usd_m']:.0f} tCO2e per USD mn lent. Weighted",
                f"data-quality score {h['wdqs']:.2f}: {sd[2]['share_financed']:.0%} of the financed emissions sit on reported lines.",
                "",
                f"The same book with no reported data (score {n0['wdqs']:.2f}): {mt(n0['financed_t'])}, and the realised-error",
                f"interval is [{mt(n0['empirical_lo'])}, {mt(n0['empirical_hi'])}], {n0['empirical_hi'] / n0['empirical_lo']:.1f} times wide end to end.",
                f"Reported emissions for this book total {mt(h['truth_t'])}. Both estimates cover it."]),
            ("Why the score distribution is the result", [
                "The headline alone cannot say which of the two books it came from. The first estimate",
                f"is within {abs(h['financed_t'] / h['truth_t'] - 1):.1%} of the reported figure; the second is {n0['financed_t'] / n0['truth_t'] - 1:+.0%} off.",
                "Same borrowers, same attribution, same estimand. The score tells the reader which",
                "number to trust, so it belongs on the same line as the total."])])

        page(pdf, "MODULE 09 / 2 of 6", "Method and data", [
            ("Data, all fetched by code (accessed " + log["accessed"] + ")", [
                "Emissions: EPA GHGRP facility table and emissions facts, data.epa.gov/efservice, direct",
                f"emitters only, with the parent-company ownership shares. {log['years']['2023']['facilities']:,} facilities in 2023.",
                "Financials and sector: SEC EDGAR XBRL company facts and submissions (revenue, assets,",
                "equity, debt, SIC code). Join: exact normalised name against SEC's ticker list.",
                f"{log['matched_parents']} parents matched; {d['population']['usable']} usable in 2023 after dropping missing or non-positive fields.",
                f"Matched parents hold {mc['share']:.0%} of all reported US direct emissions in 2023."]),
            ("Attribution and score", [
                "Financed emissions of a line = outstanding / (equity + debt) x borrower emissions.",
                "Score 2: reported emissions (GHGRP, unverified by a third party). Score 4: sector",
                "emission factor x revenue. Score 5: sector factor x assets. No score 1 or 3 exists in",
                "public data. The factor is the sector's total emissions over its total revenue or",
                f"assets, from borrowers that are not in the book. Sector: SIC 2-digit, pooled if fewer than {d['config']['min_peers']} peers.",
                "Rule: the largest 40% of the book by revenue report, the next 40% use revenue, the",
                "rest use assets. Loans are 1-5% of the borrower's debt, drawn at random."]),
            ("Uncertainty", [
                "Each sector's peer group is resampled once per replicate and sets the factor for every",
                "line in that sector. Each line then draws its own departure from the sector average.",
                "Reported lines carry none. The book is the population being estimated and is not",
                "resampled. Because borrowers are real, the estimate is also tested: 300 random books,",
                "factor fitted on the borrowers outside the book, compared to the reported total."])])

        def dist_chart(ax):
            sc = [2, 4, 5]
            x = np.arange(3); w = .27
            ax.bar(x - w, [sd[s]["lines"] / h["n_loans"] for s in sc], w, color=RULE, label="lines")
            ax.bar(x, [sd[s]["share_outstanding"] for s in sc], w, color=ACC, label="outstanding")
            ax.bar(x + w, [sd[s]["share_financed"] for s in sc], w, color=WARN, label="financed emissions")
            ax.set_xticks(x); ax.set_xticklabels([f"score {s}" for s in sc]); ax.set_ylim(0, 1)
            ax.set_ylabel("share of book"); ax.legend(frameon=False, fontsize=8)
            ax.set_title("score distribution, headline book", loc="left"); clean(ax)

        page(pdf, "MODULE 09 / 3 of 6", "Result: score distribution beside the total", [
            ("The book", [
                f"Score 2 lines are {sd[2]['lines']} of {h['n_loans']} and {sd[2]['share_outstanding']:.0%} of the money, because large firms report.",
                f"Score 4 and 5 lines are {sd[4]['lines'] + sd[5]['lines']} of {h['n_loans']} and {sd[4]['share_financed'] + sd[5]['share_financed']:.0%} of the financed emissions.",
                f"The five largest lines hold {h['top5_share_of_financed']:.0%} of the total; {int((top5.sic.astype(str).str[:2] == '49').sum())} of them are electric and gas",
                f"utilities (SIC 49) and {int((top5.score == 2).sum())} are reported lines, so they decide the number and carry no estimate error."]),
            ("Where the interval comes from", [
                f"Randomising only score 4 lines gives a width of {mt(d['width_by_score']['score 4']['width'])}, only score 5",
                f"{mt(d['width_by_score']['score 5']['width'])}, both {mt(d['width_by_score']['both']['width'])}.",
                f"Score 5 lines are {sd[5]['lines'] / h['n_loans']:.0%} of the lines and {sd[5]['share_outstanding']:.1%} of the money; their width",
                f"is {d['width_by_score']['score 5']['width'] / d['width_by_score']['score 4']['width']:.2f} times that of the score 4 tier, which holds {sd[4]['share_outstanding']:.0%} of the money."])], dist_chart)

        def val_chart(ax):
            ed = np.array(d["hist_edges_log10"]); mid = (ed[:-1] + ed[1:]) / 2
            for s, c in (("4", ACC), ("5", WARN)):
                hh = np.array(d["line_error_hist"][s]); ax.plot(mid, hh / hh.sum(), color=c, lw=2, label=f"score {s}")
            ax.axvline(0, color=MID, lw=1); ax.set_xlabel("log10 (estimate / reported), per line")
            ax.set_ylabel("share of lines"); ax.legend(frameon=False)
            ax.set_title(f"{le['4']['n'] + le['5']['n']:,} line estimates against reported emissions", loc="left"); clean(ax)

        page(pdf, "MODULE 09 / 4 of 6", "Validation: estimates against what was reported", [
            ("Line level", [
                f"Score 4: median estimate is {le['4']['median_ratio']:.2f} times the reported figure, {le['4']['share_within_factor_2']:.0%} of lines",
                f"within a factor of 2, {le['4']['share_within_factor_10']:.0%} within a factor of 10, 90% range {le['4']['q05_ratio']:.2f} to {le['4']['q95_ratio']:.0f}.",
                f"Score 5: median {le['5']['median_ratio']:.2f}, {le['5']['share_within_factor_2']:.0%} within 2, {le['5']['share_within_factor_10']:.0%} within 10, 90% range {le['5']['q05_ratio']:.2f} to {le['5']['q95_ratio']:.0f}."]),
            ("Book level, 300 random books", [
                f"Headline mix: the interval covers the reported total in {cal['coverage']:.0%} of books (nominal 95%).",
                f"Estimate over reported: median {cal['median_est_over_truth']:.2f}, 90% range {cal['q05_est_over_truth']:.2f} to {cal['q95_est_over_truth']:.2f}.",
                f"No reported data: coverage {n0['calibration']['coverage']:.0%}. The truth fell below the interval in {n0['calibration']['truth_below_interval']} books.",
                f"Cause: within a sector, intensity falls with size (slope {ss:.2f} on log revenue), the sector",
                "average ignores it, and the largest lines drive the sum. The peer resample cannot see a",
                "bias common to all peers, so for this case the interval is taken from the realised error:",
                f"[{mt(n0['empirical_lo'])}, {mt(n0['empirical_hi'])}]."]),
            ("What this does not validate", [
                "Reported emissions are the reference, not a second measurement. No independent",
                "public source measures the financed emissions of a simulated book."])], val_chart)

        def sweep_chart(ax):
            labs, lo, hi = [], [], []
            for k, v in ranked:
                labs.append(k.replace("_", " ")); lo.append(v["min_ratio"]); hi.append(v["max_ratio"])
            y = np.arange(len(labs))[::-1]
            ax.hlines(y, lo, hi, color=ACC, lw=7, alpha=.35)
            ax.plot(lo, y, "|", color=ACC, ms=11); ax.plot(hi, y, "|", color=ACC, ms=11)
            ax.axvline(1, color=MID, lw=1); ax.set_yticks(y); ax.set_yticklabels(labs)
            ax.set_xlabel("median estimate / reported total over 100 books, range across the choice")
            ax.set_title("what moves the aggregate", loc="left"); clean(ax)

        top, second = ranked[0], ranked[1]
        assert top[0] == "reporting_share", top[0]
        page(pdf, "MODULE 09 / 5 of 6", "Sensitivity: the share of reported lines decides", [
            ("Aggregate", [
                f"Largest swing in the median estimate over reported: {top[0].replace('_', ' ')}, {top[1]['swing']:.2f}",
                f"({top[1]['min_ratio']:.2f} to {top[1]['max_ratio']:.2f}). Next: {second[0].replace('_', ' ')}, {second[1]['swing']:.2f}.",
                f"Sector granularity moves it by {sws['sector_digits']['swing']:.3f}, the reference year by {sws['year']['swing']:.3f},",
                f"the loan size by {sws['loan_share']['swing']:.3f}. Book size {sws['book_size']['swing']:.3f}, minimum peers {sws['min_peers']['swing']:.3f}."]),
            ("Line level", [
                f"Share of estimated lines within a factor of 2 of the reported figure stays between",
                f"{min(v['line_within_2x_min'] for v in sws.values()):.0%} and {max(v['line_within_2x_max'] for v in sws.values()):.0%} across every choice swept. Finer SIC levels"
                f" ({sw['sector_digits'][1]['line_within_factor_2']:.0%} at 3 digits)",
                f"do not repair it; the median intensity factor lowers the aggregate to {sw['factor'][1]['median_est_over_truth']:.2f} of reported."])],
             sweep_chart)

        page(pdf, "MODULE 09 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "The book is simulated and the numerator is US direct emissions only. A multinational's",
                "balance sheet is global while its GHGRP emissions are the US facilities, so reported",
                "Scope 1 here is a floor for such borrowers and the attribution factor is not matched",
                "to the numerator. Scope 2 and 3 are absent. The size of the validated error is a",
                "property of this borrower set; a book with a different size mix will not reproduce it.",
                f"That the reporters are the large firms is an assumption of the score rule, and the",
                f"reported share is the choice that moves the result most ({top[1]['swing']:.2f})."]),
            ("What a sceptic attacks first", [
                f"Loan amounts are random, so the {mt(h['financed_t'])} describes no real bank. Matched parents",
                f"cover {mc['share']:.0%} of reported emissions; the rest are private or foreign. Books overlap",
                "across the 300 draws, so the coverage rates are not independent trials."]),
            ("Nothing here is forward-looking", [
                "The estimate is a snapshot of one reporting year; the held-out test above is across",
                "borrowers, not across time. The year sweep (2021-2023) is a robustness check."]),
            ("Next", [
                "Fit intensity on log revenue within sector, which the size slope says is missing, and",
                "re-run the same calibration. Add Scope 2 from the same reports. Replace the simulated",
                "bank with a public disclosure of sector exposures when one exists at line level."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
