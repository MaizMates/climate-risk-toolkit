"""Six pages. Every number is read from results/, none is typed here."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
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
            fig.text(0.08, y, line, fontsize=9.3, color=MID, va="top"); y -= 0.0185
        y -= 0.012
    if draw:
        draw(fig)
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def pc(x, d=1):
    return f"{100 * x:.{d}f}%"


def sl(x, d=1):
    """Slope in capture-rate points per point of share."""
    return f"{100 * x:+.{d}f}"


def iv(r, d=1, f=sl):
    return f"[{f(r[0], d)}, {f(r[1], d)}]"


def main():
    R = lambda f: os.path.join(ROOT, "results", f)
    d = json.load(open(R("capture.json")))
    ann = pd.read_csv(R("annual.csv"))
    bt = pd.read_csv(R("backtest.csv"))
    sw = pd.read_csv(R("sweep.csv"))
    val = pd.read_csv(R("validation.csv"))
    prof = pd.read_csv(R("profile.csv"))
    S, Wd, D = d["slope"]["SOLAR"], d["slope"]["WIND"], d["slope_difference"]
    jk, B, sc, pw, jwv, fa = d["jackknife_years"], d["backtest"], d["scenario"], d["partial_window_test"], d["validation"]["jw"], d["facts"]
    yrs = d["years"]
    a_s = ann[ann.tech == "SOLAR"].set_index("year"); a_w = ann[ann.tech == "WIND"].set_index("year")
    y0, y1 = yrs[0], yrs[-1]
    spread = sw[sw.group != "base"]
    mvs = d["validation"]

    with PdfPages(os.path.join(ROOT, "deck.pdf")) as pdf:
        page(pdf, "MODULE 15 / 1 of 6", "What is a megawatt-hour of solar worth?", [
            ("The estimand", [
                f"The capture rate of solar in the DE-LU bidding zone, by calendar year {y0} to {y1}: the",
                "generation-weighted average day-ahead price solar earns, divided by the baseload average",
                "price. Then the slope of that rate against solar's share of load, with onshore wind as the",
                "comparator."]),
            ("The answer", [
                f"Solar's capture rate fell from {pc(a_s.loc[y0, 'cr'])} in {y0} to {pc(a_s.loc[y1, 'cr'])} in {y1} while its share of load",
                f"rose from {a_s.loc[y0, 'share']:.1f}% to {a_s.loc[y1, 'share']:.1f}%. Onshore wind went from {pc(a_w.loc[y0, 'cr'])} to {pc(a_w.loc[y1, 'cr'])} at a share of",
                f"{a_w.loc[y0, 'share']:.1f}% to {a_w.loc[y1, 'share']:.1f}%.",
                f"Slope for solar: {sl(S['slope'])} capture-rate points per point of share. 95% interval {iv(S['ols_interval'])} across the",
                f"{S['n']} years (least squares, {S['n'] - 2} degrees of freedom); {iv(S['boot_interval'])} if only the weeks of each year are resampled.",
                f"Wind: {sl(Wd['slope'])} {iv(Wd['ols_interval'])}; the interval holds zero."]),
            ("What it does not say", [
                f"The slope is a description of {len(yrs)} years. Used to forecast, it loses to last year's value: backtest",
                f"RMSE {B['SOLAR']['slope_model']['rmse']:.2f} against {B['SOLAR']['last_year']['rmse']:.2f} (capture-rate units). The {sc['share_new']:.0f}% share scenario carries",
                f"a backtest interval of [{sc['backtest_interval'][0]:.2f}, {sc['backtest_interval'][1]:.2f}], which is no information.",
                "Solar's capture rate is falling. How fast it keeps falling is not something this data can fix."])])

        page(pdf, "MODULE 15 / 2 of 6", "Method", [
            ("Data", [
                "Energy-Charts API (Fraunhofer ISE; data from Bundesnetzagentur SMARD.de, CC BY 4.0), fetched",
                "by src/fetch.py month by month: /price (DE-LU day-ahead) and /public_power (Germany, quarter-",
                "hourly Solar, Wind onshore, Load). Complete years only; no quarter-hour is missing in any year.",
                f"2026 is partial (to 31 Oct) and is used once, as a further out-of-sample test."]),
            ("Capture rate", [
                "CR = [sum(g x p) / sum(g)] / mean(p), over every quarter-hour of the calendar year (Berlin time).",
                "Prices are hourly until 30 Sep 2025 and quarter-hourly after; an hourly price is held across its",
                "four quarters, which equals the roadmap's hourly average of generation joined to the hourly",
                f"price. Applying it literally changes 2025 by {fa['hourly_vs_quarter_cr_gap_2025'] * 100:+.2f} points."]),
            ("Intervals", [
                f"Block bootstrap over 7-day blocks, {d['draws']:,} draws, seed {d['seed']}. Weeks are resampled inside each year and",
                "calendar quarter, so the season mix is fixed. One draw of weeks serves solar, wind, baseload and",
                "load at once: the error they share is drawn once. Other years are never resampled.",
                "This measures how much each annual figure depends on which weeks occurred. It does not see the",
                f"scatter of the {S['n']} years around the line, so I also report the least-squares interval ({S['n'] - 2} df)",
                "and a leave-one-year-out check."]),
            ("Backtest", [
                "Slope fitted on years up to t-1 predicts the capture rate of year t at its realised share of load,",
                f"t = {B['SOLAR']['test_years'][0]} to {B['SOLAR']['test_years'][-1]}, against two benchmarks (last year's rate; the mean so far). The share itself is not",
                f"forecast. A fifth test uses January to October {2026} against the same window of earlier years."]),
            ("Sweep", [
                "Negative prices kept or floored; price resolution; the 2022 spike kept or dropped; start year;",
                "functional form; bootstrap block length and stratification."])])

        def fig_result(fig):
            ax = fig.add_axes([0.10, 0.37, 0.82, 0.23])
            for t, tab, c in (("solar", a_s, WARN), ("wind onshore", a_w, ACC)):
                ax.errorbar(tab["share"], tab["cr"], yerr=[tab["cr"] - tab["cr_lo"], tab["cr_hi"] - tab["cr"]],
                            xerr=[tab["share"] - tab["share_lo"], tab["share_hi"] - tab["share"]], fmt="o", color=c, ms=4, lw=.8, label=t)
                for y, r in tab.iterrows():
                    ax.annotate(str(y)[2:], (r["share"], r["cr"]), textcoords="offset points", xytext=(5, 4), fontsize=7, color=c)
                f = d["slope"]["SOLAR" if t == "solar" else "WIND"]
                xs = np.array([tab["share"].min(), tab["share"].max()])
                ax.plot(xs, f["intercept"] + f["slope"] * xs, color=c, lw=1.2)
            ax.set_xlabel("share of load, %"); ax.set_ylabel("capture rate")
            ax.set_title("annual points with 95% week-bootstrap bars, fitted lines", loc="left"); ax.legend(frameon=False, fontsize=8); clean(ax)
            ax2 = fig.add_axes([0.10, 0.07, 0.82, 0.20])
            for y, c, ls in ((y0, ACC, "-"), (y1, WARN, "-")):
                p = prof[prof.year == y]
                ax2.plot(p["hour"], p["price"], color=c, ls=ls, lw=1.4, label=f"price {y}")
            ax2.set_xlabel("hour of day (Berlin time)"); ax2.set_ylabel("mean day-ahead price, EUR/MWh"); clean(ax2)
            ax3 = ax2.twinx()
            for y, c in ((y0, ACC), (y1, WARN)):
                p = prof[prof.year == y]
                ax3.fill_between(p["hour"], p["solar"] / 1000, color=c, alpha=.12, lw=0)
            ax3.set_ylabel("mean solar feed-in, GW (shaded)")
            ax2.legend(frameon=False, fontsize=8, loc="upper left")
            ax2.set_title(f"the midday price dip deepens as solar grows ({y0} against {y1})", loc="left")

        page(pdf, "MODULE 15 / 3 of 6", "Result", [
            ("Annual capture rates", [
                "  ".join(f"{y}: {pc(a_s.loc[y, 'cr'], 0)}" for y in yrs[:4]) + "  (solar)",
                "  ".join(f"{y}: {pc(a_s.loc[y, 'cr'], 0)}" for y in yrs[4:]) + "  (solar)",
                f"Wind runs between {pc(a_w['cr'].min(), 0)} and {pc(a_w['cr'].max(), 0)}. Baseload {y0}: {fa['baseload'][str(y0)]:.0f} EUR/MWh; 2022: {fa['baseload']['2022']:.0f}; {y1}: {fa['baseload'][str(y1)]:.0f}.",
                f"Hours at a negative price: {fa['neg_hours'][str(y0)]:.0f} in {y0}, {fa['neg_hours'][str(y1)]:.0f} in {y1}; {pc(fa['solar_gen_at_neg_price_share'][str(y1)], 0)} of {y1} solar output fell in them."]),
            ("The slope", [
                f"Solar {sl(S['slope'], 2)} points per point of share (bootstrap standard error {abs(S['boot_se']) * 100:.2f}, least-squares {S['se'] * 100:.2f}).",
                f"Leave-one-year-out slopes run from {sl(jk['SOLAR']['range'][0], 2)} to {sl(jk['SOLAR']['range'][1], 2)}: no single year drives the sign.",
                f"Solar minus wind: {sl(D['point'], 2)}; bootstrap {iv(D['boot_interval'], 2)}, leave-one-year-out {iv(jk['difference']['interval'], 2)}.",
                "Both exclude zero: solar's rate falls with its own share and wind's does not.",
                f"Within a year, weekly rate on weekly share (year effects) gives {sl(d['within_year']['slope'], 2)}: a different, short-run relation."])
        ], fig_result)

        def fig_bt(fig):
            ax = fig.add_axes([0.10, 0.36, 0.82, 0.22])
            b = bt[bt.tech == "SOLAR"]
            ax.plot(b["year"], b["actual"], "o-", color=INK, label="actual")
            ax.plot(b["year"], b["slope_model"], "s--", color=WARN, label="slope fitted to earlier years")
            ax.plot(b["year"], b["last_year"], "^:", color=ACC, label="last year's rate")
            ax.plot(b["year"], b["mean_so_far"], "v:", color=OK, label="mean so far")
            ax.set_ylabel("solar capture rate"); ax.set_xticks(list(b["year"])); ax.legend(frameon=False, fontsize=8); clean(ax)
            ax.set_title("each year forecast from earlier years only, at its realised share of load", loc="left")
            ax = fig.add_axes([0.10, 0.07, 0.82, 0.20])
            xs = np.linspace(8, 25, 50)
            ax.plot(xs, S["intercept"] + S["slope"] * xs, color=WARN, lw=1.2, label="linear fit, all years")
            ax.fill_between(xs, S["intercept"] + S["slope"] * xs - 2.776 * B["SOLAR"]["slope_model"]["rmse"],
                            S["intercept"] + S["slope"] * xs + 2.776 * B["SOLAR"]["slope_model"]["rmse"], color=WARN, alpha=.12, label="backtest interval")
            ax.plot(a_s["share"], a_s["cr"], "o", color=INK, ms=4, label="annual")
            ax.plot([pw["SOLAR"]["share_2025_window"]], [pw["SOLAR"]["last_year"]], "o", mfc="white", color=MID, ms=5, label="Jan to Oct 2025")
            ax.plot([pw["SOLAR"]["share"]], [pw["SOLAR"]["actual"]], "D", color=BAD, ms=5, label="Jan to Oct 2026, actual")
            ax.set_ylim(-0.5, 1.5); ax.axvline(sc["observed_share_range"][1], color=MID, lw=.6, ls=":")
            ax.set_xlabel("share of load, %"); ax.set_ylabel("capture rate"); ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper right"); clean(ax)
            ax.set_title("extrapolation beyond the observed range (dotted line)", loc="left")

        bs, bl, bm = (B["SOLAR"][k] for k in ("slope_model", "last_year", "mean_so_far"))
        page(pdf, "MODULE 15 / 4 of 6", "Out of sample: the slope does not forecast", [
            ("Backtest, solar, 2022 to 2025", [
                f"RMSE in capture-rate units: slope model {bs['rmse']:.3f}, last year {bl['rmse']:.3f}, mean so far {bm['rmse']:.3f}.",
                f"Without 2022: {B['SOLAR']['rmse_ex2022']['slope_model']:.3f}, {B['SOLAR']['rmse_ex2022']['last_year']:.3f}, {B['SOLAR']['rmse_ex2022']['mean_so_far']:.3f}. The slope model is not better than the naive rule in either.",
                f"Wind: slope model {B['WIND']['slope_model']['rmse']:.3f}, last year {B['WIND']['last_year']['rmse']:.3f}, mean so far {B['WIND']['mean_so_far']['rmse']:.3f}; nothing to forecast beyond the mean."]),
            ("Fifth test, January to October 2026", [
                f"Share of load {pw['SOLAR']['share']:.1f}% (Jan to Oct 2025: {pw['SOLAR']['share_2025_window']:.1f}%). Fitted line predicts {pw['SOLAR']['slope_model']:.2f}; realised {pw['SOLAR']['actual']:.2f};",
                f"last year's window {pw['SOLAR']['last_year']:.2f}. The rate stopped falling while the share rose, so the line overshoots."]),
            ("The scenario, and why its interval is empty", [
                f"At {sc['share_new']:.1f}% of load ({sc['share_2025']:.1f}% in {y1} plus {d['shift_points']:.0f} points, a value I chose) the line gives {sc['cr_pred']:.2f}; log-linear {sc['cr_pred_loglinear']:.2f}.",
                f"Backtest interval [{sc['backtest_interval'][0]:.2f}, {sc['backtest_interval'][1]:.2f}] (RMSE x 2.776, four errors). The parameter-only bootstrap, [{sc['param_boot_interval'][0]:.2f}, {sc['param_boot_interval'][1]:.2f}],",
                f"ignores model error and is the wrong one to quote. Observed shares stop at {sc['observed_share_range'][1]:.1f}%."])
        ], fig_bt)

        def fig_sw(fig):
            ax = fig.add_axes([0.50, 0.08, 0.44, 0.38])
            order = list(range(len(sw)))[::-1]
            for k, i in enumerate(order):
                r = sw.iloc[i]
                lo, hi = (r["solar_boot_lo"], r["solar_boot_hi"]) if not pd.isna(r["solar_boot_lo"]) else (np.nan, np.nan)
                ax.plot([100 * r["solar_ols_lo"], 100 * r["solar_ols_hi"]], [k, k], color=RULE, lw=4, solid_capstyle="butt")
                if not np.isnan(lo):
                    ax.plot([100 * lo, 100 * hi], [k, k], color=ACC, lw=1.6)
                ax.plot(100 * r["solar_slope"], k, "o", color=BAD if r["group"] == "base" else INK, ms=4)
            ax.axvline(0, color=MID, lw=.8)
            ax.set_yticks(range(len(order))); ax.set_yticklabels([sw.iloc[i]["group"] + ": " + sw.iloc[i]["variant"][:48] for i in order], fontsize=6.4)
            ax.set_xlabel("solar slope, capture-rate points per point of share\ngrey: least-squares interval, green: week bootstrap")
            clean(ax)

        v = val.set_index("year")
        page(pdf, "MODULE 15 / 5 of 6", "Validation and sensitivity", [
            ("Against the published annual market values (2025)", [
                f"The transmission system operators publish annual market values (JW) under the EEG. For {jwv['year']}:",
                f"baseload {jwv['baseload']['published']:.2f} EUR/MWh published, {jwv['baseload']['mine']:.2f} mine; solar {jwv['solar']['published']:.2f} against {jwv['solar']['mine']:.2f} ({jwv['solar']['diff_pct']:+.1f}%);",
                f"onshore wind {jwv['wind_onshore']['published']:.2f} against {jwv['wind_onshore']['mine']:.2f} ({jwv['wind_onshore']['diff_pct']:+.1f}%). The page gives only the current year,",
                "so this is one year, not a series. It checks the price base and the weighting, not the slope."]),
            ("A published series that does not match", [
                f"The TSOs' MW Solar(a) (EEG 2012 s.33) exists for every year but differs from my solar-weighted price",
                f"by {mvs['mean_abs_diff_pct']:.0f}% on average and by up to {mvs['max_abs_diff_pct']:.0f}% ({v['diff_pct'].abs().idxmax()}), mine lower in {int((v['diff_pct'] < 0).sum())} of {len(v)} years. Levels correlate at",
                f"{mvs['corr_levels']:.2f}. I could not establish its weighting and do not use it as a check; I report the gap."]),
            ("What moves the solar slope", [
                f"Across {d['sweep_summary']['n_variants']} variants it runs from {sl(d['sweep_summary']['solar_slope_range'][0], 2)} to {sl(d['sweep_summary']['solar_slope_range'][1], 2)}; negative in all, but the",
                f"least-squares interval reaches zero or above in {int((sw['solar_ols_hi'] >= 0).sum())} of them ({'; '.join(sw[sw['solar_ols_hi'] >= 0]['group'])}).",
                f"Dropping 2022: {sl(sw[sw.variant == 'drop 2022 from the fit']['solar_slope'].iloc[0], 2)}. Flooring negative prices: {sl(sw[sw.group == 'negative prices']['solar_slope'].iloc[0], 2)}.",
                f"Wind runs from {sl(d['sweep_summary']['wind_slope_range'][0], 2)} to {sl(d['sweep_summary']['wind_slope_range'][1], 2)}; its intervals hold zero in every variant that has them.",
                f"The bootstrap block length moves the interval, not the point: width {100 * (sw[sw.variant == 'bootstrap blocks of 4 weeks']['solar_boot_hi'].iloc[0] - sw[sw.variant == 'bootstrap blocks of 4 weeks']['solar_boot_lo'].iloc[0]):.1f} with",
                f"4-week blocks against {100 * (sw.iloc[0]['solar_boot_hi'] - sw.iloc[0]['solar_boot_lo']):.1f} with one week."])
        ], fig_sw)

        page(pdf, "MODULE 15 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks it", [
                "That the share of load is what moves the capture rate. The seven annual points span a low",
                f"baseload price in 2020 ({fa['baseload']['2020']:.0f} EUR/MWh), the spike of 2022 ({a_s.loc[2022, 'cr'] * 100:.0f}% capture at {a_s.loc[2022, 'share']:.1f}% share)",
                "and the fall after it, and the slope is not separated from them. Storage build-out, rules on",
                "feed-in at negative prices and the move to quarter-hourly prices are changes I did not measure",
                "that fall in the same window.",
                f"The backtest shows what that costs: errors of both signs, up to {bt[bt.tech == 'SOLAR']['err_slope_model'].abs().max():.2f} in capture-rate units."]),
            ("What a sceptical reviewer attacks first", [
                f"Seven points. The week bootstrap gives {iv(S['boot_interval'])} and the across-year interval {iv(S['ols_interval'])}; the",
                "second is the one to quote. A capture rate is a ratio of prices, so a change in the gas price moves",
                "numerator and denominator together only if the whole curve shifts in proportion; it need not.",
                "Generation is the published feed-in, net of self-consumption. Load is grid load."]),
            ("Other limits", [
                "One bidding zone, day-ahead only: intraday and balancing revenues, and what a project realises",
                "under a PPA or the market premium, are outside the estimand. The validation covers one year of the",
                "TSO values; the MW Solar(a) series disagrees with me and I could not resolve it from public pages."]),
            ("Next", [
                "Residual-load capture rate (price on load net of wind and solar) to separate supply shape from level;",
                "monthly panel with gas and carbon prices as controls; the same rate for the Netherlands and Spain."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
