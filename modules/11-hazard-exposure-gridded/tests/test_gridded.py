"""Checks that fail loudly if the grid join, the intervals or the HDF5 read break.

Fixed inputs, so they test arithmetic and not anyone's uptime. Two checks read the fetched data and
the results and say SKIPPED if those are absent; run src/fetch.py and src/gridded.py first.

    python3 tests/test_gridded.py
"""
import json
import os
import sys
import zlib

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import gridded as G
import h5lite


def tiny_grid(values=None, land=None):
    """A Grid without files: 0.25 degree cells over lat -90..90, lon -180..179.75, all zeros."""
    g = G.Grid.__new__(G.Grid)
    g.lat = np.arange(-90, 90.01, 0.25)
    g.lon = np.arange(-180, 180, 0.25)
    g.v = {}
    g.land = land
    return g, np.zeros((721, 1440)) if values is None else values


def test_unfilter_inverts_shuffle_and_deflate():
    """If the byte order after the shuffle filter is read wrong, every value is garbage that
    still looks like floats."""
    a = np.array([0.0, 1.5, 18.75, 338.1, 0.01, 7.25], dtype="<f4")
    shuffled = np.frombuffer(a.tobytes(), np.uint8).reshape(-1, 4).T.tobytes()
    assert np.array_equal(h5lite.unfilter(zlib.compress(shuffled), 4), a)


def test_grid_index_is_latitude_ascending_and_rounds_to_nearest_centre():
    """The file runs south to north. A flipped latitude axis puts Madrid in Antarctica."""
    g, _ = tiny_grid()
    i, j = g.index(np.array([-90.0, 40.4, 40.37]), np.array([-180.0, -3.7, -3.6]))
    assert i[0] == 0, "-90 must be row 0"
    assert abs(g.lat[i[1]] - 40.5) < 1e-9 and abs(g.lon[j[1]] - (-3.75)) < 1e-9, "40.4N 3.7W is cell 40.5N 3.75W"
    assert g.index(0.0, 179.8)[1] == 1439 and g.index(0.0, 180.0)[1] == 0, "longitude must wrap"


def test_radius_zero_takes_containing_cell_and_radius_averages_neighbours_inside_only():
    g, f = tiny_grid()
    i, j = g.index(45.0, 10.0)
    f[i, j] = 10.0
    f[i, j + 1] = 20.0            # 0.25 deg east, about 19.7 km at 45N
    f[i, j + 4] = 1000.0          # 1 degree east, about 79 km: must stay outside a 25 km radius
    v0, _ = g.plant_values(f, [45.0], [10.0], 0)
    v25, _ = g.plant_values(f, [45.0], [10.0], 25)
    assert v0[0] == 10.0
    # at 45N a cell is 19.7 km wide and 27.8 km tall: within 25 km sit the centre and its east and
    # west neighbours (10, 20, 0); the cells north and south (27.8 km) and the 79 km one stay out
    assert abs(v25[0] - 10.0) < 1e-9, f"radius mean must use exactly the cells within 25 km, got {v25[0]}"


def test_land_only_skips_sea_cells_and_falls_back_when_none_is_left():
    g, f = tiny_grid()
    i, j = g.index(45.0, 10.0)
    land = np.zeros((11, 11), bool)
    i0, j0 = i - 5, j - 5
    land[5, 6] = True                      # one land cell, east of the plant
    g.land = (land, i0, j0)
    f[i, j], f[i, j + 1] = 0.0, 8.0
    v, fb = g.plant_values(f, [45.0], [10.0], 25, land_only=True)
    assert v[0] == 8.0 and fb == 0, "sea cells must not dilute a coastal plant's value"
    g.land = (np.zeros((11, 11), bool), i0, j0)
    v, fb = g.plant_values(f, [45.0], [10.0], 25, land_only=True)
    assert fb == 1 and v[0] == 0.0, "no land cell in range must fall back to the nearest cell, and say so"


def test_block_mean_and_block_lookup():
    g, f = tiny_grid()
    f[:2, :2] = np.array([[0, 2], [4, 6]])
    assert g.coarsened(f, 2)[0, 0] == 3.0
    assert g.plant_block_values(f, [-89.9], [-179.9], 2)[0] == 3.0


def test_exceeds_is_strict():
    assert list(G.exceeds([1.99, 2.0, 2.01], 2)) == [False, False, True], "exactly k is not 'more than k'"


def test_exposed_share_is_mw_weighted():
    cap = np.array([900.0, 100.0, 100.0, 100.0])
    assert abs(G.exposed_share(cap, np.array([True, False, False, False])) - 900 / 1200) < 1e-12


def test_points_in_polygon_respects_holes_and_even_odd():
    outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    x, y = np.array([1.0, 5.0, 11.0]), np.array([1.0, 5.0, 5.0])
    assert list(G.points_in_polygon(x, y, [outer, hole])) == [True, False, False]


def test_distance_to_country_is_zero_inside_and_about_right_outside():
    sq = [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
    assert G.distance_to_country_km(0.5, 0.5, [sq]) == 0.0
    d = G.distance_to_country_km(0.5, 1.1, [sq])        # 0.1 degree east of the east edge at 0.5N
    assert 10.5 < d < 11.5, f"0.1 degree of longitude at the equator is 11.1 km, got {d}"


def test_overseas_parts_are_not_european():
    assert G.in_europe([[[0, 40], [1, 40], [1, 41], [0, 41], [0, 40]]])
    assert not G.in_europe([[[-54, 4], [-53, 4], [-53, 5], [-54, 5], [-54, 4]]]), "French Guiana is not metropolitan France"


def test_coordinate_qa_repairs_a_swap_and_drops_a_typo():
    """The WRI file has a latitude and longitude swapped (Garona Verda) and a latitude typo
    (Escombreras 7.57 for 37.57). A swap is recoverable from the country polygon, a typo is not."""
    ne = {"features": [{"properties": {"ADM0_A3": "ESP", "ISO_A3_EH": "ESP"}, "geometry": {
        "type": "MultiPolygon", "coordinates": [[[[-9, 36], [3, 36], [3, 44], [-9, 44], [-9, 36]]]]}}]}
    plants = pd.DataFrame([
        {"country": "ESP", "name": "ok", "capacity_mw": 1.0, "lat": 40.0, "lon": -3.0},
        {"country": "ESP", "name": "swap", "capacity_mw": 1.0, "lat": 0.7, "lon": 42.0},
        {"country": "ESP", "name": "typo", "capacity_mw": 1.0, "lat": 7.57, "lon": -0.94}])
    old = G.COUNTRIES
    G.COUNTRIES = ["ESP"]
    try:
        out = G.coordinate_qa(plants, ne)
    finally:
        G.COUNTRIES = old
    assert list(out.qa) == ["ok", "swapped", "dropped"]
    assert (out.lat_used[1], out.lon_used[1]) == (42.0, 0.7)


def test_paired_bootstrap_difference_of_identical_vectors_is_exactly_zero():
    """Differences must come from the same resample, or the interval on 'grid minus country'
    is the sum of two independent noises and is wrong."""
    cap = np.array([5.0, 3.0, 9.0, 1.0, 7.0])
    e = np.array([True, False, True, False, True])
    b = G.paired_bootstrap(cap, {"a": e, "b": e.copy()}, n=200, seed=1)
    assert np.all(b["a"] - b["b"] == 0.0)


def test_site_bootstrap_is_wider_than_plant_bootstrap_when_units_share_a_site():
    """Twenty units on two sites are two draws, not twenty. Resampling units as if independent
    understates the interval; this fails if the grouping is ignored."""
    cap = np.full(20, 10.0)
    e = np.array([True] * 10 + [False] * 10)
    site = ["A"] * 10 + ["B"] * 10
    w_site = np.ptp(G.ci(G.paired_bootstrap(cap, {"x": e}, site, n=2000, seed=2)["x"]))
    w_unit = np.ptp(G.ci(G.paired_bootstrap(cap, {"x": e}, None, n=2000, seed=2)["x"]))
    assert w_site > 2 * w_unit, (w_site, w_unit)


def test_spearman_handles_ties_and_a_flat_series_is_nan_not_one():
    assert abs(G.spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-12
    assert abs(G.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-12
    assert np.isnan(G.spearman([0, 0, 0], [1, 2, 3])), "a constant series has no rank correlation"


def test_top_n_share_uses_only_exposed_plants():
    cap = np.array([100.0, 50.0, 10.0, 1000.0])
    ex = np.array([True, True, True, False])
    assert abs(G.top_n_share(cap, ex, 1) - 100 / 160) < 1e-12


def test_real_file_read_matches_the_cckp_country_api():
    raw = os.path.join(HERE, "..", "data", "raw")
    api = os.path.join(raw, "cckp_country_api.json")
    if not (os.path.exists(os.path.join(raw, "grid_hist_median.nc")) and os.path.exists(api)):
        print("  SKIPPED test_real_file_read_matches_the_cckp_country_api: run src/fetch.py first")
        return
    res = json.load(open(os.path.join(HERE, "..", "results", "gridded.json")))
    assert res["validation_grid_vs_api"]["max_abs_diff_days"] < 0.25, "grid read no longer reproduces the API"
    h = h5lite.H5(open(os.path.join(raw, "grid_hist_median.nc"), "rb").read())
    v = h.var("climatology-hd35-annual-mean")[0]
    assert v.shape == (721, 1440) and np.isfinite(v).all() and v.min() >= 0 and v.max() < 366


def test_results_headline_matches_a_recomputation_from_plants_csv():
    p = os.path.join(HERE, "..", "results", "plants.csv")
    r = os.path.join(HERE, "..", "results", "gridded.json")
    if not (os.path.exists(p) and os.path.exists(r)):
        print("  SKIPPED test_results_headline_matches_a_recomputation_from_plants_csv: run src/gridded.py first")
        return
    d, ref = pd.read_csv(p), json.load(open(r))["reference"]
    share = d.capacity_mw[d.cell_change > 2].sum() / d.capacity_mw.sum()
    assert abs(share - ref["grid_share"]) < 1e-9
    share_c = d.capacity_mw[d.country_change > 2].sum() / d.capacity_mw.sum()
    assert abs(share_c - ref["country_share"]) < 1e-9


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:
                fails += 1
                print("FAIL", name, "->", repr(e))
    sys.exit(1 if fails else 0)
