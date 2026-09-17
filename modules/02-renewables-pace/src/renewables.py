"""Pace of the renewable share in the EU, fitted rather than eyeballed.

ESTIMAND. For each member state, the average annual change in the renewable share of gross
final energy consumption, in percentage points per year, estimated as the least-squares slope
over a window of w years ending at the latest observation; and the projection of that slope to
2030, carried with an interval whose width comes from how badly the same procedure did
out of sample.

Data: Eurostat nrg_ind_ren, "share of renewable energy", balance REN, public dissemination API.
"""
import json
import math
import ssl
import urllib.request

API = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_ind_ren"
       "?format=JSON&lang=EN&nrg_bal=REN")

# 42.5% in RED III is the EU AGGREGATE target, not a national obligation. It is used here as one
# common ruler so member states are comparable. National contributions under the NECPs differ and
# are not in this dataset. Treating it as national would be a false premise, so it is labelled as
# a yardstick everywhere it appears.
EU_YARDSTICK_2030 = 42.5
WINDOW = 5
BACKTEST_HORIZON = 5

NON_EU = {"IS", "NO", "UK", "ME", "MK", "AL", "RS", "TR", "BA", "XK", "MD", "GE", "UA"}
AGGREGATES = {"EU27_2020", "EA19", "EA20"}


def _ctx():
    """Never disable verification: a silently unverified fetch is how you analyse someone
    else's data without knowing it."""
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
    dim = doc["dimension"]
    times = dim["time"]["category"]["index"]
    geos = dim["geo"]["category"]["index"]
    values = doc["value"]
    n_time = len(times)
    out = {}
    for geo, gi in geos.items():
        row = {int(y): float(values[str(gi * n_time + ti)])
               for y, ti in times.items() if values.get(str(gi * n_time + ti)) is not None}
        if row:
            out[geo] = row
    return out


def ols(xs, ys):
    """Slope, intercept and the standard error of the slope.

    An endpoint-to-endpoint difference throws away every observation in between and has no
    variance of its own to report. This is the smallest fix that makes the number defensible:
    the slope is an estimate, and it comes with its own uncertainty.
    """
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    dof = n - 2
    s2 = sum(r * r for r in resid) / dof if dof > 0 else 0.0
    se = math.sqrt(s2 / sxx) if sxx > 0 else 0.0
    return {"slope": b, "intercept": a, "se": se, "n": n,
            "rmse": math.sqrt(sum(r * r for r in resid) / n)}


def window_fit(row, end_year, w=WINDOW):
    years = sorted(y for y in row if end_year - w < y <= end_year)
    if len(years) < 3:
        return None
    return ols(years, [row[y] for y in years])


def backtest(series, horizon=BACKTEST_HORIZON, w=WINDOW):
    """Fit as at year t, predict t+horizon, compare with what happened.

    This is the only thing that turns a linear projection from an assumption into a number with
    a measured error. The realised errors here set the interval on the 2030 projection.
    """
    errors = []
    for geo, row in series.items():
        if geo in NON_EU or geo in AGGREGATES or len(geo) != 2:
            continue
        last = max(row)
        t = last - horizon
        fit = window_fit(row, t, w)
        if not fit or (t + horizon) not in row or t not in row:
            continue
        predicted = row[t] + fit["slope"] * horizon
        errors.append({"geo": geo, "as_of": t, "target": t + horizon,
                       "predicted": predicted, "actual": row[t + horizon],
                       "error": predicted - row[t + horizon]})
    if not errors:
        return None
    es = [e["error"] for e in errors]
    n = len(es)
    mean = sum(es) / n
    rmse = math.sqrt(sum(e * e for e in es) / n)
    mae = sum(abs(e) for e in es) / n
    return {"n": n, "bias": mean, "rmse": rmse, "mae": mae,
            "p90_abs": sorted(abs(e) for e in es)[int(0.9 * (n - 1))],
            "detail": sorted(errors, key=lambda e: abs(e["error"]), reverse=True)}


def table(series, w=WINDOW, bt=None):
    rows = []
    for geo, row in series.items():
        if geo in NON_EU or geo in AGGREGATES or len(geo) != 2:
            continue
        last = max(row)
        fit = window_fit(row, last, w)
        if not fit:
            continue
        horizon = 2030 - last
        proj = row[last] + fit["slope"] * horizon
        # Two sources of uncertainty, kept apart because they answer different objections.
        # The fit interval says how badly this window pins the slope down; the backtest band
        # says how wrong this whole procedure has been at this horizon before.
        ci = 1.96 * fit["se"] * horizon
        band = bt["rmse"] * (horizon / BACKTEST_HORIZON) if bt else None
        required = (EU_YARDSTICK_2030 - row[last]) / horizon if horizon > 0 else None
        r = {"geo": geo, "latest_year": last, "latest": row[last],
             "pace_pp_per_year": fit["slope"], "pace_se": fit["se"], "n_obs": fit["n"],
             "fit_rmse": fit["rmse"],
             "projected_2030": proj,
             "proj_lo_fit": proj - ci, "proj_hi_fit": proj + ci,
             "proj_lo_backtest": proj - band if band else None,
             "proj_hi_backtest": proj + band if band else None,
             "required_pp_per_year": required,
             "shortfall_in_pace": (required - fit["slope"]) if required is not None else None,
             "gap_to_yardstick": proj - EU_YARDSTICK_2030}
        # A verdict is only allowed when the interval does not straddle the yardstick.
        if band is not None:
            r["verdict"] = ("short" if proj + band < EU_YARDSTICK_2030 else
                            "reaches" if proj - band > EU_YARDSTICK_2030 else
                            "cannot tell")
        rows.append(r)
    rows.sort(key=lambda r: r["gap_to_yardstick"])
    return rows


def sensitivity(series, windows=(3, 5, 7, 10)):
    """The window length is arbitrary. If the ordering moves with it, that is the finding."""
    base = [r["geo"] for r in table(series, 5)]
    out = {}
    for w in windows:
        rows = table(series, w)
        order = [r["geo"] for r in rows]
        common = [g for g in base if g in order]
        # Spearman on the ranks of the countries both windows rank
        n = len(common)
        if n > 1:
            rb = {g: i for i, g in enumerate(base)}
            ro = {g: i for i, g in enumerate(order)}
            d2 = sum((rb[g] - ro[g]) ** 2 for g in common)
            rho = 1 - (6 * d2) / (n * (n * n - 1))
        else:
            rho = None
        out[str(w)] = {"n": len(rows), "spearman_vs_w5": rho,
                       "bottom3": order[:3], "top3": order[-3:]}
    return out


def main():
    series = to_series(fetch())
    bt = backtest(series)
    rows = table(series, WINDOW, bt)
    sens = sensitivity(series)
    out = {"yardstick_2030": EU_YARDSTICK_2030, "window_years": WINDOW,
           "estimand": ("average annual change in the renewable share, percentage points per "
                        "year, least-squares slope over the window, projected to 2030"),
           "backtest": bt, "sensitivity": sens, "n_countries": len(rows), "rows": rows}
    with open("results/renewables_pace.json", "w") as f:
        json.dump(out, f, indent=1)

    short = [r for r in rows if r["verdict"] == "short"]
    unclear = [r for r in rows if r["verdict"] == "cannot tell"]
    print(f"{len(rows)} member states | backtest n={bt['n']} rmse={bt['rmse']:.2f}pp "
          f"bias={bt['bias']:+.2f}pp at {BACKTEST_HORIZON}y")
    print(f"short of {EU_YARDSTICK_2030}%: {len(short)} | cannot tell: {len(unclear)} | "
          f"reaches: {len(rows) - len(short) - len(unclear)}")
    print(f"\n{'':4s} {'latest':>7s} {'slope':>7s} {'se':>6s} {'2030':>7s} "
          f"{'lo':>7s} {'hi':>7s}  verdict")
    for r in rows[:6]:
        print(f"{r['geo']:4s} {r['latest']:7.1f} {r['pace_pp_per_year']:7.2f} {r['pace_se']:6.2f} "
              f"{r['projected_2030']:7.1f} {r['proj_lo_backtest']:7.1f} {r['proj_hi_backtest']:7.1f}"
              f"  {r['verdict']}")
    print("\nwindow sensitivity (Spearman against w=5):")
    for w, s in sens.items():
        print(f"  w={w:>2s}  rho={s['spearman_vs_w5']:+.3f}  bottom3={s['bottom3']}")
    return out


if __name__ == "__main__":
    main()

