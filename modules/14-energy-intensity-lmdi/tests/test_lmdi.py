"""Checks that fail loudly if the decomposition breaks.

Arithmetic tests use fixed inputs written for the test (labelled synthetic: they exist to check
the method against a known answer, nothing in results/ comes from them). The data tests read the
committed tables in data/, so they do not depend on Eurostat's uptime.

    python3 tests/test_lmdi.py
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import lmdi as L


def _cells():
    E0, V0 = np.array([100.0, 50.0, 20.0]), np.array([1000.0, 500.0, 400.0])
    E1, V1 = np.array([110.0, 40.0, 30.0]), np.array([1200.0, 450.0, 500.0])
    return E0, V0, E1, V1


def test_logmean_of_equal_values_is_the_value_not_nan():
    assert L.logmean([5.0], [5.0])[0] == 5.0, "0/0 at equal values must resolve to the value"


def test_logmean_matches_the_closed_form():
    assert abs(L.logmean([2.0], [1.0])[0] - 1 / math.log(2)) < 1e-12


def test_zero_energy_cell_is_refused_not_silently_dropped():
    try:
        L.logmean([0.0, 1.0], [1.0, 1.0])
    except ValueError:
        return
    raise AssertionError("a cell with zero energy would drop out of the sum without a message")


def test_three_effects_sum_to_the_observed_change_exactly():
    s = L.step(*_cells())
    assert abs(s["act"] + s["str"] + s["int"] - s["dE"]) < 1e-9, "LMDI-I must leave no residual"


def test_chained_effects_sum_to_the_observed_change():
    E = np.array([[100.0, 104, 99, 90], [50.0, 48, 47, 45], [20.0, 25, 22, 30]])
    V = np.array([[1000.0, 1050, 1040, 1100], [500.0, 520, 480, 470], [400.0, 380, 420, 500]])
    t = L.chain(E, V, [0, 1, 2, 3])
    assert abs(t["act"] + t["str"] + t["int"] - (E[:, -1].sum() - E[:, 0].sum())) < 1e-9


def test_chain_and_direct_are_different_paths_to_the_same_total():
    E = np.array([[100.0, 140, 90], [50.0, 30, 55]])
    V = np.array([[1000.0, 900, 1100], [500.0, 700, 450]])
    ch, di = L.chain(E, V, [0, 1, 2]), L.chain(E, V, [0, 2])
    assert abs(ch["dE"] - di["dE"]) < 1e-9
    assert abs(ch["int"] - di["int"]) > 1e-3, "additive LMDI is path dependent; chain must differ"


def test_pure_growth_is_all_activity():
    E0, V0, _, _ = _cells()
    s = L.step(E0, V0, 2 * E0, 2 * V0)
    assert abs(s["act"] - E0.sum()) < 1e-9 and abs(s["str"]) < 1e-9 and abs(s["int"]) < 1e-9


def test_pure_efficiency_gain_is_all_intensity_with_the_right_sign():
    E0, V0, _, _ = _cells()
    s = L.step(E0, V0, E0 * np.array([0.8, 1.0, 1.0]), V0)
    assert abs(s["act"]) < 1e-9 and abs(s["str"]) < 1e-9
    assert abs(s["int"] - (-20.0)) < 1e-9, "less energy for the same output must be negative"


def test_pure_reshuffle_is_all_structure():
    E0, V0, _, _ = _cells()
    I = E0 / V0
    V1 = np.array([1100.0, 500.0, 300.0])
    s = L.step(E0, V0, I * V1, V1)
    assert abs(s["act"]) < 1e-9 and abs(s["int"]) < 1e-9
    assert abs(s["str"] - 5.0) < 1e-9, "value added moved to a cell with higher intensity must add energy"


def test_bootstrap_draws_states_whole_not_cell_by_cell():
    """Two cells per state with equal and opposite intensity effects cancel inside each state.
    Resampling states keeps them together and the effect stays zero in every draw; resampling
    the cells independently would not."""
    E = np.array([[100.0, 110], [100.0, 90]] * 4)
    V = np.array([[1000.0, 1000]] * 8)
    lab = [(g, s) for g in "ABCD" for s in ("x", "y")]
    d, worst = L.bootstrap(E, V, lab, list("ABCD"), [0, 1], n=200)
    assert np.abs(d[:, 2]).max() < 1e-9, "sector cells of one state were resampled separately"
    assert worst < 1e-9


def test_bootstrap_of_identical_states_has_no_spread():
    E = np.array([[100.0, 90]] * 3)
    V = np.array([[1000.0, 1000]] * 3)
    d, _ = L.bootstrap(E, V, [("A", "x"), ("B", "x"), ("C", "x")], list("ABC"), [0, 1], n=100)
    lo, hi = L.ci(d[:, 2])
    assert abs(hi - lo) < 1e-9, "identical states leave nothing to resample"


def test_weather_elasticity_recovers_a_known_value_on_a_synthetic_panel():
    rng = np.random.default_rng(3)
    years = range(2005, 2025)
    panel = {"energy": {}, "gva": {}, "hdd": {}}
    for g in ("AA", "BB", "CC", "DD"):
        h = {t: 3000 * math.exp(rng.normal(0, 0.1)) for t in years}
        v = {t: 100 * math.exp(0.02 * (t - 2005) + rng.normal(0, 0.03)) for t in years}
        a = rng.normal(5, 0.5)
        panel["hdd"][g] = h
        panel["gva"][(g, "J")] = v
        panel["energy"][(g, "FC_OTH_CP_E")] = {t: math.exp(a + 0.3 * math.log(h[t]) + 0.5 * math.log(v[t])
                                                           + rng.normal(0, 0.005)) for t in years}
        panel["energy"][(g, "FC_IND_E")] = panel["energy"][(g, "FC_OTH_CP_E")]
    w = L.weather_elasticity(panel, {"services": ("FC_OTH_CP_E", ["J"])})
    assert abs(w["elasticity_hdd"] - 0.3) < 0.05, "the weather regression does not recover a planted 0.3"


def _real():
    panel = L.load()
    return panel, L.members(panel)


def test_data_has_27_states_and_every_cell_is_positive():
    panel, geos = _real()
    assert len(geos) == 27
    last = L.last_year(panel)
    E, V, lab = L.build(panel, L.MAPPINGS[L.BASE_MAPPING], list(range(L.BASE_YEAR, last + 1)))
    assert E.shape[0] == 81 and (E > 0).all() and (V > 0).all(), "a zero cell breaks the logarithm"


def test_identity_holds_on_the_real_data():
    panel, _ = _real()
    last = L.last_year(panel)
    E, V, _ = L.build(panel, L.MAPPINGS[L.BASE_MAPPING], list(range(L.BASE_YEAR, last + 1)))
    t = L.chain(E, V, list(range(E.shape[1])))
    assert abs(t["act"] + t["str"] + t["int"] - t["dE"]) < 1e-6


def test_member_state_energy_adds_up_to_the_published_eu27_total():
    panel, geos = _real()
    for bal in ("FC_IND_E", "FC_OTH_CP_E", "FC_OTH_AF_E"):
        for y in (2015, L.last_year(panel)):
            s = sum(panel["energy"][(g, bal)][y] for g in geos)
            p = panel["energy"][("EU27_2020", bal)][y]
            assert abs(s / p - 1) < 1e-3, f"{bal} {y}: states do not add to EU27, a country is missing"


def test_committed_results_match_a_fresh_computation():
    panel, _ = _real()
    last = L.last_year(panel)
    E, V, _ = L.build(panel, L.MAPPINGS[L.BASE_MAPPING], list(range(L.BASE_YEAR, last + 1)))
    t = L.chain(E, V, list(range(E.shape[1])))
    r = json.load(open(os.path.join(HERE, "..", "results", "lmdi.json")))
    assert abs(r["headline"]["int"] - t["int"]) < 1e-6, "results/ is stale against the code and data"


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok   ", name)
            except AssertionError as e:
                fails += 1; print("FAIL ", name, "-", e)
    print(f"\n{'all checks pass' if not fails else str(fails) + ' failed'}")
    sys.exit(1 if fails else 0)
