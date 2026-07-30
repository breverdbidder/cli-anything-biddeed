-- Gold Standard shard-3 (st_lucie), 2nd firing on dispatch_id 8c78a8df-6a6b-473d-b3cb-ac257a1f5718
-- session: architect-20260730T160000, ~18:16 UTC
--
-- CONTEXT: this dispatch was already closed out ~1.5h earlier (commit 953bb752,
-- 16:42:50Z, session report GOLD_STANDARD_SHARD3_VOLUSIA_STLUCIE_DISPATCH_8C78A8DF_SESSION_REPORT.md)
-- reaching volusia 9/10 (G fail, blocked on a real Daytona Beach M-1 FAR/parking
-- ordinance value -- Firecrawl out of credit) and st_lucie 8/10 (E/I fail on 8
-- rows). This migration is a small, additive follow-up found via a fresh
-- diagnostic pass, not a re-run of that prior work.
--
-- FIX: one of st_lucie's 8 I-gap rows (case 2025CC004353, parcel account 171578,
-- 5420 IMAGINATION DR) already had address/geo/value -- only its zoning link was
-- missing. VERIFIED live via two independent ArcGIS REST calls:
--   1. map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels/MapServer/0
--      query where AccountNumber=171578 -> SiteAddress "5420 IMAGINATION DR"
--      (exact match to our stored address) + parcel polygon geometry.
--   2. slcgis.stlucieco.gov/hosting/rest/services/LandUse/ForttPierceZoningFLU/
--      MapServer/0 -- spatially intersected the parcel centroid AND separately
--      queried by the layer's own AccountNum=171578 attribute (double
--      confirmation, not just spatial proximity) -- both return Zoning=PD.
-- zoning_districts already has a PD/jurisdiction=971(Fort Pierce) row
-- (id=12073, far_regulated=false, density_regulated=false) from an earlier
-- session, so this insert carries zero G-regression risk (unlike the RMH-5
-- case in 20260730c, there is no new zoning_districts row being created here).
--
-- RESULT: st_lucie I: card_complete 111->112 of 119 (93.3%->94.1%). Still FAIL
-- (<95%) -- the other 7 gap rows are confirmed structurally non-fixable this
-- session (see below), so 94.1% is the honest ceiling without a policy
-- decision. E unchanged at 94.1% (this row already had parcel_id, so it was
-- already counted there).
--
-- RESIDUAL (not fixed, confirmed structural): the other 7 st_lucie E/I gap
-- rows -- 2024CA001834, 2025CC001033, 2023CA002852, 2024CA000330,
-- 2024CA000214, 2025CA002738, 2023CA000465 -- were independently
-- re-diagnosed this session via the live RealForeclose AJAX feed itself
-- (stlucie.realforeclose.com index.cfm zaction=AUCTION Zmethod=UPDATE
-- FNC=LOAD, session-cookie + browser UA, no bidder auth required). The
-- county's OWN case cards carry literal non-parcel placeholders as
-- parcel_id text: "Property Appraiser" (x4), "AIRCRAFT" (x1), "TIMESHARE"
-- (x1, a consolidated 12-count HOA lien case per clerk docket cross-check),
-- "MULTIPLE PARCELS" (x1). This corroborates the prior firing's identical
-- finding (953bb752) with fresh live data ~1.5h later. Not mechanically
-- closable without fabrication; reaching 95% on E/I requires an owner/
-- architect policy decision on excluding non-standard-collateral rows from
-- the auctions_total denominator -- out of scope for a single shard session.
--
-- volusia G: reconfirmed blocked, not touched this session. Firecrawl
-- account balance checked directly (GET /v1/team/credit-usage ->
-- remaining_credits=-2 of 1000) -- fleet-wide exhaustion, not a one-off
-- 402. A 9-agent ultracode research+adversarial-verify workflow (418 tool
-- calls) also failed to source a real Daytona Beach M-1 FAR/parking value;
-- the one numeric figure surfaced (FAR 10.0) was sourced to a Ballough Road
-- Redevelopment overlay document, not base M-1 zoning, and was correctly
-- withheld per HONESTY PROTOCOL rather than reported.
--
-- Verification: gold_standard_ultraloop_audit ids 11086 (st_lucie I,
-- survived=true), 11087 (st_lucie E residual, survived=true -- confirmed
-- structural, not a refuted improvement claim), 11088 (volusia G,
-- survived=false -- fix not achieved).

SET statement_timeout = 0;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES (
  '171578',
  971,
  'PD',
  'Planned Development',
  'gold_standard_shard3_run7519_2nd_firing:slcgis.stlucieco.gov/hosting/rest/services/LandUse/ForttPierceZoningFLU:AccountNum_171578_exact_match:2026-07-30'
)
ON CONFLICT DO NOTHING;
