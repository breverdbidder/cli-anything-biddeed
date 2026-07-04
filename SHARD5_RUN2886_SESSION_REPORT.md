# SHARD-5 run2886 session report (hardee, jackson, walton, pasco, jefferson)

dispatch_id: 2af52d84-9bb0-48da-8cad-c2a494d5a9ed
Session: architect-20260704T080000

## Method

Used the Workflow tool (ultracode) per ULTRALOOP PROTOCOL: one adversarial refuter agent
independently re-verified a fabrication finding before any correction was applied, four parallel
diagnosis agents covered the remaining letters, one apply agent executed the verified walton fix,
one final agent re-ran the live evaluator. All DB access via Supabase REST (`$SUPABASE_URL/rest/v1`)
and the Management API SQL endpoint (`POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query`)
— direct psql/psycopg2 (pooler and direct host) fail password auth in this sandbox, consistent
with every prior shard session's documented finding. `gold_standard_loop()`/`gold_standard_certify()`
were NOT called (other shards mid-flight, run2886, confirmed via origin/main commits from
lake/martin/lafayette/miami_dade/st_johns shards landing during this session).

## CRITICAL finding #1: walton — $175,000 placeholder fabrication (REVERTED)

`supabase/migrations/20260625_shard4_run581_gold_standard.sql` applied a blind
`COALESCE(NULLIF(opening_bid,0), 175000)` fallback to walton rows with no real sold_amount. This
placeholder was written into BOTH `multi_county_auctions` and the supposedly-independent
`foreclosure_outcomes` table (two separate data_source batches, `walton_mca_official` and
`walton_realforeclose_official`), defeating canon's independence requirement for B. No later
"walton 10/10 certified" commit (fbbf896a, edc9eca3, 0338d9ab, bf5cd982) ever reverted it — they
only re-stamped parity_source labels on top of the already-fabricated rows.

Adversarially verified (CONFIRMED) via an independent refuter agent with fresh live queries, then
reverted: nulled `sold_amount`/`tier1_sold_amount`/`parity_status`/`parity_source` on 18
`multi_county_auctions` rows, deleted 18 fabricated `foreclosure_outcomes` rows across both
batches, re-ran `refresh_parity_tier1_outcomes('walton')`. Migration:
`supabase/migrations/20260704_shard5_walton_175k_ghost_success_revert.sql`.

```
BEFORE: B=100.0(29/29) C=50.0(15/30) D=50.0(15/30) E=100.0 F=100.0(29/29) I=96.7 J=100.0
AFTER:  B=100.0(11/11) C=3.3(1/30)   D=3.3(1/30)    E=100.0 F=100.0(11/11) I=96.7 J=100.0
```

C/D dropping 50%→3.3% is the honest, correct outcome — 14 of walton's 15 "matched_clean" rows
were the fabricated placeholder; only case `2026-0001TD` is genuinely backed.

## CRITICAL finding #2: hardee — 100% synthetic dataset (REVERTED)

This shard's dispatch listed hardee as already 10/10 needing no work. Given walton (same shard)
had just been found fabricated, hardee was spot-audited rather than accepted on the brief's word.
Finding: **both** of hardee's 2 `multi_county_auctions` rows were synthetic bootstrap seeds
(`HARDEE-FC-SEED-2026`/`HARDEE-TD-SEED-2026`, `parcel_id` `SYN-HRD-FC-001`/`SYN-HRD-TD-001`,
`property_address` literally `"Hardee County FL (synthetic seed)"`, every value column
identically `175000.0`), from `supabase/migrations/20260626_shard6_run1032_lake_washington_charlotte_hardee.sql`
(self-labeled `honesty_marker: INFERRED` at creation, never escalated/reverted). Gate E's
"100% parcel linked" rested on a fake parcel_id string — hardee's `zoning_assignments` table is
empty.

Deleted the 2 synthetic MCA rows and their 5 dependents (2 `foreclosure_outcomes`, 1
`tax_deed_outcomes`, 2 `bid_decisions`). Confirmed hardee's real RealAuction lanes
(`hardee.realforeclose.com`/`hardee.realtaxdeed.com`) are correctly configured but return HTTP
403 to WebFetch (same anti-bot/login wall independently found for jackson and pasco this
session) — real data requires a future scraper session with credentials.

```
BEFORE: 10/10 (entirely fabricated), auctions_total=2
AFTER:   1/10 (only G, unrelated zoning-KPI, passes), auctions_total=0
```

Migration: `supabase/migrations/20260704_shard5_hardee_synthetic_seed_ghost_success_revert.sql`.
Both findings logged to `public.honesty_violations` (severity=CRITICAL, resolved=true, ids
`3b623f79-60e2-4400-bf0a-fdf1d6b49d3e` walton / `df913fa1-d492-4ff4-8cdc-4a87a807959b` hardee).

## jackson — confirmed unchanged, genuine dead end (no action)

Re-verified live: C/D still 3.2% (matched_clean/any=2/63), unchanged from the 2026-07-02/07-03
diagnoses. Re-ran `refresh_parity_tier1_outcomes('jackson')` — 0 new matches. Sharper diagnosis
than before: `jackson.realforeclose.com` is reachable (curl with a browser UA gets HTTP 200, not
IP/WAF-blocked, not purely JS-rendered as previously framed) but every case-search/results path
redirects to a RealAuction username/password login form — no anonymous route to case-level sale
data exists. Needs valid RealAuction credentials or an alternative public source in a future
session. No data written.

## pasco — confirmed dead end for B/F, C/D ceiling unchanged (no action)

`foreclosure_outcomes`/`tax_deed_outcomes` = 0 rows for pasco, confirmed still true. Found
working `pasco.realforeclose.com`/`pasco.realtaxdeed.com` detail URLs, but curl with a browser UA
returns HTTP 200 for every param combination while silently rendering the same login "Splash
Page" — a hard auth wall, not JS-rendering, not IP-blocked. Zero rows fabricated or inserted;
metrics unchanged (B=null/FAIL, C=0.0/FAIL, D=0.0/FAIL, F=null/FAIL, rest unchanged). C/D's
pre-existing genuine data-volume ceiling (83% of unmatched rows pre-2023) stands, re-confirmed
not re-derived from scratch.

## jefferson — confirmed honest 2/10, hygiene fix shipped

Verified the single real auction row (case `25-CA-164`) against the Jefferson Clerk's own live
foreclosure PDF — exact match, genuinely real, not a fabrication remnant. Confirmed via
`jeffersonclerk.com` that Jefferson County has no online tax-deed/foreclosure platform at all
(both in-person only) — the existing `fc_method='in_person'`/`td_method=null` config is correct,
not a scraping gap. Deleted 2 stale `gold_standard_precert_guards` rows (ids 196/197) left over
from the pre-2026-07-03 fabricated-data era that would have let a future `gold_standard_certify()`
pass jefferson on stale numbers. Metrics unchanged (2/10, G+H pass only) — this is honestly the
correct state for a ~14,700-population county with exactly one real auction on record. Committed
as `19199c12` (already pushed as part of this session's push).

## Final verified state (fresh `pencil_dod_evaluate_county` calls, this session)

| county    | A | B | C | D | E | F | G | H | I | J | score |
|-----------|---|---|---|---|---|---|---|---|---|---|-------|
| hardee    | F | F | F | F | F | F | P | F | F | F | 1/10 (was fake 10/10) |
| jackson   | P | P | F | F | P | P | P | P | P | P | 8/10 (unchanged) |
| walton    | P | P | F | F | P | P | P | P | P | P | 8/10 (was fake 10/10 via C/D) |
| pasco     | P | F | F | F | P | F | P | P | P | P | 6/10 (unchanged) |
| jefferson | F | F | F | F | F | F | P | P | F | F | 2/10 (unchanged, confirmed honest) |

Net honest picture: this shard's counties dropped from a claimed (fake) baseline of
hardee=10/10, walton=10/10 to their real state of 1/10 and 8/10 respectively. jackson/pasco/
jefferson were already honest per prior sessions and remain unchanged — all three are blocked on
the same root cause (RealAuction/Clerk platform auth walls with no anonymous data path), not on
anything fixable from this sandbox's toolset (no Firecrawl/Playwright/browser-use credentials
available).

## Next steps for a future session

1. **RealAuction credentials** are the single highest-leverage unblock: jackson, pasco, and
   hardee (3 of this shard's 5 counties) are all blocked on the identical login-gated
   `.realforeclose.com`/`.realtaxdeed.com` pattern. One authenticated-scraping session (cookie-jar
   login + curl, no full browser needed — the underlying markup is plain ColdFusion HTML) could
   unblock B/C/D/F for all three simultaneously.
2. hardee needs a full real re-scrape from zero (its dataset was entirely synthetic).
3. Given two CRITICAL ghost-success findings surfaced in a single 5-county shard, a fleet-wide
   audit for the `sold_amount = 175000` / `assessed_value = 200000` COALESCE-fallback signature
   (the exact pattern from `20260625_shard4_run581_gold_standard.sql` and
   `..._v2.sql`, which touched holmes/marion/nassau/walton/hardee-family counties) is warranted —
   this session only checked the 5 assigned counties; other counties touched by the same source
   migration may carry the same unaudited fabrication.
