# Gold Standard shard-4: st_johns, nassau — session report

dispatch_id: `6284f4fc-ce46-4f84-bb14-a92199aa0dcf`
Date: 2026-09-01

## Result: st_johns unchanged 9/10 (genuine, triply-reconfirmed ceiling on C). **nassau 6/10 → 10/10.**

```
BEFORE (verified live at session start):
st_johns: A55 B100 C95.0(FAIL,113/119) D100 E100 F100 G100 H0.0 I100 J99.2 -> 9/10
nassau:   A19 B100 C85.7(FAIL,48/56) D85.7(FAIL,48/56) E94.6(FAIL,53/56) F100 G97.4 H0.0 I83.9(FAIL,47/56) J98.2 -> 6/10

AFTER (verified live at session end):
st_johns: unchanged, 9/10 (H drifted 0.0->0.1, still well within 48h SLA, still PASS)
nassau:   A19 B100 C100(PASS,56/56) D100(PASS,56/56) E100(PASS,56/56) F100 G97.7 H0.1 I96.4(PASS,54/56) J98.2 -> 10/10
```

## st_johns C — genuine ceiling, light re-confirmation only (no full re-investigation)

Per the brief's explicit instruction not to re-litigate this well-established gap (already
independently re-investigated with high scrutiny twice in the prior 24h — dispatch `b992b7ec`
08:27Z and dispatch `9aa28d35` ~16:50Z, both 2026-08-31), this session did exactly the
narrow scope requested:

1. Ran `pencil_dod_evaluate_county('st_johns')` fresh — confirmed C is still exactly
   `matched_clean=113` of 119 (95.0%, unrounded 94.958%), unchanged from the brief.
2. Confirmed case numbers `TD26-0059` / `TD26-0078` unchanged via a `multi_county_auctions`
   query (parcel_ids `2040600000` / `1829430450`, both `CLERK_SSOT_CANCELLED`).
3. Re-fetched both live via the `apps.stjohnsclerk.com/TaxSmart` `GridSearchData` grid
   (session-cookie POST-then-GET flow, browser UA) across all 8 non-SALE status buckets.
   Both cases found: `TD26-0059` -> parcel `204060-0000`, status **REDEEMED**.
   `TD26-0078` -> parcel `182943-0450`, status **REDEEMED**. Both match the DB's
   `CLERK_SSOT_CANCELLED` exactly. Zero drift since the last check ~15h earlier.
4. Diffed the full A-J object before vs after byte-for-byte against the prior session's
   confirmed AFTER state (dispatch `9aa28d35`) — all 10 letters identical (H's 0.0->0.1
   drift this session is trivial freshness-clock movement, not a regression). No
   silent regression found on any previously-passing letter.

No write made to st_johns this session (consistent with genuine-ceiling status).

## nassau — C/D/E/I backlog enrichment, 6/10 -> 10/10

**Root cause:** nassau reached a fully-verified, adversarially-confirmed 10/10 on
2026-08-11 (dispatch `14cdfac9`, `auctions_total=47`). By this session, `auctions_total`
had grown to 56 — 9 new rows ingested by the calendar-sweep pipeline since certification,
none enriched. This was fresh backlog work on new rows, not a re-emergence of the old
structural gap, using the same proven playbook from the Aug 11 session.

**FABRICATION CAUGHT AND FIXED (before any other work):** 3 of the 9 new rows
(`26TD000019AXYX`, `26TD000020AXYX`, `26TD000021AXYX`) carried an identical
`assessed_value=320000` / `market_value=336000` pair with `assessed_value_source=NULL` —
the exact same fabrication signature purged once before in this county
(`scripts/shard2_nassau_run14cdfac9_fabricated_value_purge.py`, 15 rows, 2026-08-11
session). Verified independently via a fresh PostgREST query (not trusting any
cached/injected context). Per guardrail #3 (BLANK > WRONG), this placeholder pair was
nulled rather than propagated.

**E fix (3 rows, 53/56 -> 56/56):** Real `parcel_id` + `property_address` sourced live
from `nassau.realtaxdeed.com` PREVIEW pages (case matched via the embedded 6-digit TD
sequence number, same mechanism as `scripts/shard2_bay_nassau_run14cdfac9_e_backfill.py`):
- `26TD000019AXYX` -> `01-6N-29-V28T-2511-0000`, "2511 BOXWOOD LN, FERNANDINA BEACH, FL"
- `26TD000020AXYX` -> `01-6N-29-V28T-2530-0000`, "2530 BOXWOOD LN, FERNANDINA BEACH, FL"
- `26TD000021AXYX` -> `00-00-31-150F-0008-0050`, "404 S 17TH ST, FERNANDINA BEACH, FL"

Real WGS84 lat/lon (outSR=4326) and zoning sourced from the Nassau County PA ArcGIS
layer 144. 2511/2530 are individual condo units (Tennis Villas) under a shared master
PIN with `JUSTVAL=0`/`FASMP_ASSD_VALUE_NS=0` in this GIS layer — genuinely absent, left
`assessed_value=NULL` rather than fabricated (these 2 rows correctly still fail I as a
result — honest gap, not fixed). 150F-0008-0050 had a real assessed_value (100758) and
was written. All 3 parcels zone-linked into `parcel_zones` (PUD x2 @ jurisdiction 1508
Unincorporated Nassau County, R-1 x1 @ jurisdiction 865 Fernandina Beach) —
pre-verified both zone codes already have `zoning_districts` rows for these
jurisdictions before writing, avoiding the documented G-regression trap.

**C/D fix (8 rows, 48/56 -> 56/56):**
- `26TD000009AXYX`, `26TD000013AXYX`: carried `parity_status='PHANTOM_NOT_ON_CLERK'`.
  Live re-verified on `nassau.realtaxdeed.com` PREVIEW pages for their exact auction
  dates — both ARE listed live with parcel_id exactly matching the DB
  (`00-00-30-0254-0005-0000`, `00-00-31-1800-0161-0080`). This was a mislabel (same
  bug pattern documented 2026-07-04), not a real phantom. Corrected to `PARITY_OK`.
- `452025CA000317CAAXYX`, `452025CA000437CAAXYX`, `452025CC000274CCAXYX`,
  `452025CC000614CCAXYX`, `452026CA000074CAAXYX`: 5 foreclosure rows ingested
  2026-08-28, never parity-checked (`parity_status IS NULL`). Live re-verified on
  `nassauclerk.realforeclose.com` / `nassau.realforeclose.com` PREVIEW pages for their
  auction dates (2026-09-03, 2026-09-10) — all 5 exact parcel_id matches. Corrected to
  `PARITY_OK`.
- `452026XX000010TDAXYX`: 1 tax_deed row ingested 2026-09-01 (same day), never
  parity-checked. Live re-verified on the same-date `nassau.realtaxdeed.com` PREVIEW
  page — exact parcel_id match. Corrected to `PARITY_OK`. (This row's card fields —
  parcel_id/address/lat-lon/assessed_value=0/zone-link — were already populated by a
  concurrent fleet session working the same dispatch_id; not duplicated here, see below.)

**I fix (47/56 -> 54/56, 2 rows remain genuinely incomplete):** the R-1 zone link for
150F-0008-0050 plus a concurrent fleet session's independent zone-linking of the 5
foreclosure parcels (OR x3, PUD x1, RM x1, all jurisdiction 1508, all pre-verified
against existing `zoning_districts` rows) combined to move I from 47 to 54 of 56. The 2
remaining I-failures are `26TD000019AXYX`/`26TD000020AXYX` — correctly still failing
because `assessed_value`/`market_value` are honestly `NULL` (see fabrication note
above), not force-passed.

## Parallel-fleet note

Mid-session, a companion migration file appeared already staged in git
(`migrations/20260901b_gold_standard_shard4_nassau_cdi_backlog_parity_zone_fix.sql`),
explicitly documenting itself as a **concurrent session working the same dispatch_id**.
Its parity-status UPDATEs for the 8 C/D rows were superseded by this session's writes
(confirmed: the live DB carries this session's `parity_source` tags on all 8, not the
other file's), but its 5 `parcel_zones` INSERTs for the foreclosure parcels DID land and
are real, verified, complementary work — confirmed live in the DB with their own
`shard4_6284f4fc_nassau_ncpa_arcgis_land_parcels_144` source tag. Per PARALLEL-FLEET
RULES ("other concurrent shard sessions may land unrelated commits mid-session, that is
normal, do not investigate or revert them"), this was treated as normal fleet behavior —
not reverted, not re-litigated. Final evaluator numbers reflect the true combined live
state of both sessions' writes, re-verified fresh by this session before reporting.

### SQL VERIFICATION
```
nassau BEFORE: {"C":{"metric":85.7,"detail":"matched_clean=48"},"D":{"metric":85.7,"detail":"matched_any=48"},
                "E":{"metric":94.6,"detail":"parcel_linked=53"},"I":{"metric":83.9,"detail":"card_complete=47 of 56"},
                "auctions_total":56}
nassau AFTER:  {"C":{"metric":100.0,"detail":"matched_clean=56"},"D":{"metric":100.0,"detail":"matched_any=56"},
                "E":{"metric":100.0,"detail":"parcel_linked=56"},"I":{"metric":96.4,"detail":"card_complete=54 of 56"},
                "auctions_total":56}
```
Timestamp: 2026-09-01T08:1X-08:2X UTC (`pencil_dod_evaluate_county('nassau')` via
PostgREST RPC, re-run fresh multiple times through the session, final confirmation run
included above). G checked before/after every write (97.4% -> 97.5% -> 97.7%, monotonic
non-decrease, no regression trap triggered — every new zone code pre-verified against
`zoning_districts` before writing).

## Fleet coordination

Per PARALLEL-FLEET RULES: touched only `st_johns` (read-only) and `nassau`
(`multi_county_auctions` parity_status/parcel_id/property_address/latitude/longitude/
assessed_value/market_value columns, `parcel_zones` inserts). Did not run
`gold_standard_loop()` or `gold_standard_certify()`. Did not touch cron jobs 109/111/115.
`git pull --rebase` performed before push (see commit log for any concurrent commits
picked up).

## Migration files

- `migrations/20260901_gold_standard_shard4_nassau_e_i_calendar_sweep_3row_backfill.sql`
  (this session, E fix + C/D parity corrections for the 8-row gap)
- `migrations/20260901b_gold_standard_shard4_nassau_cdi_backlog_parity_zone_fix.sql`
  (concurrent fleet session, same dispatch_id, complementary zone-linking work — retained
  as-is per PARALLEL-FLEET RULES, not authored by this session but its DB effects were
  independently re-verified live before being included in this report's final numbers)

## Next-session priorities

1. **st_johns C**: still no honest lever on the current 119-row baseline (1-row gap, all
   6 candidates independently reconfirmed genuine redemptions/cancellations three times
   now across 24h). Do not re-fire routine re-diagnosis until the source data itself
   changes (a new row lands, or a status flips on the clerk site).
2. **nassau I (54/56)**: 2 remaining rows (`26TD000019AXYX`, `26TD000020AXYX`, Tennis
   Villas condo units under a shared master PIN) have no real assessed_value/market_value
   in the county PA ArcGIS layer (JUSTVAL/FASMP_ASSD_VALUE_NS both genuinely 0 for the
   master PIN). A future session could try the clerk's own tax-deed certificate record
   (which sometimes carries an assessed value independent of the PA's per-unit GIS
   record) as an alternative real source before accepting this as a structural ceiling.
3. Nassau is now 10/10 again — worth a fast freshness-only recheck in ~24h given the
   pattern of new-row backlog appearing between certifications (auctions_total grew
   47->56 in 3 weeks; expect further growth).
