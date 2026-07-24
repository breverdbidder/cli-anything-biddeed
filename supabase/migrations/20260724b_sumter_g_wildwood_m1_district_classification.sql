-- Gold Standard sumter shard-7 (dispatch a3c9a3be-ebc2-4233-a784-3b405076bc63): G regression root-cause fix
--
-- Context: an in-session subagent (errored on structured-output formatting before it could
-- report, but the DB write it made was real and independently re-verified) added a
-- parcel_zones row for case 2025-CA-000255 / parcel D29A024 -> zone_code='M-1' (City of
-- Wildwood industrial zoning), sourced from Sumter County GIS ArcGIS FeatureServer:
--   https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/FLU_Zoning/FeatureServer/10
--   query PIN='D29A024' -> Zoning_Cur='M-1' (independently re-confirmed live, exact match)
--
-- This exposed that jurisdiction_id=950 (Wildwood) had no zoning_districts row for M-1.
-- v_zoning_gold_standard_kpi_v3 LEFT JOINs zoning_districts/v_zoning_district_applicability
-- and falls back to COALESCE(a.*_applicable, true) when no district match exists -- i.e. an
-- undefined district is conservatively treated as applicable-but-unmeasured for ALL of
-- density/FAR/parking at once, which dropped sumter G from PASS 100.0 to FAIL 0.0
-- (density=93.3 far=0.0 pk1000=0.0 -- the one M-1 parcel counted against all three
-- denominators with no standards on file).
--
-- Fix: define the M-1 district with its real classification (category='industrial', a
-- standard zoning-code classification, not a guessed numeric standard). This alone corrects
-- density (industrial districts are conventionally not density-regulated -> density_applicable
-- becomes false for this parcel, restoring density to 100.0 = 14 of 14 applicable).
--
-- FAR and parking-per-1000sf standards for Wildwood M-1 remain genuinely unsourced this
-- session -- left NULL, not guessed (BLANK > WRONG). Four independent access attempts to
-- Wildwood's Land Development Regulations all failed:
--   1. https://library.municode.com/fl/wildwood -- HTTP 403 to automated fetch
--   2. Live LDR PDF (wildwood-fl.gov/.../revised_ldr_adopted_11-23-20.pdf) -- Cloudflare
--      Turnstile "Just a moment..." challenge, confirmed via both WebFetch (403) and raw curl
--      with browser UA + referer (403, challenge page body)
--   3. Wayback Machine snapshot of the same PDF (which OTHER Wildwood rows in
--      v_zoning_gold_standard_card already cite successfully, e.g. D20G135/G05R062/G07F008/
--      G06F064 standards_source_url) -- unreachable from this sandbox: WebFetch explicitly
--      refuses web.archive.org URLs, and direct curl returns a proxy-level 498/404
--   4. Firecrawl API -- HTTP 402 "Insufficient credits"
-- Next session: retry once Firecrawl credits are available, or via a session with
-- browser-use/interactive JS rendering that can clear the Turnstile challenge, or search for
-- Wildwood's Table 3-4B (Commercial/Industrial standards, adjacent to the already-cited
-- Table 3-4A Residential and Table 3-4C Mixed Use in this same LDR) via an alternate mirror.
--
-- G is now an honest FAIL (density=100.0 far=0.0 pk1000=0.0) reflecting a real,
-- previously-hidden gap rather than a stale/lucky PASS based on an incomplete residential-only
-- parcel_zones sample. Reverting the (real, GIS-verified) D29A024 parcel_zones write to
-- artificially restore the PASS was considered and rejected -- that would suppress accurate
-- data purely to inflate a score, which is exactly what the fail-loud/ghost-success
-- guardrails in this repo exist to prevent.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
VALUES (
  950,
  'M-1',
  'Industrial (Wildwood)',
  'industrial',
  'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 10 Wildwood Zoning '
  '(Zoning_Cur=M-1), independently re-confirmed 2026-07-24 via direct ArcGIS query for '
  'PIN=D29A024 (https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/FLU_Zoning/'
  'FeatureServer/10). category=industrial is a classification, not a guessed numeric standard '
  '-- standard M-1/industrial-district convention (no residential density cap). FAR/'
  'parking-per-1000sf numeric standards NOT YET SOURCED: see migration header for the 4 '
  'independent access attempts that were all blocked. Left NULL rather than guessed.'
)
ON CONFLICT DO NOTHING;
