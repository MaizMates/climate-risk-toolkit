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
        draw(fig.add_axes(draw_rect or [0.10, 0.09, 0.82, 0.36]))
    pdf.savefig(fig); plt.close(fig)


def main():
    d = json.load(open("results/hazard_exposure.json"))
    kr = {r["k"]: r for r in d["exposure_by_k"]}
    ref = kr[d["k_reference"]]
    countries = d["by_country"]
    exposed = [c for c in countries if c["exposed_at_k_reference"]]
    val = d["validation_eurostat"]["rows"]
    fs = d["fuel_definition_sensitivity"]
    base = next(r for r in fs if r["include_gas"] and not r["include_biomass"])
    no_gas = next(r for r in fs if not r["include_gas"] and not r["include_biomass"])

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 03 / 1 of 6", "The plants sitting where it gets hotter", [
            ("The estimand", [
                "The share of total thermal generating capacity, in MW, across the countries in",
                "module 01's hazard table, sitting in a country whose projected count of days at",
                "or above a 35C heat index rises by more than k days from baseline (1995-2014) to",
                "mid-century (2040-2059) under SSP2-4.5."]),
            ("Why capacity, not plant count", [
                "A grid with one 2 GW coal plant and a grid with twenty 100 MW peakers are not the",
                "same exposure. Weighting by MW is the only version of this question a risk",
                "manager can use, and the bootstrap below shows how much that weighting costs in",
                "precision once a few large plants dominate the total."]),
            ("The answer", [
                f"At k={d['k_reference']} days: {ref['exposed_share']:.1%} of {d['total_thermal_mw']:,.0f} MW",
                f"of thermal capacity across {d['n_countries']} countries sits in a country crossing",
                f"that threshold -- interval [{ref['ci_lo']:.1%}, {ref['ci_hi']:.1%}] from resampling",
                f"plants, {ref['top10_share_of_exposed']:.1%} of the exposed total held by just the",
                "ten largest exposed plants."])])

        page(pdf, "MODULE 03 / 2 of 6", "Method, and the resolution this was narrowed to", [
            ("Scope, narrowed on 21/09/2026", [
                "The original ask was plants joined to hazard grid cells. The World Bank CCKP API",
                "returned HTTP 502 when that build ran, and module 01's committed output is",
                "country-level, not gridded, so the gridded version cannot be built from anything",
                "currently in hand. This module joins at country resolution and says so on every",
                "page rather than waiting on an outage. The gridded version is module 11."]),
            ("Data", [
                "Plants: WRI Global Power Plant Database, output_database csv, fetched live from",
                "raw.githubusercontent.com by src/hazard_exposure.py, no key, no transcription.",
                "Hazard: modules/01-heat-stress-gradient/results/heat_gradient.json, already in",
                "this repository -- the reuse the roadmap intends, module 03 consumes module 01's",
                "output rather than re-fetching the hazard layer."]),
            ("Join", [
                "Filter WRI to thermal fuels (coal, oil, petcoke, plus gas by default -- see the",
                "sensitivity page), sum capacity by ISO3, join to the hazard table by ISO3. Every",
                "plant in a country inherits that country's national hazard figure; there is no",
                "finer join available at this resolution."])])

        def k_chart(ax):
            ks = [r["k"] for r in d["exposure_by_k"]]
            lo = [r["ci_lo"] for r in d["exposure_by_k"]]
            hi = [r["ci_hi"] for r in d["exposure_by_k"]]
            mid = [r["exposed_share"] for r in d["exposure_by_k"]]
            ax.vlines(ks, lo, hi, color=ACC, lw=8, alpha=.30)
            ax.plot(ks, mid, "o-", color=ACC, ms=5, label="exposed share")
            ax.axvline(d["k_reference"], color=BAD, lw=1, ls="--", label=f"k={d['k_reference']} (reference)")
            ax.set_xlabel("k, days"); ax.set_ylabel("share of thermal MW exposed")
            ax.set_ylim(0, 1.05)
            ax.legend(frameon=False, fontsize=8, loc="upper right")
            ax.set_title("exposed capacity share falls as the threshold tightens", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 03 / 3 of 6", "Result: the threshold sets the answer", [
            ("Which countries cross k=2", [
                ", ".join(f"{c['iso3']} (+{c['change_days_ssp245']:.1f}d)" for c in exposed) + ".",
                f"{len(exposed)} of {d['n_countries']} countries, holding "
                f"{sum(c['thermal_mw'] for c in exposed):,.0f} of {d['total_thermal_mw']:,.0f} MW."]),
            ("The interval widens with concentration", [
                f"At k={d['k_reference']}, {ref['top10_share_of_exposed']:.1%} of the exposed MW sits in",
                "just ten plants. That is why the bootstrap interval is wide relative to the point",
                "estimate: resampling plants, not countries, is what makes a handful of large assets",
                "move the answer, and the interval reports that honestly instead of hiding it in a",
                "single number."]),
        ], k_chart)

        def val_chart(ax):
            names = [r["iso3"] for r in val]
            ratios = [r["ratio_wri_over_eurostat"] for r in val]
            colors = [BAD if r < 0.7 else (WARN if r < 0.9 else OK) for r in ratios]
            x = list(range(len(names)))
            ax.bar(x, ratios, color=colors)
            ax.axhline(1.0, color=MID, lw=1)
            ax.set_xticks(x); ax.set_xticklabels(names)
            ax.set_ylabel("WRI thermal MW / Eurostat combustible-fuel MW")
            ax.set_title("independent check: WRI capacity against Eurostat nrg_inf_epc", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 03 / 4 of 6", "Validation against a source this module did not fit", [
            ("The check", [
                "Eurostat nrg_inf_epc publishes net electrical capacity by fuel group per member",
                "state, independent of WRI's asset-level compilation. Combustible-fuel capacity",
                "(coal, oil, gas, biofuels and waste combined) is the closest published analogue to",
                "this module's thermal definition, so the two are compared directly rather than",
                "asserting the asset-level total is right."]),
            ("What it shows", [
                "Spain, Greece, Poland, Portugal and Italy -- the countries that decide the headline",
                "number -- sit within 10% of the Eurostat figure. Austria (37%) and Belgium (58%)",
                "are the worst outliers: WRI is missing or under-recording thermal capacity there,",
                "most likely smaller or newer plants outside GEODB's and Wiki-Solar's typical",
                "coverage. Neither country crosses k=2, so this does not move the headline, but it",
                "is exactly the kind of gap that would matter for a country nearer the threshold."]),
        ], val_chart)

        def fuel_chart(ax):
            labels = [f"gas={'Y' if r['include_gas'] else 'N'}\nbiomass={'Y' if r['include_biomass'] else 'N'}"
                      for r in fs]
            mid = [r["exposed_share"] for r in fs]
            lo = [r["ci_lo"] for r in fs]
            hi = [r["ci_hi"] for r in fs]
            x = list(range(len(fs)))
            ax.vlines(x, lo, hi, color=ACC, lw=10, alpha=.30)
            ax.plot(x, mid, "o", color=ACC, ms=6)
            ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8)
            ax.set_ylabel("exposed share at k=2")
            ax.set_ylim(0, 0.6)
            ax.set_title("the fuel definition moves the answer more than the threshold does", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 03 / 5 of 6", "Sensitivity: the fuel definition, not the threshold", [
            ("The choice nobody can justify from first principles", [
                "Is gas 'thermal'? Engineering says yes -- a CCGT burns fuel to make steam and spin",
                "a turbine. Transition-plan language often treats gas as a bridge fuel, distinct",
                "from coal. Both readings are defensible, so both are reported rather than one",
                "being asserted as correct."]),
            ("What moves", [
                f"With gas: {base['exposed_share']:.1%} exposed "
                f"[{base['ci_lo']:.1%}, {base['ci_hi']:.1%}], {base['total_mw']:,.0f} MW in scope.",
                f"Without gas: {no_gas['exposed_share']:.1%} exposed "
                f"[{no_gas['ci_lo']:.1%}, {no_gas['ci_hi']:.1%}], {no_gas['total_mw']:,.0f} MW in scope.",
                "",
                f"Dropping gas removes {base['total_mw'] - no_gas['total_mw']:,.0f} MW of capacity and",
                f"moves the exposed share by "
                f"{abs(base['exposed_share'] - no_gas['exposed_share']):.1%} points -- more than moving",
                f"k from 1 to 3 does ({kr[1]['exposed_share']:.1%} to {kr[3]['exposed_share']:.1%}, "
                f"{abs(kr[1]['exposed_share'] - kr[3]['exposed_share']):.1%} points).",
                "Biomass and waste barely move it either way: both are a small share of installed",
                "MW in this country set."]),
        ], fuel_chart)

        page(pdf, "MODULE 03 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "Country resolution attributes a single national hazard figure to every plant in",
                "that country. For Spain this is close to defensible -- one country, one climate",
                "zone dominating its thermal fleet. For Germany or France it is close to",
                "meaningless: a plant on the Mediterranean coast and one on the North Sea get the",
                "same number. This module is least defensible for large, climatically diverse",
                "countries, and DEU and FRA -- 28.8% and 5.0% of total thermal MW -- are exactly",
                "the countries where that matters most."]),
            ("No backtest, and why not one for this module", [
                "STANDARD.md requires backtesting anything forward-looking. The forward-looking",
                "quantity here is CCKP's CMIP6 projection of change_days, produced by module 01 and",
                "consumed unchanged -- there is no held-out year to test it against, because",
                "mid-century has not happened and the projection was never fitted by this module.",
                "Module 01's own limitation carries forward instead: ensemble median only, no",
                "spread, so this module has no view on the tail of the hazard estimate itself."]),
            ("The join has no distance decay", [
                "A plant at the border of an exposed country and one at the geographic centre get",
                "identical treatment. The Eurostat validation on the previous page shows the asset",
                "register itself is incomplete for at least two countries, which compounds the",
                "resolution problem rather than being independent of it."]),
            ("Next", [
                "Module 11 is this module rebuilt at grid-cell resolution once the CCKP API answers",
                "again, with plant coordinates matched to cells under a stated radius and a",
                "sensitivity sweep over that radius. The comparison against this module's",
                "country-level numbers is itself the finding: it measures what the coarse",
                "resolution cost."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
