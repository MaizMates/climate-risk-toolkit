"""Expected annual flood damage for a portfolio of European power-generation assets.

ESTIMAND. Expected annual damage (EAD), as a fraction of asset value, for a portfolio of
locations, under a published depth-damage function: for each return period, read the modelled
flood depth at the location, map depth to a damage fraction with the curve, then integrate the
damage fraction over the exceedance-probability curve (1/return-period) to get one annual-average
number per location.

Data, all fetched by this script, nothing typed:
- Hazard: JRC/Copernicus EFAS "River flood hazard maps for Europe and the Mediterranean Basin
  region" v3.1.1 (Baugh et al. 2024), GeoTIFF depth rasters, one per return period, 90m
  resolution, WGS84, served from jeodpp.jrc.ec.europa.eu. Each file is ~300MB; this script never
  downloads a full file. It reads the TIFF directory with a few small HTTP range requests, then
  fetches only the compressed tiles that cover the portfolio's coordinates.
- Depth-damage curves: Huizinga, de Moel & Szewczyk (2017), "Global flood depth-damage functions",
  JRC105688, as redistributed in CLIMADA's open-source river_flood.py (the values are the
  published JRC Europe curves; this script downloads that module's source and parses the
  literal arrays out of it rather than retyping them).
- Portfolio: WRI Global Power Plant Database (as in module 03), the 20 largest plants by
  capacity in each of nine countries with a documented history of damaging river floods,
  filtered to the JRC raster's coverage.
- Validation: the JRC's own "spurious depth areas" layer from the same hazard-map release, which
  flags cells where modelled RP10 depth exceeds 10m in small channels -- the dataset's own
  documented failure mode, checked against every flooded point in the portfolio.
"""
import csv
import io
import json
import os
import random
import re
import ssl
import struct
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor

WRI_URL = ("https://raw.githubusercontent.com/wri/global-power-plant-database/master/"
           "output_database/global_power_plant_database.csv")
JRC_BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/"
JRC_DEPTH_TPL = JRC_BASE + "Europe_RP{rp}_filled_depth.tif"
JRC_SPURIOUS_URL = JRC_BASE + "Europe_spurious_depth_areas.tif"
JRC_PERMANENT_WATER_URL = JRC_BASE + "Europe_permanent_water_bodies.tif"
CURVES_URL = ("https://raw.githubusercontent.com/CLIMADA-project/climada_petals/main/"
              "climada_petals/entity/impact_funcs/river_flood.py")

RETURN_PERIODS = [10, 20, 30, 40, 50, 75, 100, 200, 500]
COUNTRIES = ["DEU", "FRA", "ITA", "AUT", "CZE", "POL", "NLD", "GBR", "ESP"]
TOP_N_PER_COUNTRY = 20
# Hydro (and wave/tidal) plants are sited in the river or sea by design: the hazard map's
# modelled depth at their coordinates is the normal operating water level, not flood damage to a
# building, and the Huizinga curves are building/infrastructure curves. Keeping them in made
# every flooded location an Austrian dam -- a siting artifact, not a finding (see notes.md).
EXCLUDED_FUELS = {"Hydro", "Wave and Tidal", "Pumped Storage"}
PRIMARY_SECTOR = "infrastructure"
ALT_SECTORS = ["industrial", "commercial"]
NODATA = -9999.0
N_BOOT = 1000
MAX_WORKERS = 16


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        try:
            return ssl.create_default_context(cafile=path)
        except Exception:
            continue
    return ssl.create_default_context()


def _urlopen(req, timeout=60, retries=3):
    last = None
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=_ctx())
        except Exception as e:
            last = e
    raise last


def http_range(url, start, end):
    req = urllib.request.Request(
        url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "climate-risk-toolkit"})
    with _urlopen(req) as r:
        return r.read()


def http_head_length(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "climate-risk-toolkit"})
    with _urlopen(req, timeout=30) as r:
        return int(r.headers["Content-Length"])


# ---------------------------------------------------------------------------
# WRI plant portfolio
# ---------------------------------------------------------------------------

def fetch_wri(url=WRI_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with _urlopen(req, timeout=120) as r:
        text = r.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def build_portfolio(wri_rows, countries=COUNTRIES, top_n=TOP_N_PER_COUNTRY,
                     excluded_fuels=EXCLUDED_FUELS):
    """The top_n largest non-hydro plants by capacity in each country, by WRI's coordinates."""
    by_country = {c: [] for c in countries}
    for row in wri_rows:
        c = row["country"]
        if c not in by_country or row["primary_fuel"] in excluded_fuels:
            continue
        try:
            cap = float(row["capacity_mw"])
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (TypeError, ValueError):
            continue
        if cap <= 0:
            continue
        by_country[c].append({"country": c, "name": row["name"], "capacity_mw": cap,
                               "lat": lat, "lon": lon, "primary_fuel": row["primary_fuel"]})
    portfolio = []
    for c, plants in by_country.items():
        plants.sort(key=lambda p: -p["capacity_mw"])
        portfolio.extend(plants[:top_n])
    return portfolio


# ---------------------------------------------------------------------------
# JRC depth-damage curves, parsed out of CLIMADA's redistribution of the JRC database
# ---------------------------------------------------------------------------

def parse_curves(text):
    """Pull the published JRC Europe depth-damage curves out of CLIMADA's river_flood.py
    source text: the literal depth breakpoints and, per sector, the literal damage-fraction
    array under the "europe" key. No value here is retyped -- only located and parsed."""
    m = re.search(r"impf\.intensity\s*=\s*np\.array\(\[([^\]]+)\]\)", text)
    depths = [float(x) for x in m.group(1).split(",") if x.strip()]

    curves = {}
    for sector in ("residential", "commercial", "industrial", "transport", "infrastructure",
                   "agriculture"):
        sm = re.search(rf"def from_jrc_impf_{sector}\(region\):", text)
        if not sm:
            continue
        start = sm.end()
        nxt = re.search(r"\ndef ", text[start:])
        block = text[start:start + nxt.start()] if nxt else text[start:]
        em = re.search(r'"europe":\s*\[([^\]]*)\]', block)
        if not em:
            continue
        values = [float(x) for x in em.group(1).split(",") if x.strip()]
        curves[sector] = values
    return depths, curves


def fetch_curves(url=CURVES_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with _urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8")
    return parse_curves(text)


def damage_fraction(depth_m, depths, values):
    """Piecewise-linear interpolation of the published curve. Depth <= 0 -> 0 damage; depth
    beyond the curve's last breakpoint is clipped to the last (always 1.0 in these curves)."""
    if depth_m <= 0:
        return 0.0
    d = min(max(depth_m, depths[0]), depths[-1])
    for i in range(len(depths) - 1):
        if depths[i] <= d <= depths[i + 1]:
            lo, hi = depths[i], depths[i + 1]
            if hi == lo:
                return values[i]
            t = (d - lo) / (hi - lo)
            return values[i] + t * (values[i + 1] - values[i])
    return values[-1]


# ---------------------------------------------------------------------------
# Tiled-GeoTIFF point reader over HTTP range requests -- never downloads a full raster
# ---------------------------------------------------------------------------

TAG_IMAGE_WIDTH, TAG_IMAGE_LENGTH = 256, 257
TAG_BITS_PER_SAMPLE, TAG_SAMPLE_FORMAT = 258, 339
TAG_TILE_WIDTH, TAG_TILE_LENGTH = 322, 323
TAG_TILE_OFFSETS, TAG_TILE_BYTECOUNTS = 324, 325
TAG_PIXEL_SCALE, TAG_TIEPOINT = 33550, 33922

# (bits per sample, SampleFormat tag value) -> struct format char. SampleFormat 1=unsigned int,
# 2=signed int, 3=IEEE float; these rasters have shown up as float32 (depth) and float64 (QA flag).
DTYPE_CHAR = {(8, 1): "B", (8, 2): "b", (16, 1): "H", (16, 2): "h",
              (32, 1): "I", (32, 2): "i", (32, 3): "f", (64, 3): "d"}


class RasterGrid:
    """Metadata + tile index for one GeoTIFF, read with a handful of small HTTP requests."""

    def __init__(self, url):
        self.url = url
        total = http_head_length(url)
        head = http_range(url, 0, 15)
        endian = "<" if head[0:2] == b"II" else ">"
        if head[0:2] not in (b"II", b"MM"):
            raise ValueError(f"{url}: not a TIFF (bad byte-order mark)")
        ifd_offset = struct.unpack(endian + "I", head[4:8])[0]

        tail_size = min(total, 2_000_000)
        start = max(0, min(ifd_offset, total - tail_size))
        tail = http_range(url, start, total - 1)
        rel = ifd_offset - start
        n = struct.unpack(endian + "H", tail[rel:rel + 2])[0]
        type_size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 11: 4, 12: 8}

        def array_value(voff, typ, count):
            size = type_size.get(typ, 1) * count
            abs_rel = voff - start
            if 0 <= abs_rel and abs_rel + size <= len(tail):
                raw = tail[abs_rel:abs_rel + size]
            else:
                raw = http_range(url, voff, voff + size - 1)
            if typ == 3:
                return struct.unpack(endian + str(count) + "H", raw)
            if typ == 4:
                return struct.unpack(endian + str(count) + "I", raw)
            if typ == 12:
                return struct.unpack(endian + str(count) + "d", raw)
            return raw

        tags = {}
        p = rel + 2
        for _ in range(n):
            entry = tail[p:p + 12]
            tag, typ, count = struct.unpack(endian + "HHI", entry[0:8])
            valoff = entry[8:12]
            size = type_size.get(typ, 1) * count
            if size <= 4:
                if typ == 3:
                    tags[tag] = struct.unpack(endian + "H", valoff[0:2])[0]
                elif typ == 4:
                    tags[tag] = struct.unpack(endian + "I", valoff)[0]
                else:
                    tags[tag] = valoff
            else:
                voff = struct.unpack(endian + "I", valoff)[0]
                tags[tag] = array_value(voff, typ, count)
            p += 12

        self.endian = endian
        self.width = tags[TAG_IMAGE_WIDTH]
        self.length = tags[TAG_IMAGE_LENGTH]
        self.tile_w = tags[TAG_TILE_WIDTH]
        self.tile_h = tags[TAG_TILE_LENGTH]
        self.n_tiles_x = -(-self.width // self.tile_w)
        scale = tags[TAG_PIXEL_SCALE]
        tiepoint = tags[TAG_TIEPOINT]
        self.scale_x, self.scale_y = scale[0], scale[1]
        self.origin_lon, self.origin_lat = tiepoint[3], tiepoint[4]
        self.tile_offsets = tags[TAG_TILE_OFFSETS]
        self.tile_bytecounts = tags[TAG_TILE_BYTECOUNTS]
        bits, sfmt = tags[TAG_BITS_PER_SAMPLE], tags[TAG_SAMPLE_FORMAT]
        key = (bits, sfmt)
        if key not in DTYPE_CHAR:
            raise ValueError(f"{url}: unsupported sample type bits={bits} format={sfmt}")
        self.dtype_char = DTYPE_CHAR[key]
        self.dtype_size = bits // 8
        self._tile_cache = {}

    def pixel_of(self, lon, lat):
        col = (lon - self.origin_lon) / self.scale_x
        row = (self.origin_lat - lat) / self.scale_y
        return col, row

    def in_bounds(self, lon, lat):
        col, row = self.pixel_of(lon, lat)
        return 0 <= col < self.width and 0 <= row < self.length

    def tile_index_of(self, col, row):
        return int(row) // self.tile_h * self.n_tiles_x + int(col) // self.tile_w

    def fetch_tile(self, tile_index):
        if tile_index in self._tile_cache:
            return self._tile_cache[tile_index]
        offset = self.tile_offsets[tile_index]
        nbytes = self.tile_bytecounts[tile_index]
        if offset == 0 or nbytes == 0:
            self._tile_cache[tile_index] = None
            return None
        raw = http_range(self.url, offset, offset + nbytes - 1)
        decompressed = zlib.decompress(raw)
        n_px = self.tile_w * self.tile_h
        decompressed = decompressed[:n_px * self.dtype_size]
        arr = struct.unpack(self.endian + str(n_px) + self.dtype_char, decompressed)
        self._tile_cache[tile_index] = arr
        return arr

    def value_at(self, lon, lat):
        if not self.in_bounds(lon, lat):
            return 0.0
        col, row = self.pixel_of(lon, lat)
        tile = self.fetch_tile(self.tile_index_of(col, row))
        if tile is None:
            return 0.0
        px, py = int(col) % self.tile_w, int(row) % self.tile_h
        val = tile[py * self.tile_w + px]
        if val != val or val <= NODATA / 2:  # NaN, or the -9999 nodata sentinel
            return 0.0
        return max(val, 0.0)

    def prefetch_tiles(self, points, max_workers=MAX_WORKERS):
        """Resolve the distinct tiles a batch of points needs, then fetch them in parallel."""
        needed = set()
        for lon, lat in points:
            if not self.in_bounds(lon, lat):
                continue
            col, row = self.pixel_of(lon, lat)
            needed.add(self.tile_index_of(col, row))
        needed = [t for t in needed if t not in self._tile_cache]
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            list(ex.map(self.fetch_tile, needed))


# ---------------------------------------------------------------------------
# Expected annual damage
# ---------------------------------------------------------------------------

def expected_annual_damage(depth_by_rp, depths, values, anchor_zero=True, tail_flat=False):
    """Integrate damage fraction over the exceedance-probability curve.

    depth_by_rp: {return_period_years: depth_m}. Points are ordered by descending exceedance
    probability p=1/T. anchor_zero adds a (p=1, damage=0) point at the frequent end -- the
    standard assumption that at a near-certain annual probability nothing resembling these return
    periods has happened yet. tail_flat extends the rarest point's damage flat out to p=0 instead
    of truncating the integral at the smallest return period in the data.
    """
    pts = sorted(((1.0 / rp, damage_fraction(depth_by_rp[rp], depths, values))
                  for rp in depth_by_rp), reverse=True)
    if anchor_zero:
        pts = [(1.0, 0.0)] + pts
    if tail_flat:
        pts = pts + [(0.0, pts[-1][1])]
    ead = 0.0
    for (p0, d0), (p1, d1) in zip(pts, pts[1:]):
        ead += 0.5 * (d0 + d1) * (p0 - p1)
    return ead


def portfolio_mean(locations, weight_key="capacity_mw", value_key="ead"):
    total_w = sum(l[weight_key] for l in locations)
    if total_w == 0:
        return None
    return sum(l[weight_key] * l[value_key] for l in locations) / total_w


def bootstrap_ci(locations, statistic_fn, n=N_BOOT, seed=0):
    rng = random.Random(seed)
    n_loc = len(locations)
    vals = []
    for _ in range(n):
        sample = [locations[rng.randrange(n_loc)] for _ in range(n_loc)]
        v = statistic_fn(sample, rng)
        if v is not None:
            vals.append(v)
    vals.sort()
    lo = vals[int(0.025 * (len(vals) - 1))]
    hi = vals[int(0.975 * (len(vals) - 1))]
    return lo, hi


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(countries=COUNTRIES, top_n=TOP_N_PER_COUNTRY, seed=0):
    print("fetching WRI Global Power Plant Database ...")
    wri_rows = fetch_wri()
    portfolio = build_portfolio(wri_rows, countries, top_n)
    print(f"portfolio: {len(portfolio)} plants across {len(countries)} countries")

    print("fetching JRC depth-damage curves (Huizinga et al. 2017, via CLIMADA) ...")
    depths, curves = fetch_curves()
    sectors = [PRIMARY_SECTOR] + ALT_SECTORS
    for s in sectors:
        if s not in curves:
            raise RuntimeError(f"curve for sector '{s}' not found in fetched source")

    points = [(p["lon"], p["lat"]) for p in portfolio]

    print("reading JRC flood hazard rasters (tiled HTTP range reads, no full download) ...")
    grids = {}
    for rp in RETURN_PERIODS:
        url = JRC_DEPTH_TPL.format(rp=rp)
        g = RasterGrid(url)
        g.prefetch_tiles(points)
        grids[rp] = g
        n_tiles = sum(1 for v in g._tile_cache.values() if v is not None)
        print(f"  RP{rp}: {n_tiles} non-empty tiles fetched for this portfolio")

    print("reading JRC spurious-depth QA layer ...")
    spurious_grid = RasterGrid(JRC_SPURIOUS_URL)
    spurious_grid.prefetch_tiles(points)

    print("reading JRC permanent-water-bodies layer (to screen out patched, not flooded, cells) ...")
    water_grid = RasterGrid(JRC_PERMANENT_WATER_URL)
    water_grid.prefetch_tiles(points)

    n_on_water = 0
    for p in portfolio:
        p["on_permanent_water"] = water_grid.value_at(p["lon"], p["lat"]) > 0
        if p["on_permanent_water"]:
            # The "filled_depth" product patches permanent water bodies in at a nominal depth so
            # the raster has no gaps along rivers. A plant whose coordinate falls on that patch
            # reads a constant, non-zero "depth" at every return period that is the normal water
            # level, not flood damage -- a building depth-damage curve does not apply to it, so
            # it is screened out here rather than mistaken for the most exposed site in the book.
            p["depth_by_rp"] = {rp: 0.0 for rp in RETURN_PERIODS}
            n_on_water += 1
        else:
            p["depth_by_rp"] = {rp: grids[rp].value_at(p["lon"], p["lat"]) for rp in RETURN_PERIODS}
        p["max_depth_m"] = max(p["depth_by_rp"].values())
        p["flooded_any_rp"] = p["max_depth_m"] > 0
        p["spurious_flag"] = spurious_grid.value_at(p["lon"], p["lat"]) > 0
        for sector in sectors:
            p[f"ead_{sector}"] = expected_annual_damage(p["depth_by_rp"], depths, curves[sector])
        p["ead"] = p[f"ead_{PRIMARY_SECTOR}"]

    print(f"{n_on_water} locations sit on the permanent-water-bodies patch and were screened "
          f"to zero depth")
    n_flooded = sum(1 for p in portfolio if p["flooded_any_rp"])
    headline = portfolio_mean(portfolio)
    print(f"{n_flooded}/{len(portfolio)} locations show nonzero depth at some return period")
    print(f"headline ({PRIMARY_SECTOR} curve): capacity-weighted mean EAD = {headline:.4%}")

    # Curve sensitivity: same portfolio, same depths, only the published curve changes.
    curve_sensitivity = {s: portfolio_mean(portfolio, value_key=f"ead_{s}") for s in sectors}

    # Location-only bootstrap: resample plants, hold the primary curve fixed.
    def stat_location_only(sample, rng):
        return portfolio_mean(sample, value_key="ead")

    loc_lo, loc_hi = bootstrap_ci(portfolio, stat_location_only, seed=seed)

    # Combined bootstrap: each draw also draws ONE curve for the whole portfolio in that draw
    # (never one curve per plant -- a shared choice drawn once, as module 05's mistake flagged).
    def stat_combined(sample, rng):
        sector = rng.choice(sectors)
        return portfolio_mean(sample, value_key=f"ead_{sector}")

    comb_lo, comb_hi = bootstrap_ci(portfolio, stat_combined, seed=seed + 1)

    curve_range = max(curve_sensitivity.values()) - min(curve_sensitivity.values())
    location_range = loc_hi - loc_lo
    driver = "curve choice" if curve_range > location_range else "hazard/location resampling"

    # Sensitivity sweep 1: portfolio size (how many largest plants per country).
    size_sweep = []
    for n in (10, 15, 20, 30):
        pf = build_portfolio(wri_rows, countries, n)
        pf_points = [(p["lon"], p["lat"]) for p in pf]
        for g in grids.values():
            g.prefetch_tiles(pf_points)
        water_grid.prefetch_tiles(pf_points)
        for p in pf:
            if water_grid.value_at(p["lon"], p["lat"]) > 0:
                p["depth_by_rp"] = {rp: 0.0 for rp in RETURN_PERIODS}
            else:
                p["depth_by_rp"] = {rp: grids[rp].value_at(p["lon"], p["lat"]) for rp in RETURN_PERIODS}
            p["ead"] = expected_annual_damage(p["depth_by_rp"], depths, curves[PRIMARY_SECTOR])
        size_sweep.append({"top_n_per_country": n, "n_locations": len(pf),
                            "headline_ead": portfolio_mean(pf)})

    # Sensitivity sweep 2: the EAD integration's arbitrary tail assumptions.
    tail_sweep = []
    for anchor_zero in (True, False):
        for tail_flat in (False, True):
            vals = [expected_annual_damage(p["depth_by_rp"], depths, curves[PRIMARY_SECTOR],
                                            anchor_zero=anchor_zero, tail_flat=tail_flat)
                    for p in portfolio]
            weights = [p["capacity_mw"] for p in portfolio]
            mean_ead = sum(w * v for w, v in zip(weights, vals)) / sum(weights)
            tail_sweep.append({"anchor_zero_at_p1": anchor_zero, "tail_flat_beyond_rp500": tail_flat,
                                "headline_ead": mean_ead})

    spurious = [p for p in portfolio if p["spurious_flag"] and p["flooded_any_rp"]]

    by_country = {}
    for p in portfolio:
        c = by_country.setdefault(p["country"], {"country": p["country"], "capacity_mw": 0.0,
                                                   "weighted_ead": 0.0, "n_plants": 0,
                                                   "n_flooded": 0})
        c["capacity_mw"] += p["capacity_mw"]
        c["weighted_ead"] += p["capacity_mw"] * p["ead"]
        c["n_plants"] += 1
        c["n_flooded"] += 1 if p["flooded_any_rp"] else 0
    by_country_rows = []
    for c in by_country.values():
        c["mean_ead"] = c["weighted_ead"] / c["capacity_mw"] if c["capacity_mw"] else None
        del c["weighted_ead"]
        by_country_rows.append(c)
    by_country_rows.sort(key=lambda r: -r["mean_ead"])

    out = {
        "estimand": ("expected annual damage (EAD), as a fraction of asset value, for a "
                     "portfolio of European power-generation assets, under the JRC/Huizinga "
                     "published depth-damage curve, integrated over the JRC river-flood hazard "
                     "maps' return periods"),
        "countries": countries,
        "top_n_per_country": top_n,
        "n_locations": len(portfolio),
        "n_flooded_any_rp": n_flooded,
        "return_periods": RETURN_PERIODS,
        "curve_depth_breakpoints_m": depths,
        "primary_sector": PRIMARY_SECTOR,
        "alt_sectors": ALT_SECTORS,
        "headline_ead": headline,
        "headline_ci_location_only": [loc_lo, loc_hi],
        "headline_ci_combined": [comb_lo, comb_hi],
        "curve_sensitivity": curve_sensitivity,
        "curve_range": curve_range,
        "location_ci_range": location_range,
        "dominant_driver": driver,
        "portfolio_size_sweep": size_sweep,
        "tail_assumption_sweep": tail_sweep,
        "spurious_flagged_flooded_locations": len(spurious),
        "n_flooded_total": n_flooded,
        "n_on_permanent_water": n_on_water,
        "by_country": by_country_rows,
        "locations": [
            {"name": p["name"], "country": p["country"], "capacity_mw": p["capacity_mw"],
             "lat": p["lat"], "lon": p["lon"], "primary_fuel": p["primary_fuel"],
             "max_depth_m": p["max_depth_m"], "flooded_any_rp": p["flooded_any_rp"],
             "spurious_flag": p["spurious_flag"], "on_permanent_water": p["on_permanent_water"],
             "ead_infrastructure": p["ead_infrastructure"], "ead_industrial": p["ead_industrial"],
             "ead_commercial": p["ead_commercial"],
             "depth_by_rp": p["depth_by_rp"]}
            for p in portfolio
        ],
        "sources": {
            "hazard": "JRC/Copernicus EFAS River flood hazard maps for Europe and the "
                      "Mediterranean Basin, v3.1.1 (Baugh et al. 2024), " + JRC_BASE,
            "curves": "Huizinga, de Moel & Szewczyk (2017), JRC105688, doi:10.2760/16510, "
                     "Europe curves as redistributed in " + CURVES_URL,
            "portfolio": "WRI Global Power Plant Database, " + WRI_URL,
            "permanent_water_bodies": JRC_PERMANENT_WATER_URL,
            "qa_layer": JRC_SPURIOUS_URL,
        },
    }
    os.makedirs("results", exist_ok=True)
    with open("results/flood_depth_damage.json", "w") as f:
        json.dump(out, f, indent=1)

    print(f"\nheadline EAD ({PRIMARY_SECTOR}): {headline:.4%} "
          f"location-only CI [{loc_lo:.4%}, {loc_hi:.4%}] "
          f"combined CI [{comb_lo:.4%}, {comb_hi:.4%}]")
    print(f"curve sensitivity: {curve_sensitivity}")
    print(f"curve range {curve_range:.4%} vs location-resampling range {location_range:.4%} "
          f"-> {driver} dominates")
    print(f"spurious-flagged flooded locations: {len(spurious)} of {n_flooded}")
    return out


if __name__ == "__main__":
    build()
