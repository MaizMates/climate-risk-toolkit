"""Checks that fail loudly if the gap arithmetic, the resampling or the committed tables break.

Tests marked SYNTHETIC build inputs here with a known answer: they check the method and nothing in results/
comes from them. The data tests read the committed tables in data/ and results/, so they need no API.

    python3 tests/test_coherence.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import coherence as C
import prepare as P

DATA, RES = os.path.join(HERE, "..", "data"), os.path.join(HERE, "..", "results")


def frame(rows):
    d = pd.DataFrame(rows, columns=["geo", "flow", "year", "monthly_gwh", "annual_gwh"])
    d["eu27"], d["m_flags"], d["a_flag"], d["alt_annual_gwh"] = 1, "", "", np.nan
    d["gap"], d["agap"] = C.gaps(d.monthly_gwh, d.annual_gwh)
    return d


def test_gap_sign_and_size_on_fixed_values():
    g, a = C.gaps([101.0, 99.0, 100.0], [100.0, 100.0, 100.0])
    assert np.allclose(g, [0.01, -0.01, 0.0]) and np.allclose(a, [0.01, 0.01, 0.0]), g


def test_annual_zero_with_monthly_positive_is_infinite_not_nan():
    # a NaN would drop out of every share silently and flatter the result
    g, a = C.gaps([5.0, 0.0], [0.0, 0.0])
    assert np.isinf(a[0]) and g[0] > 0 and a[1] == 0.0, (g, a)


def test_monthly_zero_against_positive_annual_is_a_gap_of_minus_one():
    g, _ = C.gaps([0.0], [250.0])
    assert g[0] == -1.0, g


def test_tolerance_boundary_is_inclusive():
    d = frame([("AT", "IMP", 2020, 101.0, 100.0), ("AT", "IMP", 2021, 101.01, 100.0)])
    assert C.statistic(d)["share_within"] == 0.5, "1.00% is inside the tolerance, 1.01% is outside"


def test_pairs_with_both_figures_zero_are_dropped_by_default():
    # counting 0 against 0 as coherent would lift the headline share by several points
    p = frame([("AT", "PS", y, 0.0, 0.0) for y in range(2010, 2015)] + [("AT", "IMP", 2010, 100.0, 100.0)])
    assert len(C.select(p, years=(2008, 2025))) == 1
    assert len(C.select(p, years=(2008, 2025), both_zero=True)) == 6


def test_headline_population_is_eu27_only():
    p = frame([("AT", "IMP", 2010, 1.0, 1.0), ("AL", "IMP", 2010, 1.0, 1.0)])
    p.loc[p.geo == "AL", "eu27"] = 0
    assert set(C.select(p).geo) == {"AT"}
    assert set(C.select(p, eu=False).geo) == {"AT", "AL"}


def test_persistence_needs_enough_years_and_half_of_them_outside():
    rows = [("AT", "DL", y, 150.0, 100.0) for y in range(2010, 2013)]                    # 3 of 3 outside, only 3 years
    rows += [("BE", "DL", y, 150.0 if y < 2013 else 100.0, 100.0) for y in range(2010, 2020)]   # 3 of 10 outside
    rows += [("CZ", "DL", y, 150.0 if y < 2013 else 100.0, 100.0) for y in range(2010, 2016)]   # 3 of 6: exactly half
    d = frame(rows)
    assert list(C.persistent(d).index) == ["CZ|DL"], list(C.persistent(d).index)


def test_weighted_quantile_follows_the_weights():
    v = np.array([1.0, 2.0, 3.0])
    assert C.wquantile(v, np.array([1.0, 1.0, 1.0]), [0.5])[0] == 2.0
    assert C.wquantile(v, np.array([0.0, 0.0, 5.0]), [0.5])[0] == 3.0


def test_resampled_country_year_carries_all_its_flows_with_one_multiplicity():
    # the error a country shares across flows must be drawn once, not once per flow
    rows = [(g, f, y, 1.0, 1.0) for g in ("AT", "BE", "CZ", "DK") for y in (2010, 2011, 2012) for f in C.CORE]
    d = frame(rows)
    rng = np.random.default_rng(0)
    for _ in range(50):
        w = C.draw_weights(d, rng, "country_year")
        per = pd.Series(w).groupby([d.geo.values, d.year.values]).nunique()
        assert (per == 1).all(), "flows of one country-year got different multiplicities"


def test_country_cluster_draw_keeps_every_year_of_a_country_together():
    rows = [(g, "IMP", y, 1.0, 1.0) for g in ("AT", "BE", "CZ") for y in range(2010, 2016)]
    d = frame(rows)
    rng = np.random.default_rng(1)
    for _ in range(50):
        w = C.draw_weights(d, rng, "country")
        assert (pd.Series(w).groupby(d.geo.values).nunique() == 1).all()


def test_synthetic_known_error_is_recovered_exactly():
    """SYNTHETIC: 1,000 country-years, a known 30% carry a 2% error, the rest 0.2%."""
    rng = np.random.default_rng(3)
    bad = rng.random(1000) < 0.3
    annual = rng.uniform(1000, 5000, 1000)
    monthly = annual * np.where(bad, 1.02, 0.998)
    d = frame([("X%d" % i, "IMP", 2010, monthly[i], annual[i]) for i in range(1000)])
    assert abs(C.statistic(d)["share_within"] - (1 - bad.mean())) < 1e-12
    assert abs(C.statistic(d, tol=0.025)["share_within"] - 1.0) < 1e-12


def test_synthetic_bootstrap_interval_covers_known_share_and_widens_with_clustering():
    """SYNTHETIC: 40 countries x 10 years; a country is either always coherent or never. Years are then not
    independent, so the country-cluster interval has to be wider than the country-year one."""
    rows = []
    for c in range(40):
        for y in range(2010, 2020):
            rows.append((f"C{c}", "IMP", y, 100.0 if c % 2 == 0 else 150.0, 100.0))
    d = frame(rows)
    cy = C.ci([r["share_within"] for r in C.bootstrap(d, "country_year", n=300)])
    co = C.ci([r["share_within"] for r in C.bootstrap(d, "country", n=300)])
    assert cy[0] < 0.5 < cy[1] and co[0] < 0.5 < co[1]
    assert co[1] - co[0] > 2 * (cy[1] - cy[0]), (cy, co)


def test_trace_gives_the_flag_precedence_and_calls_the_rest_unexplained():
    rows = [("AT", "DL", y, 150.0, 100.0) for y in range(2010, 2016)] + [("BE", "DL", y, 150.0, 100.0) for y in range(2010, 2016)]
    d = frame(rows)
    d.loc[d.geo == "AT", "m_flags"] = "e:12"
    t = C.trace(d).set_index("geo")
    assert t.loc["AT", "cause"].startswith("documented") and t.loc["BE", "cause"] == "unexplained"


def test_json_stat_index_arithmetic_on_a_hand_built_cube():
    """SYNTHETIC: a 2 x 3 cube whose row-major positions are known; a wrong stride would swap country and month."""
    import tempfile
    cube = {"id": ["geo", "time"], "size": [2, 3],
            "dimension": {"geo": {"category": {"index": {"AT": 0, "BE": 1}}}, "time": {"category": {"index": {"2020-01": 0, "2020-02": 1, "2020-03": 2}}}},
            "value": {"0": 10.0, "2": 12.0, "4": 21.0}, "status": {"2": "p"}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cube, f)
    t = P.tidy(f.name).set_index(["geo", "time"])
    os.unlink(f.name)
    assert t.loc[("AT", "2020-01"), "value"] == 10.0 and t.loc[("AT", "2020-03"), "value"] == 12.0 and t.loc[("BE", "2020-02"), "value"] == 21.0
    assert t.loc[("AT", "2020-03"), "flag"] == "p" and len(t) == 3


def test_committed_pairs_have_twelve_months_and_no_duplicates():
    p = pd.read_csv(os.path.join(DATA, "pairs.csv"))
    assert not p.duplicated(["geo", "flow", "year"]).any()
    assert p.monthly_gwh.notna().all() and p.annual_gwh.notna().all() and (p.annual_gwh >= 0).all()
    assert set(p.flow) == {"IMP", "EXP", "DL", "PS", "NEP"}
    assert p.year.max() <= 2025, "a partial year (2026) leaked into the pairs"


def test_headline_in_results_reproduces_from_the_committed_pairs():
    o = json.load(open(os.path.join(RES, "coherence.json")))
    st = C.statistic(C.select(C.load()))
    assert abs(st["share_within"] - o["headline"]["share_within"]) < 1e-12 and st["n_persistent"] == o["headline"]["n_persistent"]


def test_reported_interval_is_the_percentile_of_the_saved_draws():
    o = json.load(open(os.path.join(RES, "coherence.json")))
    b = pd.read_csv(os.path.join(RES, "bootstrap.csv"))
    assert len(b) == o["draws"]
    assert np.allclose(C.ci(b.share_within), o["ci_country_year"]["share_within"], atol=1e-4)
    lo, hi = o["ci_country_year"]["share_within"]
    assert lo < o["headline"]["share_within"] < hi


def test_country_year_interval_is_not_wider_than_country_interval_in_the_real_data():
    # persistence inside countries makes years dependent: if this fails, the dependence story in the README is wrong
    o = json.load(open(os.path.join(RES, "coherence.json")))
    w = lambda k: o[k]["share_within"][1] - o[k]["share_within"][0]
    assert w("ci_country") > w("ci_country_year")


if __name__ == "__main__":
    names = [n for n in dict(globals()) if n.startswith("test_")]
    for n in names:
        globals()[n]()
        print("ok  ", n)
    print(f"{len(names)} tests passed")
