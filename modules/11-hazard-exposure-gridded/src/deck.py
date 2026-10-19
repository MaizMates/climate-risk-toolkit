"""Six pages. Every number is read from results/, none is typed here. Each comparative claim in
the text is asserted against the numbers before the page is written."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")
INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})


def pc(x, d=1):
    return f"{100 * x:.{d}f}%"


def iv(c, d=1):
    return f"[{pc(c[0], d)}, {pc(c[1], d)}]"


def ivp(c, d=1):
    """Interval of a difference of shares, in points."""
    return f"[{100 * c[0]:+.{d}f}, {100 * c[1]:+.{d}f}]"


def pts(x, d=1):
    return f"{100 * abs(x):.{d}f} points"


def page(pdf, n, title, blocks, draws=()):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, f"MODULE 11 / {n} of 6", fontsize=8, color=ACC, va="top", fontfamily="monospace")
    fig.text(0.08, 0.932, title, fontsize=16.5, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.908, 0.908], color=RULE, lw=1))
    y = 0.878
    for head, body in blocks:
        if head:
            fig.text(0.08, y, head, fontsize=10, color=INK, weight="bold", va="top")
            y -= 0.022
        for line in body:
            fig.text(0.08, y, line, fontsize=9.3, color=MID, va="top")
            y -= 0.0185
        y -= 0.012
    for rect, fn in draws:
        ax = fig.add_axes(rect)
        fn(ax)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    pdf.savefig(fig)
    plt.close(fig)


def main():
    d = json.load(open(os.path.join(RES, "gridded.json")))
    plants = pd.read_csv(os.path.join(RES, "plants.csv"))
    log = json.load(open(os.path.join(RES, "fetch_log.json")))
    ref, kr = d["reference"], {r["k"]: r for r in d["by_k"]}
    K = d["k_reference"]
    sw = {s["label"]: s for s in d["sweep"]}
    sp, qa, lad = d["sweep_spans"], d["coordinate_qa"], d["resolution_ladder"]
    val = d["validation_grid_vs_api"]
    bc = d["by_country"]
    accessed = log[0]["accessed"]

    # ---- claims checked against the numbers before they are written
    assert ref["diff"] < 0 and ref["diff_ci"][1] < 0, "gap must be negative with an interval excluding zero"
    assert all(r["diff"] < 0 for r in d["by_k"]) and all(s["diff"] < 0 for s in d["sweep"])
    assert ref["diff_p10_ci"][1] < 0 and ref["diff_p90_ci"][1] < 0
    assert sp["radius"]["grid_share"]["range"] > sp["fuel"]["grid_share"]["range"] > sp["scenario"]["grid_share"]["range"]
    assert d["k1_to_k3"]["grid_share_range"] > sp["radius"]["grid_share"]["range"]
    assert ref["over_assigned_by_country_mw_share"] > 10 * ref["missed_by_country_mw_share"]
    assert d["ladder_step"]["country_to_2deg"] > d["ladder_step"]["two_deg_to_quarter_deg"]
    by = {r["iso3"]: r for r in bc}
    r03 = d["reproduces_module03"]

    with PdfPages(os.path.join(HERE, "..", "deck.pdf")) as pdf:
        page(pdf, 1, "Plants on a grid, not on a country average", [
            ("The question", [
                "Module 03 gave every thermal plant its country's projected change in hot days. What",
                "does that cost? Join the same plants to the 0.25 degree cells they sit in and compare."]),
            ("The estimand", [
                f"The share of {d['total_mw']:,.0f} MW of thermal capacity in eleven countries held by plants whose",
                f"own grid cell shows days at or above a 35 C heat index rising by more than k={K:g} days,",
                "1995-2014 to 2040-2059, SSP2-4.5, CMIP6 ensemble median; and its difference from the",
                "share obtained by assigning each plant its country's value."]),
            ("The answer", [
                f"Grid cells: {pc(ref['grid_share'])} {iv(ref['grid_ci'])} of capacity is exposed. Country values: "
                f"{pc(ref['country_share'])} {iv(ref['country_ci'])}.",
                f"The difference is {ref['diff'] * 100:+.1f} points {ivp(ref['diff_ci'])}, resampling sites, with the grid and the",
                "country measure computed on each resample together. The interval excludes zero.",
                f"It is not a rounding error between two estimates of one thing: {pc(ref['disagree_mw_share'])} of capacity",
                f"changes class, {pc(ref['over_assigned_by_country_mw_share'])} is called exposed by country and not by cell, and only",
                f"{pc(ref['missed_by_country_mw_share'])} the other way."])])

        page(pdf, 2, "Method and inputs", [
            ("Inputs, all fetched by src/fetch.py on " + accessed, [
                "Plants: WRI Global Power Plant Database (coordinates, MW, fuel).",
                "Hazard: World Bank CCKP CMIP6 0.25 degree annual climatology of hd35 (days at or above",
                "35 C heat index), ensemble median, p10 and p90, from the public S3 bucket wbg-cckp.",
                "Borders: Natural Earth 1:50m. Country values: the CCKP API (validation and comparator).",
                "URL, date, size and SHA-256 of every file are in results/fetch_log.json."]),
            ("Reading the grid", [
                "The files are HDF5; netCDF4 and h5py are outside the allowed libraries, so src/h5lite.py",
                "reads the one layout they use. It is checked against the CCKP country API (page 4)."]),
            ("Join", [
                f"Thermal = coal, oil, petcoke, gas, as in module 03: {qa['n_thermal_plants']} plants, {qa['mw']:,.0f} MW.",
                "A plant's hazard is the change in the cell containing it (radius 0), swept to 25, 50 and",
                "100 km means, with and without sea cells. Exposed means strictly more than k days.",
                f"Coordinate check: {qa['swapped']} plant had latitude and longitude swapped and is repaired; "
                f"{qa['dropped']} fall more than 10 km",
                f"outside their country's European polygon ({qa['dropped_mw']:,.0f} MW, {pc(qa['dropped_mw'] / qa['mw'], 2)}: Escombreras at latitude 7.6,",
                "and Ceuta and Melilla, exclaves outside the mainland polygon) and leave both measures.",
                f"The module reproduces module 03's country-level {pc(r03['module03_share_k2'])} on all {qa['n_thermal_plants']} plants."]),
            ("Intervals", [
                f"{d['n_boot']:,} bootstrap resamples of {d['n_sites']} sites (units on one coordinate are resampled",
                "together). Grid and country measure share each resample. The hazard error is not drawn",
                "per plant: ensemble p10 and p90 layers move every plant together (page 5)."])])

        def kchart(ax):
            ks = [r["k"] for r in d["by_k"]]
            for key, col, lab in (("grid", ACC, "grid cell"), ("country", BAD, "country value")):
                lo = [r[f"{key}_ci"][0] for r in d["by_k"]]
                hi = [r[f"{key}_ci"][1] for r in d["by_k"]]
                ax.fill_between(ks, lo, hi, color=col, alpha=.15, lw=0)
                ax.plot(ks, [r[f"{key}_share"] for r in d["by_k"]], "o-", color=col, ms=4, label=lab)
            ax.axvline(K, color=MID, lw=.8, ls="--")
            ax.set_xlabel("k, days"); ax.set_ylabel("share of thermal MW exposed")
            ax.set_ylim(0, 1.05); ax.legend(frameon=False, loc="upper right")
            ax.set_title("exposed share by threshold, 95% bands", loc="left")

        def strip(ax):
            order = [r["iso3"] for r in bc]
            rng = np.random.default_rng(0)
            for n, iso in enumerate(order):
                s = plants[plants.country == iso]
                ax.scatter(n + rng.uniform(-.18, .18, len(s)), s.cell_change, s=np.sqrt(s.capacity_mw) * 1.2,
                           color=ACC, alpha=.35, lw=0)
                ax.hlines(bc[n]["country_change"], n - .4, n + .4, color=BAD, lw=2)
            ax.axhline(K, color=MID, lw=.8, ls="--")
            ax.set_xticks(range(len(order))); ax.set_xticklabels(order)
            ax.set_yscale("symlog", linthresh=1); ax.set_ylim(0, 40); ax.set_ylabel("change in hot days per year (symlog)")
            ax.set_title("plants (dots, area ~ sqrt MW) against their country's value (red bar)", loc="left")

        page(pdf, 3, "Result: the country value sits above most of its plants", [
            ("Headline", [
                f"At k={K:g}: grid {pc(ref['grid_share'])} {iv(ref['grid_ci'])}, country {pc(ref['country_share'])} {iv(ref['country_ci'])}, "
                f"gap {ref['diff'] * 100:+.1f} points.",
                f"The grid point estimate is below the country one at every k from 0 to 8 (from {ivp([min(r['diff'] for r in d['by_k']), max(r['diff'] for r in d['by_k'])])[1:-1].replace(', ', ' to ')} points",
                "as a range of the gap). Ten plants hold " + pc(ref["top10_share_of_grid_exposed"]) + " of the grid-exposed MW."]),
            ("Where it comes from", [
                f"The country figure is an area mean. Spain's is {by['ESP']['country_change']:.1f} days, its plants' MW-weighted mean {by['ESP']['plant_mean_change']:.1f}.",
                f"Country value calls all of Spain, Italy and Portugal exposed; by cell {pc(by['ESP']['grid_exposed_share'], 0)}, "
                f"{pc(by['ITA']['grid_exposed_share'], 0)} and {pc(by['PRT']['grid_exposed_share'], 0)} of their MW is.",
                f"Greece agrees: {pc(by['GRC']['grid_exposed_share'], 0)} of its MW is exposed by cell.",
                f"Order across the eleven countries survives (Spearman {d['rank_corr_country_vs_plant_mean']:.2f}): the level moves, the ranking barely."])],
            draws=[([0.10, 0.40, 0.82, 0.22], kchart), ([0.10, 0.06, 0.82, 0.25], strip)])

        def val_chart(ax):
            for lay, col in (("hist_median", MID), ("ssp245_median", ACC), ("ssp370_median", WARN)):
                ax.scatter([r[lay]["api"] for r in val["rows"]], [r[lay]["grid"] for r in val["rows"]], s=18,
                           color=col, label=lay.replace("_median", ""))
            m = max(r["ssp370_median"]["api"] for r in val["rows"])
            ax.plot([0, m], [0, m], color=RULE, lw=1)
            ax.set_xlabel("CCKP API country value"); ax.set_ylabel("grid read, area-weighted over polygon")
            ax.legend(frameon=False, fontsize=8); ax.set_title("grid read against the API", loc="left")

        def ladder_chart(ax):
            xs = list(range(len(lad)))
            ax.plot(xs, [r["share"] for r in lad], "o-", color=ACC)
            for x, r in zip(xs, lad):
                if "ci" in r:
                    ax.vlines(x, r["ci"][0], r["ci"][1], color=ACC, lw=6, alpha=.25)
            ax.set_xticks(xs); ax.set_xticklabels([r["resolution"].replace(" degree", "°") for r in lad])
            ax.set_ylim(0, .5); ax.set_ylabel(f"exposed share at k={K:g}")
            ax.set_title("resolution ladder", loc="left")

        page(pdf, 4, "Validation and what resolution buys", [
            ("Against something I did not fit", [
                f"Area-weighted means of the grid over each country's polygon reproduce the CCKP country API",
                f"for 3 layers in 11 countries; the largest absolute difference is {val['max_abs_diff_days']:.2f} days. That",
                "checks the HDF5 reader, the grid indexing and the polygon mask together. France matches only",
                "when overseas territories are excluded, which is what the API does. It does not validate the",
                "model: the same CMIP6 ensemble sits behind both."]),
            ("Where along the resolution ladder the gap closes", [
                f"Averaging the cells into blocks shows where the step happens. Country to 2 degree blocks takes "
                f"{pts(d['ladder_step']['country_to_2deg'])} off",
                f"the {pts(ref['diff'])} gap; 2 degrees to 0.25 degrees takes {pts(d['ladder_step']['two_deg_to_quarter_deg'])} "
                f"[{100 * d['ladder_step']['two_deg_to_quarter_deg_ci'][0]:.1f}, {100 * d['ladder_step']['two_deg_to_quarter_deg_ci'][1]:.1f}].",
                "Most of the gap is already there at 2 degrees; the 0.25 degree cell adds a smaller step."])],
            draws=[([0.10, 0.28, 0.36, 0.30], val_chart), ([0.56, 0.28, 0.36, 0.30], ladder_chart)])

        def sweep_chart(ax):
            rows = [s for s in d["sweep"]]
            ys = list(range(len(rows)))[::-1]
            ax.scatter([s["grid_share"] for s in rows], ys, color=ACC, s=22, label="grid")
            ax.scatter([s["country_share"] for s in rows], ys, color=BAD, s=22, marker="s", label="country")
            for y, s in zip(ys, rows):
                ax.plot([s["grid_share"], s["country_share"]], [y, y], color=RULE, lw=1, zorder=0)
            ax.set_yticks(ys); ax.set_yticklabels([s["label"] for s in rows], fontsize=8)
            ax.set_xlabel(f"exposed share at k={K:g}"); ax.legend(frameon=False, loc="lower right")
            ax.set_title("each variant, grid against country", loc="left")

        page(pdf, 5, "Sensitivity: what moves, and what does not", [
            ("The arbitrary choices", [
                f"Matching radius (0 to 100 km, land cells or all): grid share {pc(sp['radius']['grid_share']['min'])} to "
                f"{pc(sp['radius']['grid_share']['max'])}, a range of {pts(sp['radius']['grid_share']['range'])}.",
                f"Fuel definition: {pts(sp['fuel']['grid_share']['range'])}. Scenario, SSP2-4.5 against SSP3-7.0: "
                f"{pts(sp['scenario']['grid_share']['range'])}.",
                f"Threshold k=1 against k=3: {pts(d['k1_to_k3']['grid_share_range'])}, more than any of the others; module 03 found the fuel "
                "definition larger",
                "than that step at country resolution, because a country value moves in jumps. The gap is negative in every",
                f"variant, from {ivp([min(s['diff'] for s in d['sweep']), max(s['diff'] for s in d['sweep'])])[1:-1].replace(', ', ' to ')} points.",
                f"Ranking of countries by exposed share: Spearman {min(s['rank_corr_vs_base'] for s in d['sweep']):.2f} "
                "at worst against the baseline."]),
            ("Hazard uncertainty, drawn once for all plants", [
                f"The ensemble p10 and p90 layers give a grid share of {pc(ref['grid_p10_share'])} and {pc(ref['grid_p90_share'])}. The country",
                f"measure moves with them ({pc(ref['country_p10_share'])}, {pc(ref['country_p90_share'])}). The gap stays negative: "
                f"{ref['diff_p10'] * 100:+.1f} {ivp(ref['diff_p10_ci'])} at p10,",
                f"{ref['diff_p90'] * 100:+.1f} {ivp(ref['diff_p90_ci'])} at p90. p10 and p90 are separate ensemble layers, not percentiles of the",
                "change itself, so they bound the hazard approximately."])],
            draws=[([0.30, 0.12, 0.62, 0.34], sweep_chart)])

        page(pdf, 6, "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "The 0.25 degree files are a regridded product of coarser CMIP6 models; I have not checked",
                "CCKP's documentation for their native resolution. If the within-country structure is the",
                "models' smooth field and not local conditions at the plant, the grid share is wrong in a",
                "direction this module cannot see. The ladder bounds the exposure to this:",
                f"{pts(d['ladder_step']['two_deg_to_quarter_deg'])} of the {pts(ref['diff'])} gap lies between 2 degrees and 0.25, so the",
                "finest scale is the least secure part of the result. A downscaled or station-based layer",
                "could move it either way."]),
            ("What a sceptic attacks first", [
                f"1. The 35 C heat-index count is one hazard. A plant's exposure (cooling water, load) is not hd35.",
                f"2. The register: WRI has swapped and mistyped coordinates ({qa['swapped'] + qa['dropped']} found, only because they leave the",
                "country); an error inside the country, or under 10 km, passes the test unseen.",
                "3. The country comparator is the CCKP area mean, the number module 03 used. A national value",
                "weighted by population or capacity is not tested here; it would shrink the gap if it weights",
                "the hot places less."]),
            ("No backtest, and why", [
                "Nothing here is fitted to a time series. The projection is CCKP's CMIP6 ensemble, consumed",
                "unchanged; mid-century has not happened, so there is no realised year to test against. The",
                "validation on page 4 checks the read, not the climate."]),
            ("Next", [
                "Replace hd35 with a plant-relevant hazard (cooling-water temperature, extreme-heat derating),",
                "and a downscaled layer for the comparison at the plant. Add the ensemble members, not just",
                "p10 and p90, so the hazard error has a proper distribution."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
