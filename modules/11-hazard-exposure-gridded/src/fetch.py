"""Fetch every input of module 11 from its public endpoint into data/raw/ and log it.

    python3 src/fetch.py

Nothing is typed: plants from WRI, hazard grids from the World Bank CCKP public S3 bucket,
country polygons from Natural Earth, country aggregates from the CCKP API (used only to validate
the grid read). results/fetch_log.json records URL, access date, size and SHA-256 of each file.
"""
import datetime
import hashlib
import json
import os
import ssl
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
RES = os.path.join(HERE, "..", "results")

S3 = "https://wbg-cckp.s3.amazonaws.com/data/cmip6-x0.25/hd35"
API = "https://cckpapi.worldbank.org/cckp/v1"
COUNTRIES = ["ITA", "ESP", "FRA", "DEU", "NLD", "PRT", "GRC", "AUT", "BEL", "IRL", "POL"]


def _f(scen, stat, period):
    return (f"{S3}/ensemble-all-{scen}/climatology-hd35-annual-mean_cmip6-x0.25_"
            f"ensemble-all-{scen}_climatology_{stat}_{period}.nc")


GRIDS = {
    "hist_median": _f("historical", "median", "1995-2014"),
    "hist_p10": _f("historical", "p10", "1995-2014"),
    "hist_p90": _f("historical", "p90", "1995-2014"),
    "ssp245_median": _f("ssp245", "median", "2040-2059"),
    "ssp245_p10": _f("ssp245", "p10", "2040-2059"),
    "ssp245_p90": _f("ssp245", "p90", "2040-2059"),
    "ssp370_median": _f("ssp370", "median", "2040-2059"),
}
WRI = ("https://raw.githubusercontent.com/wri/global-power-plant-database/master/"
       "output_database/global_power_plant_database.csv")
NE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
      "ne_50m_admin_0_countries.geojson")
# the same CCKP collections module 01 queries
API_COLLECTIONS = {
    "hist_median": "cmip6-x0.25_climatology_hd35_climatology_annual_1995-2014_median_historical_ensemble_all_mean",
    "ssp245_median": "cmip6-x0.25_climatology_hd35_climatology_annual_2040-2059_median_ssp245_ensemble_all_mean",
    "ssp370_median": "cmip6-x0.25_climatology_hd35_climatology_annual_2040-2059_median_ssp370_ensemble_all_mean",
}
for _s in ("p10", "p90"):
    API_COLLECTIONS[f"hist_{_s}"] = ("cmip6-x0.25_climatology_hd35_climatology_annual_1995-2014_"
                                     f"{_s}_historical_ensemble_all_mean")
    API_COLLECTIONS[f"ssp245_{_s}"] = ("cmip6-x0.25_climatology_hd35_climatology_annual_2040-2059_"
                                       f"{_s}_ssp245_ensemble_all_mean")


def ctx():
    """Never disable verification."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for p in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        try:
            return ssl.create_default_context(cafile=p)
        except Exception:
            continue
    return ssl.create_default_context()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with urllib.request.urlopen(req, timeout=180, context=ctx()) as r:
        return r.read(), r.status


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(RES, exist_ok=True)
    today = datetime.date.today().isoformat()
    log = []
    items = [(f"grid_{k}.nc", u) for k, u in GRIDS.items()]
    items += [("wri_gppd.csv", WRI), ("ne_50m_admin_0_countries.geojson", NE)]
    for fn, url in items:
        data, status = get(url)
        open(os.path.join(RAW, fn), "wb").write(data)
        log.append({"file": fn, "url": url, "accessed": today, "http_status": status,
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        print(f"{fn}: {len(data):,} bytes")
    api = {}
    for k, coll in API_COLLECTIONS.items():
        url = f"{API}/{coll}/{','.join(COUNTRIES)}?_format=json"
        data, status = get(url)
        payload = json.loads(data)
        if payload.get("metadata", {}).get("status") != "success":
            raise RuntimeError(f"CCKP API: {payload.get('metadata')}")
        api[k] = {iso: float(next(iter(s.values()))) for iso, s in payload["data"].items()}
        log.append({"file": f"api_{k}", "url": url, "accessed": today, "http_status": status,
                    "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    json.dump(api, open(os.path.join(RAW, "cckp_country_api.json"), "w"), indent=1)
    json.dump(log, open(os.path.join(RES, "fetch_log.json"), "w"), indent=1)
    print("fetch_log.json written")


if __name__ == "__main__":
    main()
