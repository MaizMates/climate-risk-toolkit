"""Fetch the ClimateBERT commitments-and-actions dataset (expert-annotated paragraphs) by code.

Text goes to data/raw/ (not committed: the licence is CC-BY-NC-SA-4.0, so the paragraphs are
fetched, not redistributed). results/fetch_log.json records URL, access date, row counts, label
counts and the SHA-256 of each split so a reader can re-run this and compare.
"""
import datetime
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
RESULTS = os.path.join(HERE, "..", "results")
DATASET = "climatebert/climate_commitments_actions"
API = "https://datasets-server.huggingface.co/rows"
CARD = f"https://huggingface.co/datasets/{DATASET}/raw/main/README.md"


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"}), timeout=60) as r:
                return r.status, r.read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(3 * (k + 1))


def fetch_split(split):
    rows, status = [], None
    while True:
        q = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": split, "offset": len(rows), "length": 100})
        status, body = get(f"{API}?{q}")
        page = json.loads(body)
        rows += [{"row": r["row_idx"], "text": r["row"]["text"], "label": r["row"]["label"]} for r in page["rows"]]
        if len(rows) >= page["num_rows_total"]:
            return rows, status, page["num_rows_total"]


def main():
    os.makedirs(RAW, exist_ok=True); os.makedirs(RESULTS, exist_ok=True)
    log = {"accessed": datetime.date.today().isoformat(), "dataset": DATASET, "endpoint": API, "splits": {}}
    for split in ("train", "test"):
        rows, status, total = fetch_split(split)
        assert len(rows) == total and [r["row"] for r in rows] == list(range(total)), "rows must be complete and ordered"
        blob = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        with open(os.path.join(RAW, f"{split}.jsonl"), "w") as f:
            f.write(blob)
        log["splits"][split] = {"http_status": status, "rows": total, "label_1": sum(r["label"] for r in rows),
                                "sha256": hashlib.sha256(blob.encode()).hexdigest()}
    status, card = get(CARD)
    log["card"] = {"url": CARD, "http_status": status, "sha256": hashlib.sha256(card).hexdigest()}
    with open(os.path.join(RESULTS, "fetch_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
