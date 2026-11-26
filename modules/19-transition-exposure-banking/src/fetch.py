"""Fetch every input of module 19 from public EBA endpoints.

- EBA 2025 EU-wide transparency exercise, full credit-risk database (tr_cre.csv), metadata and data dictionary
- EBA 2024 EU-wide transparency exercise, same three files (June 2024 reference date, for the year-on-year check)
- EBA Risk Assessment Report, December 2025 (PDF): the exercise's own aggregate NPL volume and ratio
- EBA Risk Dashboard, Q2 2025 (PDF): published EU/EEA and country distribution of NFC loans and NPL ratios by NACE

Raw files go to data/raw/ (git ignores them). data/fetch_log.json records endpoint, bytes, sha256 and access date.
The 2025 file URLs are the links on the EBA transparency-exercise page, read from that page by this script.

    python3 src/fetch.py
"""
import datetime
import hashlib
import json
import os
import re
import ssl
import time
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")
PAGE = "https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/eu-wide-transparency-exercise"
BASE = "https://www.eba.europa.eu"
TE = {"2025": BASE + "/assets/TE2025/Full_database/883401/",
      "2024": BASE + "/assets/TE2024/Full_database/256109/"}
FILES = ["tr_cre.csv", "TR_Metadata.xlsx", "SDD.xlsx"]
RAR = (BASE + "/sites/default/files/2025-12/8acb45c4-912b-4f0f-b887-37b8fc058779/"
       "Risk%20Assessment%20Report%20Autumn%202025.pdf")
DASH = (BASE + "/sites/default/files/2025-09/0b362777-be60-43a4-a8dd-3287500d7cc6/"
        "EBA%20Dashboard%20-%20Q2%202025.pdf")


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


def get(url, tries=5):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=600, context=_ctx()) as r:
                return r.read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def save(url, path, log):
    raw = get(url)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(raw)
    log[os.path.relpath(path, RAW)] = {"endpoint": url, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    log = {"accessed": datetime.date.today().isoformat()}
    page = get(PAGE).decode("utf8", "replace")
    links = set(re.findall(r'href="([^"]*TE2025/Full_database/[^"]*)"', page))
    assert TE["2025"] + "tr_cre.csv" in links, "EBA page no longer links the 2025 full database"
    log["page"] = {"endpoint": PAGE, "latest_edition_linked": "2025"}
    for ed, base in TE.items():
        for f in FILES:
            save(base + f, os.path.join(RAW, ed, f), log)
    save(RAR, os.path.join(RAW, "rar2025.pdf"), log)
    save(DASH, os.path.join(RAW, "dash_q2_2025.pdf"), log)
    json.dump(log, open(os.path.join(DATA, "fetch_log.json"), "w"), indent=1)
    print("fetched", len(log) - 2, "files")


if __name__ == "__main__":
    main()
