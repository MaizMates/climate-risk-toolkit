# notes — decisions, and the roads I did not take

**Why the World Bank CCKP and not NGFS.** NGFS is the scenario set I actually used at the ECB
and my first instinct was to start there. The Scenario Explorer needs an account, which means a
module nobody can run without registering first, and I want these to be runnable by whoever
opens the repository. CCKP is open, keyless, and CMIP6 underneath, which is the same generation
of models. NGFS belongs in the transition modules, where its damage functions and carbon prices
are the point.

**Why country level, which I do not like.** The honest answer is that it is the level at which I
can get exposures later without paying for data. A grid-level hazard layer is easy to obtain and
useless on its own, because the loan book I would overlay is not public at that resolution. I
would rather have a coarse pair that joins than a fine layer that does not.

**A bug that would have been invisible.** The API keys each value by a period string, and the
key is not the same across collections: the projection comes back as `{"2040-07": 4.14}` and the
baseline under a different key. My first version read by key and returned empty dictionaries for
the baseline, which silently made every change equal to the projection. The number looked
plausible, which is the dangerous kind of wrong. `fetch` now reads the value and ignores the key,
and `tests/test_hazard.py` pins that behaviour.

**What I dropped.** I wanted to include the ensemble spread and report an interquartile range
instead of a median, because a supervisor asks about the tail and not the middle. The CCKP
collections expose the ensemble statistics under separate names and wiring all of them up turned
into more plumbing than analysis for a first module. It is the first thing I would add.

**Time.** About a working session, most of it on the key-versus-value bug and on deciding what
this module should refuse to claim.
