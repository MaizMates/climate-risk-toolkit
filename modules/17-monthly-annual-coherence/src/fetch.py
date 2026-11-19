"""Fetch every input of module 17 from the Eurostat dissemination API (JSON-stat), no filter on country.

- nrg_cb_em: electricity supply, transformation and consumption, monthly (siec E7000, unit GWH)
- nrg_cb_pem: net electricity generation by type of fuel, monthly (siec TOTAL, unit GWH)
- nrg_cb_e: electricity supply, transformation and consumption, annual (siec E7000, unit GWH)
- Ember yearly electricity data (CC BY 4.0): net imports by country, used only to validate which side of a
  divergence a second publisher agrees with
- the explanatory metadata page (ESMS) nrg_prd_esms, kept as text for the quality notes

Raw JSON goes to data/raw/ (git ignores it). data/fetch_log.json records endpoint, filter, access
date, the dataset's own update timestamp and the observation counts.

    python3 src/fetch.py
"""
import datetime
import json
import os
import ssl
import time
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
EMBER = {"ember_yearly.csv": "https://files.ember-energy.org/public-downloads/generation/outputs/release_generation_yearly_global.csv"}
ESMS = "https://ec.europa.eu/eurostat/cache/metadata/en/nrg_prd_esms.htm"
QUERIES = {"nrg_cb_em": "format=JSON&siec=E7000&unit=GWH",
           "nrg_cb_pem": "format=JSON&siec=TOTAL&unit=GWH",
           "nrg_cb_e": "format=JSON&siec=E7000&unit=GWH"}


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


def get(url, tries=6):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180, context=_ctx()) as r:
                return r.read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def main():
    os.makedirs(RAW, exist_ok=True)
    log = {"accessed": datetime.date.today().isoformat(), "datasets": {}}
    for ds, q in QUERIES.items():
        raw = get(f"{API}{ds}?{q}")
        open(os.path.join(RAW, f"{ds}.json"), "wb").write(raw)
        d = json.loads(raw)
        dims = {k: len(v["category"]["index"]) for k, v in d["dimension"].items()}
        ann = {a["type"]: a.get("date") or a.get("title") for a in d["extension"]["annotation"]}
        log["datasets"][ds] = {"endpoint": API + ds, "filter": q, "updated": d.get("updated"), "dimensions": dims,
                               "values": len(d["value"]), "obs_period_oldest": ann.get("OBS_PERIOD_OVERALL_OLDEST"),
                               "obs_period_latest": ann.get("OBS_PERIOD_OVERALL_LATEST"),
                               "flag_labels": d["extension"].get("status", {}).get("label")}
    log["ember"] = {}
    for f, u in EMBER.items():
        raw = get(u)
        open(os.path.join(RAW, f), "wb").write(raw)
        log["ember"][f] = {"endpoint": u, "bytes": len(raw), "rows": raw.count(b"\n") - 1}
    open(os.path.join(RAW, "nrg_prd_esms.htm"), "wb").write(get(ESMS))
    log["metadata"] = {"endpoint": ESMS, "use": "quality notes: revision policy, provisional data"}
    json.dump(log, open(os.path.join(DATA, "fetch_log.json"), "w"), indent=1)
    print("fetched", ", ".join(QUERIES), ", ".join(EMBER))


if __name__ == "__main__":
    main()
