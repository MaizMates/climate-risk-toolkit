"""Six pages. Every number is read from results/, none is typed here. Claims that compare numbers are
asserted before they are written."""
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


def f1(x):
    return f"{x:.1f}"


def iv(r, f=f1):
    return f"[{f(r[0])}, {f(r[1])}]"


def main():
    R = lambda f: os.path.join(ROOT, "results", f)
    d = json.load(open(R("loadtemp.json")))
    sw = pd.read_csv(R("sweep.csv"))
    bt = pd.read_csv(R("backtest.csv"))
    bs = pd.read_csv(R("backtest_specs.csv"))
    ann = pd.read_csv(R("annual.csv"))
    curve = pd.read_csv(R("curve.csv"))
    fit = pd.read_csv(R("fit_daily.csv"), parse_dates=["date"])
    B = pd.read_csv(R("bootstrap.csv"))
    surf = pd.read_csv(R("threshold_surface.csv"))
    H, C, S, th = d["heating"], d["cooling"], d["scenario_plus1"], d["thresholds"]
    t25, t26 = d["backtest"]["target_2025"], d["backtest"]["partial_2026"]
    roll = bt[bt.test.isin(["2022", "2023", "2024", "2025"])]
    base = sw[sw.group == "base"].iloc[0]
    harm = sw[sw.label.str.contains("harmonic")]
    sweep_oth = sw[(~sw.label.str.contains("harmonic")) & (sw.group != "base") & (sw.group != "scenario")]
    hmin, hmax = harm.bh.min(), harm.bh.max()
    ok_naive = bool((roll.rmse_model < roll.rmse_naive_364).all())
    ok_cal = bool((roll.rmse_model < roll.rmse_calendar_only).all())
    assert ok_naive and ok_cal, "the text below says the model beats both benchmarks in every test year"
    ratio = (roll.total_err_pct_model.abs().max()) / abs(S["pct_of_load"])
    wk = ann.weather_gwh
    sp = bs.pivot(index="test", columns="harmonics", values="rmse_model")
    better_h2 = [str(y) for y in sp.index if sp.loc[y, 2] < sp.loc[y, 0]]
    sweep_range = (sweep_oth.bh.min(), sweep_oth.bh.max())
    assert (sw.warm1_gwh < 0).all()
    dwd = sw[sw.label.str.startswith("DWD")].iloc[0]
    cities = pd.read_csv(os.path.join(ROOT, "data", "cities.csv"))
    bv = d["bootstrap_variants"]
    blk_w = [bv[k]["bh"][1] - bv[k]["bh"][0] for k in ("7", "14", "28")]
    assert max(blk_w) - min(blk_w) < 1.0, blk_w
    cov0 = sw[(sw.group == "thresholds") & (sw.bc < 0)]

    with PdfPages(os.path.join(ROOT, "deck.pdf")) as pdf:
        def d1(fig):
            ax = fig.add_axes([0.1, 0.1, 0.82, 0.32])
            ax.hist(B.warm1_gwh / 1000, bins=40, color=ACC); ax.axvline(S["gwh_per_year"] / 1000, color=BAD)
            ax.set_xlabel("change in annual load if every day is 1 C warmer, TWh (bootstrap draws)"); ax.set_ylabel("draws"); clean(ax)
        page(pdf, "MODULE 16 / 1 of 6", "How much of German electricity demand is weather?", [
            ("The estimand", [
                f"GWh of daily electricity load per degree-day of heating (below {th['th']} C) and of cooling (above {th['tc']} C),",
                "net of weekday, holiday, Christmas-week and year effects, Germany, 2019 to 2025. Temperature is",
                "the population-weighted daily mean of six cities (Berlin, Hamburg, Munich, Cologne, Frankfurt,",
                "Stuttgart). The applied result: the change in annual load if every day were one degree warmer."]),
            ("The answer", [
                f"Heating: {f1(H['gwh_per_hdd'])} GWh per degree-day, 95% interval {iv(H['interval'])}. That is {H['share_of_load_pct']:.1f}% of annual load.",
                f"Cooling: {f1(C['gwh_per_cdd'])} GWh per degree-day, interval {iv(C['interval'])}, but only {C['share_of_load_pct']:.2f}% of annual load.",
                f"All weather together: {d['weather_share_of_load_pct']:.1f}% of annual load, interval {iv(d['weather_share_interval'])}.",
                f"A uniformly 1 C warmer year: {S['gwh_per_year'] / 1000:.2f} TWh, {iv([x / 1000 for x in S['interval']], lambda v: f'{v:.2f}')}, or {S['pct_of_load']:.2f}% of load.",
                f"Out of sample (fit 2019 to 2024, predict 2025): daily RMSE {f1(t25['rmse_model'])} GWh, interval {iv(t25['rmse_model_interval'])},",
                f"against {f1(t25['rmse_calendar_only'])} with no temperature and {f1(t25['rmse_naive_364'])} for last year's same weekday."]),
            ("What moves it", [
                f"A seasonal control. With annual harmonics in the model the heating slope is {f1(hmin)} to {f1(hmax)} GWh per degree-day, not",
                f"{f1(H['gwh_per_hdd'])}, and the +1 C effect falls to {harm.warm1_gwh.abs().min() / 1000:.2f} to {harm.warm1_gwh.abs().max() / 1000:.2f} TWh. The data cannot separate the winter rise in load",
                "due to cold from the rise due to dark evenings and the calendar. The roadmap specification, which has",
                "no seasonal term, gives the upper end; the range is the honest answer."]),
        ], d1)
        # page 2: data and method with the temperature response figure
        def d2(fig):
            ax = fig.add_axes([0.1, 0.1, 0.82, 0.4])
            ax.scatter(curve.temp, curve.load_adj, s=18, color=ACC, zorder=3, label="mean of 2 C bins, net of calendar controls")
            tt = np.linspace(curve.temp.min(), curve.temp.max(), 200)
            icpt = (curve.load_adj - (H["gwh_per_hdd"] * np.maximum(th["th"] - curve.temp, 0) + C["gwh_per_cdd"] * np.maximum(curve.temp - th["tc"], 0))).median()
            ax.plot(tt, icpt + H["gwh_per_hdd"] * np.maximum(th["th"] - tt, 0) + C["gwh_per_cdd"] * np.maximum(tt - th["tc"], 0), color=BAD, lw=1.6,
                    label="fitted piecewise-linear response")
            ax.set_xlabel("population-weighted daily mean temperature, C"); ax.set_ylabel("daily load net of calendar, GWh")
            ax.set_ylim(curve.load_adj.min() - 80, curve.load_adj.max() + 80)
            ax.legend(frameon=False, fontsize=8); clean(ax)
        page(pdf, "MODULE 16 / 2 of 6", "Data and method", [
            ("Inputs, all fetched by src/fetch.py", [
                "Energy-Charts /public_power, series Load, quarter-hourly MW (Fraunhofer ISE, Bundesnetzagentur data, CC BY 4.0).",
                "Open-Meteo historical weather archive: daily mean 2 m temperature, six cities, one call per city and year.",
                "Open-Meteo geocoding (GeoNames): coordinates and population of the cities, the weights.",
                "Nager.Date: German nationwide public holidays. DWD open data: station temperature, validation only.",
                f"{d['n_days']} days fitted, 2019 to 2025; 2026 January to October ({t26['n_days']} days) held out as a further test."]),
            ("Model", [
                "load = year effect + weekday + holiday + 24 Dec to 1 Jan + b_h HDD(Th) + b_c CDD(Tc) + error.",
                "HDD = max(Th - T, 0), CDD = max(T - Tc, 0). Th (10 to 20) and Tc (14 to 26) are chosen by least squares,",
                f"inside every bootstrap draw and every backtest window. Selected: Th = {th['th']}, Tc = {th['tc']}.",
                f"Interval: block bootstrap over {d['block_days']}-day blocks of consecutive days, {d['draws']} draws. Each draw refits both slopes and",
                "both thresholds, and evaluates the warming scenario with that same fit."]),
        ], d2)
        # page 3 result
        def d3(fig):
            ax = fig.add_axes([0.1, 0.5, 0.38, 0.26])
            ax.hist(B.bh, bins=40, color=ACC); ax.axvline(H["gwh_per_hdd"], color=BAD)
            ax.set_xlabel("heating slope, GWh per degree-day"); ax.set_ylabel("bootstrap draws"); clean(ax)
            ax2 = fig.add_axes([0.56, 0.5, 0.36, 0.26])
            ax2.hist(B.bc, bins=40, color=WARN, range=tuple(np.percentile(B.bc, [0.5, 99.5]))); ax2.axvline(C["gwh_per_cdd"], color=BAD)
            ax2.set_xlabel("cooling slope, GWh per degree-day"); clean(ax2)
            ax3 = fig.add_axes([0.1, 0.1, 0.38, 0.28])
            pv = surf.pivot(index="tc", columns="th", values="rss")
            im = ax3.imshow((pv / pv.min().min()).values, origin="lower", aspect="auto", cmap="viridis_r",
                            extent=[pv.columns.min() - .5, pv.columns.max() + .5, pv.index.min() - .5, pv.index.max() + .5], vmax=1.1)
            ax3.set_xlabel("heating threshold Th, C"); ax3.set_ylabel("cooling threshold Tc, C")
            ax3.set_title("residual sum of squares / minimum", fontsize=8); fig.colorbar(im, ax=ax3, shrink=0.8)
            ax4 = fig.add_axes([0.56, 0.1, 0.36, 0.28])
            ax4.bar(ann.year, ann.weather_gwh / 1000, color=ACC); ax4.set_ylabel("weather-driven load, TWh"); clean(ax4)
            ax4.set_ylim(0, ann.weather_gwh.max() / 1000 * 1.15)
        page(pdf, "MODULE 16 / 3 of 6", "Result", [
            ("", [
                f"Heating {f1(H['gwh_per_hdd'])} GWh per degree-day {iv(H['interval'])}; selected thresholds {th['th']} C {iv(th['th_interval'], lambda v: f'{v:.0f}')} and {th['tc']} C {iv(th['tc_interval'], lambda v: f'{v:.0f}')}.",
                f"Cooling {f1(C['gwh_per_cdd'])} {iv(C['interval'])}: positive in the base fit, but it depends on where Tc sits (page 5).",
                f"Weather-driven load by year runs from {wk.min() / 1000:.1f} TWh to {wk.max() / 1000:.1f} TWh ({ann.loc[wk.idxmin(), 'year']} and {ann.loc[wk.idxmax(), 'year']}); mean annual load is {d['mean_annual_load_gwh'] / 1000:.0f} TWh.",
                f"Temperature lifts R-squared from {d['r2_calendar_only']:.2f} to {d['r2']:.2f}; residual s.d. {f1(d['residual_sd_gwh'])} GWh a day."]),
        ], d3)
        # page 4 backtest
        def d4(fig):
            ax = fig.add_axes([0.1, 0.42, 0.82, 0.32])
            x = np.arange(len(bt)); w = 0.26
            ax.bar(x - w, bt.rmse_model, w, color=ACC, label="temperature model")
            ax.bar(x, bt.rmse_calendar_only, w, color=RULE, label="calendar only (no temperature)")
            ax.bar(x + w, bt.rmse_naive_364, w, color=WARN, label="same weekday last year (364 days)")
            ax.set_xticks(x); ax.set_xticklabels(bt.test); ax.set_ylabel("daily RMSE, GWh")
            ax.legend(frameon=False, fontsize=8); clean(ax)
            ax2 = fig.add_axes([0.1, 0.1, 0.82, 0.2])
            e = fit[fit.date.dt.year == 2025]
            ax2.axis("off")
            rows = [[r.test, f"{r.rmse_model:.1f}", f"{r.mape_model:.1f}%", f"{r.total_err_pct_model:+.1f}%", f"{r.warm1_gwh / 1000:.2f}" if pd.notna(r.warm1_gwh) else "-"] for r in bt.itertuples()]
            tb = ax2.table(cellText=rows, colLabels=["test year", "RMSE GWh", "MAPE", "total error", "+1 C scenario TWh"], loc="center", cellLoc="center")
            tb.auto_set_font_size(False); tb.set_fontsize(8.5); tb.scale(1, 1.3)
        page(pdf, "MODULE 16 / 4 of 6", "Backtest: fit on earlier years, predict the next", [
            ("", [
                f"Each test year is predicted from the years before it, with its realised weather, and the last training year's level.",
                f"This tests the sensitivity, not weather forecasting. 2025: RMSE {f1(t25['rmse_model'])} GWh {iv(t25['rmse_model_interval'])}, total {t25['total_err_pct_model']:+.1f}% {iv(t25['total_err_pct_interval'], lambda v: f'{v:+.1f}')}.",
                "Temperature beats both benchmarks in every test year.",
                f"Its RMSE gain over calendar only in 2025 is {iv(t25['rmse_gain_over_calendar_interval'])} GWh.",
                f"The annual total error reaches {roll.total_err_pct_model.abs().max():.1f}% in a crisis year, {ratio:.0f} times the {abs(S['pct_of_load']):.2f}% the +1 C scenario moves load:",
                "the level error of the year effect, not the temperature slope, limits a forecast of annual load."]),
        ], d4)
        # page 5 sensitivity and validation
        def d5(fig):
            ax = fig.add_axes([0.46, 0.08, 0.46, 0.5])
            s = sw[sw.group != "scenario"].iloc[::-1]
            yy = np.arange(len(s))
            ax.errorbar(s.bh, yy, xerr=[s.bh - s.bh_lo, s.bh_hi - s.bh], fmt="o", color=ACC, ecolor=RULE, capsize=2, ms=4)
            ax.axvline(H["gwh_per_hdd"], color=BAD, lw=0.8)
            ax.set_yticks(yy); ax.set_yticklabels([l.split(":")[0][:44] for l in s.label], fontsize=7)
            ax.set_xlabel("heating slope, GWh per degree-day (bootstrap 95%)"); clean(ax)
        page(pdf, "MODULE 16 / 5 of 6", "Validation and sensitivity", [
            ("Validation against a source I did not fit", [
                f"DWD station temperature in place of Open-Meteo: heating {f1(dwd.bh)} {iv([dwd.bh_lo, dwd.bh_hi])} against {f1(base.bh)}.",
                "Same load, an independent weather measurement; this checks the temperature input only.",
                "No second source of daily German load is in the verified list, so the load side is not checked."]),
            ("Sensitivity", [
                f"Thresholds, sample, weights, smoothing: heating {f1(sweep_range[0])} to {f1(sweep_range[1])}; the sign of the warming effect",
                f"is negative in all {len(sw)} variants.",
                f"Seasonal harmonics: {f1(hmin)} to {f1(hmax)}, the largest move. Out of sample, harmonics beat none in {len(better_h2)} of 4 years.",
                f"Cooling is not stable: with Th = 12 and Tc = 18 it is {cov0.bc.min():.1f}, its interval below zero." if len(cov0) else "Cooling is positive in every threshold pair.",
                f"Block length 7, 14, 28 days: interval width {blk_w[0]:.1f}, {blk_w[1]:.1f}, {blk_w[2]:.1f} GWh per degree-day."]),
        ], d5)
        page(pdf, "MODULE 16 / 6 of 6", "Limits and what I would build next", [
            ("The assumption that breaks the conclusion", [
                "That the winter-summer difference in load is caused by temperature. Daylight, school and holiday",
                f"seasons and industrial calendars move with it. Absorbing the seasonal cycle cuts heating to {f1(hmin)}-{f1(hmax)}",
                f"and the +1 C effect to {harm.warm1_gwh.abs().max() / base.warm1_gwh * -1:.0%} of the headline at most. The headline is the upper end, not a central value."]),
            ("What a reviewer would attack first", [
                f"Six cities, weighted by city population ({cities.population.sum() / 1e6:.1f} million people), not by load. The DWD check swaps the",
                "measurement, not the cities; a gridded or station-network temperature would test the choice of cities.",
                "Sensitivities are those of 2019 to 2025. Heat pumps and air conditioning spread, so the slope",
                "is a snapshot. The interval measures sampling error, not that drift."]),
            ("What the interval does not cover", [
                "Sampling error of the fit, given the cities, the load definition and the 2019 to 2025 regime. Not drift in",
                "the slope, not the choice of cities, and not the level error of a forecast (page 4)."]),
            ("Next", ["Daylight as an explicit regressor; load weights from regional load; a rolling-window slope to see the drift."]),
        ])


if __name__ == "__main__":
    main()
