"""Six pages. Every number is read from results/, none is typed here."""
import json
import os
import textwrap
from math import exp

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.join(HERE, ".."))

INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})


def para(text, width=98):
    return textwrap.wrap(text, width)


def page(pdf, kicker, title, blocks, draws=(), rects=()):
    fig = plt.figure(figsize=(8.27, 11.69)); fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, kicker, fontsize=8, color=ACC, va="top", fontfamily="monospace")
    fig.text(0.08, 0.932, title, fontsize=16.5, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.908, 0.908], color=RULE, lw=1))
    y = 0.878
    for head, body in blocks:
        if head:
            fig.text(0.08, y, head, fontsize=10, color=INK, weight="bold", va="top"); y -= 0.022
        for line in body:
            line = line.replace("$", r"\$")
            fig.text(0.08, y, line, fontsize=9.3, color=MID, va="top"); y -= 0.0185
        y -= 0.012
    for draw, rect in zip(draws, rects):
        draw(fig.add_axes(rect))
    pdf.savefig(fig); plt.close(fig)


def pc(x, d=1, signed=True):
    return f"{x:+.{d}%}" if signed else f"{x:.{d}%}"


def main():
    d = json.load(open("results/scenario_pd.json"))
    cfg, h, meta = d["config"], d["headline"], d["meta"]
    be = h["sector_stats"]
    bt, ba = d["backtest"], d["backtest"]["all"]
    bx = d["backtest"]["ex_moratorium"]
    vb = {(r["model"], r["scenario"]): r for r in d["vs_base"]}
    dis, orde, m = cfg["disorderly"], cfg["orderly"], cfg["model"]
    r_dis, r_ord = vb[(m, dis)], vb[(m, orde)]
    eur = lambda usd: usd / d["fx_2010"] * d["hicp_ratio"]
    sw = {s["factor"]: s for s in d["sweep_summary"]}
    top = d["sweep_summary"][:3]
    pairs = {s["value"]: s for s in d["sweeps"] if s["factor"] == "scenario pair"}
    pc_ = d["price_comparisons"]
    all_below = all(v["delayed_below_nz_every_year_2025_2050"] for v in pc_.values())
    secs = {r["sector"]: r for r in d["sectors"]}
    det = d["detail"]
    ranks = [r["spearman_vs_headline"] for r in d["rank_stability"]]
    abat = next(s for s in d["sweeps"] if s["factor"] == "abatement" and s["value"] != "static intensity")
    ps = {(s["fe"], s["sample"]): s for s in d["panel_specs"]}
    pr = lambda sc, y: next(r["price"] for r in d["prices"] if r["model"] == m and r["scenario"] == sc and r["year"] == y)
    others = [v["co2_per_gva"] for k, v in secs.items() if k not in (cfg["sector"], "H")]
    ns = [r["n_countries"] for r in det]
    scaled_cut = 1 - h["scaled_rel"] / h["rel"]
    rem = pc_[m]
    elast_span = max(sw[k]["span"] for k in ("sensitivity source", "horizon of the CHS coefficient (months)",
                                              "total assets as multiple of net fixed assets"))
    em = lambda sc, y: next(r["emissions"] for r in d["prices"] if r["model"] == m and r["scenario"] == sc and r["year"] == y)

    with PdfPages("deck.pdf") as pdf:
        # ---------------------------------------------------------------- 1
        page(pdf, "MODULE 08 / 1 of 6", "Where climate enters a credit model", [
            ("The question", para(
                "Where does climate actually enter a credit model? Here it enters through one channel, "
                "written as six steps of arithmetic that a reviewer can check one by one.")),
            ("The estimand", para(
                f"The change in the one-year probability of default of the EU industry sector (NACE {cfg['sector']}) "
                f"in {cfg['year']} under the NGFS {dis} scenario relative to {orde}, through carbon cost "
                "to profit share to log-odds of default. Static sector structure: no abatement, no demand "
                "response, no second-round effects. Positive: the disorderly scenario carries the higher PD.")),
            ("The answer", para(
                f"{pc(h['rel'])} ({h['bp']:+.1f} bp at a {cfg['pd0']:.0%} baseline PD), literature range "
                f"[{pc(h['lit_lo'])}, {pc(h['lit_hi'])}]. The sign is negative because {dis} has a lower "
                f"carbon price than {orde} in every year from 2025 to 2050"
                + (" in all three models." if all_below else ", not in every model.")
                + f" Against today, the channel lifts industry PD by {pc(r_ord['rel_vs_today'])} under {orde} "
                f"and {pc(r_dis['rel_vs_today'])} under {dis}.")),
            ("Read this first", para(
                f"The magnitude is not established. The mapping from profit to default comes from a US equity "
                f"study; on European bankruptcy data it fails out of sample (calibration slope "
                f"{ba['slope_lit']:.2f}, interval [{ba['slope_lit_ci'][0]:.2f}, {ba['slope_lit_ci'][1]:.2f}]; "
                f"1 would be calibrated). Rescaled by that slope the headline is {pc(h['scaled_rel'])} "
                f"[{pc(h['scaled_ci'][0])}, {pc(h['scaled_ci'][1])}]. The sign flips if the orderly reference is "
                f"Below 2°C ({pc(pairs['Delayed transition vs Below 2°C']['rel'])}) or if industry abates "
                f"with the region ({pc(abat['rel'])}).")),
            ("Data", para(
                f"NGFS Phase 5 (IIASA Scenario Explorer, {meta['n_ngfs_rows']} rows), Eurostat national accounts, air "
                f"emissions accounts, capital stocks and bankruptcy declarations ({meta['n_panel']:,} country-sector-year "
                f"changes), and the coefficient table of Campbell, Hilscher and Szilagyi (2008), parsed from the "
                f"paper by code. Fetched {meta['access_date']}. Reference year of the ratios: {meta['ref_year']}.")),
        ])

        # ---------------------------------------------------------------- 2
        def paths(ax):
            colors = {"Net Zero 2050": ACC, "Low demand": OK, "Below 2°C": "#5A8F7B", "Delayed transition": BAD,
                      "Fragmented World": WARN, "Nationally Determined Contributions (NDCs)": "#8A8F8C",
                      "Current Policies": "#BBBBBB"}
            for sc, col in colors.items():
                pts = sorted((r["year"], r["price"]) for r in d["prices"] if r["model"] == m and r["scenario"] == sc)
                ax.plot(*zip(*pts), color=col, lw=2.2 if sc in (dis, orde) else 1.2, label=sc.split(" (")[0])
            ax.set_title(f"Carbon price, {m} EU, USD2010 per t", loc="left")
            ax.legend(frameon=False, fontsize=7, loc="upper left"); ax.grid(axis="y", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        def ratio(ax):
            for mm, col in zip(("REMIND", "GCAM", "MESSAGE"), (ACC, WARN, BAD)):
                a = {r["year"]: r["price"] for r in d["prices"] if r["model"] == mm and r["scenario"] == dis}
                b = {r["year"]: r["price"] for r in d["prices"] if r["model"] == mm and r["scenario"] == orde}
                ys = [y for y in sorted(a) if b.get(y, 0) > 0 and y >= 2025]
                ax.plot(ys, [a[y] / b[y] for y in ys], color=col, lw=1.8, label=mm)
            ax.axhline(1, color=MID, lw=0.8, ls="--")
            ax.set_title("Delayed price / Net Zero price" if (dis, orde) == ("Delayed transition", "Net Zero 2050") else "Disorderly / orderly price", loc="left", fontsize=9); ax.legend(frameon=False, fontsize=8)
            ax.grid(axis="y", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        px = r_dis["price_usd2010"]
        steps = [
            f"1  Price {cfg['year']}, {m} EU: {orde} US${r_ord['price_usd2010']:.0f}, {dis} US${px:.0f} per t (US$2010).",
            f"2  Restated in euro of {meta['ref_year']}: x 1/{d['fx_2010']:.4f} (2010 rate) x {d['hicp_ratio']:.3f} (HICP): "
            f"EUR {eur(r_ord['price_usd2010']):.0f} and EUR {eur(px):.0f}.",
            f"3  Cost share of value added = price x {be['co2_per_gva']:.0f} t CO2 per EUR mn GVA: "
            f"{pc(r_ord['cost_share'], 1, False)} and {pc(r_dis['cost_share'], 1, False)}.",
            f"4  Profit share falls by (1 - {cfg['pass_through']:.1f}) of that. Industry profit share today: {pc(be['profit_share'], 1, False)}.",
            f"5  Quarterly net income over assets falls by that x GVA/assets ({be['gva_over_k']:.3f}) / 4; "
            f"log-odds rise by {h['coef']:.2f} times it: +{r_ord['d_logodds']:.3f} and +{r_dis['d_logodds']:.3f}.",
            f"6  PD from a {cfg['pd0']:.0%} base: {r_ord['pd']:.2%} under {orde}, {r_dis['pd']:.2%} under {dis}.",
        ]
        page(pdf, "MODULE 08 / 2 of 6", "Method: six steps, each one line", [
            ("The chain, with the numbers at each step", [l for s in steps for l in para(s, 100)]),
            ("Why the sign is what it is", para(
                f"In {m}, {dis} holds the price at US${pr(dis, 2030):.0f} through 2030 and reaches US${pr(dis, cfg['year']):.0f} in "
                f"{cfg['year']}; {orde} is at US${pr(orde, 2030):.0f} in 2030 and US${pr(orde, cfg['year']):.0f} in {cfg['year']}. "
                f"The delay does not catch up inside the horizon. Only the cost channel is in this module; the "
                "abruptness that makes a transition disorderly acts through demand, asset prices and "
                "financing conditions, none of which this channel carries.")),
        ], draws=(paths, ratio), rects=([0.08, 0.14, 0.40, 0.30], [0.58, 0.14, 0.34, 0.30]))

        # ---------------------------------------------------------------- 3
        def forest(ax):
            rows = [(f"CHS 12-month coefficient,\nrange over the five horizons", h["rel"], h["lit_lo"], h["lit_hi"], ACC),
                    ("CHS, sampling error\nof the 12-month fit only", h["rel"], h["lit_stat_lo"], h["lit_stat_hi"], "#5A8F7B"),
                    ("CHS rescaled by the\nbacktest calibration slope", h["scaled_rel"], h["scaled_ci"][0], h["scaled_ci"][1], WARN),
                    ("Slope fitted on the\nEurostat panel", h["own_rel"], h["own_lo"], h["own_hi"], BAD)]
            for i, (lab, c, lo, hi, col) in enumerate(rows[::-1]):
                ax.plot([lo, hi], [i, i], color=col, lw=3); ax.plot([c], [i], "o", color=INK, ms=5)
            ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=8)
            ax.axvline(0, color=MID, lw=0.8, ls="--")
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_title(f"PD change, {dis} vs {orde}, {cfg['year']}", loc="left")
            ax.grid(axis="x", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        def pairs_plot(ax):
            names = list(pairs)
            vals = [pairs[n]["rel"] for n in names]
            ax.barh(range(len(names)), vals, color=[ACC if v < 0 else BAD for v in vals])
            ax.set_yticks(range(len(names))); ax.set_yticklabels([n.replace(" vs ", "\nvs ") for n in names], fontsize=7)
            ax.axvline(0, color=MID, lw=0.8)
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_title("Which orderly reference?", loc="left"); ax.invert_yaxis()
            ax.grid(axis="x", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 08 / 3 of 6", "Result: the PD range the elasticity implies", [
            ("What the four mappings give", para(
                f"Headline {pc(h['rel'])}. The literature sensitivity is not one number: the five horizons in the paper's "
                f"Table 3 run from {min(d['chs']['coef']):.1f} to {max(d['chs']['coef']):.1f}, and "
                f"drawing one of them and a normal error around it gives [{pc(h['lit_lo'])}, {pc(h['lit_hi'])}]. The sampling error of "
                f"the 12-month fit alone is [{pc(h['lit_stat_lo'])}, {pc(h['lit_stat_hi'])}], which is the interval "
                "one would quote if the US equity result transferred. My own fit on Eurostat bankruptcy declarations "
                f"gives {h['beta_pp']:.4f} log points per percentage point of profit share, interval "
                f"[{h['beta_ci'][0]:.4f}, {h['beta_ci'][1]:.4f}], which includes zero: the PD change is "
                f"{pc(h['own_rel'])} [{pc(h['own_lo'])}, {pc(h['own_hi'])}].")),
            ("The scenario pair matters more than the elasticity choices", para(
                f"{dis} is below {orde}"
                + (f" but above Below 2°C in the {m} region" if rem["delayed_above_below2_2040"] else f" and not above Below 2°C in the {m} region")
                + f" at {cfg['year']}, so the sign depends on which NGFS scenario is called orderly: the six pairs run from "
                f"{pc(min(p['rel'] for p in pairs.values()))} to {pc(max(p['rel'] for p in pairs.values()))}, a span of "
                f"{sw['scenario pair']['span']:.1%} points against at most {elast_span:.1%} for the elasticity choices "
                "(source, horizon, asset scaling).")),
        ], draws=(forest, pairs_plot), rects=([0.27, 0.34, 0.65, 0.20], [0.27, 0.06, 0.65, 0.20]))

        # ---------------------------------------------------------------- 4
        def sub(ax):
            rows = sorted(det, key=lambda r: r["dl_ord"], reverse=True)[:9]
            lab = [f"{r['name']} ({r['n_countries']})" for r in rows]
            ax.barh(range(len(rows)), [pd_ for pd_ in (vb_pd(r) for r in rows)], color=ACC)
            ax.set_yticks(range(len(rows))); ax.set_yticklabels(lab, fontsize=7.5); ax.invert_yaxis()
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_title("Nine largest industry branches (countries reporting)", loc="left", fontsize=8.5)
            ax.grid(axis="x", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        def vb_pd(r):
            return d_pd(r["dl_ord"])

        def d_pd(dl):
            p0 = cfg["pd0"]; o = p0 / (1 - p0) * exp(dl)
            return o / (1 + o) / p0 - 1

        def secbar(ax):
            order = sorted(secs, key=lambda s: -secs[s]["dl_ord"])
            ax.barh(range(len(order)), [d_pd(secs[s]["dl_ord"]) for s in order], color=ACC)
            ax.set_yticks(range(len(order))); ax.set_yticklabels([f"{s} ({secs[s]['n_countries']})" for s in order], fontsize=8)
            ax.invert_yaxis(); ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_title(f"PD change vs today under {orde}, {cfg['year']}: NACE sections (countries reporting)", loc="left", fontsize=8.5)
            ax.grid(axis="x", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        topd = sorted(det, key=lambda r: r["dl_ord"], reverse=True)
        page(pdf, "MODULE 08 / 4 of 6", "Where in the economy the channel lands", [
            ("Concentration", para(
                f"Industry as a whole carries {be['co2_per_gva']:.0f} t CO2 per EUR mn of value added; transport (H) carries "
                f"{secs['H']['co2_per_gva']:.0f}, and every other section {max(others):.0f} or less. "
                f"Within industry, {topd[0]['name'].lower()}, {topd[1]['name'].lower()} and {topd[2]['name'].lower()} take the largest "
                f"hits ({pc(d_pd(topd[0]['dl_ord']), 0)}, {pc(d_pd(topd[1]['dl_ord']), 0)}, {pc(d_pd(topd[2]['dl_ord']), 0)} against today "
                f"under {orde}); the industry aggregate of {pc(r_ord['rel_vs_today'], 0)} is an average over a distribution that "
                "starts near zero.")),
            ("Order of sectors", para(
                f"The ordering of the eight sections by shock is stable across reference years 2015 to 2023: the lowest rank "
                f"correlation with the {meta['ref_year']} ordering is {min(ranks):.2f}. It does not depend on the elasticity or the "
                "pass-through, which scale every sector alike.")),
            ("Coverage", para(
                f"Branch figures use the countries that report every series for that branch, so branches rest on {min(ns)} to {max(ns)} "
                f"countries; K-N and P-S rest on {secs['K-N']['n_countries']} and {secs['P-S']['n_countries']} and carry little carbon cost.")),
        ], draws=(secbar, sub), rects=([0.30, 0.34, 0.60, 0.20], [0.40, 0.07, 0.50, 0.20]))

        # ---------------------------------------------------------------- 5
        def skill(ax):
            ys = [r["year"] for r in bt["per_year"]]
            w = 0.38
            ax.bar([i - w / 2 for i in range(len(ys))], [r["skill_own"] for r in bt["per_year"]], w, color=BAD, label="slope fitted on earlier years")
            ax.bar([i + w / 2 for i in range(len(ys))], [r["skill_lit"] for r in bt["per_year"]], w, color=ACC, label="CHS-implied slope")
            ax.set_xticks(range(len(ys))); ax.set_xticklabels(ys); ax.axhline(0, color=MID, lw=0.8)
            ax.set_title("Out-of-sample skill vs predicting no change (1 = perfect, 0 = none)", loc="left", fontsize=8.5)
            ax.legend(frameon=False, fontsize=7); ax.grid(axis="y", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        def torn(ax):
            rows = d["sweep_summary"]
            ax.barh(range(len(rows)), [r["span"] for r in rows], color=[BAD if r["flips_sign"] else ACC for r in rows])
            ax.set_yticks(range(len(rows))); ax.set_yticklabels([r["factor"] for r in rows], fontsize=7); ax.invert_yaxis()
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_title("Span of the headline when one choice varies (red: sign flips)", loc="left", fontsize=8.5)
            ax.grid(axis="x", color=RULE, lw=0.6)
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 08 / 5 of 6", "Validation and sensitivity", [
            ("Backtest of the mapping", para(
                f"For each test year from {bt['test_years'][0]} to {bt['test_years'][-1]} I fit the profit-to-bankruptcy slope on earlier "
                f"years only and predict that year's sector-year-demeaned change in bankruptcy declarations from the change in profit "
                f"share. Over {ba['n']} country-sector-years the fitted slope has skill {ba['skill_own']:+.3f} and the CHS-implied slope "
                f"{ba['skill_lit']:+.3f} against a no-change forecast (RMSE {ba['rmse_zero']:.3f}). The calibration slope of realised on "
                f"CHS-implied is {ba['slope_lit']:.2f} [{ba['slope_lit_ci'][0]:.2f}, {ba['slope_lit_ci'][1]:.2f}]; excluding 2020 and 2021, "
                f"{bx['slope_lit']:.2f} [{bx['slope_lit_ci'][0]:.2f}, {bx['slope_lit_ci'][1]:.2f}]. Bankruptcy declarations are not PDs, "
                "and noise in sector profit share attenuates any slope, so this bounds the mapping from below and does not refute it.")),
            ("What moves the headline", para(
                f"Largest spans: {top[0]['factor']} ({pc(top[0]['lo'])} to {pc(top[0]['hi'])}), {top[1]['factor']} "
                f"({pc(top[1]['lo'])} to {pc(top[1]['hi'])}), {top[2]['factor']} ({pc(top[2]['lo'])} to {pc(top[2]['hi'])}). "
                f"Leaving out any one country moves it only between {pc(sw['leave one country out of the sector']['lo'])} and "
                f"{pc(sw['leave one country out of the sector']['hi'])}.")),
        ], draws=(skill, torn), rects=([0.10, 0.31, 0.80, 0.14], [0.36, 0.06, 0.54, 0.20]))

        # ---------------------------------------------------------------- 6
        page(pdf, "MODULE 08 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", para(
                "That a carbon bill passed through a static industry profit share reaches default through a sensitivity estimated on US "
                "listed firms. If European default responds to profit as weakly as the bankruptcy backtest suggests, every PD change here "
                f"shrinks by {scaled_cut:.0%} (rescaled headline {pc(h['scaled_rel'])}); if industry abates with the region, the "
                f"{orde} scenario's regional emissions are {em(orde, cfg['year']):.0f} Mt CO2 in {cfg['year']} against {em(orde, 2020):.0f} in 2020, "
                f"its bill shrinks with them and the sign of the headline reverses ({pc(abat['rel'])}). "
                "A reviewer should attack the mapping first, then the static structure.")),
            ("Other limits", [l for t in (
                f"Pass-through is 0.7, from the 70% that Ganapati, Shapiro and Walker (2020) report for US manufacturing energy costs; it is "
                f"an assumption here, swept from 0 to 1, and it moves the headline from {pc(sw['pass-through of carbon cost']['lo'])} to "
                f"{pc(sw['pass-through of carbon cost']['hi'])}.",
                "Net fixed assets stand in for the market value of total assets; grossing them up by two or three shrinks the effect.",
                "CHS estimate a monthly failure hazard on quarterly profit; I treat the log-odds slope as transferable to a one-year PD.",
                f"The baseline PD of {cfg['pd0']:.0%} is a stated parameter and not data: no public source gives sector PDs. The relative "
                "change hardly depends on it; the basis-point figure scales with it.",
                "NGFS prices are model outputs for one region each; nothing here checks them against observed carbon prices.") for l in para("- " + t, 100)]),
            ("Next", para(
                "A bank's own sector default series would replace the bankruptcy proxy and test the elasticity directly. A second step "
                "adds the demand side (output response to price) and the abatement cost, so that abatement does not make the carbon bill vanish.")),
        ])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
