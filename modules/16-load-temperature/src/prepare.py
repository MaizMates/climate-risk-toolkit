"""Raw JSON -> data/daily.csv (one row per Berlin calendar day) and data/cities.csv.

Daily load is the sum of quarter-hourly MW x 0.25 h, in GWh (a 23- or 25-hour day sums the energy
actually used). Days with any missing quarter-hour are dropped and counted in data/quality.json.

    python3 src/prepare.py
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")


def daily_load(files):
    parts = []
    for f in files:
        d = json.load(open(f))
        parts.append(pd.DataFrame({"t": d["unix_seconds"], "mw": d["Load"]}))
    q = pd.concat(parts)
    q["date"] = pd.to_datetime(q.t, unit="s", utc=True).dt.tz_convert("Europe/Berlin").dt.tz_localize(None).dt.normalize()
    g = q.groupby("date")
    out = pd.DataFrame({"load_gwh": g.mw.sum() * 0.25 / 1000, "n_missing": g.mw.apply(lambda s: s.isna().sum()),
                        "n_quarters": g.mw.size()})
    return out


def main():
    log = json.load(open(os.path.join(DATA, "fetch_log.json")))
    years = sorted(int(y) for y in log["load"]["files"])
    ld = daily_load([os.path.join(RAW, f"load_{y}.json") for y in years])
    bad = ld[ld.n_missing > 0]
    ld = ld[ld.n_missing == 0].drop(columns="n_missing")
    cities = pd.DataFrame(log["geocoding"]["cities"]).T
    cities["population"] = cities.population.astype(float)
    cities["weight"] = cities.population / cities.population.sum()
    cities.index.name = "city"
    cities.to_csv(os.path.join(DATA, "cities.csv"))
    temps = {}
    for c in cities.index:
        rows = []
        for y in years:
            w = json.load(open(os.path.join(RAW, f"weather_{c.replace(' ', '_')}_{y}.json")))
            rows.append(pd.Series(w["temperature_2m_mean"], index=pd.to_datetime(w["time"])))
        temps[c] = pd.concat(rows)
    T = pd.DataFrame(temps)
    nt = int(T.isna().any(axis=1).sum())
    T = T.dropna()
    d = ld.join(T, how="inner")
    d["temp"] = (T.loc[d.index] * cities.weight.values).sum(axis=1)
    d["temp_equal"] = T.loc[d.index].mean(axis=1)
    dw = {}
    for c in cities.index:
        d_ = json.load(open(os.path.join(RAW, f"dwd_{c.replace(' ', '_')}.json")))
        ser = {}
        for part in d_["parts"]:
            for l in part.splitlines()[1:]:
                f = [x.strip() for x in l.split(";")]
                if len(f) > 13 and f[13] != "-999":
                    ser[pd.Timestamp(f[1])] = float(f[13])
        dw[c] = pd.Series(ser)
    DW = pd.DataFrame(dw).reindex(d.index)
    d["temp_dwd"] = (DW * cities.weight.values).sum(axis=1, min_count=len(cities))
    n_dwd = int(d.temp_dwd.isna().sum())
    hol = set()
    for y in years:
        for h in json.load(open(os.path.join(RAW, f"holidays_{y}.json"))):
            if h["global"]:
                hol.add(pd.Timestamp(h["date"]))
    d["holiday"] = d.index.isin(hol).astype(int)
    d.index.name = "date"
    d = d.drop(columns="n_quarters").round({"load_gwh": 4, **{c: 2 for c in cities.index}, "temp": 3, "temp_dwd": 3, "temp_equal": 3})
    d.to_csv(os.path.join(DATA, "daily.csv"))
    json.dump({"days": len(d), "first": str(d.index[0].date()), "last": str(d.index[-1].date()),
               "days_dropped_missing_load": [str(x.date()) for x in bad.index], "days_dropped_missing_weather": nt,
               "days_without_dwd_temperature": n_dwd, "global_holidays": len(hol), "non_standard_quarters_days": int((ld.n_quarters.isin([92, 100])).sum())},
              open(os.path.join(DATA, "quality.json"), "w"), indent=1)
    print(d.describe().T[["count", "mean", "min", "max"]])


if __name__ == "__main__":
    main()
