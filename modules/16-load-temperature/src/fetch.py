"""Fetch every input of module 16 from public endpoints.

- Energy-Charts API (Fraunhofer ISE; data from Bundesnetzagentur SMARD.de, CC BY 4.0): quarter-hourly
  public power for Germany, series "Load", one calendar year per call.
- Open-Meteo historical weather archive (free for non-commercial use): daily mean 2 m temperature,
  one call per city and year.
- Open-Meteo geocoding API (GeoNames): coordinates and population of the six cities.
- Nager.Date public-holiday API: German public holidays, one call per year.
- Deutscher Wetterdienst (DWD) open data, daily station observations (kl, TMK): an independent
  temperature source for validation, one station per city, historical and recent files.

Raw JSON goes to data/raw/ (git ignores it). data/fetch_log.json records endpoint, filter, access
date and row counts.

    python3 src/fetch.py
"""
import datetime
import io
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")
FIRST_YEAR = 2019
PAUSE = 1.5
CITIES = ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt am Main", "Stuttgart"]
EC = "https://api.energy-charts.info/public_power"
OM = "https://archive-api.open-meteo.com/v1/archive"
GEO = "https://geocoding-api.open-meteo.com/v1/search"
NAGER = "https://date.nager.at/api/v3/PublicHolidays"
DWD = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/"
DWD_STATIONS = {"Berlin": "Berlin-Tempelhof", "Hamburg": "Hamburg-Fuhlsbüttel", "Munich": "München-Stadt",
                "Cologne": "Köln/Bonn", "Frankfurt am Main": "Frankfurt/Main", "Stuttgart": "Stuttgart (Schnarrenberg)"}


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
            with urllib.request.urlopen(url, timeout=180, context=_ctx()) as r:
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


def cached(name, url, keep=None):
    path = os.path.join(RAW, name)
    if os.path.exists(path):
        return json.load(open(path))
    doc = get(url)
    if keep:
        doc = keep(doc)
    json.dump(doc, open(path, "w"))
    time.sleep(PAUSE)
    return doc


def load_only(doc):
    s = next(p for p in doc["production_types"] if p["name"] == "Load")
    return {"unix_seconds": doc["unix_seconds"], "Load": s["data"]}


def get_bytes(url, tries=5):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=180, context=_ctx()) as r:
                return r.read()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def dwd_station(name, log):
    """Resolve the station id from DWD's own station list, then keep the product file of the historical
    and the recent zip as text."""
    lst = get_bytes(DWD + "recent/KL_Tageswerte_Beschreibung_Stationen.txt").decode("latin-1").splitlines()[2:]
    row = next(l for l in lst if l[61:102].strip() == name)
    sid = row[:5]
    parts = []
    for sub, pat in (("historical/", "hist"), ("recent/", "akt")):
        idx = get_bytes(DWD + sub).decode()
        zname = next(m for m in __import__("re").findall(r'href="(tageswerte_KL_%s_[^"]*\.zip)"' % sid, idx))
        z = zipfile.ZipFile(io.BytesIO(get_bytes(DWD + sub + zname)))
        f = next(n for n in z.namelist() if n.startswith("produkt"))
        parts.append(z.read(f).decode("latin-1"))
        log[f"{name}_{pat}"] = zname
    return sid, parts


def main():
    os.makedirs(RAW, exist_ok=True)
    today = datetime.date.today()
    last_day = today.replace(day=1) - datetime.timedelta(days=1)   # last day of the last full month
    log = {"accessed": today.isoformat(), "first_day": f"{FIRST_YEAR}-01-01", "last_day": last_day.isoformat(),
           "load": {"endpoint": EC, "filter": "country=de, one calendar year per call (to last_day for the current year); series Load, MW, quarter-hourly", "files": {}},
           "weather": {"endpoint": OM, "filter": "daily=temperature_2m_mean, timezone=Europe/Berlin, one call per city and year", "files": {}},
           "geocoding": {"endpoint": GEO, "filter": "name=<city>, countryCode=DE, first result with population, count=5", "cities": {}},
           "holidays": {"endpoint": NAGER + "/<year>/DE", "files": {}}}
    for y in range(FIRST_YEAR, last_day.year + 1):
        s, e = f"{y}-01-01", min(datetime.date(y, 12, 31), last_day).isoformat()
        d = cached(f"load_{y}.json", f"{EC}?country=de&start={s}&end={e}", load_only)
        log["load"]["files"][str(y)] = len(d["unix_seconds"])
        h = cached(f"holidays_{y}.json", f"{NAGER}/{y}/DE")
        log["holidays"]["files"][str(y)] = len(h)
    for c in CITIES:
        q = urllib.parse.urlencode({"name": c, "count": 5, "language": "en", "countryCode": "DE"})
        res = cached(f"geo_{c.replace(' ', '_')}.json", f"{GEO}?{q}")["results"]
        r = next(x for x in res if x.get("population"))
        log["geocoding"]["cities"][c] = {k: r[k] for k in ("name", "admin1", "latitude", "longitude", "population", "feature_code")}
        for y in range(FIRST_YEAR, last_day.year + 1):
            s, e = f"{y}-01-01", min(datetime.date(y, 12, 31), last_day).isoformat()
            q = f"latitude={r['latitude']}&longitude={r['longitude']}&start_date={s}&end_date={e}&daily=temperature_2m_mean&timezone=Europe%2FBerlin"
            w = cached(f"weather_{c.replace(' ', '_')}_{y}.json", f"{OM}?{q}", lambda d: d["daily"])
            log["weather"]["files"][f"{c}_{y}"] = len(w["time"])
    log["dwd"] = {"endpoint": DWD, "filter": "TMK (daily mean air temperature, deg C) of one station per city; ids resolved from the station list by name", "stations": {}, "files": {}}
    for c, name in DWD_STATIONS.items():
        path = os.path.join(RAW, f"dwd_{c.replace(' ', '_')}.json")
        if not os.path.exists(path):
            zips = {}
            sid, parts = dwd_station(name, zips)
            json.dump({"id": sid, "name": name, "parts": parts, "zips": zips}, open(path, "w"))
        d = json.load(open(path))
        log["dwd"]["files"].update(d["zips"])
        log["dwd"]["stations"][c] = {"id": d["id"], "name": d["name"]}
    json.dump(log, open(os.path.join(DATA, "fetch_log.json"), "w"), indent=1)
    print(f"fetched load, weather, holidays, {FIRST_YEAR} to {last_day}")


if __name__ == "__main__":
    main()
