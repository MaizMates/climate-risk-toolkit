"""Fetch borrower data from two public endpoints and write results/borrowers.csv.

Emissions: EPA Greenhouse Gas Reporting Program (GHGRP), facility-level direct emissions with the
parent-company ownership shares (data.epa.gov/efservice, no key).
Financials and SIC code: SEC EDGAR XBRL company facts and submissions (data.sec.gov, no key, User-Agent only).
The two are joined on an exact normalised company name against SEC's ticker list. Nothing is typed.
"""
import collections
import csv
import datetime
import json
import os
import re
import time
import urllib.request

YEARS = (2021, 2022, 2023)
EPA = "https://data.epa.gov/efservice"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{:010d}.json"
UA = {"User-Agent": "climate-risk-toolkit marcoizzo2001@gmail.com"}
# GHGRP sector_type S (suppliers of fuel and gases) and I (injection) are not direct emissions.
NON_DIRECT_SECTORS = {9, 10, 11, 12, 13, 16, 17}
HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "..", "results")

REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                "SalesRevenueGoodsNet"]
EQUITY_TAGS = ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
               "StockholdersEquity"]
LTD_TAGS = ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"]
LTD_PARTS = [["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
             ["LongTermDebtCurrent", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"]]
ST_TAGS = ["ShortTermBorrowings", "CommercialPaper"]

_SUFFIX = (r"\b(INCORPORATED|INC|CORPORATION|CORP|COMPANY|CO|LLC|LP|L P|LTD|LIMITED|PLC|THE|"
           r"HOLDINGS|HOLDING|GROUP|NA|N A)\b")


def get_json(url, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(2 * (k + 1))


def norm_name(s):
    s = re.sub(r"[^A-Z0-9 ]", " ", s.upper().replace("&", " AND "))
    return re.sub(r"\s+", " ", re.sub(_SUFFIX, " ", s)).strip()


def parse_parents(s):
    """'A INC (60%); B LLC (40%)' -> [('A INC', 60.0), ('B LLC', 40.0)]. Unparseable parts drop."""
    out = []
    for part in (s or "").split(";"):
        m = re.match(r"^(.*)\((\d+(?:\.\d+)?)%\)\s*$", part.strip())
        if m:
            out.append((m.group(1).strip(), float(m.group(2))))
    return out


def fetch_pages(path, step):
    """The efservice row range is inclusive, so page boundaries repeat one row; the caller dedupes."""
    rows, i = [], 0
    while True:
        r = get_json(f"{EPA}/{path}/rows/{i}:{i + step}/JSON")
        rows += r
        if len(r) < step:
            return rows
        i += step


def fetch_epa(year):
    fac = {r["facility_id"]: r for r in fetch_pages(f"pub_dim_facility/year/=/{year}", 3000)}
    seen, tot = set(), collections.defaultdict(float)
    for r in fetch_pages(f"pub_facts_sector_ghg_emission/year/=/{year}", 5000):
        k = (r["facility_id"], r["sector_id"], r["subsector_id"], r["gas_id"])
        if k in seen or r["sector_id"] in NON_DIRECT_SECTORS or r["co2e_emission"] is None:
            continue
        seen.add(k)
        tot[r["facility_id"]] += r["co2e_emission"]
    return fac, tot


def attribute_to_parents(fac, tot):
    """Ownership-weighted direct emissions by normalised parent name, with the dominant NAICS."""
    par = collections.defaultdict(lambda: {"e": 0.0, "n": 0, "names": set(), "naics": collections.defaultdict(float)})
    unparsed = 0
    for fid, e in tot.items():
        parents = parse_parents(fac[fid]["parent_company"]) if fid in fac else []
        if not parents:
            unparsed += e
            continue
        for name, pct in parents:
            p = par[norm_name(name)]
            p["e"] += e * pct / 100
            p["n"] += 1
            p["names"].add(name)
            p["naics"][str(fac[fid]["naics_code"])] += e * pct / 100
    return par, unparsed


def annual_value(facts, tags, year, flow):
    """Largest value among the tags at the latest 10-K period end inside `year`; None if absent."""
    cand = []
    for tag in tags:
        for f in facts.get("us-gaap", {}).get(tag, {}).get("units", {}).get("USD", []):
            if not f["form"].startswith("10-K") or not f["end"].startswith(str(year)):
                continue
            if flow:
                days = (datetime.date.fromisoformat(f["end"]) - datetime.date.fromisoformat(f["start"])).days
                if not 350 <= days <= 380:
                    continue
            cand.append((f["end"], f["val"]))
    if not cand:
        return None
    end = max(c[0] for c in cand)
    return {"val": max(v for e, v in cand if e == end), "end": end}


def financials(facts, year):
    rev = annual_value(facts, REVENUE_TAGS, year, True)
    ast = annual_value(facts, ["Assets"], year, False)
    eq = annual_value(facts, EQUITY_TAGS, year, False)
    ltd = annual_value(facts, LTD_TAGS, year, False)
    if ltd is None:
        parts = [annual_value(facts, t, year, False) for t in LTD_PARTS]
        ltd = {"val": sum(p["val"] for p in parts if p), "end": None} if any(parts) else None
    debt = None
    if ltd is not None:
        debt = ltd["val"] + sum((annual_value(facts, [t], year, False) or {"val": 0})["val"] for t in ST_TAGS)
    vals = {"revenue": rev and rev["val"], "assets": ast and ast["val"],
            "equity": eq and eq["val"], "debt": debt}
    return vals, (ast or rev or {}).get("end")


def main():
    os.makedirs(RESULTS, exist_ok=True)
    tickers = get_json(SEC_TICKERS)
    by_name = collections.defaultdict(set)
    title = {}
    for v in tickers.values():
        by_name[norm_name(v["title"])].add(v["cik_str"])
        title[v["cik_str"]] = v["title"]
    log = {"accessed": datetime.date.today().isoformat(), "years": {}, "endpoints": {
        "epa_facility": f"{EPA}/pub_dim_facility/year/=/<year>/rows/<i>:<j>/JSON",
        "epa_emissions": f"{EPA}/pub_facts_sector_ghg_emission/year/=/<year>/rows/<i>:<j>/JSON",
        "sec_tickers": SEC_TICKERS, "sec_submissions": SEC_SUBMISSIONS.format(0).replace("0000000000", "<CIK10>"), "sec_facts": SEC_FACTS.format(0).replace("0000000000", "<CIK10>")},
        "filter": "GHGRP sector_type E only (sector_id not in 9,10,11,12,13,16,17); parents matched "
                  "by exact normalised name to SEC company_tickers titles, one CIK only"}
    epa = {}
    for y in YEARS:
        fac, tot = fetch_epa(y)
        par, unparsed = attribute_to_parents(fac, tot)
        epa[y] = par
        log["years"][y] = {"facilities": len(fac), "emitting_facilities": len(tot),
                           "direct_emissions_t": sum(tot.values()), "no_parent_t": unparsed}
        print(y, len(fac), round(sum(tot.values()) / 1e6, 1), "Mt", flush=True)
    keys = sorted({k for y in YEARS for k, p in epa[y].items() if len(by_name.get(k, ())) == 1})
    log["ambiguous_names"] = sorted(k for y in YEARS for k in epa[y] if len(by_name.get(k, ())) > 1)
    rows, reasons = [], collections.Counter()
    for n, k in enumerate(keys):
        cik = next(iter(by_name[k]))
        try:
            facts = get_json(SEC_FACTS.format(cik))["facts"]
            time.sleep(0.12)
            sic = get_json(SEC_SUBMISSIONS.format(cik)).get("sic") or ""
        except Exception as e:
            reasons[f"no companyfacts ({type(e).__name__})"] += 1
            continue
        time.sleep(0.12)
        for y in YEARS:
            p = epa[y].get(k)
            if not p:
                continue
            fin, fy_end = financials(facts, y)
            missing = [f for f, v in fin.items() if v is None]
            if missing:
                reasons[f"{y}: missing {','.join(missing)}"] += 1
                continue
            naics = max(p["naics"], key=p["naics"].get)
            rows.append({"year": y, "key": k, "name": title[cik], "cik": cik, "scope1_t": round(p["e"], 1),
                         "naics": naics, "sic": sic, "n_facilities": p["n"], "fy_end": fy_end, **fin})
        if n % 25 == 0:
            print(n, len(keys), flush=True)
    log["dropped_reasons"] = dict(reasons)
    log["matched_parents"] = len(keys)
    with open(os.path.join(RESULTS, "borrowers.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump(log, open(os.path.join(RESULTS, "fetch_log.json"), "w"), indent=1, default=str)
    print(len(rows), "borrower-years written", dict(reasons))


if __name__ == "__main__":
    main()
