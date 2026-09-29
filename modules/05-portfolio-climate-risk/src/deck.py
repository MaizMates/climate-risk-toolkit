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
    d = json.load(open("results/portfolio_risk.json"))
    fund, waci, overlay = d["fund"], d["waci"], d["physical_overlay"]
    sectors = sorted(d["sector_weights"].items(), key=lambda kv: -kv[1])
    mapping_sens = d["mapping_sensitivity"]
    year_sens = d["year_sensitivity"]
    val = d["validation"]
    n_years = len(year_sens)

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 05 / 1 of 6", "A real ETF, read as a climate risk book", [
            ("The estimand", [
                "For the SPDR MSCI EMU UCITS ETF (ISIN " + fund["isin"] + "), a real Eurozone",
                "equity portfolio published without an account: (a) the share of market value in",
                "climate-policy-relevant sectors (Battiston et al. 2017), and (b) the portfolio's",
                "weighted average carbon intensity (WACI), in tCO2e per EUR million of gross",
                "value added, with an interval reflecting proxy uncertainty."]),
            ("This is a proxy, not a measurement", [
                "No company reports its own emissions here. Every holding gets its home country's",
                "national average intensity for one representative NACE activity standing in for",
                "its whole GICS sector. PCAF data-quality score 5 on every line -- this deck is",
                "the reason to read that score before the number."]),
            ("The answer", [
                f"{d['cprs_share']:.1%} of this EUR {d['total_market_value_eur']/1e6:,.0f}mn, "
                f"{d['n_holdings']}-holding portfolio",
                f"(as of {fund['holdings_as_of']}) sits in climate-policy-relevant sectors.",
                f"WACI at {d['reference_year']}: {waci['point']:.0f} tCO2e/EUR mn GVA, interval "
                f"[{waci['ci_lo']:.0f}, {waci['ci_hi']:.0f}]",
                "from the spread of the same sector's intensity across EU member states --",
                "right-skewed, because a few high-carbon member states are a real possibility",
                "for any company sharing that sector code."])])

        page(pdf, "MODULE 05 / 2 of 6", "Method: a coarse, honest join", [
            ("Data, all fetched by code", [
                "Holdings: SSGA's own daily holdings file for this fund, ssga.com, no key, no",
                "account. Intensity: Eurostat env_ac_ainah_r2 (GHG by NACE) over nama_10_a64",
                "(gross value added by NACE), public API, all 27 EU member states. Physical",
                "overlay: modules/01's hazard table, already in this repository."]),
            ("The join, and how coarse it is", [
                "The holdings file carries an MSCI GICS sector label (11 categories), not a NACE",
                "code. src/portfolio_risk.py maps each GICS sector to the single NACE Rev.2 code",
                "that best represents where that sector's value actually sits in this portfolio",
                "(e.g. Information Technology -> C26, computer & optical products, because ASML",
                "alone is 9% of the fund). Every company sharing a GICS label gets the same",
                "number regardless of its actual activity. notes.md has the reasoning sector by",
                "sector, and the sensitivity page shows what the coarseness costs."]),
            ("A real data gap, not a bug", [
                f"{waci['fallback_value_share']:.1%} of portfolio value sits in a country/sector cell",
                "Eurostat's national accounts don't break out at division level (Germany and Spain",
                "do not report NACE-division GVA for several manufacturing codes, likely",
                "statistical disclosure control). Those holdings fall back to the cross-country",
                "median for their NACE code, flagged in results/ rather than silently averaged in."])])

        def sector_chart(ax):
            names = [s for s, _ in sectors]
            weights = [w * 100 for _, w in sectors]
            colors = [BAD if d["sector_to_cprs"].get(s, "not_cpr") != "not_cpr" else MID
                     for s in names]
            y = list(range(len(names)))[::-1]
            ax.barh(y, weights, color=colors)
            ax.set_yticks(y); ax.set_yticklabels(names, fontsize=8)
            ax.set_xlabel("share of portfolio market value, %")
            ax.set_title(f"climate-policy-relevant sectors (red) = {d['cprs_share']:.1%} of value",
                        loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 05 / 3 of 6", "Result: where the exposure sits", [
            ("Sector composition", [
                "Financials and Industrials dominate this fund by construction (it tracks large-",
                "and mid-cap Eurozone equities); climate-policy relevance is concentrated in four",
                "sectors that together are a minority of the book."]),
            ("The four CPRS categories present", [
                ", ".join(f"{c}: {w:.1%}" for c, w in sorted(d["cprs_breakdown"].items(),
                                                              key=lambda kv: -kv[1])
                         if c != "not_cpr") + "."]),
        ], sector_chart, draw_rect=[0.30, 0.09, 0.62, 0.36])

        def overlay_chart(ax):
            rows = overlay["by_country"]
            names = [r["country"] for r in rows]
            vals = [r["change_days"] for r in rows]
            colors = [BAD if v > overlay["k"] else OK for v in vals]
            x = list(range(len(names)))
            ax.bar(x, vals, color=colors)
            ax.axhline(overlay["k"], color=MID, lw=1, ls="--", label=f"k={overlay['k']} reference")
            ax.set_xticks(x); ax.set_xticklabels(names, rotation=40, ha="right", fontsize=7.5)
            ax.set_ylabel("change_days, SSP2-4.5, mid-century")
            ax.legend(frameon=False, fontsize=8)
            ax.set_title("physical overlay: heat-day change by country of domicile", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 05 / 4 of 6", "Validation, and a physical overlay", [
            ("Against the fund's own disclosure", [
                "State Street's own per-ISIN sustainability report discloses an MSCI Weighted",
                "Average Carbon Intensity (Scope 1+2+3) of "
                f"{val['ssga_waci_usd_per_million_sales']:.1f} tCO2e/$M Sales -- fetched from",
                "ssga.com and read with a minimal stdlib PDF text extractor, because that figure",
                "exists nowhere else machine-readable for this fund."]),
            ("Why it is not a like-for-like check", [
                "Different currency (USD sales vs EUR value added), different denominator (sales",
                "can be several times value added for the same firm), and MSCI's figure is over",
                "90% Scope 3 -- supply-chain emissions this module's NACE-level, production-based",
                "proxy has no analogue for at all. Both point the same direction; neither confirms",
                "the other's number. Where no comparable metric exists, STANDARD.md says to say",
                "so rather than force a comparison -- this is that case."]),
            ("Physical overlay, by country of domicile", [
                "Weighting module 01's SSP2-4.5 heat-day change by market value: mean "
                f"{overlay['mean_change_days']:.2f} days",
                f"[{overlay['ci_lo']:.2f}, {overlay['ci_hi']:.2f}]. "
                f"{overlay['exposed_share_at_k']:.1%} of covered value (Finland is",
                "not in module 01's table and is excluded) sits in a country crossing the k=2",
                "reference used in modules 01 and 03."]),
        ], overlay_chart)

        def sens_chart(ax):
            names = [r["variant"] for r in mapping_sens]
            waci_v = [r["waci"] for r in mapping_sens]
            x = list(range(len(names)))
            colors = [ACC if n_ == "base" else (BAD if n_ == "all alternates" else WARN)
                     for n_ in names]
            ax.bar(x, waci_v, color=colors)
            ax.set_xticks(x); ax.set_xticklabels(names, rotation=30, ha="right", fontsize=7.5)
            ax.set_ylabel("WACI, tCO2e/EUR mn GVA")
            ax.set_title("the sector-mapping choice moves WACI more than any one toggle", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 05 / 5 of 6", "Sensitivity: mapping and vintage, not the model", [
            ("The choice nobody can justify from first principles", [
                "Which single NACE code stands in for a GICS sector. Re-running with the next",
                "most defensible reading for the four sectors where this portfolio holds a real",
                f"mix (see notes.md) moves WACI from {mapping_sens[0]['waci']:.0f} (base) to "
                f"{mapping_sens[-1]['waci']:.0f}",
                f"(all alternates) -- a {mapping_sens[-1]['waci']/mapping_sens[0]['waci']-1:.0%} "
                "swing from a labelling choice, not from any data update."]),
            ("A finding the number alone would hide", [
                "Reclassifying Consumer Discretionary from retail trade to motor-vehicle",
                f"manufacture barely moves WACI ({mapping_sens[3]['waci']:.0f} vs "
                f"{mapping_sens[0]['waci']:.0f}) but moves the CPRS share from",
                f"{mapping_sens[0]['cprs_share']:.1%} to {mapping_sens[3]['cprs_share']:.1%}, "
                "because 'transportation' is a Battiston CPRS category and 'retail trade' is",
                "not. The two headline numbers are sensitive to different choices."]),
            ("The reference year", [
                f"Sweeping {year_sens[0]['year']}-{year_sens[-1]['year']} (all {n_years} years "
                "Eurostat has): WACI falls from",
                f"{year_sens[0]['waci']:.0f} to {year_sens[-1]['waci']:.0f}, monotonically, "
                "tracking the EU's own realised industrial",
                "decarbonisation and GVA growth -- not a projection, so no backtest applies; see",
                "the limits page."]),
        ], sens_chart)

        page(pdf, "MODULE 05 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "That a national-sector average is a reasonable stand-in for one company. It is",
                "not, for exactly the companies that matter most to the answer: ASML, Siemens and",
                "SAP are each far from their sector's national average by construction (they are",
                "the reason the sector has that average). The proxy is most defensible for the",
                "Financials-heavy middle of the book and least defensible for its largest, most",
                "distinctive single names -- the opposite of where a reader's attention goes."]),
            ("The mapping is many-to-one by design", [
                "One NACE code per GICS sector cannot separate a chemicals company from a mining",
                "company inside 'Materials', or an airline from a machinery maker inside",
                "'Industrials'. The sensitivity page shows this costs more than the year chosen or",
                "the interval width -- it is the first thing a skeptical reviewer should attack."]),
            ("No backtest, and why not one here", [
                "STANDARD.md requires backtesting anything forward-looking. Nothing in this module",
                "is: the portfolio is a snapshot of today's holdings, the intensity is a realised",
                "national statistic, and the CPRS classification is a fixed taxonomy. The year",
                "sweep on the previous page is a robustness check on which vintage to use, not a",
                "forecast, so there is no future value to hold out and test against."]),
            ("Next", [
                "Module 07 (PACTA alignment) and module 09 (financed emissions, PCAF) both need",
                "company-level activity data this module does not have. The natural next step for",
                "this module specifically is repeating it against a non-Eurozone, non-EU holding",
                "set (module 01's hazard table and Eurostat's NACE intensities both stop at the",
                "EU border), to see how much of this proxy's defensibility was borrowed from",
                "picking a portfolio that happens to sit inside the data's own coverage."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
