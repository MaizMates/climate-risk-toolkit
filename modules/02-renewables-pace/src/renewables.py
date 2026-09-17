"""Pace of the renewable share in the EU, and where five more years of it lands.

The question this answers: if each member state keeps going at the speed it has actually
managed over the last five years, where is its renewable share in 2030, and how far is that
from the EU-wide 42.5% yardstick?

Data: Eurostat nrg_ind_ren, "Main indicators - share of renewable energy", balance REN.
Pulled live over the public dissemination API, no key, no scraping.
"""
import json
import ssl
import urllib.request

API = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_ind_ren"
       "?format=JSON&lang=EN&nrg_bal=REN")

# The 42.5% in RED III is an EU AGGREGATE target, not a national obligation. It is used here as
# one common yardstick so the countries are comparable; national contributions differ and are
# not in this dataset. Saying otherwise would be the kind of quiet false premise that makes a
# whole analysis worthless.
EU_YARDSTICK_2030 = 42.5

# Non-member states that sit in the same Eurostat table.
NON_EU = {"IS", "NO", "UK", "ME", "MK", "AL", "RS", "TR", "BA", "XK", "MD", "GE", "UA"}
AGGREGATES = {"EU27_2020", "EA19", "EA20"}


def _ctx():
    """Some python builds ship without a trust store wired in. Use certifi when it is there,
    then the system bundle. Never disable verification: a silently unverified fetch is how you
    end up analysing someone else's data."""
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


def fetch(url=API):
    with urllib.request.urlopen(url, timeout=60, context=_ctx()) as r:
        return json.loads(r.read().decode("utf-8"))


def to_series(doc):
    """{country_code: {year: share}} from Eurostat's flattened value array."""
    dim = doc["dimension"]
    times = dim["time"]["category"]["index"]
    geos = dim["geo"]["category"]["index"]
    values = doc["value"]
    n_time = len(times)
    out = {}
    for geo, gi in geos.items():
        row = {}
        for year, ti in times.items():
            v = values.get(str(gi * n_time + ti))
            if v is not None:
                row[int(year)] = float(v)
        if row:
            out[geo] = row
    return out


def pace(row, first, last):
    """Average annual change in percentage points over a window, using the ends that exist."""
    years = sorted(y for y in row if first <= y <= last)
    if len(years) < 2:
        return None
    a, b = years[0], years[-1]
    return (row[b] - row[a]) / (b - a)


def project(row, to_year=2030, window=5):
    """Latest value carried forward at the pace actually achieved in the last `window` years."""
    if not row:
        return None
    last = max(row)
    p = pace(row, last - window, last)
    if p is None:
        return None
    return {"latest_year": last, "latest": row[last], "pace_pp_per_year": p,
            "projected_2030": row[last] + p * (to_year - last)}


def table(series):
    rows = []
    for geo, row in series.items():
        if geo in NON_EU or geo in AGGREGATES or len(geo) != 2:
            continue
        pr = project(row)
        if not pr:
            continue
        pr["geo"] = geo
        pr["gap_to_yardstick"] = pr["projected_2030"] - EU_YARDSTICK_2030
        # pace still required from the latest year to reach the yardstick by 2030
        yrs = 2030 - pr["latest_year"]
        pr["required_pp_per_year"] = ((EU_YARDSTICK_2030 - pr["latest"]) / yrs) if yrs > 0 else None
        pr["shortfall_in_pace"] = (pr["required_pp_per_year"] - pr["pace_pp_per_year"]
                                   if pr["required_pp_per_year"] is not None else None)
        rows.append(pr)
    rows.sort(key=lambda r: r["gap_to_yardstick"])
    return rows


def main():
    rows = table(to_series(fetch()))
    out = {"yardstick_2030": EU_YARDSTICK_2030, "n_countries": len(rows), "rows": rows}
    with open("results/renewables_pace.json", "w") as f:
        json.dump(out, f, indent=1)
    on = [r for r in rows if r["gap_to_yardstick"] >= 0]
    print(f"{len(rows)} member states, {len(on)} reach {EU_YARDSTICK_2030}% by 2030 at their own pace")
    print(f"{'':4s} {'latest':>8s} {'pace':>7s} {'needs':>7s} {'2030':>7s}")
    for r in rows[:6] + rows[-4:]:
        print(f"{r['geo']:4s} {r['latest']:8.1f} {r['pace_pp_per_year']:7.2f} "
              f"{r['required_pp_per_year']:7.2f} {r['projected_2030']:7.1f}")
    return out


if __name__ == "__main__":
    main()
