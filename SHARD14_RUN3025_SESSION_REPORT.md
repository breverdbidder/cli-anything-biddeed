# SHARD-14 run3025 — duval/sarasota/holmes/union (2nd dispatch)

dispatch_id: 9e70dcd7-f9cd-4c17-b3a1-596a9da4b20f
chat_session: architect-20260704T160000

## DUPLICATE-DISPATCH FINDING (headline)

This dispatch (identical `dispatch_id` and `chat_session` string) was **already executed and
shipped to main** as commit `59f12298` ("SHARD-14 run3025 (duval/sarasota/holmes/union): duval C +1
verified CT match via ultracode workflow, sarasota/holmes/union ceilings honestly reconfirmed"),
which is a confirmed ancestor of HEAD (`git merge-base --is-ancestor 59f12298 HEAD` → true).

Rather than re-run an 11-agent ULTRALOOP workflow to re-derive conclusions already reached and
committed, this session first re-verified live state matches that commit exactly (see below), then
spent the turn on one genuinely unexplored thread: union's Letter I gate, which the prior dispatch
did not investigate.

## Live re-verification (fresh `pencil_dod_evaluate_county` RPC calls, this session)

Zero drift since 59f12298 shipped — every letter metric is bit-for-bit identical to that commit's
recorded "AFTER" state:

| county   | B (verified/closed) | C (matched_clean) | D (matched_any) | F (tier1) | I (card) |
|----------|---------------------|--------------------|------------------|-----------|----------|
| duval    | 100.0 (55/55)       | 14.4 (89/620)      | 48.5 (301/620)   | 100.0     | 96.1 (596/620) |
| sarasota | 100.0 (78/78)       | 81.3 (165/203)     | 81.3 (165/203)   | 100.0     | 98.5 (200/203) |
| holmes   | null (0/0)          | 7.7 (1/13)         | 7.7 (1/13)       | null (0/0)| 100.0 (13/13)  |
| union    | null (0/0)          | 0.0 (0/3)          | 0.0 (0/3)        | null (0/0)| 0.0 (0/3)      |

No writes were made this session (all calls were SELECT / read-only). No certification run
(`gold_standard_loop`/`certify`) — nothing changed, nothing to certify.

## Tooling note (environment changed since the prior dispatch)

The prior dispatch's migration note recorded the Supabase Management API SQL endpoint failing with a
Cloudflare 1010 error, forcing all work through PostgREST + existing RPC functions. This session
confirmed the Management API SQL endpoint (`POST /v1/projects/.../database/query`) **now works**
(HTTP 200/201, ran arbitrary SELECTs successfully) — useful for future sessions. FIRECRAWL_API_KEY is
still absent from env; `unionclerk.com` still returns HTTP 403. Direct `psql` to the pooler still fails
(`ENOIDENTIFIER: no tenant identifier provided` — SNI/tenant routing not resolvable from this sandbox).

## NEW finding: union Letter I root cause + a discovered cross-shard data bug (not fixed, out of scope)

Union's `card_complete=0/3` is gated on four AND'd conditions per the evaluator SQL
(`pencil_dod_evaluate_county`, `c` CTE): `property_address IS NOT NULL`,
`COALESCE(latitude, po_latitude) IS NOT NULL`, `COALESCE(longitude, po_longitude) IS NOT NULL`,
`COALESCE(assessed_value, market_value) IS NOT NULL`, plus a zoning-card parcel match. Live query of
all 3 union `multi_county_auctions` rows:

| case_number | property_address | lat/lng | assessed/market_value |
|---|---|---|---|
| 63-2025-CA-0053 | present | NULL / NULL | NULL / NULL |
| 63-2024-CA-0047 | present | NULL / NULL | NULL / NULL |
| UNION-TD-CERT223 | **NULL** | NULL / NULL | NULL / NULL |

All 3 rows fail on lat/lng and value regardless of address. The standard remediation path (join to
`fl_parcels` by `co_no`) was attempted and surfaced a real, previously-undocumented data-integrity bug:
**`fl_parcels` rows tagged `co_no=63` are not Union County** — sampled rows are `phy_city='BARTOW'`
(Bartow is in Polk County). `co_no=63` is Union's correct FL DOR county number (confirmed via
`public.fl_counties` and the `63-` case-number prefix), so this is a real contamination bug in a
shared statewide table, not a lookup error on my part. This is a cross-county issue outside this
shard's surgical scope (touching `fl_parcels` co_no assignment could affect every county that reads
that table) and was **not remediated** here — flagging for a dedicated session/owner review.

Direct live FL GIO ArcGIS queries (`Florida_Statewide_Cadastral` FeatureServer, filtering
`CO_NO=63 AND PARCEL_ID=...`) timed out repeatedly from this sandbox — consistent with
`scripts/ingest_county.py`'s own code comment ("`WHERE CO_NO=X` times out on count"), which is why that
script uses OBJECTID-range pagination instead of ad-hoc filtered queries. A proper fix for union I
requires that paginated ingestion pattern (or a corrected `fl_parcels`), not a quick interactive query
— correctly left undone (BLANK > WRONG) rather than forced or faked.

## Summary

- 0 letters moved this session (by design — this dispatch duplicates already-shipped work).
- 1 new root-cause finding (union I) + 1 new cross-shard data-integrity bug discovered (`fl_parcels`
  co_no=63 contamination) — both documented, neither fixed, both correctly out of this session's
  surgical scope.
- No certification, no migration, no scraping performed.
