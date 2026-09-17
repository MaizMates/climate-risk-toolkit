"""One runnable check that fails if the logic breaks.

It uses a fixed, hand-made series, so it tests the arithmetic and not Eurostat's uptime.

    python3 tests/test_renewables.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import renewables as R


def test_pace_is_per_year_not_per_window():
    row = {2020: 10.0, 2025: 20.0}
    assert R.pace(row, 2020, 2025) == 2.0, "10 points over 5 years is 2 a year"


def test_projection_carries_the_pace_forward():
    pr = R.project({2020: 10.0, 2025: 20.0})
    assert pr["latest_year"] == 2025
    assert pr["projected_2030"] == 30.0, "5 more years at 2 a year"


def test_a_falling_share_projects_downwards():
    pr = R.project({2020: 20.0, 2025: 15.0})
    assert pr["pace_pp_per_year"] == -1.0
    assert pr["projected_2030"] == 10.0, "a negative pace must not be clipped to zero"


def test_required_pace_and_shortfall_agree():
    rows = R.table({"XX": {2020: 10.0, 2025: 20.0}})
    r = rows[0]
    assert abs(r["required_pp_per_year"] - (42.5 - 20.0) / 5) < 1e-9
    assert abs(r["shortfall_in_pace"] - (r["required_pp_per_year"] - 2.0)) < 1e-9


def test_non_members_and_aggregates_are_dropped():
    rows = R.table({"NO": {2020: 70.0, 2025: 75.0}, "EU27_2020": {2020: 20.0, 2025: 24.0},
                    "DE": {2020: 19.0, 2025: 23.9}})
    assert [r["geo"] for r in rows] == ["DE"], "Norway is not a member state, EU27 is not a country"


def test_a_single_observation_cannot_make_a_trend():
    assert R.project({2025: 20.0}) is None


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   ", name)
            except AssertionError as e:
                fails += 1
                print("FAIL ", name, "-", e)
    print(f"\n{'all checks pass' if not fails else str(fails) + ' failed'}")
    sys.exit(1 if fails else 0)
