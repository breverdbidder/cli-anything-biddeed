#!/usr/bin/env python3
"""Read-only evidence log — Lake county letter J root-cause investigation
(dispatch shard11 dc2817a3). NOT a generator. Does not write to any table.

QUESTION POSED BY THE DISPATCH: scripts/shard2_lake_j_generator_real_v2.py's
docstring claims "auctions_total=109, deal_complete=98 before this fix" for
its own 11-row scope, yet the live baseline today is only 80/109 -- an
apparent ~18-row regression. Investigate before generating anything new.

ROOT CAUSE (CONFIRMED, not a regression at all -- a subsequent honest
correction within the SAME 2026-07-24 session that the "98" figure is
quoted from):

1. On 2026-07-19 (commit b532816f), lake J was reverted from a fabricated
   100%/108 (raw assessed_value * 0.65 ghost formula) down to an honest
   90.7% / deal_complete=98 of 108. This "98" is the number quoted in both
   shard2_lake_j_generator_real_v2.py's docstring and
   shard2_lake_j_ghost_purge_full_regen.py's docstring as the "before this
   fix" baseline -- it was already stale by the time either script's
   docstring was written.

2. On 2026-07-24 (commit 4a274321, session run 6148), the SAME session that
   wrote both scripts ran scripts/shard2_lake_j_generator_real_v2.py FIRST
   (11-row scope), which appeared to reach 100% -- but its own adversarial
   refuter caught that this "100%" was a false positive: 97 PRE-EXISTING
   bid_decisions rows outside its 11-row scope (written by an even earlier
   session's scripts/shard7_lake_j_generator.py) carried a constant
   ml_score=0.5500 ghost-success stub with placeholder factor values
   (distress_owner='unknown', distress_location=literal county name,
   distress_property=literal sale_type) that satisfied the evaluator's
   JSON-key-presence check without reflecting a real deal thesis.

3. The SAME session then ran scripts/shard2_lake_j_ghost_purge_full_regen.py
   (108-row union scope = the original 11 + the 97 ghost rows) as the
   corrective fix:
     - 79 rows had real assessed_value/market_value -> real per-property
       XGBoost inference, UPDATEd with genuine values.
     - 29 rows had NO real assessed_value/market_value at all (parcel_id
       IS NULL, no ArcGIS owner-name match found) -> per HARD RULES
       (never fabricate), these were explicitly NULLed
       (pipeline_version suffix '_nulled_no_real_arv') rather than left
       with the stale ghost values.
     - 3 stale ghost duplicate rows were deleted.
   Documented live in supabase/migrations/20260724v_shard2_lake_j_ghost_purge_full_regen.sql,
   which states explicitly:
     "BEFORE (fabricated-100%, adversarially refuted): deal_complete=109 of 109
      AFTER (honest, live-verified): deal_complete=80 of 109 (73.4%)"

CONCLUSION: there was no external regression, no schema change, and no
denominator growth outpacing coverage. The "80 of 109" baseline this
dispatch was handed IS the corrected, honest number the 2026-07-24 session
itself produced and documented -- it just postdates the "98" figure quoted
in the two scripts' docstrings (which describes an intermediate, since-
refuted state from earlier in that same session, before the ghost-purge
ran). The dispatch's "regression" framing was a false alarm caused by
reading a stale in-code comment instead of the live evaluator + migration
record.

FRESH VERIFICATION (this session, 2026-07-31, read-only queries only):

  pencil_dod_evaluate_county('lake') -> J: pass=false, metric=73.4,
    detail="deal_complete=80", auctions_total=109 (byte-identical
    before/after this investigation -- zero writes made)

  Evaluator's exact J-scope denominator (from
  supabase/migrations/20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql):
    SELECT case_number FROM multi_county_auctions
    WHERE lower(county)='lake'
      AND (data_source <> 'propertyonion' OR tier1_authoritative = true)
  -> live query returns exactly 109 distinct case_numbers, matching
     auctions_total=109 exactly (confirmed by direct REST query against
     multi_county_auctions, not assumed).

  bid_decisions for those 109 case_numbers: 112 rows exist (3 case_numbers
  -- 2025CA001088, 2025CA001532, 2025CA002292 -- carry a genuine duplicate:
  one row from the 2026-07-24 ghost-purge run with real Shapira V14 factors,
  and one newer row from a DIFFERENT, later, unidentified process with
  pipeline_version=NULL, ml_score=0.58 constant, "sources":["market_value_proxy"]
  / ["assessed_value_proxy"] tagged factors -- also a live, complete, non-
  fabricated-looking row structurally, just from an unknown later writer.
  Both twins independently satisfy the EXISTS-based J predicate, so this
  duplication does NOT affect the metric (deal_complete counts a
  case_number once regardless of how many qualifying rows exist) -- flagged
  here only as a data-hygiene observation, NOT fixed (out of this
  investigation's scope, no instruction to dedupe was given).

  The 29 case_numbers still failing J (all carrying
  pipeline_version='lake_j_ghost_purge_full_regen_shard2_shapira_v14_real_nulled_no_real_arv',
  i.e. explicitly NULLed by the 2026-07-24 fix itself) were cross-checked
  fresh against multi_county_auctions:
    - all 29 have parcel_id IS NULL (100% overlap with letter E's
      documented 29-row unlinked ceiling, confirmed independently in this
      session's fresh E re-run: "parcel_linked=80, 29 unlinked")
    - all 29 have assessed_value IS NULL AND market_value IS NULL AND
      latitude IS NULL -- zero real valuation or geocode input of any kind
    - all 29 have property_address IS NULL -- only owner_name and
      case_number exist (data_source='lake_clerk_foreclosure_calendar_v1'),
      which is exactly the input surface this session's E matcher
      (scripts/shard14_lake_e_ownername_match.py) already exhausted this
      session with 0/29 unique matches.

DECISION: no new bid_decisions rows were generated. Generating real ARV
requires a linked parcel with assessed_value/market_value on file; none of
the 29 gap rows have one, and E (run fresh earlier this session, same
dispatch chain) already confirmed this is a genuine, currently-unresolvable
linkage ceiling -- not a data-entry gap this script could close without
fabricating a value, which HONESTY PROTOCOL / BLANK > WRONG forbids.

pencil_dod_evaluate_county('lake') fresh before this investigation:
{"J":{"pass":false,"detail":"deal_complete=80 (triangle + two-arm CMA + ml_score + max_bid)","metric":73.4},"auctions_total":109}

pencil_dod_evaluate_county('lake') fresh after this investigation:
{"J":{"pass":false,"detail":"deal_complete=80 (triangle + two-arm CMA + ml_score + max_bid)","metric":73.4},"auctions_total":109}

No DB writes performed by this script or this session. This file is
evidence-only, per the required unique-filename convention for this
dispatch (shard11_dc2817a3_*).
"""
