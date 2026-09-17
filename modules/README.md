# modules

One module per scheduled run, Monday and Thursday. Two files govern this directory:

- **[`ROADMAP.md`](ROADMAP.md)** — what gets built, in order, with the estimand and the data
  source named in advance. The run builds the lowest-numbered module that does not yet exist. It
  does not choose and does not reorder.
- **[`STANDARD.md`](STANDARD.md)** — the bar each one has to clear: a stated estimand, inputs
  fetched rather than typed, an interval on every headline number, an out-of-sample test, a
  sensitivity sweep over the arbitrary choices, and a limits section that names the assumption
  which would break the conclusion.

## Built

| # | Module | The finding |
|---|---|---|
| 01 | [`01-heat-stress-gradient`](01-heat-stress-gradient/) | where heat stress grows fastest in the euro area, and that the ordering by growth is not the ordering by level |
| 02 | [`02-renewables-pace`](02-renewables-pace/) | 19 of 27 member states fall short of the 42.5% yardstick on their realised pace; the method's own five-year error is 5.5 points, so one country cannot be called either way |

## Removed

`02-thermal-power-exposure` was deleted on 17 September 2026. Its data file presented itself as an
extract from the WRI Global Power Plant Database and contained five plants that do not exist in
it — checked against the real database, 34,492 plants, zero matches. The question it asked was a
good one and it is now module 03 in the roadmap, to be built on the real database.
