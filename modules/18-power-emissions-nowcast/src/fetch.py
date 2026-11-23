"""Fetch every input of module 18 from public endpoints, no filter on the Ember file.

- Ember monthly electricity data, global long format (CC BY 4.0): generation and emissions by source
- Eurostat env_air_gge (air emissions accounts by source sector, greenhouse gases, EU27, CRF 1.A.1.a public
  electricity and heat production, MIO_T): annual, an inventory Ember does not build on, used only to validate

Raw files go to data/raw/ (git ignores them). data/fetch_log.json records endpoint, filter, access date and counts.

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
EMBER = "https://files.ember-energy.org/public-downloads/generation/outputs/release_generation_monthly_global.csv"
CRF = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/env_air_gge"
CRF_Q = "format=JSON&geo=EU27_2020&airpol=GHG&src_crf=CRF1A1A&unit=MIO_T"


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
            with urllib.request.urlopen(url, timeout=300, context=_ctx()) as r:
                return r.read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def main():
    os.makedirs(RAW, exist_ok=True)
    raw = get(EMBER)
    open(os.path.join(RAW, "ember_monthly.csv"), "wb").write(raw)
    raw2 = get(f"{CRF}?{CRF_Q}")
    open(os.path.join(RAW, "env_air_gge.json"), "wb").write(raw2)
    d = json.loads(raw2)
    log = {"accessed": datetime.date.today().isoformat(),
           "ember": {"endpoint": EMBER, "filter": "none (whole file)", "bytes": len(raw), "rows": raw.count(b"\n") - 1},
           "eurostat": {"endpoint": CRF, "filter": CRF_Q, "updated": d.get("updated"), "values": len(d["value"])}}
    json.dump(log, open(os.path.join(DATA, "fetch_log.json"), "w"), indent=1)
    print("fetched ember_monthly.csv, env_air_gge.json")


if __name__ == "__main__":
    main()
