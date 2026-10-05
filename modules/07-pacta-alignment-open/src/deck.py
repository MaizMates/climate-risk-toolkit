"""Six pages. Every number is read from results/, none is typed here."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.join(HERE, ".."))

INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})


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
            fig.text(0.08, y, line, fontsize=9.3, color=MID, va="top"); y -= 0.0185
        y -= 0.012
    for draw, rect in zip(draws, rects):
        draw(fig.add_axes(rect))
    pdf.savefig(fig); plt.close(fig)


def pct(x, signed=False):
    return f"{x:+.1%}" if signed else f"{x:.1%}"


def main():
    d = json.load(open("results/pacta_alignment.json"))
    h = d["headline"]
    cfg = h["config"]
    bt = {r["tech"]: r for r in h["by_tech"]}
    coal, gas, ren = bt["Coal"], bt["Gas"], bt["Renewables"]
    fossil = h["fossil"]
    cov = d["coverage"]
    val = {r["tech"]: r for r in d["validation_wri_vs_eurostat"]}
    sw = {r["factor"]: r for r in d["sweep_summary"]}
    top = d["sweep_summary"][0]
    grid = d["scenario_grid"]
    gmin, gmax = min(r["coal"] for r in grid), max(r["coal"] for r in grid)
    alloc = d["allocation_rank_agreement"]
    unlisted = sorted(g for g, v in d["listing"].items() if not v["listed"])
    cov_row = next(r for r in d["sweeps"] if r["factor"].startswith("WRI coverage"))
    pace_row = next(r for r in d["sweeps"] if r["factor"].startswith("scenario pace"))
    s1, s2 = d["sweep_summary"][1], d["sweep_summary"][2]
    edf = d["listing"].get("EDF", {})
    mw = lambda x: f"{x:,.0f}"

    with PdfPages("deck.pdf") as pdf:
        page(pdf, "MODULE 07 / 1 of 6", "The coal that has to go, by 2030", [
            ("The question", [
                "You say you built an alignment methodology. Here it is on public inputs: how far",
                "does the fleet of listed European power utilities sit from an NGFS pathway?"]),
            ("The estimand", [
                "For a set of listed power utilities, the production-weighted gap between the",
                f"capacity held in a technology in {2020} and the PACTA market-share target for it",
                f"in {cfg['horizon']}, as a share of the set's total capacity. Positive: more than the target.",
                "Capacity is the production metric, as in PACTA's power sector."]),
            ("The answer", [
                f"{h['n_companies']} listed groups, {mw(h['total_mw'])} MW. Under NGFS Net Zero 2050 (REMIND, EU28) the set",
                f"holds {pct(coal['held_share'])} of its capacity in coal against a {cfg['horizon']} target of {pct(coal['target_share'])}:",
                f"a coal gap of {pct(coal['gap'], True)} [{pct(coal['ci_lo'], True)}, {pct(coal['ci_hi'], True)}] of the set's capacity.",
                f"Coal, gas and oil together: {pct(fossil['gap'], True)} [{pct(fossil['ci_lo'], True)}, {pct(fossil['ci_hi'], True)}].",
                "The interval resamples the utilities, with the scenario held fixed."]),
            ("Read this first", [
                "The gap is between the fleet as it stood in 2020 and the target. It is not a gap",
                "between the companies' plans and the target: the public asset register carries no",
                "retirement or build-out plans, so none enters. That makes it a measure of the",
                "change required, and it overstates misalignment wherever a utility has announced",
                "closures or a pipeline."])])

        page(pdf, "MODULE 07 / 2 of 6", "Method and inputs", [
            ("Data, all fetched by src/pacta_alignment.py on each run", [
                "Plants and owners: WRI Global Power Plant Database, raw.githubusercontent.com.",
                f"{cov['n_plants']:,} plants in the EU27 and UK commissioned by 2020 or with no year, {mw(cov['plant_mw'])} MW.",
                "Scenario: NGFS Phase 5, IIASA Scenario Explorer, anonymous API, Capacity|Electricity.",
                "Three IAMs (REMIND, GCAM, MESSAGE), each on its own Europe region.",
                "Listed status: Wikidata, a stock-exchange statement with no end date.",
                "Validation: Eurostat nrg_inf_epc, EU27 net electrical capacity by fuel."]),
            ("The target, from r2dii.analysis (RMI)", [
                "Increasing technologies (renewables, hydro, nuclear): the company adds the scenario's",
                "change as a share of the scenario's sector size, times its own sector capacity.",
                "    target = P0_tech + P0_sector x (S_tech(t) - S_tech(0)) / S_sector(0), floored at 0",
                "Decreasing technologies (coal, gas, oil): it follows the scenario's ratio.",
                "    target = P0_tech x S_tech(t) / S_tech(0)"]),
            ("The set", [
                f"WRI names an owner for {mw(cov['owner_known_mw'])} of {mw(cov['plant_mw'])} MW. Owner strings map to {len(d['listing'])} groups by a",
                f"name rule; {h['n_companies']} are listed by Wikidata and above {mw(cfg['min_mw'])} MW.",
                f"Not listed by Wikidata: {', '.join(unlisted)}.",
                f"The set holds {mw(cov['set_mw'])} MW, {cov['set_mw'] / cov['plant_mw']:.0%} of the register.",
                f"Allocation: ownership splits stated percentages; control gives a plant to its first-named owner."])])

        def result_chart(ax):
            techs = [r["tech"] for r in h["by_tech"]][::-1]
            rows = {r["tech"]: r for r in h["by_tech"]}
            for i, t in enumerate(techs):
                r = rows[t]
                ax.hlines(i + 0.17, r["incl_model_ci_lo"], r["incl_model_ci_hi"], color=WARN, lw=5, alpha=.45)
                ax.hlines(i - 0.05, r["ci_lo"], r["ci_hi"], color=ACC, lw=5, alpha=.55)
                ax.plot(r["gap"], i, "o", color=INK, ms=6)
                ax.text(max(r["ci_hi"], r["incl_model_ci_hi"]) + 0.03, i, f"{r['gap']:+.1%}", va="center", fontsize=8, color=INK)
            ax.axvline(0, color=MID, lw=1)
            ax.set_yticks(range(len(techs))); ax.set_yticklabels(techs)
            ax.set_xlim(-1.3, 0.75)
            ax.set_xlabel("held minus target, share of the set's capacity")
            ax.plot([], [], color=ACC, lw=5, alpha=.55, label="95%, resampling utilities, scenario fixed")
            ax.plot([], [], color=WARN, lw=5, alpha=.45, label=f"95%, also drawing one of {h['n_models_drawn']} IAMs per replicate")
            ax.legend(frameon=False, fontsize=7.5, loc="center left")
            ax.set_title(f"gap in {cfg['horizon']} by technology, {cfg['scenario']} (REMIND)", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 07 / 3 of 6", "Result: the scenario sets the size, the fleet sets the mix", [
            ("What the chart shows", [
                f"Coal {pct(coal['gap'], True)}, gas {pct(gas['gap'], True)}, oil {pct(bt['Oil']['gap'], True)}. Renewables {pct(ren['gap'], True)}: the target is",
                f"{pct(ren['target_share'])} of today's capacity against {pct(ren['held_share'])} held, because the scenario's EU",
                f"renewable capacity changes by {ren['scenario_change_pct']:+.0f}% to {cfg['horizon']}."]),
            ("Why the renewables interval has no width", [
                "Under the market-share approach every company is asked to add the same fraction of its",
                "sector. Summed over any set of companies, the build-out gap is minus the scenario's",
                "change over sector size, whoever is in the set. Company data cannot move it. Only the",
                "decreasing technologies depend on the companies: their gap is the held share times",
                f"(1 - scenario ratio). The wider interval draws the scenario model once per replicate."]),
            ("Who", [
                f"The two largest groups hold {pct(h['largest_two_share_of_set'])} of the set's MW. Dropping any one group moves",
                f"the coal gap between {pct(min(r['coal'] for r in h['leave_one_out']))} and {pct(max(r['coal'] for r in h['leave_one_out']))} (headline {pct(coal['gap'])})."])],
            [result_chart], [[0.17, 0.18, 0.72, 0.32]])

        def val_chart(ax):
            ts = [t for t in val]
            ax.bar(range(len(ts)), [val[t]["ratio"] for t in ts],
                   color=[BAD if abs(val[t]["ratio"] - 1) > .3 else (WARN if abs(val[t]["ratio"] - 1) > .1 else OK) for t in ts])
            ax.axhline(1, color=MID, lw=1)
            ax.set_xticks(range(len(ts))); ax.set_xticklabels(ts, fontsize=8)
            ax.set_ylabel("WRI MW / Eurostat MW"); ax.set_title("register coverage, EU27, 2020", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        def bt_chart(ax):
            techs = list(val)
            for i, t in enumerate(techs):
                rows = [r for r in d["backtest"] if r["tech"] == t]
                sc = [r["scenario_ratio"] for r in rows]
                ax.vlines(i, min(sc), max(sc), color=ACC, lw=7, alpha=.4)
                ax.plot(i, rows[0]["realised_ratio"], "D", color=BAD, ms=6)
            ax.axhline(1, color=MID, lw=.8)
            ax.set_xticks(range(len(techs))); ax.set_xticklabels(techs, fontsize=8)
            ax.set_ylabel("capacity 2024 / 2020"); ax.set_title("backtest: realised (red) vs scenarios (band)", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        bts = [r for r in d["backtest"] if r["model"] == cfg["model"] and r["scenario"] == cfg["scenario"]]
        btc = next(r for r in bts if r["tech"] == "Coal")
        page(pdf, "MODULE 07 / 4 of 6", "Validation and backtest", [
            ("Against a source this module did not fit", [
                "Eurostat's EU27 capacity by fuel checks the register. Coverage by technology, WRI / Eurostat:",
                ", ".join(f"{t} {val[t]['ratio']:.2f}" for t in val) + ".",
                "Renewables are badly under-covered and coal over-covered. The register's latest",
                f"commissioning year is {cov['max_commissioning_year']}; I did not test whether closures by 2020 explain the coal",
                "excess. The set's mix is therefore tilted to fossil.",
                f"Rescaling each technology to Eurostat moves the coal gap from {pct(coal['gap'])} to {pct(cov_row['coal'])}."]),
            ("Backtest of the scenario's first four years", [
                "Nothing here is forecast by me; the forward-looking object is the scenario. I test its",
                "2020-24 path against what Eurostat reports for 2024. Coal capacity fell to "
                f"{btc['realised_ratio']:.2f} of its 2020 level;",
                f"REMIND Net Zero had {btc['scenario_ratio']:.2f}. Scenario errors by technology are in results/. Carrying the",
                f"realised pace forward at a constant annual rate moves the coal gap to {pct(pace_row['coal'])}",
                f"and the renewables gap to {pct(pace_row['renewables'])}. No other source reports listed status, so that",
                "step has no independent check: it is Wikidata against itself."])],
            [val_chart, bt_chart], [[0.10, 0.20, 0.36, 0.26], [0.57, 0.20, 0.36, 0.26]])

        def sens_chart(ax):
            rows = d["sweep_summary"][::-1]
            for i, r in enumerate(rows):
                ax.hlines(i, r["coal_min"], r["coal_max"], color=ACC, lw=7, alpha=.5)
                ax.text(r["coal_max"] + 0.008, i, f"{r['coal_span'] * 100:.1f} pts", va="center", fontsize=8)
            ax.axvspan(coal["ci_lo"], coal["ci_hi"], color=WARN, alpha=.12, label="95% interval from resampling utilities")
            ax.axvline(coal["gap"], color=BAD, lw=1, ls="--", label="headline")
            ax.set_yticks(range(len(rows))); ax.set_yticklabels([r["factor"] for r in rows], fontsize=8)
            ax.set_xlabel("coal gap, share of the set's capacity")
            ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(-0.2, -0.12), ncol=2)
            ax.set_title("range of the coal gap as each choice is varied alone", loc="left")
            for s in ("top", "right"): ax.spines[s].set_visible(False)

        page(pdf, "MODULE 07 / 5 of 6", "Sensitivity: what moves the answer", [
            ("Ranked by the span of the coal gap", [
                f"1. {top['factor']}: {top['coal_span'] * 100:.1f} pts.",
                f"2. {s1['factor']}: {s1['coal_span'] * 100:.1f} pts.",
                f"3. {s2['factor']}: {s2['coal_span'] * 100:.1f} pts.",
                f"The headline sits at {'the top' if abs(gmax - coal['gap']) < 1e-9 else 'a point'} of the scenario grid ({pct(gmin)} to {pct(gmax)} across",
                f"{len(grid)} IAM-scenario pairs). The span of each choice is read off the coal gap alone."]),
            ("The allocation rule, which practitioners argue about", [
                f"It moves nothing here: {alloc['share_of_attributed_mw']:.1%} of attributed MW ({mw(alloc['mw_moved_between_groups'])} MW) changes",
                f"owner, and the rank correlation of company coal shares across the two rules is {alloc['spearman_coal_share']:.3f}.",
                "WRI gives one owner string per plant and few joint ventures, so the rule has little to bite on.",
                "That is a property of the data, not evidence the rule is unimportant."])],
            [sens_chart], [[0.36, 0.18, 0.56, 0.34]])

        page(pdf, "MODULE 07 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "The fleet is held at its 2020 level. If the utilities' announced retirements and",
                "build-out are what a plan-based PACTA run would use, the gaps here shrink, and the",
                "ranking of companies may change. WRI has no plans, so this module cannot size that.",
                f"The coal gap is {pct(coal['gap'])} of the set's capacity only if no coal capacity leaves before {cfg['horizon']}."]),
            ("What a sceptical reviewer attacks first", [
                f"Coverage. The share-of-capacity form depends on the register's mix; rescaling to Eurostat",
                f"gives {pct(cov_row['coal'])}. The MW held in coal does not depend on the other technologies' coverage.",
                "Listing is as of today, owners as of the register's vintage. EDF's Wikidata record:",
                f"{'; '.join(edf.get('ended_exchanges', [])) or 'no stock-exchange statement'}. It is counted as unlisted."]),
            ("Also", [
                "Three IAMs report different Europe regions; MESSAGE's is wider than the EU28 plant set.",
                "Eurostat hydro includes pumped storage; the NGFS hydro definition may not.",
                "Alias rules are my judgement; the strict tier is the sweep that bounds it."]),
            ("Next", [
                "A plan-based run needs company retirement and pipeline data. I found no source of it",
                "that I could fetch by code without a login; I did not exhaust the options. That is the",
                "single input that would turn this fleet gap into the plan gap PACTA measures."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
