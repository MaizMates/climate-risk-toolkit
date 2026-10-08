"""Scenario to ratio to PD: how an NGFS carbon-price path moves a sector's one-year probability of default.

ESTIMAND. The change in the one-year probability of default (PD) of the EU industry sector (NACE
B-E), in 2040, under the NGFS Delayed transition scenario (disorderly) relative to Net Zero 2050
(orderly), through one stated channel: carbon price x sector CO2 intensity of value added = carbon
cost as a share of value added; the part not passed on to customers lowers the sector's profit
share; the fall in profitability raises the log-odds of default by a published sensitivity.
Static sector structure: no abatement, no demand response, no second-round effects.

Every step is one line of arithmetic:
    cost_share   = price_EUR_per_t x CO2_per_EUR_mn_GVA / 1e6                      (share of GVA)
    d_profit     = -(1 - pass_through) x cost_share                                 (profit share of GVA)
    d_nimta_q    = d_profit x (GVA / fixed assets) / assets_scale / 4               (quarterly NI / assets)
    d_logodds    = coef x d_nimta_q                       (coef: Campbell-Hilscher-Szilagyi 2008, Table 3)
    PD           = logistic(logit(PD0) + d_logodds)

Data, all fetched by this file:
- Scenario: NGFS Phase 5, IIASA Scenario Explorer anonymous API (Price|Carbon, Emissions|CO2|Energy
  and Industrial Processes), three models.
- Sector ratios: Eurostat nama_10_a64 (value added, compensation of employees), env_ac_ainah_r2
  (air emissions accounts), nama_10_nfa_st (net fixed assets), ert_bil_eur_a and prc_hicp_aind
  (to restate USD-2010 prices in euro of the reference year).
- Sensitivity of default to profitability: coefficients parsed from the Campbell, Hilscher and
  Szilagyi (2008) NBER working paper PDF, Table 3.
- Check on the mapping: Eurostat sts_rb_a, bankruptcy declarations by sector and country.
"""
import csv
import json
import math
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")

ES = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
AUTH_URL = "https://api.manager.ece.iiasa.ac.at/legacy/anonym/"
NGFS_BASE = "https://db1.ene.iiasa.ac.at/ngfs-phase-5-api/rest/v2.1"
CHS_URL = "https://www.nber.org/papers/w12362.pdf"
UA = {"User-Agent": "climate-risk-toolkit/1.0 (public portfolio, github.com/MaizMates)"}

EU27 = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "EL", "HU", "IE", "IT",
        "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]

# NACE sections used by sts_rb_a, built from the A64 codes that all four Eurostat tables share.
SECTORS = {"B-E": ["B", "C", "D", "E"], "F": ["F"], "G": ["G"], "H": ["H"], "I": ["I"], "J": ["J"],
           "K-N": ["K", "L68A", "M", "N"], "P-S": ["P", "Q", "R", "S95", "S96"]}
RB_CODE = {"B-E": "B-E", "F": "F", "G": "G", "H": "H", "I": "I", "J": "J", "K-N": "K-N",
           "P-S": "P-S_X_S94"}
# Sub-sectors of industry, for the table of where the shock lands.
INDUSTRY_DETAIL = {"B": "Mining and quarrying", "C10-C12": "Food, beverages, tobacco",
                   "C13-C15": "Textiles, clothing, leather", "C16": "Wood products",
                   "C17": "Paper", "C19": "Coke and refined petroleum", "C20": "Chemicals",
                   "C21": "Pharmaceuticals", "C22": "Rubber and plastics",
                   "C23": "Non-metallic minerals (cement, glass)", "C24": "Basic metals",
                   "C25": "Fabricated metal products", "C26": "Computers, electronics",
                   "C27": "Electrical equipment", "C28": "Machinery", "C29": "Motor vehicles",
                   "D": "Electricity, gas, steam", "E36": "Water supply", "E37-E39": "Waste, sewerage"}

MODELS = {"REMIND": ("REMIND-MAgPIE 3.3-4.8", "REMIND-MAgPIE 3.3-4.8|EU 28"),
          "GCAM": ("GCAM 6.0 NGFS", "GCAM 6.0 NGFS|EU-15"),
          "MESSAGE": ("MESSAGEix-GLOBIOM 2.0-M-R12-NGFS", "MESSAGEix-GLOBIOM 2.0-R12|Western Europe")}
SCENARIOS = ["Net Zero 2050", "Below 2°C", "Low demand", "Delayed transition", "Fragmented World",
             "Nationally Determined Contributions (NDCs)", "Current Policies"]
ORDERLY = ["Net Zero 2050", "Below 2°C", "Low demand"]
DISORDERLY = ["Delayed transition", "Fragmented World"]
NGFS_YEARS = list(range(2020, 2055, 5))
NGFS_VARS = ["Price|Carbon", "Emissions|CO2|Energy and Industrial Processes"]

# Pre-registered choices (the headline); every one of them is swept.
HEADLINE = {"model": "REMIND", "disorderly": "Delayed transition", "orderly": "Net Zero 2050",
            "year": 2040, "sector": "B-E", "ref_year": 2022, "pass_through": 0.7, "lag": 12,
            "assets_scale": 1.0, "gas": "CO2", "abatement": False, "pd0": 0.02}
CHS_LAGS = [0, 6, 12, 24, 36]
YEAR_SWEEP = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]
N_MC = 4000
N_BOOT = 1000
PANEL_FIRST, PANEL_LAST = 2015, 2025
TEST_YEARS = [2019, 2020, 2021, 2022, 2023]
MORATORIUM_YEARS = (2020, 2021)


# ---------------------------------------------------------------- http

def _ctx():
    """Never disable verification."""
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


def _open(url, data=None, headers=None, timeout=180, tries=6):
    """GET or POST; on HTTP 429 or 5xx wait (Retry-After if given) and retry."""
    for k in range(tries):
        req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=_ctx())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            time.sleep(float(e.headers.get("Retry-After") or 5 * (k + 1)))


# ---------------------------------------------------------------- fetch

def jsonstat_rows(doc):
    """Flatten a JSON-stat 2.0 document into [(coordinates dict, value)]."""
    ids, sizes = doc["id"], doc["size"]
    names = [{v: k for k, v in doc["dimension"][i]["category"]["index"].items()} for i in ids]
    out = []
    for flat, v in doc["value"].items():
        k, coord = int(flat), {}
        for i, s, nm in zip(reversed(ids), reversed(sizes), reversed(names)):
            coord[i] = nm[k % s]
            k //= s
        out.append((coord, v))
    return out


def eurostat(dataset, **params):
    q = urllib.parse.urlencode({"format": "JSON", "lang": "EN", **params}, doseq=True)
    url = ES + dataset + "?" + q
    return jsonstat_rows(json.load(_open(url))), url


def fetch_ngfs():
    """Rows [model, scenario, region, variable, year, unit, value] for the three models' EU region."""
    token = json.load(_open(AUTH_URL))
    auth = {"Authorization": "Bearer " + token}
    runs = json.load(_open(NGFS_BASE + "/runs?getOnlyDefaultRuns=true", headers=auth))
    names = {m[0]: k for k, m in MODELS.items()}
    want = {r["run_id"]: r for r in runs if r["model"] in names and r["scenario"] in SCENARIOS}
    regions = sorted(m[1] for m in MODELS.values())
    body = {"filters": {"regions": regions, "variables": NGFS_VARS, "runs": sorted(want),
                        "years": NGFS_YEARS, "units": [], "timeslices": []}}
    rows = json.load(_open(NGFS_BASE + "/runs/bulk/ts", data=json.dumps(body).encode(),
                           headers={**auth, "Content-Type": "application/json"}))
    out = []
    for r in rows:
        key = names[r["model"]]
        if r["region"] != MODELS[key][1]:
            continue
        # The bulk rows spell "Below 2°C" with a question mark; the run list is the reference.
        out.append([key, want[r["runId"]]["scenario"], r["region"], r["variable"], r["year"],
                    r["unit"], r["value"]])
    return sorted(out)


def pdf_lines(raw):
    """Text lines of a PDF from its Flate streams. Only the standard library is allowed, so the TJ
    and Tj operators are read directly; a kerning gap wider than 150 units counts as a space."""
    out = []
    for s in re.findall(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        try:
            d = zlib.decompress(s)
        except zlib.error:
            continue
        for arr, lit in re.findall(rb"\[((?:[^\]\\]|\\.)*)\]\s*TJ|\(((?:[^)\\]|\\.)*)\)\s*Tj", d):
            if arr:
                t = ""
                for sx, num in re.findall(rb"\(((?:[^)\\]|\\.)*)\)|(-?\d+\.?\d*)", arr):
                    if sx:
                        t += sx.decode("latin1")
                    elif float(num) < -150:
                        t += " "
                out.append(t)
            else:
                out.append(lit.decode("latin1"))
    return out


def parse_chs(lines):
    """Table 3 of Campbell, Hilscher and Szilagyi (2008): the NIMTAAVG row (logit coefficient on
    quarterly net income over market total assets) at lags 0, 6, 12, 24, 36 months, and the
    absolute z statistics beneath it. Fails loudly if the layout is not found."""
    for i, l in enumerate(lines):
        if l.strip() == "NIMTAAVG" and i + 2 < len(lines):
            coef = [float(x) for x in re.findall(r"-?\d+\.\d+", lines[i + 1])]
            z = [float(x) for x in re.findall(r"\\\((\d+\.\d+)\\\)", lines[i + 2])]
            if len(coef) == 5 and len(z) == 5 and all(c < 0 for c in coef):
                return {"lags": CHS_LAGS, "coef": coef, "z": z,
                        "se": [abs(c) / zz for c, zz in zip(coef, z)]}
    raise RuntimeError("NIMTAAVG row of Table 3 not found in the Campbell-Hilscher-Szilagyi PDF")


def fetch_chs():
    return parse_chs(pdf_lines(_open(CHS_URL).read()))


def fetch_eurostat_all():
    """All Eurostat inputs, as {name: rows}, plus the URLs used."""
    raw, urls = {}, {}
    since = {"sinceTimePeriod": PANEL_FIRST - 1}
    raw["a64"], urls["a64"] = eurostat("nama_10_a64", unit="CP_MEUR", na_item=["B1G", "D1"], **since)
    raw["air"], urls["air"] = eurostat("env_ac_ainah_r2", unit="T", airpol=["CO2", "GHG"], **since)
    raw["nfa"], urls["nfa"] = eurostat("nama_10_nfa_st", unit="CRC_MEUR", asset10="N11N", **since)
    raw["rb"], urls["rb"] = eurostat("sts_rb_a", indic_bt="BKRT", unit="I15")
    raw["fx"], urls["fx"] = eurostat("ert_bil_eur_a", currency="USD", statinfo="AVG",
                                     sinceTimePeriod=2010)
    raw["hicp"], urls["hicp"] = eurostat("prc_hicp_aind", geo="EA", coicop="CP00",
                                         unit="INX_A_AVG", sinceTimePeriod=2010)
    return raw, urls


# ---------------------------------------------------------------- tables

def index_tables(raw):
    """Dictionaries keyed for lookup. Values below zero or missing are dropped."""
    a64, air, nfa = {}, {}, {}
    for c, v in raw["a64"]:
        a64[(c["geo"], c["nace_r2"], int(c["time"]), c["na_item"])] = v
    for c, v in raw["air"]:
        air[(c["geo"], c["nace_r2"], int(c["time"]), c["airpol"])] = v
    for c, v in raw["nfa"]:
        nfa[(c["geo"], c["nace_r2"], int(c["time"]))] = v
    rb = {}
    for c, v in raw["rb"]:
        if v and v > 0:
            rb[(c["geo"], c["nace_r2"], int(c["time"]))] = math.log(v)
    fx = {int(c["time"]): v for c, v in raw["fx"]}
    hicp = {int(c["time"]): v for c, v in raw["hicp"]}
    return {"a64": a64, "air": air, "nfa": nfa, "rb": rb, "fx": fx, "hicp": hicp}


def cell(T, geo, codes, year):
    """One country-sector-year: value added, compensation, fixed assets, CO2 and GHG (tonnes)
    summed over the A64 codes, or None if any component is missing."""
    gva = comp = k = co2 = ghg = 0.0
    for c in codes:
        vals = [T["a64"].get((geo, c, year, "B1G")), T["a64"].get((geo, c, year, "D1")),
                T["nfa"].get((geo, c, year)), T["air"].get((geo, c, year, "CO2")),
                T["air"].get((geo, c, year, "GHG"))]
        if any(v is None for v in vals):
            return None
        gva += vals[0]; comp += vals[1]; k += vals[2]; co2 += vals[3]; ghg += vals[4]
    if gva <= 0 or k <= 0:
        return None
    return {"gva": gva, "comp": comp, "k": k, "co2": co2, "ghg": ghg}


def aggregate(T, codes, year, geos=EU27):
    """EU27 aggregate of a sector in a year over the countries with complete data. The ratios are
    ratios of sums, so a large country weighs more, as it does in the sector."""
    cs = [(g, cell(T, g, codes, year)) for g in geos]
    cs = [(g, c) for g, c in cs if c]
    if not cs:
        return None
    s = {k: sum(c[k] for _, c in cs) for k in ("gva", "comp", "k", "co2", "ghg")}
    return {"n_countries": len(cs), "countries": [g for g, _ in cs],
            "profit_share": 1 - s["comp"] / s["gva"], "gva_over_k": s["gva"] / s["k"],
            "co2_per_gva": s["co2"] / s["gva"], "ghg_per_gva": s["ghg"] / s["gva"],
            "gva_meur": s["gva"], "co2_t": s["co2"]}


# ---------------------------------------------------------------- the channel

def price_eur(usd2010, fx, hicp, ref_year):
    """NGFS prices are US$2010 per tonne. Convert at the 2010 average rate, then inflate with the
    euro-area HICP to the prices of the reference year."""
    return usd2010 / fx[2010] * hicp[ref_year] / hicp[2010]


def cost_share(price_eur_per_t, t_per_eur_mn_gva):
    """Carbon cost as a share of gross value added: EUR per tonne x tonnes per EUR million of GVA,
    over one million."""
    return price_eur_per_t * t_per_eur_mn_gva / 1e6


def delta_profit(cost, pass_through):
    """Change in the profit share of value added, GVA held at its base level."""
    return -(1.0 - pass_through) * cost


def delta_logodds(d_profit, gva_over_k, coef, assets_scale=1.0):
    """Change in the log-odds of default. coef is on quarterly net income over market total
    assets, so an annual change in profit is divided by four. Net fixed assets stand in for total
    assets (assets_scale > 1 grosses them up); the tax shield is ignored."""
    return coef * d_profit * gva_over_k / assets_scale / 4.0


def logistic(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def pd_after(pd0, d_logodds):
    return logistic(math.log(pd0 / (1 - pd0)) + d_logodds)


# ---------------------------------------------------------------- scenario lookups

def index_ngfs(rows):
    """{(model, scenario, variable, year): value}."""
    return {(r[0], r[1], r[3], r[4]): r[6] for r in rows}


def abatement_factor(NG, model, scenario, year):
    """Regional CO2 (energy and industrial processes) in the year over its 2020 value, floored at
    zero: a crude stand-in for the sector shrinking its own emissions."""
    v = "Emissions|CO2|Energy and Industrial Processes"
    return max(NG[(model, scenario, v, year)] / NG[(model, scenario, v, 2020)], 0.0)


def logodds_shift(NG, T, stats, cfg, scenario, coef=None, beta_pp=None):
    """Change in log-odds of default of one sector, from today's static structure to `scenario`
    in cfg['year']. With `coef`, the Campbell-Hilscher-Szilagyi sensitivity through assets; with
    `beta_pp`, the semi-elasticity of bankruptcy declarations to the profit share, per percentage
    point, estimated on the Eurostat panel."""
    price = NG[(cfg["model"], scenario, "Price|Carbon", cfg["year"])]
    ei = stats["co2_per_gva" if cfg["gas"] == "CO2" else "ghg_per_gva"]
    if cfg["abatement"]:
        ei *= abatement_factor(NG, cfg["model"], scenario, cfg["year"])
    d_profit = delta_profit(cost_share(price_eur(price, T["fx"], T["hicp"], cfg["ref_year"]), ei),
                            cfg["pass_through"])
    if beta_pp is not None:
        return beta_pp * 100.0 * d_profit
    return delta_logodds(d_profit, stats["gva_over_k"], coef, cfg["assets_scale"])


def pair_change(NG, T, stats, cfg, coef=None, beta_pp=None):
    """PD under the disorderly and the orderly scenario at the baseline PD, and the change."""
    dl_dis = logodds_shift(NG, T, stats, cfg, cfg["disorderly"], coef, beta_pp)
    dl_ord = logodds_shift(NG, T, stats, cfg, cfg["orderly"], coef, beta_pp)
    pd_dis, pd_ord = pd_after(cfg["pd0"], dl_dis), pd_after(cfg["pd0"], dl_ord)
    return {"dl_dis": dl_dis, "dl_ord": dl_ord, "pd_dis": pd_dis, "pd_ord": pd_ord,
            "rel": pd_dis / pd_ord - 1.0, "bp": (pd_dis - pd_ord) * 1e4}


def reference_year(T, sector="B-E", min_countries=26):
    """Latest year in which at least `min_countries` report every series for the sector."""
    ys = [y for y in range(PANEL_LAST, PANEL_FIRST - 1, -1)
          if (aggregate(T, SECTORS[sector], y) or {"n_countries": 0})["n_countries"] >= min_countries]
    return ys[0]


# ---------------------------------------------------------------- the panel behind the check

def build_panel(T, years=range(PANEL_FIRST + 1, PANEL_LAST + 1)):
    """One-year changes by country, sector and year: log bankruptcy declarations (Eurostat index)
    and the profit share of value added in percentage points. Rows where either is missing drop."""
    rows = []
    for geo in EU27:
        for s, codes in SECTORS.items():
            for y in years:
                b1, b0 = T["rb"].get((geo, RB_CODE[s], y)), T["rb"].get((geo, RB_CODE[s], y - 1))
                p1, p0 = _profit_share(T, geo, codes, y), _profit_share(T, geo, codes, y - 1)
                if None in (b1, b0, p1, p0):
                    continue
                rows.append({"geo": geo, "sector": s, "year": y, "dlnb": b1 - b0,
                             "dps": 100.0 * (p1 - p0)})
    return rows


def _profit_share(T, geo, codes, year):
    gva = comp = 0.0
    for c in codes:
        g, d = T["a64"].get((geo, c, year, "B1G")), T["a64"].get((geo, c, year, "D1"))
        if g is None or d is None:
            return None
        gva += g; comp += d
    return None if gva <= 0 else 1 - comp / gva


def _design(rows, fe):
    """Design matrix: dps, then dummies for the fixed effects named in `fe`, then a constant."""
    cols = [np.array([r["dps"] for r in rows])]
    for spec in fe:
        keys = [tuple(r[k] for k in spec) for r in rows]
        levels = sorted(set(keys))[1:]
        for lv in levels:
            cols.append(np.array([1.0 if k == lv else 0.0 for k in keys]))
    cols.append(np.ones(len(rows)))
    return np.column_stack(cols)


FE_SPECS = {"country + sector-year": [("geo",), ("sector", "year")],
            "country + year": [("geo",), ("year",)]}


def fit_beta(rows, fe=FE_SPECS["country + sector-year"]):
    """Slope of one-year log change in bankruptcy declarations on the one-year change in profit
    share (per percentage point), with fixed effects, by least squares."""
    y = np.array([r["dlnb"] for r in rows])
    return float(np.linalg.lstsq(_design(rows, fe), y, rcond=None)[0][0])


def cluster_resample(rows, rng):
    """Draw countries with replacement; a country drawn twice becomes two clusters."""
    geos = sorted({r["geo"] for r in rows})
    by = {g: [r for r in rows if r["geo"] == g] for g in geos}
    out = []
    for j, g in enumerate(rng.choice(geos, len(geos))):
        out += [{**r, "geo": f"{g}#{j}"} for r in by[g]]
    return out


def bootstrap_beta(rows, fe, n=N_BOOT, seed=0):
    rng = np.random.default_rng(seed)
    return np.array([fit_beta(cluster_resample(rows, rng), fe) for _ in range(n)])


def demean_groups(rows, vals, key=("sector", "year")):
    """Subtract the mean within each sector-year; groups of fewer than three rows drop (index -1)."""
    groups = {}
    for i, r in enumerate(rows):
        groups.setdefault(tuple(r[k] for k in key), []).append(i)
    out, keep = np.zeros(len(rows)), np.zeros(len(rows), bool)
    for idx in groups.values():
        if len(idx) >= 3:
            out[idx] = vals[idx] - vals[idx].mean()
            keep[idx] = True
    return out, keep


def backtest(rows, kappa_by_sector, test_years=TEST_YEARS, fe=FE_SPECS["country + sector-year"]):
    """Out-of-sample test of the mapping. For each test year, fit the panel slope on earlier years
    only, then predict that year's sector-year-demeaned log change in bankruptcy declarations from
    the demeaned change in profit share. Three predictors: zero, the fitted slope, and the slope
    the literature mapping implies (kappa, per percentage point, by sector)."""
    pooled = {"y": [], "x": [], "own": [], "lit": [], "geo": [], "year": []}
    per_year = []
    for ty in test_years:
        train = [r for r in rows if r["year"] < ty]
        test = [r for r in rows if r["year"] == ty]
        if len(train) < 100 or len(test) < 10:
            continue
        b = fit_beta(train, fe)
        y, keep = demean_groups(test, np.array([r["dlnb"] for r in test]))
        x, _ = demean_groups(test, np.array([r["dps"] for r in test]))
        kap = np.array([kappa_by_sector[r["sector"]] for r in test])
        # the literature slope times the demeaned profit change, by row
        lit = kap * x
        y, x, lit = y[keep], x[keep], lit[keep]
        sse0 = float((y ** 2).sum())
        per_year.append({"year": ty, "n": int(keep.sum()), "beta_train": b,
                         "skill_own": 1 - float(((y - b * x) ** 2).sum()) / sse0,
                         "skill_lit": 1 - float(((y - lit) ** 2).sum()) / sse0,
                         "rmse_zero": math.sqrt(sse0 / len(y))})
        pooled["y"] += list(y); pooled["x"] += list(x); pooled["own"] += list(b * x)
        pooled["lit"] += list(lit)
        pooled["geo"] += [r["geo"] for r, k in zip(test, keep) if k]
        pooled["year"] += [ty] * int(keep.sum())
    return per_year, {k: np.array(v) for k, v in pooled.items()}


def calibration_slope(y, pred, geo, n=N_BOOT, seed=0):
    """Slope of realised on predicted through the origin, 95% interval by resampling countries.
    1 means the mapping is calibrated; 0 means it carries no information."""
    slope = lambda yy, pp: float((yy * pp).sum() / (pp ** 2).sum())
    rng = np.random.default_rng(seed)
    geos = sorted(set(geo))
    idx = {g: np.where(geo == g)[0] for g in geos}
    draws = []
    for _ in range(n):
        sel = np.concatenate([idx[g] for g in rng.choice(geos, len(geos))])
        draws.append(slope(y[sel], pred[sel]))
    return slope(y, pred), [float(v) for v in np.percentile(draws, [2.5, 97.5])]


def spearman(a, b):
    def rank(v):
        v = np.asarray(v, float)
        order = np.argsort(v, kind="mergesort")
        r = np.empty(len(v))
        r[order] = np.arange(len(v), dtype=float)
        for u in np.unique(v):
            m = v == u
            r[m] = r[m].mean()
        return r
    ra, rb = rank(a), rank(b)
    return float(np.corrcoef(ra, rb)[0, 1])


# ---------------------------------------------------------------- intervals

def mc_literature(NG, T, stats_by_sector, cfg, chs, n=N_MC, seed=0):
    """Draw the CHS sensitivity: a horizon uniformly from the five reported, then a normal draw
    around that horizon's coefficient. One draw per replicate is shared by every sector, since it
    is one transferable sensitivity and not one per sector. Returns {sector: rel changes} and the
    coefficients drawn."""
    rng = np.random.default_rng(seed)
    lag = rng.integers(0, len(chs["coef"]), n)
    coef = np.array(chs["coef"])[lag] + np.array(chs["se"])[lag] * rng.standard_normal(n)
    out = {s: np.array([pair_change(NG, T, st, cfg, coef=c)["rel"] for c in coef])
           for s, st in stats_by_sector.items()}
    return out, coef


# ---------------------------------------------------------------- the build

def sector_stats(T, ref_year, groups):
    return {s: a for s, codes in groups.items() if (a := aggregate(T, codes, ref_year))}


def write_csv(name, header, rows):
    with open(os.path.join(RESULTS, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def pct_span(vals):
    return max(vals) - min(vals)


def build():
    os.makedirs(RESULTS, exist_ok=True)
    access = time.strftime("%Y-%m-%d")
    ng_rows = fetch_ngfs()
    chs = fetch_chs()
    raw, urls = fetch_eurostat_all()
    T, NG = index_tables(raw), index_ngfs(ng_rows)
    write_csv("ngfs_eu_carbon.csv", ["model", "scenario", "region", "variable", "year", "unit", "value"],
              ng_rows)

    ref = reference_year(T)
    cfg = {**HEADLINE, "ref_year": ref}
    stats = sector_stats(T, ref, SECTORS)
    detail = sector_stats(T, ref, {c: [c] for c in INDUSTRY_DETAIL})
    be = stats[cfg["sector"]]
    coefs = dict(zip(chs["lags"], chs["coef"]))
    coef = coefs[cfg["lag"]]
    write_csv("sector_table.csv",
              ["code", "name", "n_countries", "profit_share", "gva_over_fixed_assets",
               "co2_t_per_eur_mn_gva", "ghg_t_per_eur_mn_gva", "gva_eur_mn"],
              [[s, s, a["n_countries"], a["profit_share"], a["gva_over_k"], a["co2_per_gva"],
                a["ghg_per_gva"], a["gva_meur"]] for s, a in stats.items()] +
              [[c, INDUSTRY_DETAIL[c], a["n_countries"], a["profit_share"], a["gva_over_k"],
                a["co2_per_gva"], a["ghg_per_gva"], a["gva_meur"]] for c, a in detail.items()])

    # --- headline through the literature sensitivity, and its range
    head = pair_change(NG, T, be, cfg, coef=coef)
    draws, cdraw = mc_literature(NG, T, stats, cfg, chs)
    lit_lo, lit_hi = [float(v) for v in np.percentile(draws[cfg["sector"]], [2.5, 97.5])]
    one_lag = {l: pair_change(NG, T, be, cfg, coef=c)["rel"] for l, c in coefs.items()}
    stat_only = np.array([pair_change(NG, T, be, cfg, coef=coef + chs["se"][2] * z)["rel"]
                          for z in np.random.default_rng(1).standard_normal(N_MC)])
    # a shared draw moves every sector in proportion: the ratio of log-shifts between two
    # sectors is the same in every replicate
    ratio_check = None
    if "H" in stats:
        a = np.log1p(draws["B-E"]); b = np.log1p(draws["H"])
        ratio_check = float(np.std(a / b) / abs(np.mean(a / b)))

    # --- the panel behind the check, and the interval from it
    rows = build_panel(T)
    write_csv("panel_changes.csv", ["country", "sector", "year", "d_ln_bankruptcies", "d_profit_share_pp"],
              [[r["geo"], r["sector"], r["year"], r["dlnb"], r["dps"]] for r in rows])
    main_fe = FE_SPECS["country + sector-year"]
    beta = fit_beta(rows, main_fe)
    bdraw = bootstrap_beta(rows, main_fe)
    beta_ci = [float(v) for v in np.percentile(bdraw, [2.5, 97.5])]
    own_rel = lambda b: pair_change(NG, T, be, cfg, beta_pp=b)["rel"]
    own_draws = np.array([own_rel(b) for b in bdraw])
    own_lo, own_hi = [float(v) for v in np.percentile(own_draws, [2.5, 97.5])]
    kappa_lit = coef * be["gva_over_k"] / 4.0 / 100.0
    panel_specs = []
    for name, fe in FE_SPECS.items():
        for label, sel in (("all years", rows),
                           ("excluding 2020-2021", [r for r in rows if r["year"] not in (2020, 2021)])):
            b = fit_beta(sel, fe)
            panel_specs.append({"fe": name, "sample": label, "n": len(sel), "beta": b,
                                "rel": own_rel(b)})

    # --- backtest of the mapping on years it did not see
    kappa = {s: coefs[cfg["lag"]] * st["gva_over_k"] / 4.0 / 100.0 for s, st in stats.items()}
    per_year, pooled = backtest(rows, kappa)
    def metrics(mask):
        y, lit, own = pooled["y"][mask], pooled["lit"][mask], pooled["own"][mask]
        sl, ci = calibration_slope(y, lit, pooled["geo"][mask])
        sse0 = float((y ** 2).sum())
        return {"n": int(mask.sum()), "rmse_zero": math.sqrt(sse0 / len(y)),
                "skill_own": 1 - float(((y - own) ** 2).sum()) / sse0,
                "skill_lit": 1 - float(((y - lit) ** 2).sum()) / sse0,
                "slope_lit": sl, "slope_lit_ci": ci}
    allm = np.ones(len(pooled["y"]), bool)
    bt = {"test_years": [r["year"] for r in per_year], "per_year": per_year,
          "all": metrics(allm), "ex_moratorium": metrics(~np.isin(pooled["year"], MORATORIUM_YEARS)),
          "kappa_lit_be": kappa[cfg["sector"]],
          "sd_dps_be_pp": float(np.std([r["dps"] for r in rows if r["sector"] == cfg["sector"]])),
          "sd_dlnb": float(np.std([r["dlnb"] for r in rows]))}
    sl_lit, sl_lit_ci = bt["all"]["slope_lit"], bt["all"]["slope_lit_ci"]
    # what the literature mapping, rescaled by its calibration slope, gives for the headline
    scaled = pair_change(NG, T, be, cfg, beta_pp=sl_lit * kappa_lit * 1.0)["rel"]
    scaled_ci = sorted(pair_change(NG, T, be, cfg, beta_pp=s * kappa_lit)["rel"] for s in sl_lit_ci)

    # --- scenarios against today, and the price paths
    pdb = cfg["pd0"]
    vs_base = []
    for m in MODELS:
        for sc in SCENARIOS:
            c2 = {**cfg, "model": m}
            dl = logodds_shift(NG, T, be, c2, sc, coef=coef)
            vs_base.append({"model": m, "scenario": sc, "price_usd2010": NG[(m, sc, "Price|Carbon", cfg["year"])],
                            "cost_share": cost_share(price_eur(NG[(m, sc, "Price|Carbon", cfg["year"])], T["fx"], T["hicp"], ref), be["co2_per_gva"]),
                            "d_logodds": dl, "pd": pd_after(pdb, dl), "rel_vs_today": pd_after(pdb, dl) / pdb - 1})
    prices = [{"model": m, "scenario": sc, "year": y, "price": NG[(m, sc, "Price|Carbon", y)],
               "emissions": NG[(m, sc, "Emissions|CO2|Energy and Industrial Processes", y)]}
              for m in MODELS for sc in SCENARIOS for y in NGFS_YEARS
              if (m, sc, "Price|Carbon", y) in NG]
    cmp_ = {}
    for m in MODELS:
        d = lambda sc: [NG[(m, sc, "Price|Carbon", y)] for y in NGFS_YEARS if y >= 2025]
        cmp_[m] = {"delayed_below_nz_every_year_2025_2050": all(a <= b for a, b in zip(d("Delayed transition"), d("Net Zero 2050"))),
                   "delayed_above_below2_2040": NG[(m, "Delayed transition", "Price|Carbon", 2040)] > NG[(m, "Below 2°C", "Price|Carbon", 2040)],
                   "delayed_above_lowdemand_2040": NG[(m, "Delayed transition", "Price|Carbon", 2040)] > NG[(m, "Low demand", "Price|Carbon", 2040)]}

    # --- sweeps (headline metric: PD change, disorderly vs orderly, industry, at the baseline PD)
    sweeps = []

    def add(factor, value, rel, bp=None, note=""):
        sweeps.append({"factor": factor, "value": value, "rel": rel, "bp": bp, "note": note})

    def run(over, kind="lit", lag=None):
        c2 = {**cfg, **over}
        st = sector_stats(T, c2["ref_year"], SECTORS)[c2["sector"]] if "ref_year" in over else (stats[c2["sector"]])
        r = pair_change(NG, T, st, c2, coef=coefs[c2["lag"] if lag is None else lag] if kind == "lit" else None,
                        beta_pp=beta if kind == "own" else None)
        return r["rel"], r["bp"]

    for pt in (0.0, 0.25, 0.5, 0.7, 0.85, 1.0):
        add("pass-through of carbon cost", pt, *run({"pass_through": pt}))
    for y in (2030, 2035, 2040, 2045, 2050):
        add("year", y, *run({"year": y}))
    for m in MODELS:
        add("IAM", m, *run({"model": m}))
    for o in ORDERLY:
        for d in DISORDERLY:
            add("scenario pair", f"{d} vs {o}", *run({"orderly": o, "disorderly": d}))
    for ry in YEAR_SWEEP:
        if (aggregate(T, SECTORS["B-E"], ry) or {"n_countries": 0})["n_countries"] >= 20:
            add("reference year of ratios", ry, *run({"ref_year": ry}))
    for l in CHS_LAGS:
        add("horizon of the CHS coefficient (months)", l, *run({}, lag=l))
    for sc_ in (1.0, 2.0, 3.0):
        add("total assets as multiple of net fixed assets", sc_, *run({"assets_scale": sc_}))
    add("gas", "CO2", *run({"gas": "CO2"}))
    add("gas", "all GHG", *run({"gas": "GHG"}))
    add("abatement", "static intensity", *run({"abatement": False}))
    add("abatement", "intensity follows regional emissions", *run({"abatement": True}))
    for p0 in (0.005, 0.01, 0.02, 0.05, 0.10):
        add("baseline PD", p0, *run({"pd0": p0}))
    add("sensitivity source", "CHS 12-month", *run({}))
    for ps_ in panel_specs:
        add("sensitivity source", f"EU panel, {ps_['fe']}, {ps_['sample']}", ps_["rel"],
            pair_change(NG, T, be, cfg, beta_pp=ps_["beta"])["bp"])
    add("sensitivity source", "CHS rescaled by calibration slope", scaled,
        pair_change(NG, T, be, cfg, beta_pp=sl_lit * kappa_lit)["bp"])
    sl_x = bt["ex_moratorium"]["slope_lit"]
    add("sensitivity source", "CHS rescaled by slope, excluding 2020-2021 test years",
        pair_change(NG, T, be, cfg, beta_pp=sl_x * kappa_lit)["rel"],
        pair_change(NG, T, be, cfg, beta_pp=sl_x * kappa_lit)["bp"])
    # leave one country out of the sector aggregate
    loo = []
    for g in EU27:
        a = aggregate(T, SECTORS["B-E"], ref, [x for x in EU27 if x != g])
        if a and g in stats["B-E"]["countries"]:
            loo.append((g, pair_change(NG, T, a, cfg, coef=coef)["rel"]))

    summary = []
    for f in dict.fromkeys(s["factor"] for s in sweeps):
        v = [s["rel"] for s in sweeps if s["factor"] == f]
        summary.append({"factor": f, "lo": min(v), "hi": max(v), "span": pct_span(v),
                        "flips_sign": min(v) < 0 < max(v)})
    summary.append({"factor": "leave one country out of the sector", "lo": min(v for _, v in loo),
                    "hi": max(v for _, v in loo), "span": pct_span([v for _, v in loo]),
                    "flips_sign": min(v for _, v in loo) < 0 < max(v for _, v in loo)})
    summary.sort(key=lambda s: -s["span"])

    # --- where in industry, and whether the order of sectors holds
    detail_rows = []
    for c, a in detail.items():
        r = pair_change(NG, T, a, cfg, coef=coef)
        detail_rows.append({"code": c, "name": INDUSTRY_DETAIL[c], "n_countries": a["n_countries"],
                            "co2_per_gva": a["co2_per_gva"], "gva_over_k": a["gva_over_k"], **r})
    detail_rows.sort(key=lambda r: r["rel"])
    sector_rows = []
    for s, a in stats.items():
        sector_rows.append({"sector": s, "n_countries": a["n_countries"], "co2_per_gva": a["co2_per_gva"],
                            "profit_share": a["profit_share"], "gva_over_k": a["gva_over_k"],
                            **pair_change(NG, T, a, cfg, coef=coef)})
    ranks = []
    for ry in YEAR_SWEEP:
        st2 = sector_stats(T, ry, SECTORS)
        common = [s for s in stats if s in st2]
        if len(common) >= 6:
            ranks.append({"ref_year": ry, "n_sectors": len(common),
                          "spearman_vs_headline": spearman(
                              [pair_change(NG, T, stats[s], cfg, coef=coef)["dl_ord"] for s in common],
                              [pair_change(NG, T, st2[s], {**cfg, "ref_year": ry}, coef=coef)["dl_ord"] for s in common])})
    coverage = {y: (aggregate(T, SECTORS["B-E"], y) or {"n_countries": 0})["n_countries"]
                for y in range(PANEL_FIRST, PANEL_LAST + 1)}

    out = {
        "meta": {"access_date": access, "urls": urls, "ngfs_base": NGFS_BASE, "chs_url": CHS_URL,
                 "ref_year": ref, "ref_year_rule": "latest year with at least 26 EU27 countries reporting every series for NACE B-E",
                 "n_ngfs_rows": len(ng_rows), "n_panel": len(rows)},
        "config": cfg, "chs": chs,
        "headline": {**head, "sector_stats": be, "coef": coef, "lit_lo": lit_lo, "lit_hi": lit_hi,
                     "lit_stat_lo": float(np.percentile(stat_only, 2.5)),
                     "lit_stat_hi": float(np.percentile(stat_only, 97.5)),
                     "by_lag": one_lag, "own_lo": own_lo, "own_hi": own_hi,
                     "own_rel": own_rel(beta), "beta_pp": beta, "beta_ci": beta_ci,
                     "scaled_rel": scaled, "scaled_ci": scaled_ci,
                     "shared_draw_ratio_cv": ratio_check,
                     "coef_draw_range": [float(cdraw.min()), float(cdraw.max())]},
        "panel_specs": panel_specs, "backtest": bt, "vs_base": vs_base, "prices": prices,
        "price_comparisons": cmp_, "sweeps": sweeps, "sweep_summary": summary,
        "leave_one_country": [{"country": g, "rel": v} for g, v in loo],
        "sectors": sector_rows, "detail": detail_rows, "rank_stability": ranks,
        "coverage_be": coverage,
        "fx_2010": T["fx"][2010], "hicp_ratio": T["hicp"][ref] / T["hicp"][2010],
    }
    with open(os.path.join(RESULTS, "scenario_pd.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    return out


if __name__ == "__main__":
    o = build()
    h = o["headline"]
    print(f"ref year {o['meta']['ref_year']}; PD change disorderly vs orderly {h['rel']:+.1%} "
          f"literature range [{h['lit_lo']:+.1%}, {h['lit_hi']:+.1%}] panel [{h['own_lo']:+.1%}, {h['own_hi']:+.1%}]")
    for s in o["sweep_summary"][:6]:
        print(f"  {s['factor']}: {s['lo']:+.1%} to {s['hi']:+.1%}")
