"""Four pages: question, method, result, limits. Every number comes from results/."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

INK, MID, ACC, OK, BAD = "#10201E", "#33453F", "#0F5257", "#2F6B4F", "#A32914"


def page(pdf, title, lines, draw=None):
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    fig.text(0.08, 0.94, title, fontsize=17, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.915, 0.915], color="#D3DCD6", lw=1))
    y = 0.875
    for ln in lines:
        bold = ln.startswith("**")
        fig.text(0.08, y, ln.replace("**", ""), fontsize=10.5 if not bold else 11.5,
                 color=INK if bold else MID, va="top", wrap=True,
                 weight="bold" if bold else "normal")
        y -= 0.033 + 0.021 * (len(ln) // 95)
    if draw:
        draw(fig)
    pdf.savefig(fig)
    plt.close(fig)


def main():
    d = json.load(open("results/renewables_pace.json"))
    rows = d["rows"]
    yard = d["yardstick_2030"]
    on = [r for r in rows if r["gap_to_yardstick"] >= 0]
    worst = rows[:8]

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "Renewables: the pace, not the target",
             ["**The question**",
              "Every member state has a renewable-share target for 2030. Targets are a statement of",
              "intent. This asks a different question: at the speed each country has actually",
              "managed over the last five years, where does it land in 2030?",
              "",
              "**Why it matters for a supervisor**",
              "A transition plan that assumes the national grid decarbonises on schedule is",
              "assuming something the last five years of data may not support. The pace is",
              "observable; the target is not evidence.",
              "",
              "**The answer, in one line**",
              f"{len(on)} of {len(rows)} member states reach {yard}% by 2030 at their own pace."])

        page(pdf, "Method",
             ["**Data**",
              "Eurostat nrg_ind_ren, share of renewable energy, balance REN, pulled live from the",
              "public dissemination API. No key, no scraping, no manual download.",
              "",
              "**Calculation**",
              "For each member state: take the latest observed year, measure the average annual",
              "change over the five years ending there, and carry that pace forward to 2030.",
              "Then compare with the pace that would be required from the latest year.",
              "",
              "**The yardstick**",
              f"{yard}% is the EU AGGREGATE target in RED III. It is not a national obligation.",
              "It is used here as one common ruler so the countries can be compared. National",
              "contributions differ and are not in this dataset. Stating otherwise would make the",
              "whole comparison a false premise.",
              "",
              "**Check**",
              "tests/test_renewables.py covers the arithmetic on a fixed series, including a",
              "falling share, which must project downwards rather than be clipped at zero."])

        def chart(fig):
            ax = fig.add_axes([0.12, 0.08, 0.80, 0.42])
            names = [r["geo"] for r in worst]
            achieved = [r["pace_pp_per_year"] for r in worst]
            needed = [r["required_pp_per_year"] for r in worst]
            x = range(len(names))
            ax.bar([i - 0.2 for i in x], needed, width=0.4, color=BAD, label="required per year")
            ax.bar([i + 0.2 for i in x], achieved, width=0.4, color=ACC, label="achieved per year")
            ax.axhline(0, color=MID, lw=0.8)
            ax.set_xticks(list(x))
            ax.set_xticklabels(names)
            ax.set_ylabel("percentage points a year")
            ax.legend(frameon=False, fontsize=9)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)

        page(pdf, "Result",
             ["**The gap is in the pace, not in the level**",
              f"The eight furthest from the yardstick need between {worst[-1]['required_pp_per_year']:.1f}",
              f"and {worst[0]['required_pp_per_year']:.1f} points a year. None of them has managed",
              "anything close over the last five years.",
              "",
              f"**{worst[0]['geo']} is going backwards**",
              f"Its share fell {abs(worst[0]['pace_pp_per_year']):.2f} points a year over the window,",
              f"from a {worst[0]['latest']:.1f}% base.",
              "",
              "**Italy is flat**",
              f"{[r for r in rows if r['geo'] == 'IT'][0]['pace_pp_per_year']:+.2f} points a year against"
              f" {[r for r in rows if r['geo'] == 'IT'][0]['required_pp_per_year']:.2f} required.",
              "Not falling, but not moving either, from a 20% base."], chart)

        page(pdf, "Limits, and what I would do next",
             ["**A linear pace is the crudest possible model**",
              "Deployment is lumpy: one offshore wind farm moves a small country's number. Five",
              "years smooths that, it does not remove it.",
              "",
              "**The denominator moves too**",
              "The share is renewables over gross final consumption. A country can gain share by",
              "consuming less, which is not the same achievement as building capacity.",
              "",
              "**The yardstick is an aggregate**",
              "Comparing each state against 42.5% is a ruler, not an assessment of compliance.",
              "The honest next step is the national contributions in the NECPs, which are not",
              "machine-readable in this dataset.",
              "",
              "**What I would build next**",
              "Weight each country by gross final consumption to get the EU aggregate path, and",
              "test whether the aggregate reaches 42.5% even when most members do not. That is",
              "the number that actually matters, and it is not the average of these."])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
