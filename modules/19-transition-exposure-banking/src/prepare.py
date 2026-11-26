"""Turn the raw EBA files into the small tables the analysis reads (each under 1 MB, committed).

- data/nace_extract.csv       loans and advances to non-financial corporations by NACE section and bank: gross
                              carrying amount and non-performing amount, EUR m. Banks carry a sequence number, not
                              a name or LEI; countries with fewer than MIN_BANKS banks are pooled as XX.
- data/eba_published.csv      the EBA Risk Dashboard Q2 2025 annex: share of NFC loans and NPL ratio by NACE
                              section, by country and EU/EEA, June 2025 (parsed from the PDF)
- data/reconciliation.json    the exercise against itself and against the EBA Risk Assessment Report totals

    python3 src/prepare.py
"""
import csv
import json
import os
import re
import sys

import pandas as pd
import pypdf

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")
SECTIONS = list("ABCDEFGHIJKLMNOPQRS")          # NACE_codes 1..19 in the EBA metadata
OTHER = "XXXXXXXXXXXXXXXXXXXX"                  # the EBA's "other banks" aggregate row, not a bank
MIN_BANKS = 3
NON_EU27 = {"NO", "LI", "IS"}
EXTRACT = [("2025", p) for p in ("202409", "202412", "202503", "202506")] + [("2024", "202406")]


def load(ed):
    d = pd.read_csv(os.path.join(RAW, ed, "tr_cre.csv"), dtype=str,
                    usecols=["LEI_Code", "NSA", "Period", "Item", "Exposure", "Perf_Status", "NACE_codes", "Amount", "Sheet"])
    d["Amount"] = pd.to_numeric(d["Amount"])
    return d


def nace_table(d, ed, period):
    """One row per bank and NACE section: gross carrying amount and non-performing amount."""
    p = ed[2:]
    n = d[(d.Sheet == "NACE") & (d.Period == period) & (d.Item == p + "21301") & (d.LEI_Code != OTHER)]
    g = n[(n.Perf_Status == "0") & (n.NACE_codes != "0")].set_index(["LEI_Code", "NSA", "NACE_codes"]).Amount
    q = n[(n.Perf_Status == "2") & (n.NACE_codes != "0")].set_index(["LEI_Code", "NSA", "NACE_codes"]).Amount
    t = pd.concat([g, q], axis=1, keys=["gross", "npe"]).reset_index()
    t["nace"] = t.NACE_codes.astype(int).map(lambda i: SECTIONS[i - 1])
    return t.rename(columns={"LEI_Code": "lei", "NSA": "country"})[["lei", "country", "nace", "gross", "npe"]]


def reconcile(d, ed, period):
    """The NACE sheet against the NPE sheet and the EBA report: three independent routes to the same totals."""
    p = ed[2:]
    nace = d[(d.Sheet == "NACE") & (d.Period == period) & (d.Item == p + "21301") & (d.Perf_Status == "0")]
    tot0 = nace[nace.NACE_codes == "0"].Amount.sum()
    sec = nace[nace.NACE_codes != "0"].Amount.sum()
    npe = d[(d.Sheet == "NPE") & (d.Period == period)]
    nfc = npe[(npe.Item == p + "20605") & (npe.Exposure == "301") & (npe.Perf_Status == "0")].Amount.sum()
    loans = npe[(npe.Item == p + "20603") & (npe.Exposure == "0")].groupby("Perf_Status").Amount.sum()
    cash = npe[(npe.Item == p + "20608") & (npe.Exposure == "0") & (npe.Perf_Status == "0")].Amount.sum()
    npl_nfc = npe[(npe.Item == p + "20605") & (npe.Exposure == "301") & (npe.Perf_Status == "2")].Amount.sum()
    return {"nace_total_nace0": tot0, "nace_sum_sections": sec, "npe_sheet_nfc_total": nfc,
            "loans_gross_all": loans["0"], "loans_npl_all": loans["2"], "cash_balances": cash,
            "npl_ratio_loans_only": loans["2"] / loans["0"],
            "npl_ratio_with_cash_in_denominator": loans["2"] / (loans["0"] + cash),
            "nfc_npl": npl_nfc, "nfc_npl_ratio": npl_nfc / nfc}


def report_totals():
    """Pull the NPL volume and ratio the EBA states in its Risk Assessment Report (text of the PDF)."""
    r = pypdf.PdfReader(os.path.join(RAW, "rar2025.pdf"))
    for i, pg in enumerate(r.pages):
        t = re.sub(r"\s+", " ", pg.extract_text())
        m = re.search(r"reported EUR (\d+) bn of NPLs.*?NPL ratio was reported at (\d+\.\d+)%", t)
        if m:
            return {"page": i + 1, "npl_bn": float(m.group(1)), "npl_ratio": float(m.group(2)) / 100,
                    "text": m.group(0)[:260]}
    raise RuntimeError("NPL totals not found in the Risk Assessment Report")


def parse_row(line):
    """('AT', {section: Jun-25 value}) from one table line, or None. A line is a country code and one Mar-25 and one
    Jun-25 percentage per section: 20 pairs-values for sections A to J, 18 for K to S (plus layout noise)."""
    f = line.split()
    vals = [x for x in f[1:] if x.endswith("%")]
    if len(f) > 20 and re.fullmatch(r"[A-Z]{2}|EU/EEA", f[0]) and len(vals) in (18, 20):
        secs = SECTIONS[:10] if len(vals) == 20 else SECTIONS[10:]
        return f[0], {s: float(vals[2 * k + 1][:-1]) / 100 for k, s in enumerate(secs)}   # Jun-25 is the second of a pair
    return None


def dashboard():
    """Annex pages 'Distribution of NFC loans and advances by NACE code' and 'NPL ratios of NFC loans ... by NACE
    code': each page holds two tables (sections A to J, then K to S); each section has a Mar-25 and a Jun-25 column."""
    r = pypdf.PdfReader(os.path.join(RAW, "dash_q2_2025.pdf"))
    out = []
    for idx, measure in ((28, "share"), (29, "npl_ratio")):
        text = r.pages[idx].extract_text()
        assert ("Distribution of NFC loans" if measure == "share" else "NPL ratios of NFC") in text, "dashboard layout moved"
        for line in text.split("\n"):
            row = parse_row(line)
            if row:
                out += [(measure, row[0], sec, v) for sec, v in row[1].items()]
        assert out, "no dashboard rows parsed"
    return out


def main():
    os.makedirs(DATA, exist_ok=True)
    frames, recon = [], {}
    for ed in ("2025", "2024"):
        d = load(ed)
        for e, period in EXTRACT:
            if e == ed:
                t = nace_table(d, ed, period)
                t.insert(0, "period", period)
                t.insert(0, "edition", ed)
                frames.append(t)
                recon[f"{ed}_{period}"] = reconcile(d, ed, period)
        del d
    allr = pd.concat(frames, ignore_index=True)
    latest = allr[(allr.edition == "2025") & (allr.period == "202506")]
    nb = latest.groupby("country").lei.nunique()
    small = set(nb[nb < MIN_BANKS].index)
    ids = {lei: f"B{i + 1:03d}" for i, lei in enumerate(sorted(allr.lei.unique()))}
    allr["bank"] = allr.lei.map(ids)
    allr["eu27"] = (~allr.country.isin(NON_EU27)).astype(int)
    allr["country"] = allr.country.where(~allr.country.isin(small), "XX")
    allr[["gross", "npe"]] = allr[["gross", "npe"]].round(4)
    allr.sort_values(["edition", "period", "bank", "nace"])[
        ["edition", "period", "bank", "country", "eu27", "nace", "gross", "npe"]].to_csv(
        os.path.join(DATA, "nace_extract.csv"), index=False)
    pub = dashboard()
    with open(os.path.join(DATA, "eba_published.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["measure", "country", "nace", "value_jun25"])
        w.writerows(pub)
    recon["rar_2025"] = report_totals()
    recon["pooled_small_countries"] = sorted(small)
    recon["banks_by_country_2025_06"] = {k: int(v) for k, v in nb.items() if k not in small}
    json.dump(recon, open(os.path.join(DATA, "reconciliation.json"), "w"), indent=1)
    print("extract rows", len(allr), "dashboard values", len(pub), "pooled:", sorted(small))


if __name__ == "__main__":
    sys.exit(main())
