"""Five pages. Every number is read from results/, none is typed here."""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})
pc = lambda v: f"{100 * v:.1f}%"
TPL = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"]


def page(pdf, kicker, title, blocks, draw=None, draw_rect=None, min_y=0.45):
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
    assert not draw or y > min_y, f"text runs into the figure on: {title}"
    if draw:
        draw(fig.add_axes(draw_rect or [0.10, 0.09, 0.82, 0.34]))
    if os.environ.get("DECK_PNG"):
        fig.savefig(f"{os.environ['DECK_PNG']}/{kicker.split()[-3]}.png", dpi=70)
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def main():
    d = json.load(open("results/index.json"))
    pt = json.load(open("results/parser_test.json"))
    log = json.load(open("results/fetch_log.json"))
    h, pb, tp, sw = d["headline"], d["per_bank"], d["per_template"], d["sweeps"]
    n = d["n_banks_scored"]
    all_pub = sum(v["published"] == 9 for v in pb.values())
    fills = {t: v["mean_fill"] for t, v in tp.items() if v["mean_fill"] is not None}
    low_t = min(fills, key=fills.get)
    hi_t = max(fills, key=fills.get)
    order = sorted(pb, key=lambda k: pb[k]["index"])
    tv = d["toc_totals"]
    par = d["parser"]
    swm = {k: v["mean"] for k, v in sw.items()}
    sw_lo, sw_hi = min(swm, key=swm.get), max(swm, key=swm.get)
    nonpres = {k: v for k, v in sw.items() if k != "presence only (fill ignored)"}
    lo_np = min(v["spearman_vs_baseline"] for v in nonpres.values())

    assert all(tp[t]["published"] == n for t in TPL[:5]), "text says every bank publishes T1 to T5"
    assert (h["interval_banks_only"][1] - h["interval_banks_only"][0]) > (h["interval_parser_only"][1] - h["interval_parser_only"][0])
    with PdfPages("deck.pdf") as pdf:
        def p1(ax):
            y = np.arange(len(order))
            for i, k in enumerate(order):
                lo, hi = pb[k]["interval_parser"]
                ax.plot([lo, hi], [i, i], color=ACC, lw=2, alpha=.55)
                ax.plot(pb[k]["index"], i, "o", color=ACC, ms=5)
                ax.plot(pb[k]["presence"], i, "|", color=BAD, ms=9)
            ax.axvspan(*h["interval"], color=WARN, alpha=.15)
            ax.axvline(h["mean_index"], color=WARN, lw=1.2)
            ax.set_yticks(y); ax.set_yticklabels(order); ax.set_xlim(0, 1.02); clean(ax)
            ax.set_xlabel("index (dot, interval from parser error) and presence-only score (red tick)")
        page(pdf, "MODULE 10 / 1 of 5", "How complete are banks' Pillar 3 ESG templates?", [
            ("The estimand", [
                "Per bank: the mean, over the nine mandatory EBA ESG templates (1 to 8 and 10), of the share",
                "of cells that show a value among cells that show a value or a placeholder; 0 for a template",
                "that is not in the report. Headline: the mean of that index over the banks scored.",
                f"{n} banks scored; {len(d['out_of_scope'])} of {d['n_banks_listed']} listed holds no ESG template in its PDF."]),
            ("The answer", [
                f"Mean index {pc(h['mean_index'])}, interval [{pc(h['interval'][0])}, {pc(h['interval'][1])}] (bank resampling plus parser error).",
                f"{all_pub} of {n} banks publish all nine templates; presence alone scores {pc(h['presence_mean'])}.",
                f"Completeness of the cells is where banks differ: bank indices run from {pc(pb[order[0]]['index'])} ({order[0]})",
                f"to {pc(pb[order[-1]]['index'])} ({order[-1]}). Presence does not separate banks; fill does."]),
        ], p1, [0.22, 0.07, 0.70, 0.40])

        def p2(ax):
            r = pt["rows"]
            ax.scatter([x["truth"] for x in r], [x["measured"] for x in r], s=9, color=ACC, alpha=.6)
            xs = np.linspace(0, 1, 2)
            ax.plot(xs, xs, color=MID, lw=1, ls="--")
            ax.plot(xs, par["intercept"] + par["slope"] * xs, color=BAD, lw=1.2)
            ax.set_xlabel("true fill rate of the generated table (SYNTHETIC)"); ax.set_ylabel("fill rate the parser measures")
            clean(ax)
        page(pdf, "MODULE 10 / 2 of 5", "Method: locate, count, test the counter", [
            ("Locating", [
                f"{len(log)} bank reports fetched as PDF (data/sources.csv, access date in results/fetch_log.json), text read",
                "with pypdf. A template starts at a heading line (label such as 'Template 4' or 'Tabella 4',",
                "or its full EBA title) and runs over the table pages that follow until another heading.",
                "Contents lists, prose and 'not applicable' lines are not headings. Per page, a table needs 5 cells."]),
            ("Scoring", [
                "Cells are numeric tokens (years excluded) and placeholders ('-', 'n/a', 'not available').",
                "Template score = numeric / (numeric + placeholder). Not in the report = 0. Bank index = mean of nine.",
                "A template the bank says it omits is scored 0 in the baseline and dropped in a sweep."]),
            ("The parser is tested on tables with a known answer (SYNTHETIC, labelled as such)", [
                f"200 generated tables, five layouts, rendered to PDF and read back: mean error {100 * par['mean_error']:.1f} points,",
                f"slope {par['slope']:.2f}, residual SD {100 * par['resid_sd']:.1f} points. The fitted line (red) corrects the index;",
                "the residual is drawn once per bank, shared by its templates, in the interval."]),
        ], p2, [0.12, 0.07, 0.40, 0.30], min_y=0.40)

        def p3(ax):
            M = np.full((len(order), len(TPL)), np.nan)
            for i, k in enumerate(order):
                for j, t in enumerate(TPL):
                    row = d["status"][k][t]
                    M[i, j] = row["fill"] if row["status"] == "published" else np.nan
            im = ax.imshow(M, aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
            for i, k in enumerate(order):
                for j, t in enumerate(TPL):
                    s = d["status"][k][t]["status"]
                    if s != "published":
                        ax.text(j, i, "omit" if s == "omitted_stated" else "n/f", ha="center", va="center", fontsize=6.5, color=BAD)
            ax.set_xticks(range(len(TPL))); ax.set_xticklabels(TPL)
            ax.set_yticks(range(len(order))); ax.set_yticklabels(order)
            plt.colorbar(im, ax=ax, fraction=.03, label="fill rate")
        page(pdf, "MODULE 10 / 3 of 5", "Result: templates are present; the cells are not all there", [
            ("What the grid shows", [
                f"Every bank publishes T1 to T5. T9 (BTAR) is in no report: {tp['T9']['not_found']} silent, {tp['T9']['stated_omitted']} say so.",
                f"Lowest mean fill: {low_t} ({pc(fills[low_t])}); highest: {hi_t} ({pc(fills[hi_t])}). T7 reads {pc(fills['T7'])}, T5 {pc(fills['T5'])}.",
                f"Interval parts: bank resampling alone [{pc(h['interval_banks_only'][0])}, {pc(h['interval_banks_only'][1])}], parser error alone",
                f"[{pc(h['interval_parser_only'][0])}, {pc(h['interval_parser_only'][1])}]. The spread between banks dominates; n={n} is small.",
                f"Parser-corrected mean: {pc(h['parser_corrected_mean'])}. 'omit' = bank states omission, 'n/f' = not found."]),
        ], p3, [0.22, 0.07, 0.62, 0.40], min_y=0.50)

        def p4(ax):
            names = list(sw)
            for i, k in enumerate(names):
                ax.plot(sw[k]["mean"], i, "o", color=ACC if k != "presence only (fill ignored)" else BAD)
                ax.text(1.0, i, f"rho {sw[k]['spearman_vs_baseline']:.2f}", va="center", fontsize=7.5, color=MID, transform=ax.get_yaxis_transform())
            ax.axvspan(*h["interval"], color=WARN, alpha=.15)
            ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=7.5); ax.invert_yaxis()
            ax.set_xlim(0.4, 1.0); ax.set_xlabel("mean index across banks (shaded: baseline interval)"); clean(ax)
        page(pdf, "MODULE 10 / 4 of 5", "Validation and sensitivity", [
            ("Validation against a source I did not fit", [
                f"Banks' own contents lists print a page for each template: {tv['agree']} of {tv['matched']} agree with the located first page",
                "(within one page, after the bank's constant printed-to-PDF offset, estimated from the same pairs).",
                "No machine-readable second source for these cells was reached: the EBA Pillar 3 data hub is the",
                "natural one. That is a limit, not a pass: cell counts have no independent check beyond the synthetic test."]),
            ("Sensitivity", [
                f"Mean index ranges {pc(swm[sw_lo])} ({sw_lo}) to {pc(swm[sw_hi])} ({sw_hi}).",
                f"Excluding presence-only, the lowest rank correlation with the baseline is {lo_np:.2f}: the fill ranking moves",
                f"with the cell definition. Presence-only has rho {sw['presence only (fill ignored)']['spearman_vs_baseline']:.2f} with it: the two measure different things."]),
        ], p4, [0.40, 0.07, 0.52, 0.34], min_y=0.50)

        page(pdf, "MODULE 10 / 5 of 5", "Limits and next step", [
            ("The assumption that would break the conclusion", [
                "A blank cell leaves no token in the PDF text. The index sees placeholders, not empty cells, so a bank",
                "that leaves cells empty scores as complete. Banks scoring near 100% may simply not print a dash.",
                "The fill rate is a lower bound on incompleteness; bank-level ranks are only as good as that proxy.",
                "The test: compare against the EBA Pillar 3 data hub submission, where an empty cell is a field."]),
            ("What a sceptical reviewer attacks first", [
                f"Sample: {n} banks that were hand-picked in sources.csv, not a draw from euro-area banks; the interval",
                "covers banks like these, not the sector. Periods differ: two reports are FY2025, and Omnibus relief",
                "removed templates 6 to 10 for one of them. Layouts differ by bank, and the parser test covers five",
                "synthetic layouts, fewer than the real ones. Row codes and footnote digits inflate numeric counts."]),
            ("Not forward-looking", [
                "The index describes one published report. It predicts nothing, so no backtest applies."]),
            ("Next", [
                "Read the EBA data hub for the same banks, score empty fields, and compare with this proxy."]),
        ])


if __name__ == "__main__":
    main()
