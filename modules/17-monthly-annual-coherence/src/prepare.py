"""Raw Eurostat JSON-stat and Ember CSV -> the tables the analysis reads (all under 1 MB).

data/pairs.csv           one row per country, flow and calendar year with all twelve monthly figures
                         present and an annual figure: monthly_gwh (their sum), annual_gwh
data/ember_netimports.csv  Ember yearly net imports, GWh, EU27 (validation only)
data/quality.json        what was dropped and why

Flows (monthly code in nrg_cb_em or nrg_cb_pem -> annual code in nrg_cb_e):
IMP -> IMP, EXP -> EXP, DL -> DL, PS: TI_EHG_EPS -> TI_EHG_EPS_PURE + TI_EHG_EPS_MIX (the annual table
splits pumped storage by plant type), NEP: nrg_cb_pem TOTAL -> NEP (extension, not in nrg_cb_em).
alt_annual_gwh holds the annual LOSS next to DL, used only to test a definitional explanation.

    python3 src/prepare.py
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")
EU27 = "BE BG CZ DK DE EE IE EL ES FR HR IT CY LV LT LU HU MT NL AT PL PT RO SI SK FI SE".split()
ISO3 = dict(zip(EU27, "BEL BGR CZE DNK DEU EST IRL GRC ESP FRA HRV ITA CYP LVA LTU LUX HUN MLT NLD AUT POL PRT ROU SVN SVK FIN SWE".split()))
AGGREGATES = ["EU27_2020", "EA21"]


def tidy(path):
    d = json.load(open(path))
    ids, sz = d["id"], d["size"]
    cats = [sorted(d["dimension"][k]["category"]["index"], key=d["dimension"][k]["category"]["index"].get) for k in ids]
    st = d.get("status", {})
    rows = []
    for pos, v in d["value"].items():
        p, idx = int(pos), []
        for s in reversed(sz):
            idx.append(p % s)
            p //= s
        rows.append({k: c[i] for k, c, i in zip(ids, cats, idx[::-1])} | {"value": v, "flag": st.get(pos, "")})
    return pd.DataFrame(rows)


def flagstr(s):
    c = s[s != ""].value_counts()
    return " ".join(f"{k}:{v}" for k, v in sorted(c.items()))


def monthly_sums(df, flow_col):
    df = df[~df.geo.isin(AGGREGATES)].copy()
    df["year"] = df.time.str[:4].astype(int)
    g = df.groupby(["geo", flow_col, "year"])
    out = g.agg(monthly_gwh=("value", "sum"), n_months=("value", "size")).reset_index()
    out["m_flags"] = g.flag.apply(flagstr).values
    return out.rename(columns={flow_col: "flow"})


def main():
    em, pem, ann = (tidy(os.path.join(RAW, f"{n}.json")) for n in ("nrg_cb_em", "nrg_cb_pem", "nrg_cb_e"))
    pem["nrg_bal"] = "NEP"
    m = pd.concat([monthly_sums(em[em.nrg_bal.isin(["IMP", "EXP", "DL", "TI_EHG_EPS"])], "nrg_bal"), monthly_sums(pem, "nrg_bal")])
    m["flow"] = m.flow.replace({"TI_EHG_EPS": "PS"})
    q = {"monthly_country_flow_years": int(len(m)), "dropped_incomplete_year": int((m.n_months != 12).sum())}
    m = m[m.n_months == 12].drop(columns="n_months")

    ann = ann[~ann.geo.isin(AGGREGATES)].copy()
    ann["year"] = ann.time.astype(int)
    a = ann[ann.nrg_bal.isin(["IMP", "EXP", "DL", "NEP"])][["geo", "nrg_bal", "year", "value", "flag"]].rename(columns={"nrg_bal": "flow", "value": "annual_gwh", "flag": "a_flag"})
    ps = ann[ann.nrg_bal.isin(["TI_EHG_EPS_PURE", "TI_EHG_EPS_MIX"])]
    ps = ps.groupby(["geo", "year"]).agg(annual_gwh=("value", lambda x: x.sum(min_count=1)), a_flag=("flag", lambda x: "".join(sorted(set(x) - {""})))).reset_index()
    ps["flow"] = "PS"
    a = pd.concat([a, ps]).dropna(subset=["annual_gwh"])
    loss = ann[ann.nrg_bal == "LOSS"][["geo", "year", "value"]].rename(columns={"value": "alt_annual_gwh"})
    loss["flow"] = "DL"

    p = m.merge(a, on=["geo", "flow", "year"], how="inner").merge(loss, on=["geo", "flow", "year"], how="left")
    p.insert(1, "eu27", p.geo.isin(EU27).astype(int))
    q["pairs"] = int(len(p))
    q["pairs_by_flow"] = p.flow.value_counts().to_dict()
    q["monthly_without_annual"] = int(len(m) - len(m.merge(a, on=["geo", "flow", "year"])))
    q["geos"] = sorted(p.geo.unique())
    q["years"] = [int(p.year.min()), int(p.year.max())]
    q["monthly_flag_counts_months"] = {k: int(v) for k, v in pd.concat([em, pem]).flag.value_counts().items() if k}
    p.sort_values(["flow", "geo", "year"]).round(3).to_csv(os.path.join(DATA, "pairs.csv"), index=False)

    y = pd.read_csv(os.path.join(RAW, "ember_yearly.csv"))
    y = y[(y["Electricity source"] == "Net imports") & (y["Area type"] == "Country or economy")]
    inv = {v: k for k, v in ISO3.items()}
    y = y[y["ISO 3 code"].isin(inv)].assign(geo=lambda d: d["ISO 3 code"].map(inv))
    y["ember_net_imports_gwh"] = (y["Generation (TWh)"] * 1000).round(1)
    y[["geo", "Year", "ember_net_imports_gwh"]].rename(columns={"Year": "year"}).sort_values(["geo", "year"]).to_csv(os.path.join(DATA, "ember_netimports.csv"), index=False)
    q["ember_rows"] = int(len(y))
    json.dump(q, open(os.path.join(DATA, "quality.json"), "w"), indent=1)
    print(q["pairs"], "pairs", q["pairs_by_flow"], "dropped", q["dropped_incomplete_year"])


if __name__ == "__main__":
    main()
