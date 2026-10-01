"""Arithmetic checks on fixed inputs. Run as: python3 tests/test_flood_depth_damage.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flood_depth_damage import (
    damage_fraction, expected_annual_damage, parse_curves, portfolio_mean, bootstrap_ci,
    build_portfolio, RasterGrid,
)

DEPTHS = [0.0, 0.05, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 12.0]
INFRA = [0.0, 0.0, 0.25, 0.42, 0.55, 0.65, 0.8, 0.9, 1.0, 1.0, 1.0]

passed = 0


def check(name, cond):
    global passed
    assert cond, f"FAILED: {name}"
    passed += 1
    print(f"ok: {name}")


# --- damage_fraction ---------------------------------------------------------

check("damage_fraction: zero depth has zero damage",
      damage_fraction(0.0, DEPTHS, INFRA) == 0.0)

check("damage_fraction: negative depth (should never happen post-nodata-screen) is zero too",
      damage_fraction(-1.0, DEPTHS, INFRA) == 0.0)

check("damage_fraction: exact breakpoint returns the published value exactly",
      damage_fraction(1.0, DEPTHS, INFRA) == 0.42)

check("damage_fraction: halfway between 1.0m (0.42) and 1.5m (0.55) interpolates linearly",
      abs(damage_fraction(1.25, DEPTHS, INFRA) - 0.485) < 1e-9)

check("damage_fraction: depth far beyond the curve's last breakpoint clips to 1.0, not "
      "extrapolates past it",
      damage_fraction(50.0, DEPTHS, INFRA) == 1.0)

# --- expected_annual_damage ---------------------------------------------------

check("expected_annual_damage: no depth at any return period gives zero EAD",
      expected_annual_damage({10: 0.0, 100: 0.0, 500: 0.0}, DEPTHS, INFRA) == 0.0)

# Single return period at a depth saturating the curve (damage=1.0): by hand, with the p=1,
# damage=0 anchor, EAD = trapezoid((p=1,d=0), (p=0.1,d=1)) = 0.5*(0+1)*(1-0.1) = 0.45.
ead_one_point = expected_annual_damage({10: 50.0}, DEPTHS, INFRA)
check("expected_annual_damage: single saturated return period matches the hand-computed "
      f"trapezoid (got {ead_one_point:.6f}, expected 0.45)",
      abs(ead_one_point - 0.45) < 1e-9)

# The edge case that would silently produce a plausible-looking wrong answer: without the p=1
# anchor, all the probability mass between "every year" and the rarest tabulated return period
# is simply dropped, not spread in some other way -- this must shrink the number, never grow it.
ead_no_anchor = expected_annual_damage({10: 50.0}, DEPTHS, INFRA, anchor_zero=False)
check("expected_annual_damage: dropping the p=1 anchor must not increase EAD, and with only "
      "one point and no anchor there is nothing to integrate, so EAD is exactly zero",
      ead_no_anchor == 0.0 and ead_no_anchor < ead_one_point)

# Flat damage beyond the rarest point adds exactly the extra rectangle's worth of probability.
ead_flat = expected_annual_damage({10: 50.0}, DEPTHS, INFRA, tail_flat=True)
check("expected_annual_damage: a flat tail below the rarest return period adds p_min * damage "
      "to the truncated integral",
      abs(ead_flat - (0.45 + 0.1 * 1.0)) < 1e-9)

# Monotonicity: more depth can never produce less damage, so EAD must be monotonic in depth too.
ead_shallow = expected_annual_damage({10: 0.3}, DEPTHS, INFRA)
ead_deeper = expected_annual_damage({10: 1.5}, DEPTHS, INFRA)
check("expected_annual_damage: EAD increases when the input depth increases",
      ead_deeper > ead_shallow)

# --- portfolio_mean / bootstrap_ci --------------------------------------------

locs = [{"capacity_mw": 100.0, "ead": 0.01}, {"capacity_mw": 300.0, "ead": 0.00}]
check("portfolio_mean: capacity-weighted, not a plain average "
      "(300MW at 0% should pull the mean well below the midpoint of 0% and 1%)",
      abs(portfolio_mean(locs) - (100.0 * 0.01) / 400.0) < 1e-12)

check("portfolio_mean: an all-zero-capacity portfolio returns None rather than dividing by zero",
      portfolio_mean([{"capacity_mw": 0.0, "ead": 0.5}]) is None)


def stat_mean(sample, rng):
    return portfolio_mean(sample)


lo, hi = bootstrap_ci(locs * 20, stat_mean, n=500, seed=1)
check("bootstrap_ci: the interval brackets the point estimate",
      lo <= portfolio_mean(locs * 20) <= hi)

# --- parse_curves: a miniature stand-in for CLIMADA's river_flood.py source ---------------

FAKE_SOURCE = '''
def from_jrc_impf_residential(region):
    return _from_jrc_impf(
        region=region,
        sector="Residential",
        impf_values_map={
            "europe":       [0., 0.,    0.25,  0.4,   0.5,   0.6,   0.75,  0.85,  0.95,  1., 1.],
        }
    )


def from_jrc_impf_infrastructure(region):
    return _from_jrc_impf(
        region=region,
        sector="Infrastructure",
        impf_values_map={
            "europe": [0., 0., 0.25, 0.42, 0.55, 0.65, 0.8, 0.9, 1., 1., 1.],
        }
    )

impf.intensity = np.array([0., 0.05, 0.5, 1., 1.5, 2., 3., 4., 5., 6., 12.])
'''

parsed_depths, parsed_curves = parse_curves(FAKE_SOURCE)
check("parse_curves: depth breakpoints parsed out of the source text, not retyped",
      parsed_depths == DEPTHS)
check("parse_curves: the infrastructure Europe curve is parsed out of its own function block, "
      "not the residential block that happens to come first in the file",
      parsed_curves["infrastructure"] == INFRA)

# --- RasterGrid pixel/tile arithmetic (no network: metadata set directly) -----------------

g = RasterGrid.__new__(RasterGrid)
g.width, g.length = 110162, 51992
g.tile_w, g.tile_h = 256, 256
g.n_tiles_x = -(-g.width // g.tile_w)
g.scale_x = g.scale_y = 0.0008333333333333334
g.origin_lon, g.origin_lat = -24.54208333, 71.13375
g.endian = "<"
g.dtype_char, g.dtype_size = "f", 4
g._tile_cache = {}

col, row = g.pixel_of(g.origin_lon, g.origin_lat)
check("RasterGrid.pixel_of: the tiepoint itself maps to pixel (0, 0)",
      abs(col) < 1e-9 and abs(row) < 1e-9)

check("RasterGrid.in_bounds: a point far outside the raster's extent (mid-Atlantic) is out of "
      "bounds, which must resolve to zero depth rather than an index error",
      not g.in_bounds(-40.0, 71.0))

check("RasterGrid.tile_index_of: pixel (300, 0), one tile-width past the origin, lands in tile "
      "column 1, not tile column 0",
      g.tile_index_of(300, 0) == 1)

g._tile_cache[0] = None  # sparse tile: JRC's own encoding for "entirely nodata"
check("RasterGrid.value_at: a sparse (all-nodata) tile reads as zero depth, not nodata or NaN",
      g.value_at(g.origin_lon + 0.0001, g.origin_lat - 0.0001) == 0.0)

tile = [0.0] * (256 * 256)
tile[5 * 256 + 7] = 2.5
tile[5 * 256 + 8] = -9999.0
g._tile_cache[0] = tile
lon_a = g.origin_lon + 7 * g.scale_x + 1e-7
lat_a = g.origin_lat - 5 * g.scale_y - 1e-7
check("RasterGrid.value_at: reads the correct pixel out of a decoded tile",
      abs(g.value_at(lon_a, lat_a) - 2.5) < 1e-6)
lon_b = g.origin_lon + 8 * g.scale_x + 1e-7
check("RasterGrid.value_at: the -9999 nodata sentinel reads as zero, not as -9999m of water",
      g.value_at(lon_b, lat_a) == 0.0)

# --- build_portfolio: hydro exclusion and the top-N-per-country rule -----------------------

wri_rows = [
    {"country": "DEU", "name": "Big Hydro", "capacity_mw": "900", "latitude": "50.0",
     "longitude": "7.0", "primary_fuel": "Hydro"},
    {"country": "DEU", "name": "Small Gas", "capacity_mw": "50", "latitude": "50.1",
     "longitude": "7.1", "primary_fuel": "Gas"},
    {"country": "DEU", "name": "Big Gas", "capacity_mw": "500", "latitude": "50.2",
     "longitude": "7.2", "primary_fuel": "Gas"},
    {"country": "FRA", "name": "Negative plant", "capacity_mw": "-10", "latitude": "45.0",
     "longitude": "2.0", "primary_fuel": "Gas"},
]
pf = build_portfolio(wri_rows, countries=["DEU", "FRA"], top_n=1)
names = {p["name"] for p in pf}
check("build_portfolio: hydro is excluded even though it is the largest DEU plant by far",
      "Big Hydro" not in names)
check("build_portfolio: the largest remaining (non-hydro) DEU plant is kept",
      "Big Gas" in names and "Small Gas" not in names)
check("build_portfolio: a non-positive capacity row is dropped, not treated as a zero-weight "
      "location that would silently vanish from a capacity-weighted mean anyway",
      "Negative plant" not in names)

print(f"\n{passed} checks passed")
