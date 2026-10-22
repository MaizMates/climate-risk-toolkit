"""Fetch every input of module 12 from its public endpoint into data/raw/ and log it.

    python3 src/fetch.py

Nothing is typed: ENCORE dependency ratings and the activity hierarchy from the JSON that
encorenature.org serves to its own public Explore tool (no login), the fund's holdings from
State Street's holdings file, the comparator figure from the ECB's own blog page.
results/fetch_log.json records URL, access date, size and SHA-256 of each file.
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

SOURCES = {
    "ecosystem_services.json": "https://encorenature.org/en/ecosystem_services",
    "sectors.json": "https://encorenature.org/en/sectors",
    "zpre_holdings.xlsx": ("https://www.ssga.com/library-content/products/fund-data/etfs/emea/"
                           "holdings-daily-emea-en-zpre-gy.xlsx"),
    "ecb_blog.html": ("https://www.ecb.europa.eu/press/blog/date/2023/html/"
                      "ecb.blog230608~5cffb7c349.en.html"),
}


def ctx():
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


def get(url, timeout=90):
    headers = {"User-Agent": "climate-risk-toolkit"}
    if "encorenature.org" in url:
        headers["Accept"] = "application/json"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=ctx()) as r:
        return r.read()


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(RES, exist_ok=True)
    log = []
    for name, url in SOURCES.items():
        raw = get(url)
        with open(os.path.join(RAW, name), "wb") as f:
            f.write(raw)
        log.append({"file": name, "url": url, "accessed": datetime.date.today().isoformat(),
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        print(f"{name}: {len(raw):,} bytes")
    with open(os.path.join(RES, "fetch_log.json"), "w") as f:
        json.dump(log, f, indent=1)


if __name__ == "__main__":
    main()
