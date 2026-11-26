"""Checks that fail loudly if the exposure arithmetic, the resampling or the committed tables break.

The fixtures in the first block are SYNTHETIC, built only to test arithmetic with a known answer. Everything from
test_extract onwards reads the committed tables made from the EBA files.

    python3 tests/test_exposure.py
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import exposure as X
import prepare as P

DATA, RES = os.path.join(HERE, "..", "data"), os.path.join(HERE, "..", "results")


def banks(rows):
    """Synthetic banks x 19 sections: rows of (country, {section: (gross, npe)})."""
    g = np.zeros((len(rows), 19))
    n = np.zeros((len(rows), 19))
    for i, (_, d) in enumerate(rows):
        for s, (a, b) in d.items():
            g[i, X.SECTIONS.index(s)], n[i, X.SECTIONS.index(s)] = a, b
    idx = [f"b{i}" for i in range(len(rows))]
    return pd.DataFrame(g, idx, X.SECTIONS), pd.DataFrame(n, idx, X.SECTIONS), pd.Series([c for c, _ in rows], idx)


def test_share_and_gap_on_a_known_book():
    # A (in base) 60 with 6 non-performing; G (not in base) 40 with 2: share 0.6, NPL 10% inside, 5% outside
    g, n, _ = banks([("XX", {"A": (60, 6), "G": (40, 2)})])
    st = X.stats(X.components(g, n).sum(0), X.NAMES.index(X.BASE))
    assert abs(st["share"] - 0.6) < 1e-12 and abs(st["npl_in"] - 0.10) < 1e-12 and abs(st["npl_out"] - 0.05) < 1e-12
    assert abs(st["gap"] - 0.05) < 1e-12, "gap must be inside minus outside, not the reverse"


def test_pooled_share_is_loan_weighted_not_a_mean_of_bank_shares():
    # bank 1: 100 loans all in A; bank 2: 900 loans all in G. Pooled 10%, bank average 50%
    g, n, _ = banks([("XX", {"A": (100, 0)}), ("XX", {"G": (900, 0)})])
    st = X.stats(X.components(g, n).sum(0), X.NAMES.index(X.BASE))
    assert abs(st["share"] - 0.10) < 1e-12, "pooling must weight banks by loans"


def test_sections_of_the_base_mapping_are_the_documented_ones():
    assert X.VARIANTS[X.BASE][0] == set("ABCDFHL"), "base mapping changed; README and deck describe A, B, C, D, F, H, L"
    assert all(v[0] <= X.ALL for v in X.SPECS.values())


def test_denominator_variant_drops_financial_sector_from_the_denominator_only():
    g, n, _ = banks([("XX", {"A": (50, 0), "K": (50, 0)})])
    k = X.NAMES.index("base, K out of the denominator")
    assert abs(X.stats(X.components(g, n).sum(0), k)["share"] - 1.0) < 1e-12
    assert abs(X.stats(X.components(g, n).sum(0), X.NAMES.index(X.BASE))["share"] - 0.5) < 1e-12


def test_a_stratum_of_identical_banks_has_no_sampling_variance():
    """Resampling must stay inside the country: identical banks in one country give a zero-width interval, so any width
    left would come from drawing across countries."""
    g, n, c = banks([("DE", {"A": (10, 1), "G": (10, 1)})] * 4 + [("FR", {"A": (5, 0), "G": (15, 0)})] * 3)
    est = X.estimate(X.components(g, n), c, np.random.default_rng(1), b=200)
    k = X.NAMES.index(X.BASE)
    for ctry in ("DE", "FR"):
        s = X.stats(est["bs"][ctry], k)["share"]
        assert s.max() - s.min() < 1e-12
    s = X.stats(est["bs_eu"], k)["share"]
    assert s.max() - s.min() < 1e-12, "country weights are fixed, so identical banks leave nothing to vary"


def test_one_draw_is_shared_by_all_variants():
    """A replicate is one draw of banks, read by every variant. Two banks give three possible draws (0, 1 or 2 copies of
    the first bank); the pair (base share, 'B, D, H' share) can then take at most three values. Independent draws per
    variant would give up to nine."""
    g, n, c = banks([("DE", {"A": (10, 0)}), ("DE", {"G": (10, 0), "H": (10, 0)})])
    est = X.estimate(X.components(g, n), c, np.random.default_rng(3), b=500)
    a = X.stats(est["bs_eu"], X.NAMES.index(X.BASE))["share"]
    h = X.stats(est["bs_eu"], X.NAMES.index("B, D, H (fossil, power, transport)"))["share"]
    pairs = {(round(x, 9), round(y, 9)) for x, y in zip(a, h)}
    assert len(pairs) <= 3, "draws differ across variants: the shared error is being drawn independently"


def test_within_country_gap_removes_the_country_mix():
    """Simpson case. Each country has no gap (inside and outside both 1% in country X, both 9% in country Y), but Y
    holds more of its book inside, so the pooled gap is positive and the within-country gap is zero."""
    g, n, c = banks([("X", {"A": (20, 0.2), "G": (80, 0.8)}), ("Y", {"A": (80, 7.2), "G": (20, 1.8)})])
    est = X.estimate(X.components(g, n), c, np.random.default_rng(1), b=10)
    k = X.NAMES.index(X.BASE)
    assert X.stats(est["pt_eu"], k)["gap"] > 0.03, "pooled gap should carry the composition effect"
    assert abs(X.within_country_gap(est["pt"], k)) < 1e-12, "within-country gap must not"


def test_spearman_of_a_reversed_order_is_minus_one():
    assert abs(X.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-12


def test_dashboard_row_takes_the_june_column_not_march():
    """Synthetic line in the layout of the EBA annex: each section has (Mar-25, Jun-25)."""
    line = "XX " + " ".join(f"{i}.0% {i}.5%" for i in range(1, 11))
    c, d = P.parse_row(line)
    assert c == "XX" and abs(d["A"] - 0.015) < 1e-12 and abs(d["J"] - 0.105) < 1e-12, "picked the March column"
    line2 = "XX " + " ".join(f"{i}.0% {i}.5%" for i in range(1, 10)) + " T12_1 T12_1"
    assert list(P.parse_row(line2)[1]) == list("KLMNOPQRS"), "second table must map to sections K to S"
    assert P.parse_row("Mar-25 Jun-25 Mar-25") is None


# ---- committed tables from here on

def extract():
    return pd.read_csv(os.path.join(DATA, "nace_extract.csv"), dtype={"edition": str, "period": str})


def test_extract_is_small_pseudonymous_and_complete():
    p = os.path.join(DATA, "nace_extract.csv")
    assert os.path.getsize(p) < 1_000_000, "committed file over 1 MB"
    d = extract()
    assert not d.bank.str.contains(r"[A-Z0-9]{20}").any() and d.bank.str.fullmatch(r"B\d{3}").all(), "LEI leaked"
    assert not d.duplicated(["edition", "period", "bank", "nace"]).any(), "duplicate bank-section rows double count"
    assert (d.npe <= d.gross + 1e-3).all() and (d.gross >= 0).all(), "non-performing above gross, or negative"
    assert set(d.nace) == set(X.SECTIONS)
    last = d[(d.edition == "2025") & (d.period == "202506")]
    counts = last[last.country != "XX"].groupby("country").bank.nunique()
    assert (counts >= 3).all(), "a country with fewer than three banks is shown on its own"


def test_totals_reconcile_to_the_eba_report():
    v = json.load(open(os.path.join(RES, "summary.json")))["validation_totals"]
    assert abs(v["nace_sections_vs_nace_total"]) < 1e-6 and abs(v["nace_total_vs_npe_sheet_nfc"]) < 1e-6
    assert abs(v["npl_volume_all_eur_bn"] - v["report_npl_eur_bn"]) < 2.0, "NPL volume off the EBA report by over EUR 2 bn"
    assert abs(v["npl_ratio_incl_cash"] - v["report_npl_ratio"]) < 0.0005, "NPL ratio off the EBA report"


def test_published_shares_sum_to_one_and_regions_are_complete():
    p = pd.read_csv(os.path.join(DATA, "eba_published.csv"))
    eu = p[(p.country == "EU/EEA") & (p.measure == "share")]
    assert len(eu) == 19 and abs(eu.value_jun25.sum() - 1) < 0.01, "section shares of the EBA table do not sum to 1"


def test_headline_is_inside_its_interval_and_matches_a_fresh_computation():
    s = json.load(open(os.path.join(RES, "summary.json")))["head"]
    for k in ("share", "npl_in", "npl_out", "gap", "gap_within_country"):
        lo, hi = s[k + "_ci"]
        assert lo <= s[k] <= hi, f"{k} outside its own interval"
    g, n, c = X.bank_matrix(extract(), "2025", "202506")
    st = X.stats(X.components(g, n).sum(0), X.NAMES.index(X.BASE))
    assert abs(st["share"] - s["share"]) < 1e-9 and abs(st["gap"] - s["gap"]) < 1e-9, "results/ is stale against the code"


def test_every_country_row_has_at_least_three_banks_and_ordered_intervals():
    c = pd.read_csv(os.path.join(RES, "country.csv"))
    assert (c.banks >= 3).all()
    assert ((c.share_lo <= c.share) & (c.share <= c.share_hi)).all()
    assert ((c.thin == 1) == (c.banks < X.THIN)).all()


def test_readme_numbers_match_results():
    """The README quotes the headline; if results/ changes and the text does not, this fails."""
    s = json.load(open(os.path.join(RES, "summary.json")))
    h = s["head"]
    text = open(os.path.join(HERE, "..", "README.md")).read()
    for needle in (f"{h['share']:.1%}", f"{h['share_ci'][0]:.1%}", f"{h['share_ci'][1]:.1%}",
                   f"{h['gap'] * 100:+.2f}", f"{h['gap_ci'][0] * 100:+.2f}", f"{h['gap_ci'][1] * 100:+.2f}"):
        assert needle in text, f"README does not contain {needle}"


def test_largest_section_claim():
    """README says real estate is the largest section of NFC lending."""
    sec = pd.read_csv(os.path.join(RES, "section.csv"))
    assert sec.sort_values("share").iloc[-1].section == "L"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(len(fns), "passed")
