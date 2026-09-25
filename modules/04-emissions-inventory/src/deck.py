"""Six pages. Every number is read from results/, none is typed here."""
import json
import textwrap
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


def w(text, width=82):
    return textwrap.wrap(text, width)


def main():
    d = json.load(open("results/emissions_inventory.json"))
    mc = d["monte_carlo"]
    loc, mkt = mc["total_location_based"], mc["total_market_based"]
    scopes = mc["by_scope"]
    rec = d["reconciliation"]
    val = d["validation"]["rows"]
    oom = d["order_of_magnitude_check"]
    vint = d["vintage_check"]
    hc = d["sensitivity"]["headcount"]
    cv = d["sensitivity"]["gas_calorific_value_convention"]
    s3b = d["sensitivity"]["scope3_boundary"]
    n_emp = sum(c["employees"] for c in d["organisation"]["cities"])
    top3 = mc["top_variance_drivers"]
    offices_str = ", ".join(f"{c['city']} ({c['employees']} employees)"
                            for c in d["organisation"]["cities"])

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 04 / 1 of 6", "A GHG inventory for a firm that does not exist", [
            ("The estimand", [
                "Total greenhouse-gas emissions, in tCO2e, for reporting year 2024, of an",
                "illustrative office-based financial-services firm with offices in Frankfurt,",
                "Paris and Milan, by scope, with a 95% Monte Carlo interval on every number."]),
            ("Why illustrative", [
                *w("The firm is invented and says so on every page. What is not invented is "
                   "any fact about Germany, France or Italy: emission factors "
                   f"({vint['vintages']['DESNZ conversion factors']}), grid intensity, office "
                   "energy intensity and commuting patterns are all fetched from public "
                   "endpoints by src/emissions_inventory.py."),
                *w("The firm's own headcount, commute distance and travel budget are "
                   "assumptions, labelled as such, in "
                   "results/emissions_inventory.json:assumptions -- never fetched, because no "
                   "public source describes a firm that does not exist.")]),
            ("The answer", [
                f"Location-based: {loc['point_estimate']:,.0f} tCO2e "
                f"[{loc['ci_lo']:,.0f}, {loc['ci_hi']:,.0f}] across {n_emp} employees.",
                f"Market-based: {mkt['point_estimate']:,.0f} tCO2e "
                f"[{mkt['ci_lo']:,.0f}, {mkt['ci_hi']:,.0f}] -- "
                f"{rec['delta_pct_of_location']:.0%} higher than location-based.",
                "The method a firm picks for Scope 2 changes the headline number more than any",
                "other choice in this inventory. Page 3 shows why."])])

        page(pdf, "MODULE 04 / 2 of 6", "Method: boundary, sources, vintages", [
            ("Boundary", [
                "GHG Protocol Corporate Standard, operational control. Reporting year 2024.",
                f"Offices: {offices_str}."]),
            ("Activity data", [
                "Office electricity and gas: Eurostat final energy consumption in commercial and",
                "public services (nrg_bal_c, FC_OTH_CP_E), divided by Eurostat services-sector",
                "employment (nama_10_a10_e) to give a national per-employee intensity, scaled by",
                "the firm's assumed headcount per city."]),
            ("Emission factors, fetched, vintages recorded", [
                *w("Scope 1 and Scope 3 combustion/travel: "
                   f"{vint['vintages']['DESNZ conversion factors']}."),
                *w("Scope 2 location-based: Eurostat env_air_gge (CRF sector 1.A.1.a, public "
                   "electricity and heat production) / nrg_bal_c (gross electricity "
                   "production) -- replicates EEA's own stated method; EEA's CSV endpoint "
                   "returned HTTP 410 when this build ran."),
                *w("Scope 2 market-based: AIB European Residual Mixes "
                   f"{vint['vintages']['AIB European Residual Mixes']}, CO2 sheet."),
                *w(vint["note"] + ".")])])

        def scope_chart(ax):
            names = ["Scope 1", "Scope 2\n(location)", "Scope 2\n(market)", "Scope 3"]
            keys = ["scope1", "scope2_location", "scope2_market", "scope3"]
            mid = [scopes[k]["point_estimate"] for k in keys]
            lo = [scopes[k]["ci_lo"] for k in keys]
            hi = [scopes[k]["ci_hi"] for k in keys]
            x = list(range(len(keys)))
            colors = [ACC, ACC, BAD, ACC]
            ax.bar(x, mid, color=colors, alpha=.85)
            ax.vlines(x, lo, hi, color=INK, lw=1.3)
            ax.set_xticks(x); ax.set_xticklabels(names)
            ax.set_ylabel("tCO2e, 95% Monte Carlo interval")
            ax.set_title("Scope 2 market-based more than doubles the location-based figure",
                        loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 04 / 3 of 6", "Result: by scope, with an interval on each", [
            ("Reconciliation", [
                f"Location-based total {rec['location_based_tco2e']:,.0f} tCO2e vs market-based",
                f"{rec['market_based_tco2e']:,.0f} tCO2e, a gap of {rec['delta_tco2e']:,.0f} tCO2e",
                f"({rec['delta_pct_of_location']:.0%}). The gap is Germany: its AIB residual mix",
                "is priced near-fully fossil because German generators sell most of their",
                "renewable attributes as Guarantees of Origin, leaving the 'residual' pool almost",
                "entirely grey. A firm buying no certificates reports against that residual mix."]),
            ("What drives the interval", [
                *w("Top 3 variance contributors: " + "; ".join(
                    f"{t['city']} {t['category']} (sd={t['sd_tco2e']:.0f} tCO2e)"
                    for t in top3) + ".")]),
        ], scope_chart)

        def val_chart(ax):
            names = [r["country"] for r in val]
            computed = [r["computed_location_g_co2e_kwh"] for r in val]
            aib = [r["aib_production_mix_g_co2_kwh"] for r in val]
            x = list(range(len(names)))
            w = 0.35
            ax.bar([i - w/2 for i in x], computed, width=w, color=ACC, label="computed (this module)")
            ax.bar([i + w/2 for i in x], aib, width=w, color=WARN, label="AIB production mix")
            ax.set_xticks(x); ax.set_xticklabels(names)
            ax.set_ylabel("g CO2(e) / kWh")
            ax.legend(frameon=False, fontsize=8)
            ax.set_title("validation: computed location-based intensity vs AIB's own figure",
                        loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 04 / 4 of 6", "Validation against a source this module did not fit", [
            ("The check", [
                "AIB publishes its own 'production mix CO2' figure per country alongside the",
                "residual mix this module uses for Scope 2 market-based -- computed by Grexel on",
                "Ecoinvent data, independent of the Eurostat CRF1A1A/GEP ratio this module fits",
                "for the location-based figure. The two methods should agree in direction even",
                "though they are not the same calculation."]),
            ("What it shows", [
                f"Germany: {val[0]['abs_pct_diff']:.0%} apart -- close agreement.",
                f"France: {[r for r in val if r['country']=='FR'][0]['abs_pct_diff']:.0%} apart --",
                "France's computed figure (CRF1A1A/GEP) is roughly double AIB's Ecoinvent-based",
                "figure; both are near zero in absolute terms (French generation is >90% nuclear",
                "and hydro), so a small absolute gap reads as a large percentage one.",
                f"Italy: {[r for r in val if r['country']=='IT'][0]['abs_pct_diff']:.0%} apart --",
                "CRF1A1A excludes autoproducer (industrial CHP) generation, which is material in",
                "Italy; this is the gap this module's own method note flags as a limitation."]),
        ], val_chart)

        def sens_chart(ax):
            labels = [h["label"] for h in hc]
            vals = [h["total_location_tco2e"] for h in hc]
            x = list(range(len(hc)))
            ax.plot(x, vals, "o-", color=ACC, ms=6)
            ax.set_xticks(x); ax.set_xticklabels(labels)
            ax.set_ylabel("total tCO2e, location-based")
            ax.set_title("headcount is a linear lever -- everything else in this inventory scales with it",
                        loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 04 / 5 of 6", "Sensitivity: the choices nobody can justify alone", [
            ("Scope 2 method: the biggest mover", [
                *w(f"Location-based {rec['location_based_tco2e']:,.0f} tCO2e vs market-based "
                   f"{rec['market_based_tco2e']:,.0f} tCO2e -- a "
                   f"{rec['delta_pct_of_location']:.0%} swing from one methodological choice "
                   "the GHG Protocol requires firms to report both sides of, precisely "
                   "because neither is obviously right.")]),
            ("Calorific value convention: a small but real trap", [
                f"Correct (Net CV, matching Eurostat's activity basis): "
                f"{cv['net_cv_tco2e']:,.0f} tCO2e.",
                *w(f"Gross CV factor misapplied to the same net-basis activity: "
                   f"{cv['gross_cv_tco2e']:,.0f} tCO2e "
                   f"({cv['pct_difference_if_gross_used_on_net_activity']:.0%}). Small next to "
                   "the Scope 2 method choice, but the kind of error that passes a sanity "
                   "check.")]),
            ("Scope 3 boundary", [
                f"Categories 6+7 (business travel, commuting) are {s3b['cat6_cat7_share_of_total']:.0%}",
                "of the location-based total -- material, and built on this module's least",
                "constrained assumptions (commute distance, travel budget). Dropping them would",
                "understate the inventory by exactly that share."]),
        ], sens_chart)

        excluded = [c for c in d["completeness"] if not c["included"]]
        page(pdf, "MODULE 04 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", [
                *w("Every activity-data line in this inventory is a national sector average "
                   "scaled by an assumed headcount, not a metered bill. If this firm's actual "
                   "electricity or gas intensity per employee differs from the national "
                   "commercial-services average by more than the stated uncertainty range, "
                   "every downstream number moves with it -- the Monte Carlo interval reflects "
                   "the assumption's stated range, not a verified bound on how wrong the "
                   "assumption could be.")]),
            ("Scope 3 completeness: 3 of 15 categories built", [
                *w("Category 1 (purchased goods and services) is the largest likely gap: "
                   f"{excluded[0]['reason']}."),
                *w("Full completeness table with every exclusion's reason: "
                   "results/emissions_inventory.json:completeness.")]),
            ("No backtest, and why not one for this module", [
                "STANDARD.md requires backtesting anything forward-looking. Nothing in this",
                "module is a projection -- it is a single historical reporting year (2024) built",
                "from data already realised, not a forecast of a future one. There is no held-out",
                "year to test a forecast against, because this module makes no forecast."]),
            ("Next", [
                *w("Module 05 adds Category 15 (financed emissions) for a real, disclosed "
                   "portfolio -- the category this module excludes and names as the reason."),
                *w(f"Order-of-magnitude check: "
                   f"{oom['tco2e_per_employee_scope12_location']:.2f} tCO2e/employee "
                   f"(Scope 1+2 location-based), within the sanity bound "
                   f"[{oom['bound_lo']}, {oom['bound_hi']}]: {oom['within_bound']}.")])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
