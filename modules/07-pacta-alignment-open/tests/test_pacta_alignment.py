"""Checks that fail loudly if the target arithmetic, the owner allocation or the interval breaks.

Fixed inputs, so this tests the arithmetic and not anyone's uptime.

    python3 tests/test_pacta_alignment.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import pacta_alignment as A

T = A.TECHS


def test_increasing_target_adds_a_share_of_the_sector_not_a_multiple_of_own_capacity():
    """A company with no renewables still gets a renewables target under the market-share
    approach. A tmsr-style ratio would leave it at 0 x anything = 0 and hide the whole gap."""
    t = A.target(p_tech=0.0, p_sector=1000.0, s0_tech=100.0, st_tech=300.0, s0_sector=1000.0,
                 increasing=True)
    assert abs(t - 200.0) < 1e-9, "(300-100)/1000 of a 1000 MW sector is 200 MW"


def test_decreasing_target_scales_own_production_by_the_scenario_ratio():
    t = A.target(p_tech=500.0, p_sector=1000.0, s0_tech=200.0, st_tech=50.0, s0_sector=1000.0,
                 increasing=False)
    assert abs(t - 125.0) < 1e-9, "500 MW x (50/200) is 125 MW"


def test_increasing_target_is_floored_at_zero():
    """A scenario that shrinks nuclear by more than a company's nuclear fleet must give 0, not a
    negative capacity that would be read as a surplus elsewhere."""
    t = A.target(p_tech=10.0, p_sector=1000.0, s0_tech=100.0, st_tech=0.0, s0_sector=1000.0,
                 increasing=True)
    assert t == 0.0


def test_decreasing_technology_with_zero_scenario_base_raises():
    """Dividing by a zero scenario base would give inf or nan and a silently wrong aggregate."""
    try:
        A.target(10.0, 100.0, 0.0, 0.0, 100.0, increasing=False)
    except ValueError:
        return
    raise AssertionError("zero base-year scenario capacity must raise")


def test_flat_scenario_gives_zero_gap_for_every_technology():
    P = np.array([[100.0, 50, 10, 20, 30, 40], [10.0, 5, 1, 2, 3, 4]])
    s = np.array([5.0, 4, 3, 2, 1, 6])
    flags = [t in A.INCREASING for t in T]
    g = A.gap(P, A.targets_matrix(P, s, s.copy(), flags))
    assert np.allclose(g, 0), "target equal to base year means no gap"


def test_gap_is_capacity_weighted_not_a_company_average():
    """One 9,000 MW coal company and one 1,000 MW clean company: the set's coal gap must be set
    by the big one. A mean of company gaps would give 0.5."""
    P = np.array([[9000.0, 0, 0, 0, 0, 0], [0.0, 0, 0, 0, 0, 1000.0]])
    s0 = np.array([100.0, 100, 100, 100, 100, 100])
    st = np.array([0.0, 100, 100, 100, 100, 100])
    flags = [t in A.INCREASING for t in T]
    g = A.gap(P, A.targets_matrix(P, s0, st, flags))
    assert abs(g[0] - 0.9) < 1e-9, "9,000 of 10,000 MW above a zero target"


def test_increasing_gap_is_the_same_for_every_resample():
    """Structural property of the market-share approach: summed over companies, the build-out
    gap equals minus the scenario's change as a share of sector, whoever is in the set. If this
    fails the target formula has stopped being the PACTA one."""
    rng = np.random.default_rng(1)
    P = rng.uniform(1, 100, (6, 6))
    s0 = np.array([50.0, 40, 10, 20, 30, 50])
    st = np.array([5.0, 30, 5, 25, 33, 140])
    flags = [t in A.INCREASING for t in T]
    Tm = A.targets_matrix(P, s0, st, flags)
    b = A.bootstrap_gap(P, Tm, rng, n=200)
    expected = -(st[5] - s0[5]) / s0.sum()
    assert np.allclose(b[:, 5], expected), "renewables gap must not depend on who is resampled"
    assert b[:, 0].std() > 0, "the coal gap must depend on who is resampled"


def test_model_draw_is_shared_by_every_company_in_a_replicate():
    """Identical companies, two scenario models with opposite gaps. If the model were drawn per
    company the replicate gaps would take intermediate values; drawn once they take only two."""
    P = np.tile(np.array([[10.0, 0, 0, 0, 0, 0]]), (8, 1))
    T1 = np.zeros_like(P)
    T2 = P * 2
    b = A.bootstrap_gap_models(P, [T1, T2], np.random.default_rng(0), n=300)
    assert len(set(np.round(b[:, 0], 9))) == 2, "model error must be one draw for all lines"


def test_ownership_uses_stated_percentages_and_splits_the_remainder_equally():
    s = dict(A.split_shares("60% Alpha; Beta; Gamma", "ownership"))
    assert abs(s["Alpha"] - 0.6) < 1e-9 and abs(s["Beta"] - 0.2) < 1e-9 and abs(s["Gamma"] - 0.2) < 1e-9


def test_ownership_with_no_percentages_splits_equally_and_never_exceeds_the_plant():
    for owner in ("A/B", "A; B; C", "100% A"):
        tot = sum(sh for _, sh in A.split_shares(owner, "ownership"))
        assert tot <= 1.0 + 1e-9, f"{owner}: shares sum to {tot}"
    assert dict(A.split_shares("A/B", "ownership")) == {"A": 0.5, "B": 0.5}


def test_control_gives_the_whole_plant_to_the_first_named_owner():
    assert A.split_shares("40% Alpha; 60% Beta", "control") == [("Alpha", 1.0)]


def test_scottish_and_southern_is_sse_not_scottish_power():
    """'Scottish' is in both names. SSE must not be rolled into Iberdrola by the extended tier."""
    assert A.group_of("Scottish and Southern Energy (SSE)", "extended") == "SSE"
    assert A.group_of("Scottish Power Renewables", "extended") == "Iberdrola"
    assert A.group_of("Scottish Power Renewables", "strict") is None


def test_eon_pattern_does_not_match_unrelated_names():
    assert A.group_of("E.On Kraftwerke GmbH", "strict") == "E.ON"
    assert A.group_of("Mark-E AG", "strict") is None
    assert A.group_of("Leon Power Ltd", "strict") is None


def test_plant_commissioned_after_base_year_is_excluded_and_unknown_year_is_kept():
    base = {"name": "p", "country": "DEU", "primary_fuel": "Coal", "capacity_mw": "100",
            "owner": "RWE"}
    rows = [dict(base, commissioning_year="2021"), dict(base, commissioning_year=""),
            dict(base, commissioning_year="2020")]
    assert len(A.load_plants(rows)) == 2, "2021 out; blank and 2020 in"


def test_unmapped_fuel_and_non_eu_country_are_dropped():
    base = {"name": "p", "capacity_mw": "100", "owner": "", "commissioning_year": ""}
    rows = [dict(base, country="DEU", primary_fuel="Storage"),
            dict(base, country="USA", primary_fuel="Coal"),
            dict(base, country="DEU", primary_fuel="Petcoke")]
    out = A.load_plants(rows)
    assert len(out) == 1 and out[0]["tech"] == "Oil", "petcoke maps to Oil; storage and USA drop"


def test_spearman_of_identical_and_reversed_rankings():
    assert abs(A.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-9
    assert abs(A.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-9


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
