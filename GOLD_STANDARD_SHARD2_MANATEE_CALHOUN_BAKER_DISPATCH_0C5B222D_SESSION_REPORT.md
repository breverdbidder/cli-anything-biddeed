# Gold Standard Shard-2: manatee + calhoun + baker — Session Report

- dispatch_id: `0c5b222d-47d8-4a85-8e3c-3344c9e01394`
- chat_session: `architect-20260725T000000`
- loop run: 6288
- date: 2026-07-25
- issue: breverdbidder/cli-anything-biddeed#13939
- ultraloop_mode: native (Workflow tool)

## Scope

Assigned shard: **manatee** (10/10 per brief), **calhoun** (8/10, B/F failing),
**baker** (6/10, C/D/E/I failing). Per PARALLEL-FLEET RULES, only these three
counties were touched. `gold_standard_loop()`/`gold_standard_certify()` were
**not** run fleet-wide this session (no confirmed all-clear on concurrent
shards) — per-county `pencil_dod_evaluate_county()` was used throughout, plus
a `gold_standard_ultraloop_audit`-writing ULTRALOOP audit+adversarial-verify
pass (16 claims, 2 refuted, all persisted — see below).

## manatee — no action needed, 10/10 confirmed + re-verified

Live-verified at session start, unaffected by this session's writes (no
manatee rows were touched), and independently re-audited + adversarially
verified letter-by-letter this session (10/10 claims survived refutation,
1 minor evidentiary correction noted below — the underlying PASS is correct).

```json
{"county":"manatee","auctions_total":86,
 "A":{"pass":true,"metric":3,"detail":"fc=83 td=3"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=5 closed_sold=5"},
 "C":{"pass":true,"metric":96.5,"detail":"matched_clean=83"},
 "D":{"pass":true,"metric":96.5,"detail":"matched_any=83"},
 "E":{"pass":true,"metric":96.5,"detail":"parcel_linked=83"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=5 closed_sold=5"},
 "G":{"pass":true,"metric":96.3,"detail":"density=96.3 far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":true,"metric":96.5,"detail":"card_complete=83 of 86"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=86 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

**Audit finding (minor, non-blocking):** the letter-B audit claim asserted
"none of the 5 verified-outcome rows are propertyonion-sourced on the mca
side." The independent refuter disproved this: 1 of the 5 (case
412025CA002459CAAXMA) has `data_source='propertyonion'` on the
`multi_county_auctions` row itself, and is included in the evaluator's
denominator only because `tier1_authoritative=true` legitimately overrides
the propertyonion exclusion filter — which is correct, designed evaluator
behavior, not a bug. The headline metric (B=100.0%, verified=5,
closed_sold=5) reproduced cleanly and is correct; only the audit claim's
supporting narrative was imprecise. Logged as `survived=false` in
`gold_standard_ultraloop_audit` for honesty (the claim as *worded*
overstated its evidence), but this is **not** a metric problem and does not
put manatee's B PASS in question.

manatee's precert guards (`calendar_parity`, `denominator_integrity`) show
`passed=true` daily through 2026-07-24 (auto-populated, not touched this
session). manatee is certification-ready pending a fleet-wide
`gold_standard_loop()` + `gold_standard_certify()` run once no shard is
mid-flight.

## baker — real fix shipped: fabricated linkage purged, honest baseline now 20%

**Root cause (confirmed live):** 3 of baker's 15 rows had `parcel_id`
literally set to the string `'Property Appraiser'` — scraper-bug anchor text
from an empty `bakerpa.com` link, not a real parcel — stamped with a
**fabricated** `parity_status='matched_clean'` /
`parity_source='tier1_supplementary:shard3:2026-06-25'` by a prior session.
A migration to purge this (`20260724_shard2_baker_c_d_e_i_property_appraiser_purge.sql`)
was **committed on 2026-07-24 but never executed against the live DB**
(files-only, SHIP GATE violation — confirmed via `updated_at` timestamps and
a live re-check showing the garbage values still present at session start).

**Fix (this session, executed + pushed to main,
`supabase/migrations/20260725_shard2_baker_property_appraiser_purge_executed.sql`):**
ran the purge live, extended to also null `parity_status`/`parity_source`
(the fabricated match-stamp rode on the same garbage value and needed the
same treatment).

```json
BEFORE (session start):
{"county":"baker","auctions_total":15,
 "C":{"pass":false,"metric":40.0,"detail":"matched_clean=6"},
 "D":{"pass":false,"metric":40.0,"detail":"matched_any=6"},
 "E":{"pass":false,"metric":40.0,"detail":"parcel_linked=6"},
 "I":{"pass":false,"metric":20.0,"detail":"card_complete=3 of 15"}}

AFTER (session end):
{"county":"baker","auctions_total":15,
 "A":{"pass":true,"metric":7,"detail":"fc=7 td=8"},
 "B":{"pass":true,"metric":100.0,"detail":"verified=1 closed_sold=1"},
 "C":{"pass":false,"metric":20.0,"detail":"matched_clean=3"},
 "D":{"pass":false,"metric":20.0,"detail":"matched_any=3"},
 "E":{"pass":false,"metric":20.0,"detail":"parcel_linked=3"},
 "F":{"pass":true,"metric":100.0,"detail":"tier1_sold=1 closed_sold=1"},
 "G":{"pass":true,"metric":100.0,"detail":"density= far=100.0 pk1000=100.0"},
 "H":{"pass":true,"metric":0.1,"detail":"hours since last_seen (SLA 48h)"},
 "I":{"pass":false,"metric":20.0,"detail":"card_complete=3 of 15"},
 "J":{"pass":true,"metric":100.0,"detail":"deal_complete=15 (triangle + two-arm CMA + ml_score + max_bid)"}}
```

C/D/E **dropped** 40.0%→20.0% and I is unchanged at 20.0%. This is the
**correct direction** — a fabricated ghost-success was removed, not a
regression. All 4 claims (C, D, E, I) independently re-verified and survived
adversarial refutation (see audit table).

**Remaining gap, confirmed still genuinely blocked (3rd independent
verification, following the 2026-06 and 2026-07-24 sessions):** the other 6
case numbers (12 rows) have **zero** owner_name/plaintiff/trellis_url/
property_address/legal_description anywhere in `multi_county_auctions` —
no search key exists to query any external source with. New this session:
**bakerpa.com is back online** (HTTP 200, was HTTP 521 on 2026-07-24) — but
with no name/address/parcel to search it with for these specific 6 cases,
this is not yet actionable. `baker.realforeclose.com`'s own Parcel ID link
is empty (`href="...?parcel="`) for these cases at the source — Baker County
itself has not linked a parcel yet. **Next-session lever:** a
browser-automation session against `civitekflorida.com/ocrs/county/02/`
(stateful JSF/PrimeFaces court-record search, not reachable via plain
`curl`) could surface defendant/owner names, which would then be searchable
against the now-live bakerpa.com.

## calhoun — B/F re-confirmed blocked; genuine new lead found, not acted on

**Baseline unchanged, re-verified fresh:**

```json
{"county":"calhoun","auctions_total":7,
 "B":{"pass":false,"metric":null,"detail":"verified=0 closed_sold=0"},
 "F":{"pass":false,"metric":null,"detail":"tier1_sold=0 closed_sold=0"}}
```

This is the **3rd independent live re-verification** (following dispatch
`d0d45cbc` and its 2nd-firing addendum) confirming calhoun has never had a
closed sale at the source. `scripts/calhoun_clerk_harvest.py` correctly
mirrors `calhounclerk.com`'s own WordPress CPTs daily; there is no
results/outcomes scraper because the source has never published one.

**New lead (adversarial-verify found this, not the primary audit pass):**
`calhounclerk.com`'s `/wp-json/wp/v2/taxdeedoverbids` endpoint has a record
(slug `2026-5-td`, posted 2026-07-24) for cert **"171 OF 2023"** —
`owner="Bama Lee Cooper"`, `balance="2579.51"`, same `parcel` and
`sale_date` (Jul 9, 2026) as the open cert. An overbid/surplus record is
only generated by the clerk **after** a tax deed sells for more than the
statutory minimum — its existence is strong evidence the sale actually
closed on 2026-07-09, even though both `calhounclerk.com`'s own `taxdeeds`
CPT (`status: scheduled`) and our DB (`auction_status: upcoming`,
`sold_amount: NULL`) are stale/unupdated.

**Deliberately not acted on:** `balance` is the surplus paid to the former
owner, not the winning bid. Reverse-computing a `sold_amount` as
`opening_bid + balance` ($6,472.01 + $2,579.51 = $9,051.52) would only be a
**lower bound** — if other lienholders were paid from the overbid before the
former owner, the true winning bid is higher — and writing an estimated
figure into `sold_amount` would repeat exactly the fabrication pattern this
campaign's guardrails exist to prevent. **Next-session lever:** pull the
actual recorded Certificate of Title for cert 171 OF 2023 (the deed
recording states the literal winning bid) rather than inferring one.

## ULTRALOOP audit + adversarial verify (this session, native Workflow)

16 claims generated (10 manatee, 4 baker, 2 calhoun), each independently
re-verified live against the DB/source by a separate adversarial-refuter
agent instructed to default to `refuted=true` unless it could reproduce the
claim's core assertions itself. **14/16 survived, 2 refuted** (both
overstatement-in-narrative issues, not metric errors — see manatee B and
calhoun F sections above for full refuter reasoning). All 16 rows persisted
to `public.gold_standard_ultraloop_audit` with `dispatch_id=0c5b222d-...`,
`ultraloop_mode='native'` — verified via
`SELECT count(*) ... WHERE dispatch_id='0c5b222d-...'` returning 16.

## Verification protocol

- `pencil_dod_evaluate_county()` run fresh for all 3 counties at session
  start and session end (pasted above).
- Baker fix verified via direct SQL re-query (`parcel_id !~ '[0-9]'` and
  literal `'property appraiser'` search both return 0 rows post-fix) plus
  the independent ULTRALOOP refuter re-deriving the same counts from raw
  SQL, not just re-reading the RPC.
- calhoun blocker re-verified against live `calhounclerk.com` endpoints
  (taxdeeds, foreclosures, taxdeedoverbids), not from memory of prior
  sessions' findings.
- `gold_standard_loop()`/`gold_standard_certify()` **not run** this session
  (parallel-fleet caution — no positive confirmation the fleet was idle).

## Commits pushed to main

- `80142e66` — `fix(gold-standard-shard2-baker): execute the never-applied
  2026-07-24 parcel_id purge live`

## Next-session priorities

1. baker: browser-automation OCRS court-record lookup for the 6 blocked
   cases' owner names, then search the now-live bakerpa.com.
2. calhoun: pull the actual recorded Certificate of Title for "171 OF 2023"
   to get a real winning-bid figure (not inferred) — would flip B and F
   simultaneously if it lands.
3. Fleet: once confirmed idle, run `gold_standard_loop()` +
   `gold_standard_certify()` — manatee's guards + 10/10 + fresh audit
   evidence all line up for certification.
