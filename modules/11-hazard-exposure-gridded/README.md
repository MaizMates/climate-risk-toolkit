# 11: Hazard exposure at grid-cell resolution

**Joined to the 0.25 degree cell each plant sits in, 17.7% [13.1%, 22.5%] of 259,319 MW of thermal
capacity in eleven countries is exposed to a rise of more than two days a year above a 35 C heat
index by 2040-2059 (SSP2-4.5). Joined to its country's value, as in module 03, the same plants give
42.9% [36.6%, 49.3%]. The gap is -25.2 points [-31.4, -19.4]: the country value gave the higher
exposure in every variant I swept.**

An independent project on public data. Nothing here comes from, or is affiliated with, any employer.

## Estimand

The share of thermal generating capacity, in MW, across the eleven countries of modules 01 and 03,
held by plants whose own 0.25 degree grid cell shows the annual number of days at or above a 35 C
heat index rising by more than *k* days from 1995-2014 to 2040-2059 under SSP2-4.5 (CMIP6 ensemble
median), with *k* = 2 as the reference; and the difference between that share and the one obtained
by giving each plant its country's value. If I knew them exactly, the difference would be what
module 03's country resolution cost, in points of capacity share.

## Data

All fetched by [`src/fetch.py`](src/fetch.py), listed in [`data/sources.csv`](data/sources.csv);
[`results/fetch_log.json`](results/fetch_log.json) records URL, access date (2026-10-19), HTTP
status, size and SHA-256 of each file. The raw files are not committed (`data/raw/` is ignored).

- **Plants.** WRI Global Power Plant Database, 672 thermal plants (coal, oil, petcoke, gas) in
  ITA, ESP, FRA, DEU, NLD, PRT, GRC, AUT, BEL, IRL, POL after the coordinate check below.
- **Hazard.** World Bank CCKP, CMIP6 0.25 degree annual climatology of `hd35`, ensemble median, p10
  and p90, historical 1995-2014 and SSP2-4.5 2040-2059, plus SSP3-7.0 for a sweep. They sit in the
  public S3 bucket `wbg-cckp` as HDF5 files. The CCKP API that modules 01 and 03 used answers
  for countries and for subnational units (identifiers such as `ESP.2292716`), and returned an empty
  answer to every coordinate form I tried, which is why the build reads the files.
- **Borders.** Natural Earth 1:50m country polygons, for the coordinate check, the land mask and the
  grid validation.
- **Country values.** The CCKP API, the same collections module 01 queries, for the comparator and
  for the validation. Module 03's 43.2% is reproduced on all 676 plants (`reproduces_module03` in
  `results/gridded.json`) before the bad-coordinate plants are removed.

netCDF4 and h5py are outside what a module may use, so [`src/h5lite.py`](src/h5lite.py) reads the
one HDF5 layout these files have and refuses any other.

## Method

[`src/gridded.py`](src/gridded.py). A plant's hazard is the change (SSP2-4.5 minus historical) in the
cell containing it. A plant is exposed if that change is strictly more than *k* days. Exposed share
is capacity-weighted. The country comparator uses the same plants and the same threshold with the CCKP
country value.

Coordinate check. WRI carries wrong coordinates. A plant more than 10 km outside its own country's
European polygon is repaired if swapping latitude and longitude puts it inside (one plant, 15 MW,
Garona Verda) and dropped from both measures otherwise: four plants, 1,306 MW, 0.50% of capacity.
Escombreras (1,199 MW) has a latitude of 7.57. Ceuta and Melilla are exclaves that lie outside the
mainland polygon. Nothing is corrected by hand.

## Uncertainty

Plants resampled with replacement, 2,000 times, in groups of sites: units that share a coordinate
share a cell and a hazard value, so they are drawn together (617 sites). The grid share, the
country share and their difference are computed on each resample together, so the interval on the
gap is paired. Resampling plants one by one gives a gap interval [-31.4, -19.4], the same to
the first decimal.

The hazard error is a different thing: it is common to all plants, so it is not drawn per plant.
I move every plant together to the ensemble p10 and p90 layers. The grid share is 10.5% and 46.6%
there, the country share 21.1% and 60.8%, and the gap -10.7 points [-16.1, -5.1] and -14.2
[-22.0, -6.0]. The p10 and p90 layers are separate ensemble layers, not percentiles of the change,
so this brackets the hazard error approximately and is not a 95% interval.

## Backtest

Nothing in this module is fitted to a time series. The projection is CCKP's CMIP6 ensemble,
consumed unchanged; mid-century has not happened, so there is no realised year to test it against.
The validation below checks the read of the files, not the climate.

## Validation

The grid, averaged with latitude weights over each country's polygon, reproduces the CCKP country
API for three layers in eleven countries; the largest absolute difference is 0.15 days. That checks
the HDF5 reader, the grid indexing and the polygon mask together. It does not check the model: the
same ensemble is behind both. No second, independent gridded source for the same variable is
available to me.

## Sensitivity

Reference *k* = 2, one choice moved at a time, in `results/gridded.json`:

| Choice moved | Grid share | Gap to country |
|---|---|---|
| matching radius 0 to 100 km, all cells or land only | 17.7% to 32.5% | -25.2 to -10.4 |
| fuel definition (gas, biomass in or out) | 10.9% to 17.7% | -25.2 to -16.9 |
| scenario, SSP2-4.5 against SSP3-7.0 | 17.7% to 18.4% | -25.2 to -24.5 |
| *k* from 1 to 3 | 32.6% to 14.5% | -15.3 to -28.4 |

The threshold moves the answer most (18.0 points between *k* = 1 and 3), then the radius (14.8),
then the fuel definition (6.7), then the scenario (0.7). At country resolution module 03 found the
fuel definition larger than the step from *k* = 1 to 3; at grid resolution it is smaller, because a
country value moves in jumps when a country crosses *k*. The gap is negative in every variant and
at every *k*, with the plant-resampling interval excluding zero at every *k* from 0 to 8. The
baseline is the cell containing the plant, the end of the radius sweep with the largest gap. The
ranking of countries by exposed share keeps a Spearman correlation of at least 0.66 against the
baseline.

Resolution ladder, averaging the cells into blocks: country 42.9%, 2 degrees 24.3%, 1 degree
23.2%, 0.5 degrees 20.5%, 0.25 degrees 17.7%. The step from country to 2 degrees is 18.6 points of
the 25.2; the step from 2 degrees to 0.25 is 6.6 points [1.9, 11.4].

## Findings by country

The country value calls Spain, Italy and Portugal exposed in full; by cell, 28%, 36% and 26% of their
MW is. Spain's country value is 11.6 days; its plants' MW-weighted mean is 5.1. Greece agrees with
its country value: 90% of its MW is exposed by cell. Austria, three plants and 2,067 MW, goes the other
way: not exposed by country, 81% by cell. Of the 28.1% of capacity that changes class at *k* = 2,
26.7 points are called exposed by country and not by cell and 1.4 points the other way. Ten plants
hold 34.7% of the grid-exposed MW.

## Limits

- **The assumption that would break the conclusion.** The 0.25 degree files are a regridded product
  of coarser CMIP6 models; I have not checked CCKP's documentation for their native resolution. If the
  structure inside a country is the models' smooth field and not conditions at the plant, the grid
  share is wrong in a direction this module cannot see. The ladder bounds the exposure: 6.6 of the
  25.2 points lie between 2 degrees and 0.25, so the finest scale is the least secure part.
- **One hazard.** Days above a 35 C heat index is ambient heat. Cooling-water temperature, which
  curtails thermal plants, is a different variable.
- **The register.** The coordinate check finds errors only if they leave the country. An error inside
  the country, or under 10 km, passes unseen.
- **The comparator.** The country value is CCKP's area mean, the number module 03 used. A national
  value weighted by population or capacity is not tested here. It would shrink the gap if it weights
  the hot places less.

## Run it

```bash
python3 src/fetch.py              # inputs -> data/raw/, results/fetch_log.json
python3 tests/test_gridded.py
python3 src/gridded.py            # about a minute -> results/gridded.json, results/plants.csv
python3 src/deck.py               # six pages -> deck.pdf
```

[`notes.md`](notes.md) has what I tried and dropped.
