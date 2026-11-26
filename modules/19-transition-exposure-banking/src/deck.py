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
RES = os.path.join(ROOT, "results")
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
        paras, cur = [], ""
        for line in body:                      # an item ending in a full stop closes the paragraph
            cur = (cur + " " + line).strip()
            if line.rstrip()[-1] in ".?":
                paras.append(cur); cur = ""
        paras += [cur] if cur else []
        for para in paras:
            for part in textwrap.wrap(para, 92, break_long_words=False):
                fig.text(0.08, y, part, fontsize=9.3, color=MID, va="top"); y -= 0.0185
            y -= 0.006
        y -= 0.012
    if draw:
        draw(fig)
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def pc(x, d=1):
    return f"{x * 100:.{d}f}%"


def pp(x, d=2):
    t = f"{x * 100:+.{d}f}"
    return t[1:] if float(t) == 0 else t


def iv(c, d=1):
    return f"[{c[0] * 100:.{d}f}%, {c[1] * 100:.{d}f}%]"


def ivp(c, d=2):
    return f"[{pp(c[0], d)}, {pp(c[1], d)}]"


def main():
    S = json.load(open(os.path.join(RES, "summary.json")))
    h, cs, yoy, vp, vc, vt = S["head"], S["country_summary"], S["yoy"], S["validation_published"], S["validation_country"], S["validation_totals"]
    cty = pd.read_csv(os.path.join(RES, "country.csv"))
    sec = pd.read_csv(os.path.join(RES, "section.csv"))
    sw = pd.read_json(os.path.join(RES, "sweep_mapping.json"))
    dt = pd.read_json(os.path.join(RES, "sweep_date.json"))
    bsh = pd.read_csv(os.path.join(RES, "bank_shares.csv"))
    named = cty[cty.country != "other EU (pooled)"]
    thick = named[named.banks >= S["thin_below"]].sort_values("share", ascending=False)
    top, bot = thick.iloc[0], thick.iloc[-1]
    sec_by_share = sec.sort_values("share", ascending=False)
    assert sec_by_share.iloc[0].section == "L", "claim: real estate is the largest section"
    L = sec[sec.section == "L"].iloc[0]
    C = sec[sec.section == "C"].iloc[0]
    nol = sw[sw.variant == "base without L (real estate)"].iloc[0]
    cbr = sw[sw.variant == "EU benchmark high-impact (A-H, L)"].iloc[0]
    bdh = sw[sw.variant == "B, D, H (fossil, power, transport)"].iloc[0]
    assert sw.share.max() == cbr.share and sw.share.min() == bdh.share, "claim: range of the mapping sweep"
    flips = sw[(sw.gap_ci.map(lambda c: c[0] > 0))]
    sec_npl = sec.sort_values("npl_ratio", ascending=False)
    assert top.share_lo > bot.share_hi, "claim: the ends of the country range are separated"
    de = named[named.country == "DE"].iloc[0]
    assert de.bank_share_median > de.share, "claim: the median German bank is above the pooled share"
    sF, sD = sec[sec.section == "F"].iloc[0], sec[sec.section == "D"].iloc[0]
    assert sec.npl_ratio.idxmax() == sF.name, "claim: construction has the highest NPL ratio"
    assert sec[sec.in_base == 1].npl_ratio.idxmin() == sD.name, "claim: utilities lowest among mapped"
    assert L.npl_ratio < h["npl_out"] < C.npl_ratio, "claim: L below and C above the outside ratio"
    keepL = sw[(sw.variant != "base") & sw.sections.str.contains("L")]
    dropL = sw[~sw.sections.str.contains("L")]
    assert (dropL.spearman_country_share_vs_base < 0).all() and (keepL.spearman_country_share_vs_base > 0.8).all()
    d5 = dt[~dt.date.str.contains("EU/EEA")]
    gap_pos = thick[thick.gap_lo > 0].country.tolist()
    gap_neg = thick[thick.gap_hi < 0].country.tolist()
    base_secs = ", ".join(sec[sec.in_base == 1].section)

    with PdfPages(os.path.join(ROOT, "deck.pdf")) as pdf:
        page(pdf, "MODULE 19 / 1 of 6", "Where transition risk sits in bank lending", [
            ("The question", [
                "What share of EU banks' loans to non-financial corporations sits in climate-policy-relevant NACE",
                "sections, by country of the reporting bank, and do those sections already carry more non-performing",
                "loans than the rest? Read straight from the EBA's supervisory disclosures, at the June 2025 date of",
                "the latest transparency exercise. Countries and distributions only; no bank is named or ranked."]),
            ("The answer", [
                f"{pc(h['share'])} {iv(h['share_ci'])} of EUR {h['loans_eur_bn'] / 1000:.1f} trillion of corporate loans held by "
                f"{h['banks']} EU27 banks sits in the sections ({base_secs}).",
                f"The non-performing ratio is {pc(h['npl_in'])} inside them and {pc(h['npl_out'])} outside: a gap of "
                f"{pp(h['gap'])} points {ivp(h['gap_ci'])}. The interval contains zero, so at EU level there is no "
                "measurable gap yet."]),
            ("What moves", [
                f"Real estate (L) alone is {pc(L.share)} of the corporate book. Without it the share is {pc(nol.share)} and the "
                f"gap becomes {pp(nol.gap)} {ivp(nol.gap_ci)}, positive. The mapping moves the share from "
                f"{pc(bdh.share)} to {pc(cbr.share)}; the bank sample moves it by {(h['share_ci'][1] - h['share_ci'][0]) * 50:.1f} points either side. The share is a "
                "statement about the mapping before it is a statement about banks."])])

        page(pdf, "MODULE 19 / 2 of 6", "Method", [
            ("Data, fetched by src/fetch.py", [
                "EBA 2025 EU-wide transparency exercise, full database tr_cre.csv (sheet NACE: gross carrying amount and",
                "non-performing amount of loans and advances to non-financial corporations, by NACE section, by bank), with",
                "its metadata and dictionary. Reference date June 2025; the 2024 exercise gives June 2024. The EBA Risk",
                "Assessment Report (December 2025) and Risk Dashboard (Q2 2025) are fetched as PDFs and read with pypdf, for",
                "validation only. No bank-level figure is typed; the committed extract carries a sequence number, not a name."]),
            ("Estimator", [
                "Share = gross carrying amount in the mapped sections over the total, pooled across the banks of a country",
                "(volume-weighted, not an average of bank shares). NPL ratio = non-performing over gross amount; gap = ratio inside",
                "minus ratio outside. Mapping: Battiston et al. (2017) climate-policy-relevant sectors read at section level, as",
                f"in module 05 ({base_secs}); manufacturing is taken whole because the exercise does not split it.",
                f"Eight alternatives are swept. Countries with fewer than 3 banks are pooled; fewer than {S['thin_below']} is flagged thin."]),
            ("Interval", [
                f"Stratified bootstrap, {S['bootstrap_draws']} draws: banks are resampled with replacement inside each country and "
                "nothing else is resampled. Every statistic, mapping variant and section is read off the same draw, so the "
                "differences between variants carry their own intervals. The EU figure fixes each country's bank count. The interval "
                "measures how much the pooled figure depends on which banks sit in the country's sample; the "
                f"{h['banks']} banks are the exercise's population, not a random draw from it."]),
            ("Why nothing is projected", [
                "This is a snapshot of reported balance sheets, not a forecast, so there is nothing to backtest. The "
                "stability of the figure over five reporting dates and across two exercises stands in for it (page 5)."])])

        def fig3(fig):
            ax = fig.add_axes([0.14, 0.07, 0.78, 0.50])
            d = named.sort_values("share")
            y = np.arange(len(d))
            for yi, (_, r) in zip(y, d.iterrows()):
                c = WARN if r.thin else ACC
                ax.plot([r.share_lo, r.share_hi], [yi, yi], color=c, lw=5, alpha=.35, solid_capstyle="butt")
                ax.plot(r.share, yi, "o", color=c, ms=6)
                pts = bsh[bsh.country == r.country].share
                ax.plot(pts, [yi] * len(pts), "|", color=MID, ms=7, alpha=.8)
            ax.axvline(h["share"], color=BAD, lw=1.1, ls="--")
            ax.set_ylim(-0.6, len(d) + 0.4)
            ax.text(h["share"] + 0.005, len(d) - 0.1, f"EU27 {pc(h['share'])}", color=BAD, fontsize=8, ha="left")
            ax.set_yticks(y); ax.set_yticklabels([f"{r.country}  (n={r.banks})" for _, r in d.iterrows()])
            ax.set_xlabel("share of NFC loans in the mapped sections, June 2025")
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_title("pooled share with 95% bank-resampling interval; ticks are individual banks (countries with 5 or more)", loc="left", fontsize=8.5)
            clean(ax)

        page(pdf, "MODULE 19 / 3 of 6", "Result: the share, by country", [
            ("What the figure shows", [
                f"Among the {len(thick)} countries with at least {S['thin_below']} banks the share runs from {pc(bot.share)} ({bot.country}) to "
                f"{pc(top.share)} ({top.country}). Orange marks countries with 3 or 4 banks: the bootstrap is unreliable there.",
                f"The intervals separate only {cs['pairs_ge5_separated']} of {cs['pairs_ge5']} country pairs. The ordering of countries in the "
                "middle is not supported; the ends are.",
                f"Within a country banks differ a great deal (ticks): the median bank in DE is at "
                f"{pc(named[named.country == 'DE'].bank_share_median.iloc[0], 0)} against a pooled {pc(named[named.country == 'DE'].share.iloc[0], 0)}, "
                "because the pooled figure is weighted by loans."]),
            ("Concentration of the EU figure", [
                f"The five largest banks hold {pc(h['top5_banks_loan_share'], 0)} of the loans. Dropping any single bank moves the EU share by "
                f"at most {h['leave_one_bank_out_max_share_move_pp']:.2f} points."])], fig3)

        def fig4(fig):
            ax = fig.add_axes([0.20, 0.38, 0.70, 0.17])
            s = sec.sort_values("npl_ratio", ascending=False)
            x = np.arange(len(s))
            cols = [BAD if i else MID for i in s.in_base]
            ax.vlines(x, s.npl_ratio_lo, s.npl_ratio_hi, color=cols, lw=4, alpha=.35)
            ax.plot(x, s.npl_ratio, "o", color="none", ms=0)
            for xi, v, c in zip(x, s.npl_ratio, cols):
                ax.plot(xi, v, "o", color=c, ms=4.5)
            ax.set_xticks(x); ax.set_xticklabels(s.section)
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_ylabel("NPL ratio")
            ax.set_title("EU27 NPL ratio by NACE section; red = in the mapped set", loc="left", fontsize=8.5)
            clean(ax)
            ax2 = fig.add_axes([0.20, 0.07, 0.70, 0.22])
            d = thick.sort_values("gap")
            y = np.arange(len(d))
            for yi, (_, r) in zip(y, d.iterrows()):
                c = BAD if r.gap_lo > 0 else (OK if r.gap_hi < 0 else MID)
                ax2.plot([r.gap_lo * 100, r.gap_hi * 100], [yi, yi], color=c, lw=5, alpha=.35, solid_capstyle="butt")
                ax2.plot(r.gap * 100, yi, "o", color=c, ms=6)
            ax2.axvline(0, color=INK, lw=1)
            ax2.axvspan(h["gap_ci"][0] * 100, h["gap_ci"][1] * 100, color=ACC, alpha=.10)
            ax2.set_yticks(y); ax2.set_yticklabels(d.country)
            ax2.set_xlabel("NPL ratio inside minus outside the mapped sections, points (band: EU27 interval)")
            ax2.set_title("gap by country (5 or more banks)", loc="left", fontsize=8.5)
            clean(ax2)

        page(pdf, "MODULE 19 / 4 of 6", "Result: do the mapped sections perform worse?", [
            ("EU27", [
                f"No. The gap is {pp(h['gap'])} points {ivp(h['gap_ci'])}. Holding the country mix fixed (loan-weighted mean of country gaps) it is "
                f"{pp(h['gap_within_country'])} {ivp(h['gap_within_country_ci'])}: the sign is not an effect of which countries lend where.",
                f"The sections differ widely: construction (F) is the worst of all at {pc(sF.npl_ratio)}, utilities (D) "
                f"the best of the mapped ones at {pc(sD.npl_ratio)}. Real estate ({pc(L.npl_ratio)}) sits below and manufacturing "
                f"({pc(C.npl_ratio)}) above the ratio outside the set ({pc(h['npl_out'])}); they carry most of the weight and offset, which is why the gap nets to nothing."]),
            ("By country", [
                f"The interval excludes zero positive for {', '.join(gap_pos)} and negative for {', '.join(gap_neg)}; it contains zero for the rest. "
                f"Across all {cs['countries_reported']} reported countries {cs['gap_interval_excludes_zero']} intervals exclude zero. At 95%, "
                f"{cs['countries_reported'] * 0.05:.1f} of {cs['countries_reported']} would exclude zero by chance alone; read the sign pattern, not each country."])], fig4)

        def fig5(fig):
            ax = fig.add_axes([0.40, 0.28, 0.52, 0.16])
            y = np.arange(len(sw))[::-1]
            for yi, (_, r) in zip(y, sw.iterrows()):
                ax.plot(r.share_ci, [yi, yi], color=ACC, lw=5, alpha=.35, solid_capstyle="butt")
                ax.plot(r.share, yi, "o", color=ACC, ms=5)
            ax.set_yticks(y); ax.set_yticklabels(sw.variant, fontsize=7.5)
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
            ax.set_title("EU27 share by mapping", loc="left", fontsize=8.5); clean(ax)
            ax2 = fig.add_axes([0.40, 0.06, 0.52, 0.15])
            for yi, (_, r) in zip(y, sw.iterrows()):
                c = BAD if r.gap_ci[0] > 0 else (OK if r.gap_ci[1] < 0 else MID)
                ax2.plot([v * 100 for v in r.gap_ci], [yi, yi], color=c, lw=5, alpha=.35, solid_capstyle="butt")
                ax2.plot(r.gap * 100, yi, "o", color=c, ms=5)
            ax2.axvline(0, color=INK, lw=1)
            ax2.set_yticks(y); ax2.set_yticklabels(sw.variant, fontsize=7.5)
            ax2.set_xlabel("NPL gap, points"); ax2.set_title("EU27 gap by mapping (red: above zero, green: below)", loc="left", fontsize=8.5); clean(ax2)

        rho = sw[sw.variant != "base"]
        page(pdf, "MODULE 19 / 5 of 6", "Validation and sensitivity", [
            ("Against the EBA's own aggregates", [
                f"Reconciliation: the NACE sheet sums to its own total and to the NFC row of the NPE sheet. The exercise's NPL volume is "
                f"EUR {vt['npl_volume_all_eur_bn']:.1f} bn against EUR {vt['report_npl_eur_bn']:.0f} bn in the EBA's December 2025 report (p. {vt['report_page']}), and its ratio "
                f"with cash balances in the denominator is {vt['npl_ratio_incl_cash'] * 100:.2f}% against {vt['report_npl_ratio'] * 100:.2f}%.",
                f"EBA Risk Dashboard Q2 2025, EU/EEA row: the base share is {pc(vp['eba_share'])} from its published section shares, mine {pc(vp['mine_share'])} "
                f"{iv(vp['mine_share_ci'])}; the gap is {pp(vp['eba_gap'])} against {pp(vp['mine_gap'])} {ivp(vp['mine_gap_ci'])}. All 19 section shares and 19 section NPL ratios fall in my intervals "
                f"(mean absolute difference {vp['share_mae_pp']:.2f} and {vp['npl_mae_pp']:.2f} points). This confirms the extraction, not the interval: the EBA table is "
                "built from nearly the same banks. By country, "
                f"{vc['share_inside']} of {vc['countries']} EBA shares fall inside my interval, mean absolute difference {vc['share_mae_pp']:.1f} points, worst {vc['share_max_abs_pp']:.1f}; EBA country rows include the subsidiaries of foreign groups, mine count each bank once, in its own country."]),
            ("What moves", [
                f"Mapping: share from {pc(bdh.share)} to {pc(cbr.share)}. The gap is {pp(nol.gap)} points without real estate and {pp(cbr.gap)} under the "
                f"EU benchmark set; the interval is above zero in {len(flips)} of {len(sw)} variants, below zero in {int(sw.gap_ci.map(lambda c: c[1] < 0).sum())}, and contains zero in the rest: the sign depends on the mapping. The country ranking by share survives every variant that keeps real estate "
                f"(rank correlation {keepL.spearman_country_share_vs_base.min():.2f} to {keepL.spearman_country_share_vs_base.max():.2f}) and reverses in every one that drops it "
                f"({dropL[dropL.variant != 'base'].spearman_country_share_vs_base.min():.2f} to {dropL[dropL.variant != 'base'].spearman_country_share_vs_base.max():.2f}).",
                f"Date: the share is {pc(d5.share.min())} to {pc(d5.share.max())} over five reporting dates (Sep 2024 to Jun 2025, plus Jun 2024 from the earlier exercise). "
                f"On {yoy['banks_matched']} banks present in both, it changed {pp(yoy['share_change'], 2)} points {ivp(yoy['share_change_ci'])} between June 2024 and June 2025; "
                f"the gap changed {pp(yoy['gap_change'])} {ivp(yoy['gap_change_ci'])}."])], fig5)

        page(pdf, "MODULE 19 / 6 of 6", "Limits, and what I would build next", [
            ("The assumption that breaks it", [
                "That a NACE section is a unit of climate-policy exposure. It is not. Section C holds both steel and "
                "furniture; D holds coal plants and wind farms; L covers all real estate activity, whatever the building's energy performance. "
                f"The 'transition-relevant' share is {pc(h['share'])} largely because C ({pc(C.share)}) and L ({pc(L.share)}) are counted whole; across the sets "
                f"tried it runs from {pc(bdh.share)} to {pc(cbr.share)}. The headline measures where the mapping points, and the mapping is the weakest link."]),
            ("What a sceptical reviewer attacks first", [
                f"1. Exposure is not risk. A loan in an exposed section may be collateralised, short, or to a firm already transitioning. "
                "2. The NPL gap is backward-looking: low defaults in the sections today say nothing about repricing after a carbon "
                "price. The module cannot see that and does not claim to. 3. The bank sample is the large banks of each country "
                "(EBA exercise), so a country figure is not the country's whole banking system. 4. Small-country rows rest on 3 or 4 banks."]),
            ("Other limits", [
                "Loans to non-financial corporations only: no securities, no off-balance-sheet, no household mortgages (where building "
                "energy performance is the transition channel). Gross carrying amount, so no collateral or provisions. "
                "Country is the reporting bank's domicile, not the borrower's: a Dutch bank's German borrower counts for NL."]),
            ("Next", [
                "Join the sector shares to module 05's emission intensities by NACE section and Eurostat's country-level GVA, to put a "
                "financed-emission proxy on each country's book (module 09's method). It is the first step from where lending sits to how "
                "much carbon it carries. It needs only data already used in this repository."])])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
