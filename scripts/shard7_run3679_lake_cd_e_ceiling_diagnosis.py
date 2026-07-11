#!/usr/bin/env python3
"""
Shard-7 run3679: Lake county C/D and E ceiling diagnosis (read-only, no writes).

Documents why C, D, and E did not move further this session, with live
evidence, so the next session doesn't re-spend budget re-discovering the
same ceiling.

C/D (matched_clean/matched_any, tier1-sourced parity):
  - All 11 tax-deed auctions are ALREADY matched_clean with a tier1 parity
    source (parity_source LIKE 'tier1:shard14_2a2b2667_ajax_harvest:...' or
    'tier1_po_mca_match_lake_20260703') -- TD lane is fully wired, 100%.
  - Of the 87 foreclosure auctions, only 18 have ANY PropertyOnion
    cross-reference in po_mca_matches (the only litmus source verified
    reachable for the FC lane -- Lake has no RealAuction/RealForeclose FC
    platform at all, confirmed live: lake.realforeclose.com's own county
    picker only lists "Lake Taxdeed", no "Lake Foreclosure" entry). All 18
    existing po_mca_matches rows are already wired to a tier1 parity_source
    (16 matched_divergent/matched_clean via tier1_po_mca_match_lake_20260703,
    2 via the TD ajax harvest). Net new FC matches available in po_mca_matches
    this session: 0.
  - Attempted a direct case_number join between our 87 FC rows and the 668
    archived county='lake' data_source='propertyonion' rows -- 0 matches
    (PO archive case numbers are synthetic 'PO-nnnnnnn' identifiers for the
    majority of rows, not the real court case number, so case_number join
    is not a viable additional matching path without a new fuzzy
    address/owner matcher -- out of scope for this session's DML-only
    mandate).
  - Lake Clerk's official-records search subdomain (or.lakecountyclerk.org)
    does not resolve from this environment (connection failure) and the
    public foreclosurecalendar.lakecountyclerkfl.gov page (used successfully
    for A/case-existence) does not publish bid/sale amounts or a
    machine-queryable historical ledger -- confirmed live, see
    shard7_run3679_lake_bf_realtaxdeed_probe.py.
  CONCLUSION: C=13.3%, D=27.6% are a genuine litmus-source-coverage ceiling
  for the FC lane this session, not an unwired-match backlog. Ceiling would
  require either (a) a new address/owner fuzzy matcher against the 668 PO
  archive rows (real scope, meaningfully larger than a data-backfill
  session), or (b) an authenticated Lake Clerk official-records session
  (not available in this environment).

E (parcel_linked, 74.5% = 73/98):
  - Re-ran scripts/shard14_lake_e_ownername_match.py --dry-run fresh against
    the 25 still-unlinked rows (all foreclosure, Clerk-calendar-only source
    with owner_name but no address/parcel). Result: 0 new unique matches.
    All 25 are either: ambiguous (2+ ArcGIS OwnerName candidates share the
    surname-position token -- e.g. multiple people/entities with the same
    surname), had 0 ArcGIS hits, or resolved to hundreds of seed hits with no
    surname-position survivor (common surname / LLC name with no individual
    owner match). This is the same conservative BLANK > WRONG matcher that
    found exactly 1 new match in the immediately preceding session --
    further gains from this specific method appear exhausted.
  CONCLUSION: E=74.5% is very likely at or near its real ceiling for the
  FC-Clerk-calendar lane given currently reachable data sources. Full
  documentation preserved in this diagnostic rather than silently
  re-attempting the same script next session without a new strategy.

No DB writes performed by this script (diagnosis only).
"""
print(__doc__)
