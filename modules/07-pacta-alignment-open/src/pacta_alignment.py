"""PACTA-style alignment gap of listed European power utilities against an NGFS pathway.

ESTIMAND. For a set of listed power utilities, the production-weighted gap between the capacity
they hold in a technology at the base year (2020) and the capacity a scenario trajectory implies
for them at a stated horizon (2030), as a share of the set's total capacity, by technology.
Positive: the set holds more than the target (coal above a phase-out path). Negative: it holds
less (renewables below a build-out path).

Method: the PACTA market-share approach as written in r2dii.analysis (RMI), reproduced from its
public source. Increasing technologies (renewables, hydro, nuclear):
    target = P0_tech + P0_sector * (S_tech(t) - S_tech(0)) / S_sector(0)         (smsp, floored at 0)
Decreasing technologies (coal, gas, oil):
    target = P0_tech * S_tech(t) / S_tech(0)                                      (tmsr)
P is a company's capacity, S the scenario's regional capacity.

Data, all fetched by this file:
- Plants and owners: WRI Global Power Plant Database (raw.githubusercontent.com).
- Scenario: NGFS Phase 5, IIASA Scenario Explorer, anonymous API (Capacity|Electricity|*).
- Listed status of owner groups: Wikidata (stock-exchange statement P414 without an end date).
- Validation and backtest: Eurostat nrg_inf_epc, net electrical capacity by fuel, EU27.
"""
import csv
import io
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")

WRI_URL = ("https://raw.githubusercontent.com/wri/global-power-plant-database/master/"
           "output_database/global_power_plant_database.csv")
AUTH_URL = "https://api.manager.ece.iiasa.ac.at/legacy/anonym/"
NGFS_BASE = "https://db1.ene.iiasa.ac.at/ngfs-phase-5-api/rest/v2.1"
EUROSTAT_URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nrg_inf_epc"
                "?format=JSON&lang=EN&geo=EU27_2020&plant_tec=CAP_NET_ELC&operator=TOTAL&unit=MW")
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "climate-risk-toolkit/1.0 (public portfolio, github.com/MaizMates)"}

EU28 = ["AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA", "DEU", "GRC", "HUN",
        "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "ESP",
        "SWE", "GBR"]

BASE_YEAR = 2020
HORIZON = 2030
HORIZONS = [2025, 2030, 2035]
TECHS = ["Coal", "Gas", "Oil", "Nuclear", "Hydro", "Renewables"]
# r2dii.data::increasing_or_decreasing for the power sector.
INCREASING = {"Renewables", "Hydro", "Nuclear"}
FUEL2TECH = {"Coal": "Coal", "Gas": "Gas", "Oil": "Oil", "Petcoke": "Oil", "Nuclear": "Nuclear",
             "Hydro": "Hydro", "Wind": "Renewables", "Solar": "Renewables",
             "Biomass": "Renewables", "Waste": "Renewables", "Geothermal": "Renewables",
             "Wave and Tidal": "Renewables"}
NGFS_VARS = {"Coal": ["Coal"], "Gas": ["Gas"], "Oil": ["Oil"], "Nuclear": ["Nuclear"],
             "Hydro": ["Hydro"], "Renewables": ["Wind", "Solar", "Biomass", "Geothermal"]}
# The three NGFS Phase 5 models report different regions. Each is summed over the regions that
# cover the EU plus the UK, the country set the plants are drawn from.
MODELS = {
    "REMIND": ("REMIND-MAgPIE 3.3-4.8", ["REMIND-MAgPIE 3.3-4.8|EU 28"]),
    "GCAM": ("GCAM 6.0 NGFS", ["GCAM 6.0 NGFS|EU-15", "GCAM 6.0 NGFS|EU-12"]),
    "MESSAGE": ("MESSAGEix-GLOBIOM 2.0-M-R12-NGFS",
                ["MESSAGEix-GLOBIOM 2.0-R12|Western Europe",
                 "MESSAGEix-GLOBIOM 2.0-R12|Eastern Europe"]),
}
SCENARIOS = ["Net Zero 2050", "Below 2°C", "Delayed transition", "Nationally Determined Contributions (NDCs)",
             "Current Policies"]
SCEN_YEARS = [2020, 2024, 2025, 2030, 2035]

# Owner string -> group. `strict` matches the brand in the owner name; `extended` adds renamings
# and subsidiaries I know to belong to the same group. Which tier to use is a swept choice.
# (group, wikidata search term, strict regex, extended-only regex)
ALIASES = [
    ("Iberdrola", "Iberdrola", r"iberdrola", r"scottish\s*power|scottishpower"),
    ("Endesa", "Endesa", r"endesa", r"union electrica de canarias|gas y electricidad"),
    ("Naturgy", "Naturgy", r"naturgy", r"gas natural|fenosa"),
    ("EDP", "Energias de Portugal", r"\bedp\b|energias de portugal", r"hidroelectrica del cantabrico"),
    ("Enel", "Enel", r"\benel\b", r"$^"),
    ("RWE", "RWE", r"\brwe\b", r"npower|essent|innogy"),
    ("E.ON", "E.ON", r"\be[\.\s]?on\b", r"$^"),
    ("Uniper", "Uniper", r"uniper", r"$^"),
    ("EDF", "Électricité de France", r"\bedf\b|electricit[eé] de france", r"british energy"),
    ("Engie", "Engie", r"\bengie\b", r"gdf[\s-]*suez|electrabel"),
    ("Orsted", "Ørsted", r"[øo]rsted", r"dong\s*energy"),
    ("Fortum", "Fortum", r"fortum", r"$^"),
    ("PGE", "PGE Polska Grupa Energetyczna", r"polska grupa energetyczna|\bpge\b", r"$^"),
    ("Tauron", "Tauron Polska Energia", r"tauron", r"$^"),
    ("Enea", "Enea SA", r"\benea\b", r"$^"),
    ("Energa", "Energa", r"\benerga\b", r"$^"),
    ("CEZ", "ČEZ Group", r"\b[cč]ez\b", r"$^"),
    ("Verbund", "Verbund", r"verbund", r"$^"),
    ("PPC", "Public Power Corporation", r"\bppc\b|public power company|public power corporation", r"$^"),
    ("Vattenfall", "Vattenfall", r"vattenfall", r"\bnuon\b"),
    ("Statkraft", "Statkraft", r"statkraft", r"$^"),
    ("EnBW", "EnBW", r"enbw|energie baden", r"$^"),
    ("Centrica", "Centrica plc", r"centrica", r"british gas"),
    ("SSE", "SSE plc", r"scottish (and|&) southern|\bsse\b", r"$^"),
    ("Drax", "Drax Group", r"\bdrax\b", r"$^"),
    ("A2A", "A2A", r"\ba2a\b", r"$^"),
    ("Edison", "Edison S.p.A.", r"\bedison\b", r"$^"),
    ("TVO", "Teollisuuden Voima", r"teollisuuden voima", r"$^"),
    ("ESB", "Electricity Supply Board", r"\besb\b|electricity supply board|esbpg", r"$^"),
]
N_BOOT = 4000
MIN_MW = 2000.0
MIN_MW_SWEEP = [500.0, 1000.0, 2000.0, 5000.0]
HEADLINE = {"model": "REMIND", "scenario": "Net Zero 2050", "alloc": "ownership",
            "alias": "extended", "horizon": HORIZON, "direction": "lookup", "min_mw": MIN_MW,
            "listed_only": True}


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


def _open(url, data=None, headers=None, timeout=180, tries=6):
    """GET or POST; on HTTP 429 or 5xx wait (Retry-After if given) and retry."""
    for k in range(tries):
        req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=_ctx())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            time.sleep(float(e.headers.get("Retry-After") or 5 * (k + 1)))


# ---------------------------------------------------------------- fetch

def fetch_wri():
    text = _open(WRI_URL).read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def fetch_ngfs():
    """{model: {scenario: {tech: {year: GW}}}} for the headline scenarios, EU-wide."""
    token = json.load(_open(AUTH_URL))
    auth = {"Authorization": "Bearer " + token}
    runs = json.load(_open(NGFS_BASE + "/runs?getOnlyDefaultRuns=true", headers=auth))
    names = {m[0] for m in MODELS.values()}
    want = {r["run_id"]: (r["model"], r["scenario"]) for r in runs
            if r["model"] in names and r["scenario"] in SCENARIOS}
    regions = sorted({reg for m in MODELS.values() for reg in m[1]})
    variables = sorted({f"Capacity|Electricity|{v}" for vs in NGFS_VARS.values() for v in vs})
    body = {"filters": {"regions": regions, "variables": variables, "runs": sorted(want),
                        "years": SCEN_YEARS, "units": [], "timeslices": []}}
    rows = json.load(_open(NGFS_BASE + "/runs/bulk/ts", data=json.dumps(body).encode(),
                           headers={**auth, "Content-Type": "application/json"}))
    inv = {m[0]: k for k, m in MODELS.items()}
    var2tech = {f"Capacity|Electricity|{v}": t for t, vs in NGFS_VARS.items() for v in vs}
    out, raw = {}, []
    for r in rows:
        key = inv[r["model"]]
        if r["region"] not in MODELS[key][1] or r["unit"] != "GW":
            continue
        t = var2tech[r["variable"]]
        cell = out.setdefault(key, {}).setdefault(r["scenario"], {}).setdefault(t, {})
        cell[r["year"]] = cell.get(r["year"], 0.0) + r["value"]
        raw.append([key, r["scenario"], r["region"], r["variable"], r["year"], r["value"]])
    return out, raw


def fetch_eurostat():
    """{tech: {year: MW}} for EU27, mapped to the six technologies."""
    doc = json.load(_open(EUROSTAT_URL))
    dim = doc["dimension"]
    sizes, ids = doc["size"], doc["id"]
    siec, time = dim["siec"]["category"]["index"], dim["time"]["category"]["index"]
    strides, s = {}, 1
    for name, size in zip(reversed(ids), reversed(sizes)):
        strides[name] = s
        s *= size
    groups = {"Coal": ["C0000", "P1000"], "Gas": ["G3000"], "Oil": ["O4000"], "Nuclear": ["N9000"],
              "Hydro": ["RA100"], "Renewables": ["RA200", "RA300", "RA410", "RA420", "RA500",
                                                  "R5000_W6000"]}
    out = {t: {} for t in groups}
    for t, codes in groups.items():
        for y, yi in time.items():
            vals = [doc["value"].get(str(siec[c] * strides["siec"] + yi * strides["time"]))
                    for c in codes]
            if all(v is not None for v in vals):
                out[t][int(y)] = float(sum(vals))
    return out


def wikidata_listing(groups):
    """{group: {qid, label, description, listed, exchanges}}: first search hit whose description
    reads as an energy company, then its P414 statements without an end date (P582)."""
    found = {}
    for g, term in groups:
        u = WIKIDATA_API + "?" + urllib.parse.urlencode(
            {"action": "wbsearchentities", "format": "json", "language": "en", "limit": 8,
             "search": term})
        time.sleep(1.0)
        hits = json.load(_open(u))["search"]
        pick = next((h for h in hits if re.search(
            r"energy|electric|utility|power|oil|gas|nuclear|renewable|public company|business", h.get("description") or "", re.I)),
            None)
        found[g] = {"qid": pick["id"] if pick else None, "label": pick["label"] if pick else None,
                    "description": pick.get("description") if pick else None,
                    "listed": False, "exchanges": [], "ended_exchanges": []}
    qids = " ".join(f"wd:{v['qid']}" for v in found.values() if v["qid"])
    q = ("SELECT ?c ?exLabel ?end WHERE { VALUES ?c { %s } ?c p:P414 ?st . ?st ps:P414 ?ex . "
         "OPTIONAL { ?st pq:P582 ?end } SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". } }"
         % qids)
    rows = json.load(_open(WIKIDATA_SPARQL + "?format=json&query=" + urllib.parse.quote(q)))
    by_qid = {v["qid"]: g for g, v in found.items() if v["qid"]}
    for b in rows["results"]["bindings"]:
        g = by_qid[b["c"]["value"].rsplit("/", 1)[1]]
        if "end" not in b:
            found[g]["listed"] = True
            found[g]["exchanges"].append(b["exLabel"]["value"])
        else:
            found[g]["ended_exchanges"].append(
                f"{b['exLabel']['value']} (until {b['end']['value'][:10]})")
    return found


# ---------------------------------------------------------------- plants and owners

def load_plants(rows, base_year=BASE_YEAR):
    """Plants in the EU27+UK with a mapped technology, in the base year. A plant with no
    commissioning year is kept: WRI has none for half the register, and dropping them would drop
    the oldest fleet."""
    out = []
    for r in rows:
        tech = FUEL2TECH.get(r["primary_fuel"])
        if r["country"] not in EU28 or tech is None:
            continue
        try:
            cap = float(r["capacity_mw"])
        except ValueError:
            continue
        if cap <= 0:
            continue
        yr = r["commissioning_year"]
        if yr and int(float(yr)) > base_year:
            continue
        out.append({"name": r["name"], "country": r["country"], "tech": tech, "mw": cap,
                    "year": int(float(yr)) if yr else None,
                    "owner": (r["owner"] or "").strip()})
    return out


def parse_owner(owner):
    """Split an owner string into [(name, stated_share_or_None)], on ';' and '/'."""
    parts = []
    for p in re.split(r"[;/]", owner):
        p = p.strip()
        if not p:
            continue
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", p)
        parts.append((re.sub(r"\d+(?:\.\d+)?\s*%", "", p).strip(" :"), float(m.group(1)) / 100 if m else None))
    return parts


def split_shares(owner, alloc):
    """[(name, share)] for one plant. 'control': the first-named owner holds the whole plant
    (WRI has no operator field; first-named is the proxy). 'ownership': stated percentages where
    given; the remainder split equally among parts with none; all equal if none are stated."""
    parts = parse_owner(owner)
    if not parts:
        return []
    if alloc == "control":
        return [(parts[0][0], 1.0)]
    stated = sum(s for _, s in parts if s is not None)
    free = [i for i, (_, s) in enumerate(parts) if s is None]
    rest = max(0.0, 1.0 - stated) / len(free) if free else 0.0
    return [(n, s if s is not None else rest) for n, s in parts]


def group_of(name, tier):
    for g, _, strict, ext in ALIASES:
        if re.search(strict, name, re.I) or (tier == "extended" and re.search(ext, name, re.I)):
            return g
    return None


def capacity_matrix(plants, alloc, tier):
    """{group: {tech: MW}} of base-year capacity attributed to each group."""
    out = {}
    for p in plants:
        for name, share in split_shares(p["owner"], alloc):
            g = group_of(name, tier)
            if g:
                row = out.setdefault(g, dict.fromkeys(TECHS, 0.0))
                row[p["tech"]] += p["mw"] * share
    return out


# ---------------------------------------------------------------- PACTA arithmetic

def target(p_tech, p_sector, s0_tech, st_tech, s0_sector, increasing):
    """Market-share-approach target for one company and technology (r2dii.analysis)."""
    if increasing:
        return max(0.0, p_tech + p_sector * (st_tech - s0_tech) / s0_sector)
    if s0_tech <= 0:
        raise ValueError("decreasing technology with zero base-year scenario capacity")
    return p_tech * st_tech / s0_tech


def targets_matrix(P, s0, st, increasing_flags):
    """P: companies x techs (MW). s0, st: scenario capacity by tech at base and horizon.
    Returns companies x techs targets."""
    p_sector = P.sum(axis=1)
    s0_sector = s0.sum()
    T = np.zeros_like(P)
    for j in range(P.shape[1]):
        T[:, j] = [target(P[i, j], p_sector[i], s0[j], st[j], s0_sector, increasing_flags[j])
                   for i in range(P.shape[0])]
    return T


def gap(P, T):
    """Set-level gap by tech: (held - target) / total held, production-weighted by construction
    because both sums are in MW."""
    return (P.sum(axis=0) - T.sum(axis=0)) / P.sum()


def bootstrap_gap(P, T, rng, n=N_BOOT):
    """Resample companies, the population the set belongs to. The scenario enters through T,
    which is the same array in every replicate, so a scenario error is shared by all companies
    by construction."""
    c = P.shape[0]
    out = np.empty((n, P.shape[1]))
    for b in range(n):
        idx = rng.integers(0, c, c)
        out[b] = gap(P[idx], T[idx])
    return out


def bootstrap_gap_models(P, Ts, rng, n=N_BOOT):
    """As bootstrap_gap, and each replicate also draws ONE scenario model for all companies at
    once: the model error is shared by every line, never drawn per company."""
    c = P.shape[0]
    out = np.empty((n, P.shape[1]))
    for b in range(n):
        T = Ts[rng.integers(0, len(Ts))]
        idx = rng.integers(0, c, c)
        out[b] = gap(P[idx], T[idx])
    return out


def spearman(a, b):
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


# ---------------------------------------------------------------- orchestration

def scenario_vectors(ngfs, model, scenario, horizon, pace=None):
    s = ngfs[model][scenario]
    s0 = np.array([s[t][BASE_YEAR] for t in TECHS])
    st = np.array([s[t][horizon] for t in TECHS])
    if pace is not None:
        st = s0 * (st / s0) ** 1.0 * np.array([pace[t] ** ((horizon - BASE_YEAR) / 4.0) for t in TECHS])
    return s0, st


def set_matrix(plants, listing, alloc, tier, min_mw, listed_only=True):
    cm = capacity_matrix(plants, alloc, tier)
    members = sorted(g for g, row in cm.items()
                     if (listing.get(g, {}).get("listed") or not listed_only)
                     and sum(row.values()) >= min_mw)
    P = np.array([[cm[g][t] for t in TECHS] for g in members])
    return members, P


def evaluate(ngfs, plants, listing, cfg, pace=None, coverage=None):
    members, P = set_matrix(plants, listing, cfg["alloc"], cfg["alias"], cfg["min_mw"],
                            cfg["listed_only"])
    if coverage is not None:
        P = P * np.array([coverage[t] for t in TECHS])
    s0, st = scenario_vectors(ngfs, cfg["model"], cfg["scenario"], cfg["horizon"], pace)
    flags = [(t in INCREASING) if cfg["direction"] == "lookup" else bool(st[j] >= s0[j])
             for j, t in enumerate(TECHS)]
    T = targets_matrix(P, s0, st, flags)
    return members, P, T, gap(P, T)


def available(ngfs, model, scenario):
    s = ngfs.get(model, {}).get(scenario)
    return bool(s) and all(t in s and all(y in s[t] for y in (BASE_YEAR, 2025, 2030, 2035))
                           for t in TECHS)


def backtest(ngfs, eurostat, year=2024):
    """Realised EU27 capacity growth 2020->year (Eurostat) against each scenario's, by tech.
    Scenario value at `year` is interpolated linearly between 2020 and 2025."""
    rows = []
    w = (year - BASE_YEAR) / 5.0
    for t in TECHS:
        real = eurostat[t][year] / eurostat[t][BASE_YEAR]
        for m in MODELS:
            for sc in SCENARIOS:
                if not available(ngfs, m, sc):
                    continue
                s = ngfs[m][sc][t]
                sy = s[BASE_YEAR] + w * (s[2025] - s[BASE_YEAR])
                rows.append({"tech": t, "model": m, "scenario": sc, "realised_ratio": real,
                             "scenario_ratio": sy / s[BASE_YEAR],
                             "error": sy / s[BASE_YEAR] - real})
    return rows


def pace_factors(ngfs, eurostat, model, scenario, year=2024):
    """Annualised-ratio correction: (realised/scenario ratio at `year`), per tech."""
    f = {}
    for r in backtest(ngfs, eurostat, year):
        if r["model"] == model and r["scenario"] == scenario:
            f[r["tech"]] = r["realised_ratio"] / r["scenario_ratio"]
    return f


def build(seed=0):
    rng = np.random.default_rng(seed)
    wri = fetch_wri()
    ngfs, ngfs_raw = fetch_ngfs()
    eurostat = fetch_eurostat()
    plants = load_plants(wri)
    listing = wikidata_listing([(g, term) for g, term, _, _ in ALIASES])

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "ngfs_eu_capacity.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "scenario", "region", "variable", "year", "gw"])
        w.writerows(sorted(ngfs_raw))

    cfg = dict(HEADLINE)
    members, P, T, g = evaluate(ngfs, plants, listing, cfg)
    boots = bootstrap_gap(P, T, rng)
    lo, hi = np.percentile(boots, [2.5, 97.5], axis=0)
    total = float(P.sum())
    s0, st = scenario_vectors(ngfs, cfg["model"], cfg["scenario"], cfg["horizon"])
    headline = {
        "config": cfg, "n_companies": len(members), "members": members, "total_mw": total,
        "by_tech": [{"tech": t, "held_mw": float(P[:, j].sum()), "target_mw": float(T[:, j].sum()),
                     "held_share": float(P[:, j].sum() / total),
                     "target_share": float(T[:, j].sum() / total),
                     "gap": float(g[j]), "ci_lo": float(lo[j]), "ci_hi": float(hi[j]),
                     "scenario_change_pct": float(100 * (st[j] / s0[j] - 1))}
                    for j, t in enumerate(TECHS)],
        "n_boot": N_BOOT,
    }
    fossil = boots[:, [0, 1, 2]].sum(axis=1)
    Ts = []
    for m in MODELS:
        if available(ngfs, m, cfg["scenario"]):
            Ts.append(evaluate(ngfs, plants, listing, dict(cfg, model=m))[2])
    incl = bootstrap_gap_models(P, Ts, rng)
    ilo, ihi = np.percentile(incl, [2.5, 97.5], axis=0)
    for j, r in enumerate(headline["by_tech"]):
        r["incl_model_ci_lo"], r["incl_model_ci_hi"] = float(ilo[j]), float(ihi[j])
    ifossil = incl[:, [0, 1, 2]].sum(axis=1)
    headline["n_models_drawn"] = len(Ts)
    headline["fossil"] = {"incl_model_ci_lo": float(np.percentile(ifossil, 2.5)),
                          "incl_model_ci_hi": float(np.percentile(ifossil, 97.5)),"gap": float(g[:3].sum()), "ci_lo": float(np.percentile(fossil, 2.5)),
                          "ci_hi": float(np.percentile(fossil, 97.5))}
    sizes = P.sum(axis=1)
    top = np.argsort(-sizes)
    headline["companies"] = [{"group": members[i], "mw": float(sizes[i]),
                              **{t: float(P[i, j]) for j, t in enumerate(TECHS)},
                              "gap_mw": {t: float(P[i, j] - T[i, j]) for j, t in enumerate(TECHS)},
                              "listed_on": listing[members[i]]["exchanges"]} for i in top]
    headline["largest_two_share_of_set"] = float(sizes[top[:2]].sum() / total)
    # leave-one-out: how much does the coal and renewables gap move when each company is dropped
    loo = []
    for i in range(len(members)):
        keep = [k for k in range(len(members)) if k != i]
        gi = gap(P[keep], T[keep])
        loo.append({"dropped": members[i], "coal": float(gi[0]), "renewables": float(gi[5])})
    headline["leave_one_out"] = loo

    # sweeps: one factor at a time around the headline
    def sweep(label, values, key, fmt=str):
        rows = []
        for v in values:
            c = dict(HEADLINE)
            c[key] = v
            mem, Pp, Tp, gp = evaluate(ngfs, plants, listing, c)
            rows.append({"factor": label, "value": fmt(v), "n_companies": len(mem),
                         "total_mw": float(Pp.sum()), "coal": float(gp[0]), "fossil": float(gp[:3].sum()),
                         "renewables": float(gp[5]), "gap": {t: float(gp[j]) for j, t in enumerate(TECHS)}})
        return rows

    sweeps = (sweep("set definition", [True, False], "listed_only",
                    lambda v: "listed owner groups" if v else "all aliased owner groups")
              + sweep("allocation rule", ["ownership", "control"], "alloc")
              + sweep("owner-name aliases", ["strict", "extended"], "alias")
              + sweep("minimum fleet, MW", MIN_MW_SWEEP, "min_mw", lambda v: f"{v:,.0f}")
              + sweep("horizon", HORIZONS, "horizon")
              + sweep("direction rule", ["lookup", "scenario"], "direction")
              + sweep("IAM", list(MODELS), "model"))
    scen_rows = []
    for m in MODELS:
        for sc in SCENARIOS:
            if not available(ngfs, m, sc):
                continue
            c = dict(HEADLINE, model=m, scenario=sc)
            mem, Pp, Tp, gp = evaluate(ngfs, plants, listing, c)
            scen_rows.append({"model": m, "scenario": sc, "coal": float(gp[0]),
                              "fossil": float(gp[:3].sum()), "renewables": float(gp[5]),
                              "gap": {t: float(gp[j]) for j, t in enumerate(TECHS)}})
    def one(label, value, **kw):
        mem, Pp, Tp, gp = evaluate(ngfs, plants, listing, cfg, **kw)
        return {"factor": label, "value": value, "n_companies": len(mem),
                "total_mw": float(Pp.sum()), "coal": float(gp[0]), "fossil": float(gp[:3].sum()),
                "renewables": float(gp[5]), "gap": {t: float(gp[j]) for j, t in enumerate(TECHS)}}

    pf = pace_factors(ngfs, eurostat, cfg["model"], cfg["scenario"])
    cov = {t: eurostat[t][BASE_YEAR] / sum(p["mw"] for p in plants
                                           if p["tech"] == t and p["country"] != "GBR")
           for t in TECHS}
    sweeps.append(one("WRI coverage rescaled to Eurostat, by technology", "rescaled", coverage=cov))
    sweeps.append(one("scenario pace corrected by 2020-24 backtest", "corrected", pace=pf))
    base_coal = headline["by_tech"][0]["gap"]
    spans = {}
    for r in sweeps:
        spans.setdefault(r["factor"], []).append(r["coal"])
    spans["scenario and IAM grid"] = [r["coal"] for r in scen_rows]
    sweep_summary = sorted(
        [{"factor": f, "coal_min": min(v + [base_coal]), "coal_max": max(v + [base_coal]),
          "coal_span": max(v + [base_coal]) - min(v + [base_coal])} for f, v in spans.items()],
        key=lambda r: -r["coal_span"])

    # allocation-rule rank agreement on company-level coal share
    own = capacity_matrix(plants, "ownership", "extended")
    ctl = capacity_matrix(plants, "control", "extended")
    common = [m for m in members if m in own and m in ctl]
    moved = sum(abs(own.get(m, dict.fromkeys(TECHS, 0))[t] - ctl.get(m, dict.fromkeys(TECHS, 0))[t])
                for m in set(own) | set(ctl) for t in TECHS) / 2
    rank = {"n": len(common), "mw_moved_between_groups": moved,
            "share_of_attributed_mw": moved / sum(sum(r.values()) for r in own.values()),
            "spearman_coal_share": spearman(
                [own[m]["Coal"] / sum(own[m].values()) for m in common],
                [ctl[m]["Coal"] / sum(ctl[m].values()) for m in common])}

    bt = backtest(ngfs, eurostat)
    # validation of WRI against Eurostat, EU27 only (Eurostat has no UK)
    wri27 = {t: sum(p["mw"] for p in plants if p["tech"] == t and p["country"] != "GBR") for t in TECHS}
    val = [{"tech": t, "wri_mw": wri27[t], "eurostat_mw": eurostat[t][BASE_YEAR],
            "ratio": wri27[t] / eurostat[t][BASE_YEAR]} for t in TECHS]
    owned = sum(p["mw"] for p in plants if p["owner"])
    attributed = sum(sum(P[i]) for i in range(len(members)))
    out = {
        "estimand": ("production-weighted gap, as a share of the set's capacity, between the "
                     "base-year (2020) capacity of a set of listed European power utilities and "
                     "the PACTA market-share-approach target from an NGFS Phase 5 pathway, by "
                     "technology, at the horizon"),
        "headline": headline, "sweeps": sweeps, "sweep_summary": sweep_summary,
        "coverage_factors": cov, "scenario_grid": scen_rows,
        "allocation_rank_agreement": rank, "backtest": bt, "pace_factors": pf,
        "validation_wri_vs_eurostat": val,
        "coverage": {"n_plants": len(plants),
                     "max_commissioning_year": max(p["year"] for p in plants if p["year"]),
                     "n_without_commissioning_year": sum(1 for p in plants if not p["year"]), "plant_mw": sum(p["mw"] for p in plants),
                     "owner_known_mw": owned, "set_mw": float(attributed),
                     "n_owner_strings": len({p["owner"] for p in plants if p["owner"]})},
        "listing": listing,
        "sources": {"wri": WRI_URL, "ngfs": NGFS_BASE, "eurostat": EUROSTAT_URL,
                    "wikidata": WIKIDATA_API},
        "scenario_regions": {k: v[1] for k, v in MODELS.items()},
    }
    with open(os.path.join(RESULTS, "pacta_alignment.json"), "w") as f:
        json.dump(out, f, indent=1)
    with open(os.path.join(RESULTS, "company_capacity.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group", "listed_on"] + TECHS + ["total_mw"])
        for c in headline["companies"]:
            w.writerow([c["group"], "; ".join(c["listed_on"])] + [round(c[t], 1) for t in TECHS]
                       + [round(c["mw"], 1)])
    print(f"{len(plants)} plants, {len(members)} listed groups, {total:,.0f} MW")
    for r in headline["by_tech"]:
        print(f"  {r['tech']:11s} held {r['held_share']:6.1%} target {r['target_share']:6.1%} "
              f"gap {r['gap']:+7.1%} [{r['ci_lo']:+.1%}, {r['ci_hi']:+.1%}]")
    return out


if __name__ == "__main__":
    build()
