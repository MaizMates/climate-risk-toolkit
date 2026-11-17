"""Checks that fail loudly if the degree-day arithmetic, the resampling or the committed tables break.

Tests marked synthetic use series generated here with a known answer: they check the method and
nothing in results/ comes from them. The data tests read the committed tables in data/ and results/,
so they do not depend on any API.

    python3 tests/test_loadtemp.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import loadtemp as L

DATA, RES = os.path.join(HERE, "..", "data"), os.path.join(HERE, "..", "results")


def synthetic(noise=0.0, seed=0, years=(2019, 2020, 2021), bh=12.0, bc=5.0, th=15, tc=22, year_step=0.0):
    """SYNTHETIC: daily load with a known piecewise-linear temperature response."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31")
    doy = dates.dayofyear.values
    T = 10 - 12 * np.cos(2 * np.pi * (doy - 15) / 365.25) + rng.normal(0, 2.5, len(dates))
    wd = dates.weekday.values
    hol = ((dates.month == 5) & (dates.day == 1) | (dates.month == 10) & (dates.day == 3)).astype(int)
    y = 1000 + 20 * (wd == 5) - 60 * (wd == 6) - 90 * hol + bh * np.maximum(th - T, 0) + bc * np.maximum(T - tc, 0)
    y = y + year_step * (dates.year.values - years[0]) + rng.normal(0, noise, len(dates))
    return pd.DataFrame({"date": dates, "year": dates.year.values, "load_gwh": y, "temp": T, "holiday": hol})


def test_exact_recovery_of_thresholds_and_slopes_without_noise():
    m = L.fit(synthetic())
    assert (m["th"], m["tc"]) == (15, 22), (m["th"], m["tc"])
    assert abs(m["bh"] - 12.0) < 1e-6 and abs(m["bc"] - 5.0) < 1e-6, (m["bh"], m["bc"])


def test_slope_recovered_inside_its_bootstrap_interval_with_noise():
    d = synthetic(noise=25.0, seed=3)
    B = L.boot(d, L.BASE, 150, 1, fixed=(15, 22))
    lo, hi = L.ci(B[:, 2])
    assert lo < 12.0 < hi, (lo, hi)


def test_holiday_effect_does_not_leak_into_temperature_slope():
    """Holidays fall in May and October here; without the control the heating slope would be biased."""
    d = synthetic()
    d_no = d.assign(holiday=0)
    assert abs(L.fit(d, thresholds=(15, 22))["bh"] - 12.0) < 1e-6
    assert abs(L.fit(d_no, thresholds=(15, 22))["bh"] - 12.0) > 1e-3


def test_degree_days_are_zero_on_the_wrong_side_of_the_threshold():
    d = synthetic()
    T = d.temp.values
    h, c = np.maximum(15 - T, 0), np.maximum(T - 22, 0)
    assert (h * c).max() == 0.0 and h.min() >= 0 and c.min() >= 0


def test_prediction_carries_the_last_training_year_effect():
    """SYNTHETIC: with a level that rises 30 GWh a year, a prediction one year ahead uses the last training level."""
    d = synthetic(years=(2019, 2020, 2021, 2022), year_step=30.0)
    train, test = d[d.year < 2022], d[d.year == 2022]
    m = L.fit(train)
    err = (L.predict(m, test) - test.load_gwh.values).mean()
    assert abs(err + 30.0) < 1e-6, err


def test_backtest_does_not_see_the_test_year():
    d = L.load()
    d = d[d.year <= 2025]
    a = L.backtest(d, L.BASE, 2025)
    d2 = d.copy()
    d2.loc[d2.year == 2025, "load_gwh"] *= 1.5
    b = L.backtest(d2, L.BASE, 2025)
    assert (a["th"], a["tc"], a["bh"], a["bc"]) == (b["th"], b["tc"], b["bh"], b["bc"])
    assert b["rmse_model"] > 3 * a["rmse_model"]


def test_scenario_arithmetic_on_a_known_year():
    d = pd.DataFrame({"date": pd.date_range("2021-01-01", periods=365), "temp": np.r_[np.full(100, 0.0), np.full(165, 18.0), np.full(100, 30.0)],
                      "load_gwh": 0.0})
    got = L.scenario(None, d, 1.0, 10.0, 4.0, 15, 22)
    want = (-10.0 * 100 + 4.0 * 100) / (365 / 365.25)
    assert abs(got - want) < 1e-9, (got, want)


def test_block_index_blocks_are_contiguous_and_in_range():
    ix = L.block_index(1000, np.random.default_rng(0), 14)
    assert len(ix) == 1000 and ix.min() >= 0 and ix.max() <= 999
    blocks = ix[:994].reshape(-1, 14)
    assert (np.diff(blocks, axis=1) == 1).all()


def test_bootstrap_scenario_uses_the_same_draw_as_the_coefficients():
    """A scenario computed from a row's own coefficients must equal the row's scenario column."""
    d = L.load()
    d = d[d.year <= 2025].reset_index(drop=True)
    B = pd.read_csv(os.path.join(RES, "bootstrap.csv"))
    for _, r in B.head(25).iterrows():
        want = L.scenario(None, d, 1.0, r.bh, r.bc, r.th, r.tc)
        assert abs(want - r.warm1_gwh) < 1e-6 * max(1, abs(want)), (want, r.warm1_gwh)


def test_committed_daily_table_is_complete_and_plausible():
    d = pd.read_csv(os.path.join(DATA, "daily.csv"), parse_dates=["date"])
    assert d.date.is_unique and d.date.is_monotonic_increasing
    assert (d.date.diff().dropna() == pd.Timedelta(days=1)).all(), "a calendar day is missing"
    assert d.load_gwh.between(700, 1800).all(), d.load_gwh.describe()
    assert d.temp.between(-25, 40).all()
    g = d.set_index("date").load_gwh
    ratio = g["2019-03-31"] / g[["2019-03-24", "2019-04-07"]].mean()
    assert 0.90 < ratio < 1.0, f"the 23-hour Sunday should carry about 23/24 of a neighbouring Sunday, got {ratio:.3f}"


def test_city_weights_sum_to_one_and_temperature_is_their_weighted_mean():
    c = pd.read_csv(os.path.join(DATA, "cities.csv"), index_col=0)
    d = pd.read_csv(os.path.join(DATA, "daily.csv"))
    assert abs(c.weight.sum() - 1) < 1e-9
    w = (d[c.index] * c.weight.values).sum(axis=1)
    assert (w - d.temp).abs().max() < 2e-3


def test_headline_equals_a_fresh_fit_of_the_committed_data():
    d = L.load()
    d = d[d.year.isin(L.FIT_YEARS)].reset_index(drop=True)
    m = L.fit(d)
    j = json.load(open(os.path.join(RES, "loadtemp.json")))
    assert abs(m["bh"] - j["heating"]["gwh_per_hdd"]) < 1e-9 and (m["th"], m["tc"]) == (j["thresholds"]["th"], j["thresholds"]["tc"])
    lo, hi = j["heating"]["interval"]
    assert lo < m["bh"] < hi
    assert j["scenario_plus1"]["interval"][0] < j["scenario_plus1"]["gwh_per_year"] < j["scenario_plus1"]["interval"][1]


def test_every_sweep_row_has_a_negative_warming_effect():
    sw = pd.read_csv(os.path.join(RES, "sweep.csv"))
    assert (sw.warm1_gwh < 0).all(), sw[sw.warm1_gwh >= 0]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(f"{len(fns)} passed")
