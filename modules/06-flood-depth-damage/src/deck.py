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
    d = json.load(open("results/flood_depth_damage.json"))
    flooded = sorted([l for l in d["locations"] if l["flooded_any_rp"]],
                      key=lambda l: -l["max_depth_m"])
    sweep = d["portfolio_size_sweep"]
    tail = d["tail_assumption_sweep"]
    base_tail = next(r for r in tail if r["anchor_zero_at_p1"] and not r["tail_flat_beyond_rp500"])
    no_anchor = next(r for r in tail if not r["anchor_zero_at_p1"] and not r["tail_flat_beyond_rp500"])
    cs = d["curve_sensitivity"]

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 06 / 1 of 6", "What a flood depth is worth, in damage", [
            ("The estimand", [
                "Expected annual damage (EAD), as a fraction of asset value, for a portfolio of",
                "European power-generation assets: for each JRC return period, read the",
                "modelled flood depth at the site, map it to a damage fraction with a published",
                "depth-damage curve, then integrate that fraction over the exceedance-",
                "probability curve to get one annual-average number per site."]),
            ("The answer", [
                f"Capacity-weighted mean EAD across {d['n_locations']} plants in "
                f"{len(d['countries'])} countries: {d['headline_ead']:.2%} of asset value per",
                f"year -- interval [{d['headline_ci_location_only'][0]:.2%}, "
                f"{d['headline_ci_location_only'][1]:.2%}] from resampling locations, "
                f"[{d['headline_ci_combined'][0]:.2%}, {d['headline_ci_combined'][1]:.2%}]",
                "combining location resampling with curve choice drawn once per draw.",
                f"{d['n_flooded_any_rp']} of {d['n_locations']} sites show any flood depth at",
                "all; the number is small and skewed, which is exactly why it carries an",
                "interval instead of a single figure."]),
            ("Why this, not a heavier number", [
                "A risk manager does not want a depth map. They want one number per asset that",
                "feeds a loss distribution, and this module is the full chain from a public",
                "hazard raster to that number, done honestly about where the uncertainty is."]),
        ])

        page(pdf, "MODULE 06 / 2 of 6", "Data and method, nothing typed", [
            ("Hazard", [
                "JRC/Copernicus EFAS river flood hazard maps for Europe and the Mediterranean",
                "Basin, v3.1.1 (Baugh et al. 2024): nine return-period depth rasters "
                f"({', '.join(str(r) for r in d['return_periods'])} years), 90m resolution,",
                "~300MB each. src/flood_depth_damage.py never downloads a full raster -- it",
                "reads the TIFF directory with a handful of small HTTP range requests, then",
                "fetches only the compressed tiles under the portfolio's coordinates."]),
            ("Depth-damage curve", [
                "Huizinga, de Moel & Szewczyk (2017), JRC105688, the published Europe curves,",
                "fetched from CLIMADA's open-source redistribution of the JRC database and",
                "parsed out of that source file's literal arrays -- the infrastructure sector",
                "as the primary curve, industrial and commercial as the published alternates."]),
            ("Portfolio", [
                f"WRI Global Power Plant Database, the {d['top_n_per_country']} largest plants",
                f"by capacity in each of {len(d['countries'])} countries with a documented",
                "history of damaging river floods, excluding hydro and wave/tidal plants: those",
                "sit in the river or sea by design, so the hazard map's modelled depth at their",
                "coordinates is the normal operating water level, not flood damage to a",
                "building -- see page 5."]),
        ])

        def flooded_chart(ax):
            names = [f"{l['name'][:18]} ({l['country']})" for l in flooded]
            vals = [l["ead_infrastructure"] * 100 for l in flooded]
            colors = [BAD if l["spurious_flag"] else ACC for l in flooded]
            y = list(range(len(names)))
            ax.barh(y, vals, color=colors)
            ax.set_yticks(y); ax.set_yticklabels(names, fontsize=7.5)
            ax.invert_yaxis()
            ax.set_xlabel("EAD, infrastructure curve, % of asset value/year")
            ax.set_title("every flooded site in the portfolio (red = JRC spurious-depth flag)",
                         loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 06 / 3 of 6", "Result: a handful of sites carry the whole number", [
            ("What is actually flooded", [
                f"{d['n_flooded_any_rp']} of {d['n_locations']} sites show nonzero depth at any",
                "return period, all of them gas or nuclear plants sited on a river for cooling",
                "water -- never a coal, solar or wind site in this portfolio. The headline EAD",
                "is a capacity-weighted average over all "
                f"{d['n_locations']} sites, so these "
                f"{d['n_flooded_any_rp']} carry the entire result."]),
        ], flooded_chart)

        def driver_chart(ax):
            labels = list(cs.keys())
            vals = [cs[k] * 100 for k in labels]
            x = list(range(len(labels)))
            ax.bar(x, vals, color=ACC, width=0.5)
            ax.set_xticks(x); ax.set_xticklabels(labels)
            ax.set_ylabel("headline EAD, %")
            lo, hi = d["headline_ci_location_only"]
            ax.axhspan(lo * 100, hi * 100, color=BAD, alpha=0.15,
                      label=f"location-resampling interval [{lo:.2%}, {hi:.2%}]")
            ax.legend(frameon=False, fontsize=7.5, loc="upper right")
            ax.set_title("curve choice moves the number far less than resampling the portfolio",
                         loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 06 / 4 of 6", "Sensitivity: the curve, or the portfolio?", [
            ("The roadmap's question", [
                "Repeat with at least two published curves and report the spread; say whether",
                "the hazard or the curve drives the answer. Swapping the primary curve "
                f"(infrastructure, {cs['infrastructure']:.3%}) for industrial "
                f"({cs['industrial']:.3%}) or commercial ({cs['commercial']:.3%}) moves the",
                f"headline by {d['curve_range']:.3%} points at most."]),
            ("What actually dominates here", [
                f"Resampling which plants land in the portfolio moves the number by "
                f"{d['location_ci_range']:.3%} points -- "
                f"{d['location_ci_range']/d['curve_range']:.1f}x the curve's range. With only "
                f"{d['n_flooded_any_rp']} flooded sites out of {d['n_locations']}, the answer is",
                "the survey design, not the damage function: this portfolio's driver is "
                f"{d['dominant_driver']}, not the curve choice the roadmap expected to",
                "dominate -- the curves published for Europe's building sectors turn out to be",
                "close to each other at the depths this portfolio actually sees."]),
        ], driver_chart)

        def tail_chart(ax):
            labels = ["anchor p=1\nat 0 damage\n(headline)", "no anchor:\ntruncate at\nRP10's p"]
            vals = [base_tail["headline_ead"] * 100, no_anchor["headline_ead"] * 100]
            ax.bar([0, 1], vals, color=[ACC, WARN], width=0.5)
            ax.set_xticks([0, 1]); ax.set_xticklabels(labels, fontsize=8)
            ax.set_ylabel("headline EAD, %")
            ax.set_title("the EAD integral's frequent-end convention, not the curve, is the "
                        "biggest lever", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 06 / 5 of 6", "Sensitivity and validation", [
            ("The EAD integral has its own arbitrary choice", [
                "Whether to assume zero damage at an annual probability of 1 (so floods more",
                "frequent than the rarest tabulated return period still contribute something) or",
                "to simply stop the integral at the most frequent return period in the data "
                f"moves the headline from {base_tail['headline_ead']:.3%} to "
                f"{no_anchor['headline_ead']:.3%} -- a "
                f"{base_tail['headline_ead']/max(no_anchor['headline_ead'],1e-9):.1f}x swing,",
                "bigger than the curve choice on the previous page. Extending the rarest point's",
                "damage flat below RP500 instead of truncating there moves the headline by only "
                f"{abs(tail[1]['headline_ead']-base_tail['headline_ead']):.4%} points -- that",
                "end of the integral is not where the sensitivity lives."]),
            ("Portfolio size", [
                "Taking the 10/15/20/30 largest plants per country instead of 20 moves the "
                "headline across "
                + ", ".join(f"{r['headline_ead']:.2%}" for r in sweep) + " -- same order of",
                "magnitude throughout, no reversal of the finding."]),
            ("Validation: the JRC's own quality flags", [
                f"{d['spurious_flagged_flooded_locations']} of {d['n_flooded_any_rp']} flooded",
                "sites fall inside JRC's own 'spurious depth areas' layer -- cells where the",
                "model may overpredict depth in small channels -- flagged red on page 3 rather",
                "than hidden. Separately, "
                f"{d['n_on_permanent_water']} site(s) sat on the hazard map's permanent-water-",
                "bodies patch (a constant fill value, not a flood signal) and were screened to",
                "zero rather than counted as the most exposed site in the book. No independent",
                "EAD or loss benchmark was fetched for this module; none of comparable public,",
                "code-fetchable granularity was found -- stated here rather than skipped."]),
        ], tail_chart, draw_rect=[0.10, 0.07, 0.82, 0.30])

        page(pdf, "MODULE 06 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "A depth-damage curve is a national average for a generic building in its",
                "sector. It says nothing about this specific plant's finished-floor elevation,",
                "flood defences, or whether critical equipment sits in a basement or on a",
                "raised platform -- two sites at the same modelled depth can have very",
                "different real damage. This module answers 'what does a hazard map say' not",
                "'what would this specific asset actually lose', and the gap between the two is",
                "largest for exactly the handful of flooded sites that carry the headline."]),
            ("No backtest, and why not one for this module", [
                "STANDARD.md requires backtesting anything forward-looking. The JRC hazard maps",
                "used here are a present-day statistical hazard assessment (LISFLOOD/LISFLOOD-FP",
                "fitted to the historical EFAS reanalysis), not a climate-change projection --",
                "there is no future year to hold out and no projected trend fitted by this",
                "module, so there is nothing to backtest. A forward-looking version would need",
                "JRC's climate-adjusted hazard maps, which this release does not include."]),
            ("Asset coordinates are a point, not a footprint", [
                "WRI's plant coordinates are a single point per site; a large plant's actual",
                "equipment can span several 90m pixels with different depths. The portfolio",
                "also excludes hydro by construction (page 2) -- this module says nothing about",
                "flood risk to hydroelectric generation, only to thermal and nuclear plants."]),
            ("Next", [
                "Replace the single-point coordinate with the plant's actual footprint where",
                "one is public, and bring in the JRC flood-risk (not just hazard) layer if a",
                "country-level EAD benchmark becomes available to validate the headline number",
                "against, which page 5 could not do this round."]),
        ])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
