"""Checks that fail loudly if the scenario-to-PD arithmetic, the fetched-coefficient parser or the
intervals break. Fixed inputs, so this tests the arithmetic and not anyone's uptime.

    python3 tests/test_scenario_pd.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import scenario_pd as S


def test_cost_share_is_price_times_tonnes_per_million_over_a_million():
    """EUR 100 per tonne on 500 t per EUR million of value added is 5% of value added. A missing
    1e6 would put the carbon bill at 50,000 times the sector's output."""
    assert abs(S.cost_share(100.0, 500.0) - 0.05) < 1e-12


def test_full_pass_through_leaves_profit_untouched_and_none_takes_the_whole_bill():
    assert S.delta_profit(0.05, 1.0) == 0.0
    assert abs(S.delta_profit(0.05, 0.0) + 0.05) < 1e-12
    assert abs(S.delta_profit(0.05, 0.7) + 0.015) < 1e-12


def test_logodds_rise_when_profit_falls_and_the_annual_change_is_quartered():
    """coef is on quarterly NI over assets: -20 x (-0.10 x 0.4 / 4) = +0.2. A sign slip or a
    missing /4 gives -0.2 or 0.8, both plausible-looking."""
    assert abs(S.delta_logodds(-0.10, 0.4, -20.0) - 0.2) < 1e-12
    assert abs(S.delta_logodds(-0.10, 0.4, -20.0, assets_scale=2.0) - 0.1) < 1e-12


def test_pd_after_is_unchanged_by_zero_shift_and_stays_inside_zero_one():
    assert abs(S.pd_after(0.02, 0.0) - 0.02) < 1e-12
    assert 0.02 < S.pd_after(0.02, 1.0) < 1.0
    assert 0.0 <= S.pd_after(0.02, -900.0) < 1e-12, "a very negative shift must not overflow"
    assert abs(S.pd_after(0.5, 0.0) - 0.5) < 1e-12


def test_price_conversion_goes_through_the_2010_exchange_rate_then_the_deflator():
    p = S.price_eur(100.0, {2010: 2.0}, {2010: 100.0, 2022: 150.0}, 2022)
    assert abs(p - 75.0) < 1e-12, "100 USD / 2.0 = 50 EUR in 2010 prices; x1.5 = 75 EUR in 2022"


def test_abatement_factor_is_floored_at_zero_for_negative_emissions():
    v = "Emissions|CO2|Energy and Industrial Processes"
    NG = {("M", "s", v, 2020): 1000.0, ("M", "s", v, 2040): -95.0, ("M", "t", v, 2020): 1000.0,
          ("M", "t", v, 2040): 250.0}
    assert S.abatement_factor(NG, "M", "s", 2040) == 0.0, "net-negative emissions are not a negative carbon bill"
    assert abs(S.abatement_factor(NG, "M", "t", 2040) - 0.25) < 1e-12


def _world(price_dis, price_ord):
    NG = {("M", "dis", "Price|Carbon", 2040): price_dis, ("M", "ord", "Price|Carbon", 2040): price_ord}
    T = {"fx": {2010: 1.0}, "hicp": {2010: 100.0, 2022: 100.0}}
    st = {"co2_per_gva": 500.0, "ghg_per_gva": 600.0, "gva_over_k": 0.4}
    cfg = {"model": "M", "disorderly": "dis", "orderly": "ord", "year": 2040, "gas": "CO2",
           "abatement": False, "ref_year": 2022, "pass_through": 0.5, "assets_scale": 1.0, "pd0": 0.02}
    return NG, T, st, cfg


def test_pair_change_is_positive_when_the_disorderly_price_is_higher_and_flips_when_swapped():
    NG, T, st, cfg = _world(400.0, 100.0)
    up = S.pair_change(NG, T, st, cfg, coef=-20.0)["rel"]
    NG2, _, _, _ = _world(100.0, 400.0)
    down = S.pair_change(NG2, T, st, cfg, coef=-20.0)["rel"]
    assert up > 0 > down
    assert S.pair_change(*_world(100.0, 100.0)[:3], _world(1, 1)[3], coef=-20.0)["rel"] == 0.0


def test_pair_change_matches_a_hand_calculation():
    """400 EUR x 500 t = 0.2 of GVA; half passed on: -0.1; x0.4/4 x -20 = +0.2 log-odds."""
    NG, T, st, cfg = _world(400.0, 0.0)
    r = S.pair_change(NG, T, st, cfg, coef=-20.0)
    assert abs(r["dl_dis"] - 0.2) < 1e-12 and r["dl_ord"] == 0.0


def test_parse_chs_reads_the_row_and_refuses_a_page_without_it():
    lines = ["Table 3", "NIMTAAVG", "-29.672 -23.915 -20.264 -13.232 -14.061",
             "\\(23.37\\)** \\(21.82\\)** \\(18.09\\)** \\(10.50\\)** \\(9.77\\)**", "TLMTA"]
    r = S.parse_chs(lines)
    assert r["coef"][2] == -20.264 and r["lags"][2] == 12
    assert abs(r["se"][2] - 20.264 / 18.09) < 1e-9
    try:
        S.parse_chs(["nothing here"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("a layout change must raise, not return a stale number")
    try:
        S.parse_chs(["NIMTAAVG", "29.672 23.915 20.264 13.232 14.061", lines[3]])
    except RuntimeError:
        pass
    else:
        raise AssertionError("positive coefficients mean the wrong row was read")


def test_jsonstat_flattening_uses_row_major_order_with_unequal_dimensions():
    doc = {"id": ["geo", "time"], "size": [2, 3],
           "dimension": {"geo": {"category": {"index": {"AT": 0, "BE": 1}}},
                         "time": {"category": {"index": {"2020": 0, "2021": 1, "2022": 2}}}},
           "value": {"0": 1.0, "4": 5.0, "5": 6.0}}
    rows = {(c["geo"], c["time"]): v for c, v in S.jsonstat_rows(doc)}
    assert rows == {("AT", "2020"): 1.0, ("BE", "2021"): 5.0, ("BE", "2022"): 6.0}


def test_aggregate_is_a_ratio_of_sums_not_a_mean_of_ratios():
    T = {"a64": {}, "air": {}, "nfa": {}}
    for geo, gva, comp, co2 in (("AT", 1000.0, 400.0, 100.0), ("BE", 100.0, 80.0, 50.0)):
        T["a64"][(geo, "X", 2020, "B1G")] = gva; T["a64"][(geo, "X", 2020, "D1")] = comp
        T["nfa"][(geo, "X", 2020)] = gva * 2; T["air"][(geo, "X", 2020, "CO2")] = co2
        T["air"][(geo, "X", 2020, "GHG")] = co2
    a = S.aggregate(T, ["X"], 2020, geos=["AT", "BE"])
    assert abs(a["co2_per_gva"] - 150.0 / 1100.0 * 1.0) < 1e-12
    assert abs(a["profit_share"] - (1 - 480.0 / 1100.0)) < 1e-12
    assert S.aggregate(T, ["X"], 2021, geos=["AT"]) is None


def test_reference_year_is_the_latest_year_with_enough_countries():
    T = {"a64": {}, "air": {}, "nfa": {}}
    geos = S.EU27[:26]
    for y, n in ((2021, 26), (2022, 26), (2023, 25)):
        for g in geos[:n]:
            for c in S.SECTORS["B-E"]:
                T["a64"][(g, c, y, "B1G")] = 10.0; T["a64"][(g, c, y, "D1")] = 5.0
                T["nfa"][(g, c, y)] = 20.0
                T["air"][(g, c, y, "CO2")] = 1.0; T["air"][(g, c, y, "GHG")] = 1.0
    assert S.reference_year(T) == 2022, "2023 has 25 countries and must not be chosen"


def test_fit_beta_recovers_a_known_slope_through_country_and_sector_year_effects():
    rng = np.random.default_rng(3)
    rows = []
    for gi, g in enumerate(S.EU27[:12]):
        for s in ("B-E", "F", "G"):
            for y in range(2016, 2024):
                x = rng.normal(0, 3)
                rows.append({"geo": g, "sector": s, "year": y, "dps": x,
                             "dlnb": -0.02 * x + 0.1 * gi + 0.3 * (y - 2016) + rng.normal(0, 0.05)})
    assert abs(S.fit_beta(rows) + 0.02) < 0.003


def test_cluster_resample_keeps_a_country_drawn_twice_as_two_clusters():
    rows = [{"geo": g, "x": i} for i, g in enumerate("AABBCC")]
    out = S.cluster_resample(rows, np.random.default_rng(0))
    labels = {r["geo"] for r in out}
    assert len(out) == 6 and len(labels) == 3, "three draws of two rows, each draw its own cluster"


def test_demean_drops_groups_too_small_to_demean():
    rows = [{"sector": "a", "year": 1}] * 3 + [{"sector": "b", "year": 1}] * 2
    out, keep = S.demean_groups(rows, np.array([1.0, 2.0, 3.0, 10.0, 20.0]))
    assert list(keep) == [True] * 3 + [False] * 2 and abs(out[:3].sum()) < 1e-12


def test_calibration_slope_recovers_half_and_the_interval_contains_it():
    rng = np.random.default_rng(1)
    pred = rng.normal(0, 1, 400)
    y = 0.5 * pred + rng.normal(0, 0.2, 400)
    geo = np.array([S.EU27[i % 20] for i in range(400)])
    s, (lo, hi) = S.calibration_slope(y, pred, geo, n=300)
    assert abs(s - 0.5) < 0.05 and lo < 0.5 < hi


def test_one_coefficient_draw_is_shared_by_every_sector():
    """If each sector had its own draw, the ratio of two sectors' log-shifts would vary from
    replicate to replicate. A shared draw keeps it fixed."""
    NG, T, st, cfg = _world(30.0, 0.0)
    cfg["pd0"] = 1e-6
    st2 = {**st, "co2_per_gva": 125.0}
    chs = {"coef": [-29.0, -24.0, -20.0, -13.0, -14.0], "se": [1.2, 1.1, 1.1, 1.2, 1.4]}
    draws, coef = S.mc_literature(NG, T, {"a": st, "b": st2}, cfg, chs, n=200)
    ratio = np.log1p(draws["a"]) / np.log1p(draws["b"])
    assert np.std(ratio) < 1e-3 and abs(ratio.mean() - 4.0) < 1e-2
    assert coef.min() < -25 and coef.max() > -16, "the draws must spread over the reported horizons"


def test_spearman_of_identical_reversed_and_tied_rankings():
    assert abs(S.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1) < 1e-9
    assert abs(S.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-9
    assert abs(S.spearman([1, 1, 2, 3], [1, 1, 2, 3]) - 1) < 1e-9


if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
