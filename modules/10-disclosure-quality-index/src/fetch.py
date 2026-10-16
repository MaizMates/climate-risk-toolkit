"""Fetch each bank's published Pillar 3 PDF listed in data/sources.csv into data/cache/.

The cache is not committed (the PDFs are large); results/fetch_log.json records the URL, access
date, HTTP status, size and SHA-256 of every file, so a reader can re-run this and compare.
"""
import csv
import datetime
import hashlib
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CACHE = os.path.join(DATA, "cache")
RESULTS = os.path.join(HERE, "..", "results")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36", "Accept": "application/pdf,*/*"}


def slug(bank):
    return "".join(c.lower() if c.isalnum() else "_" for c in bank).strip("_")


def pdf_path(bank):
    return os.path.join(CACHE, slug(bank) + ".pdf")


def download(url, dest, tries=3):
    last = None
    for k in range(tries):
        try:
            origin = "/".join(url.split("/")[:3]) + "/"  # some publishers return 403 without a Referer
            req = urllib.request.Request(url, headers={**UA, "Referer": origin})
            with urllib.request.urlopen(req, timeout=300) as r:
                status, body = r.status, r.read()
            if not body.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            with open(dest, "wb") as f:
                f.write(body)
            return status, len(body)
        except Exception as e:
            last = repr(e)
            time.sleep(3 * (k + 1))
    return last, 0


def main():
    os.makedirs(RESULTS, exist_ok=True)
    log = []
    for row in csv.DictReader(open(os.path.join(DATA, "sources.csv"))):
        dest = pdf_path(row["bank"])
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            status, size = "cached", os.path.getsize(dest)
        else:
            status, size = download(row["url"], dest)
        entry = {"bank": row["bank"], "period": row["period"], "url": row["url"],
                 "verified": row["verified"], "status": status, "bytes": size,
                 "accessed": datetime.date.today().isoformat()}
        if size:
            entry["sha256"] = hashlib.sha256(open(dest, "rb").read()).hexdigest()
        log.append(entry)
        print(row["bank"], status, size, flush=True)
    json.dump(log, open(os.path.join(RESULTS, "fetch_log.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
