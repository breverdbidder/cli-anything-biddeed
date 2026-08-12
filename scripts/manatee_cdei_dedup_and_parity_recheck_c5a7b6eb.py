#!/usr/bin/env python3
"""Manatee C/D/E/I dedup + parity recheck -- dispatch c5a7b6eb, shard-2 (franklin/manatee).

ROOT CAUSE (VERIFIED live via PostgREST, 2026-08-12): 19 manatee case_numbers
existed as TWO multi_county_auctions rows each -- a sparse row in the clerk's
own short calendar format (e.g. "2025CA002937AX", data_source=NULL,
parity_source='manatee_clerk_foreclosure', no parcel_id/address/geo/value)
and a fully-enriched sibling row in the tier1 format (e.g.
"412025CA002937CAAXMA", data_source='realtaxdeed' or 'calendar_sweep_mca_v3',
parcel_id/address/geo/value all populated). Same real-world auction, same
parcel, same auction_date -- confirmed by a unique constraint violation
(uq_mca_county_sale_date_parcel) when 3 of the 19 sparse rows were briefly
patched with the sibling's parcel_id.

This is the identical root-cause pattern already diagnosed and fixed for
suwannee in scripts/suwannee_cdeij_dedup_orphan_merge_20260811.py (two
ingestion pipelines writing case_number in different formats for the same
real sale). That fix's precedent: DELETE the sparse orphan row, keep the
enriched sibling, and if the orphan-detection logic had flagged the sibling
PHANTOM_NOT_ON_CLERK (because the parity checker only recognized the sparse
row's format as clerk-confirmed), re-verify and correct the sibling's
parity_status with fresh live evidence.

STEPS APPLIED THIS SESSION (PostgREST only, SUPABASE_SERVICE_ROLE_KEY):
  1. DELETE 19 sparse orphan rows by verified id (each confirmed to have
     zero data not already present on its enriched sibling; no FK references
     multi_county_auctions.id in any migration). auctions_total 181 -> 162.
  2. PATCH 3 sibling rows previously parity_status='PHANTOM_NOT_ON_CLERK'
     (412025CC004086CCAXMA, 412026CA000001CAAXMA, 412026CA001304CAAXMA) ->
     'PARITY_OK'. Live-reverified against records.manateeclerk.com/
     CourtRecords/Search/ForeclosureSales this session: all 3 case numbers
     DO appear on the live clerk calendar (CANCELLED/SOLD status) --
     "PHANTOM_NOT_ON_CLERK" was itself the bug, caused by the parity checker
     only recognizing the sparse-row case_number format.
  3. PATCH 2 sibling rows previously parity_status='matched_divergent'
     (412025CA001253CAAXMA $190,121.62, 412025CA002616CAAXMA $216,445.23) ->
     'PARITY_OK'. Live-reverified against records.manateeclerk.com: both show
     PENDING ONLINE with judgment amounts matching our DB exactly. The
     original divergence notes were against manatee.realforeclose.com's
     DAYLIST, which returns 403 as of this session -- the Clerk's own site is
     the live-reachable independent source and shows no divergence.
  NOT touched (documented residual, not silently fixed):
     - 412025CA001812CAAXMA (PHANTOM_NOT_ON_CLERK): has its own bare sibling
       "2025CA001812AX" with a DIFFERENT auction_date (2026-10-28 vs
       2026-08-12 on the CAAXMA row) -- likely a genuine reschedule, not a
       clean duplicate pair. Needs a dedicated docket check before touching.
     - 4 CLERK_SSOT_CANCELLED rows: live-reverified on the clerk calendar,
       genuinely cancelled (reasons SATISFIED / JUDGE ORDERED CANCELLATION /
       JUDICIAL ORDER x2) -- the label is correct, not a bug. Whether a truly
       cancelled sale should count in the C/D denominator at all is an
       evaluator-scope question, out of this session's authority (canon SQL
       in pencil_dod_evaluate_county is not to be modified per campaign
       rules).

RESULT (VERIFIED live via pencil_dod_evaluate_county('manatee') before/after):
  before this script's steps (but after this session's earlier real-J fix
  and partial E backfill): auctions_total=181, C=94.5 FAIL(171) D=97.8 E=87.8
  FAIL(159) I=68.0 FAIL(123) J=100.0
  after: auctions_total=162, C=97.5 PASS(158) D=99.4 PASS(161) E=88.3
  FAIL(143) I=66.7 FAIL(108) J=100.0 PASS
  Manatee moved from 7/10 to 8/10 this session (C flipped PASS, J already
  flipped PASS via the earlier real-inference generator run). Only E and I
  remain, both needing genuine external research (19 case numbers with zero
  address on file, ~36 parcels absent from the zoning GIS layer) -- out of
  scope for a mechanical script, handed to the ULTRALOOP research workflow.

This file is investigation documentation + the exact steps applied (already
executed live this session); it is not meant to be re-run.
"""
