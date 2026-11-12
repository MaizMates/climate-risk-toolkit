"""Raw Energy-Charts JSON (data/raw/) to the two small tables the analysis reads.

data/weekly.csv: sufficient statistics per 7-day block of each calendar year (Europe/Berlin), enough
to rebuild every annual capture rate, every bootstrap draw and every sweep without the raw files.
data/profile.csv: mean price, solar and wind by year and local hour of day.
data/quality.json: row counts and gaps.

Quarter-hour grid: generation is quarter-hourly. Day-ahead prices are hourly until 30 Sep 2025 and
quarter-hourly after; an hourly price is held across its four quarter-hours. For the hourly era
this equals averaging generation to the hour and joining the hourly price, which is the roadmap method.
Column GPh is that method applied literally (hourly mean generation times hourly mean price) so the
two can be compared after the change of price resolution.

    python3 src/prepare.py
"""
import glob
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")
TZ = "Europe/Berlin"
TECH = {"solar": "Solar", "wind": "Wind onshore", "woff": "Wind offshore"}
LAST_BLOCK = 51


def load_raw():
    pw, pr = [], []
    for f in sorted(glob.glob(os.path.join(RAW, "*_power.json"))):
        d = json.load(open(f))
        df = pd.DataFrame({"ts": d["unix_seconds"]})
        by = {p["name"]: p["data"] for p in d["production_types"]}
        for k, name in list(TECH.items()) + [("load", "Load")]:
            df[k] = pd.to_numeric(pd.Series(by[name]), errors="coerce")
        pw.append(df)
    for f in sorted(glob.glob(os.path.join(RAW, "*_price.json"))):
        d = json.load(open(f))
        pr.append(pd.DataFrame({"ts": d["unix_seconds"], "price": pd.to_numeric(pd.Series(d["price"]), errors="coerce")}))
    pw = pd.concat(pw).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    pr = pd.concat(pr).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    return pw, pr


def join_price(pw, pr):
    """Price in force at each quarter-hour: the latest price stamp at or before it, within one hour."""
    m = pd.merge_asof(pw, pr, on="ts", direction="backward", tolerance=3600)
    return m


def block_id(local_time):
    """0..51: 7-day block of the local calendar year; days 358 onward fold into block 51."""
    return np.minimum((local_time.dt.dayofyear.values - 1) // 7, LAST_BLOCK)


def build(pw, pr):
    m = join_price(pw, pr)
    need = ["price", "solar", "wind", "woff", "load"]
    q = {"rows_power": int(len(m)), "rows_dropped_missing": int(m[need].isna().any(axis=1).sum())}
    m = m.dropna(subset=need).copy()
    lt = pd.to_datetime(m["ts"], unit="s", utc=True).dt.tz_convert(TZ)
    m["year"], m["block"], m["hour"] = lt.dt.year.values, block_id(lt), lt.dt.hour.values
    m["pf"] = m["price"].clip(lower=0)
    m["neg"] = (m["price"] < 0).astype(float)
    # hourly-average variant (roadmap method literally)
    m["h"] = m["ts"] // 3600
    for k in ("solar", "wind"):
        gb = m.groupby("h")[k].transform("mean")
        pb = m.groupby("h")["price"].transform("mean")
        m[k + "_gph"] = gb * pb
    agg = {"n": ("price", "size"), "P": ("price", "sum"), "Pf": ("pf", "sum"), "L": ("load", "sum"),
           "nneg": ("neg", "sum")}
    for k in TECH:
        m[k + "_gp"], m[k + "_gpf"] = m[k] * m["price"], m[k] * m["pf"]
        agg.update({k.upper() + "_G": (k, "sum"), k.upper() + "_GP": (k + "_gp", "sum"),
                    k.upper() + "_GPf": (k + "_gpf", "sum")})
    m["solar_gneg"] = m["solar"] * m["neg"]
    agg["SOLAR_Gneg"] = ("solar_gneg", "sum")
    for k in ("solar", "wind"):
        agg[k.upper() + "_GPh"] = (k + "_gph", "sum")
    w = m.groupby(["year", "block"]).agg(**agg).reset_index()
    w["quarter"] = ((pd.to_datetime(w["year"].astype(str) + "-01-01") + pd.to_timedelta(7 * w["block"], unit="D")).dt.month - 1) // 3
    prof = m.groupby(["year", "hour"]).agg(price=("price", "mean"), solar=("solar", "mean"),
                                           wind=("wind", "mean")).reset_index()
    q["rows_per_year"] = {int(y): int(n) for y, n in m.groupby("year").size().items()}
    q["unmatched_price"] = int(m["price"].isna().sum())
    return w, prof, q


def main():
    pw, pr = load_raw()
    w, prof, q = build(pw, pr)
    w.round(4).to_csv(os.path.join(DATA, "weekly.csv"), index=False)
    prof.round(4).to_csv(os.path.join(DATA, "profile.csv"), index=False)
    json.dump(q, open(os.path.join(DATA, "quality.json"), "w"), indent=1)
    print(q)


if __name__ == "__main__":
    main()
