-- Gold Standard shard-2 (dispatch df5a4f3a-b78a-493b-976e-6081a988c1ae): osceola, letters G and I.
--
-- osceola has the deepest prior history of any county in this campaign (~12 prior sessions,
-- see 20260711t/20260719/20260724[_qrs]/20260725[_f]/20260731[_dgm]/20260802[_bc] migrations).
-- This session's job per dispatch brief: find the SPECIFIC residual gap remaining right now,
-- not redo generic GIS backfills that already ran.
--
-- ================================================================================
-- BASELINE (fresh live query, this session, via pencil_dod_evaluate_county('osceola')):
--   G: FAIL detail="density=90.7 far= pk1000=78.6" metric=78.6
--   I: FAIL detail="card_complete=127 of 137" metric=92.7
--   auctions_total=137
-- ================================================================================
--
-- G ROOT CAUSE (re-derived live via the v_zoning_gold_standard_kpi_v3 view's own `pj` CTE,
-- listing exactly which osceola parcels are applicable-but-null):
--   pk1000 (14 applicable, 11/14=78.6%): all 3 gap parcels sit on zoning_districts.id=13180
--     (Kissimmee SRPUD) -- SAME single district identified and left genuinely blocked by the
--     2026-07-31 and 2026-08-02 sessions (Municode/Kissimmee.gov 403 Akamai WAF, Firecrawl out
--     of credits). NOT re-attempted with a new lever this session beyond a fresh confirm below.
--   density (54 applicable, 49/54=90.7%): 5 gap parcels across 3 known-blocked districts
--     (T4-R id=13389, T5-U id=13390, MUPUD id=13391 -- documented residuals from 2026-08-02,
--     Ch.14-5 Form-Based-Code table + FLU-formula genuinely unreachable) PLUS 2 parcels on
--     zoning_districts.id=13226 "RS-2 Residential Single Family" (Osceola County unincorporated)
--     -- THIS IS THE NEW FINDING. District 13226 was created 2026-07-31 with category/far_regulated/
--     density_regulated set but its description explicitly flagged "density inferred from category
--     precedent... INFERRED not VERIFIED -- flagged for a future session with working web access to
--     pull the exact Table 3-4 density figure." It had ZERO zone_standards row (no max_density_du_acre)
--     until this session -- a genuinely closeable gap that prior sessions had flagged but not closed.
--
-- FIX APPLIED (VERIFIED via zoneomics.com/code/osceola-county-unincorporated-FL/chapter_5, live
-- WebFetch this session -- same accessible mirror used successfully for RS-3/R-1/RA-1/RA-2 on
-- 2026-08-02, since official osceola.org and library.municode.com remain 403-blocked):
--   RS-2 (13226) is a "preceding zoning district" per Ch.3 Table 3.2 (Preceding Zoning District
--   Development Standards Matrix), same table RS-3/R-1 came from: min lot 10,000 sq ft, min lot
--   width 85 ft, max height 2 stories. No explicit du/acre figure in the table (same pattern as
--   RS-3/RA-1/RA-2) -- density DERIVED as 43,560/10,000 = 4.30 du/acre, using the identical
--   derivation methodology already accepted for the 4 sibling preceding/single-family districts
--   on 2026-08-02. confidence_score=0.6 (matches the derived-not-explicit sibling rows).
--
-- RESULT (VERIFIED via pencil_dod_evaluate_county('osceola'), live, this session):
--   G: density 90.7 -> 94.4 (real, verified). G overall STILL FAIL -- pk1000=78.6 remains the
--   binding constraint (LEAST(density,far,pk1000)), untouched by this fix since RS-2 has no
--   pk1000 applicability. No pass-to-fail flip either direction.
--   I: unchanged at 92.7 (127/137) -- not touched this session, see residual below.
--
-- ================================================================================
-- G RESIDUAL (CONFIRMED STILL BLOCKED, fresh channels tried this session, no new lever found):
--   T4-R/T5-U/MUPUD density + SRPUD pk1000, same 4 districts flagged blocked on 2026-08-02.
--   Fresh attempts this session:
--     - zoneomics.com/code/kissimmee-FL/chapter_5 and chapter_7 fetched live: confirmed these
--       zoneomics chapter numbers actually map to Kissimmee LDC Sec 14-4-5 (use-permission
--       tables) and Sec 14-4-7 (overlay districts text), NOT the real Form-Based-Code Ch.14-5
--       (Table 5-2 Transect Zone Dimensional Standards) or the real parking Ch.14-7 numeric
--       ratios -- zoneomics simply does not mirror those chapters, confirmed by content, not
--       assumed.
--     - images1.showcase.com Ch.14-5 PDF (a fresh URL/token surfaced via WebSearch this session,
--       different from the one the 2026-08-02 session tried) -> HTTP 403 Akamai WAF, same
--       failure as before.
--     - Firecrawl credit balance re-checked live via GET api.firecrawl.dev/v2/team/credit-usage:
--       still -4/1000 (unchanged, billing period resets 2026-08-28).
--     - browser-use CLI: confirmed not installed (`which`/`command -v` both exit 1).
--   Did NOT write any numeric value or applicability override for these 4 districts --
--   genuinely source-exhausted, not fabricated.
--
-- I RESIDUAL (CONFIRMED STILL BLOCKED, fresh channels tried this session, no new lever found):
--   Same 10 property_card_complete gap rows as the 2026-08-02 session (case_numbers:
--   2025 CA 001721 MF, 35922022, 41922024, 48132023, 27092022, 40652024, 58662022, 7772024,
--   1302024, 43912024). 9 of 10 have only a generic placeholder address ("Osceola County, FL
--   34741"), no lat/long, no assessed/market value, and a truncated ~12-digit STRAP prefix
--   (the same osceola-specific truncation trap fixed for 33 OTHER rows on 2026-08-02, but the
--   2026-08-02 session explicitly reported these 10 as requiring case-number-keyed clerk-portal
--   lookups it could not perform that session). 1 row (case 2025 CA 001721 MF) has a fully
--   synthetic non-STRAP parcel_id (OSC-2CEAE2B1037A) and zero fields at all.
--   Fresh attempts this session:
--     - gis.osceola.org (Parcels FeatureServer/3, Zoning MapServer) -> WebFetch returned
--       "unable to verify the first certificate" (TLS chain validation failure) on every
--       protocol/path tried -- a DIFFERENT failure mode than the 2026-08-02 session logged for
--       other osceola.org-family hosts (which were reachable), suggesting this specific
--       subdomain's cert changed or is misconfigured; not a WAF block, a genuine connectivity
--       failure from this session's environment.
--     - ocpaweb.ocpafl.org: resolved to the WRONG county (Orange County Property Appraiser) --
--       a bad URL guess, discarded, not used.
--     - search.property-appraiser.org (the real current Osceola County Property Appraiser site,
--       found via fresh WebSearch this session) -> HTTP 403.
--     - app.regrid.com: has parcel data but no free/unauthenticated parcel-number query path
--       found without a paid API key.
--     - Firecrawl: -4/1000 credits (unchanged). browser-use: not installed (unchanged).
--   Did NOT write any address/geo/value/parcel_id change for these 10 rows -- genuinely
--   source-exhausted, not fabricated.
--
-- ================================================================================
-- Audit trail: 3 rows inserted into public.gold_standard_ultraloop_audit
-- (dispatch_id df5a4f3a-b78a-493b-976e-6081a988c1ae, county_slug='osceola'):
--   id=12660 letter='G' (RS-2 fix, survived=true)
--   id=12663 letter='G' (residual confirmation, survived=true)
--   id=12668 letter='I' (residual confirmation, survived=true)
-- ================================================================================

UPDATE public.zoning_districts
SET ordinance_section = 'Ch.3 Table 3.2 (Preceding Zoning District Development Standards Matrix)'
WHERE id = 13226;

INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft,
  source_url, ordinance_section, scraped_at, confidence_score
)
VALUES (
  13226, 4.30, 10000, 85,
  'https://www.zoneomics.com/code/osceola-county-unincorporated-FL/chapter_5',
  'Ch.3 Table 3.2 (Preceding Zoning District Development Standards Matrix) -- density derived from min lot size (43560/10000=4.3), not an explicit ordinance du/acre figure, same derivation method already accepted for RS-3/R-1/RA-1/RA-2 on 2026-08-02',
  now(), 0.6
)
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  min_lot_sqft = EXCLUDED.min_lot_sqft,
  min_lot_width_ft = EXCLUDED.min_lot_width_ft,
  source_url = EXCLUDED.source_url,
  ordinance_section = EXCLUDED.ordinance_section,
  scraped_at = EXCLUDED.scraped_at,
  confidence_score = EXCLUDED.confidence_score;

SELECT public.pencil_dod_evaluate_county('osceola');
