"""Fetch every input of module 15 from the Energy-Charts API (Fraunhofer ISE; data from
Bundesnetzagentur SMARD.de, CC BY 4.0), month by month.

Raw JSON goes to data/raw/ (git ignores it). data/fetch_log.json records endpoint, filter, access
date and row counts. The API answers HTTP 429 under load: the client waits and retries.

    python3 src/fetch.py
"""
import datetime
import calendar
import html
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

BASE = "https://api.energy-charts.info"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")
FIRST_YEAR = 2019
PAUSE = 1.5


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


def get(url, tries=8):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120, context=_ctx()) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if k == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After", 0) or 0) if e.code == 429 else 0
            time.sleep(max(wait, 5 * (k + 1)))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


MV_URL = ("https://www.netztransparenz.de/en/Renewable-energies-and-levies/EEG/Transparency-requirements/"
          "Market-premium/Market-value-overview")


def market_values():
    """Validation input: the annual solar market value (MW Solar(a), ct/kWh) the transmission system
    operators publish, parsed from the semicolon block under the header 'Jahr;MW Solar(a)'."""
    req = urllib.request.Request(MV_URL, headers={"User-Agent": "Mozilla/5.0"})
    for k in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120, context=_ctx()) as r:
                page = r.read().decode("utf-8", "ignore")
            break
        except Exception:
            if k == 3:
                raise
            time.sleep(5 * (k + 1))
    with open(os.path.join(RAW, "market_value_overview.html"), "w") as f:
        f.write(page)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)))
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    i = next(k for k, l in enumerate(lines) if l.startswith("Jahr;MW Solar"))
    rows = []
    for l in lines[i + 1:]:
        m = re.fullmatch(r"(\d{4});(\d+(?:\.\d+)?)", l)
        if not m:
            break
        rows.append((int(m.group(1)), float(m.group(2))))
    prose = {int(y): float(v) for y, v in re.findall(r"for the year (\d{4}) (\d+\.\d+) ct/kWh", " ".join(lines))}
    with open(os.path.join(DATA, "market_value_solar.csv"), "w") as f:
        f.write("year,mw_solar_ct_kwh_csv_block,mw_solar_ct_kwh_prose\n")
        for y, v in rows:
            f.write(f"{y},{v},{prose.get(y, '')}\n")
    # annual market values (JW) under the EEG, as shown for the one year the page opens on
    yr = re.search(r'Alle Werte in ct/kWh</th><th[^>]*>(\d{4})</th>', page).group(1)
    jw = re.findall(r"<span>JW</span>\s*<span>([^<]*)</span>\s*</td><td[^>]*>([\d.]+)</td>", page)
    names = {"": "baseload", "Wind an Land": "wind_onshore", "Wind auf See": "wind_offshore", "Solar": "solar"}
    with open(os.path.join(DATA, "market_value_jw.csv"), "w") as f:
        f.write("year,series,ct_kwh\n")
        for lab, v in jw:
            f.write(f"{yr},{names[lab.strip()]},{v}\n")
    return len(rows)


def months(last_full):
    y, m = FIRST_YEAR, 1
    while (y, m) <= (last_full.year, last_full.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main():
    os.makedirs(RAW, exist_ok=True)
    today = datetime.date.today()
    last_full = today.replace(day=1) - datetime.timedelta(days=1)
    log = {"accessed": today.isoformat(), "licence": "CC BY 4.0, Bundesnetzagentur | SMARD.de via Energy-Charts (Fraunhofer ISE)",
           "price": {"endpoint": BASE + "/price", "filter": "bzn=DE-LU, one calendar month per call"},
           "public_power": {"endpoint": BASE + "/public_power", "filter": "country=de, one calendar month per call; series Solar, Wind onshore, Wind offshore, Load used"},
           "first_month": f"{FIRST_YEAR}-01", "last_month": last_full.strftime("%Y-%m"), "files": {}}
    for y, m in months(last_full):
        s = f"{y}-{m:02d}-01"
        e = f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"
        for name, q in (("price", f"price?bzn=DE-LU&start={s}&end={e}"),
                        ("power", f"public_power?country=de&start={s}&end={e}")):
            path = os.path.join(RAW, f"{y}-{m:02d}_{name}.json")
            if not os.path.exists(path):
                doc = get(f"{BASE}/{q}")
                with open(path, "w") as f:
                    json.dump(doc, f)
                time.sleep(PAUSE)
            else:
                doc = json.load(open(path))
            log["files"][f"{y}-{m:02d}_{name}"] = len(doc["unix_seconds"])
    log["market_value_solar"] = {"endpoint": MV_URL, "filter": "csv block 'Jahr;MW Solar(a)' and the prose line for each year",
                                 "rows": market_values()}
    json.dump(log, open(os.path.join(DATA, "fetch_log.json"), "w"), indent=1)
    print(f"fetched {len(log['files'])} files, {log['first_month']} to {log['last_month']}")


if __name__ == "__main__":
    main()
