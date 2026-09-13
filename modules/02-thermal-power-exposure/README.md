# Thermal power exposure screening

A reproducible screening exercise linking a small, transparent thermal-power asset sample to a heat-hazard signal. It is designed as a methodology demonstration for physical-risk and exposure integration roles, not as a loss estimate or an investment recommendation.

## Question
How does a simple asset-level exposure score change when a common heat-stress threshold is applied to plants with different cooling technologies?

## Data provenance
- Asset attributes: World Resources Institute, Global Power Plant Database (public dataset), accessed 2026-09-13. The included CSV is a clearly labelled illustrative extract for reproducibility.
- Hazard signal: World Bank Climate Change Knowledge Portal, CMIP6 indicator methodology, accessed 2026-09-13. This module uses a transparent scenario-independent screening signal rather than claiming a site-specific forecast.

## Method
The script computes a heat exposure score = annual hot-day signal × capacity factor × cooling vulnerability weight. The score is a screening index; it is not expected loss, a regulatory capital number or a climate projection.

Run:
```bash
python analysis.py
python -m unittest discover -s tests
```

Limitations: the sample is small, the hazard signal is illustrative, no geocoding or asset-level downscaling is performed, and cooling technology is self-reported. Results should be replaced with the complete public dataset before any investment use.
