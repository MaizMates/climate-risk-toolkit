"""Pillar 3 ESG template completeness index across the banks in data/sources.csv -> results/.

Run after fetch.py, extract.py and synth.py:  python3 src/index.py
"""
import csv
import json
import os
import re
from collections import Counter

import numpy as np

import disclosure as D
from extract import extract
from fetch import DATA, RESULTS

KW0 = dict(exclude_years=True, zero_is_blank=False, exclude_row_codes=False)
SEED, B = 20261016, 4000


def bank_index(status, templates=D.MANDATORY, omit="zero", presence_only=False, fill_adj=None):
    """Mean over templates of the fill rate (0 when not published). omit='drop' removes templates the
    bank states it omits from the denominator instead of scoring them 0."""
    vals = []
    for t in templates:
        s = status[t]
        if omit == "drop" and s["status"] == "omitted_stated":
            continue
        if s["status"] != "published":
            vals.append(0.0)
        else:
            vals.append(1.0 if presence_only else (fill_adj(s["fill"]) if fill_adj else s["fill"]))
    return float(np.mean(vals)) if vals else float("nan")


def in_scope(status):
    return any(status[t]["status"] == "published" for t in D.TEMPLATES)


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


def detect_year(pages, status):
    c = Counter()
    for t in D.TEMPLATES:
        for p in status[t]["pages"]:
            c.update(re.findall(r"\b(202[3-5])\b", pages[p - 1], re.I))
    return int(c.most_common(1)[0][0]) if c else None


def toc_check(pages, status):
    """Compare each template's first located page with the page the bank's own contents list prints."""
    printed = {}
    for text in pages:
        if len(D.heading_hits(text, strict=False)) < 4:
            continue
        for line in D.normalise(text).split("\n"):
            hit = D.heading_hits(line, strict=False)
            m = re.search(r"(\d{1,3})\s*$", line.strip())
            if len(hit) == 1 and m:
                printed.setdefault(next(iter(hit)), int(m.group(1)))
    pairs = [(printed[t], min(status[t]["pages"])) for t in printed if status[t]["pages"]]
    if len(pairs) < 3:
        return None
    off = int(np.median([a - b for a, b in pairs]))
    agree = sum(abs(a - b - off) <= 1 for a, b in pairs)
    return {"matched": len(pairs), "agree": agree, "offset": off}


def main():
    cal = json.load(open(os.path.join(RESULTS, "parser_test.json")))["calibration"]
    a, b_, resid = cal["intercept"], cal["slope"], np.array(cal["residuals"])
    banks, pages = [], {}
    for r in csv.DictReader(open(os.path.join(DATA, "sources.csv"))):
        banks.append(r["bank"])
        pages[r["bank"]] = extract(r["bank"])

    base = {k: D.bank_status(pages[k], **KW0) for k in banks}
    scope = [k for k in banks if in_scope(base[k])]
    out_scope = [k for k in banks if k not in scope]
    year = {k: detect_year(pages[k], base[k]) for k in banks}
    idx = {k: bank_index(base[k]) for k in scope}
    pres = {k: bank_index(base[k], presence_only=True) for k in scope}

    # CSV: every bank x template
    with open(os.path.join(RESULTS, "template_status.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bank", "template", "status", "pages", "numeric_cells", "placeholder_cells", "fill"])
        for k in banks:
            for t in D.TEMPLATES:
                s = base[k][t]
                w.writerow([k, t, s["status"], " ".join(map(str, s["pages"])), s["numeric"], s["placeholder"], round(s["fill"], 4)])

    # headline interval: resample banks, one parser-error draw per bank shared by its templates
    rng = np.random.default_rng(SEED)
    adj = lambda e: (lambda x: min(1.0, max(0.0, (x - a - e) / b_)))
    n = len(scope)
    both, banks_only, parser_only = [], [], []
    for _ in range(B):
        draw = rng.integers(0, n, n)
        es = rng.choice(resid, n)
        both.append(np.mean([bank_index(base[scope[j]], fill_adj=adj(es[i])) for i, j in enumerate(draw)]))
        banks_only.append(np.mean([idx[scope[j]] for j in draw]))
        parser_only.append(np.mean([bank_index(base[scope[i]], fill_adj=adj(es[i])) for i in range(n)]))
    pct = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    corrected = float(np.mean([bank_index(base[k], fill_adj=adj(0.0)) for k in scope]))

    per_bank = {}
    for k in scope:
        draws = [bank_index(base[k], fill_adj=adj(e)) for e in rng.choice(resid, 2000)]
        s = base[k]
        pub = [t for t in D.MANDATORY if s[t]["status"] == "published"]
        per_bank[k] = {"index": idx[k], "interval_parser": pct(draws), "presence": pres[k],
                       "published": len(pub), "mean_fill_published": float(np.mean([s[t]["fill"] for t in pub])) if pub else None,
                       "period_detected": year[k], "period_listed": next(r["period"] for r in csv.DictReader(open(os.path.join(DATA, "sources.csv"))) if r["bank"] == k),
                       "not_published": [t for t in D.MANDATORY if s[t]["status"] != "published"]}

    per_template = {}
    for t in D.TEMPLATES:
        pub = [k for k in scope if base[k][t]["status"] == "published"]
        per_template[t] = {"published": len(pub), "of": len(scope),
                           "stated_omitted": sum(base[k][t]["status"] == "omitted_stated" for k in scope),
                           "not_found": sum(base[k][t]["status"] == "not_found" for k in scope),
                           "mean_fill": float(np.mean([base[k][t]["fill"] for k in pub])) if pub else None}

    # sweeps
    base_vec = np.array([idx[k] for k in scope])
    sweeps = {}

    def add(name, fn, banks_=None, **kw):
        sc = banks_ or scope
        st = {k: (D.bank_status(pages[k], **{**KW0, **kw.get("dkw", {})}) if kw.get("dkw") or kw.get("loc") else base[k]) for k in sc} if not kw.get("loc") else \
             {k: D.bank_status(pages[k], **{**KW0, **kw.get("dkw", {})}, **kw["loc"]) for k in sc}
        v = {k: bank_index(st[k], **kw.get("ix", {})) for k in sc}
        common = [k for k in sc if k in idx]
        rho = spearman([idx[k] for k in common], [v[k] for k in common]) if len(common) > 2 else None
        sweeps[name] = {"mean": float(np.nanmean(list(v.values()))), "n_banks": len(sc), "spearman_vs_baseline": rho}

    add("baseline", None)
    add("T9 (BTAR) included in the template set", None, ix=dict(templates=D.TEMPLATES))
    add("stated omissions dropped from denominator", None, ix=dict(omit="drop"))
    add("presence only (fill ignored)", None, ix=dict(presence_only=True))
    add("zero counted as blank", None, dkw=dict(zero_is_blank=True))
    add("years not excluded from numeric cells", None, dkw=dict(exclude_years=False))
    add("leading row codes excluded", None, dkw=dict(exclude_row_codes=True))
    add("fill counted on lenient rows (long labels kept)", None, dkw=dict(strict=False))
    add("table page needs 10 cells, template 12", None, loc=dict(min_page=10, min_tpl=12))
    add("table page needs 3 cells, template 4", None, loc=dict(min_page=3, min_tpl=4))
    add("run caps halved", None, loc=dict(run_scale=0.5))
    add("run caps doubled", None, loc=dict(run_scale=2.0))
    fy = [k for k in scope if year[k] == 2024]
    add("only documents detected as FY2024", None, banks_=fy)
    add("out-of-scope banks scored (zeros) as well", None, banks_=banks)
    sweeps["out-of-scope banks scored (zeros) as well"]["note"] = "banks whose document holds no ESG template are scored 0"
    means = {k: v["mean"] for k, v in sweeps.items()}
    rhos = {k: v["spearman_vs_baseline"] for k, v in sweeps.items() if v["spearman_vs_baseline"] is not None}

    # validation: the bank's own contents list vs located pages
    toc = {k: toc_check(pages[k], base[k]) for k in scope}
    toc = {k: v for k, v in toc.items() if v}

    res = {
        "estimand": "mean over banks of the bank index; bank index = mean over the nine mandatory ESG templates (1-8, 10) of the fill rate (0 if not published)",
        "n_banks_listed": len(banks), "n_banks_scored": len(scope), "out_of_scope": out_scope,
        "headline": {"mean_index": float(np.mean(base_vec)), "interval": pct(both),
                     "interval_banks_only": pct(banks_only), "interval_parser_only": pct(parser_only),
                     "parser_corrected_mean": corrected,
                     "presence_mean": float(np.mean(list(pres.values()))),
                     "min_bank": min(idx, key=idx.get), "max_bank": max(idx, key=idx.get)},
        "per_bank": per_bank, "status": {k: {t: {x: base[k][t][x] for x in ("status", "fill")} for t in D.TEMPLATES} for k in banks}, "per_template": per_template, "sweeps": sweeps,
        "sweep_range": {"min": min(means.values()), "max": max(means.values()),
                        "min_spearman": min(rhos.values())},
        "toc_validation": toc,
        "toc_totals": {"matched": sum(v["matched"] for v in toc.values()), "agree": sum(v["agree"] for v in toc.values())},
        "parser": {k: cal[k] for k in ("intercept", "slope", "resid_sd", "mean_error", "mean_abs_error", "by_style")},
        "bootstrap": {"B": B, "seed": SEED},
    }
    json.dump(res, open(os.path.join(RESULTS, "index.json"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("headline", "sweep_range", "toc_totals", "out_of_scope")}, indent=1))
    for k, v in sweeps.items():
        print(f"{k:55s} {v['mean']:.3f} rho={v['spearman_vs_baseline']}")
    for k, v in per_bank.items():
        print(f"{k:18s} {v['index']:.3f} {v['interval_parser']} pub={v['published']} yr={v['period_detected']}")
    for t, v in per_template.items():
        print(t, v)
    print(toc)


if __name__ == "__main__":
    main()
