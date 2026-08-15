#!/usr/bin/env python3
"""Manatee E/I fix -- dispatch 7ad7b689, shard-5, 2026-08-15.

ROOT CAUSE (VERIFIED live via PostgREST): 16 manatee case_numbers existed as
TWO multi_county_auctions rows each -- a bare stub in the clerk's own short
calendar format ("2025CA000550AX", parity_source='manatee_clerk_foreclosure',
no property_address/parcel_id/owner/financial data beyond case_number,
auction_date, sale_type, auction_status) and an already-enriched sibling row
in the 12th Judicial Circuit's long clerk form ("412025CA000550CAAXMA" = "41"
circuit prefix + the stub's own YYYY/TYPE/NNNNNN core + a repeated TYPE +
"AXMA" suffix), sourced from realtaxdeed/calendar_sweep_mca_v3 and already
carrying property_address/parcel_id/parity_status='matched_clean' or
'PARITY_OK'/tier1_authoritative.

This is the same duplicate-pair pattern already diagnosed and partially fixed
in scripts/manatee_cdei_dedup_and_parity_recheck_c5a7b6eb.py (2026-08-12/13,
19 pairs). It recurred because that fix was a one-time manual cleanup, not a
change to the ingestion pipeline itself: scripts/clerk_ssot/run_parity.py's
diff_and_reconcile() canonicalizes case-number formatting differences (a
"/"-split fallback, a zero-pad fallback) but had no rule recognizing the
manatee-specific short-vs-long wrapper shape. Every daily clerk_ssot run that
saw a manatee case get continued to a new sale date under the short-form
number re-created (or re-upserted) an empty stub instead of updating the
enriched sibling's auction_date, because canonicalization never connected the
two formats.

FIX APPLIED THIS SESSION:
  1. (this script's actions, PostgREST only, SUPABASE_SERVICE_ROLE_KEY)
     For each of the 16 pairs: copy the stub's auction_date (and, for the one
     case with auction_status='CANCELLED', its status/parity_status) onto the
     enriched sibling, then DELETE the stub row by id. Zero unique content
     lost -- every stub's only non-null fields beyond scrape bookkeeping were
     case_number/auction_date/sale_type/auction_status (verified per-row
     before deleting; see inline diagnostic run, not re-included here since
     this file documents actions already executed live).
  2. scripts/clerk_ssot/run_parity.py: added _MANATEE_SHORT_RE/_MANATEE_LONG_RE
     to _canonical_case() so future clerk_ssot runs recognize both wrapper
     shapes as the same case and update the existing enriched row's
     auction_date instead of creating a new duplicate stub. Purely additive --
     a no-op for every other clerk_ssot county (verified: no other county's
     case-number shape matches either new regex). Also added auction_date
     sync to the clean_matches reconciliation UPDATE, so a canonical-fallback
     match (case continued) actually corrects the surviving row's date
     instead of leaving it stale.

RESULT (VERIFIED live via pencil_dod_evaluate_county('manatee') before/after):
  before: auctions_total=180, E=89.4 FAIL(161) I=88.3 FAIL(159 of 180),
          A/B/C/D/F/G/H/J all PASS (8/10 overall)
  after dedup merge (16 pairs): auctions_total=164, E=98.2 PASS(161)
          I=97.0 PASS(159 of 164), A/B/C/D/F/G/H/J unchanged PASS (10/10)
  after 3-orphan backfill (below): E=100.0 PASS(164 of 164), I unchanged
          97.0 PASS(159 of 164) -- MANATEE CONFIRMED 10/10 LIVE

The 16 case_number pairs merged (short -> enriched sibling kept, new date):
  2025CA000550AX -> 412025CA000550CAAXMA  (2026-08-26)
  2024CA001288AX -> 412024CA001288CAAXMA  (2026-08-27)
  2025CC003179AX -> 412025CC003179CCAXMA  (2026-08-27)
  2024CA000296AX -> 412024CA000296CAAXMA  (2026-09-02)
  2025CA002937AX -> 412025CA002937CAAXMA  (2026-09-09)
  2025CA002616AX -> 412025CA002616CAAXMA  (2026-09-16)
  2023CA000253AX -> 412023CA000253CAAXMA  (2026-09-16)
  2023CA006592AX -> 412023CA006592CAAXMA  (2026-09-16)
  2025CA001253AX -> 412025CA001253CAAXMA  (2026-09-16)
  2024CA001322AX -> 412024CA001322CAAXMA  (2026-09-16)
  2025CC000720AX -> 412025CC000720CCAXMA  (2026-09-22, CANCELLED status synced)
  2023CA004855AX -> 412023CA004855CAAXMA  (2026-09-30)
  2018CA005016AX -> 412018CA005016CAAXMA  (2026-08-19)
  2023CA005803AX -> 412023CA005803CAAXMA  (2026-09-02)
  2024CA000409AX -> 412024CA000409CAAXMA  (2026-10-28)
  2025CC002885AX -> 412025CC002885CCAXMA  (2026-10-28)

3-ORPHAN BACKFILL (2025CA003113AX, 2025CC000770AX, 2024CA000642AX): these had
NO enriched sibling under any format -- genuinely new cases, live-confirmed
PENDING ONLINE on the clerk's own foreclosure-sale calendar
(records.manateeclerk.com), which carries zero property data itself (no
address, no plaintiff/defendant, no parcel). E/I were already PASS without
them (161/164 E, 159/164 I), so an ULTRALOOP research agent per case fetched
the actual Manatee Clerk case-detail page (POST /CourtRecords/Case/Details)
and the scanned Notice of Lis Pendens image/PDF for each -- the recorded
legal description + parcel/tax-ID, cross-verified against the Manatee County
Property Appraiser's own ArcGIS/JSON parcel search (manateepao.gov /
gis.manateepao.gov), never PropertyOnion. All 3 confidence=VERIFIED with
cited source URLs/document IDs (see the workflow's research-phase result for
full per-case evidence). Findings applied live via PATCH:
  2025CA003113AX -> parcel_id=401646309, 10460 Ladybug Cv, Parrish FL
    (owner Clarence & Karina Knight, matches Lis Pendens defendants exactly)
  2025CC000770AX -> parcel_id=500229009, 3771 Manorwood Loop, Parrish FL 34219
    (HOA lien foreclosure, owner match via legal description PAR_LEGAL1 query)
  2024CA000642AX -> parcel_id=731800009, address NOT found (PAO's
    parcel-search AJAX endpoint 200s with an empty body without a browser JS
    session; legal description + Tax ID from the recorded Lis Pendens PDF is
    sufficient to identify the parcel unambiguously, so parcel_id was written
    without a property_address -- this row correctly still does not count
    toward I's card_complete, which requires property_address non-null)
Result: E 98.2->100.0 (164/164, parcel_id now non-null on every in-scope row).
I unchanged at 97.0 (only 2 of the 3 orphans gained an address, and neither
has lat/long, assessed_value, or a resolved zoning-card parcel yet, so
neither counts toward card_complete -- I remains genuinely PASS, not gamed).

ADVERSARIAL VERIFY (ULTRALOOP, 3 independent refuters, 2026-08-15): the live
10/10 claim and the 16-pair dedup-safety claim both SURVIVED refutation
(refuters independently re-ran pencil_dod_evaluate_county and independently
re-derived the case-number-core match for all 16 pairs). The run_parity.py
regex-fix-no-regression claim was REFUTED as originally scoped: a refuter
found levy's and liberty's foreclosure CASE_RE
(^\d{2,4}-?\d*-?(CA|CC|TD)[A-Z0-9-]*$, both currently zero-live-card /
real-format-unverified) is loose enough to also match the new
_MANATEE_SHORT_RE/_MANATEE_LONG_RE patterns, and calhoun/lafayette-tax_deed
apply no case-number regex at all -- an unscoped fallback was a latent
collision risk for those 4 counties. Fixed by gating _canonical_case's new
branch on `county_slug == "manatee"` (see the diff in
scripts/clerk_ssot/run_parity.py) -- now a provable no-op for every other
county regardless of their real case-number shape, not just a
currently-observed one.

This file is investigation documentation + the exact steps applied (already
executed live this session); it is not meant to be re-run.
"""
