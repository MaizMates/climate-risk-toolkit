# tools/ — the crawler

`monitor.py` enumerates every employer in `ledger.json`, filters titles, diffs against
`state/seen.json`, and prints **only new or changed postings**.

The point is not speed, it is context. Marsh McLennan and ABB are ~3,500 postings between
them. Pulling those through an agent's context costs more than the rest of a run combined;
pulling them through this script costs nothing but wall-clock. That is why the old
"enumerate, never search" rule is now affordable: HTTP is free, context is not.

```bash
python3 monitor.py --only marsh,abb          # one or more ledger ids
python3 monitor.py --write-seen              # persist hashes after a real run
python3 monitor.py --all                     # every promoted title, not just new ones
```

Output is JSON: `counts` per employer (this is the coverage ledger's live half), `errors`,
and `hits`. Each hit carries the list that promoted it (`A` climate, `B` physical risk,
`C` quant-adjacent) and `senior_title`, which is gate 2 pre-computed.

## Filters

- **A** and **B** always apply. **C** applies only where `climate_practice: true`, because
  applied globally it promotes ~12% of a large board and stops being a filter.
- `actuar` was removed from list C on 2026-09-09: it produced ~40 rows on Marsh alone, all
  of them failing gate 6, because actuarial work wants exams I do not have.
- `RE_GEO_NO` rejects local-hire hubs and no-right-to-work markets before the agent sees
  them. The UK is deliberately absent: it needs the sponsor-register check, a judgement.

## Adding an employer

Never guess a tenant. Read the ATS host out of the careers page source, confirm one real
response, then add the row. Guessed Phenom `domain` values return `"Tenant not identified"`
and guessed Workday tenants return 422 — neither is a signal about the employer.
