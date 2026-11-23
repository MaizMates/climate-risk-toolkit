"""Six pages. Every number is read from results/, none is typed here. Claims that compare numbers are
asserted before they are written."""
import json
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
COL = {"last year": WARN, "share of year": ACC, "regression": BAD}
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})


def page(pdf, kicker, title, blocks, draw=None):
    fig = plt.figure(figsize=(8.27, 11.69)); fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, kicker, fontsize=8, color=ACC, va="top", fontfamily="monospace")
    fig.text(0.08, 0.932, title, fontsize=16.5, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.908, 0.908], color=RULE, lw=1))
    y = 0.878
    for head, body in blocks:
        if head:
            fig.text(0.08, y, head, fontsize=10, color=INK, weight="bold", va="top"); y -= 0.022
        for line in body:
            ind = line[:len(line) - len(line.lstrip())]
            for part in textwrap.wrap(line, 90, subsequent_indent=ind + "  ", break_long_words=False):
                fig.text(0.08, y, part, fontsize=9.3, color=MID, va="top"); y -= 0.0185
        y -= 0.012
    if draw:
        draw(fig)
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def pc(x, d=1):
    return f"{100 * x:.{d}f}%"


def mt(x, d=0):
    return f"{x:,.{d}f}"


def main():
    R = lambda f: os.path.join(ROOT, "results", f)
    o = json.load(open(R("nowcast.json")))
    cur = pd.read_csv(R("nowcast_current.csv"))
    bt = pd.read_csv(R("backtest.csv"))
    rb = pd.read_csv(R("rmse_boot.csv"))
    rr = pd.read_csv(R("rmse_ratio_boot.csv"))
    sel = pd.read_csv(R("selection.csv"))
    cov = pd.read_csv(R("loo_coverage.csv"))
    sw = pd.read_csv(R("sweep.csv"))
    sh = pd.read_csv(R("shares.csv"))
    ms = pd.read_csv(R("monthly_series.csv"))
    val = json.load(open(R("validation.json")))
    log = json.load(open(os.path.join(ROOT, "data", "fetch_log.json")))
    cy, ly = o["current_year"], o["last_year_actual"]
    HZ = [3, 6, 9, 10]
    C = lambda k, m: cur[(cur.method == k) & (cur.horizon == m)].iloc[0]
    RM = lambda k, m: rb[(rb.method == k) & (rb.horizon == m)].iloc[0]
    H = C("share of year", 9)

    # comparative claims, checked before they are written
    for m in HZ:
        assert RM("share of year", m).rmse < RM("regression", m).rmse < RM("last year", m).rmse, m
    for k in ("share of year", "regression"):
        r_ = [RM(k, m).rmse for m in HZ]
        assert r_ == sorted(r_, reverse=True), "error does not fall with horizon"
    sep = lambda a, b: [m for m in HZ if rr[(rr.a == a) & (rr.b == b) & (rr.horizon == m)].iloc[0].hi < 1]
    rr_ab = rr[(rr.a == "regression") & (rr.b == "share of year")].set_index("horizon")
    reg_worse_sep = [m for m in HZ if rr_ab.loc[m, "lo"] > 1]
    assert reg_worse_sep == [6], reg_worse_sep
    assert sep("share of year", "last year") == HZ
    assert sep("regression", "last year") == [6, 9, 10]
    lyb = bt[bt.method == "last year"].drop_duplicates("year").set_index("year").rel_err
    assert lyb.abs().idxmax() == 2023
    s3 = bt[(bt.method == "share of year") & (bt.horizon == 3)].set_index("year").rel_err
    assert s3.abs().idxmax() == 2025
    assert H.lo < ly < H.hi, "text says the 9-month interval holds last year's value"
    H10 = C("share of year", 10)
    assert H10.lo > ly, "text says the 10-month interval excludes last year's value"
    assert (sel.rmse_selected == sel.rmse_best_in_sample).all()
    cm = cov.groupby("method").covered.mean()
    assert cm["last year"] < cm["share of year"] <= cm["regression"] <= 1
    nb = {m: int((sw[(sw.horizon == m) & (sw.method == "share of year")].set_index("variant").rmse
                  < sw[(sw.horizon == m) & (sw.method == "regression")].set_index("variant").rmse).sum()) for m in HZ}
    nvar = sw.variant.nunique()
    assert nb[9] == nvar and nb[10] == nvar and nb[3] >= nvar - 1
    base_var = sw[sw.group != "target"]
    h9 = base_var[(base_var.horizon == 9) & (base_var.method == "share of year")]
    lo9, hi9 = h9.nowcast.min(), h9.nowcast.max()
    assert lo9 < H.nowcast < hi9 or lo9 <= H.nowcast <= hi9
    assert H.lo <= lo9 and hi9 <= H.hi, "sweep range of the nowcast sits inside the interval"
    fos = sw[(sw.variant == "Fossil emissions only") & (sw.horizon == 9) & (sw.method == "share of year")].iloc[0]
    fos_last = o["actual_by_year"][str(cy - 1)]
    rstab = {m: [sw[(sw.horizon == m) & (sw.method == "share of year") & (sw.group == g)].rmse.agg(["min", "max"]).tolist()
                 for g in ("backtest years",)][0] for m in HZ}
    coef = o["factors_fitted_2018"]; fac = o["factor_mean"]
    bio_bad = coef["Bioenergy"] < 0
    assert bio_bad and coef["Wind"] > 2 * o["factor_range"]["Wind"][1]
    ab = {int(k): v for k, v in o['actual_by_year'].items()}
    assert sh.pivot(index='year', columns='horizon', values='share')[3].idxmax() == 2025
    for m in (3, 6, 9):
        assert C('share of year', m).lo < ly < C('share of year', m).hi
    sh9 = sh[(sh.horizon == 9) & (sh.year <= cy - 1)].share
    growth_tot = H.nowcast / ly - 1
    vf, vt = val["crf_Fossil"], val["crf_Total generation"]
    assert vf["corr_changes"] > 0.9 and val["members_Fossil"]["max_abs_rel_diff"] < 0.01
    rng_all = sw[(sw.horizon == 9) & (sw.method == "share of year") & (sw.group.isin(["history window", "training years", "share rule"]))]

    with PdfPages(os.path.join(ROOT, "deck.pdf")) as pdf:
        def d1(fig):
            ax = fig.add_axes([0.12, 0.12, 0.78, 0.34])
            a = {int(k): v for k, v in o["actual_by_year"].items()}
            ax.plot(list(a), list(a.values()), "-o", color=INK, ms=4, lw=1.4, label="Ember, complete year")
            for i, k in enumerate(("last year", "share of year", "regression")):
                r = C(k, 9); x = cy + (i - 1) * 0.18
                ax.errorbar(x, r.nowcast, yerr=[[r.nowcast - r.lo], [r.hi - r.nowcast]], fmt="o", color=COL[k], ms=5,
                            capsize=3, label=f"{k}, first 9 months")
            ax.axhline(ly, color=RULE, lw=1, zorder=0)
            ax.set_ylabel("MtCO2e"); ax.set_xticks(list(a) + [cy]); ax.set_xticklabels([str(y) for y in a] + [f"{cy}\nnowcast"])
            ax.legend(frameon=False, fontsize=8, loc="upper right"); clean(ax)
            ax.set_title("EU27 power-sector emissions: complete years and the 2026 nowcast (95% intervals)", loc="left")
        page(pdf, "MODULE 18 · POWER EMISSIONS NOWCAST", "Nowcasting this year's EU power emissions", [
            ("Question and estimand", [
                f"The calendar-year EU27 power-sector emissions (MtCO2e, Ember's series for all generation, lifecycle factors) estimated from the first 3, 6 and 9 months of monthly data, and the error of each estimate measured on every complete year from 2018 to {cy - 1}. If I knew it exactly, I could publish the year's number months before the year is complete, with the error it carries."]),
            ("Answer", [
                f"{cy} emissions nowcast from January to September: {mt(H.nowcast)} MtCO2e, 95% interval [{mt(H.lo)}, {mt(H.hi)}] (share-of-year method, backtest RMSE {pc(RM('share of year', 9).rmse)} at this horizon). That is {pc(H.nowcast / ly - 1)} on {cy - 1} ({mt(ly)}), and the interval contains {cy - 1}: nine months cannot separate a rise from no change. With October added the nowcast is {mt(H10.nowcast)} [{mt(H10.lo)}, {mt(H10.hi)}], which excludes {cy - 1}.",
                f"The method's own record: the share-of-year RMSE falls from {pc(RM('share of year', 3).rmse)} at 3 months to {pc(RM('share of year', 6).rmse)} at 6 and {pc(RM('share of year', 9).rmse)} at 9. Repeating last year has RMSE {pc(RM('last year', 9).rmse)} at every horizon, and its worst year, {lyb.abs().idxmax()}, was {pc(abs(lyb.loc[lyb.abs().idxmax()]))} off."]),
        ], d1)

        def d2(fig):
            ax = fig.add_axes([0.12, 0.08, 0.78, 0.3])
            for m, c in zip((3, 6, 9), (WARN, ACC, BAD)):
                g = sh[sh.horizon == m]
                ax.plot(g.year, g.share, "-o", color=c, ms=4, label=f"first {m} months")
                ax.axhline(g.share.mean(), color=c, lw=0.6, ls=":")
            ax.set_ylabel("share of the year's emissions"); clean(ax); ax.legend(frameon=False, fontsize=8)
            ax.set_title("What the share-of-year method assumes: the share each horizon covers (dotted: mean)", loc="left")
        page(pdf, "METHOD", "Three benchmarks, each seeing only month m", [
            ("Data", [
                f"Ember's monthly electricity data (CC BY 4.0), the Area 'EU' aggregate of the 27 member states, source 'Total generation' and its sources, generation in TWh and emissions in MtCO2e, January 2016 to {cy}-10. Fetched by code on {log['accessed']} from {log['ember']['endpoint']}, no filter ({log['ember']['rows']:,} rows). Complete years: 2016 to {cy - 1}. Validation only: Eurostat env_air_gge, EU27, GHG, CRF 1.A.1.a, annual, updated {log['eurostat']['updated'][:10]}."]),
            ("Methods", [
                "1. Last year: the previous calendar year's total.",
                "2. Share of year: emissions of months 1 to m divided by the mean share that months 1 to m took in all earlier years.",
                f"3. Regression: months 1 to m as observed, plus months m+1 to 12 predicted as the sum over nine sources of b x generation. b is fitted by least squares, no intercept, on the months of earlier years. A source's generation in a remaining month is last year's value for that month times this year's year-to-date over last year's.",
                "Backtest: for each year y from 2018 and each m, only complete years before y and months 1 to m of y enter. History is the latest Ember vintage, so revisions are not replayed (limits, page 6)."]),
            ("Interval", [
                f"For a method and horizon, the {len(o['backtest_years'])} backtest errors e = nowcast / actual - 1 give a root mean square r (it includes bias). The 95% interval for the realised value is N / (1 + q) to N / (1 - q), q = t(0.975, {len(o['backtest_years'])} df) x r. It comes from the backtest, not from the in-sample fit. The RMSE intervals resample the {len(o['backtest_years'])} backtest years, one draw of years shared by every method and horizon ({o['boot']['n']:,} draws, seed {o['boot']['seed']})."]),
        ], d2)

        def d3(fig):
            yrs = o["backtest_years"]
            for i, m in enumerate((3, 6, 9)):
                ax = fig.add_axes([0.1 + i * 0.31, 0.2, 0.26, 0.2])
                for j, k in enumerate(("last year", "share of year", "regression")):
                    e = bt[(bt.method == k) & (bt.horizon == m)].set_index("year").rel_err.reindex(yrs)
                    ax.plot(yrs, 100 * e.values, "o-", color=COL[k], ms=3.5, lw=0.9, label=k)
                ax.axhline(0, color=MID, lw=0.6); clean(ax); ax.set_title(f"first {m} months", loc="left")
                ax.set_xticks(yrs[::2]); ax.tick_params(labelsize=7)
                if i == 0:
                    ax.set_ylabel("error, % of actual"); ax.legend(frameon=False, fontsize=7)
            ax = fig.add_axes([0.1, 0.045, 0.8, 0.09]); ax.axis("off")
            rows = [[k] + [f"{pc(RM(k, m).rmse)} [{pc(RM(k, m).lo)}, {pc(RM(k, m).hi)}]" for m in (3, 6, 9)]
                    for k in ("last year", "share of year", "regression")]
            t = ax.table(cellText=rows, colLabels=["RMSE, 95% interval", "3 months", "6 months", "9 months"], loc="center", cellLoc="left")
            t.auto_set_font_size(False); t.set_fontsize(8); t.scale(1, 1.3)
        page(pdf, "BACKTEST", f"Pseudo out-of-sample, {o['backtest_years'][0]} to {o['backtest_years'][-1]}", [
            ("Result", [
                f"At every horizon the order of the point RMSE is share of year, then regression, then last year. The share-of-year RMSE is {pc(RM('share of year', 3).rmse)}, {pc(RM('share of year', 6).rmse)} and {pc(RM('share of year', 9).rmse)} at 3, 6 and 9 months. Regression: {pc(RM('regression', 3).rmse)}, {pc(RM('regression', 6).rmse)}, {pc(RM('regression', 9).rmse)}. Last year: {pc(RM('last year', 9).rmse)}.",
                f"Against last year, the share-of-year RMSE ratio is {rr[(rr.a == 'share of year') & (rr.b == 'last year') & (rr.horizon == 3)].ratio.iloc[0]:.2f} at 3 months (interval [{rr[(rr.a == 'share of year') & (rr.b == 'last year') & (rr.horizon == 3)].lo.iloc[0]:.2f}, {rr[(rr.a == 'share of year') & (rr.b == 'last year') & (rr.horizon == 3)].hi.iloc[0]:.2f}]) and {rr[(rr.a == 'share of year') & (rr.b == 'last year') & (rr.horizon == 9)].ratio.iloc[0]:.2f} at 9 (interval [{rr[(rr.a == 'share of year') & (rr.b == 'last year') & (rr.horizon == 9)].lo.iloc[0]:.2f}, {rr[(rr.a == 'share of year') & (rr.b == 'last year') & (rr.horizon == 9)].hi.iloc[0]:.2f}]); the interval is below 1 at every horizon. The regression is separable from last year at 6, 9 and 10 months, not at 3.",
                f"The regression is not separable from the share rule except at 6 months: its RMSE ratio to the share rule is {rr_ab.loc[3, 'ratio']:.2f} [{rr_ab.loc[3, 'lo']:.2f}, {rr_ab.loc[3, 'hi']:.2f}] at 3, {rr_ab.loc[6, 'ratio']:.2f} [{rr_ab.loc[6, 'lo']:.3f}, {rr_ab.loc[6, 'hi']:.2f}] at 6 and {rr_ab.loc[9, 'ratio']:.2f} [{rr_ab.loc[9, 'lo']:.2f}, {rr_ab.loc[9, 'hi']:.2f}] at 9. Adding a regression on generation by source does not buy accuracy over a seasonal ratio.",
                f"Large errors are single years. Last year's value missed {lyb.abs().idxmax()} by {pc(abs(lyb.loc[lyb.abs().idxmax()]))} (actual emissions that year fell {pc(1 - ab[2023] / ab[2022])} from {mt(ab[2022])} to {mt(ab[2023])}); the share rule at 3 months missed {s3.abs().idxmax()} by {pc(abs(s3.loc[s3.abs().idxmax()]))}, because the first quarter of that year carried the largest share of the year in the data (page 2)."]),
        ], d3)

        def d4(fig):
            ax = fig.add_axes([0.12, 0.1, 0.78, 0.26])
            for i, k in enumerate(("last year", "share of year", "regression")):
                for h, m in enumerate((3, 6, 9, 10)):
                    r = C(k, m); x = h + (i - 1) * 0.22
                    ax.plot([x, x], [r.lo, r.hi], color=COL[k], lw=3, solid_capstyle="butt")
                    ax.plot(x, r.nowcast, "o", color=COL[k], ms=4)
            ax.axhline(ly, color=MID, lw=0.8, ls="--"); ax.text(3.45, ly + 3, f"{cy - 1}", fontsize=8, color=MID, ha="right")
            ax.set_xticks(range(4)); ax.set_xticklabels([f"first {m} months" for m in (3, 6, 9, 10)])
            ax.set_ylabel("MtCO2e"); clean(ax)
            ax.set_title(f"{cy} nowcast and 95% interval by method and horizon", loc="left")
        n_unc = len(cov)
        page(pdf, "INTERVALS", "The interval is the backtest error", [
            ("Does the interval method hold?", [
                f"A leave-one-year-out check builds each backtest year's interval from the other seven years' errors and asks whether it holds the actual. Coverage over {n_unc} cases: last year {pc(cm['last year'], 0)}, share of year {pc(cm['share of year'], 0)}, regression {pc(cm['regression'], 0)}. The misses are last year in 2023 and the share rule at 3 months in 2025. With eight years per cell this is a coarse check: it shows that the interval is not far too narrow, no more."]),
            (f"{cy} nowcast", [
                f"Share of year: {mt(C('share of year', 3).nowcast)} [{mt(C('share of year', 3).lo)}, {mt(C('share of year', 3).hi)}] at 3 months of data, {mt(C('share of year', 6).nowcast)} [{mt(C('share of year', 6).lo)}, {mt(C('share of year', 6).hi)}] at 6, {mt(H.nowcast)} [{mt(H.lo)}, {mt(H.hi)}] at 9, {mt(H10.nowcast)} [{mt(H10.lo)}, {mt(H10.hi)}] at 10. Regression at 9 months: {mt(C('regression', 9).nowcast)} [{mt(C('regression', 9).lo)}, {mt(C('regression', 9).hi)}]. Last year's value, {mt(ly)}, sits inside every share-of-year interval up to 9 months and outside the 10-month one.",
                f"Selection: choosing the method with the lowest RMSE on the other years, then scoring it on the held-out year, gives the same RMSE as the in-sample best at every horizon (the share rule is chosen every time), so the choice of method carries no selection bias here."]),
        ], d4)

        def d5(fig):
            x = sw[(sw.horizon == 9)].copy()
            order = list(dict.fromkeys(x.variant))
            ax = fig.add_axes([0.38, 0.05, 0.52, 0.3])
            for k in ("last year", "share of year", "regression"):
                g = x[x.method == k].set_index("variant").rmse.reindex(order)
                ax.plot(100 * g.values, range(len(order))[::-1], "o", color=COL[k], ms=4, label=k)
            ax.set_yticks(range(len(order))[::-1]); ax.set_yticklabels(order, fontsize=7); ax.set_xlabel("RMSE at 9 months, %")
            clean(ax); ax.legend(frameon=False, fontsize=8)
        mv = sw[(sw.horizon == 9) & (sw.method == "share of year")].set_index("variant")
        page(pdf, "VALIDATION AND SENSITIVITY", "Validation and sensitivity", [
            ("Sensitivity", [
                f"{nvar - 1} variants beyond the base: history window, training years, the share rule, the regression's sources and projection, the series (fossil only) and the backtest years. The share rule has a lower RMSE than the regression in {nb[3]} of {nvar} variants at 3 months, {nb[6]} at 6, {nb[9]} at 9 and {nb[10]} at 10.",
                f"The nowcast at 9 months moves from {mt(lo9)} to {mt(hi9)} across the variants that keep the series (base {mt(H.nowcast)}); the whole range sits inside the base interval [{mt(H.lo)}, {mt(H.hi)}]. The share rule's RMSE at 9 months moves across the backtest-year variants from {pc(rstab[9][0], 2)} to {pc(rstab[9][1], 2)}. Fossil-only emissions give {mt(fos.nowcast)} [{mt(fos.lo)}, {mt(fos.hi)}] at 9 months, {pc(fos.nowcast / fos_last - 1)} on {cy - 1}: a different level, as the series is a different estimand, and growth of {pc(growth_tot)} for the total series.",
                f"The regression's coefficients are not stable. Fitted on 2016 to 2017 (24 months, 9 sources) bioenergy gets {coef['Bioenergy']:.3f} and wind {coef['Wind']:.3f} where Ember's own factors are {fac['Bioenergy']:.3f} and {fac['Wind']:.3f}: the sources move together, so the fit cannot separate them. Ember's emissions are generation times a near-constant factor per source, which the regression has to rediscover."]),
            ("Validation against sources that were not fitted", [
                f"Ember's EU aggregate against the sum of its 27 member series: largest monthly gap {pc(val['members_Fossil']['max_abs_rel_diff'], 2)} (fossil, {val['members_Fossil']['months']} months with all 27 present) and {pc(val['members_Total generation']['max_abs_rel_diff'], 2)} (all generation, {val['members_Total generation']['months']} months).",
                f"Eurostat's inventory line for public electricity and heat (CRF 1.A.1.a), {vf['years'][0]} to {vf['years'][1]}: Ember fossil emissions are {pc(vf['mean_ratio'], 1)} of it on average, and the year-on-year changes correlate at {vf['corr_changes']:.3f} (n = {vf['n_changes']}; same sign in {pc(vf['same_sign'], 0)}; RMS difference in the change {vf['rmse_change_pp']:.1f} points). The inventory includes heat and is built on different rules, so it checks the movement, not the level. It stops at {vf['years'][1]}, so it cannot check a nowcast of {cy}."]),
        ], d5)
        page(pdf, "LIMITS AND NEXT STEPS", "What would break the conclusion", [
            ("The assumption that breaks it", [
                f"That the seasonal profile of 2016 to 2025 is the profile of 2026. The share-of-year method is accurate because the first nine months cover {pc(sh9.min())} to {pc(sh9.max())} of the year in the ten complete years; if a shock lands in the last quarter (a cold December, a gas supply cut, a hydro shortfall), the nowcast is wrong by the size of that shock and the interval, built from eight years that include 2020 and 2022, does not know about it.",
                "A sceptical reviewer would attack first the number of backtest years: eight, of which 2018 has only two years of history and 2020 and 2022 are not ordinary years. The interval is a statement about those eight errors."]),
            ("Other limits", [
                "Vintage. History and target are the latest Ember data. A real nowcaster sees recent months before revision, and I did not check how Ember treats its latest months. The backtest therefore understates the error a real-time user faces, by an amount this module cannot measure from one extraction.",
                f"Series definition. Ember's emissions apply fixed lifecycle factors by source; this is not the ETS or the inventory number, and a regression on generation recovers Ember's factors rather than physical ones. Validation against the inventory covers 2016 to {vf['years'][1]} only.",
                "Selection. The share rule won the backtest at every horizon but not by an interval that excludes the regression at 3, 9 and 10 months; I report the regression because the roadmap fixed it in advance, and its benefit is not established.",
                "Population. The intervals are about one series, the EU27 total; no claim is made for any member state."]),
            ("What I would build next", [
                "A real-time version that archives Ember's file every month, so that the backtest uses the vintage a forecaster would have had. A member-state nowcast with the same backtest. A test of weather as a predictor of the remaining months (module 16 gives the load side)."]),
        ])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
