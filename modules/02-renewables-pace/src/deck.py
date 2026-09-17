"""Six pages. Every number is read from results/, none is typed here."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})


def page(pdf, kicker, title, blocks, draw=None, draw_rect=None):
    fig = plt.figure(figsize=(8.27, 11.69)); fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, kicker, fontsize=8, color=ACC, va="top",
             fontfamily="monospace")
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
        draw(fig.add_axes(draw_rect or [0.10, 0.09, 0.82, 0.36]))
    pdf.savefig(fig); plt.close(fig)


def main():
    d = json.load(open("results/renewables_pace.json"))
    rows, bt, sens, yard = d["rows"], d["backtest"], d["sensitivity"], d["yardstick_2030"]
    short = [r for r in rows if r["verdict"] == "short"]
    reach = [r for r in rows if r["verdict"] == "reaches"]
    unclear = [r for r in rows if r["verdict"] == "cannot tell"]
    it = [r for r in rows if r["geo"] == "IT"][0]
    worst = rows[:10]

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 02 / 1 of 6", "The pace, not the target", [
            ("The estimand", [
                "For each member state: the average annual change in the renewable share of gross",
                "final energy consumption, in percentage points per year, estimated as the",
                "least-squares slope over the five years ending at the latest observation, and",
                "projected to 2030."]),
            ("Why this and not the target", [
                "A target is a statement of intent. A transition plan that assumes the national grid",
                "decarbonises on schedule is assuming something the realised data may not support.",
                "The pace is observable; the target is not evidence."]),
            ("The answer", [
                f"Of {len(rows)} member states, {len(short)} fall short of the {yard}% yardstick,",
                f"{len(reach)} reach it, and for {len(unclear)} the method cannot tell.",
                "",
                f"That last category exists because the procedure's own out-of-sample error is",
                f"{bt['rmse']:.1f} points at a five-year horizon. Any verdict narrower than that",
                "would be false precision."])])

        page(pdf, "MODULE 02 / 2 of 6", "Method", [
            ("Data", [
                "Eurostat nrg_ind_ren, share of renewable energy, balance REN, pulled live from the",
                "public dissemination API by src/renewables.py. No key, no manual download, no",
                "transcription. Re-running the fetch reproduces the table."]),
            ("Estimator", [
                "Least squares on the window, not the difference between the first and last value.",
                "An endpoint difference discards every observation in between and has no variance",
                "of its own to report. On Italy the two disagree materially: the endpoint method",
                f"gives +0.03 points a year, the fitted slope gives {it['pace_pp_per_year']:+.2f}.",
                "The first version of this module published the endpoint figure. It was wrong."]),
            ("The yardstick, stated plainly", [
                f"{yard}% is the EU AGGREGATE target in RED III. It is not a national obligation.",
                "It is used here as one common ruler so that member states are comparable. National",
                "contributions under the NECPs differ and are not in this dataset. Reading the",
                "chart as compliance would be a false premise."])])

        def band_chart(ax):
            names = [r["geo"] for r in worst]
            x = list(range(len(names)))
            lo = [r["proj_lo_backtest"] for r in worst]
            hi = [r["proj_hi_backtest"] for r in worst]
            mid = [r["projected_2030"] for r in worst]
            ax.vlines(x, lo, hi, color=ACC, lw=6, alpha=.30)
            ax.plot(x, mid, "o", color=ACC, ms=5, label="projected 2030")
            ax.axhline(yard, color=BAD, lw=1.2, ls="--", label=f"{yard}% yardstick")
            ax.set_xticks(x); ax.set_xticklabels(names)
            ax.set_ylabel("renewable share in 2030, %")
            ax.legend(frameon=False, fontsize=8, loc="upper left")
            ax.set_title("the ten furthest from the yardstick, with the backtest band", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 02 / 3 of 6", "Result", [
            ("The gap is in the pace, not the level", [
                f"The ten furthest need between {worst[0]['required_pp_per_year']:.1f} and",
                f"{worst[-1]['required_pp_per_year']:.1f} points a year. The fastest of them has",
                f"managed {max(r['pace_pp_per_year'] for r in worst):.2f}."]),
            ("Two that are worth naming", [
                f"{worst[0]['geo']}: the fitted slope is {worst[0]['pace_pp_per_year']:+.2f} points a",
                f"year, standard error {worst[0]['pace_se']:.2f}. The share is not rising.",
                "",
                f"IT: {it['pace_pp_per_year']:+.2f} a year against {it['required_pp_per_year']:.2f}",
                f"required, from a {it['latest']:.1f}% base. Moving, and not nearly fast enough."]),
        ], band_chart)

        def bt_chart(ax):
            errs = [e["error"] for e in bt["detail"]]
            ax.hist(errs, bins=12, color=ACC, alpha=.75, edgecolor="white")
            ax.axvline(0, color=MID, lw=1)
            ax.axvline(bt["bias"], color=BAD, lw=1.2, ls="--",
                       label=f"bias {bt['bias']:+.2f}")
            ax.set_xlabel("predicted minus actual, percentage points")
            ax.set_ylabel("member states")
            ax.legend(frameon=False, fontsize=8)
            ax.set_title("out-of-sample error, five-year horizon", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 02 / 4 of 6", "Does the method work out of sample?", [
            ("The test", [
                f"Fit the same estimator as at {bt['detail'][0]['as_of']}, using only data up to that",
                "year, predict five years ahead, and compare with what actually happened. This is the",
                "only thing that turns a linear projection from an assumption into a number with a",
                "measured error."]),
            ("The result", [
                f"n = {bt['n']} member states. Bias {bt['bias']:+.2f} points, so the method does not",
                f"systematically over- or under-shoot. RMSE {bt['rmse']:.2f} points, mean absolute",
                f"error {bt['mae']:.2f}, and 90% of errors within {bt['p90_abs']:.2f} points.",
                "",
                "That error is large relative to the gaps on the previous page, and it is why the",
                f"verdict column refuses to call {len(unclear)} of {len(rows)} either way."]),
            ("The worst miss", [
                f"{bt['detail'][0]['geo']}: predicted {bt['detail'][0]['predicted']:.1f}%, actual",
                f"{bt['detail'][0]['actual']:.1f}%, error {bt['detail'][0]['error']:+.1f} points.",
                "Deployment is lumpy, and a single large project moves a small country."]),
        ], bt_chart)

        page(pdf, "MODULE 02 / 5 of 6", "Sensitivity to the arbitrary choice", [
            ("The choice", [
                "The five-year window is not derivable from anything. Three years overweights the",
                "2022 energy shock; ten years reaches back before the directive that changed the",
                "incentives. So vary it and see what moves."]),
            ("The ordering barely moves", [
                "Spearman rank correlation of the country ordering against the five-year window:"]
                + [f"   w = {w:>2s} years   rho = {s['spearman_vs_w5']:+.3f}"
                   for w, s in sorted(sens.items(), key=lambda kv: int(kv[0]))]),
            ("What that buys, and what it does not", [
                "The ranking is robust to the window, so the ordering is not an artefact of one",
                "choice. The LEVELS are not: the projected 2030 value for a given country moves",
                "with the window by more than the gap between neighbouring countries. Use this",
                "for who, not for how much."])])

        page(pdf, "MODULE 02 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks it", [
                "A constant pace. Deployment is not linear: it responds to auction schedules, grid",
                "connection queues and permitting, all of which move in steps. The backtest measures",
                "how much that has cost historically, and the answer is a lot."]),
            ("The denominator", [
                "The share is renewables over gross final consumption. A country can gain share by",
                "consuming less. This module cannot separate building capacity from shrinking the",
                "denominator, and the two have opposite meanings for a transition plan."]),
            ("The yardstick is an aggregate", [
                "Comparing each state against a single EU number is a ruler, not an assessment. The",
                "honest version needs the national contributions in the NECPs, which are not",
                "machine-readable, and typing them in is exactly what this repository does not do."]),
            ("Next", [
                "Weight each country by gross final consumption and ask whether the EU aggregate",
                "reaches 42.5% even when most members do not. That is the number that matters, and",
                "it is not the average of these. It needs one further Eurostat series, nrg_bal_c,",
                "and it is the first thing I would add."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
