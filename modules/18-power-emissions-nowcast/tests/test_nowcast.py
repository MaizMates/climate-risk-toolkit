"""Checks that fail loudly if the nowcast arithmetic, the information set or the interval break.

Tests marked SYNTHETIC build inputs here with a known answer: they check the method and nothing in results/
comes from them. The data tests read the committed tables in data/ and results/, so they need no API.

    python3 tests/test_nowcast.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import nowcast as N

DATA, RES = os.path.join(HERE, "..", "data"), os.path.join(HERE, "..", "results")
SEASON = np.array([1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.8, 0.8, 0.9, 1.0, 1.1, 1.3])
FAC = dict(zip(N.FOSSIL + N.CLEAN + ["Fossil", "Clean"], [1.0, 0.5, 0.7, 0.2, 0.02, 0.005, 0.02, 0.05, 0.01, 0.0, 0.0]))


def synth(years=range(2016, 2022), mix=lambda y, s: 1.0):
    """SYNTHETIC: each source has its own seasonal shape and its own level path, so the regression is identified;
    emissions = known factor x generation."""
    C, G = {}, {}
    for i, s in enumerate(N.FOSSIL + N.CLEAN):
        G[s] = pd.DataFrame({m: [100.0 * (1 + 0.1 * i) * (1 + 0.03 * (i + 1) * (-1) ** i * (y - 2016)) * np.roll(SEASON, i)[m - 1] * mix(y, s)
                                 for y in years] for m in range(1, 13)}, index=list(years))
        C[("gen", s)] = G[s]
    C[("emis", "Total generation")] = sum(FAC[s] * G[s] for s in G)
    C[("gen", "Fossil")] = sum(G[s] for s in N.FOSSIL)
    C[("gen", "Clean")] = sum(G[s] for s in N.CLEAN)
    return C


def cfg(**kw):
    return {**N.BASE, **kw}


def test_last_year_is_the_previous_calendar_year_total():
    C = synth(); T = C[("emis", "Total generation")]
    assert np.isclose(N.nowcasts(C, 2020, 6, cfg())["last year"], T.loc[2019].sum())


def test_share_of_year_is_exact_when_the_seasonal_shape_never_changes():
    # SYNTHETIC. Level grows each year but the shape is fixed, so YTD / mean share must equal the annual total
    T = pd.DataFrame({m: [(100.0 + 5 * k) * SEASON[m - 1] for k in range(6)] for m in range(1, 13)}, index=range(2016, 2022))
    for m in (3, 6, 9):
        assert np.isclose(N.m_share(T, 2020, m), T.loc[2020].sum()), m


def test_regression_recovers_known_factors_and_is_exact_on_a_stable_mix():
    # SYNTHETIC. Emissions are built from known factors; the fit has to return them
    C = synth(); T = C[("emis", "Total generation")]
    G = {s: C[("gen", s)] for s in N.FOSSIL + N.CLEAN}
    b, _ = N.fit_factors(T, G, N.FOSSIL + N.CLEAN, [2016, 2017, 2018])
    assert np.allclose(b, [FAC[s] for s in N.FOSSIL + N.CLEAN], atol=1e-6), b
    for m in (3, 6, 9):
        assert np.isclose(N.nowcasts(C, 2020, m, cfg())["regression"], T.loc[2020].sum()), m


def test_regression_follows_a_mix_shift_that_the_share_method_cannot_see():
    # SYNTHETIC. Coal doubles for the whole of 2020. Its year-to-date generation shows it and the scaled
    # projection carries it into the remaining months; the share rule reads the jump as a seasonal peak
    C = synth(mix=lambda y, s: 2.0 if (y == 2020 and s == "Coal") else 1.0); T = C[("emis", "Total generation")]
    a = T.loc[2020].sum()
    n = N.nowcasts(C, 2020, 6, cfg())
    assert abs(n["regression"] / a - 1) < 1e-9 and abs(n["share of year"] / a - 1) > 0.005, (n, a)


def test_no_nowcast_uses_data_after_month_m_of_the_nowcast_year_or_later_years():
    # leakage would make the backtest look better than the method is. Change everything the method may not see.
    C = synth(); base = N.nowcasts(C, 2019, 6, cfg())
    assert len(C[('emis', 'Total generation')]) == 6
    D = {k: v.copy() for k, v in C.items()}
    for k, v in D.items():
        v.loc[2019, 7:12] *= 3.0
        v.loc[2020:, :] *= 5.0
    assert N.nowcasts(D, 2019, 6, cfg()) == base


def test_training_years_before_the_backtest_start_are_only_the_years_that_exist():
    C = N.load(os.path.join(DATA, "eu_monthly.csv")); T = C[("emis", "Total generation")]
    assert N.train_years(T, 2018) == [2016, 2017]
    assert N.train_years(T, 2018, window=1) == [2017]
    assert N.train_years(T, 2022, exclude=(2020,)) == [2016, 2017, 2018, 2019, 2021]


def test_a_missing_month_raises_instead_of_giving_a_plausible_sum():
    T = pd.DataFrame({m: [1.0] for m in range(1, 13)}, index=[2020]); T.loc[2020, 5] = np.nan
    try:
        N.ytd(T, 2020, 6)
    except ValueError:
        return
    raise AssertionError("a NaN month passed into the year-to-date sum")


def test_student_t_quantile_matches_published_values():
    # 97.5th percentile, standard table: df 1 12.706, df 8 2.306, df 30 2.042
    for df, q in ((1, 12.706), (8, 2.306), (30, 2.042)):
        assert abs(N.t_quantile(0.975, df) - q) < 2e-3, (df, N.t_quantile(0.975, df))


def test_interval_is_relative_to_the_actual_and_widens_with_the_error():
    lo1, hi1 = N.interval(100.0, [0.01, -0.01, 0.02, -0.02])
    lo2, hi2 = N.interval(100.0, [0.05, -0.05, 0.08, -0.08])
    assert lo1 < 100 < hi1 and lo2 < lo1 and hi2 > hi1
    # an overestimate by 10% of the actual: N = 1.1 A, so A = N / 1.1 must be the value the interval would centre on
    e = 0.1
    assert abs(N.interval(110.0, [e, e, e])[0] - 110.0 / (1 + N.t_quantile(0.975, 3) * e)) < 1e-9
    try:
        N.interval(100.0, [0.9, -0.9])
    except ValueError:
        return
    raise AssertionError("an error scale above 100% produced a negative or infinite bound")


def test_bootstrap_draws_one_set_of_years_for_all_methods_and_horizons():
    rng = np.random.default_rng(0); e = rng.normal(size=(8, 1, 1))
    cube = np.repeat(np.repeat(e, 3, axis=1), 2, axis=2)          # three identical methods, two identical horizons
    d = N.bootstrap_rmse(cube, n=200, seed=1)
    assert np.allclose(d[:, 0, 0], d[:, 1, 0]) and np.allclose(d[:, 0, 0], d[:, 2, 1]), "years drawn separately per column"


def test_bootstrap_only_resamples_the_years_it_was_given():
    cube = np.zeros((8, 1, 1)); cube[3, 0, 0] = 0.1
    d = N.bootstrap_rmse(cube, n=500, seed=2)[:, 0, 0]
    assert set(np.round(d ** 2 * 8, 9)) <= set(np.round(np.arange(0, 9) * 0.01, 9)), "RMSE outside what 8 draws of one error give"


def test_relative_error_sign_overestimate_has_a_positive_sign():
    C = synth(); bt = N.backtest(C, cfg(), years=[2020], horizons=(6,))
    ly = bt[bt.method == "last year"].iloc[0]
    T = C[("emis", "Total generation")]
    assert np.sign(ly.rel_err) == np.sign(T.loc[2019].sum() - T.loc[2020].sum()) != 0
    assert np.isclose(ly.rel_err, T.loc[2019].sum() / T.loc[2020].sum() - 1)


# ---- committed data and results

def test_the_year_in_the_data_are_complete_for_2016_to_2025_and_partial_for_the_current_year():
    C = N.load(os.path.join(DATA, "eu_monthly.csv")); T = C[("emis", "Total generation")]
    assert N.complete_years(T) == list(range(2016, 2026))
    assert T.loc[2026].notna().sum() >= 9


def test_total_emissions_equal_the_sum_of_source_emissions_in_the_data():
    C = N.load(os.path.join(DATA, "eu_monthly.csv"))
    tot = C[("emis", "Total generation")].loc[2016:2025]
    parts = sum(C[("emis", s)].loc[2016:2025] for s in N.FOSSIL + N.CLEAN)
    assert ((tot - parts).abs() / tot).max().max() < 0.005


def test_committed_current_nowcast_reproduces_from_the_committed_data():
    C = N.load(os.path.join(DATA, "eu_monthly.csv"))
    cy, cur = N.current_year(C, N.BASE)
    r = pd.read_csv(os.path.join(RES, "nowcast_current.csv"))
    for k in N.METHODS:
        v = r[(r.method == k) & (r.horizon == 9)].nowcast.iloc[0]
        assert abs(v - cur[9][k]) < 1e-6, k
    assert cy == 2026


def test_committed_backtest_errors_are_nowcast_over_actual_minus_one_and_cover_2018_to_2025():
    bt = pd.read_csv(os.path.join(RES, "backtest.csv"))
    assert np.allclose(bt.rel_err, bt.nowcast / bt.actual - 1)
    assert sorted(bt.year.unique()) == list(range(2018, 2026)) and len(bt) == 8 * 3 * 4


def test_the_interval_method_covers_in_leave_one_year_out_at_close_to_its_level():
    cov = pd.read_csv(os.path.join(RES, "loo_coverage.csv"))
    assert cov.covered.mean() > 0.85, cov.covered.mean()


def test_current_year_interval_contains_its_own_nowcast_in_every_row():
    r = pd.read_csv(os.path.join(RES, "nowcast_current.csv"))
    assert ((r.lo < r.nowcast) & (r.nowcast < r.hi)).all()


if __name__ == "__main__":
    names = [n for n in dict(globals()) if n.startswith("test_")]
    for n in names:
        globals()[n]()
        print("ok  ", n)
    print(f"{len(names)} tests passed")
