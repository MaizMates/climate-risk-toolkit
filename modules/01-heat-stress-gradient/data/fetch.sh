#!/usr/bin/env bash
# The CCKP API is queried live by src/hazard.py; there is nothing to download in advance.
# This file exists to say so, rather than leaving you to wonder where the data is.
echo "No pre-download step. src/hazard.py calls the World Bank CCKP API directly."
