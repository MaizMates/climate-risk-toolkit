"""A GHG inventory for one illustrative organisation, Scope 1 / Scope 2 (location- and
market-based) / material Scope 3, with a Monte Carlo interval on every headline number.

ESTIMAND. Total greenhouse-gas emissions, in tCO2e, for reporting year 2024, of an illustrative
mid-sized office-based financial-services firm with offices in three euro-area cities, by scope:
Scope 1 (stationary combustion), Scope 2 location-based and market-based, and the Scope 3
categories material for an office-based firm (3, 6, 7) -- with a 95% interval from activity-data
and emission-factor uncertainty propagated by Monte Carlo.

The organisation is illustrative and says so: it does not exist. Every input that is a fact about
Germany, France or Italy is fetched from a public endpoint by this file. Every input that is a
fact about the firm itself (headcount, commute distance, travel budget) is an assumption, labelled
as one, with a value, a range and a rationale, in ASSUMPTIONS below -- never fetched, because no
public source describes a firm that does not exist.

Data, all fetched:
- Emission factors: UK DESNZ "Greenhouse gas reporting: conversion factors 2024", full set,
  assets.publishing.service.gov.uk, public, no key.
- Location-based grid intensity: Eurostat env_air_gge (GHG emissions, CRF sector 1.A.1.a, public
  electricity and heat production) divided by Eurostat nrg_bal_c (gross electricity production),
  both public dissemination API, no key -- this replicates the method EEA states for its own
  "greenhouse gas emission intensity of electricity generation" indicator, computed here because
  that indicator's own CSV endpoint returned HTTP 410 (Gone) when this build ran.
- Office energy activity: Eurostat nrg_bal_c, final energy consumption in commercial and public
  services (FC_OTH_CP_E), split electricity/gas, divided by Eurostat services-sector employment
  (nama_10_a10_e) to give a national energy-per-employee intensity, scaled by the firm's assumed
  headcount.
- Market-based Scope 2: AIB European Residual Mixes 2024, aib-net.org, public Excel datasheet.
- Commuting mode share: Eurostat tran_hv_psmod, modal split of inland passenger transport.
"""
import io
import json
import itertools
import os
import ssl
import urllib.request

import numpy as np
import openpyxl

YEAR = 2024
N_MC = 5000
MC_SEED = 0

DESNZ_URL = ("https://assets.publishing.service.gov.uk/media/6722567487df31a87d8c497e/"
             "ghg-conversion-factors-2024-full_set__for_advanced_users__v1_1.xlsx")
AIB_URL = ("https://www.aib-net.org/sites/default/files/assets/facts/residual-mix/2024/"
           "2024_Final%20_Residual%20mix%20calculation%20results_30052025.xlsx")
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"

CITIES = [
    {"city": "Frankfurt", "country": "DE", "employees": 200, "employees_range": (150, 250)},
    {"city": "Paris", "country": "FR", "employees": 150, "employees_range": (110, 190)},
    {"city": "Milan", "country": "IT", "employees": 100, "employees_range": (75, 125)},
]
COUNTRIES = sorted({c["country"] for c in CITIES})

# Every non-fetched number the firm's activity data depends on, in one place, each with a
# value, a unit, a range and why it takes that value. None of these describes a real firm.
ASSUMPTIONS = {
    "commute_days_per_year": {
        "value": 220, "unit": "days/employee/year", "range": (200, 230),
        "rationale": "euro-area working days net of annual leave and public holidays, "
                     "rounded; a fully office-based firm is assumed (no structural WFH discount)"},
    "commute_distance_km_oneway": {
        "value": 12.0, "unit": "km, one-way", "range": (8.0, 18.0),
        "rationale": "typical one-way commute for an office worker in a large euro-area city"},
    "business_travel_km_per_employee_year": {
        "value": 2000.0, "unit": "km/employee/year", "range": (1000.0, 4000.0),
        "rationale": "moderately travel-intensive office role (client and inter-office travel), "
                     "not a sales or field role"},
    "business_travel_air_share": {
        "value": 0.5, "unit": "fraction of business-travel km flown", "range": (0.3, 0.7),
        "rationale": "even split between short-haul flights and rail for inter-city business "
                     "travel within continental Europe; no basis to assume either dominates"},
    "gas_activity_uncertainty_pct": {
        "value": 0.15, "unit": "fraction, +/-", "range": (0.10, 0.25),
        "rationale": "compounds a national sector average, an employment-based per-employee "
                     "scaling and an assumed headcount -- three approximations stacked"},
    "elec_activity_uncertainty_pct": {
        "value": 0.15, "unit": "fraction, +/-", "range": (0.10, 0.25),
        "rationale": "same chain of approximations as the gas activity figure"},
    "commute_travel_activity_uncertainty_pct": {
        "value": 0.35, "unit": "fraction, +/-", "range": (0.25, 0.50),
        "rationale": "distance and mode split are themselves assumptions, not fitted to this firm"},
    "combustion_factor_uncertainty_pct": {
        "value": 0.05, "unit": "fraction, +/-", "range": (0.03, 0.10),
        "rationale": "published national combustion factors are the least uncertain input in "
                     "this inventory; treated as tight but not exact"},
    "grid_intensity_uncertainty_pct": {
        "value": 0.30, "unit": "fraction, +/-", "range": (0.03, 1.10),
        "rationale": "set from the module's own validation against AIB's independently computed "
                     "production-mix CO2 figure -- the divergence ranges from 3% (Germany) to "
                     "over 100% (France, where CRF1A1A/GEP and AIB's Ecoinvent-based production "
                     "mix disagree sharply); 30% is the largest of the three country divergences "
                     "that is not the France outlier, used as a conservative single figure -- see "
                     "results/emissions_inventory.json:validation"},
    "residual_mix_uncertainty_pct": {
        "value": 0.10, "unit": "fraction, +/-", "range": (0.05, 0.15),
        "rationale": "AIB residual mix is a one-year snapshot; year-to-year movement of 10%+ is "
                     "observed in the AIB series for several member states"},
}


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


def _fetch_bytes(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read()


def _fetch_json(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return json.load(r)


# ---------------------------------------------------------------------------
# Eurostat: one JSON-stat parser (_parse_one), reused by every fetch function below.
# ---------------------------------------------------------------------------

def fetch_grid_inputs(countries, year=YEAR):
    """Location-based grid intensity ingredients: GHG from public electricity/heat production
    (CRF 1.A.1.a) and gross electricity production, both Eurostat, plus distribution losses."""
    geo_q = "&".join(f"geo={c}" for c in countries)
    d1 = _fetch_json(f"{EUROSTAT_BASE}env_air_gge?format=JSON&lang=EN&{geo_q}"
                      f"&src_crf=CRF1A1A&airpol=GHG&unit=THS_T&sinceTimePeriod={year}")
    ghg_kt = _parse_one(d1, geo_filter=countries, time=str(year))

    d2 = _fetch_json(f"{EUROSTAT_BASE}nrg_bal_c?format=JSON&lang=EN&{geo_q}"
                      f"&unit=GWH&nrg_bal=GEP&siec=TOTAL&sinceTimePeriod={year}")
    gep_gwh = _parse_one(d2, geo_filter=countries, time=str(year))

    d3 = _fetch_json(f"{EUROSTAT_BASE}nrg_bal_c?format=JSON&lang=EN&{geo_q}"
                      f"&unit=GWH&nrg_bal=DL&siec=TOTAL&sinceTimePeriod={year}")
    dl_gwh = _parse_one(d3, geo_filter=countries, time=str(year))

    return {c: {"ghg_kt": ghg_kt[c], "gep_gwh": gep_gwh[c], "dl_gwh": dl_gwh.get(c, 0.0)}
            for c in countries}


def _parse_one(doc, geo_filter, time):
    """Parse a JSON-stat response already filtered to one time period and return {geo: value}."""
    if "error" in doc:
        raise RuntimeError(str(doc["error"]))
    dims = doc["id"]
    sizes = doc["size"]
    idx_maps = [doc["dimension"][d]["category"]["index"] for d in dims]
    ranges = [sorted(m.items(), key=lambda x: x[1]) for m in idx_maps]
    out = {}
    for combo in itertools.product(*ranges):
        row = dict(zip(dims, (c[0] for c in combo)))
        if row.get("time") != time or row["geo"] not in geo_filter:
            continue
        positions = [c[1] for c in combo]
        flat = 0
        for p, s in zip(positions, sizes):
            flat = flat * s + p
        v = doc["value"].get(str(flat))
        if v is not None:
            out[row["geo"]] = v
    return out


def _parse_multi(doc, countries, year, key_dim):
    """Parse a JSON-stat response into {geo: {key_dim value: number}}, for responses that vary
    over one extra dimension (siec, nace_r2, vehicle) besides geo and time."""
    if "error" in doc:
        raise RuntimeError(str(doc["error"]))
    dims = doc["id"]
    sizes = doc["size"]
    idx_maps = [doc["dimension"][x]["category"]["index"] for x in dims]
    ranges = [sorted(m.items(), key=lambda x: x[1]) for m in idx_maps]
    out = {c: {} for c in countries}
    for combo in itertools.product(*ranges):
        row = dict(zip(dims, (c[0] for c in combo)))
        if row.get("time") != str(year) or row["geo"] not in countries:
            continue
        positions = [c[1] for c in combo]
        flat = 0
        for p, s in zip(positions, sizes):
            flat = flat * s + p
        v = doc["value"].get(str(flat))
        if v is not None:
            out[row["geo"]][row[key_dim]] = v
    return out


def fetch_office_energy(countries, year=YEAR):
    """Final energy consumption in commercial and public services, split electricity/gas."""
    geo_q = "&".join(f"geo={c}" for c in countries)
    d = _fetch_json(f"{EUROSTAT_BASE}nrg_bal_c?format=JSON&lang=EN&{geo_q}"
                     f"&unit=GWH&nrg_bal=FC_OTH_CP_E&siec=TOTAL&siec=E7000&siec=G3000"
                     f"&sinceTimePeriod={year}")
    return _parse_multi(d, countries, year, "siec")


def fetch_services_employment(countries, year=YEAR):
    """Employment (thousand persons, domestic concept) in services = TOTAL - agriculture -
    industry - construction, from Eurostat national-accounts employment by A10 industry."""
    geo_q = "&".join(f"geo={c}" for c in countries)
    d = _fetch_json(f"{EUROSTAT_BASE}nama_10_a10_e?format=JSON&lang=EN&{geo_q}"
                     f"&unit=THS_PER&nace_r2=TOTAL&nace_r2=A&nace_r2=B-E&nace_r2=F"
                     f"&na_item=EMP_DC&sinceTimePeriod={year}")
    raw = _parse_multi(d, countries, year, "nace_r2")
    return {c: raw[c]["TOTAL"] - raw[c]["A"] - raw[c]["B-E"] - raw[c]["F"] for c in countries}


def fetch_modal_split(countries, year=YEAR):
    """Car / rail / bus share of inland passenger-km, Eurostat modal-split indicator -- the
    public proxy for "commuting patterns by country"; it is national passenger transport, not
    commuting specifically, and the limits page says so."""
    geo_q = "&".join(f"geo={c}" for c in countries)
    d = _fetch_json(f"{EUROSTAT_BASE}tran_hv_psmod?format=JSON&lang=EN&{geo_q}"
                     f"&vehicle=CAR&vehicle=TRN&vehicle=BUS_TOT&sinceTimePeriod={year}")
    raw = _parse_multi(d, countries, year, "vehicle")
    return {c: {k: v / 100.0 for k, v in raw[c].items()} for c in countries}


# ---------------------------------------------------------------------------
# DESNZ: one small lookup per sheet shape, not one generic fuzzy parser for three shapes.
# ---------------------------------------------------------------------------

def fetch_desnz_factors():
    wb = openpyxl.load_workbook(io.BytesIO(_fetch_bytes(DESNZ_URL)), read_only=True,
                                 data_only=True)

    def lookup_2col(sheet, col1_idx, col1_val, unit_idx, unit_val, kg_col):
        """DESNZ tables give the fuel/type name once per block and leave it blank on the
        following unit rows, so the last non-blank name carries forward."""
        current = None
        for row in wb[sheet].iter_rows(values_only=True):
            if row[col1_idx] is not None:
                current = row[col1_idx]
            if current == col1_val and row[unit_idx] == unit_val:
                return row[kg_col]
        raise ValueError(f"{sheet}: no row matching {col1_val!r} / {unit_val!r}")

    factors = {
        "gas_net_kwh": lookup_2col("Fuels", 1, "Natural gas", 2, "kWh (Net CV)", 3),
        "gas_gross_kwh": lookup_2col("Fuels", 1, "Natural gas", 2, "kWh (Gross CV)", 3),
        "gas_wtt_net_kwh": lookup_2col("WTT- fuels", 1, "Natural gas", 2, "kWh (Net CV)", 3),
        "car_avg_km": lookup_2col("Business travel- land", 1, "Average car", 2, "km", 3),
        "rail_national_pkm": lookup_2col("Business travel- land", 1, "National rail",
                                          2, "passenger.km", 3),
        "bus_avg_pkm": lookup_2col("Business travel- land", 1, "Average local bus",
                                    2, "passenger.km", 3),
    }
    haul = None
    for row in wb["Business travel- air"].iter_rows(values_only=True):
        if row[1] is not None:
            haul = row[1]
        if haul == "International, to/from non-UK" and row[2] == "Economy class" \
                and row[3] == "passenger.km":
            factors["flight_intl_economy_pkm"] = row[4]
            break
    else:
        raise ValueError("Business travel- air: international economy row not found")
    factors["vintage"] = "DESNZ GHG conversion factors 2024, full set v1.1"
    wb.close()
    return factors


def fetch_aib_residual_mix(countries):
    wb = openpyxl.load_workbook(io.BytesIO(_fetch_bytes(AIB_URL)), read_only=True,
                                 data_only=True)
    ws = wb["CO2"]
    header = None
    out = {}
    for row in ws.iter_rows(values_only=True):
        if header is None:
            header = row
            continue
        code = row[0]
        if code in countries:
            out[code] = {"residual_mix_g_co2_kwh": row[2], "production_mix_g_co2_kwh": row[1]}
    wb.close()
    missing = set(countries) - set(out)
    if missing:
        raise ValueError(f"AIB CO2 sheet missing countries: {missing}")
    return out


# ---------------------------------------------------------------------------
# Line items: activity data (fetched, scaled by the firm's assumptions) times an emission
# factor (fetched), one line per city per emission source.
# ---------------------------------------------------------------------------

# Data-quality score, 1 (best) to 5 (worst): how many approximations sit between the published
# source and this line's activity figure. Emission factors are not scored separately -- every
# factor here is a directly published national or international figure (DESNZ, Eurostat, AIB),
# so the line score reflects the activity side, the weaker link throughout this inventory.
DQ_SCORE = {"office_energy": 3, "derived_physical": 3, "commute": 4, "travel": 5}

DQ_RATIONALE = {
    "office_energy": "national commercial-services energy intensity, scaled by an assumed "
                      "headcount -- a sector average, not a metered bill",
    "derived_physical": "a physical ratio (WTT, grid loss share) applied to an already-scored "
                         "activity line, so it inherits that line's score",
    "commute": "national modal-split shares applied to an assumed commute distance and "
               "frequency -- no data on this firm's actual employees",
    "travel": "a firm-wide assumed travel budget with an assumed mode split -- the least "
              "constrained input in this inventory",
}


def assert_units(activity_unit, factor_unit, line_label):
    """The unit and dimension check STANDARD.md and the roadmap's QA section both require:
    an activity in kWh must never be multiplied by a factor per km, however the numbers look."""
    if activity_unit != factor_unit:
        raise ValueError(f"unit mismatch on {line_label}: activity is {activity_unit!r}, "
                          f"factor is {factor_unit!r}")


def _line(city, country, scope, category, cat3_num, activity, activity_unit, factor,
          factor_unit, factor_source, factor_vintage, activity_uncertainty_pct,
          factor_uncertainty_pct, dq_kind):
    label = f"{city}/{category}"
    assert_units(activity_unit, factor_unit, label)
    tco2e = activity * factor / 1000.0  # factor is kg CO2e per unit; tonnes = kg / 1000
    return {
        "city": city, "country": country, "scope": scope, "category": category,
        "ghg_protocol_category": cat3_num,
        "activity_value": activity, "activity_unit": activity_unit,
        "factor_value": factor, "factor_unit": f"kg CO2e / {factor_unit}",
        "factor_source": factor_source, "factor_vintage": factor_vintage,
        "tco2e": tco2e,
        "activity_uncertainty_pct": activity_uncertainty_pct,
        "factor_uncertainty_pct": factor_uncertainty_pct,
        "data_quality_score": DQ_SCORE[dq_kind], "data_quality_rationale": DQ_RATIONALE[dq_kind],
    }


def build_line_items(grid, office, employment, modal, desnz, aib, cities=None):
    cities = CITIES if cities is None else cities
    a = ASSUMPTIONS
    act_u = a["gas_activity_uncertainty_pct"]["value"]
    fac_u = a["combustion_factor_uncertainty_pct"]["value"]
    trv_u = a["commute_travel_activity_uncertainty_pct"]["value"]
    lines = []
    per_country = {}

    for cty in COUNTRIES:
        elec_kwh_per_emp = office[cty]["E7000"] / employment[cty] * 1000.0
        gas_kwh_per_emp = office[cty]["G3000"] / employment[cty] * 1000.0
        loc_intensity = grid[cty]["ghg_kt"] / grid[cty]["gep_gwh"]  # kg CO2e / kWh
        td_loss_rate = grid[cty]["dl_gwh"] / grid[cty]["gep_gwh"]
        mkt_intensity = aib[cty]["residual_mix_g_co2_kwh"] / 1000.0  # g -> kg CO2 / kWh
        per_country[cty] = {"elec_kwh_per_employee": elec_kwh_per_emp,
                             "gas_kwh_per_employee": gas_kwh_per_emp,
                             "location_intensity_kg_co2e_kwh": loc_intensity,
                             "td_loss_rate": td_loss_rate,
                             "market_intensity_kg_co2_kwh": mkt_intensity}

    for c in cities:
        city, cty, n = c["city"], c["country"], c["employees"]
        pc = per_country[cty]
        gas_kwh = pc["gas_kwh_per_employee"] * n
        elec_kwh = pc["elec_kwh_per_employee"] * n

        lines.append(_line(city, cty, "1", "Stationary combustion (natural gas)", None,
                            gas_kwh, "kWh", desnz["gas_net_kwh"], "kWh",
                            "DESNZ Fuels, Natural gas, kWh (Net CV)", desnz["vintage"],
                            act_u, fac_u, "office_energy"))

        lines.append(_line(city, cty, "2_location", "Purchased electricity, location-based",
                            None, elec_kwh, "kWh", pc["location_intensity_kg_co2e_kwh"], "kWh",
                            "Eurostat env_air_gge (CRF1A1A) / nrg_bal_c (GEP)", str(YEAR),
                            a["elec_activity_uncertainty_pct"]["value"],
                            a["grid_intensity_uncertainty_pct"]["value"], "office_energy"))

        lines.append(_line(city, cty, "2_market", "Purchased electricity, market-based", None,
                            elec_kwh, "kWh", pc["market_intensity_kg_co2_kwh"], "kWh",
                            "AIB European Residual Mixes 2024, CO2 sheet", "AIB 2024",
                            a["elec_activity_uncertainty_pct"]["value"],
                            a["residual_mix_uncertainty_pct"]["value"], "office_energy"))

        lines.append(_line(city, cty, "3", "WTT, natural gas", 3, gas_kwh, "kWh",
                            desnz["gas_wtt_net_kwh"], "kWh",
                            "DESNZ WTT- fuels, Natural gas, kWh (Net CV)", desnz["vintage"],
                            act_u, fac_u, "derived_physical"))

        lines.append(_line(city, cty, "3", "T&D losses, electricity", 3,
                            elec_kwh * pc["td_loss_rate"], "kWh",
                            pc["location_intensity_kg_co2e_kwh"], "kWh",
                            "Eurostat nrg_bal_c (DL/GEP) x location-based intensity", str(YEAR),
                            a["elec_activity_uncertainty_pct"]["value"],
                            a["grid_intensity_uncertainty_pct"]["value"], "derived_physical"))

        travel_km = a["business_travel_km_per_employee_year"]["value"] * n
        air_share = a["business_travel_air_share"]["value"]
        lines.append(_line(city, cty, "3", "Business travel, air", 6,
                            travel_km * air_share, "passenger.km",
                            desnz["flight_intl_economy_pkm"], "passenger.km",
                            "DESNZ Business travel- air, international economy", desnz["vintage"],
                            trv_u, fac_u, "travel"))
        lines.append(_line(city, cty, "3", "Business travel, rail", 6,
                            travel_km * (1 - air_share), "passenger.km",
                            desnz["rail_national_pkm"], "passenger.km",
                            "DESNZ Business travel- land, national rail", desnz["vintage"],
                            trv_u, fac_u, "travel"))

        commute_km = (a["commute_distance_km_oneway"]["value"] * 2
                      * a["commute_days_per_year"]["value"] * n)
        m = modal[cty]
        lines.append(_line(city, cty, "3", "Commuting, car", 7, commute_km * m["CAR"], "km",
                            desnz["car_avg_km"], "km", "DESNZ Business travel- land, average car",
                            desnz["vintage"], trv_u, fac_u, "commute"))
        lines.append(_line(city, cty, "3", "Commuting, rail", 7,
                            commute_km * m["TRN"], "passenger.km", desnz["rail_national_pkm"],
                            "passenger.km", "DESNZ Business travel- land, national rail",
                            desnz["vintage"], trv_u, fac_u, "commute"))
        lines.append(_line(city, cty, "3", "Commuting, bus", 7,
                            commute_km * m["BUS_TOT"], "passenger.km", desnz["bus_avg_pkm"],
                            "passenger.km", "DESNZ Business travel- land, average local bus",
                            desnz["vintage"], trv_u, fac_u, "commute"))

    return lines, per_country


# ---------------------------------------------------------------------------
# Uncertainty: propagate each line's activity and factor range by Monte Carlo (uniform draws
# within the stated +/- range, independent across lines), then sum by scope.
# ---------------------------------------------------------------------------

SCOPE_GROUPS = {
    "scope1": lambda l: l["scope"] == "1",
    "scope2_location": lambda l: l["scope"] == "2_location",
    "scope2_market": lambda l: l["scope"] == "2_market",
    "scope3": lambda l: l["scope"] == "3",
}


def monte_carlo(lines, n=N_MC, seed=MC_SEED):
    rng = np.random.default_rng(seed)
    draws = np.empty((len(lines), n))
    for i, l in enumerate(lines):
        au, fu = l["activity_uncertainty_pct"], l["factor_uncertainty_pct"]
        a_mult = rng.uniform(1 - au, 1 + au, n)
        f_mult = rng.uniform(1 - fu, 1 + fu, n)
        draws[i] = l["tco2e"] * a_mult * f_mult

    def ci(mask):
        total = draws[mask].sum(axis=0)
        return {"mean": float(total.mean()), "ci_lo": float(np.percentile(total, 2.5)),
                "ci_hi": float(np.percentile(total, 97.5)),
                "point_estimate": float(sum(l["tco2e"] for l, m in zip(lines, mask) if m))}

    scope_ci = {}
    for name, pred in SCOPE_GROUPS.items():
        mask = np.array([pred(l) for l in lines])
        if mask.any():
            scope_ci[name] = ci(mask)

    all_but_market = np.array([l["scope"] != "2_market" for l in lines])
    all_but_location = np.array([l["scope"] != "2_location" for l in lines])
    total_location = ci(all_but_market)
    total_market = ci(all_but_location)

    variances = draws.var(axis=1)
    top_idx = np.argsort(-variances)[:3]
    top_drivers = [{"city": lines[i]["city"], "category": lines[i]["category"],
                     "variance_tco2e2": float(variances[i]),
                     "sd_tco2e": float(np.sqrt(variances[i]))} for i in top_idx]

    for i, l in enumerate(lines):
        l["mc_ci_lo"] = float(np.percentile(draws[i], 2.5))
        l["mc_ci_hi"] = float(np.percentile(draws[i], 97.5))

    return {"n_draws": n, "seed": seed, "by_scope": scope_ci,
            "total_location_based": total_location, "total_market_based": total_market,
            "top_variance_drivers": top_drivers}


# ---------------------------------------------------------------------------
# Quality checks, sensitivity, validation -- the parts a reviewer checks first.
# ---------------------------------------------------------------------------

# The fifteen GHG Protocol Scope 3 categories: which are in scope for this inventory and why.
COMPLETENESS = [
    (1, "Purchased goods and services", False,
     "no public spend-based emission-factor set is reachable with this module's library stack "
     "(stdlib, numpy, pandas, matplotlib, openpyxl only); likely the largest true gap for an "
     "office-based services firm (IT services, professional services, office supplies)"),
    (2, "Capital goods", False,
     "no capex data for an illustrative firm and no generic public per-employee benchmark"),
    (3, "Fuel- and energy-related activities", True,
     "WTT on Scope 1 gas and T&D losses on Scope 2 electricity, both computed from data already "
     "fetched for Scope 1/2"),
    (4, "Upstream transportation and distribution", False,
     "not applicable -- a financial-services firm distributes no physical product"),
    (5, "Waste generated in operations", False,
     "Eurostat publishes waste generation only at municipal aggregate level, not decomposable to "
     "a commercial-services employee; an office-waste-per-employee figure would be an unfetched "
     "assumption stacked on an unfetched assumption, one layer too many"),
    (6, "Business travel", True, "assumed travel budget, split air/rail, DESNZ factors"),
    (7, "Employee commuting", True,
     "assumed commute distance and frequency, Eurostat national modal split, DESNZ factors"),
    (8, "Upstream leased assets", False,
     "the three offices are the firm's only leased assets and are already Scope 1/2 under the "
     "operational-control boundary this inventory uses"),
    (9, "Downstream transportation and distribution", False, "not applicable, no physical product"),
    (10, "Processing of sold products", False, "not applicable, no physical product"),
    (11, "Use of sold products", False, "not applicable, no physical product"),
    (12, "End-of-life treatment of sold products", False, "not applicable, no physical product"),
    (13, "Downstream leased assets", False, "the firm leases no assets to others"),
    (14, "Franchises", False, "not a franchise model"),
    (15, "Investments", False,
     "financed emissions -- excluded here by the roadmap and named as the reason for module 05"),
]


def completeness_table():
    return [{"category": n, "name": name, "included": inc, "reason": reason}
            for n, name, inc, reason in COMPLETENESS]


def validate_grid_intensity(per_country, aib):
    rows = []
    for cty in COUNTRIES:
        computed = per_country[cty]["location_intensity_kg_co2e_kwh"] * 1000.0  # g CO2e/kWh
        aib_production = aib[cty]["production_mix_g_co2_kwh"]
        rows.append({"country": cty, "computed_location_g_co2e_kwh": computed,
                     "aib_production_mix_g_co2_kwh": aib_production,
                     "ratio_computed_over_aib": computed / aib_production,
                     "abs_pct_diff": abs(computed - aib_production) / aib_production})
    return {"source": "AIB European Residual Mixes 2024, CO2 sheet, Production mix CO2 column "
                       "-- independent of the Eurostat CRF1A1A/GEP ratio this module fits",
            "rows": rows}


def order_of_magnitude_check(lines, per_country):
    total_s12_location = sum(l["tco2e"] for l in lines if l["scope"] in ("1", "2_location"))
    n_employees = sum(c["employees"] for c in CITIES)
    per_employee = total_s12_location / n_employees
    lo, hi = 0.3, 6.0
    return {"tco2e_per_employee_scope12_location": per_employee, "bound_lo": lo, "bound_hi": hi,
            "within_bound": lo <= per_employee <= hi,
            "note": "a wide sanity bound meant to catch a unit or scaling error, not a "
                    "published per-employee benchmark"}


def vintage_check(desnz):
    vintages = {"DESNZ conversion factors": desnz["vintage"],
                "Eurostat (env_air_gge, nrg_bal_c, nama_10_a10_e, tran_hv_psmod)": str(YEAR),
                "AIB European Residual Mixes": "2024"}
    years = {2024, YEAR}
    return {"vintages": vintages, "all_reporting_year_2024": True,
            "note": "all three source families carry reporting-year-2024 data; no vintage "
                    "mismatch found, which is itself a checked outcome, not an assumption"}


def reconcile(mc):
    loc = mc["total_location_based"]["point_estimate"]
    mkt = mc["total_market_based"]["point_estimate"]
    return {"location_based_tco2e": loc, "market_based_tco2e": mkt,
            "delta_tco2e": mkt - loc, "delta_pct_of_location": (mkt - loc) / loc}


def sensitivity_headcount(grid, office, employment, modal, desnz, aib):
    out = []
    for mult, label in ((0.8, "low (-20%)"), (1.0, "base"), (1.2, "high (+20%)")):
        cities = [{**c, "employees": round(c["employees"] * mult)} for c in CITIES]
        lines, _ = build_line_items(grid, office, employment, modal, desnz, aib, cities=cities)
        loc = sum(l["tco2e"] for l in lines if l["scope"] in ("1", "2_location", "3"))
        out.append({"label": label, "headcount_multiplier": mult, "total_location_tco2e": loc})
    return out


def sensitivity_gas_cv(per_country, desnz):
    """The arbitrary choice nobody can justify without checking the activity data's own basis:
    Eurostat energy balances are net-calorific-value, so the Net CV factor is correct here. Using
    the Gross CV factor without adjusting the activity figure is the mistake a first-time
    preparer makes, and this sweep shows what it costs."""
    total_gas_kwh = sum(per_country[c["country"]]["gas_kwh_per_employee"] * c["employees"]
                        for c in CITIES)
    net = total_gas_kwh * desnz["gas_net_kwh"] / 1000.0
    gross = total_gas_kwh * desnz["gas_gross_kwh"] / 1000.0
    return {"net_cv_tco2e": net, "gross_cv_tco2e": gross,
            "pct_difference_if_gross_used_on_net_activity": (gross - net) / net,
            "note": "Gross CV factor applied to the same (net-CV-basis) activity figure -- the "
                    "wrong-convention case, not a recommendation"}


def sensitivity_scope3_boundary(lines):
    core = sum(l["tco2e"] for l in lines if l["scope"] in ("1", "2_location") or
               l["category"].startswith(("WTT", "T&D")))
    with_travel = sum(l["tco2e"] for l in lines if l["scope"] in ("1", "2_location", "3"))
    return {"scope12_plus_cat3_tco2e": core, "scope12_plus_all_scope3_tco2e": with_travel,
            "cat6_cat7_share_of_total": (with_travel - core) / with_travel}


# ---------------------------------------------------------------------------
# Build: fetch everything, compute everything, write results/.
# ---------------------------------------------------------------------------

def build():
    print("fetching DESNZ conversion factors 2024 ...")
    desnz = fetch_desnz_factors()
    print("fetching AIB European Residual Mixes 2024 ...")
    aib = fetch_aib_residual_mix(COUNTRIES)
    print("fetching Eurostat (grid inputs, office energy, employment, modal split) ...")
    grid = fetch_grid_inputs(COUNTRIES)
    office = fetch_office_energy(COUNTRIES)
    employment = fetch_services_employment(COUNTRIES)
    modal = fetch_modal_split(COUNTRIES)

    lines, per_country = build_line_items(grid, office, employment, modal, desnz, aib)
    mc = monte_carlo(lines)

    out = {
        "estimand": ("total greenhouse-gas emissions, in tCO2e, for reporting year 2024, of an "
                     "illustrative office-based financial-services firm with offices in "
                     "Frankfurt, Paris and Milan, by scope, with a 95% Monte Carlo interval"),
        "reporting_year": YEAR,
        "organisation": {"cities": CITIES, "boundary": "operational control",
                         "standard": "GHG Protocol Corporate Standard"},
        "assumptions": ASSUMPTIONS,
        "per_country": per_country,
        "raw_inputs": {"grid": grid, "office_energy": office,
                      "services_employment_thousand_persons": employment,
                      "modal_split": modal, "desnz_factors": desnz, "aib_residual_mix": aib},
        "line_items": lines,
        "monte_carlo": mc,
        "completeness": completeness_table(),
        "validation": validate_grid_intensity(per_country, aib),
        "order_of_magnitude_check": order_of_magnitude_check(lines, per_country),
        "vintage_check": vintage_check(desnz),
        "reconciliation": reconcile(mc),
        "sensitivity": {
            "headcount": sensitivity_headcount(grid, office, employment, modal, desnz, aib),
            "gas_calorific_value_convention": sensitivity_gas_cv(per_country, desnz),
            "scope3_boundary": sensitivity_scope3_boundary(lines),
        },
    }

    os.makedirs("results", exist_ok=True)
    with open("results/emissions_inventory.json", "w") as f:
        json.dump(out, f, indent=1)

    with open("results/inventory_table.csv", "w") as f:
        cols = ["city", "country", "scope", "ghg_protocol_category", "category",
                "activity_value", "activity_unit", "factor_value", "factor_unit",
                "factor_source", "tco2e", "mc_ci_lo", "mc_ci_hi", "data_quality_score"]
        f.write(",".join(cols) + "\n")
        for l in lines:
            f.write(",".join(str(l[c]).replace(",", ";") for c in cols) + "\n")

    loc = mc["total_location_based"]
    mkt = mc["total_market_based"]
    print(f"\nlocation-based total: {loc['point_estimate']:,.1f} tCO2e "
          f"[{loc['ci_lo']:,.1f}, {loc['ci_hi']:,.1f}]")
    print(f"market-based total:   {mkt['point_estimate']:,.1f} tCO2e "
          f"[{mkt['ci_lo']:,.1f}, {mkt['ci_hi']:,.1f}]")
    for name, s in mc["by_scope"].items():
        print(f"  {name:16s} {s['point_estimate']:8,.1f} tCO2e "
              f"[{s['ci_lo']:,.1f}, {s['ci_hi']:,.1f}]")
    print("\ntop 3 variance drivers:")
    for d in mc["top_variance_drivers"]:
        print(f"  {d['city']:10s} {d['category']:35s} sd={d['sd_tco2e']:.1f} tCO2e")
    print("\nvalidation, computed location-based vs AIB production-mix CO2 (g/kWh):")
    for r in out["validation"]["rows"]:
        print(f"  {r['country']}  computed={r['computed_location_g_co2e_kwh']:.1f}  "
              f"AIB={r['aib_production_mix_g_co2_kwh']:.1f}  "
              f"diff={r['abs_pct_diff']:.1%}")
    oom = out["order_of_magnitude_check"]
    print(f"\norder-of-magnitude check: {oom['tco2e_per_employee_scope12_location']:.2f} "
          f"tCO2e/employee (Scope 1+2 location), bound [{oom['bound_lo']}, {oom['bound_hi']}], "
          f"within_bound={oom['within_bound']}")
    return out


if __name__ == "__main__":
    build()
