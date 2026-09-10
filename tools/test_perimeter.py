#!/usr/bin/env python3
"""The perimeter regression. Run it after any change to promote() or to the lexicons.

Every title in MUST_DROP was shown to me and rejected: they are data roles with no climate
object. Every title in MUST_KEEP is a role I would actually apply to. Both lists are checked
with climate_practice=True, which is the hardest case, because that flag is exactly what used
to wave the data roles through.

    python3 test_perimeter.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("mon", os.path.join(HERE, "monitor.py"))
mon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mon)

MUST_DROP = [
    "Data Engineer",                              # Capco Milan
    "Data Engineering Consultant",                # Baringa Sofia
    "Management Consultant - Data Engineering",   # Baringa Sofia
    "Fixed Income Data Analyst",                  # LSEG Gdynia
    "Junior Data Scientist",                      # LSEG Gdynia
    "Data Analyst with German language",          # Capco
    "Data Modelling Consultant (Insurance)",      # Capco
    "Quantitative Support Engineer",              # LSEG
    "AI Data Engineer",                           # LSEG
]

MUST_KEEP = [
    "Climate Data Specialist",                                    # MSCI Sofia
    "Climate and Energy Analyst [Open to Tier 1 applicants]",     # UNDP Rome
    "Programme Analyst- Climate and Sustainable Energy Finance",  # UNDP Bonn
    "Hydrological Modelling and GIS Analyst",                     # Aon Prague
    "Statistical Modeler in Wildfire Team",                       # Aon Prague
    "Carbon Markets Analyst",                                     # UNDP
    "Climate Consultant (m/w/d)",                                 # ISS ESG
    "Sustainability Analyst",                                     # Quantexa
]


def main():
    fails = []
    for title in MUST_DROP:
        if mon.promote({"title": title}, True) is not None:
            fails.append(("should have dropped", title))
    for title in MUST_KEEP:
        if mon.promote({"title": title}, True) is None:
            fails.append(("should have kept", title))
    for what, title in fails:
        print(f"FAIL  {what}: {title}")
    print(f"{len(MUST_DROP) + len(MUST_KEEP) - len(fails)} of "
          f"{len(MUST_DROP) + len(MUST_KEEP)} pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
