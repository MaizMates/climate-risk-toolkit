"""Arithmetic and interval checks on fixed inputs. Run: python3 tests/test_financed.py"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import financed as f  # noqa: E402

CFG = dict(f.BASE)


def test_attribution_uses_equity_plus_debt_not_debt_alone():
    assert abs(f.attribution_factor(10, 30, 70) - 0.10) < 1e-12
    assert f.attribution_factor(10, 30, 70) != f.attribution_factor(10, 0, 70)


def test_wdqs_weights_by_outstanding_not_by_line_count():
    assert abs(f.wdqs([2, 5], [90, 10]) - 2.3) < 1e-12
    assert f.wdqs([2, 5], [90, 10]) != 3.5


def test_scores_go_to_the_largest_revenues_first_and_counts_follow_the_mix():
    s = f.assign_scores([5, 100, 1, 50, 10, 20, 30, 40, 2, 3], (0.2, 0.5, 0.3))
    assert list(np.flatnonzero(s == 2)) == [1, 3]
    assert (s == 4).sum() == 5 and (s == 5).sum() == 3


def test_ratio_factor_is_the_sector_intensity_not_the_mean_of_firm_intensities():
    e, x = np.array([1.0, 100.0]), np.array([1.0, 10.0])
    assert abs(f.factor(e, x, "ratio") - 101 / 11) < 1e-12
    assert abs(f.factor(e, x, "median") - 5.5) < 1e-12


def test_group_falls_back_to_pooled_when_too_few_peers_and_uses_finer_level_when_enough():
    pool = np.array(["4911", "4911", "4911", "4931", "2800", "2800"])
    g = f.resolve_groups(pool, ["4911", "2899", "7000"], 3, 3)
    assert g[0][0] == "3:491" and len(g[0][1]) == 3
    assert g[1][0] == "pooled" and len(g[2][1]) == 6
    g2 = f.resolve_groups(pool, ["4911"], 2, 5)
    assert g2[0][0] == "pooled"


def _fixture(n_book_lines, scores, book_e=1e6):
    pool = pd.DataFrame({"scope1_t": [10., 20., 40., 80.], "revenue": [1e3] * 4, "assets": [2e3] * 4,
                         "sic": ["4911"] * 4})
    book = pd.DataFrame({"scope1_t": [book_e] * n_book_lines, "revenue": [1e3] * n_book_lines,
                         "assets": [2e3] * n_book_lines, "sic": ["4911"] * n_book_lines,
                         "score": scores, "af": [0.1] * n_book_lines})
    return book, pool


class CountingRng:
    def __init__(self, seed):
        self.r, self.shapes = np.random.default_rng(seed), []

    def integers(self, lo, hi, size):
        self.shapes.append(size)
        return self.r.integers(lo, hi, size)


def test_sector_factor_error_is_drawn_once_per_group_not_once_per_line():
    book, pool = _fixture(3, [4, 4, 4])
    rng = CountingRng(1)
    f.interval(book, pool, {**CFG, "min_peers": 3}, rng, 50)
    assert rng.shapes == [(50, 4), (50, 3)], rng.shapes


def test_interval_does_not_resample_the_book_it_estimates():
    cfg = {**CFG, "min_peers": 3}
    a, pool = _fixture(3, [4, 5, 4], book_e=1.0)
    b, _ = _fixture(3, [4, 5, 4], book_e=1e9)
    da = f.interval(a, pool, cfg, np.random.default_rng(5), 200)
    db = f.interval(b, pool, cfg, np.random.default_rng(5), 200)
    assert np.allclose(da, db)


def test_reported_lines_carry_no_uncertainty_and_equal_the_truth():
    book, pool = _fixture(3, [2, 2, 2])
    d = f.interval(book, pool, {**CFG, "min_peers": 3}, np.random.default_rng(0), 100)
    assert d.min() == d.max() == (book.af * book.scope1_t).sum()


def test_lines_in_one_group_share_the_factor_draw_so_their_errors_do_not_average_out():
    book, pool = _fixture(8, [4] * 8)
    pool["scope1_t"] = [10., 10., 10., 10.]   # every peer identical: only the factor draw could vary
    d = f.interval(book, pool, {**CFG, "min_peers": 3}, np.random.default_rng(0), 100)
    assert np.ptp(d) < 1e-9
    pool["scope1_t"] = [10., 20., 40., 80.]
    d = f.interval(book, pool, {**CFG, "min_peers": 3}, np.random.default_rng(0), 4000)
    one = f.interval(book.iloc[:1], pool, {**CFG, "min_peers": 3}, np.random.default_rng(0), 4000)
    assert d.std() / d.mean() > one.std() / one.mean() * 0.5   # eight lines keep far more than 1/sqrt(8) of the spread


def test_population_filter_drops_nonpositive_equity_and_missing_sic():
    rows = [dict(year=2023, key="a", name="A", cik=1, scope1_t=5, naics="1", sic="4911", n_facilities=1,
                 fy_end="2023-12-31", revenue=10, assets=20, equity=5, debt=5),
            dict(year=2023, key="b", name="B", cik=2, scope1_t=5, naics="1", sic="4911", n_facilities=1,
                 fy_end="2023-12-31", revenue=10, assets=20, equity=-5, debt=5),
            dict(year=2023, key="c", name="C", cik=3, scope1_t=5, naics="1", sic=None, n_facilities=1,
                 fy_end="2023-12-31", revenue=10, assets=20, equity=5, debt=5)]
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "b.csv")
        pd.DataFrame(rows).to_csv(p, index=False)
        pop, n0 = f.load_population(2023, p)
    assert n0 == 3 and list(pop.name) == ["A"]


def test_headline_book_reproduces_and_estimates_never_below_zero():
    pop, _ = f.load_population(2023)
    a = f.run_book(pop, 7, CFG)
    b = f.run_book(pop, 7, CFG)
    assert a["fe_est"] == b["fe_est"] and (a["est"] > 0).all()
    assert (a["book"].af <= 1).all()


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            n += 1
            print("ok", k)
    print(n, "tests passed")
