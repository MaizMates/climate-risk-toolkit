"""Thermal capacity exposed to rising heat stress, joined to 0.25 degree grid cells.

ESTIMAND. The share of thermal generating capacity, in MW, across the eleven countries of
modules 01 and 03, held by plants whose own 0.25 degree grid cell shows the annual count of days
at or above a 35 C heat index rising by more than k days from 1995-2014 to 2040-2059 under
SSP2-4.5 (CMIP6 ensemble median), and the difference between that share and the one module 03
gets by giving every plant its country's value. The difference is what country resolution cost.

Inputs are fetched by src/fetch.py. Run: python3 src/gridded.py
"""
import csv
import json
import math
import os

import numpy as np
import pandas as pd

from h5lite import H5

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
RES = os.path.join(HERE, "..", "results")
MOD03 = os.path.join(HERE, "..", "..", "03-hazard-exposure-join", "results", "hazard_exposure.json")

COUNTRIES = ["ITA", "ESP", "FRA", "DEU", "NLD", "PRT", "GRC", "AUT", "BEL", "IRL", "POL"]
VAR = "climatology-hd35-annual-mean"
CORE, GAS, BIOMASS = {"Coal", "Oil", "Petcoke"}, {"Gas"}, {"Biomass", "Waste"}
K_REF, K_VALUES = 2.0, [0, 1, 2, 3, 5, 8]
RADII_KM = [0, 25, 50, 100]          # 0 = the cell containing the plant
COARSEN = [1, 2, 4, 8]               # cells per block side: 0.25, 0.5, 1, 2 degrees
OFF_COUNTRY_KM = 10.0                # a plant farther than this from its own country is a bad coordinate
N_BOOT, SEED = 2000, 20260919
R_EARTH = 6371.0


# ---------------------------------------------------------------- geometry

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def points_in_ring(x, y, ring):
    """Even-odd rule, vectorised over points. ring: (n, 2) lon/lat, closed."""
    ring = np.asarray(ring)
    inside = np.zeros(x.shape, bool)
    for (xa, ya), (xb, yb) in zip(ring[:-1], ring[1:]):
        if ya == yb:
            continue
        cross = (ya > y) != (yb > y)
        inside ^= cross & (x < (xb - xa) * (y - ya) / (yb - ya) + xa)
    return inside


def polygon_parts(feature):
    g = feature["geometry"]
    return g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]


def points_in_polygon(x, y, poly):
    """poly = [outer, hole, hole...]. Only the points inside the outer ring's box are tested."""
    out = np.zeros(x.shape, bool)
    outer = np.asarray(poly[0])
    box = ((x >= outer[:, 0].min()) & (x <= outer[:, 0].max())
           & (y >= outer[:, 1].min()) & (y <= outer[:, 1].max()))
    if not box.any():
        return out
    m = points_in_ring(x[box], y[box], outer)
    for hole in poly[1:]:
        m &= ~points_in_ring(x[box], y[box], hole)
    out[box] = m
    return out


def in_europe(poly):
    c = np.asarray(poly[0]).mean(axis=0)
    return -32 < c[0] < 45 and 27 < c[1] < 72    # drops French Guiana, Reunion and so on


def country_feature(ne, iso):
    for f in ne["features"]:
        p = f["properties"]
        if iso in (p.get("ADM0_A3"), p.get("ISO_A3_EH")):
            return f
    raise KeyError(iso)


def distance_to_country_km(lat, lon, parts):
    """0 if the point is inside the country's European parts, else distance to the nearest
    boundary segment, on a local flat projection (adequate at the 10 km scale used)."""
    for poly in parts:
        if points_in_polygon(np.array([lon]), np.array([lat]), poly)[0]:
            return 0.0
    best = np.inf
    kx = 111.32 * math.cos(math.radians(lat))
    for poly in parts:
        for ring in poly:
            r = np.asarray(ring)
            ax, ay = (r[:-1, 0] - lon) * kx, (r[:-1, 1] - lat) * 110.57
            bx, by = (r[1:, 0] - lon) * kx, (r[1:, 1] - lat) * 110.57
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = np.clip(np.where(L2 > 0, -(ax * dx + ay * dy) / np.where(L2 > 0, L2, 1), 0), 0, 1)
            d = np.hypot(ax + t * dx, ay + t * dy)
            best = min(best, float(d.min()))
    return best


# ---------------------------------------------------------------- grids

class Grid:
    def __init__(self, layers):
        h = H5(open(os.path.join(RAW, "grid_hist_median.nc"), "rb").read())
        self.lat, self.lon = h.var("lat"), h.var("lon")
        assert abs(self.lat[1] - self.lat[0] - 0.25) < 1e-6 and abs(self.lon[1] - self.lon[0] - 0.25) < 1e-6
        self.v = {k: H5(open(os.path.join(RAW, f"grid_{k}.nc"), "rb").read()).var(VAR)[0] for k in layers}
        self.land = None

    def change(self, scen, stat="median"):
        return self.v[f"{scen}_{stat}"] - self.v[f"hist_{stat}"]

    def index(self, lat, lon):
        return (np.rint((np.asarray(lat) + 90) / 0.25).astype(int),
                np.rint((np.asarray(lon) + 180) / 0.25).astype(int) % 1440)

    def build_land(self, ne, box=(20, 65, -25, 40)):
        """Land flag on the cells of a European box, from all Natural Earth polygons."""
        la0, la1, lo0, lo1 = box
        i0, j0 = self.index(la0, lo0)
        i1, j1 = self.index(la1, lo1)
        LON, LAT = np.meshgrid(self.lon[j0:j1 + 1], self.lat[i0:i1 + 1])
        land = np.zeros(LON.shape, bool)
        for f in ne["features"]:
            for poly in polygon_parts(f):
                o = np.asarray(poly[0])
                if o[:, 0].max() < lo0 or o[:, 0].min() > lo1 or o[:, 1].max() < la0 or o[:, 1].min() > la1:
                    continue
                land |= points_in_polygon(LON.ravel(), LAT.ravel(), poly).reshape(LON.shape)
        self.land = (land, i0, j0)

    def plant_values(self, field, lats, lons, radius_km=0.0, land_only=False):
        """Mean of the cells whose centre is within radius_km of each plant (the cell containing
        it when radius_km is 0). With land_only, sea cells are skipped; a plant with no cell
        left falls back to its nearest cell. Returns (values, n_fallback)."""
        out, fallback = np.zeros(len(lats)), 0
        ii, jj = self.index(lats, lons)
        for n, (la, lo) in enumerate(zip(lats, lons)):
            if radius_km == 0:
                out[n] = field[ii[n], jj[n]]
                continue
            di = int(radius_km / 27.0) + 1
            dj = int(radius_km / (27.0 * max(math.cos(math.radians(la)), 0.2))) + 1
            I = np.arange(ii[n] - di, ii[n] + di + 1)
            J = np.arange(jj[n] - dj, jj[n] + dj + 1) % 1440
            JJ, II = np.meshgrid(J, I)
            d = haversine_km(la, lo, self.lat[II], self.lon[JJ])
            ok = d <= radius_km
            if land_only:
                land, i0, j0 = self.land
                ok &= land[II - i0, JJ - j0]
            if not ok.any():
                fallback += 1
                out[n] = field[ii[n], jj[n]]
            else:
                out[n] = field[II[ok], JJ[ok]].mean()
        return out, fallback

    def coarsened(self, field, b):
        """Block means of b x b cells (latitude row 90N dropped so blocks tile evenly)."""
        f = field[:720].reshape(720 // b, b, 1440 // b, b).mean(axis=(1, 3))
        return f

    def plant_block_values(self, field, lats, lons, b):
        ii, jj = self.index(lats, lons)
        return self.coarsened(field, b)[np.minimum(ii, 719) // b, jj // b]


# ---------------------------------------------------------------- plants

def thermal_fuels(gas=True, biomass=False):
    return CORE | (GAS if gas else set()) | (BIOMASS if biomass else set())


def load_plants(path, fuels):
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["country"] not in COUNTRIES or r["primary_fuel"] not in fuels:
            continue
        try:
            cap, la, lo = float(r["capacity_mw"]), float(r["latitude"]), float(r["longitude"])
        except ValueError:
            continue
        if cap > 0:
            rows.append({"country": r["country"], "name": r["name"], "fuel": r["primary_fuel"],
                         "capacity_mw": cap, "lat": la, "lon": lo})
    return pd.DataFrame(rows)


def coordinate_qa(plants, ne):
    """Flag plants whose coordinates fall outside their own country. A plant whose latitude and
    longitude, swapped, land inside its country is repaired by the swap; any other is dropped
    from the gridded join (and from the country-level comparator, so both see the same plants).
    The WRI file carries both kinds of error."""
    parts = {iso: [p for p in polygon_parts(country_feature(ne, iso)) if in_europe(p)] for iso in COUNTRIES}
    status, lat, lon, dist = [], [], [], []
    for r in plants.itertuples():
        d = distance_to_country_km(r.lat, r.lon, parts[r.country])
        la, lo = r.lat, r.lon
        s = "ok"
        if d > OFF_COUNTRY_KM:
            if abs(r.lon) <= 90 and distance_to_country_km(r.lon, r.lat, parts[r.country]) <= OFF_COUNTRY_KM:
                la, lo, s = r.lon, r.lat, "swapped"
            else:
                s = "dropped"
        status.append(s); lat.append(la); lon.append(lo); dist.append(d)
    out = plants.copy()
    out["lat_used"], out["lon_used"], out["qa"], out["km_off_country"] = lat, lon, status, dist
    return out


# ---------------------------------------------------------------- estimators

def exceeds(values, k):
    """Exposed means a rise of MORE than k days; a plant sitting exactly on k is not exposed."""
    return np.asarray(values) > k


def exposed_share(cap, exposed):
    """Capacity-weighted share. cap and exposed are aligned arrays; exposed is boolean."""
    tot = cap.sum()
    return float((cap * exposed).sum() / tot) if tot > 0 else float("nan")


def paired_bootstrap(cap, exposures, groups=None, n=N_BOOT, seed=SEED):
    """Resample with replacement, the same resample for every exposure vector, so that
    differences between vectors are paired. groups: one label per plant; units of one site are
    resampled together (they share a cell and a hazard value, so they are not independent draws).
    Without groups every plant is its own site. exposures: {name: bool array}. Returns
    {name: array of n shares}."""
    rng = np.random.default_rng(seed)
    gid = np.arange(len(cap)) if groups is None else pd.factorize(np.asarray(groups))[0]
    ng = gid.max() + 1
    counts = rng.multinomial(ng, np.full(ng, 1.0 / ng), size=n)[:, gid]               # (n, plants)
    w = counts * cap
    den = w.sum(axis=1)
    return {k: (w @ e.astype(float)) / den for k, e in exposures.items()}


def ci(x, lo=2.5, hi=97.5):
    return [float(np.percentile(x, lo)), float(np.percentile(x, hi))]


def spearman(a, b):
    if len(set(a)) < 2 or len(set(b)) < 2:
        return float("nan")
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))


def top_n_share(cap, exposed, n=10):
    c = np.sort(cap[exposed])[::-1]
    return float(c[:n].sum() / c.sum()) if c.sum() > 0 else float("nan")


# ---------------------------------------------------------------- run

def main():
    os.makedirs(RES, exist_ok=True)
    ne = json.load(open(os.path.join(RAW, "ne_50m_admin_0_countries.geojson")))
    api = json.load(open(os.path.join(RAW, "cckp_country_api.json")))
    G = Grid(["hist_median", "hist_p10", "hist_p90", "ssp245_median", "ssp245_p10", "ssp245_p90",
              "ssp370_median"])
    G.build_land(ne)
    chg = {"ssp245": G.change("ssp245"), "ssp370": G.change("ssp370"),
           "ssp245_p10": G.change("ssp245", "p10"), "ssp245_p90": G.change("ssp245", "p90")}
    country_chg = {s: {c: api[f"{s}_median"][c] - api["hist_median"][c] for c in COUNTRIES}
                   for s in ("ssp245", "ssp370")}
    for q in ("p10", "p90"):
        country_chg[f"ssp245_{q}"] = {c: api[f"ssp245_{q}"][c] - api[f"hist_{q}"][c] for c in COUNTRIES}

    # ---- validation 1: the grid read against the CCKP country API
    lonm, latm = np.meshgrid(G.lon, G.lat)
    wgt = np.cos(np.radians(latm))
    val = []
    for iso in COUNTRIES:
        mask = np.zeros(latm.shape, bool)
        sel = np.zeros(latm.shape, bool)
        parts = [p for p in polygon_parts(country_feature(ne, iso)) if in_europe(p)]
        for p in parts:
            o = np.asarray(p[0])
            sel = (latm >= o[:, 1].min()) & (latm <= o[:, 1].max()) & (lonm >= o[:, 0].min()) & (lonm <= o[:, 0].max())
            idx = np.where(sel)
            mask[idx] |= points_in_polygon(lonm[idx], latm[idx], p)
        row = {"iso3": iso, "n_cells": int(mask.sum())}
        for layer, key in (("hist_median", "hist_median"), ("ssp245_median", "ssp245_median"),
                           ("ssp370_median", "ssp370_median")):
            g = float((G.v[layer] * wgt)[mask].sum() / wgt[mask].sum())
            row[layer] = {"grid": g, "api": api[key][iso], "diff": g - api[key][iso]}
        val.append(row)
    max_abs = max(abs(r[l]["diff"]) for r in val for l in ("hist_median", "ssp245_median", "ssp370_median"))

    # ---- plants
    plants_all = load_plants(os.path.join(RAW, "wri_gppd.csv"), thermal_fuels())
    plants_all = coordinate_qa(plants_all, ne)
    qa = {"n_thermal_plants": int(len(plants_all)), "mw": float(plants_all.capacity_mw.sum()),
          "swapped": int((plants_all.qa == "swapped").sum()),
          "swapped_mw": float(plants_all[plants_all.qa == "swapped"].capacity_mw.sum()),
          "dropped": int((plants_all.qa == "dropped").sum()),
          "dropped_mw": float(plants_all[plants_all.qa == "dropped"].capacity_mw.sum()),
          "dropped_names": plants_all[plants_all.qa == "dropped"][["country", "name", "lat", "lon", "capacity_mw"]]
          .to_dict("records"),
          "swapped_names": plants_all[plants_all.qa == "swapped"][["country", "name", "lat", "lon", "capacity_mw"]]
          .to_dict("records")}

    def prep(fuels):
        p = load_plants(os.path.join(RAW, "wri_gppd.csv"), fuels)
        p = coordinate_qa(p, ne)
        return p[p.qa != "dropped"].reset_index(drop=True)

    def hazard(p, scen, radius, land):
        v, fb = G.plant_values(chg[scen], p.lat_used.values, p.lon_used.values, radius, land)
        return v, fb

    def country_exposed(p, scen, k):
        return np.array([country_chg[scen][c] > k for c in p.country])

    base = prep(thermal_fuels())
    cap = base.capacity_mw.values
    base["cell_change"], _ = hazard(base, "ssp245", 0, False)
    base["country_change"] = [country_chg["ssp245"][c] for c in base.country]
    base["p10_change"], _ = hazard(base, "ssp245_p10", 0, False)
    base["p90_change"], _ = hazard(base, "ssp245_p90", 0, False)
    site = (base.lat_used.round(3).astype(str) + "," + base.lon_used.round(3).astype(str)).values

    # ---- headline and k sweep, bootstrap paired between grid and country resolution
    ex = {}
    for k in K_VALUES:
        ex[f"grid{k}"] = exceeds(base.cell_change.values, k)
        ex[f"country{k}"] = country_exposed(base, "ssp245", k)
        ex[f"p10_{k}"] = exceeds(base.p10_change.values, k)
        ex[f"p90_{k}"] = exceeds(base.p90_change.values, k)
        ex[f"cp10_{k}"] = country_exposed(base, "ssp245_p10", k)
        ex[f"cp90_{k}"] = country_exposed(base, "ssp245_p90", k)
    bs = paired_bootstrap(cap, ex, site)
    bs_plant = paired_bootstrap(cap, {f"grid{k}": ex[f"grid{k}"] for k in K_VALUES} |
                                {f"country{k}": ex[f"country{k}"] for k in K_VALUES})
    k_rows = []
    for k in K_VALUES:
        g, c = ex[f"grid{k}"], ex[f"country{k}"]
        diff = bs[f"grid{k}"] - bs[f"country{k}"]
        k_rows.append({
            "k": k, "grid_share": exposed_share(cap, g), "grid_ci": ci(bs[f"grid{k}"]),
            "country_share": exposed_share(cap, c), "country_ci": ci(bs[f"country{k}"]),
            "diff": exposed_share(cap, g) - exposed_share(cap, c), "diff_ci": ci(diff),
            "plant_level_grid_ci": ci(bs_plant[f"grid{k}"]),
            "plant_level_diff_ci": ci(bs_plant[f"grid{k}"] - bs_plant[f"country{k}"]),
            "grid_p10_share": exposed_share(cap, ex[f"p10_{k}"]),
            "grid_p90_share": exposed_share(cap, ex[f"p90_{k}"]),
            "country_p10_share": exposed_share(cap, ex[f"cp10_{k}"]),
            "country_p90_share": exposed_share(cap, ex[f"cp90_{k}"]),
            "diff_p10": exposed_share(cap, ex[f"p10_{k}"]) - exposed_share(cap, ex[f"cp10_{k}"]),
            "diff_p90": exposed_share(cap, ex[f"p90_{k}"]) - exposed_share(cap, ex[f"cp90_{k}"]),
            "diff_p10_ci": ci(bs[f"p10_{k}"] - bs[f"cp10_{k}"]),
            "diff_p90_ci": ci(bs[f"p90_{k}"] - bs[f"cp90_{k}"]),
            "envelope": [ci(bs[f"p10_{k}"])[0], ci(bs[f"p90_{k}"])[1]],
            "missed_by_country_mw_share": float(cap[g & ~c].sum() / cap.sum()),
            "over_assigned_by_country_mw_share": float(cap[~g & c].sum() / cap.sum()),
            "disagree_mw_share": float(cap[g != c].sum() / cap.sum()),
            "top10_share_of_grid_exposed": top_n_share(cap, g)})
    ref = next(r for r in k_rows if r["k"] == K_REF)

    # ---- reproduce module 03's country-level number on the plants it used
    m03 = json.load(open(MOD03))
    m03_ref = next(r for r in m03["exposure_by_k"] if r["k"] == 2)
    all_plants_cap = plants_all.capacity_mw.values
    all_country_ex = np.array([country_chg["ssp245"][c] > K_REF for c in plants_all.country])
    repro = {"module03_share_k2": m03_ref["exposed_share"],
             "this_module_share_k2_all_plants": exposed_share(all_plants_cap, all_country_ex),
             "module03_total_mw": m03["total_thermal_mw"], "this_module_total_mw": float(all_plants_cap.sum())}

    # ---- by country
    by_country = []
    for iso in COUNTRIES:
        s = base[base.country == iso]
        if s.empty:
            continue
        w = s.capacity_mw.values
        m = float(np.average(s.cell_change, weights=w))
        sd = float(math.sqrt(np.average((s.cell_change - m) ** 2, weights=w)))
        g, c = exceeds(s.cell_change.values, K_REF), country_chg["ssp245"][iso] > K_REF
        by_country.append({
            "iso3": iso, "n_plants": int(len(s)), "thermal_mw": float(w.sum()),
            "share_of_total_mw": float(w.sum() / cap.sum()),
            "country_change": country_chg["ssp245"][iso], "plant_mean_change": m,
            "plant_min_change": float(s.cell_change.min()), "plant_max_change": float(s.cell_change.max()),
            "plant_sd_change": sd, "country_exposed": bool(c),
            "grid_exposed_mw": float(w[g].sum()), "grid_exposed_share": float(w[g].sum() / w.sum()),
            "disagree_mw_share": float(w[g != c].sum() / w.sum())})
    by_country.sort(key=lambda r: -r["thermal_mw"])
    rho_country = spearman([r["country_change"] for r in by_country], [r["plant_mean_change"] for r in by_country])

    # ---- sweep: radius x land, scenario, fuels (k fixed at the reference)
    sweep = []

    def run(label, fuels, scen, radius, land, kind):
        p = prep(fuels)
        v, fb = hazard(p, scen, radius, land)
        w = p.capacity_mw.values
        g = exceeds(v, K_REF)
        c = country_exposed(p, scen, K_REF)
        pc = [float(w[(g) & (p.country.values == iso)].sum() / w[p.country.values == iso].sum())
              if (p.country.values == iso).any() else 0.0 for iso in COUNTRIES]
        return {"label": label, "kind": kind, "scenario": scen, "radius_km": radius, "land_only": land,
                "gas": "Gas" in fuels, "biomass": "Waste" in fuels, "n_plants": int(len(p)),
                "mw": float(w.sum()), "grid_share": exposed_share(w, g), "country_share": exposed_share(w, c),
                "diff": exposed_share(w, g) - exposed_share(w, c), "fallbacks": fb, "per_country": pc}

    fu = thermal_fuels()
    for r in RADII_KM:
        for land in (False, True):
            if r == 0 and land:
                continue
            sweep.append(run(f"radius {r} km" + (", land cells" if land else ""), fu, "ssp245", r, land, "radius"))
    sweep.append(run("SSP3-7.0", fu, "ssp370", 0, False, "scenario"))
    for gas in (True, False):
        for bio in (False, True):
            if gas and not bio:
                continue
            sweep.append(run(f"gas {'in' if gas else 'out'}, biomass {'in' if bio else 'out'}",
                             thermal_fuels(gas, bio), "ssp245", 0, False, "fuel"))
    b0 = next(s for s in sweep if s["label"] == "radius 0 km")
    for s in sweep:
        s["rank_corr_vs_base"] = spearman(s["per_country"], b0["per_country"])
    # the one-at-a-time ranges
    def span(kind, key):
        v = [s[key] for s in sweep if s["kind"] == kind] + [b0[key]]
        return {"min": min(v), "max": max(v), "range": max(v) - min(v)}
    spans = {kind: {key: span(kind, key) for key in ("grid_share", "diff")} for kind in ("radius", "scenario", "fuel")}
    k_span = {"grid_share": {"min": min(r["grid_share"] for r in k_rows), "max": max(r["grid_share"] for r in k_rows)},
              "diff": {"min": min(r["diff"] for r in k_rows), "max": max(r["diff"] for r in k_rows)}}
    k13 = [r for r in k_rows if r["k"] in (1, 3)]

    # ---- resolution ladder: country, 2 deg, 1 deg, 0.5 deg, 0.25 deg
    ladder = [{"resolution": "country", "degrees": None, "share": ref["country_share"]}]
    for b in sorted(COARSEN, reverse=True):
        v = G.plant_block_values(chg["ssp245"], base.lat_used.values, base.lon_used.values, b)
        ladder.append({"resolution": f"{0.25 * b:g} degree", "degrees": 0.25 * b,
                       "share": exposed_share(cap, exceeds(v, K_REF))})
    ladder_ex = {f"b{b}": exceeds(G.plant_block_values(chg["ssp245"], base.lat_used.values,
                                                       base.lon_used.values, b), K_REF) for b in COARSEN}
    bl = paired_bootstrap(cap, ladder_ex, site)
    for row in ladder:
        if row["degrees"]:
            row["ci"] = ci(bl[f"b{int(round(row['degrees'] / 0.25))}"])
    ladder_step = {"country_to_2deg": ladder[0]["share"] - ladder[1]["share"],
                   "two_deg_to_quarter_deg": ladder[1]["share"] - ladder[-1]["share"],
                   "two_deg_to_quarter_deg_ci": ci(bl["b8"] - bl["b1"])}

    out = {
        "estimand": ("share of thermal MW, in eleven countries, held by plants whose 0.25 degree cell shows "
                     "the annual count of days at or above a 35 C heat index rising by more than k days, "
                     "1995-2014 to 2040-2059, SSP2-4.5 ensemble median; and its difference from the "
                     "country-level share module 03 computes"),
        "k_reference": K_REF, "n_boot": N_BOOT, "seed": SEED,
        "n_plants": int(len(base)), "total_mw": float(cap.sum()), "reference": ref, "by_k": k_rows,
        "coordinate_qa": qa, "reproduces_module03": repro,
        "validation_grid_vs_api": {"rows": val, "max_abs_diff_days": max_abs},
        "by_country": by_country, "rank_corr_country_vs_plant_mean": rho_country,
        "sweep": sweep, "sweep_spans": spans, "k_span": k_span,
        "k1_to_k3": {"grid_share_range": abs(k13[0]["grid_share"] - k13[1]["grid_share"]),
                     "diff_range": abs(k13[0]["diff"] - k13[1]["diff"])},
        "resolution_ladder": ladder, "ladder_step": ladder_step,
        "n_sites": int(len(set(site))),
    }
    base.drop(columns=["lat", "lon"]).rename(columns={"lat_used": "lat", "lon_used": "lon"}).round(4).to_csv(
        os.path.join(RES, "plants.csv"), index=False)
    json.dump(out, open(os.path.join(RES, "gridded.json"), "w"), indent=1)
    print(f"{len(base)} plants, {cap.sum():,.0f} MW ({qa['dropped']} dropped, {qa['swapped']} swapped)")
    print(f"k=2: grid {ref['grid_share']:.1%} {ref['grid_ci']}, country {ref['country_share']:.1%} {ref['country_ci']},"
          f" diff {ref['diff']:+.1%} {ref['diff_ci']}")
    print(f"validation max abs diff {max_abs:.3f} days")
    return out


if __name__ == "__main__":
    main()
