"""Checks that fail loudly if the rating logic, the mapping, the weighting or the interval breaks.

Fixed toy inputs (labelled as such), so this tests the arithmetic and not the publishers' uptime.

    python3 tests/test_encore.py
"""
import io
import json
import os
import sys

import numpy as np
import openpyxl
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import encore as E

# Toy hierarchy: section S holds sub-industries A (process 1, rated H on service 0) and
# B (process 2, rated L). Section T holds C (process 3, rated VH).
SUBS = {"Aaa": {"section": "S", "pids": [1]}, "Bbb": {"section": "S", "pids": [2]},
        "Ccc": {"section": "T", "pids": [3]}}
MAP = {"ind": ["Aaa"], "ind2": ["Aaa", "Ccc"]}
PROC = {1: {}, 2: {}, 3: {}}
RAT = {(0, 1): "H", (0, 2): "L", (0, 3): "VH"}


def test_thresholds_are_nested_and_any_column_is_the_or_of_services():
    m = {t: E.flag_matrix(["s0", "s1"], PROC, {(0, 1): "H", (1, 1): "M", (0, 3): "VH"}, t)[1] for t in E.THRESHOLDS}
    assert (m["VH"][:, -1] <= m["H+"][:, -1]).all() and (m["H+"][:, -1] <= m["M+"][:, -1]).all(), \
        "a stricter threshold must never flag more processes"
    assert m["H+"][0, -1] and not m["VH"][0, -1] and m["M+"][0, 1], "H counts at H+, not at VH; M counts at M+"
    assert not m["H+"][1].any(), "an unrated process is not dependent"


def test_mapping_variants_nest_and_weights_sum_to_one():
    nar = E.process_weights("ind2", "narrow", "process", SUBS, MAP)
    base = E.process_weights("ind2", "base", "process", SUBS, MAP)
    broad = E.process_weights("ind2", "broad", "process", SUBS, MAP)
    assert set(nar) <= set(base) <= set(broad) and set(broad) == {1, 2, 3}
    for w in (nar, base, broad):
        assert abs(sum(w.values()) - 1) < 1e-12, "process weights must sum to one"


def test_sub_industry_weighting_differs_from_process_weighting_when_sizes_differ():
    subs = {"Aaa": {"section": "S", "pids": [1]}, "Bbb": {"section": "S", "pids": [2, 3, 4]}}
    m = {"x": ["Aaa", "Bbb"]}
    p = E.process_weights("x", "base", "process", subs, m)
    s = E.process_weights("x", "base", "sub", subs, m)
    assert abs(p[1] - 0.25) < 1e-12 and abs(s[1] - 0.5) < 1e-12


def test_ambiguous_or_missing_name_prefix_is_refused():
    for bad in ("", "Zzz"):
        try:
            E.resolve(bad, SUBS)
        except ValueError:
            continue
        raise AssertionError(f"prefix '{bad}' must not resolve silently")


def test_point_share_is_value_weighted_not_count_weighted():
    pids, mat = E.flag_matrix(["s0"], PROC, RAT, "H+")
    col = {p: i for i, p in enumerate(pids)}
    h = pd.DataFrame({"industry": ["ind", "ind2", "ind2"], "mv": [900.0, 50.0, 50.0]})
    pt, _ = E.point_share(h, mat, col, SUBS, "base", "process", MAP)
    # ind: A -> flagged (1.0). ind2: A and C both flagged (1.0). All of it is flagged.
    assert abs(pt[-1] - 1.0) < 1e-12
    h = pd.DataFrame({"industry": ["ind", "ind"], "mv": [900.0, 100.0]})
    pt, _ = E.point_share(h, mat, col, SUBS, "broad", "process", MAP)
    assert abs(pt[-1] - 0.5) < 1e-12, "broad ind = {A flagged, B not}: half"


def test_mapping_draw_is_shared_across_holdings_of_one_industry():
    pids, mat = E.flag_matrix(["s0"], PROC, RAT, "H+")
    col = {p: i for i, p in enumerate(pids)}
    h = pd.DataFrame({"industry": ["ind"] * 20, "mv": [1.0] * 20})
    d = E.draw_shares(h, mat, col, SUBS, mix_variants=True, n=3000, seed=1, mapping=MAP)[:, -1]
    # narrow and base map to A (share 1); broad gives about 0.5. One shared variant per draw
    # puts about 2/3 of draws at exactly 1.0; 20 independent variants would put almost none there.
    assert 0.6 < (d == 1.0).mean() < 0.72, "variant draw must be shared by all holdings of an industry"


def test_conditional_draw_centres_on_the_point_estimate():
    pids, mat = E.flag_matrix(["s0"], PROC, RAT, "H+")
    col = {p: i for i, p in enumerate(pids)}
    h = pd.DataFrame({"industry": ["ind"] * 50, "mv": [1.0] * 50})
    pt, _ = E.point_share(h, mat, col, SUBS, "broad", "process", MAP)
    # base mapping is a single flagged process, so no spread; check the broad-only mean by hand
    d = E.draw_shares(h, mat, col, SUBS, mix_variants=False, n=2000, seed=2, mapping={"ind": ["Aaa", "Bbb"]})[:, -1]
    assert abs(d.mean() - 0.5) < 0.02, "Monte Carlo mean must match the expected flagged share"


def test_spearman_handles_ties_and_perfect_order():
    assert abs(E.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-12
    assert abs(E.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-12
    assert abs(E.spearman([1, 1, 2, 3], [1, 1, 2, 3]) - 1) < 1e-12


def test_holdings_parser_drops_unassigned_rows_and_checks_header():
    wb = openpyxl.Workbook(); ws = wb.active   # synthetic fixture, test only
    ws.append(["Fund Name:", "Toy"]); ws.append(["ISIN:", "X"]); ws.append(["Ticker Symbol:", "T"])
    ws.append(["Holdings As Of:", "01-Jan-2026"]); ws.append([None])
    ws.append(["ISIN", "SEDOL", "Security Name", "Currency", "Number of Shares", "Percent of Fund",
               "Trade Country Name", "Local Price", "Sector Classification", "Industry Classification",
               "Base Market Value"])
    ws.append(["A", "s", "Real", "EUR", 1, 0.5, "France", 1, "Utilities", "Electric Utilities", 100.0])
    ws.append(["B", "s", "Cash", "EUR", 1, 0.5, "France", 1, "Unassigned", "Unassigned", 50.0])
    buf = io.BytesIO(); wb.save(buf)
    df, unassigned, meta = E.parse_holdings(buf.getvalue())
    assert len(df) == 1 and unassigned == 50.0, "unassigned value must be reported, not scored"
    ws.cell(row=6, column=11).value = "Value"; buf = io.BytesIO(); wb.save(buf)
    try:
        E.parse_holdings(buf.getvalue())
    except ValueError:
        return
    raise AssertionError("a changed header must stop the parse")


def test_ecb_comparator_is_read_from_the_page_text():
    p = os.path.join(HERE, "..", "data", "raw")
    os.makedirs(p, exist_ok=True)
    tmp = os.path.join(HERE, "_ecb_fixture")
    os.makedirs(tmp, exist_ok=True)
    with open(os.path.join(tmp, "ecb_blog.html"), "w") as f:
        f.write("<p>nearly 75 per cent of all bank loans</p><p>approximately 72 per cent of companies</p>"
                "<p>dependency score (greater than 0.7)</p>")
    try:
        c = E.ecb_comparator(tmp)
    finally:
        os.remove(os.path.join(tmp, "ecb_blog.html")); os.rmdir(tmp)
    assert c == {"loans_share_pct": 75, "companies_share_pct": 72, "score_threshold": 0.7}


def test_every_mapped_name_and_every_fund_industry_resolves_against_the_fetched_data():
    if not os.path.exists(os.path.join(E.RAW, "sectors.json")):
        print("  (skipped: run src/fetch.py first)"); return
    _, _, subs, _ = E.load_encore()
    for ind, names in E.GICS_TO_ENCORE.items():
        for n in names:
            E.resolve(n, subs)
    h, _, _ = E.parse_holdings(open(os.path.join(E.RAW, "zpre_holdings.xlsx"), "rb").read())
    assert set(h["industry"]) <= set(E.GICS_TO_ENCORE), "a holding would be silently dropped"


def test_published_interval_brackets_the_point_estimate():
    p = os.path.join(E.RES, "nature_dependency.json")
    if not os.path.exists(p):
        print("  (skipped: run src/encore.py first)"); return
    r = json.load(open(p))["headline"]
    for k in ("ci_conditional", "ci_with_mapping"):
        assert r[k][0] <= r["share_any"] <= r[k][1], f"{k} must contain the point estimate"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok  ", fn.__name__)
    print(f"{len(fns)} passed")
