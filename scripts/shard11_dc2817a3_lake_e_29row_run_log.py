#!/usr/bin/env python3
"""SHARD-11 (dispatch dc2817a3): lake county, letter E parcel-linkage re-run.

Read-only evidence log (no matching logic here -- this documents the results
of a REAL (non-dry-run) execution of the existing, unmodified
scripts/shard14_lake_e_ownername_match.py against the current 29 unlinked
lake foreclosure rows, run 2026-07-31.

BASELINE (fetched live via pencil_dod_evaluate_county('lake') before this run):
  auctions_total=109, E.metric=73.4%, E.detail="parcel_linked=80"
  (29 = 109 - 80 unlinked, all data_source='lake_clerk_foreclosure_calendar_v1')

CANDIDATE SET (live query, county=lake, parcel_id IS NULL, script's own
tier1/non-propertyonion filter): 29 rows, all lake_clerk_foreclosure_calendar_v1.

  - 21 rows created_at='2026-07-02' -- this is the batch that was already
    dry-run-tested by the prior session's ceiling diagnosis
    (scripts/shard7_run3679_lake_cd_e_ceiling_diagnosis.py, ~2026-07-19,
    which described "25 unlinked" at that time; the live set has since
    narrowed to this 21-row remainder of that same batch). REPEAT attempts.
  - 8 rows created_at in {2026-07-10, 2026-07-14, 2026-07-15, 2026-07-16,
    2026-07-18} -- created AFTER the prior diagnosis ran, so NEVER
    previously attempted by this matcher:
      2023CA002935  2026-07-10  UNKNOWN HEIRS OF TERRY G. TAYLOR, ET AL
      2025CA002336  2026-07-10  PATRICK ROLLE, ET AL
      2025CA001392  2026-07-10  ASHLY DUHAMELL, ET AL
      2025CA001205  2026-07-14  DANILO HENRIQUE GARCIA DA SILVA, ET AL
      2025CA002823  2026-07-15  UNKNOWN SUCCESSOR TRUSTEES OF THE NUMA J. PILLION ...
      2025CA002017  2026-07-15  CHERYL M. VELTING, ET AL
      2025CA001886  2026-07-16  AMBER JANE PRESCOTT ET AL
      2025CA000251  2026-07-18  UNKNOWN TRUSTEE OF THE CLERMONT REALTY 2022 TRUST, ...

EXECUTION: `python3 scripts/shard14_lake_e_ownername_match.py` (no --dry-run,
i.e. live PATCH attempts enabled). Script unmodified from repo HEAD.

RESULT: candidates=29 matched=0 skipped=29. Breakdown of the 8 NEW rows:
  - 2 ambiguous_2_surname_position_hits (ASHLY DUHAMELL; NUMA J. PILLION trust
    -- wait, see full receipt: actually TERRY G. TAYLOR and ASHLY DUHAMELL
    were the two ambiguous_2 results among the new rows)
  - 6 no_surname_position_match_of_N_seed_hits / no_hits (common surname or
    trust/LLC name with zero individual-owner ArcGIS survivor)
  0 of the 8 new rows produced a unique ArcGIS OwnerName match.

Full 21 repeat rows: same 0/21 result as the prior session's dry-run
diagnosis (all still no_hits / ambiguous / no-surname-position-match) --
consistent, not a regression, confirms the matcher's ceiling is stable
against re-fetch of live ArcGIS data (not a stale-cache artifact).

POST-RUN VERIFICATION (fresh pencil_dod_evaluate_county('lake') call):
  auctions_total=109, E.metric=73.4%, E.detail="parcel_linked=80"
  IDENTICAL to baseline -- confirms 0 DB writes landed (consistent with
  0 unique matches; the script only PATCHes on a unique survivor).

CONCLUSION: E=73.4% (80/109) is a genuine ceiling for the
owner-name-vs-ArcGIS-FieldMap method against the current live Lake PA
ArcGIS data, for BOTH the previously-attempted 21-row remainder AND the
8 rows that had never been attempted before. No further gain is available
from this method without a materially different data source (e.g. an
authenticated Lake Clerk official-records session for defendant addresses,
or a different property-appraiser dataset) -- out of scope for this
dispatch (script-logic changes toward "less conservative" matching were
explicitly disallowed and would violate BLANK > WRONG).

No DB writes performed by this script (log/diagnosis only). The live writes
(zero of them, since zero unique matches) happened inside the unmodified
shard14 script itself, not here.
"""
print(__doc__)
