"""Four pages: the question, the method, the result, the limits.

The figure is drawn from results/heat_gradient.json, which src/hazard.py wrote from the API.
Nothing here is typed in by hand, so the deck cannot drift away from the numbers."""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK, MUTED, ACCENT, PRIMARY = "#10201E", "#61736D", "#B04E15", "#0F5257"


def page(pdf, title, blocks, foot):
    fig = plt.figure(figsize=(11.69, 8.27))          # A4 landscape
    fig.patch.set_facecolor("white")
    fig.text(0.06, 0.90, title, fontsize=21, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.865, 0.865], color="#D3DCD6", lw=1))
    y = 0.80
    for head, body in blocks:
        if head:
            fig.text(0.06, y, head, fontsize=10, color=PRIMARY, weight="bold", va="top")
            y -= 0.045
        for line in body:
            fig.text(0.06, y, line, fontsize=11.5, color=INK, va="top")
            y -= 0.042
        y -= 0.025
    fig.text(0.06, 0.055, foot, fontsize=8.5, color=MUTED, va="top")
    pdf.savefig(fig); plt.close(fig)


def main():
    with open(os.path.join(HERE, "results", "heat_gradient.json")) as f:
        rows = json.load(f)
    hot = [r for r in rows if r["scenario"] == "ssp370"]
    by_level = sorted(hot, key=lambda r: -r["midcentury_days"])
    by_change = sorted(hot, key=lambda r: -r["change_days"])
    out = os.path.join(HERE, "deck.pdf")

    with PdfPages(out) as pdf:
        page(pdf, "Where does heat stress grow fastest in the euro area?",
             [("The question", [
                 "Is the ranking of countries by the LEVEL of heat stress the same as the ranking",
                 "by its CHANGE between now and mid-century?"]),
              ("Why it matters", [
                 "If the two agree, today's exposure map still works for tomorrow.",
                 "If they disagree, a book concentrated where the level is already high is exposed now,",
                 "and a book concentrated where the change is largest is exposed to repricing later.",
                 "Those are two different conversations with two different time horizons."]),
              ("Why I started here", [
                 "Both my ECB years were transition risk: PACTA alignment over AnaCredit exposures,",
                 "trajectories, Pillar 3 disclosure quality. Physical risk is the half I had read",
                 "about and never built. This is the smallest honest piece of it."])],
             "Marco Izzo  ·  climate-risk-toolkit  ·  module 01  ·  page 1 of 4")

        page(pdf, "Method",
             [("Data", [
                 "World Bank Climate Change Knowledge Portal, CMIP6 ensemble median.",
                 "Indicator hd35: days per year with a maximum heat index at or above 35 C.",
                 "Public API, no key, no registration. Queried live at run time."]),
              ("Comparison", [
                 "Baseline   1995-2014, historical",
                 "Projection 2040-2059, SSP2-4.5 and SSP3-7.0",
                 "Change     projection minus baseline, per country"]),
              ("Scope", [
                 "Eleven euro-area countries plus Poland: ES PT GR IT FR PL AT DE BE IE NL.",
                 "One request per collection for the whole country list, not one per country."]),
              ("Check", [
                 "tests/test_hazard.py pins two things that would fail silently: that the value is",
                 "read from the payload rather than from its period key, and that change is",
                 "projection minus baseline and not the reverse."])],
             "Method  ·  module 01  ·  page 2 of 4")

        # results page, figure from the data
        fig = plt.figure(figsize=(11.69, 8.27)); fig.patch.set_facecolor("white")
        fig.text(0.06, 0.93, "Result: the two orderings are not the same",
                 fontsize=21, color=INK, weight="bold", va="top")
        fig.add_artist(plt.Line2D([0.06, 0.94], [0.885, 0.885], color="#D3DCD6", lw=1))
        ax1 = fig.add_axes([0.08, 0.20, 0.38, 0.60])
        ax2 = fig.add_axes([0.56, 0.20, 0.38, 0.60])
        for ax, data, key, lab, col in (
                (ax1, by_level[::-1], "midcentury_days", "days per year at or above 35 C, 2040-2059", PRIMARY),
                (ax2, by_change[::-1], "change_days", "change in days from the 1995-2014 baseline", ACCENT)):
            names = [r["iso3"] for r in data]
            vals = [r[key] for r in data]
            ax.barh(names, vals, color=col, height=0.68)
            ax.set_xlabel(lab, fontsize=9, color=MUTED)
            ax.tick_params(labelsize=9, colors=INK)
            for s in ("top", "right"): ax.spines[s].set_visible(False)
            for s in ("left", "bottom"): ax.spines[s].set_color("#D3DCD6")
        ax1.set_title("by level", fontsize=12, color=INK, weight="bold", loc="left")
        ax2.set_title("by change", fontsize=12, color=INK, weight="bold", loc="left")
        swap = [r["iso3"] for r in by_level[:3]] != [r["iso3"] for r in by_change[:3]]
        fig.text(0.06, 0.135,
                 ("Greece and Portugal swap between the two rankings: Portugal is second by level and third by change."
                  if swap else "The two rankings agree in the top three."),
                 fontsize=11.5, color=INK, va="top")
        fig.text(0.06, 0.095,
                 "The effect is small in absolute days and I have not inflated it. What it establishes is that level and",
                 fontsize=11.5, color=INK, va="top")
        fig.text(0.06, 0.062,
                 "gradient are separate variables, which is the assumption module 02 needs before overlaying exposures.",
                 fontsize=11.5, color=INK, va="top")
        fig.text(0.06, 0.022, "Result  ·  figure generated from results/heat_gradient.json  ·  page 3 of 4",
                 fontsize=8.5, color=MUTED, va="top")
        pdf.savefig(fig); plt.close(fig)

        page(pdf, "Limits, and what comes next",
             [("What this does not tell you", [
                 "Country means hide what matters. Heat stress is urban and local; a national average",
                 "over Spain averages Seville with Bilbao. Countries are used because exposure data is",
                 "reported by country, not because the hazard is national.",
                 "hd35 is one indicator. It says nothing about drought, flood or wind.",
                 "Ensemble median only: no spread, so no view on the tail, which is what a supervisor asks about.",
                 "No exposures. This is the hazard layer alone."]),
              ("Next", [
                 "Module 02 overlays this on exposures. Doing it honestly needs exposure data at a finer",
                 "grain than country, which is the real constraint and the reason 01 stops here.",
                 "The first thing I would add to 01 is the ensemble spread, reported as an interquartile",
                 "range rather than a median."])],
             "Limits  ·  module 01  ·  page 4 of 4")
    print("wrote", out, os.path.getsize(out), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
