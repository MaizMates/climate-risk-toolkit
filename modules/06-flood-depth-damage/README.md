# 06 — Flood depth to damage: what a hazard map is worth to a risk manager

**Capacity-weighted mean expected annual damage (EAD) across 167 of Europe's largest gas and
nuclear power plants, under the published JRC infrastructure depth-damage curve: 0.81% of asset
value per year — interval [0.14%, 1.67%] from resampling which plants land in the portfolio,
[0.13%, 1.54%] combining that with curve choice. Only 7 of the 167 sites show any flood depth at
all, and resampling the portfolio moves the number roughly ten times more than switching between
the three published European sector curves does.**

## Estimand

Expected annual damage (EAD), as a fraction of asset value, for a portfolio of locations, under a
published depth-damage function: for each return period, the modelled flood depth at the site is
mapped to a damage fraction with the curve, and that fraction is integrated over the
exceedance-probability curve (1/return period) to get one annual-average number per site.

## Data, fetched by `src/flood_depth_damage.py`

- **Hazard.** JRC/Copernicus EFAS "River flood hazard maps for Europe and the Mediterranean Basin
  region", v3.1.1 (Baugh et al. 2024), nine return-period depth rasters (10, 20, 30, 40, 50, 75,
  100, 200, 500 years), 90m resolution, WGS84, `jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/`.
  Each file is ~300MB. The script never downloads a full raster: it reads the TIFF directory
  (byte order, image dimensions, tile layout, geotransform, tile offset/byte-count tables) with a
  handful of small HTTP range requests, then fetches only the compressed tiles under the
  portfolio's coordinates and decodes them (zlib, float32) in memory.
- **Depth-damage curves.** Huizinga, de Moel & Szewczyk (2017), *Global flood depth-damage
  functions*, JRC105688, doi:10.2760/16510 — the published Europe curves, as redistributed in
  CLIMADA's open-source `river_flood.py`. The script downloads that file and parses the literal
  depth-breakpoint and damage-fraction arrays out of its source text; no value is retyped.
  Infrastructure is the primary sector curve (power-generation buildings and plant), industrial
  and commercial the published alternates.
- **Portfolio.** WRI Global Power Plant Database (as in module 03), the 20 largest plants by
  capacity in each of nine countries with a documented history of damaging river floods (DEU,
  FRA, ITA, AUT, CZE, POL, NLD, GBR, ESP), excluding hydro and wave/tidal — see Limits.
- **QA layers.** JRC's own `Europe_spurious_depth_areas.tif` (cells where modelled RP10 depth
  exceeds 10m in a small channel, the dataset's documented failure mode) and
  `Europe_permanent_water_bodies.tif` (cells patched to a constant fill depth so the hazard
  rasters have no gaps along rivers) — both fetched and checked against every portfolio location.

## Method

For each of the 167 portfolio locations and each of the nine return periods, read the modelled
depth from the JRC raster; map depth to a damage fraction by linear interpolation of the
published curve; integrate the fraction over exceedance probability (trapezoidal rule, anchored
at zero damage at an annual probability of 1) to get one EAD per location; take the
capacity-weighted mean across the portfolio.

## Uncertainty

Two sources, kept separate and then combined:

- **Location resampling.** Bootstrap over the 167 locations (2.5–97.5th percentile of 1,000
  resamples), holding the primary curve fixed — the correct population to resample, since the
  estimate is a capacity-weighted mean over exactly this set of sites.
- **Curve choice.** The three published European sector curves (infrastructure, industrial,
  commercial) applied to the same, unresampled portfolio.
- **Combined.** A second bootstrap in which each resample also draws one curve for the *whole*
  portfolio in that draw — never one curve per plant independently, which is the mistake module
  05's first interval made.

Location resampling moves the headline by 1.53 points (location-only CI width); the curve choice
moves it by 0.15 points at most. With only 7 of 167 sites flooded, which large plants happen to
land in or out of the resample is what drives the interval, not the damage function.

## Sensitivity

- **Curve.** Infrastructure 0.81%, commercial 0.69%, industrial 0.66% — a 0.15-point range. The
  roadmap expected the curve to dominate; it does not here, because Europe's three building-sector
  curves are close to each other at the depths this portfolio actually sees (mostly under 4m).
- **The EAD integral's own arbitrary choice.** Whether to anchor the integral at zero damage at an
  annual probability of 1, letting floods more frequent than the rarest tabulated return period
  still contribute, or to truncate at the most frequent return period in the data: 0.81% anchored
  vs 0.18% truncated — a ~4.5x swing, the single largest lever found in this module, bigger than
  the curve choice. Extending the rarest point's damage flat below RP500 instead of stopping there
  moves the number by under 0.05 points; that end of the integral is not where the sensitivity is.
- **Portfolio size.** Taking the 10/15/20/30 largest plants per country instead of 20: 0.81%,
  0.62%, 0.81%, 1.12%. Same order of magnitude throughout, no reversal.

## Validation

JRC's own `Europe_spurious_depth_areas.tif` flags 2 of the 7 flooded sites (CTCC Soto de Ribera,
Spain, and Timelkam, Austria) as sitting where the hazard model may overpredict depth in a small
channel — the dataset's own documented failure mode, surfaced rather than hidden. One site (Eems,
Netherlands) sat on the permanent-water-bodies patch — a constant depth of exactly 1.0m at every
return period, the fill value for "always wet", not a flood signal — and was screened to zero
rather than counted as exposed; it was found by checking why one location's depth was identical
across all nine return periods when every genuinely flooded site's depth increases monotonically
with return period as expected. No independent EAD or economic-loss benchmark at comparable
public, code-fetchable granularity was found for this module; stated here rather than skipped, per
`STANDARD.md` point 6.

## Limits

- **A curve is a national average for a generic building; a specific asset is not.** The curve
  knows nothing about this plant's finished-floor elevation, on-site flood defences, or whether
  the exposed equipment sits in a basement or on a raised platform. Two sites at the same modelled
  depth can have very different real losses. This module answers "what does a published hazard
  map and a published curve imply", not "what would this specific asset actually lose" — and that
  gap is largest for exactly the handful of flooded sites that carry the entire headline number.
- **No backtest, and why not one for this module.** `STANDARD.md` requires backtesting anything
  forward-looking. The JRC hazard maps used here are a present-day statistical hazard assessment
  (LISFLOOD/LISFLOOD-FP fitted to the historical EFAS reanalysis), not a climate-change
  projection — there is no future year held out and no trend fitted by this module, so there is
  nothing to backtest. A forward-looking version would need JRC's climate-adjusted hazard maps,
  which this dataset release does not include.
- **Hydro is excluded by construction.** Hydro and wave/tidal plants sit in the river or sea by
  design, so the hazard map's modelled depth at their coordinates is the normal operating water
  level, not flood damage to a building — keeping them in made every flooded location an Austrian
  dam (see `notes.md`). This module says nothing about flood risk to hydroelectric generation.
- **One coordinate, not a footprint.** WRI gives one point per plant; a large site's actual
  equipment can span several 90m pixels at different depths, and the portfolio's 20-per-country
  cutoff is a size filter, not a flood-risk filter, so it says nothing about smaller flood-exposed
  assets below that threshold.

## Run it

```bash
python3 src/flood_depth_damage.py   # fetch JRC rasters (tiled, no full download), WRI, curves -> results/
python3 tests/test_flood_depth_damage.py
python3 src/deck.py                 # six pages
```

[`notes.md`](notes.md) has what was tried and dropped: the hydro-siting artifact, the
permanent-water-bodies patch, and why the raster reader never downloads a full file.
