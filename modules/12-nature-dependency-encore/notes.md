# Notes: what I tried, what I dropped

**The ENCORE download needs a login.** The "Download the updated ENCORE knowledge base" button on
encorenature.org is disabled without an account, and I will not build a module on an account. The
Explore tool on the same site loads its ratings from a JSON endpoint (`/en/ecosystem_services`,
`/en/sectors`) that answers without a login. I found the endpoint list in the site's own
JavaScript bundle and use those two. I did not check whether the login-only files differ from this
JSON, so a reader with an account could compare them. The site's terms mention CC BY-SA 4.0 for the
downloaded files; I read that as covering the same data, and commit only derived results.

**The old domain.** `encore.naturalcapital.finance`, where I expected ENCORE to live, now answers
with a redirect to an unrelated gambling site. I did not follow it or use anything from it.

**Considered and rejected: resampling holdings.** A bootstrap over the 213 holdings would estimate
how the share would change for a different fund drawn from the same universe. The estimand is this
fund, and module 05's first interval went wrong exactly there. The only random element is which
process a company is. Draws are independent per holding and the crosswalk variant is drawn once per
industry, which a test pins (`test_mapping_draw_is_shared_across_holdings_of_one_industry`).

**A number I removed.** I first wrote a "pass-through" share for financials, assuming they
inherit their borrowers' share. It equalled the non-financial share by construction, so it carried
no information. The deck states only the non-financial share and the rise it would imply.

**The crosswalk, industry by industry.** GICS industries are mapped to ENCORE sub-industries by
what the fund holds under each label, first entry dominant. Choices a reviewer may dispute:
Aerospace & Defense to other transport equipment plus fabricated metal (weapons); Industrial
Conglomerates to machinery plus electrical equipment; Personal Care and Household Products to chemicals; Gas Utilities to the
electricity, gas and steam sub-industry, which includes manufacture and distribution of gas;
Biotechnology to pharmaceuticals; Software to publishing plus computer programming (ENCORE files
software publishing under publishing). The narrow and broad variants bracket these choices; they
move the headline by 4.2 points. Weighting each sub-industry equally instead of each process moves
it by 0.07 points, so I left it in the sweep but do not discuss it further.

**Fetch glitches.** The first fetch returned HTTP 406 for the holdings file because I sent a JSON
`Accept` header to every host; it is now sent to encorenature.org only. SciPy is not in the allowed
list, so the rank correlation is written with pandas ranks (average ranks for ties) and tested.

**Not done.** I did not map the ECB's 0.7 score onto ENCORE letters; the page does not state the
mapping and I would be guessing. I did not run a second fund. A fund with fewer financials would
raise the headline mechanically, and that is the point of the financials line in the limits.
