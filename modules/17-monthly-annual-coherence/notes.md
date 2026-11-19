# Notes: what I tried, what I threw away, what I got wrong

**Both-zero pairs: in the headline, then out.** My first run counted a pair with a monthly sum of 0 and an annual figure of 0 as a
gap of 0, which is coherent. That gave 73.1%. Then I saw that 214 of the 1,641 pairs were zero against zero (146 pumped storage, 26 exports,
24 imports, 18 distribution losses), mostly countries with no such flow, and that they were adding agreement the data do not show: the relative gap of
0 over 0 is undefined. I dropped them. The headline is 69.0%, and the 73.1% sits in the sweep. I changed this after seeing both
numbers, so the README shows both.

**The roadmap's flow pairing for distribution losses does not compare like with like, and I kept it.** The roadmap says to use the flows that exist in
both datasets, and `DL` exists in both under one code. Monthly `DL` against annual `DL` agrees in 6.7% of country-years. Looking for
why, I tried annual `LOSS` (all losses) and it fits the monthly figure far better: median ratio 0.96 to 1.00 in every year. I kept the
same-code pairing as the headline because the roadmap fixed it in advance and because changing the pairing after seeing the
result is a choice I would not be able to defend. `LOSS` is in the sweep. Even against `LOSS` only 33.6% agree, so it is part of
the story, not all of it. The annual `DL` also changes level twice (zero for at least half the countries to 2021, 0.72 to 0.73 of `LOSS` in
2022 to 2024) and then jumps in 2025 and I cannot say why from the metadata.

**Pumped storage: one line against two.** The monthly table has one pumped-storage line and the annual has two, by plant type. I
looked at the monthly line against the pure line alone and against the mixed line alone, and neither is stable: the annual lines
move volume between each other and across years. For Sweden the annual sum is 147 to 208 GWh a year in 2008 to 2016 against a
monthly sum of 1 to 50, and 32 to 137 against 31 to 95 from 2017 (within 12% in 2017 to 2021 and in 2024, 31%, 41% and 46% below in 2022, 2023 and 2025). The sum is the only
pairing that does not depend on how a country splits plants between the two lines. It is still my choice, not Eurostat's, and the
persistent pumped-storage pairs (9 of 31) mostly stay unexplained.

**Available to the internal market.** The monthly table has `AIM` and I tried it against annual `ID` (inland demand) and `AFC`
(available for final consumption). They agreed in a minority of country-years. I dropped them because nothing I could read says
they are the same quantity, and a mismatch I cannot tell from a definition difference is not a data-quality finding. I did not keep the
exploratory numbers.

**Net generation from a second monthly table.** The roadmap names `nrg_cb_em` only. Net electricity generation is in `nrg_cb_pem` and
has an annual counterpart (`NEP`), which would have given a fifth flow. I kept it out of the headline and put it in the sweep: 61.8%
pooled with it, 40.6% alone. Adding a table the roadmap did not name to the headline would have moved the result a lot.

**Interval unit.** The roadmap says to resample country-years. I did, with all of a country's flows in one draw. Then I saw that
divergence persists in a country across years (that is the other half of the estimand), so country-years are not independent and the
interval is too narrow for the question "how many countries are coherent". I added the whole-country resample. It is wider for the
pooled share, 11.4 points against 4.6. For distribution losses it is slightly narrower, 6.5 against 7.5, which I did not expect
and did not investigate.

**The persistent-count interval is biased and I left it.** A draw of country-years leaves some pairs with fewer than five years, and
those drop out of the count. The point value, 31, sits near the top of its interval [25, 33]. A fix would be to define persistence by
the share of outside years only, with no minimum. I did not do that, because the minimum protects against calling a two-year blip
persistent, and I prefer a stated bias to a looser definition. The sweep shows the count from 13 to 36 over four rules.

**A mistake in the Ember check, avoided.** I expected the second publisher to settle which side is right. For imports and exports it
cannot: net imports cancel part of the gap (the import and export gaps in GWh correlate at 0.96 across country-years, driven by a few
large ones; their signs agree in only 55%), and Ember's yearly figures sit within a few GWh of Eurostat's. I downloaded Ember's monthly
file as well and did not use it, so I removed it from the fetch.

**Metadata.** The roadmap asks for each persistent divergence to be traced to a documented cause where the metadata gives one. The page I
expected for the monthly electricity table (`nrg_cb_em_esms`) returns HTTP 404, and the explanatory link in the API response points at
an oil page. I read the annual energy-statistics page instead. It gives the questionnaire structure and the rounding rule (whole numbers
to 2016, up to three decimals from 2017), and it does not describe any country's exception. So the "documented" cause in this module
is only the flag on the observation, 4 of 31, and everything else is a pattern I found.

**What I would check next.** Whether the annual `DL` jump in 2025 is a redefinition or a reporting change, which needs the release notes
of the November 2026 vintage or an older vintage to compare; I have one extraction and cannot separate it from revision.
