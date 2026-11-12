"""Checks that fail loudly if the capture-rate arithmetic or the intervals break.

Arithmetic and resampling tests use small tables written for the test (labelled synthetic: they
exist to check the method against a known answer; nothing in results/ comes from them). The data
tests read the committed tables in data/ and results/, so they do not depend on the API's uptime.

    python3 tests/test_capture.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import capture as C
import prepare as P

DATA, RES = os.path.join(HERE, "..", "data"), os.path.join(HERE, "..", "results")


def row(**kw):
    base = {"n": 4, "P": 0.0, "Pf": 0.0, "L": 100.0}
    for t in C.TECHS:
        base.update({f"{t}_G": 0.0, f"{t}_GP": 0.0, f"{t}_GPf": 0.0, f"{t}_GPh": 0.0})
    base.update(kw)
    return base


def synthetic_weeks(years=(2019, 2020), n_blocks=8, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for y in years:
        for b in range(n_blocks):
            p = rng.uniform(20, 120, 4)
            g = rng.uniform(1, 50, 4)
            r = row(n=4, P=p.sum(), Pf=p.sum(), L=400.0)
            for t in C.TECHS:
                r.update({f"{t}_G": g.sum(), f"{t}_GP": (g * p).sum(), f"{t}_GPf": (g * p).sum(), f"{t}_GPh": (g * p).sum()})
            r.update(year=y, block=b, quarter=b * 4 // n_blocks)
            rows.append(r)
    return pd.DataFrame(rows)


def test_flat_profile_gives_capture_rate_one_not_a_price_level():
    s = row(P=400.0, SOLAR_G=40.0, SOLAR_GP=40.0 * 100.0)   # 4 quarters at 100, solar flat at 10
    assert abs(C.cr_of(s, "SOLAR") - 1.0) < 1e-12, "solar flat across hours must earn the baseload price"


def test_solar_in_the_cheap_hour_only_earns_less_than_baseload():
    # prices 100 then 0 (two quarters each), solar only in the first: earns 100, baseload 50
    s = row(n=2, P=100.0, SOLAR_G=10.0, SOLAR_GP=1000.0)
    assert abs(C.cr_of(s, "SOLAR") - 2.0) < 1e-12


def test_floor_changes_numerator_and_denominator_together():
    p, g = np.array([-10.0, 50.0, 60.0]), np.array([1.0, 1.0, 0.0])
    s = row(n=3, P=p.sum(), Pf=np.clip(p, 0, None).sum(), SOLAR_G=g.sum(), SOLAR_GP=(g * p).sum(),
            SOLAR_GPf=(g * np.clip(p, 0, None)).sum())
    assert abs(C.cr_of(s, "SOLAR") - 20.0 / (100.0 / 3)) < 1e-12
    assert abs(C.cr_of(s, "SOLAR", floor=True) - 25.0 / (110.0 / 3)) < 1e-12, "flooring only one side would bias the ratio"


def test_ols_recovers_an_exact_line_with_zero_standard_error():
    a, b, se, n = C.ols([1, 2, 3, 4], [5, 3, 1, -1])
    assert abs(b + 2) < 1e-12 and abs(a - 7) < 1e-12 and se < 1e-12 and n == 4


def test_ols_interval_is_wider_than_the_week_bootstrap_would_make_it_only_if_years_scatter():
    lo, hi = C.t_interval(-0.05, 0.02, 7)
    assert abs((hi - lo) / 2 - 2.571 * 0.02) < 1e-12, "seven years leave five degrees of freedom, not infinity"


def test_chunks_never_mix_years_or_quarters():
    W = synthetic_weeks()
    for unit_list in C.chunks(W, 1, True):
        keys = {(W.loc[i, "year"], W.loc[i, "quarter"]) for u in unit_list for i in u}
        assert len(keys) == 1, "a resampling stratum must hold one year and one quarter"
    assert sum(len(u) for ul in C.chunks(W, 1, True) for u in ul) == len(W)


def test_bootstrap_never_borrows_weeks_from_another_year():
    W = synthetic_weeks()
    first = W[W.year == 2019].iloc[0]
    for i in W.index[W.year == 2019]:                  # 2019: eight identical weeks, so every draw equals the census
        W.loc[i, first.index] = first.values
        W.loc[i, "block"] = i
    W.loc[W.year == 2020, ["P", "Pf"]] *= 10           # 2020 has a price level ten times higher
    CR, _ = C.bootstrap(W, [2019, 2020], draws=60)
    census = C.cr_of(W[W.year == 2019].sum(numeric_only=True), "SOLAR")
    assert np.allclose(CR[:, 0, 0], census), "a 2019 draw contained a week of another year"


def test_one_draw_of_weeks_serves_solar_and_wind_baseload_and_load():
    W = synthetic_weeks()                              # wind columns equal solar columns by construction
    CR, SH = C.bootstrap(W, [2019, 2020], draws=60)
    assert np.allclose(CR[:, :, 0], CR[:, :, 1]) and np.allclose(SH[:, :, 0], SH[:, :, 1]), \
        "solar and wind must see the same resampled weeks; independent draws would break this equality"


def test_bootstrap_keeps_the_seasonal_mix_when_stratified():
    W = synthetic_weeks(years=(2019,), n_blocks=8)
    W["P"] = W["quarter"] * 100.0 + 1.0                # price level fixed by quarter
    W = W.assign(SOLAR_G=1.0, SOLAR_GP=1.0)            # solar term constant, so cr = 1 / baseload
    CR, _ = C.bootstrap(W, [2019], draws=40, stratify=True)
    assert np.allclose(CR[:, 0, 0], CR[0, 0, 0]), "season mix, hence baseload, must be fixed in every stratified draw"
    CRu, _ = C.bootstrap(W, [2019], draws=40, stratify=False)
    assert CRu[:, 0, 0].std() > 0, "unstratified draws change the season mix; the test would pass vacuously otherwise"


def test_backtest_prediction_for_year_t_ignores_year_t_capture_rate():
    tab = pd.DataFrame([{"year": y, "tech": "SOLAR", "cr": 1.0 - 0.05 * (y - 2019), "share": 8.0 + (y - 2019)}
                        for y in C.YEARS])
    p1 = C.predict([2019, 2020, 2021], tab, "SOLAR", 2022)
    tab.loc[tab.year == 2022, "cr"] = 9.9
    assert C.predict([2019, 2020, 2021], tab, "SOLAR", 2022) == p1, "the test year's outcome leaked into its own forecast"
    assert abs(p1 - 0.85) < 1e-12


def test_backtest_trains_on_strictly_earlier_years():
    tab = pd.DataFrame([{"year": y, "tech": "SOLAR", "cr": 1.0 - 0.05 * (y - 2019), "share": 8.0 + (y - 2019)}
                        for y in C.YEARS])
    b = C.backtest(tab, "SOLAR")
    assert list(b["year"]) == [2022, 2023, 2024, 2025] and list(b["n_train"]) == [3, 4, 5, 6]
    assert np.allclose(b["err_slope_model"], 0), "an exact linear history must be forecast exactly"


def test_block_id_folds_day_366_into_the_last_block():
    t = pd.Series(pd.to_datetime(["2020-01-01", "2020-01-07", "2020-01-08", "2020-12-31"]).tz_localize("Europe/Berlin"))
    assert list(P.block_id(t)) == [0, 0, 1, 51]


def test_hourly_price_is_held_across_its_four_quarter_hours_and_quarter_prices_are_kept():
    pw = pd.DataFrame({"ts": [0, 900, 1800, 2700, 3600, 4500]})
    pr = pd.DataFrame({"ts": [0, 3600, 3600 + 900], "price": [10.0, 20.0, 30.0]})
    m = P.join_price(pw, pr)
    assert list(m["price"]) == [10.0, 10.0, 10.0, 10.0, 20.0, 30.0]


def test_missing_price_is_dropped_and_counted_not_filled():
    ts = list(range(1_600_000_000, 1_600_000_000 + 900 * 8, 900))
    pw = pd.DataFrame({"ts": ts, "solar": 1.0, "wind": 1.0, "woff": 1.0, "load": 10.0})
    pr = pd.DataFrame({"ts": [t for t in ts if t % 3600 == ts[0] % 3600][:1], "price": [5.0]})
    w, prof, q = P.build(pw, pr)
    assert q["rows_dropped_missing"] > 0 and w["n"].sum() == q["rows_power"] - q["rows_dropped_missing"]


def test_committed_weekly_table_is_complete_for_every_quarter_hour_of_each_year():
    W = pd.read_csv(os.path.join(DATA, "weekly.csv"))
    assert not W.isna().any().any()
    n = W.groupby("year")["n"].sum()
    for y in C.YEARS:
        assert n[y] == (35136 if y % 4 == 0 else 35040), f"year {y} is missing quarter-hours"


def test_2025_baseload_price_equals_the_published_annual_market_value():
    W = pd.read_csv(os.path.join(DATA, "weekly.csv"))
    jw = pd.read_csv(os.path.join(DATA, "market_value_jw.csv")).set_index("series")["ct_kwh"]
    s = W[W.year == 2025].sum(numeric_only=True)
    assert abs(s["P"] / s["n"] - 10 * jw["baseload"]) < 0.05, "my price base disagrees with the TSOs' published JW"


def test_published_results_match_a_recomputation_from_the_committed_table():
    W = pd.read_csv(os.path.join(DATA, "weekly.csv"))
    tab = C.annual_table(W, C.YEARS)
    s = tab[tab.tech == "SOLAR"]
    b = C.ols(s["share"], s["cr"])[1]
    out = json.load(open(os.path.join(RES, "capture.json")))
    assert abs(out["slope"]["SOLAR"]["slope"] - b) < 1e-9, "results/ is stale against data/"
    lo, hi = out["slope"]["SOLAR"]["boot_interval"]
    assert lo < b < hi


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:
                failed += 1
                print("FAIL", name, "->", repr(e))
    sys.exit(1 if failed else 0)
