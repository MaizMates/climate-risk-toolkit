"""Six pages. Every number is read from results/, none is typed here."""
import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
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
        draw(fig.add_axes(draw_rect or [0.10, 0.09, 0.82, 0.34]))
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def mt(x):
    return f"{x / 1000:,.1f}"


def main():
    d = json.load(open(os.path.join(ROOT, "results", "lmdi.json")))
    h, b, v, sw = d["headline"], d["bootstrap"], d["validation"], d["sweep"]
    wx, ann, bys = d["weather_model"], d["annual"], d["by_sector"]
    b0, b1 = d["base_year"], d["last_year"]
    rng = d["sweep_range"]
    jk = d["jackknife_most_influential"]
    grp = rng["by_group"]
    pc = v["intensity_change_pct"]
    own = pc["productive_economy_final_energy_per_gva"]
    pub = pc["eurostat_nrg_ind_ei_gross_available_energy_per_gdp_clv15"]
    pre = [r for r in sw if r["variant"].startswith(f"{b0} to 2019")][0]
    post = [r for r in sw if r["variant"].startswith("2021 to")][0]
    gran1 = [r for r in sw if r["variant"].startswith("one cell per state")][0]
    gran3 = [r for r in sw if r["variant"].startswith("EU27 aggregates")][0]
    wxs = [r for r in sw if r["group"] == "weather"]
    rev = {r["year"]: r for r in ann}
    pr = d["energy_price"]
    rp = pr["real_energy_price"]
    only_agri = [s for s in bys if bys[s]["int"] > 0]
    wdiff = max(abs(r["int_pct"] - h["int_pct"]) for r in wxs)
    cs = lambda k: f"[{b[k][0] / 1000:,.1f}, {b[k][1] / 1000:,.1f}]"
    cp = lambda k: f"[{b[k + '_pct'][0]:+.1f}%, {b[k + '_pct'][1]:+.1f}%]"

    with PdfPages(os.path.join(ROOT, "deck.pdf")) as pdf:
        page(pdf, "MODULE 14 / 1 of 6", "Energy use fell. Was it efficiency?", [
            ("The estimand", [
                f"The change in EU27 final energy consumption of industry, services and agriculture",
                f"between {b0} and {b1}, in Mtoe, split by additive LMDI-I into an activity effect, a",
                "structure effect and an intensity effect that sum to the observed change exactly."]),
            ("The answer", [
                f"Consumption fell {abs(h['dE']) / 1000:,.1f} Mtoe ({h['dE_pct']:+.1f}% of {d['energy_base_ktoe'] / 1000:,.0f} Mtoe), 95% interval "
                f"{cs('dE')}.",
                f"Activity added {mt(h['act'])} Mtoe {cs('act')}.",
                f"Structure removed {mt(abs(h['str']))} Mtoe {cs('str')}: value added moved to leaner cells.",
                f"Intensity removed {mt(abs(h['int']))} Mtoe {cs('int')}, {h['int_pct']:+.1f}% of {b0} use.",
                "",
                f"Intensity is {100 * d['intensity_share_of_offset']:.0f}% of the offset to activity growth "
                f"[{100 * b['intensity_share_of_offset'][0]:.0f}%, {100 * b['intensity_share_of_offset'][1]:.0f}%]."]),
            ("What it does not say", [
                f"{100 * d['intensity_2022_23_share']:.0f}% of the intensity effect falls in 2022 and 2023, when the real energy price",
                f"index (HICP energy over all items, {b0}=100) went from {rp['2021']:.0f} to {rp['2022']:.0f}. A fall in energy per euro of value added is not the same thing",
                "as an efficiency gain, and the deck shows where the two come apart."]),
            ("Nothing here is a forecast", [
                "The decomposition accounts for a change that has happened. It projects nothing, so",
                "there is no backtest; the checks are the identity, the sweep and Eurostat's own series."])])

        page(pdf, "MODULE 14 / 2 of 6", "Method", [
            ("Data", [
                "Eurostat nrg_bal_s (final consumption by sector, KTOE, all fuels) and nama_10_a10",
                "(gross value added, chain-linked 2015 prices), pulled live from the public API by",
                f"src/fetch.py. {d['member_states']} member states, three sectors each: {d['cells']} cells. Households and",
                "transport are outside the estimand because they have no value-added denominator."]),
            ("Sector mapping", [
                "Industry (FC_IND_E) over NACE B-E and F; services (FC_OTH_CP_E) over G to U;",
                "agriculture (FC_OTH_AF_E) over A. The mapping is a choice; the sweep varies it."]),
            ("Decomposition", [
                "For each cell i: E = Q x S_i x I_i, with Q total value added, S_i the cell's share",
                "and I_i its energy per unit of value added. Additive LMDI-I weights each log ratio",
                "by the logarithmic mean of the cell's energy in the two years, which leaves no",
                "residual. Effects are computed year by year and summed (chained)."]),
            ("Interval", [
                f"Cluster bootstrap over member states, {b['n']} draws, seed {b['seed']}. A state comes with all three",
                "of its sectors; the total, activity and structure are recomputed on every draw.",
                "It answers: how much does the headline depend on which states the EU is made of.",
                "It does not measure error in Eurostat's figures, which the identity cannot see."]),
            ("Check on the arithmetic", [
                f"Identity residual {d['identity_residual_ktoe']:.0e} ktoe; largest over {b['n']} bootstrap draws "
                f"{b['max_identity_residual_ktoe']:.0e} ktoe."])])

        def waterfall(ax):
            names = ["activity", "structure", "intensity", "observed\nchange"]
            ks = ["act", "str", "int", "dE"]
            vals = [h[k] / 1000 for k in ks]
            cols = [WARN, ACC, ACC, MID]
            ax.bar(range(4), vals, color=cols, width=0.55)
            for i, k in enumerate(ks):
                lo, hi = b[k][0] / 1000, b[k][1] / 1000
                ax.plot([i, i], [lo, hi], color=INK, lw=1.4)
                ax.plot([i - .07, i + .07], [lo, lo], color=INK, lw=1.4)
                ax.plot([i - .07, i + .07], [hi, hi], color=INK, lw=1.4)
                ax.text(i + .32, vals[i], f"{vals[i]:+.1f}", va="center", fontsize=8.5, color=INK)
            ax.axhline(0, color=MID, lw=1)
            ax.set_xticks(range(4)); ax.set_xticklabels(names)
            ax.set_ylabel(f"Mtoe, {b0} to {b1}")
            ax.set_title("effects with 95% bootstrap interval over member states", loc="left")
            clean(ax)

        page(pdf, "MODULE 14 / 3 of 6", "Result", [
            ("Three effects, one identity", [
                f"Observed {mt(h['dE'])} Mtoe = activity {mt(h['act'])} + structure {mt(h['str'])} + intensity {mt(h['int'])}.",
                f"As a share of {b0} use: {h['act_pct']:+.1f}%, {h['str_pct']:+.1f}%, {h['int_pct']:+.1f}%, net {h['dE_pct']:+.1f}%."]),
            ("What the intervals support", [
                f"Intensity is negative in {100 * b['share_draws_intensity_negative']:.0f}% of draws and structure in {100 * b['share_draws_structure_negative']:.0f}%.",
                f"The net fall is below zero across its interval {cp('dE')}.",
                f"Intensity exceeds activity growth in {100 * b['share_draws_intensity_offsets_activity']:.0f}% of draws: the point estimates say",
                "yes, the interval does not settle it. Do not read the two bars as a ranking.",
                f"Germany is the most influential state: without it the intensity effect is {mt(jk['int_without'])} Mtoe,",
                f"not {mt(jk['int_with'])}."])
        ], waterfall)

        def annual_chart(ax):
            ys = [r["year"] for r in ann]
            for j, (k, c, n) in enumerate((("act", WARN, "activity"), ("str", OK, "structure"),
                                           ("int", ACC, "intensity"))):
                ax.bar([y + (j - 1) * .27 for y in ys], [r[k] / 1000 for r in ann], color=c, width=.27, label=n)
            ax.plot(ys, [r["dE"] / 1000 for r in ann], "o-", color=INK, ms=4, lw=1, label="observed change")
            ax.axhline(0, color=MID, lw=1)
            ax.set_ylabel("Mtoe, year on year"); ax.legend(frameon=False, fontsize=8, ncol=4, loc="lower left")
            ax.set_title("the chained annual effects", loc="left"); clean(ax)

        page(pdf, "MODULE 14 / 4 of 6", "When it happened, and where", [
            ("The timing is the finding", [
                f"{b0 + 1} to 2019: intensity effects sum to {sum(rev[y]['int'] for y in range(b0 + 1, 2020)) / 1000:+.1f} Mtoe; activity added "
                f"{sum(rev[y]['act'] for y in range(b0 + 1, 2020)) / 1000:+.1f}.",
                f"2020: activity {rev[2020]['act'] / 1000:+.1f}, intensity {rev[2020]['int'] / 1000:+.1f}. Output fell faster than energy, so intensity rose.",
                f"2022 and 2023: intensity {rev[2022]['int'] / 1000:+.1f} and {rev[2023]['int'] / 1000:+.1f} Mtoe; real energy price index {rp['2021']:.0f}, {rp['2022']:.0f}, {rp['2023']:.0f} (2021 to 2023).",
                f"Those two years carry {100 * d['intensity_2022_23_share']:.0f}% of the {b0} to {b1} intensity effect "
                f"[{100 * b['intensity_2022_23_share'][0]:.0f}%, {100 * b['intensity_2022_23_share'][1]:.0f}%]."]),
            ("By sector (Mtoe)", [
                f"Industry:     intensity {mt(bys['industry']['int'])}, structure {mt(bys['industry']['str'])}, activity {mt(bys['industry']['act'])}.",
                f"Services:     intensity {mt(bys['services']['int'])}, structure {mt(bys['services']['str'])}, activity {mt(bys['services']['act'])}.",
                f"Agriculture:  intensity {mt(bys['agriculture']['int'])}, structure {mt(bys['agriculture']['str'])}, activity {mt(bys['agriculture']['act'])}.",
                f"Sectors whose intensity rose: {', '.join(only_agri) or 'none'}."])
        ], annual_chart, [0.10, 0.08, 0.82, 0.45])

        def sweep_chart(ax):
            order = sorted(range(len(sw)), key=lambda i: sw[i]["int_pct"])
            lab = [sw[i]["group"] + ": " + sw[i]["variant"][:62] for i in order]
            xs = [sw[i]["int_pct"] for i in order]
            ax.axvspan(b["int_pct"][0], b["int_pct"][1], color=ACC, alpha=.12,
                       label="95% interval, base case")
            ax.axvline(h["int_pct"], color=ACC, lw=1.2)
            ax.scatter(xs, range(len(xs)), color=[BAD if sw[i]["group"] == "base" else ACC for i in order], s=18, zorder=3)
            ax.set_yticks(range(len(xs))); ax.set_yticklabels(lab, fontsize=6.8)
            ax.set_xlabel("intensity effect, % of base-year energy")
            ax.legend(frameon=False, fontsize=8, loc="lower right"); clean(ax)

        page(pdf, "MODULE 14 / 5 of 6", "Validation and sensitivity", [
            ("Against what Eurostat publishes", [
                "Energy summed over states equals the published EU27 total in every sector and year;",
                f"value added differs by at most {v['max_abs_gva_diff_pct']:.2f}% (chain-linked volumes are not strictly additive).",
                f"Final energy per unit of value added of the productive economy: {own:+.1f}%. Eurostat's own energy",
                f"intensity of the economy (nrg_ind_ei, gross available energy per GDP): {pub:+.1f}%. Different",
                "numerators and denominators, same direction and order of magnitude; no like-for-like series exists."]),
            ("What moves the intensity effect", [
                f"Across {len(sw)} variants it runs from {rng['int_pct'][0]:+.1f}% to {rng['int_pct'][1]:+.1f}% of base-year energy; it is negative in all.",
                f"Sector mapping: {grp['sector mapping'][0]:+.1f}% to {grp['sector mapping'][1]:+.1f}%. Base year: {grp['base year'][0]:+.1f}% to {grp['base year'][1]:+.1f}%.",
                f"End year: {pre['int_pct']:+.1f}% to 2019, {post['int_pct']:+.1f}% for {2021}-{b1} alone. 2020 in or out of the chain: no change.",
                f"Weather (services, HDD elasticity {wx['elasticity_hdd']:.2f}, se {wx['se']:.2f}): {min(r['int_pct'] for r in wxs):+.1f}% to {max(r['int_pct'] for r in wxs):+.1f}%.",
                f"Granularity matters most for structure: {gran1['str_pct']:+.1f}% with one cell per state,",
                f"{gran3['str_pct']:+.1f}% with EU27 aggregates only, {h['str_pct']:+.1f}% with both dimensions."])
        ], sweep_chart, [0.52, 0.08, 0.42, 0.33])

        page(pdf, "MODULE 14 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks it", [
                "That a fall in energy per unit of value added is efficiency. It is an accounting",
                f"residual: fuel switching, price-driven curtailment and lower output of energy-intensive",
                f"products inside a sector all land in it. {100 * d['intensity_2022_23_share']:.0f}% of it sits in 2022 and 2023, which is",
                "consistent with curtailment, though nothing here proves it. Three sectors cannot separate the cases."]),
            ("Sector detail", [
                f"Moving from one cell per state to three sectors shifted {gran1['str_pct'] - h['str_pct']:.1f} points from intensity to",
                "structure. Finer industry detail may shift more; I have not tested it, so the intensity",
                "effect here is not a clean estimate of within-activity change."]),
            ("Other attacks", [
                f"Weather: EU27 heating degree days fell {abs(d['hdd_eu27']['change_pct']):.1f}% between {b0} and {b1}; correcting services",
                f"energy moves the intensity effect by at most {wdiff:.1f} points, and the elasticity is itself estimated.",
                "Value added is a volume index: structural change in prices and the treatment of",
                "energy-sector own use are not modelled. The interval covers the choice of states, not",
                "revisions to Eurostat's figures."]),
            ("Next", [
                "Industry by branch (nrg_bal_c against nama_10_a64) to split structure from intensity",
                "where it matters, and the same decomposition on 2022 to 2024 with monthly prices."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
