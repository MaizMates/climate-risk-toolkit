#!/usr/bin/env python3
"""Climate Risk Vacancy Radar - board crawler.

Fetches every employer in ledger.json, filters titles, diffs against seen state,
and prints ONLY new/changed postings. Payloads never leave this process, which is
the point: the agent that runs this reads tens of lines, not megabytes.

stdlib only. Usage:
    python3 monitor.py --ledger ledger.json --seen state/seen.json [--only id,id] [--write-seen]
"""
import argparse, concurrent.futures as cf, gzip, hashlib, json, re, sys, urllib.error, urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122 Safari/537.36"
TIMEOUT = 30


def _ssl_ctx():
    """Real CA verification. Some python builds ship without a trust store wired in;
    fall back to certifi or the system bundle rather than disabling verification."""
    import ssl
    for cafile in _ca_candidates():
        try:
            return ssl.create_default_context(cafile=cafile)
        except Exception:
            continue
    return ssl.create_default_context()


def _ca_candidates():
    try:
        import certifi
        yield certifi.where()
    except ImportError:
        pass
    for p in ("/etc/ssl/cert.pem", "/usr/local/etc/openssl@3/cert.pem",
              "/etc/ssl/certs/ca-certificates.crt"):
        if Path(p).exists():
            yield p
    yield None


CTX = None

# --- lexical filters -------------------------------------------------------
# A: climate and transition. B: physical risk and geospatial. Both always apply.
# C: quant-adjacent - ONLY at employers with a named climate practice. Applied
# globally it promotes ~12% of a board and stops being a filter (the Capco case).
LIST_A = r"climate|sustainab|esg|carbon|transition|nature|decarbon|environment|green"
LIST_B = (r"catastroph|\bcat\b|peril|hazard|flood|wildfire|windstorm|storm|drought|hydrolog|"
          r"meteorolog|geospatial|\bgis\b|remote sensing|satellite|natcat|nat cat|exposure|"
          r"resilien|impact forecasting|physical risk|extreme")
# 'actuar' was here and produced ~40 useless rows on Marsh alone: actuarial work wants
# IFoA/SOA exams Marco does not have and is not pursuing, so it fails gate 6 every time.
LIST_C = (r"quant|analytics|data scien|data analyst|data engineer|risk model|scenario|"
          r"stress test|statistic|modell?ing|portfolio analytics")
RE_A, RE_B, RE_C = (re.compile(x, re.I) for x in (LIST_A, LIST_B, LIST_C))

# Titles that fail gate 2 on sight. Interns/graduates/trainees are ADMITTED (Marco's
# call, 2026-09-09): he wants the EY Zurich/Geneva quant internships in scope.
RE_SENIOR = re.compile(r"\b(senior|sr\.?|lead|principal|manager|director|vp|vice president|head of|staff|chief)\b", re.I)

# Gate 4 is deterministic for these: local-hire hubs and markets with no right to work and
# no stated sponsorship. Rejecting them here keeps them out of the agent's context entirely.
# UK is NOT here: it needs the sponsor register check, which is a judgement, not a rule.
RE_GEO_NO = re.compile(
    r"\b(united states|usa|canada|mexico|brazil|brasil|colombia|argentina|chile|peru|"
    r"india|bengaluru|bangalore|gurugram|mumbai|hyderabad|pune|noida|"
    r"philippines|taguig|manila|makati|malaysia|kuala lumpur|singapore|"
    r"china|xiamen|shanghai|beijing|taiwan|taipei|japan|tokyo|korea|"
    r"australia|new zealand|south africa|egypt|cairo|nigeria|kenya|"
    r"t\u00fcrkiye|turkey|istanbul|uae|dubai|saudi|qatar|israel)\b", re.I)


def get(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "*/*"}
    if headers:
        h.update(headers)
    global CTX
    if CTX is None:
        CTX = _ssl_ctx()
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")


def jget(url, data=None, headers=None):
    return json.loads(get(url, data, headers))


def norm(emp, jid, title, loc, url, posted=""):
    return {"emp": emp["id"], "org": emp["name"], "id": f'{emp["id"]}:{jid}',
            "title": (title or "").strip(), "loc": (loc or "").strip(),
            "url": url or "", "posted": posted or ""}


# --- adapters --------------------------------------------------------------
def a_ashby(e):
    d = jget(f'https://api.ashbyhq.com/posting-api/job-board/{e["slug"]}')
    return [norm(e, j["id"], j.get("title"),
                 j.get("location") or "", j.get("jobUrl") or "", j.get("publishedAt", "")[:10])
            for j in d.get("jobs", []) if j.get("isListed", True)]


def a_greenhouse(e):
    d = jget(f'https://boards-api.greenhouse.io/v1/boards/{e["slug"]}/jobs')
    return [norm(e, j["id"], j.get("title"),
                 (j.get("location") or {}).get("name", ""), j.get("absolute_url", ""),
                 (j.get("updated_at") or "")[:10]) for j in d.get("jobs", [])]


def a_lever(e):
    d = jget(f'https://api.lever.co/v0/postings/{e["slug"]}?mode=json')
    return [norm(e, j["id"], j.get("text"),
                 (j.get("categories") or {}).get("location", ""), j.get("hostedUrl", ""))
            for j in d]


def a_phenom(e):
    """Server-rendered. phApp.ddo.eagerLoadRefineSearch.{totalHits,data.jobs}.
    10 per page, from= steps by 10. Full enumeration: HTTP is free, context is not."""
    host, out, seen, frm, total = e["host"], [], set(), 0, None
    pat = re.compile(r"phApp\.ddo\s*=\s*(\{.*?\})\s*;\s*(?:phApp|window|var|</script>)", re.S)
    while frm < (total if total is not None else 10) and frm < 3000:
        h = get(f"https://{host}/global/en/search-results?from={frm}&s=1")
        m = pat.search(h)
        if not m:
            break
        rs = (json.loads(m.group(1)).get("eagerLoadRefineSearch") or {})
        if total is None:
            total = int(rs.get("totalHits") or 0)
        jobs = (rs.get("data") or {}).get("jobs") or []
        if not jobs:
            break
        for j in jobs:
            jid = str(j.get("jobId") or j.get("reqId") or "")
            if jid in seen:
                continue
            seen.add(jid)
            out.append(norm(e, jid, j.get("title"),
                            j.get("cityStateCountry") or j.get("location") or "",
                            j.get("applyUrl") or "", (j.get("postedDate") or "")[:10]))
        frm += 10
    return out


def a_smartrecruiters(e):
    out, off = [], 0
    while off < 3000:
        d = jget(f'https://api.smartrecruiters.com/v1/companies/{e["slug"]}/postings?limit=100&offset={off}')
        c = d.get("content") or []
        if not c:
            break
        for j in c:
            loc = j.get("location") or {}
            out.append(norm(e, j["id"], j.get("name"),
                            f'{loc.get("city","")} {loc.get("country","")}'.strip(),
                            f'https://jobs.smartrecruiters.com/{e["slug"]}/{j["id"]}',
                            (j.get("releasedDate") or "")[:10]))
        off += 100
        if off >= int(d.get("totalFound") or 0):
            break
    return out


def a_workable(e):
    d = jget(f'https://apply.workable.com/api/v1/widget/accounts/{e["slug"]}?details=true')
    seen, out = set(), []
    for j in d.get("jobs", []):
        sc = j.get("shortcode")           # widget duplicates one vacancy per city
        if sc in seen:
            continue
        seen.add(sc)
        out.append(norm(e, sc, j.get("title"), j.get("location", ""), j.get("url", "")))
    return out


def a_recruitee(e):
    d = jget(f'https://{e["slug"]}.recruitee.com/api/offers/')
    return [norm(e, j["id"], j.get("title"),
                 f'{j.get("city","")} {j.get("country","")}'.strip(), j.get("careers_url", ""))
            for j in d.get("offers", [])]


def a_workday(e):
    out, off, total = [], 0, None
    url = f'https://{e["host"]}/wday/cxs/{e["tenant"]}/{e["site"]}/jobs'
    while off < 3000:
        d = jget(url, data=json.dumps({"appliedFacets": {}, "limit": 20, "offset": off,
                                       "searchText": ""}).encode(),
                 headers={"Content-Type": "application/json"})
        if d.get("errorCode"):        # an errorCode invalidates the count, always
            raise RuntimeError(f'workday {d["errorCode"]}')
        posts = d.get("jobPostings") or []
        if not posts:
            break
        if total is None:
            total = int(d.get("total") or 0)
        for j in posts:
            p = j.get("externalPath", "")
            out.append(norm(e, p, j.get("title"), j.get("locationsText", ""),
                            f'https://{e["host"]}{e["path"]}{p}' if e.get("path") else p))
        off += 20
    return out


ADAPTERS = {"ashby": a_ashby, "greenhouse": a_greenhouse, "lever": a_lever, "phenom": a_phenom,
            "smartrecruiters": a_smartrecruiters, "workable": a_workable,
            "recruitee": a_recruitee, "workday": a_workday}


# --- filter + diff ---------------------------------------------------------
def promote(job, climate_practice):
    """Return the list that promoted this title, or None."""
    t = job["title"]
    if RE_A.search(t):
        return "A"
    if RE_B.search(t):
        return "B"
    if climate_practice and RE_C.search(t):
        return "C"
    return None


def crawl(e):
    fn = ADAPTERS.get(e.get("ats"))
    if not fn:
        return e["id"], None, f'no adapter for ats={e.get("ats")}'
    try:
        return e["id"], fn(e), None
    except Exception as ex:
        return e["id"], None, f"{type(ex).__name__}: {ex}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="ledger.json")
    ap.add_argument("--seen", default="state/seen.json")
    ap.add_argument("--only", default="")
    ap.add_argument("--write-seen", action="store_true")
    ap.add_argument("--all", action="store_true", help="print every promoted title, not just new")
    a = ap.parse_args()

    emps = [e for e in json.loads(Path(a.ledger).read_text()) if e.get("status") != "skip"]
    if a.only:
        want = set(a.only.split(","))
        emps = [e for e in emps if e["id"] in want]

    seen_p = Path(a.seen)
    seen = json.loads(seen_p.read_text()) if seen_p.exists() else {}

    counts, errors, hits = {}, {}, []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for eid, jobs, err in ex.map(crawl, emps):
            e = next(x for x in emps if x["id"] == eid)
            if err:
                errors[eid] = err
                counts[eid] = {"total": None, "status": "error"}
                continue
            promoted = []
            for j in jobs:
                lst = promote(j, e.get("climate_practice", False))
                if not lst:
                    continue
                if RE_GEO_NO.search(j["loc"]):
                    continue
                j["list"] = lst
                j["senior_title"] = bool(RE_SENIOR.search(j["title"]))
                j["h"] = hashlib.sha1(f'{j["id"]}|{j["title"]}|{j["loc"]}'.encode()).hexdigest()[:12]
                promoted.append(j)
            fresh = [j for j in promoted if seen.get(j["id"]) != j["h"]]
            counts[eid] = {"total": len(jobs), "promoted": len(promoted), "new": len(fresh),
                           "status": "green"}
            hits.extend(promoted if a.all else fresh)
            for j in promoted:
                seen[j["id"]] = j["h"]

    if a.write_seen:
        seen_p.parent.mkdir(parents=True, exist_ok=True)
        seen_p.write_text(json.dumps(seen, indent=0, sort_keys=True))

    json.dump({"counts": counts, "errors": errors,
               "hits": sorted(hits, key=lambda j: (j["emp"], j["title"]))},
              sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
