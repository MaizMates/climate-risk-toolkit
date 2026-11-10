"""Fetch every input of module 14 from the Eurostat dissemination API.

Raw JSON goes to data/raw/ (git ignores it); the tidy tables the analysis and the tests read are
written to data/ (each under 1 MB) together with data/fetch_log.json: endpoint, filter, access date.

    python3 src/fetch.py
"""
import csv
import datetime
import json
import os
import ssl
import time
import urllib.request

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")

MEMBERS = ["BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT", "CY", "LV",
           "LT", "LU", "HU", "MT", "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]
GEOS = ["EU27_2020"] + MEMBERS
SINCE = 2005
BASE_YEAR = 2015
ENERGY_BALANCES = ["FC_IND_E", "FC_OTH_CP_E", "FC_OTH_AF_E", "FC_TRA_E", "FC_OTH_HH_E"]
NACE = ["A", "B-E", "C", "F", "G-I", "J", "K", "L", "M_N", "O-Q", "R-U"]


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


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120, context=_ctx()) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if k == tries - 1:
                raise
            time.sleep(3 * (k + 1))


def flat(doc):
    """Yield (dims, value) from a JSON-stat 2 document; dims maps dimension id to category code."""
    ids, size = doc["id"], doc["size"]
    cats = [sorted(doc["dimension"][i]["category"]["index"].items(), key=lambda kv: kv[1])
            for i in ids]
    for key, v in doc["value"].items():
        pos, k = [], int(key)
        for n in reversed(size):
            pos.append(k % n)
            k //= n
        pos.reverse()
        yield {i: cats[j][pos[j]][0] for j, i in enumerate(ids)}, float(v)


def q(*pairs):
    return "&".join(f"{k}={v}" for k, v in pairs)


def main():
    os.makedirs(RAW, exist_ok=True)
    geo = [("geo", g) for g in GEOS]
    jobs = {
        "energy": ("nrg_bal_s", [("format", "JSON"), ("unit", "KTOE"), ("siec", "TOTAL")]
                   + [("nrg_bal", b) for b in ENERGY_BALANCES] + geo + [("sinceTimePeriod", SINCE)]),
        "gva": ("nama_10_a10", [("format", "JSON"), ("unit", "CLV15_MEUR"), ("na_item", "B1G")]
                + [("nace_r2", n) for n in NACE] + geo + [("sinceTimePeriod", SINCE)]),
        "hdd": ("nrg_chdd_a", [("format", "JSON"), ("indic_nrg", "HDD")] + geo
                + [("sinceTimePeriod", SINCE)]),
        "hicp": ("prc_hicp_aind", [("format", "JSON"), ("unit", "INX_A_AVG"), ("coicop", "NRG"),
                                   ("coicop", "CP00"), ("geo", "EU27_2020"),
                                   ("sinceTimePeriod", BASE_YEAR)]),
        "ei": ("nrg_ind_ei", [("format", "JSON"), ("unit", "KGOE_TEUR"), ("nrg_bal", "EI_GDP_CLV15"),
                              ("geo", "EU27_2020"), ("sinceTimePeriod", SINCE)]),
    }
    log = {"accessed": datetime.date.today().isoformat(), "datasets": {}}
    cols = {"energy": ("geo", "nrg_bal", "time"), "gva": ("geo", "nace_r2", "time"),
            "hdd": ("geo", "time"), "hicp": ("geo", "coicop", "time"), "ei": ("geo", "time")}
    for name, (code, params) in jobs.items():
        url = f"{BASE}/{code}?{q(*params)}"
        doc = get(url)
        with open(os.path.join(RAW, f"{name}.json"), "w") as f:
            json.dump(doc, f)
        rows = [dict(d, value=v) for d, v in flat(doc)]
        with open(os.path.join(DATA, f"{name}.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(list(cols[name]) + ["value"])
            for r in sorted(rows, key=lambda r: tuple(r[c] for c in cols[name])):
                w.writerow([r[c] for c in cols[name]] + [r["value"]])
        log["datasets"][name] = {"table": code, "url": url, "rows": len(rows),
                                 "updated": doc.get("updated")}
        print(f"{name:7s} {code:12s} {len(rows):6d} rows  updated {doc.get('updated')}")
    with open(os.path.join(DATA, "fetch_log.json"), "w") as f:
        json.dump(log, f, indent=1)


if __name__ == "__main__":
    main()
