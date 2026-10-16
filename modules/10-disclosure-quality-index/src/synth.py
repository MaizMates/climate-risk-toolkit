"""Measure the fill-rate parser's error on SYNTHETIC tables with a known share of blank cells.

Synthetic data, used only to test the parser (never to estimate anything about a bank): each page
is a generated table in one of five layouts, rendered to PDF with matplotlib, read back with pypdf,
and scored by disclosure.cell_counts. The truth is the share of filled cells that was generated.
"""
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pypdf
from matplotlib.backends.backend_pdf import PdfPages

import disclosure as D

HERE = os.path.dirname(os.path.abspath(__file__))
STYLES = ["codes+labels", "wrapped labels+footnotes", "no codes", "n/a placeholders", "percent+zeros"]


def make_page(pdf, rng, style, q_blank):
    rows, cols = int(rng.integers(8, 30)), int(rng.integers(5, 14))
    fig = plt.figure(figsize=(11.7, 8.3))
    fig.text(0.04, 0.96, "Template X: Banking book - Climate change - synthetic table 2024", fontsize=9)
    filled = total = 0
    ph = {"n/a placeholders": "n/a"}.get(STYLES[style], "-")
    y0, dy = 0.9, 0.85 / (rows + 1)
    for r in range(rows):
        y = y0 - r * dy
        if STYLES[style] != "no codes":
            fig.text(0.03, y, f"{(r + 1) * 10:03d}" if style == 0 else str(r + 1), fontsize=5)
        label = f"Sector {chr(65 + r % 20)} manufacturing of goods" if style != 2 else f"Sector {chr(65 + r % 20)}"
        fig.text(0.07, y, label, fontsize=5)
        if style == 1:
            fig.text(0.07, y - dy * 0.45, f"of which item {r}", fontsize=4)
            fig.text(0.23, y, str(1 + r % 3), fontsize=4)  # footnote marker
        for c in range(cols):
            total += 1
            if rng.random() < q_blank:
                fig.text(0.28 + c * 0.7 / cols, y, ph, fontsize=5)
                continue
            filled += 1
            v = rng.lognormal(4, 2)
            if style == 4:
                txt = "0" if rng.random() < 0.08 else f"{rng.uniform(0, 100):.1f}%"
            else:
                txt = f"{v:,.0f}" if v > 10 else f"{v:.2f}"
            fig.text(0.28 + c * 0.7 / cols, y, txt, fontsize=5)
    pdf.savefig(fig)
    plt.close(fig)
    return filled / total


def run(n=200, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        style, q = k % len(STYLES), float(rng.uniform(0, 0.9))
        buf = io.BytesIO()
        with PdfPages(buf) as pdf:
            truth = make_page(pdf, rng, style, q)
        txt = pypdf.PdfReader(io.BytesIO(buf.getvalue())).pages[0].extract_text()
        a, b = D.cell_counts(txt)
        out.append({"style": STYLES[style], "truth": truth, "measured": a / (a + b) if a + b else 0.0})
    return out


def calibrate(rows):
    t = np.array([r["truth"] for r in rows])
    m = np.array([r["measured"] for r in rows])
    b, a = np.polyfit(t, m, 1)
    resid = m - (a + b * t)
    return {"intercept": float(a), "slope": float(b), "resid_sd": float(resid.std(ddof=2)),
            "residuals": resid.tolist(), "mean_error": float((m - t).mean()),
            "mean_abs_error": float(np.abs(m - t).mean()),
            "by_style": {s: float(np.mean([r["measured"] - r["truth"] for r in rows if r["style"] == s]))
                         for s in STYLES}}


def main():
    rows = run()
    cal = calibrate(rows)
    json.dump({"note": "SYNTHETIC tables, parser test only", "rows": rows, "calibration": cal},
              open(os.path.join(HERE, "..", "results", "parser_test.json"), "w"))
    print({k: v for k, v in cal.items() if k != "residuals"})


if __name__ == "__main__":
    main()
