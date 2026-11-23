"""Raw -> small committed tables.

- data/eu_monthly.csv: Ember's EU aggregate (Area 'EU', the 27 member states), month x source: generation and emissions
- data/members_sum.csv: sum over the 27 member states of the same series for Fossil and Total generation, to check the
  aggregate against its parts
- data/crf_annual.csv: Eurostat env_air_gge, annual MtCO2e, CRF 1.A.1.a

    python3 src/prepare.py
"""
import json
import os

import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW, DATA = os.path.join(ROOT, "data", "raw"), os.path.join(ROOT, "data")


def main():
    d = pd.read_csv(os.path.join(RAW, "ember_monthly.csv"),
                    usecols=["Area", "Date", "Electricity source", "Generation (TWh)", "Emissions (MtCO2e)", "EU member"])
    d = d.rename(columns={"Electricity source": "source", "Generation (TWh)": "gen_twh", "Emissions (MtCO2e)": "emis_mt"})
    d["Date"] = d.Date.str[:7]
    eu = d[d.Area == "EU"][["Date", "source", "gen_twh", "emis_mt"]]
    eu = eu[eu.source != "Demand"].sort_values(["Date", "source"])
    eu.to_csv(os.path.join(DATA, "eu_monthly.csv"), index=False)
    m = d[(d["EU member"] == True) & d.source.isin(["Fossil", "Total generation"])]  # noqa: E712
    ms = m.groupby(["Date", "source"]).agg(emis_mt=("emis_mt", "sum"), n_states=("Area", "nunique")).reset_index()
    ms.to_csv(os.path.join(DATA, "members_sum.csv"), index=False)
    j = json.load(open(os.path.join(RAW, "env_air_gge.json")))
    yrs = sorted(j["dimension"]["time"]["category"]["index"], key=lambda k: j["dimension"]["time"]["category"]["index"][k])
    pd.DataFrame({"year": [int(y) for y in yrs],
                  "crf_mt": [j["value"][str(j["dimension"]["time"]["category"]["index"][y])] for y in yrs]}) \
        .to_csv(os.path.join(DATA, "crf_annual.csv"), index=False)
    print("eu_monthly", len(eu), "members_sum", len(ms), "crf", len(yrs))


if __name__ == "__main__":
    main()
