# Gold Standard shard-1 (brevard/jefferson/holmes) — dispatch `a42bf937-8d85-46f9-8158-554d3d6ffd21`, loop run 8310

chat_session: `architect-20260802T160000`
mode: ULTRALOOP native (ultracode opt-in — Workflow fan-out: 2 refuters against the session's own claims)

## Result: brevard 9/10 unchanged (I still FAIL, but honestly re-measured), jefferson 8/10 unchanged, holmes 6/10 unchanged

```
brevard:   A,B,C,D,E,F,G,H,J pass / I fail (card_complete=6028 of 7238, 83.3%)
jefferson: A,C,D,E,G,H,I,J pass / B,F fail (unchanged from 11th firing)
holmes:    A,E,G,H,I,J pass / B,C,D,F fail (unchanged from prior session)
```

No letter flipped PASS this session. Real, verified data-quality work landed in all three counties'
shared ledger (brevard I got real forward progress *and* a real correction), and jefferson/holmes
were re-confirmed as genuine structural blockers rather than re-worked from scratch, per the
redispatch protocol ("do not repeat work a prior comment marks complete").

## Brevard — letter I (property card completeness)

### Diagnosis
Live evaluator at session start: `card_complete=6044 of 7238` (83.5%). Decomposed the gap precisely
via direct SQL against `multi_county_auctions`, `v_zoning_gold_standard_card`, and `sample_properties`:
- 1124 rows missing `property_address`; 1058 of those have a numeric-format `parcel_id` (BCPAO tax
  account). Checked all 1058 live against Brevard County's own authoritative parcel GIS
  (`gis.brevardfl.gov` `Base_Map/Parcel_New_WKID2881` MapServer/5, field `STREET_NAME`): only 21 carry
  a real, non-placeholder street name. This independently reproduces a finding from a 2026-07-30
  session on this same county (`GOLD_STANDARD_SHARD4_BREVARD_DISPATCH_09F985FC_SESSION_REPORT.md`) —
  ~98% of the address gap is genuinely no-situs vacant/tax-deed land per the county's own record, not
  a scraper defect.
- Of the 21, one (`2209912`) had `STREET_NAME='CONFIDENTIAL'` — a Florida address-confidentiality-
  program flag, not a usable street address. Excluded, not written.
- The remaining ~70 rows had an address already but were missing geo/value/zoning. 68 of 70 were
  missing a `parcel_zones` row. Root cause: Brevard's county-level zoning GIS layer
  (`Planning_Development/Zoning_WKID2881`) covers unincorporated county only; most of these parcels
  sit inside one of Brevard's ~13 municipalities, which run separate zoning GIS systems not yet
  integrated into this pipeline — a genuine, bounded substrate gap for a future session, not a
  fixable-today item.

### Fix applied live (2026-08-02)
- 20 `property_address` UPDATEs sourced directly from `gis.brevardfl.gov` STREET_NUMBER/STREET_NAME/
  STREET_TYPE/CITY/ZIP_CODE fields, keyed by `TaxAcct = parcel_id`.
- 1 `parcel_zones` INSERT (tax_account `2103356`, zone `RU-1-7`, jurisdiction 13/Unincorporated
  Brevard County) via a live point-in-polygon spatial query against the county's own zoning layer.
- 11 more `parcel_zones` INSERTs copying zone codes that already existed, real and sourced, in
  `sample_properties.zone_code` (tagged `zoning_assignments_sync` / `gis_conquest` from legitimate
  prior pipelines) but had never been copied into the table the evaluator actually reads.
- Migration: `migrations/20260802_gold_standard_shard1_brevard_i_gis_backfill.sql`.

Net effect of these 32 writes, live-verified: `card_complete` 6044 → 6077 (83.5% → 84.0%).

### ULTRALOOP adversarial verify — REFUTED, then reconciled
A refuter agent independently re-ran the live evaluator and directly queried `multi_county_auctions`/
`parcel_zones`. It confirmed the `parcel_zones` writes (items 2+3, 12 rows) as real and non-fabricated,
and confirmed the live metric value (6077) was accurate — but flagged that `multi_county_auctions.
updated_at` for the 20 address rows read `2026-07-04`, over a month before this session, and concluded
the address writes "did not happen during this session," rating the overall claim **REFUTED**.

Followed up directly rather than accepting or dismissing the refutation: queried `pg_trigger` on
`multi_county_auctions` and confirmed there is **no** `BEFORE UPDATE ... SET updated_at = now()`
trigger on this table (5 triggers exist — quarantine enforcement, stale-card marking, freshness
capture, winning-bidder-to-lead — none of them touch `updated_at`). A raw `UPDATE ... SET
property_address = ...` issued via the Supabase Management API therefore legitimately does not move
`updated_at`, because nothing in the schema makes it move. Re-selected the 20 rows directly: all 20
carry the exact GIS-sourced addresses this session wrote, byte-for-byte matching the values fetched
from `gis.brevardfl.gov`. The refuter's method (using `updated_at` as a recency proxy) was invalid for
this table; the writes are real. **Reconciled verdict: SURVIVES**, with the refuter's method documented
so a future session doesn't repeat the same false-positive pattern.

### The refuter's real catch: a pre-existing ghost-success violation
While investigating the timestamp discrepancy, the refuter's own evidence trail (batches at
`2026-07-31`/`2026-08-01`, written by an unrelated prior session, not this one) led to a genuine find:
**49 rows** in `multi_county_auctions.property_address` held the literal placeholder strings
`'0 UNKNOWN'` (47 rows) and `'0 CONFIDENTIAL NO TPP'` (2 rows) — a naive `STREET_NUMBER || ' ' ||
STREET_NAME` concatenation from some prior session that never filtered out GIS non-address sentinel
values (the exact mistake this session's own script deliberately guarded against for the `CONFIDENTIAL`
case). Because these strings are `NOT NULL`, they were silently counting as `card_complete` under the
evaluator's `property_address IS NOT NULL` check — inflating brevard's I metric by 49 points before
this session ever touched anything.

Purged live (`property_address = NULL` where it held either placeholder), per the same
`ghost_success_purge` precedent already established elsewhere in this campaign (pasco/hillsborough/
glades/suwannee). This is a correction, not new work by this session, but it directly bears on I's
integrity and was verified and applied within this session.

### Honest before/after
```sql
-- Session start (before any writes):        card_complete=6044 of 7238  (83.5%)
-- After the 32 real GIS-sourced writes:      card_complete=6077 of 7238  (84.0%)
-- After purging the 49 ghost-success rows:   card_complete=6028 of 7238  (83.3%)
```
Net session effect: 6044 → 6028 (**-16**, i.e. the headline number goes *down*). This is the honest
outcome of +33 genuine new completions minus 49 fabricated ones that should never have counted. The
metric moving down here is evidence the correction was applied, not evidence of a regression — brevard
was never at 6044 real complete cards; it was at ~5997, reported as 6044 by a prior session's bug.

I remains a confirmed, evidence-backed data-availability ceiling (~84% max via currently known real
sources: ~98% of the address gap is genuinely no-situs vacant land, and the residual zoning gap needs
per-municipality GIS integration across up to 13 separate Brevard jurisdiction systems). Not a
scraper/matcher bug, matching the same conclusion an independent 2026-07-30 session reached.

## Jefferson — letters B/F (unchanged, correctly blocked)

Re-verified live rather than re-searched, per the 11th firing's explicit recommendation
(`GOLD_STANDARD_SHARD12_JEFFERSON_DISPATCH_675AA97F_11TH_FIRING_REPORT.md`, itself less than 3 days
old): `25-CA-164` sold, `sold_amount` still null; `26-TD-04`/`26-TD-05` both `auction_date=2026-08-19`,
`auction_status=scheduled` — the sale has not happened yet, so B/F cannot resolve by construction.
Confirmed live via direct SQL and via the RPC evaluator (zero drift). ULTRALOOP refuter independently
reproduced all three facts and did a light 2-3 search check for any genuinely new lever — found none.
**Verdict: SURVIVES.** Per the 11th firing's recommendation, further re-firing before 2026-08-19 (or
2026-08-24, first weekly clerk-scraper cron after) should be suspended.

## Holmes — letters B/C/D/F (unchanged, correctly blocked)

Re-verified live rather than re-searched, per `GOLD_STANDARD_SHARD5_HOLMES_DISPATCH_F60CABE3_SESSION_
REPORT.md` (one session prior, 2026-08-01) which documented an exhaustive 13+-session dead end.
Firecrawl credit balance re-checked live: `remaining_credits=-4`, still exhausted, not restored (the
condition that report set for re-attempting). ULTRALOOP refuter re-ran the live evaluator (zero drift),
re-confirmed the credit balance, and checked two nominally-new candidate sources
(`taxsaleresources.com`, `taxcertsale.com/HolmesTaxSale`) — both dead ends (one already ruled out in a
prior session, the other a signup-gated landing page with no visible disposition data, no Cloudflare/
CAPTCHA encountered or bypassed). **Verdict: SURVIVES.** No new lever this session; holmes B/C/D/F
should continue to be treated as a documented structural ceiling per the prior report's recommendation.

## ULTRALOOP audit trail

8 rows inserted into `gold_standard_ultraloop_audit` for dispatch `a42bf937-8d85-46f9-8158-554d3d6ffd21`:
brevard/I (writes claim, survived after reconciliation), brevard/I (ghost-success purge finding,
survived), jefferson/B, jefferson/F, holmes/B, holmes/C, holmes/D, holmes/F (all survived).

## Verification protocol followed

- `pencil_dod_evaluate_county` re-run live for all three counties, multiple times, before/during/after
  changes — every number in this report is a fresh live read, not a cached or remembered value.
- Independent ULTRALOOP refuter workflow (2 agents, isolated context) ran against this session's own
  claims. One claim was genuinely refuted on first pass; rather than either accepting the refutation
  uncritically or dismissing it, the underlying disagreement was resolved with fresh evidence
  (`pg_trigger` inspection + direct row re-selection), and the refutation's own trail surfaced a real,
  separate, pre-existing data-integrity bug that was fixed in the same session.
- No fabricated address, zone code, or value was written anywhere this session. Two candidate address
  matches (`CONFIDENTIAL` street name, and separately the 49-row ghost-success discovery) were
  identified as non-real and excluded/purged rather than written.

### SQL VERIFICATION

```sql
-- Brevard, live, 2026-08-02 ~16:40 UTC (post-purge, final state this session):
SELECT public.pencil_dod_evaluate_county('brevard');
-- I: {"pass": false, "detail": "card_complete=6028 of 7238", "metric": 83.3}
-- (all other 9 letters unchanged PASS)

-- Jefferson, live:
SELECT public.pencil_dod_evaluate_county('jefferson');
-- B: {"pass": false, "metric": null, "detail": "verified=0 closed_sold=0"}
-- F: {"pass": false, "metric": null, "detail": "tier1_sold=0 closed_sold=0"}

-- Holmes, live:
SELECT public.pencil_dod_evaluate_county('holmes');
-- B: {"pass": false} C: {"pass": false, "metric": 61.5} D: {"pass": false, "metric": 61.5}
-- F: {"pass": false}
```

Timestamp UTC: 2026-08-02T16:45Z (approximate, session close-out).

## Recommendation for future sessions

1. **Brevard I structural ceiling (~84%)**: further gains need per-municipality zoning GIS
   integration (Brevard has ~13 incorporated jurisdictions each with a separate zoning map beyond the
   county's own unincorporated-only layer) — a genuine substrate-build task, not another address/
   zoning-link sweep against the same two endpoints used this session and the 2026-07-30 session.
2. **Fleet-wide**: this session's ghost-success find (naive GIS-field concatenation writing sentinel
   values like `'UNKNOWN'`/`'CONFIDENTIAL'` as if real) is a pattern, not a one-off — worth a quick
   grep across other counties' `property_address` columns for the same `'0 UNKNOWN'`-style signature
   before trusting their I numbers.
3. **Jefferson**: do not re-fire before 2026-08-19 (tax deed sale date) / 2026-08-24 (next clerk cron).
4. **Holmes**: do not re-fire unless Firecrawl credits are confirmed restored (currently -4) or a
   genuinely new, non-Cloudflare-gated source is identified.

---
dispatch_id: a42bf937-8d85-46f9-8158-554d3d6ffd21
