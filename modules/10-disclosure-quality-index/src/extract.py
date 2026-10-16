"""Extract per-page text from each cached PDF with pypdf into data/cache/<bank>.pages.json."""
import csv
import json
import os

import pypdf

from fetch import DATA, CACHE, pdf_path, slug


def pages_path(bank):
    return os.path.join(CACHE, slug(bank) + ".pages.json")


def extract(bank):
    dest = pages_path(bank)
    if os.path.exists(dest):
        return json.load(open(dest))
    reader = pypdf.PdfReader(pdf_path(bank))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    json.dump(pages, open(dest, "w"))
    return pages


def main():
    for row in csv.DictReader(open(os.path.join(DATA, "sources.csv"))):
        n = len(extract(row["bank"]))
        print(row["bank"], n, "pages", flush=True)


if __name__ == "__main__":
    main()
