"""Checks that fail loudly if the estimator breaks.

Fixed inputs, so this tests the arithmetic and not Eurostat's uptime.

    python3 tests/test_renewables.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import renewables as R


def test_ols_recovers_a_known_line():
    fit = R.ols([1, 2, 3, 4, 5], [3.0, 5.0, 7.0, 9.0, 11.0])
    assert abs(fit["slope"] - 2.0) < 1e-9
    assert abs(fit["se"]) < 1e-9, "a perfect line has no slope uncertainty"


def test_ols_reports_uncertainty_when_the_points_scatter():
    fit = R.ols([1, 2, 3, 4, 5], [3.0, 6.0, 6.5, 9.5, 11.0])
    assert fit["se"] > 0, "scattered points must not report a certain slope"


def test_slope_is_not_the_endpoint_difference():
    """The whole reason for OLS.

    A country that jumps early and then stalls has the same first and last value as one that
    crawls and then jumps, so an endpoint difference gives both the same pace. The fitted slope
    does not, and the difference is the size of the error the old method was making.
    """
    ys = [10.0, 20.0, 20.0, 20.0, 20.0]
    endpoint = (ys[-1] - ys[0]) / 4
    fitted = R.ols([0, 1, 2, 3, 4], ys)["slope"]
    assert abs(endpoint - 2.5) < 1e-9
    assert abs(fitted - 2.0) < 1e-9
    assert abs(fitted - endpoint) > 0.4, "the two estimators must not agree on this series"


def test_two_points_are_refused():
    assert R.ols([1, 2], [1.0, 2.0]) is None, "two points cannot support a standard error"


def test_a_falling_share_keeps_its_sign():
    fit = R.ols([2021, 2022, 2023, 2024, 2025], [20.0, 19.0, 18.0, 17.0, 16.0])
    assert fit["slope"] < 0, "a negative pace must never be clipped to zero"


def test_backtest_error_is_prediction_minus_outcome():
    series = {"XX": {y: float(y - 2010) for y in range(2011, 2026)}}
    bt = R.backtest(series)
    assert bt["n"] == 1
    assert abs(bt["rmse"]) < 1e-9, "a perfectly linear country must backtest exactly"


def test_verdict_refuses_to_call_it_when_the_band_straddles_the_yardstick():
    series = {"XX": {y: 42.5 for y in range(2015, 2026)}}
    bt = {"rmse": 5.0, "n": 1, "bias": 0.0, "mae": 0.0, "p90_abs": 5.0, "detail": []}
    row = R.table(series, 5, bt)[0]
    assert row["verdict"] == "cannot tell", "sitting exactly on the yardstick is not a finding"


def test_non_members_and_aggregates_are_dropped():
    rows = R.table({"NO": {y: 70.0 + y - 2020 for y in range(2021, 2026)},
                    "EU27_2020": {y: 20.0 for y in range(2021, 2026)},
                    "DE": {y: 19.0 + 0.9 * (y - 2020) for y in range(2021, 2026)}})
    assert [r["geo"] for r in rows] == ["DE"]


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
