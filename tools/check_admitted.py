#!/usr/bin/env python3
"""Every role written down as AMMESSO must actually be in the dashboard.

This is the check that was missing. On 10 September be-TSE and Zero Carbon Shipping were
adjudicated, with the deciding sentence, and never placed: the run's own rule only required
a written verdict, not that the verdict reached the page. Marco found them himself.

    python3 tools/check_admitted.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERDICTS = os.path.join(ROOT, "docs", "VERDICTS-marco-links.md")
DASH = os.path.join(ROOT, "dashboard", "climate-risk-vacancy-radar.live.html")

# Un ruolo ammesso e poi escluso dal perimetro non e' un buco: e' una decisione, e sta qui
# con la ragione, cosi' il check non la riapre a ogni giro.
RITIRATI = {
    "EY Zurigo": "quant, non climate: fuori dal perimetro del 10/09",
    "Oliver Wyman": "data & analytics, non climate: stessa ragione di Capco, Baringa e LSEG",
    "ABB": "reporting e sostenibilita' corporate, non rischio",
    "UNDP": "cancello eleggibilita': aperti solo a personale interno",
}


def admitted(text):
    for line in text.splitlines():
        if not line.startswith("|") or "AMMESSO" not in line:
            continue
        m = re.search(r"\*\*(.+?)\*\*", line)
        if m:
            yield m.group(1)


def main():
    verdicts = open(VERDICTS, encoding="utf-8").read()
    dash = open(DASH, encoding="utf-8").read()
    missing = []
    for role in admitted(verdicts):
        skip = next((r for k, r in RITIRATI.items() if k.lower() in role.lower()), None)
        if skip:
            print("ritirato  %-60s %s" % (role[:60], skip))
            continue
        # il nome del datore e' la prima parte prima della virgola
        org = role.split(",")[0].strip()
        if org.lower() in dash.lower():
            print("in lista  %s" % role[:70])
        else:
            missing.append(role)
            print("MANCANTE  %s" % role[:70])
    if missing:
        print("\n%d ruoli ammessi non sono in dashboard." % len(missing))
        return 1
    print("\nOgni ruolo ammesso e' in dashboard o ha una ragione scritta per non esserci.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
