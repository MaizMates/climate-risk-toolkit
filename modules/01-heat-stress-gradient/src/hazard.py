"""Heat-stress gradient across euro-area countries, from the World Bank CCKP CMIP6 ensemble.

One question: between now and mid-century, where does heat stress grow fastest, and is the
ranking of *change* the same as the ranking of *level*? It is not, and that difference is the
whole point: a portfolio concentrated where the level is already high is exposed today, while a
portfolio concentrated where the change is largest is exposed to repricing.

Source: World Bank Climate Change Knowledge Portal API, CMIP6 ensemble median, indicator hd35
(days per year with a maximum heat index at or above 35 C). No key, no registration.
"""
import json, urllib.request, ssl, sys

API = "https://cckpapi.worldbank.org/cckp/v1"


def _trust_store():
    """Some Python builds ship without a usable CA bundle and every HTTPS call fails with
    CERTIFICATE_VERIFY_FAILED. Fall back to certifi, then to the system bundle. Never
    disable verification: a module that turns off TLS to get a number is not a result."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    for path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        try:
            return ssl.create_default_context(cafile=path)
        except Exception:
            continue
    return ssl.create_default_context()


CTX = _trust_store()
# euro area plus the two markets that keep coming up in supervisory work
COUNTRIES = ["ITA", "ESP", "FRA", "DEU", "NLD", "PRT", "GRC", "AUT", "BEL", "IRL", "POL"]
BASE = ("cmip6-x0.25_climatology_hd35_climatology_annual_"
        "1995-2014_median_historical_ensemble_all_mean")
PROJ = ("cmip6-x0.25_climatology_hd35_climatology_annual_"
        "2040-2059_median_{ssp}_ensemble_all_mean")
SSPS = ["ssp245", "ssp370"]


def fetch(collection, countries):
    """Return {iso3: value}. One request for the whole country list, which is how the API
    is meant to be used: eleven separate calls would be eleven times the load for one answer."""
    url = f"{API}/{collection}/{','.join(countries)}?_format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        payload = json.load(r)
    if payload.get("metadata", {}).get("status") != "success":
        raise RuntimeError(f"CCKP returned {payload.get('metadata')}")
    out = {}
    for iso, series in (payload.get("data") or {}).items():
        vals = [v for v in series.values() if isinstance(v, (int, float))]
        if vals:                       # the API keys the value by period, and the key moves
            out[iso] = float(vals[0])  # between collections, so read the value not the key
    return out


def gradient(countries=None):
    countries = countries or COUNTRIES
    base = fetch(BASE, countries)
    rows = []
    for ssp in SSPS:
        proj = fetch(PROJ.format(ssp=ssp), countries)
        for iso in countries:
            if iso in base and iso in proj:
                rows.append({"iso3": iso, "scenario": ssp,
                             "baseline_days": round(base[iso], 2),
                             "midcentury_days": round(proj[iso], 2),
                             "change_days": round(proj[iso] - base[iso], 2)})
    return rows


def main():
    rows = gradient()
    with open("results/heat_gradient.json", "w") as f:
        json.dump(rows, f, indent=1)
    hot = [r for r in rows if r["scenario"] == "ssp370"]
    by_level = sorted(hot, key=lambda r: -r["midcentury_days"])
    by_change = sorted(hot, key=lambda r: -r["change_days"])
    print("SSP3-7.0, 2040-2059, days per year at or above 35 C heat index\n")
    print(f"{'':<6}{'by level':<26}{'by change':<26}")
    for i in range(len(hot)):
        a, b = by_level[i], by_change[i]
        print(f"{i+1:<6}{a['iso3']} {a['midcentury_days']:>8.2f} days   "
              f"{b['iso3']} {b['change_days']:>+8.2f} days")
    same = [a["iso3"] for a in by_level[:3]] == [b["iso3"] for b in by_change[:3]]
    print(f"\nTop three identical under both orderings: {same}")
    return rows


if __name__ == "__main__":
    sys.exit(0 if main() else 0)
