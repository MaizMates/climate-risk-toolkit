"""Checks that fail loudly if the arithmetic, the unit checks or the aggregation break.

Fixed inputs only, so this tests the logic and not DESNZ's, Eurostat's or AIB's uptime.

    python3 tests/test_emissions_inventory.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import emissions_inventory as E


def test_line_converts_kg_to_tonnes_and_records_the_right_fields():
    line = E._line("City", "XX", "1", "Test category", None, 1000.0, "kWh", 0.2, "kWh",
                    "source", "2024", 0.1, 0.05, "office_energy")
    assert abs(line["tco2e"] - 0.2) < 1e-9, "1000 kWh * 0.2 kg CO2e/kWh = 200 kg = 0.2 t"
    assert line["data_quality_score"] == E.DQ_SCORE["office_energy"]


def test_unit_mismatch_raises_instead_of_silently_multiplying():
    """A kWh activity multiplied by a kg CO2e/km factor is a real mistake this module could
    make if a factor lookup ever returned the wrong sheet's row -- it must fail loudly."""
    try:
        E._line("City", "XX", "1", "Bad line", None, 1000.0, "kWh", 0.2, "km",
                "source", "2024", 0.1, 0.05, "office_energy")
        assert False, "unit mismatch must raise"
    except ValueError:
        pass


def test_monte_carlo_scope_totals_sum_to_the_grand_total():
    lines = [
        E._line("A", "XX", "1", "gas", None, 100.0, "kWh", 0.2, "kWh", "s", "2024", 0.1, 0.05,
                "office_energy"),
        E._line("A", "XX", "2_location", "elec loc", None, 100.0, "kWh", 0.3, "kWh", "s", "2024",
                0.1, 0.05, "office_energy"),
        E._line("A", "XX", "2_market", "elec mkt", None, 100.0, "kWh", 0.5, "kWh", "s", "2024",
                0.1, 0.05, "office_energy"),
        E._line("A", "XX", "3", "travel", 6, 10.0, "passenger.km", 0.15, "passenger.km", "s",
                "2024", 0.1, 0.05, "travel"),
    ]
    mc = E.monte_carlo(lines, n=2000, seed=1)
    loc_total = mc["total_location_based"]["point_estimate"]
    expected = sum(l["tco2e"] for l in lines if l["scope"] != "2_market")
    assert abs(loc_total - expected) < 1e-9, "location-based total must exclude the market line"
    mkt_total = mc["total_market_based"]["point_estimate"]
    expected_mkt = sum(l["tco2e"] for l in lines if l["scope"] != "2_location")
    assert abs(mkt_total - expected_mkt) < 1e-9, "market-based total must exclude the location line"


def test_monte_carlo_interval_widens_with_stated_uncertainty():
    tight = [E._line("A", "XX", "1", "gas", None, 100.0, "kWh", 0.2, "kWh", "s", "2024",
                     0.01, 0.01, "office_energy")]
    wide = [E._line("A", "XX", "1", "gas", None, 100.0, "kWh", 0.2, "kWh", "s", "2024",
                    0.5, 0.5, "office_energy")]
    mc_tight = E.monte_carlo(tight, n=4000, seed=2)
    mc_wide = E.monte_carlo(wide, n=4000, seed=2)
    w_tight = mc_tight["by_scope"]["scope1"]["ci_hi"] - mc_tight["by_scope"]["scope1"]["ci_lo"]
    w_wide = mc_wide["by_scope"]["scope1"]["ci_hi"] - mc_wide["by_scope"]["scope1"]["ci_lo"]
    assert w_wide > w_tight, "a wider stated uncertainty must produce a wider interval"


def test_top_variance_driver_is_the_most_uncertain_line_not_the_biggest_point_estimate():
    """A small line with huge uncertainty should outrank a big line with almost none -- variance
    ranks lines by how much they move the total, not by their point estimate."""
    small_uncertain = E._line("A", "XX", "3", "small-uncertain", 6, 1000.0, "passenger.km", 1.0,
                              "passenger.km", "s", "2024", 0.9, 0.9, "travel")
    big_certain = E._line("A", "XX", "1", "big-certain", None, 100000.0, "kWh", 0.2, "kWh",
                          "s", "2024", 0.0001, 0.0001, "office_energy")
    mc = E.monte_carlo([small_uncertain, big_certain], n=4000, seed=3)
    assert big_certain["tco2e"] > small_uncertain["tco2e"], "sanity: big-certain has more mass"
    assert mc["top_variance_drivers"][0]["category"] == "small-uncertain", \
        "the volatile small line must top the variance ranking despite its small point estimate"


def test_completeness_table_covers_all_fifteen_categories_exactly_once():
    rows = E.completeness_table()
    nums = [r["category"] for r in rows]
    assert nums == list(range(1, 16)), "every GHG Protocol Scope 3 category must appear once"
    included = {r["category"] for r in rows if r["included"]}
    assert included == {3, 6, 7}, "only categories 3, 6 and 7 are built into this inventory"
    assert all(r["reason"] for r in rows), "every row, included or not, needs a stated reason"


def test_gas_calorific_value_sensitivity_shows_gross_cv_is_lower_not_higher():
    """DESNZ's own table: Gross CV kg CO2e/kWh < Net CV kg CO2e/kWh for natural gas, because the
    same energy content is expressed over a larger kWh figure on a gross basis. Applying the
    gross factor to net-basis activity data must understate emissions, and the sign of that
    understatement is worth locking down with a test, not just eyeballing the printed number."""
    per_country = {"DE": {"gas_kwh_per_employee": 1000.0}}
    cities_saved = list(E.CITIES)
    E.CITIES[:] = [{"city": "Frankfurt", "country": "DE", "employees": 1}]
    try:
        desnz = {"gas_net_kwh": 0.20264, "gas_gross_kwh": 0.1829}
        result = E.sensitivity_gas_cv(per_country, desnz)
    finally:
        E.CITIES[:] = cities_saved
    assert result["gross_cv_tco2e"] < result["net_cv_tco2e"]
    assert result["pct_difference_if_gross_used_on_net_activity"] < 0


def test_order_of_magnitude_check_flags_an_obviously_broken_scale():
    lines = [E._line("A", "XX", "1", "gas", None, 1.0, "kWh", 100000.0, "kWh", "s", "2024",
                     0.1, 0.05, "office_energy")]
    per_country = {"XX": {}}
    cities_saved = list(E.CITIES)
    E.CITIES[:] = [{"city": "A", "country": "XX", "employees": 1}]
    try:
        result = E.order_of_magnitude_check(lines, per_country)
    finally:
        E.CITIES[:] = cities_saved
    assert result["within_bound"] is False, "1 tCO2e from 1 kWh is a broken scale, not a real firm"


def test_reconcile_reports_market_minus_location():
    mc = {"total_location_based": {"point_estimate": 100.0},
          "total_market_based": {"point_estimate": 150.0}}
    r = E.reconcile(mc)
    assert abs(r["delta_tco2e"] - 50.0) < 1e-9
    assert abs(r["delta_pct_of_location"] - 0.5) < 1e-9


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
