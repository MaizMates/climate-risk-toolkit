"""Thermal generating capacity exposed to rising heat stress, joined at country resolution.

ESTIMAND. The share of total thermal generating capacity, in MW, across the countries in
module 01's hazard table, that sits in a country whose projected annual count of days at or
above a 35C heat index rises by more than k days from baseline to mid-century under SSP2-4.5.

Scope narrowed on 21/09/2026: the original module asked for plants joined to hazard *grid
cells*. The World Bank CCKP API returned HTTP 502 when that build ran, and module 01's committed
output is country-level, not gridded, so the gridded version cannot be built from anything
currently in hand. This module joins at the resolution the data actually supports and says so
throughout, rather than waiting on someone else's outage. See modules/11 in the roadmap for the
gridded successor.

Data:
- Plants: WRI Global Power Plant Database, output_database/global_power_plant_database.csv,
  raw.githubusercontent.com, public, no key.
- Hazard: modules/01-heat-stress-gradient/results/heat_gradient.json, already in this repository.
  This is the reuse the roadmap intends: module 03 consumes module 01's output rather than
  re-fetching the hazard layer.
- Validation: Eurostat nrg_inf_epc, combustible-fuel net electrical capacity, public
  dissemination API, no key. An independent capacity source module 01 does not touch.
"""
import csv
import io
import json
import math
import os
import random
import ssl
import urllib.request

WRI_URL = ("https://raw.githubusercontent.com/wri/global-power-plant-database/master/"
           "output_database/global_power_plant_database.csv")
EUROSTAT_CF_URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
                    "nrg_inf_epc?format=JSON&lang=EN&siec=CF&plant_tec=CAP_NET_ELC"
                    "&operator=TOTAL&unit=MW")

# Coal, oil and petcoke are thermal under any reasonable definition. Gas and biomass are the
# arguable ones -- a CCGT is thermal by any engineering definition but is also the technology
# transition plans lean on as a bridge fuel, and biomass is carbon-accounted as near-zero despite
# burning fuel. Both are swept in the sensitivity section instead of being asserted away.
THERMAL_CORE = {"Coal", "Oil", "Petcoke"}
GAS = {"Gas"}
BIOMASS = {"Biomass", "Waste"}

ISO3_TO_EUROSTAT2 = {"AUT": "AT", "BEL": "BE", "DEU": "DE", "ESP": "ES", "FRA": "FR",
                      "GRC": "EL", "IRL": "IE", "ITA": "IT", "NLD": "NL", "POL": "PL",
                      "PRT": "PT"}

K_VALUES = [0, 1, 2, 3, 5, 8]
K_REFERENCE = 2
N_BOOT = 2000

HAZARD_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                 "01-heat-stress-gradient", "results", "heat_gradient.json"),
    "/tmp/module-build-Te0u/repo/modules/01-heat-stress-gradient/results/heat_gradient.json",
]


def _ctx():
    """Never disable verification: a silently unverified fetch is how you analyse someone
    else's data without knowing it."""
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


def fetch_wri(url=WRI_URL):
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with urllib.request.urlopen(req, timeout=120, context=_ctx()) as r:
        text = r.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def hazard_path():
    for c in HAZARD_CANDIDATES:
        if os.path.exists(c):
            return c
    raise FileNotFoundError(
        "module 01 hazard output not found; expected heat_gradient.json at one of: "
        + ", ".join(HAZARD_CANDIDATES))


def load_hazard(scenario="ssp245"):
    """{iso3: change_days} for one scenario, read from module 01's committed output."""
    rows = json.load(open(hazard_path()))
    return {r["iso3"]: r["change_days"] for r in rows if r["scenario"] == scenario}


def fetch_eurostat_cf(url=EUROSTAT_CF_URL):
    """Latest available year of combustible-fuel net electrical capacity, by Eurostat geo2."""
    with urllib.request.urlopen(url, timeout=60, context=_ctx()) as r:
        doc = json.load(r)
    dim = doc["dimension"]
    times = dim["time"]["category"]["index"]
    geos = dim["geo"]["category"]["index"]
    n_time = len(times)
    years_desc = sorted(times, key=int, reverse=True)
    out = {}
    for geo, gi in geos.items():
        for y in years_desc:
            v = doc["value"].get(str(gi * n_time + times[y]))
            if v is not None:
                out[geo] = {"year": y, "mw": float(v)}
                break
    return out


def thermal_fuels(include_gas=True, include_biomass=False):
    fuels = set(THERMAL_CORE)
    if include_gas:
        fuels |= GAS
    if include_biomass:
        fuels |= BIOMASS
    return fuels


def load_thermal_plants(wri_rows, iso3_set, fuels):
    out = []
    for row in wri_rows:
        if row["country"] not in iso3_set or row["primary_fuel"] not in fuels:
            continue
        try:
            cap = float(row["capacity_mw"])
        except (TypeError, ValueError):
            continue
        if cap <= 0:
            continue
        out.append({"country": row["country"], "name": row["name"], "capacity_mw": cap})
    return out


def exposed_share(plants, hazard, k):
    """Capacity-weighted share of plants sitting in a country whose change_days exceeds k."""
    total = sum(p["capacity_mw"] for p in plants)
    if total == 0:
        return None
    exposed = sum(p["capacity_mw"] for p in plants
                  if hazard.get(p["country"], float("-inf")) > k)
    return exposed / total


def bootstrap_ci(plants, hazard, k, n=N_BOOT, seed=0):
    """Resample plants with replacement: the capacity distribution is heavily skewed by a few
    large plants, and an interval that ignores that skew understates how much the answer would
    move if a handful of the largest plants were different."""
    rng = random.Random(seed)
    n_p = len(plants)
    if n_p == 0:
        return None, None
    shares = []
    for _ in range(n):
        sample = [plants[rng.randrange(n_p)] for _ in range(n_p)]
        s = exposed_share(sample, hazard, k)
        if s is not None:
            shares.append(s)
    shares.sort()
    lo = shares[int(0.025 * (len(shares) - 1))]
    hi = shares[int(0.975 * (len(shares) - 1))]
    return lo, hi


def top10_share_of_exposed(plants, hazard, k):
    exposed_plants = [p for p in plants if hazard.get(p["country"], float("-inf")) > k]
    exposed_total = sum(p["capacity_mw"] for p in exposed_plants)
    if exposed_total == 0:
        return None
    top10 = sorted(exposed_plants, key=lambda p: -p["capacity_mw"])[:10]
    return sum(p["capacity_mw"] for p in top10) / exposed_total


def build(k_values=K_VALUES, seed=0):
    wri_rows = fetch_wri()
    hazard = load_hazard()
    iso3_set = set(hazard)

    try:
        eurostat_cf = fetch_eurostat_cf()
    except Exception as e:
        eurostat_cf = None
        eurostat_error = str(e)
    else:
        eurostat_error = None

    base_fuels = thermal_fuels(include_gas=True, include_biomass=False)
    plants = load_thermal_plants(wri_rows, iso3_set, base_fuels)

    by_country_cap = {}
    for p in plants:
        by_country_cap[p["country"]] = by_country_cap.get(p["country"], 0.0) + p["capacity_mw"]
    total_mw = sum(by_country_cap.values())

    validation_rows = []
    for iso3, geo2 in sorted(ISO3_TO_EUROSTAT2.items()):
        wri_mw = by_country_cap.get(iso3, 0.0)
        es = eurostat_cf.get(geo2) if eurostat_cf else None
        validation_rows.append({
            "iso3": iso3,
            "wri_thermal_mw": wri_mw,
            "eurostat_combustible_mw": es["mw"] if es else None,
            "eurostat_year": es["year"] if es else None,
            "ratio_wri_over_eurostat": (wri_mw / es["mw"]) if es and es["mw"] else None,
        })

    k_rows = []
    for k in k_values:
        share = exposed_share(plants, hazard, k)
        lo, hi = bootstrap_ci(plants, hazard, k, seed=seed)
        top10 = top10_share_of_exposed(plants, hazard, k)
        k_rows.append({"k": k, "exposed_share": share, "ci_lo": lo, "ci_hi": hi,
                       "top10_share_of_exposed": top10,
                       "n_countries_exposed": len({p["country"] for p in plants
                                                    if hazard.get(p["country"], float("-inf")) > k})})

    # Sensitivity to the fuel definition, at the reference k. The roadmap flags this as the
    # choice that moves the answer more than the threshold does, so it gets its own table.
    fuel_sens = []
    for include_gas in (True, False):
        for include_biomass in (False, True):
            fuels = thermal_fuels(include_gas, include_biomass)
            p2 = load_thermal_plants(wri_rows, iso3_set, fuels)
            share = exposed_share(p2, hazard, K_REFERENCE)
            lo, hi = bootstrap_ci(p2, hazard, K_REFERENCE, seed=seed)
            fuel_sens.append({"include_gas": include_gas, "include_biomass": include_biomass,
                              "n_plants": len(p2),
                              "total_mw": sum(x["capacity_mw"] for x in p2),
                              "exposed_share": share, "ci_lo": lo, "ci_hi": hi})

    by_country = []
    for iso3 in sorted(iso3_set):
        cap = by_country_cap.get(iso3, 0.0)
        by_country.append({
            "iso3": iso3, "thermal_mw": cap,
            "share_of_total_thermal": (cap / total_mw) if total_mw else None,
            "change_days_ssp245": hazard[iso3],
            "exposed_at_k_reference": hazard[iso3] > K_REFERENCE,
        })
    by_country.sort(key=lambda r: -r["thermal_mw"])

    out = {
        "estimand": ("share of total thermal generating capacity, in MW, across the countries "
                     "in module 01's hazard table, sitting in a country whose projected change "
                     "in annual days >=35C heat index (baseline 1995-2014 to mid-century "
                     "2040-2059, SSP2-4.5) exceeds k days"),
        "thermal_definition_base": sorted(base_fuels),
        "k_reference": K_REFERENCE,
        "n_plants": len(plants),
        "n_countries": len(by_country_cap),
        "total_thermal_mw": total_mw,
        "by_country": by_country,
        "exposure_by_k": k_rows,
        "fuel_definition_sensitivity": fuel_sens,
        "validation_eurostat": {
            "source": "Eurostat nrg_inf_epc, combustible fuels (siec=CF), net max electrical "
                      "capacity, operator=TOTAL",
            "error": eurostat_error,
            "rows": validation_rows,
        },
    }
    os.makedirs("results", exist_ok=True)
    with open("results/hazard_exposure.json", "w") as f:
        json.dump(out, f, indent=1)

    ref = next(r for r in k_rows if r["k"] == K_REFERENCE)
    print(f"{len(plants)} thermal plants across {len(by_country_cap)} countries, "
          f"{total_mw:,.0f} MW total")
    print(f"at k={K_REFERENCE}: exposed share {ref['exposed_share']:.1%} "
          f"[{ref['ci_lo']:.1%}, {ref['ci_hi']:.1%}], "
          f"top 10 plants = {ref['top10_share_of_exposed']:.1%} of exposed capacity")
    print("\nexposed share by k:")
    for r in k_rows:
        print(f"  k={r['k']:>2d}  share={r['exposed_share']:6.1%}  "
              f"ci=[{r['ci_lo']:.1%}, {r['ci_hi']:.1%}]  countries={r['n_countries_exposed']}")
    print("\nfuel definition sensitivity at k=2:")
    for r in fuel_sens:
        print(f"  gas={str(r['include_gas']):5s} biomass={str(r['include_biomass']):5s}  "
              f"n={r['n_plants']:5d}  mw={r['total_mw']:10,.0f}  "
              f"share={r['exposed_share']:.1%}  ci=[{r['ci_lo']:.1%}, {r['ci_hi']:.1%}]")
    if eurostat_error:
        print(f"\nvalidation: Eurostat fetch failed ({eurostat_error}), section recorded as such")
    else:
        diffs = [r["ratio_wri_over_eurostat"] for r in validation_rows
                 if r["ratio_wri_over_eurostat"] is not None]
        print(f"\nvalidation: WRI/Eurostat capacity ratio across {len(diffs)} countries, "
              f"median {sorted(diffs)[len(diffs)//2]:.2f}")
    return out


if __name__ == "__main__":
    build()
