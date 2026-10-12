"""Parsing and attribution checks for the fetch step. Run: python3 tests/test_fetch.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import fetch as g  # noqa: E402


def test_parent_shares_are_parsed_and_unparseable_parts_are_dropped_not_guessed():
    assert g.parse_parents("A INC (60%); B LLC (40.5%)") == [("A INC", 60.0), ("B LLC", 40.5)]
    assert g.parse_parents("A INC; B LLC (40%)") == [("B LLC", 40.0)]
    assert g.parse_parents(None) == []


def test_name_normalisation_matches_edgar_style_titles_and_keeps_distinct_firms_apart():
    assert g.norm_name("THE SOUTHERN CO") == g.norm_name("Southern Company") == "SOUTHERN"
    assert g.norm_name("AIR PRODUCTS & CHEMICALS INC") == g.norm_name("Air Products and Chemicals, Inc.")
    assert g.norm_name("Duke Energy Corp") != g.norm_name("Dominion Energy Inc")


def test_ownership_split_attributes_exactly_the_facility_total():
    fac = {1: {"parent_company": "A INC (60%); B LLC (40%)", "naics_code": 221112}}
    par, unparsed = g.attribute_to_parents(fac, {1: 1000.0})
    assert abs(par["A"]["e"] - 600) < 1e-9 and abs(par["B"]["e"] - 400) < 1e-9 and unparsed == 0


def test_facility_without_parent_is_counted_as_unattributed_not_assigned_to_anyone():
    par, unparsed = g.attribute_to_parents({1: {"parent_company": None, "naics_code": 1}}, {1: 50.0})
    assert not par and unparsed == 50.0


def test_page_boundary_rows_are_not_double_counted(monkeypatch=None):
    rows = [{"facility_id": 1, "sector_id": 3, "subsector_id": 1, "gas_id": 1, "co2e_emission": 10.0},
            {"facility_id": 1, "sector_id": 3, "subsector_id": 1, "gas_id": 1, "co2e_emission": 10.0},
            {"facility_id": 2, "sector_id": 10, "subsector_id": 1, "gas_id": 1, "co2e_emission": 99.0},
            {"facility_id": 3, "sector_id": 3, "subsector_id": 1, "gas_id": 1, "co2e_emission": None}]
    orig = g.fetch_pages
    g.fetch_pages = lambda path, step: ([{"facility_id": 1}] if "facility" in path else rows)
    try:
        _, tot = g.fetch_epa(2023)
    finally:
        g.fetch_pages = orig
    assert dict(tot) == {1: 10.0}


def test_annual_value_takes_the_ten_k_year_period_not_quarters_or_other_years():
    u = lambda **k: {"form": "10-K", "filed": "2024-02-01", **k}
    facts = {"us-gaap": {"Revenues": {"units": {"USD": [
        u(start="2023-01-01", end="2023-12-31", val=100),
        u(start="2023-10-01", end="2023-12-31", val=30),
        u(start="2022-01-01", end="2022-12-31", val=80),
        {"form": "10-Q", "filed": "2023-05-01", "start": "2023-01-01", "end": "2023-03-31", "val": 20}]}}}}
    assert g.annual_value(facts, ["Revenues"], 2023, True)["val"] == 100
    assert g.annual_value(facts, ["Revenues"], 2021, True) is None


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
