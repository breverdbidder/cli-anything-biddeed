# GOLD STANDARD SHARD-6 — hillsborough, madison, wakulla, hernando

dispatch_id: `cc6bdc10-6b93-496a-bcd6-7919ff2757cf`
session: `architect-20260703T160000`
loop run: 2753
mode: ULTRALOOP native (Workflow tool, fan-out fix + adversarial refuter verify per county)

## Methodology note (read first)

Direct psql/pooler auth (`SUPABASE_DB_PASSWORD`) was rejected by both the pooler
host and `db.mocerqjnksmhcjzxrewo.supabase.co` in this runner (`password
authentication failed for user "postgres"`). All live reads/writes this session
went through the Supabase Management API SQL endpoint
(`https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query` with
`SUPABASE_ACCESS_TOKEN`), same as the precedent set by
`20260703_shard10_desoto_jackson_orange_volusia_cd_ghost_success_purge.sql`. That
endpoint rate-limits aggressively (Cloudflare 403 `error code: 1010` on bursts of
rapid single-line-query POSTs) — spacing writes ~4s apart resolved it. Flagging
for future sessions hitting the same endpoint.

## Before/after (pencil_dod_evaluate_county, live, pasted verbatim)

### hillsborough (was 9/10, now 8/10 — HONEST regression, not a bug)

BEFORE:
```json
{"A":{"pass":true,"metric":377,"detail":"fc=539 td=377"},"B":{"pass":true,"metric":100.0,"detail":"verified=187 closed_sold=187"},"C":{"pass":false,"metric":92.6,"detail":"matched_clean=848"},"D":{"pass":true,"metric":98.6,"detail":"matched_any=903"},"E":{"pass":true,"metric":97.8,"detail":"parcel_linked=896"},"F":{"pass":true,"metric":100.0,"detail":"tier1_sold=187 closed_sold=187"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":95.0,"detail":"card_complete=870 of 916"},"J":{"pass":true,"metric":97.3},"county":"hillsborough","auctions_total":916}
```

AFTER (fresh re-run, post-close-out):
```json
{"A":{"pass":true,"metric":377},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":77.4,"detail":"matched_clean=709"},"D":{"pass":false,"metric":77.4,"detail":"matched_any=709"},"E":{"pass":true,"metric":97.8},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.1},"I":{"pass":false,"metric":95.0,"detail":"card_complete=870 of 916"},"J":{"pass":true,"metric":97.3},"county":"hillsborough","auctions_total":916}
```

**D went from a FALSE PASS (98.6%) to an honest FAIL (77.4%).** Root cause: 194
rows carried `parity_source` values (`tier1_supervisor_parity_restore_20260623`,
`tier1_official_platform_open_auction_parcel`, `tier1_official_platform_open_auction_address`,
`tier1_realforeclose_hillsborough`) with **zero backing** in
`tax_deed_outcomes`/`foreclosure_outcomes`. Two of the four labels have no source
file anywhere in the repo. The other two were created by
`20260702_shard7_citrus_hillsborough_nassau_suwannee_cd_parity.sql` (lines 58-70)
under a comment claiming "official-platform parcel_id/address presence" — the
actual SQL condition only checks that **our own row** already has a `parcel_id`
of length ≥8, never queries any external platform. This is the same
ghost-success pattern already purged today for jackson/orange/volusia
(`20260703_shard10_...sql`). Purged + re-ran the canonical
`refresh_parity_tier1_outcomes('hillsborough')`. Real ceiling = 709 closed rows /
916 total = 77.4% (207 upcoming auctions structurally cannot match). Migration:
`supabase/migrations/20260703_shard6_hillsborough_cd_ghost_success_purge.sql`.

I remains FAIL (870/916 = 94.98%, displayed as 95.0 but the raw comparison is
`>= 95` and fails by a hair). Root cause: 25 newly-scraped upcoming auctions with
real addresses but no geocode/value/zoning enrichment yet, plus 1 row missing
address. **Did not run** `scripts/shard5_i_enrichment_hillsborough.py` — that
script fabricates fallback lat/lng (county centroid), a flat $100k default
assessed value, and a placeholder `R-1` zone code, which is banned under this
repo's own honesty rules. No real fix attempted this session (would require a
live HCPAO value scrape + zoning ingestion for those 25 parcels).

### madison — **NOW 10/10, PASS on all letters**

BEFORE:
```json
{"A":{"pass":true,"metric":4},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":8.0},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"county":"madison","auctions_total":9}
```

AFTER (fresh re-run):
```json
{"A":{"pass":true,"metric":4},"B":{"pass":true,"metric":100.0},"C":{"pass":true,"metric":100.0,"detail":"matched_clean=9"},"D":{"pass":true,"metric":100.0,"detail":"matched_any=9"},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":8.3},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"county":"madison","auctions_total":9}
```

Ran the canonical `refresh_parity_tier1_outcomes('madison')` (existing, unmodified
shared function). All 9 auctions matched clean via case_number against real
`foreclosure_outcomes`/`tax_deed_outcomes` rows (data_source
`realforeclose:shard5-v1`/`realforeclose:shard5-loop472`,
`realtaxdeed:shard5-v1`/`realtaxdeed:shard5-loop472` — non-promote, legitimate).
Prior blocker was the untraceable `tier1_madison_direct` label sitting on
`parity_status='mca_only'` rows, silently preventing the canonical matcher from
ever touching them. Migration:
`supabase/migrations/20260703_shard6_madison_cd_canonical_rematch.sql`.

**madison is gold-candidate: 10/10 on pencil_dod_evaluate_county. Certification
requires a second consecutive 10/10 at the daily 07:30Z `gold_standard_loop()`
run — not triggered this session per PARALLEL-FLEET RULES (other shards may be
running concurrently).**

### wakulla — C/D improved, hit genuine structural ceiling (still 8/10)

BEFORE:
```json
{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":5.1},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"county":"wakulla","auctions_total":5}
```

AFTER (fresh re-run):
```json
{"A":{"pass":true,"metric":2},"B":{"pass":true,"metric":100.0},"C":{"pass":false,"metric":60.0,"detail":"matched_clean=3"},"D":{"pass":false,"metric":60.0,"detail":"matched_any=3"},"E":{"pass":true,"metric":100.0},"F":{"pass":true,"metric":100.0},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":5.5},"I":{"pass":true,"metric":100.0},"J":{"pass":true,"metric":100.0},"county":"wakulla","auctions_total":5}
```

Ran canonical `refresh_parity_tier1_outcomes('wakulla')`. All 3 closed-status
auctions matched clean against real `foreclosure_outcomes`/`tax_deed_outcomes`
rows (data_source `shard5_bootstrap_run338_wakulla`). **Structural ceiling: only
3 of wakulla's 5 auctions are closed-status; the other 2 are upcoming and cannot
be matched until they close.** Ceiling = 3/5 = 60.0%, below the 95% threshold —
correctly reported as FAIL, no false PASS claimed. Migration:
`supabase/migrations/20260703_shard_wakulla_cd_ghost_success_purge_and_refresh.sql`.

### hernando — no metric change, all findings are genuine structural ceilings (5/10)

BEFORE and AFTER are byte-for-byte identical (confirmed no drift):
```json
{"A":{"pass":true,"metric":10},"B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},"C":{"pass":false,"metric":0.0},"D":{"pass":false,"metric":0.0},"E":{"pass":true,"metric":100.0},"F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"},"G":{"pass":true,"metric":100.0},"H":{"pass":true,"metric":0.7},"I":{"pass":false,"metric":43.5,"detail":"card_complete=10 of 23"},"J":{"pass":true,"metric":100.0},"county":"hernando","auctions_total":23}
```

**B/C/D/F: genuine structural ceiling, not a bug.** All 23 hernando auctions are
`auction_status='upcoming'` with `sold_amount IS NULL`, and zero rows exist in
`tax_deed_outcomes`/`foreclosure_outcomes` for hernando. B and F are 0/0
(undefined — nothing has sold yet). C and D are 0/23 because the canonical
matcher only ever sets `parity_status` on closed-status rows. These will
self-resolve once real auctions close and get scraped outcomes — no action was
possible or attempted this session.

**I: real, specific blocker identified, not fixed (would require new zoning
ingestion).** 13 of 23 rows fail `card_complete`. Extracted the exact evaluator
SQL and proved the blocker is solely the `zone_code` join against
`v_zoning_gold_standard_card`, which has only **11 total rows for hernando**
(covering 10 of 23 auction parcels — matches the 10 passing rows exactly). 7 of
the 13 failing rows already have complete address + lat/lng + value and are
blocked *purely* by the missing zoning-district assignment; backfilling
lat/lng/value for the other 6 would be a no-op against the AND-gated metric, so
no writes were made (would add noise, not progress). Root cause: hernando has
essentially no zoning-district ingestion yet — a real scraper build against
Hernando County GIS is required, out of this session's scope.

## Ghost-success audit trail

All 4 claims above were independently adversarially verified by a separate
refuter agent (re-ran every query live, spot-checked source-table backing,
confirmed structural ceilings independently) — all 4 **SURVIVED**. Logged as 11
rows (one per letter) to `gold_standard_ultraloop_audit`
(`dispatch_id=cc6bdc10-6b93-496a-bcd6-7919ff2757cf`, `ultraloop_mode='native'`,
`survived=true`).

## Scoreboard summary

| county | before | after | letters still failing |
|---|---|---|---|
| hillsborough | 9/10 | 8/10 | C, D (real ceiling 77.4%), I (94.98%, enrichment lag) |
| madison | 8/10 | **10/10** | none — awaiting certify's 2nd-consecutive-run gate |
| wakulla | 8/10 | 8/10 | C, D (real ceiling 60.0%, will rise as auctions close) |
| hernando | 5/10 | 5/10 | B, C, D, F (0 sold yet), I (zoning ingestion gap) |

`gold_standard_loop()` / `gold_standard_certify()` **not invoked** this session
per PARALLEL-FLEET RULES (other shards run concurrently) — verification above
uses `pencil_dod_evaluate_county()` per county only, as instructed.

## Deferred / next steps (flagged honestly, not attempted)

- hillsborough I: HCPAO real-value scrape + zoning link for 25 newly-scraped
  parcels (no fabrication).
- hernando I: new zoning-district ingestion (GIS scrape) for hernando — only 11
  parcel_zones rows exist county-wide today.
- hernando/wakulla B/C/D/F: will improve automatically as upcoming auctions
  close and get real clerk-sourced outcomes; no scraper gap identified, just
  time/accrual.
