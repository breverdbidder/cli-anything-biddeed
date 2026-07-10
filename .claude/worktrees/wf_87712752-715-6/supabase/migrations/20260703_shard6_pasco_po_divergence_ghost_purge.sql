-- SHARD-6 (brevard, jackson, pasco, alachua, sumter) — pasco D ghost-divergence purge
-- dispatch_id: a21cf8eb-3760-4adb-85ae-d0af017bfa1a
-- Session: architect-20260703T000000 (continuation of run 2484)
--
-- FINDING: 26 pasco multi_county_auctions rows carry parity_status='matched_divergent'
-- with parity_source IN ('tier1_supplementary_shard6','tier1_realforeclose'), all on rows
-- still auction_status='upcoming'. Root-caused via one investigating pass + one
-- independent adversarial refuter agent (ULTRALOOP pattern, workflow wf_8e1c282b-33d):
--
--   1. public.refresh_parity_tier1_outcomes() -- the ONLY canonical writer of tier1_*
--      parity_source values -- only ever emits 'tier1_tax_deed_outcome' /
--      'tier1_foreclosure_outcome', and only ever touches rows with
--      auction_status IN ('redeemed','completed','sold','cancelled','canceled').
--      'upcoming' rows are categorically excluded from its output. So these 26 rows
--      cannot have been produced by the canonical matcher.
--   2. 'tier1_supplementary_shard6' is a renamed label (via
--      20260628_parity_source_tier1_prefix_17counties.sql) of the original
--      'shard6_loop581_supplementary_litmus' -- whichever script wrote that is not
--      present anywhere in the repo; its match logic cannot be audited.
--   3. Zero of the 26 rows have any match in foreclosure_outcomes or tax_deed_outcomes
--      for county=pasco, by parcel_id, normalized case_number, OR raw case_number
--      (checked all three, independently, twice).
--   4. All 26 rows have tier1_authoritative=false and tier1_verified_at=NULL -- they
--      fail the same tier1_verified_at/tier1_authoritative/parity_checked_at bar this
--      session already established and applied for pinellas/clay
--      (20260703_shard10c_pinellas_cd_realforeclose_aids_matches.sql).
--   5. parity_divergences on every one of the 26 rows is keyed on {"po": ..., "ours": ...}
--      (confirmed by direct inspection, e.g. auction_status: {"po":"Sold","ours":"upcoming"})
--      -- i.e. the divergence itself was computed against a PropertyOnion snapshot, not
--      against tax_deed_outcomes/foreclosure_outcomes. No live data_source='propertyonion'
--      row exists for these case_numbers to audit the snapshot against. This is the exact
--      PropertyOnion-as-data-source anti-pattern HARD GUARDRAILS #1 forbids, and the same
--      class of bug already caught+reverted this session for clay/lake/miami_dade/st_lucie.
--   6. Refuter found partial (not sufficient) backing for 4 of the 26 case_numbers in
--      public.realforeclose_aids (real case_number+parcel_id match, e.g.
--      51-2022-CA-001142-CAAX-WS -> parcel_id=10-25-16-0570-00000-3450,
--      "11817 ALPINE PKWY, PORT RICHEY, 34668") -- but realforeclose_aids has no
--      outcome/status column, so it can prove the case exists as a real listing, not
--      that a post-auction "matched_divergent" outcome classification is valid. Per the
--      house standard from item 4 (tier1_verified_at/tier1_authoritative required), this
--      thin backing does not clear the bar either. All 26 are reverted together for
--      consistency; none are matched_clean (no genuine-clean data is at risk).
--
-- EFFECT: D (matched_any) for pasco drops from the previously-reported 14.9% (29/195)
-- to the honest ~1.5% (3/195, matched_clean only) -- unchanged from before this session's
-- case-sensitivity fix. This is a correction, not a regression: the 14.9% figure was never
-- real.
--
-- Applied live via Supabase Management API 2026-07-03. This migration is the idempotent
-- record. Gated on a live NOT EXISTS check (not a hardcoded parity_source string) so any
-- row that legitimately gains real outcome-table backing in the future is left untouched.

UPDATE multi_county_auctions m
SET parity_status = 'mca_only',
    parity_source = NULL,
    updated_at = now()
WHERE lower(m.county) = 'pasco'
  AND m.parity_status = 'matched_divergent'
  AND NOT EXISTS (
    SELECT 1 FROM foreclosure_outcomes fo
    WHERE lower(fo.county) = 'pasco'
      AND (fo.parcel_id = m.parcel_id
           OR normalize_case_number(fo.case_number) = normalize_case_number(m.case_number))
  )
  AND NOT EXISTS (
    SELECT 1 FROM tax_deed_outcomes td
    WHERE lower(td.county) = 'pasco'
      AND (td.parcel_id = m.parcel_id
           OR normalize_case_number(td.case_number) = normalize_case_number(m.case_number))
  );

-- VERIFICATION QUERY:
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expected: C unchanged 1.5% (matched_clean=3), D drops from 14.9% to ~1.5% (matched_any=3)
