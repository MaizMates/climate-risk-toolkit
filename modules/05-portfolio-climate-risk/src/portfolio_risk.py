"""Climate risk of a real, public equity portfolio: sector exposure and a carbon-intensity proxy.

ESTIMAND. For the SPDR MSCI EMU UCITS ETF (ISIN IE00B910VR50), a real, fully disclosed Eurozone
equity portfolio published without an account: (a) the share of market value in climate-policy-
relevant sectors (Battiston et al. 2017), and (b) the portfolio's weighted average carbon
intensity, in tCO2e per EUR million of gross value added, with an interval that reflects proxy
uncertainty.

This is a sector-average proxy, not a company-level measurement: every holding gets its home
country's national average intensity for one representative NACE activity. PCAF data-quality
score 5 on every line -- see README.md and the first page of the deck.

Data:
- Holdings. SSGA's own daily holdings file for ZPRE GY (SPDR MSCI EMU UCITS ETF), fetched live
  from ssga.com, no key, no account, no transcription.
- Emission intensity. Eurostat env_ac_ainah_r2 (air emissions accounts by NACE Rev.2, greenhouse
  gases, thousand tonnes) divided by Eurostat nama_10_a64 (gross value added by NACE Rev.2,
  current prices), public dissemination API, no key, across all EU member states that report it.
- Climate-policy-relevant sector classification. Battiston, Mandel, Monasterolo, Schuetze &
  Visentin (2017), "A climate stress-test of the financial system", Nature Climate Change 7,
  283-288 -- encoded here as a category label per NACE code, not a number transcribed from the
  paper.
- Physical risk overlay. modules/01-heat-stress-gradient/results/heat_gradient.json, already in
  this repository, by the holding's country of domicile.
- Validation. State Street's own per-ISIN sustainability report (MSCI-sourced Weighted Average
  Carbon Intensity), fetched from ssga.com and read with a minimal stdlib PDF text extractor,
  because this fund does not publish that figure anywhere machine-readable otherwise.
"""
import io
import json
import os
import random
import re
import ssl
import urllib.request
import zlib

import openpyxl

FUND_ISIN = "IE00B910VR50"
HOLDINGS_URL = ("https://www.ssga.com/library-content/products/fund-data/etfs/emea/"
                "holdings-daily-emea-en-zpre-gy.xlsx")
SUSTAINABILITY_URL = ("https://www.ssga.com/library-content/products/ssga-sustainability-report/"
                      f"etfs/{FUND_ISIN.lower()}-ssga-sustainability-report.pdf")

GHG_URL_TEMPLATE = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
                    "env_ac_ainah_r2?format=JSON&lang=EN&airpol=GHG&unit=THS_T"
                    "&sinceTimePeriod=2015&{naces}&{geos}")
GVA_URL_TEMPLATE = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
                    "nama_10_a64?format=JSON&lang=EN&unit=CP_MEUR&na_item=B1G"
                    "&sinceTimePeriod=2015&{naces}&{geos}")

HAZARD_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                 "01-heat-stress-gradient", "results", "heat_gradient.json"),
]

REF_YEAR = 2024
YEAR_SWEEP = list(range(2015, 2025))
K_REFERENCE = 2  # module 01/03's reference threshold on change_days, reused for continuity
N_BOOT = 2000

# The holding's country, as SSGA's file names it -> (ISO3 for module 01's hazard table,
# Eurostat 2-letter geo code). Only the ten Eurozone countries this fund actually holds.
COUNTRY_MAP = {
    "France": ("FRA", "FR"), "Germany": ("DEU", "DE"), "Netherlands": ("NLD", "NL"),
    "Spain": ("ESP", "ES"), "Italy": ("ITA", "IT"), "Finland": ("FIN", "FI"),
    "Belgium": ("BEL", "BE"), "Ireland": ("IRL", "IE"), "Austria": ("AUT", "AT"),
    "Portugal": ("PRT", "PT"),
}

# All EU member states that could report a given NACE code's intensity -- the cross-country
# spread this module resamples for its interval on the proxy (see build()).
EU_GEOS = ["BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT", "CY", "LV",
           "LT", "LU", "HU", "MT", "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]

# The holdings file carries an MSCI GICS sector label, not a NACE code -- a coarse, many-to-one
# join: one NACE Rev.2 code stands in for an entire GICS sector, chosen as the single code that
# best represents where that sector's market value actually sits in this specific portfolio (see
# notes.md for the industry breakdown behind each choice). Every choice collapses real
# heterogeneity inside the sector; that is the coarseness the roadmap asks this module to name.
GICS_TO_NACE = {
    "Energy": "B",                    # oil & gas / coal extraction -- refining (C19) excluded
    "Materials": "C20",                # chemicals -- the largest Materials sub-industry here
    "Industrials": "C28",              # machinery & equipment -- the modal Industrials industry
    "Consumer Discretionary": "G",     # wholesale/retail trade & repair, incl. of motor vehicles
    "Consumer Staples": "C10-C12",     # food, beverages, tobacco manufacture
    "Health Care": "C21",              # pharmaceutical manufacturing, not health services (Q)
    "Financials": "K",                 # financial and insurance activities
    "Information Technology": "C26",   # computer, electronic & optical products (ASML-driven)
    "Communication Services": "J",     # information and communication
    "Utilities": "D",                  # electricity, gas, steam and air conditioning supply
    "Real Estate": "L",                # real estate activities
}

# One alternative NACE code per sector, for the sensitivity sweep -- the next most defensible
# reading of the same GICS label, picked where this portfolio actually holds a real mix of
# sub-industries under one label (see notes.md).
ALT_GICS_TO_NACE = {
    "Materials": "C24",                # basic metals, instead of chemicals
    "Industrials": "C",                # whole manufacturing section, instead of one division
    "Consumer Discretionary": "C29",   # motor vehicle manufacture, instead of retail trade
    "Health Care": "Q",                # human health activities, instead of pharma manufacturing
}

NACE_CODES = sorted(set(GICS_TO_NACE.values()) | set(ALT_GICS_TO_NACE.values()))

# Climate policy relevant sectors (CPRS), category per NACE code, after Battiston, Mandel,
# Monasterolo, Schuetze & Visentin (2017), "A climate stress-test of the financial system",
# Nature Climate Change 7, 283-288. This is a categorical label taken from the paper's published
# sector groupings, not a number transcribed from it.
CPRS_CATEGORY = {
    "A": "agriculture",
    "B": "fossil_fuel",
    "C17": "energy_intensive", "C19": "energy_intensive", "C20": "energy_intensive",
    "C23": "energy_intensive", "C24": "energy_intensive",
    "D": "utilities",
    "F": "housing", "L": "housing",
    "C29": "transportation", "C30": "transportation", "H": "transportation",
}


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


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "climate-risk-toolkit"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read()


def fetch_holdings(url=HOLDINGS_URL):
    """Parse SSGA's daily holdings file. Returns (holdings, as_of) with one dict per real
    holding -- cash, FX and 'Unassigned' rows are dropped, not counted as a sector."""
    raw = _get(url)
    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    rows = list(wb.active.iter_rows(values_only=True))
    as_of = next(r[1] for r in rows if r and r[0] == "Holdings As Of:")
    header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "ISIN")
    header = rows[header_idx]
    expected = ("ISIN", "SEDOL", "Security Name", "Currency", "Number of Shares",
                "Percent of Fund", "Trade Country Name", "Local Price",
                "Sector Classification", "Industry Classification", "Base Market Value")
    if header[:len(expected)] != expected:
        raise ValueError(f"holdings file header changed, expected {expected}, got {header}")

    holdings = []
    for r in rows[header_idx + 1:]:
        if not r or not r[0] or r[0] == "Unassigned":
            continue
        isin, sedol, name, ccy, shares, pct, country, price, sector, industry, mv = r[:11]
        if not isinstance(mv, (int, float)) or mv <= 0:
            continue
        if country not in COUNTRY_MAP or sector not in GICS_TO_NACE:
            continue
        holdings.append({"isin": isin, "name": name, "country": country,
                         "sector": sector, "industry": industry, "market_value": float(mv)})
    return holdings, as_of


def _jsonstat_strides(doc):
    strides, acc = {}, 1
    for name, size in zip(reversed(doc["id"]), reversed(doc["size"])):
        strides[name] = acc
        acc *= size
    return strides


def _jsonstat_get(doc, strides, **selectors):
    idx = 0
    for name in doc["id"]:
        cat = doc["dimension"][name]["category"]["index"]
        if name in selectors:
            key = selectors[name]
            if key not in cat:
                return None
            idx += cat[key] * strides[name]
    return doc["value"].get(str(idx))


def fetch_eurostat_table(url_template, naces=NACE_CODES, geos=EU_GEOS, years=YEAR_SWEEP):
    """One Eurostat call for every (geo, nace, year) combination needed. Returns
    {(geo, nace, year): value}, omitting cells Eurostat doesn't report."""
    naces_q = "&".join(f"nace_r2={n}" for n in naces)
    geos_q = "&".join(f"geo={g}" for g in geos)
    doc = json.loads(_get(url_template.format(naces=naces_q, geos=geos_q)))
    strides = _jsonstat_strides(doc)
    out = {}
    for g in geos:
        for n in naces:
            for y in years:
                v = _jsonstat_get(doc, strides, geo=g, nace_r2=n, time=str(y))
                if v is not None:
                    out[(g, n, y)] = v
    return out


def intensity_table(ghg, gva, naces=NACE_CODES, geos=EU_GEOS, years=YEAR_SWEEP):
    """tCO2e per EUR million of gross value added, {(geo, nace, year): intensity}. THS_T
    (thousand tonnes) times 1000 gives tonnes; GVA is already in EUR million."""
    out = {}
    for g in geos:
        for n in naces:
            for y in years:
                ghg_v, gva_v = ghg.get((g, n, y)), gva.get((g, n, y))
                if ghg_v is not None and gva_v is not None and gva_v > 0:
                    out[(g, n, y)] = ghg_v * 1000.0 / gva_v
    return out


def sector_distribution(intensity, nace, year):
    """Intensity for one NACE code across every EU member state that reports it: the spread
    this module resamples for the interval on the proxy."""
    return [v for (g, n, y), v in intensity.items() if n == nace and y == year]


def holding_intensity(intensity, geo, nace, year):
    """(value, is_fallback). Falls back to the cross-country median when the holding's own
    country doesn't report that NACE division -- true for Germany and Spain at division level
    in nama_10_a64, a real Eurostat disclosure-control gap, not a bug. See notes.md."""
    v = intensity.get((geo, nace, year))
    if v is not None:
        return v, False
    dist = sector_distribution(intensity, nace, year)
    if not dist:
        return None, True
    dist.sort()
    return dist[len(dist) // 2], True


def classify_cprs(nace):
    return CPRS_CATEGORY.get(nace, "not_cpr")


def portfolio_waci(holdings, intensity, mapping, year=REF_YEAR):
    """Market-value-weighted average carbon intensity, plus each holding's own intensity and
    fallback flag, for reuse by the bootstrap and the sensitivity sweep."""
    rows = []
    for h in holdings:
        _, geo2 = COUNTRY_MAP[h["country"]]
        nace = mapping[h["sector"]]
        val, is_fallback = holding_intensity(intensity, geo2, nace, year)
        rows.append({**h, "nace": nace, "intensity": val, "fallback": is_fallback})
    total_mv = sum(r["market_value"] for r in rows if r["intensity"] is not None)
    if total_mv == 0:
        return None, rows
    waci = sum(r["market_value"] * r["intensity"] for r in rows
              if r["intensity"] is not None) / total_mv
    return waci, rows


def _ratio_distribution(intensity, nace, year):
    """Cross-country intensities for one NACE code, expressed as a ratio to their own median.
    A plain draw of the absolute cross-country levels would recentre the whole portfolio on the
    EU27 average -- dominated by higher-intensity member states this fund barely holds -- instead
    of putting an interval around this portfolio's own point estimate. The ratio has the same
    dispersion but a median of 1, so resampling it around each holding's own value is what turns
    the roadmap's 'spread across member states' into an interval, not a different central value."""
    dist = sector_distribution(intensity, nace, year)
    if not dist:
        return None
    med = sorted(dist)[len(dist) // 2]
    return [v / med for v in dist] if med else None


def bootstrap_waci_ci(rows, intensity, year=REF_YEAR, n=N_BOOT, seed=0):
    """Resample each holding's own intensity by the cross-country dispersion for its NACE code --
    the roadmap's stated proxy uncertainty: how much this holding's number would move if it sat
    in a different member state, since a single company-level figure is not available."""
    rng = random.Random(seed)
    ratios = {n_: _ratio_distribution(intensity, n_, year) for n_ in {r["nace"] for r in rows}}
    usable = [r for r in rows if r["intensity"] is not None and ratios.get(r["nace"])]
    total_mv = sum(r["market_value"] for r in usable)
    if total_mv == 0:
        return None, None
    draws = []
    for _ in range(n):
        s = 0.0
        for r in usable:
            rr = ratios[r["nace"]]
            s += r["market_value"] * r["intensity"] * rr[rng.randrange(len(rr))]
        draws.append(s / total_mv)
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return lo, hi


def cprs_share(holdings, mapping):
    total_mv = sum(h["market_value"] for h in holdings)
    by_cat = {}
    for h in holdings:
        cat = classify_cprs(mapping[h["sector"]])
        by_cat[cat] = by_cat.get(cat, 0.0) + h["market_value"]
    cprs_mv = sum(v for c, v in by_cat.items() if c != "not_cpr")
    return cprs_mv / total_mv, {c: v / total_mv for c, v in by_cat.items()}


def hazard_path():
    for c in HAZARD_CANDIDATES:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("module 01 hazard output not found at: " + ", ".join(HAZARD_CANDIDATES))


def load_hazard(scenario="ssp245"):
    rows = json.load(open(hazard_path()))
    return {r["iso3"]: r["change_days"] for r in rows if r["scenario"] == scenario}


def physical_overlay(holdings, hazard, k=K_REFERENCE, n=N_BOOT, seed=0):
    """Market-value-weighted change_days by country of domicile, and the share of value in
    countries crossing module 01/03's k=2 reference threshold. Countries module 01 never
    covered (here, Finland) are excluded and their weight reported separately."""
    covered = [h for h in holdings if COUNTRY_MAP[h["country"]][0] in hazard]
    uncovered_mv = sum(h["market_value"] for h in holdings) - sum(h["market_value"] for h in covered)
    total_mv = sum(h["market_value"] for h in covered)
    if total_mv == 0:
        return None
    mean_change = sum(h["market_value"] * hazard[COUNTRY_MAP[h["country"]][0]]
                      for h in covered) / total_mv
    exposed_mv = sum(h["market_value"] for h in covered
                     if hazard[COUNTRY_MAP[h["country"]][0]] > k)

    rng = random.Random(seed)
    n_h = len(covered)
    draws = []
    for _ in range(n):
        sample = [covered[rng.randrange(n_h)] for _ in range(n_h)]
        s_mv = sum(h["market_value"] for h in sample)
        if s_mv == 0:
            continue
        draws.append(sum(h["market_value"] * hazard[COUNTRY_MAP[h["country"]][0]]
                         for h in sample) / s_mv)
    draws.sort()
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]

    by_country = {}
    for h in covered:
        iso3 = COUNTRY_MAP[h["country"]][0]
        by_country.setdefault(h["country"], {"iso3": iso3, "change_days": hazard[iso3],
                                             "market_value": 0.0})
        by_country[h["country"]]["market_value"] += h["market_value"]
    portfolio_total = sum(h["market_value"] for h in holdings)
    by_country_rows = sorted(
        ({"country": c, **v, "weight": v["market_value"] / portfolio_total}
         for c, v in by_country.items()),
        key=lambda r: -r["weight"])

    return {"mean_change_days": mean_change, "ci_lo": lo, "ci_hi": hi,
           "exposed_share_at_k": exposed_mv / total_mv, "k": k,
           "covered_value_share": total_mv / (total_mv + uncovered_mv),
           "by_country": by_country_rows}


_TJ = re.compile(rb"\((?:[^()\\]|\\.)*\)\s*Tj")
_TJ_INNER = re.compile(rb"\((.*)\)\s*Tj", re.DOTALL)


def pdf_text(raw):
    """A minimal stdlib PDF text extractor: decompress each FlateDecode stream and pull out
    literal-string Tj operators, in file order. No PDF library is on the allowed list, and this
    fund's climate metrics are not published in any other machine-readable form."""
    streams = re.findall(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL)
    texts = []
    for s in streams:
        try:
            d = zlib.decompress(s)
        except zlib.error:
            continue
        for tok in _TJ.findall(d):
            m = _TJ_INNER.match(tok)
            if m:
                texts.append(m.group(1))
    return b" ".join(texts).decode("latin1", errors="replace")


def extract_ssga_waci(text):
    """The MSCI-sourced Scope 1+2+3 Weighted Average Carbon Intensity (tCO2e/$M Sales) from
    State Street's own per-fund sustainability report. Returns None if the report's layout has
    changed enough that this can no longer be located -- fail loud, not a stale number."""
    m = re.search(r"Weighted Average Carbon Intensity.*?Scope\s*1\+2\+3\s+([\d,]+\.\d+)",
                 text, re.DOTALL)
    return float(m.group(1).replace(",", "")) if m else None


def mapping_sensitivity(holdings, intensity, year=REF_YEAR):
    rows = []
    base_waci, _ = portfolio_waci(holdings, intensity, GICS_TO_NACE, year)
    base_cprs, _ = cprs_share(holdings, GICS_TO_NACE)
    rows.append({"variant": "base", "waci": base_waci, "cprs_share": base_cprs})
    for sector, alt_nace in ALT_GICS_TO_NACE.items():
        m = dict(GICS_TO_NACE)
        m[sector] = alt_nace
        waci, _ = portfolio_waci(holdings, intensity, m, year)
        cprs, _ = cprs_share(holdings, m)
        rows.append({"variant": f"{sector} -> {alt_nace}", "waci": waci, "cprs_share": cprs})
    m_all = dict(GICS_TO_NACE, **ALT_GICS_TO_NACE)
    waci_all, _ = portfolio_waci(holdings, intensity, m_all, year)
    cprs_all, _ = cprs_share(holdings, m_all)
    rows.append({"variant": "all alternates", "waci": waci_all, "cprs_share": cprs_all})
    return rows


def year_sensitivity(holdings, intensity, years=YEAR_SWEEP):
    out = []
    for y in years:
        waci, _ = portfolio_waci(holdings, intensity, GICS_TO_NACE, y)
        out.append({"year": y, "waci": waci})
    return out


def build():
    holdings, as_of = fetch_holdings()
    ghg = fetch_eurostat_table(GHG_URL_TEMPLATE)
    gva = fetch_eurostat_table(GVA_URL_TEMPLATE)
    intensity = intensity_table(ghg, gva)
    hazard = load_hazard()

    total_mv = sum(h["market_value"] for h in holdings)
    waci, waci_rows = portfolio_waci(holdings, intensity, GICS_TO_NACE, REF_YEAR)
    ci_lo, ci_hi = bootstrap_waci_ci(waci_rows, intensity, REF_YEAR)
    fallback_mv = sum(r["market_value"] for r in waci_rows if r["fallback"])
    cprs, cprs_breakdown = cprs_share(holdings, GICS_TO_NACE)

    sector_mv = {}
    for h in holdings:
        sector_mv[h["sector"]] = sector_mv.get(h["sector"], 0.0) + h["market_value"]
    country_mv = {}
    for h in holdings:
        country_mv[h["country"]] = country_mv.get(h["country"], 0.0) + h["market_value"]

    overlay = physical_overlay(holdings, hazard)
    mapping_sens = mapping_sensitivity(holdings, intensity)
    year_sens = year_sensitivity(holdings, intensity)

    try:
        ssga_waci = extract_ssga_waci(pdf_text(_get(SUSTAINABILITY_URL)))
        ssga_error = None
    except Exception as e:
        ssga_waci, ssga_error = None, str(e)

    out = {
        "estimand": ("share of market value in climate-policy-relevant sectors, and the "
                    "portfolio's weighted average carbon intensity in tCO2e per EUR million of "
                    "gross value added, for the SPDR MSCI EMU UCITS ETF"),
        "fund": {"isin": FUND_ISIN, "name": "SPDR MSCI EMU UCITS ETF", "holdings_as_of": str(as_of)},
        "reference_year": REF_YEAR,
        "n_holdings": len(holdings),
        "total_market_value_eur": total_mv,
        "sector_weights": {s: v / total_mv for s, v in sorted(sector_mv.items())},
        "country_weights": {c: v / total_mv for c, v in sorted(country_mv.items())},
        "cprs_share": cprs,
        "cprs_breakdown": cprs_breakdown,
        "sector_to_cprs": {s: classify_cprs(n) for s, n in GICS_TO_NACE.items()},
        "waci": {"point": waci, "ci_lo": ci_lo, "ci_hi": ci_hi,
                 "fallback_value_share": fallback_mv / total_mv, "unit": "tCO2e / EUR mn GVA"},
        "physical_overlay": overlay,
        "mapping_sensitivity": mapping_sens,
        "year_sensitivity": year_sens,
        "validation": {
            "source": "State Street per-ISIN sustainability report, MSCI Weighted Average "
                      "Carbon Intensity, Scope 1+2+3, tCO2e/$M Sales",
            "url": SUSTAINABILITY_URL,
            "ssga_waci_usd_per_million_sales": ssga_waci,
            "error": ssga_error,
            "note": ("Not unit-comparable: SSGA/MSCI use company Scope 1+2+3 emissions over "
                    "USD sales; this module uses NACE-sector emissions over EUR gross value "
                    "added. Reported as an order-of-magnitude and no-disclosed-metric check, "
                    "not a like-for-like validation."),
        },
    }
    os.makedirs("results", exist_ok=True)
    with open("results/portfolio_risk.json", "w") as f:
        json.dump(out, f, indent=1)

    print(f"{len(holdings)} holdings, EUR {total_mv:,.0f} total, as of {as_of}")
    print(f"CPRS share: {cprs:.1%}")
    print(f"WACI at {REF_YEAR}: {waci:.1f} [{ci_lo:.1f}, {ci_hi:.1f}] tCO2e/EUR mn GVA "
         f"({fallback_mv/total_mv:.1%} of value on a cross-country fallback)")
    if ssga_waci:
        print(f"SSGA/MSCI disclosed WACI (different units): {ssga_waci:.1f} tCO2e/$M Sales")
    else:
        print(f"SSGA validation fetch failed: {ssga_error}")
    print(f"Physical overlay: mean change_days {overlay['mean_change_days']:.2f} "
         f"[{overlay['ci_lo']:.2f}, {overlay['ci_hi']:.2f}], "
         f"{overlay['exposed_share_at_k']:.1%} of covered value in countries crossing k=2")
    return out


if __name__ == "__main__":
    build()
