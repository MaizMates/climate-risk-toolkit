"""Checks that fail loudly if the join or the estimator breaks.

Fixed inputs, so this tests the arithmetic and not WRI's or Eurostat's uptime.

    python3 tests/test_hazard_exposure.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hazard_exposure as H


def test_exposed_share_is_capacity_weighted_not_plant_count():
    plants = [{"country": "AAA", "capacity_mw": 900.0},
              {"country": "BBB", "capacity_mw": 100.0},
              {"country": "BBB", "capacity_mw": 100.0},
              {"country": "BBB", "capacity_mw": 100.0}]
    hazard = {"AAA": 10.0, "BBB": 0.5}
    # 3 of 4 plants sit in the exposed country, but only 300 of 1200 MW does.
    share = H.exposed_share(plants, hazard, k=1)
    assert abs(share - 900.0 / 1200.0) < 1e-9, "share must be MW-weighted, not a plant count"


def test_threshold_is_strictly_greater_than_k():
    """A country sitting exactly on k is not 'a rise of more than k days' -- the roadmap's
    own wording. Off-by-one here would silently reclassify every country sitting on a round
    threshold."""
    plants = [{"country": "AAA", "capacity_mw": 100.0}]
    hazard = {"AAA": 2.0}
    assert H.exposed_share(plants, hazard, k=2) == 0.0, "exactly k days is not '> k'"
    assert H.exposed_share(plants, hazard, k=1) == 1.0


def test_country_missing_from_hazard_table_is_not_exposed():
    """A plant in a country module 01 never covered must not silently count as exposed just
    because a missing lookup compares as falsy or zero."""
    plants = [{"country": "ZZZ", "capacity_mw": 500.0}]
    hazard = {"AAA": 99.0}
    assert H.exposed_share(plants, hazard, k=0) == 0.0


def test_bootstrap_ci_is_wider_when_one_plant_dominates():
    """The roadmap's whole reason for bootstrapping: the capacity distribution is skewed by a
    few large plants. A flat portfolio and a concentrated one with the same total and the same
    point estimate must not get the same interval."""
    hazard = {"AAA": 10.0, "BBB": 0.0}
    concentrated = [{"country": "AAA", "capacity_mw": 900.0}] + \
        [{"country": "BBB", "capacity_mw": 10.0} for _ in range(10)]
    flat = [{"country": "AAA", "capacity_mw": 90.0} for _ in range(10)] + \
        [{"country": "BBB", "capacity_mw": 10.0} for _ in range(10)]
    assert abs(H.exposed_share(concentrated, hazard, 1) - 0.9) < 1e-9
    assert abs(H.exposed_share(flat, hazard, 1) - 0.9) < 1e-9
    lo_c, hi_c = H.bootstrap_ci(concentrated, hazard, 1, n=2000, seed=1)
    lo_f, hi_f = H.bootstrap_ci(flat, hazard, 1, n=2000, seed=1)
    assert (hi_c - lo_c) > (hi_f - lo_f), "one dominant plant must widen the interval"


def test_top10_share_of_exposed_ignores_unexposed_plants():
    hazard = {"AAA": 10.0, "BBB": 0.0}
    plants = [{"country": "AAA", "capacity_mw": 100.0, "name": f"a{i}"} for i in range(15)] + \
        [{"country": "BBB", "capacity_mw": 100000.0, "name": "huge-but-not-exposed"}]
    top10 = H.top10_share_of_exposed(plants, hazard, k=1)
    assert abs(top10 - 10 * 100.0 / (15 * 100.0)) < 1e-9, \
        "the huge unexposed plant must not be pulled into the exposed concentration figure"


def test_thermal_fuels_gas_and_biomass_are_additive_toggles():
    core = H.thermal_fuels(include_gas=False, include_biomass=False)
    assert core == H.THERMAL_CORE
    assert "Gas" in H.thermal_fuels(include_gas=True, include_biomass=False)
    assert "Biomass" in H.thermal_fuels(include_gas=False, include_biomass=True)
    assert "Solar" not in H.thermal_fuels(include_gas=True, include_biomass=True)


def test_load_thermal_plants_drops_wrong_country_wrong_fuel_and_bad_capacity():
    rows = [
        {"country": "ITA", "primary_fuel": "Coal", "capacity_mw": "500.0", "name": "in-scope"},
        {"country": "USA", "primary_fuel": "Coal", "capacity_mw": "500.0", "name": "wrong-country"},
        {"country": "ITA", "primary_fuel": "Solar", "capacity_mw": "500.0", "name": "wrong-fuel"},
        {"country": "ITA", "primary_fuel": "Coal", "capacity_mw": "", "name": "no-capacity"},
        {"country": "ITA", "primary_fuel": "Coal", "capacity_mw": "0", "name": "zero-capacity"},
    ]
    plants = H.load_thermal_plants(rows, {"ITA"}, H.thermal_fuels())
    assert [p["name"] for p in plants] == ["in-scope"]


def test_exposed_share_with_no_capacity_is_none_not_zero_division():
    assert H.exposed_share([], {"AAA": 10.0}, k=0) is None


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
