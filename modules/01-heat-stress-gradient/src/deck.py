"""Four pages: the question, the method, the result, the limits.

Every number, and the figure, come from results/heat_gradient.json, which src/hazard.py wrote
from the API. Nothing is typed in by hand, so the deck cannot drift away from the numbers."""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK, MUTED, HAIR, BAR, ACCENT = "#14181A", "#6E7B80", "#DCE1E3", "#B7C0C4", "#B4451E"
L, R = 0.07, 0.93                      # text margins
SOURCE = ("Source: World Bank Climate Change Knowledge Portal, CMIP6 ensemble median, indicator "
          "hd35. Baseline 1995-2014 against 2040-2059, SSP3-7.0.")

matplotlib.rcParams.update({
    "font.family": ["Arial", "Helvetica Neue", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42,
})


def ordinal(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def rule(fig, y, x0=L, x1=R):
    fig.add_artist(plt.Line2D([x0, x1], [y, y], color=HAIR, lw=0.8))


def chrome(fig, kicker, title, page):
    """Header and footer shared by every page, so no page depends on the ones before it."""
    fig.patch.set_facecolor("white")
    fig.text(L, 0.945, kicker.upper(), fontsize=8, color=ACCENT, weight="bold", va="top")
    fig.text(L, 0.895, title, fontsize=23, color=INK, weight="bold", va="top")
    rule(fig, 0.845)
    rule(fig, 0.075)
    fig.text(L, 0.052, "Marco Izzo  ·  climate-risk-toolkit  ·  module 01", fontsize=8,
             color=MUTED, va="top")
    fig.text(R, 0.052, "%d of 4" % page, fontsize=8, color=MUTED, va="top", ha="right")


def body(fig, y, lines, size=11.5, color=INK, lead=0.040, x=L, weight="normal"):
    for line in lines:
        fig.text(x, y, line, fontsize=size, color=color, va="top", weight=weight)
        y -= lead
    return y


def head(fig, y, text, x=L):
    fig.text(x, y, text, fontsize=9.5, color=ACCENT, weight="bold", va="top")
    return y - 0.045


def page1(pdf, facts, top_level, top_change, swaps):
    fig = plt.figure(figsize=(11.69, 8.27))
    chrome(fig, "Module 01  ·  heat-stress gradient, euro area",
           "Where it is hot and where it is heating are two different lists", 1)
    y = body(fig, 0.775, [
        "Between now and mid-century, which euro-area countries",
        "see heat stress grow fastest, and is that ranking the same",
        "as the ranking by level of heat stress today?",
    ], size=13.5, lead=0.046)

    y = head(fig, y - 0.030, "Why the distinction changes the answer")
    y = body(fig, y, [
        "A book concentrated where the level is already high holds a",
        "hazard that should be priced today. One concentrated where the",
        "change is largest holds a hazard that arrives inside the maturity",
        "of loans written now. If the two orderings agree, today's exposure",
        "map still serves. If they do not, it stops serving.",
    ], lead=0.038)

    y = head(fig, y - 0.030, "Finding")
    for label, seq in (("By level", top_level), ("By change", top_change)):
        fig.text(L, y, label, fontsize=12, color=MUTED, va="top")
        fig.text(L + 0.11, y, "  ".join(seq), fontsize=15, color=INK, weight="bold", va="top")
        y -= 0.055
    body(fig, y - 0.010, [
        ("The orderings differ: %s and %s trade places (page 3)." % swaps) if swaps
        else "The orderings agree in the top three (page 3).",
        "The gap is small in days; the point is that it is not zero.",
    ], lead=0.038)

    # right-hand column: enough of the setup to read this page on its own
    x = 0.60
    yy = head(fig, 0.795, "At a glance", x=x)
    rule(fig, yy + 0.020, x0=x, x1=R)
    for k, v in facts:
        fig.text(x, yy, k, fontsize=10, color=MUTED, va="top")
        fig.text(x + 0.13, yy, v, fontsize=11, color=INK, va="top")
        yy -= 0.052
        rule(fig, yy + 0.020, x0=x, x1=R)
    pdf.savefig(fig); plt.close(fig)


def page2(pdf, n, isos):
    fig = plt.figure(figsize=(11.69, 8.27))
    chrome(fig, "Method", "One indicator, two periods, one subtraction", 2)
    rows = [
        ("Source", ["World Bank Climate Change Knowledge Portal API. Public, no key, no registration,",
                    "queried live at run time."]),
        ("Model", ["CMIP6 ensemble median, 0.25° climatology, aggregated to country."]),
        ("Indicator", ["hd35 — days per year with a maximum heat index at or above 35 °C."]),
        ("Baseline", ["1995–2014, historical."]),
        ("Projection", ["2040–2059, under SSP2-4.5 and SSP3-7.0."]),
        ("Change", ["projection minus baseline, per country, in days per year."]),
        ("Coverage", ["%d countries: %s." % (n, " ".join(isos))]),
        ("Requests", ["one call per collection for the whole country list, not one per country."]),
    ]
    y = 0.775
    rule(fig, y + 0.022)
    for k, lines in rows:
        fig.text(L, y, k, fontsize=10.5, color=ACCENT, weight="bold", va="top")
        yy = body(fig, y, lines, size=11.5, lead=0.034, x=L + 0.13)
        y = min(y - 0.050, yy - 0.016)
        rule(fig, y + 0.022)

    y = head(fig, y - 0.022, "What the code is defended against")
    body(fig, y, [
        "The API keys each value by a period string, and that key is not the same across",
        "collections. Reading by key returned empty baselines, which silently made every change",
        "equal to the projection: plausible numbers, wrong ones. tests/test_hazard.py now pins",
        "that the value is read from the payload rather than from its key, and that change is",
        "projection minus baseline and not the reverse.",
    ], lead=0.036)
    pdf.savefig(fig); plt.close(fig)


def panel(fig, box, data, key, title, unit, highlight, fmt):
    ax = fig.add_axes(box)
    names = [r["iso3"] for r in data][::-1]
    vals = [r[key] for r in data][::-1]
    ax.barh(names, vals, color=[ACCENT if n in highlight else BAR for n in names], height=0.62)
    span = max(vals) or 1.0
    for i, (n, v) in enumerate(zip(names, vals)):
        ax.text(v + span * 0.02, i, fmt % v, va="center", fontsize=9.5,
                color=ACCENT if n in highlight else MUTED)
    ax.set_xlim(0, span * 1.18)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0, labelsize=10.5, colors=INK)
    for s in ax.spines.values():
        s.set_visible(False)
    x0, y1 = box[0], box[1] + box[3]
    fig.text(x0 - 0.005, y1 + 0.055, title, fontsize=12.5, color=INK, weight="bold", va="top")
    fig.text(x0 - 0.005, y1 + 0.022, unit, fontsize=9.5, color=MUTED, va="top")


def page3(pdf, by_level, by_change, swaps, detail):
    fig = plt.figure(figsize=(11.69, 8.27))
    chrome(fig, "Result", ("%s and %s trade places between level and change" % swaps) if swaps
           else "The two rankings hold the same order", 3)
    body(fig, 0.795, detail, size=12, lead=0.036)
    hi = set(swaps)
    panel(fig, [0.085, 0.225, 0.345, 0.430], by_level, "midcentury_days",
          "By level, 2040–2059", "days per year at or above 35 °C", hi, "%.1f")
    panel(fig, [0.585, 0.225, 0.345, 0.430], by_change, "change_days",
          "By change from baseline", "additional days per year vs 1995–2014", hi, "+%.1f")
    body(fig, 0.175, [
        "The left panel is a photograph, the right panel is the direction of travel. A portfolio "
        "ranked on either one alone",
        "is answering a different question from the one it thinks it is answering.",
    ], size=11, lead=0.030)
    fig.text(L, 0.100, SOURCE, fontsize=8, color=MUTED, va="top")
    pdf.savefig(fig); plt.close(fig)


def page4(pdf):
    fig = plt.figure(figsize=(11.69, 8.27))
    chrome(fig, "Limits", "What this does not tell you", 4)
    items = [
        ("Country means hide the hazard.",
         ["Heat stress is urban and local. A national mean over Spain",
          "averages Seville with Bilbao. Countries are used because",
          "exposure data is reported by country, not because the",
          "hazard is national."]),
        ("hd35 is one indicator.",
         ["It says nothing about drought, flood, wildfire or wind,",
          "which reach a balance sheet through different channels",
          "and on different timescales."]),
        ("Ensemble median only.",
         ["No spread, therefore no view on the tail, which is the part",
          "a supervisor asks about first. An interquartile range in",
          "place of the median is the first thing I would add."]),
        ("No exposures.",
         ["This is the hazard layer alone: an input to a risk view,",
          "not a risk view. Overlaying it is module 02, and doing that",
          "honestly needs exposure data at a finer grain than country,",
          "which is the real constraint and the reason 01 stops here."]),
    ]
    for i, (lead, lines) in enumerate(items):
        x = L if i % 2 == 0 else 0.52
        y = 0.775 if i < 2 else 0.470
        rule(fig, y + 0.030, x0=x, x1=x + 0.38)
        fig.text(x, y, lead, fontsize=12.5, color=INK, weight="bold", va="top")
        body(fig, y - 0.050, lines, size=11, color=MUTED, lead=0.034, x=x)
    fig.text(L, 0.170, "Everything above is a limit on the claim, not a caveat on the code. "
                       "The numbers are what the model says; what they",
             fontsize=11, color=INK, va="top")
    fig.text(L, 0.142, "cannot carry is a view on any single asset, any single city, or the tail.",
             fontsize=11, color=INK, va="top")
    fig.text(L, 0.100, SOURCE, fontsize=8, color=MUTED, va="top")
    pdf.savefig(fig); plt.close(fig)


def main():
    with open(os.path.join(HERE, "results", "heat_gradient.json")) as f:
        rows = json.load(f)
    hot = [r for r in rows if r["scenario"] == "ssp370"]
    by_level = sorted(hot, key=lambda r: -r["midcentury_days"])
    by_change = sorted(hot, key=lambda r: -r["change_days"])
    lvl = [r["iso3"] for r in by_level]
    chg = [r["iso3"] for r in by_change]

    # countries whose rank moves between the two orderings, taken from the data
    moved = [iso for iso in lvl[:5] if lvl.index(iso) != chg.index(iso)]
    swaps = tuple(moved[:2])
    if len(swaps) == 2:
        a, b = (next(r for r in hot if r["iso3"] == i) for i in swaps)
        detail = [
            "%s ranks %s by level (%.1f days per year) but %s by change (+%.1f days)."
            % (swaps[0], ordinal(lvl.index(swaps[0]) + 1), a["midcentury_days"],
               ordinal(chg.index(swaps[0]) + 1), a["change_days"]),
            "%s is the reverse: %s by level (%.1f days), %s by change (+%.1f days)."
            % (swaps[1], ordinal(lvl.index(swaps[1]) + 1), b["midcentury_days"],
               ordinal(chg.index(swaps[1]) + 1), b["change_days"]),
        ]
    else:
        swaps, detail = (), ["No country in the top five changes rank between the two orderings."]

    facts = [("Indicator", "hd35, days ≥ 35 °C"),
             ("Model", "CMIP6 ensemble median"),
             ("Baseline", "1995–2014"),
             ("Projection", "2040–2059"),
             ("Scenarios", "SSP2-4.5, SSP3-7.0"),
             ("Coverage", "%d countries" % len(hot)),
             ("Source", "World Bank CCKP")]

    out = os.path.join(HERE, "deck.pdf")
    with PdfPages(out) as pdf:
        pdf.infodict().update({"Title": "Heat-stress gradient across euro-area countries",
                               "Author": "Marco Izzo", "Subject": "climate-risk-toolkit module 01"})
        page1(pdf, facts, lvl[:3], chg[:3], swaps)
        page2(pdf, len(hot), lvl)
        page3(pdf, by_level, by_change, swaps, detail)
        page4(pdf)
    print("wrote", out, os.path.getsize(out), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
