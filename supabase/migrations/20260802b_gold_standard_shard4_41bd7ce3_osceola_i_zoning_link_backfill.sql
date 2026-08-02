-- Gold Standard shard-4 (dispatch 41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4): osceola, letter I.
--
-- Baseline (VERIFIED via pencil_dod_evaluate_county('osceola'), live 2026-08-02
-- before this session's work): 8/10. I FAIL metric=75.9, card_complete=104 of 137.
--
-- ROOT CAUSE (VERIFIED this session via direct LEFT JOIN of multi_county_auctions
-- against v_zoning_gold_standard_card for county=osceola, reproducing the RPC's
-- own `c` CTE exactly): 33 gap rows split into two overlapping types --
--   (a) missing property_address/lat-long/assessed+market value, and
--   (b) EVERY one of the 33 sampled rows has has_zone=false, because the stored
--       parcel_id is a TRUNCATED ~12-digit STRAP PREFIX (documented osceola trap
--       from .claude/workflows/gold-standard-shard9-highlands-osceola-255f0be0-v2.js)
--       that never matches parcel_zones/zoning_districts.
--
-- 23 of the 33 rows already had full property_address+lat/long+value ("cheapest
-- fix" bucket per dispatch instructions) and needed ONLY a real zoning link.
-- The remaining 10 rows have zero address/geo/value on file at all and require
-- case-number-keyed lookups against Cloudflare-JS-challenge-protected clerk
-- portals (osceolaclerk.com/tax-deeds/, or.occompt.com/recorder/tdsmweb) -- no
-- working browser automation tool was available this session (browser-use CLI
-- not installed; Firecrawl credit balance was -4/1000, confirmed via
-- GET api.firecrawl.dev/v2/team/credit-usage) so these 10 are reported as a
-- genuine, honest residual, NOT fabricated.
--
-- ================================================================================
-- METHOD (per the 255f0be0-v2 prior-session methodology): resolve REAL full
-- STRAPs and zone codes via case-specific/parcel-specific GIS lookups, never by
-- treating the stored truncated parcel_id as authoritative.
-- ================================================================================
-- Unincorporated Osceola County (jurisdiction_id=1186):
--   gis.osceola.org/hosting/rest/services/Parcels/FeatureServer/3  (spatial
--     point-in-polygon query by our stored lat/lon -> real full Strap + address
--     + AssessedVa/CurrJust, used to CONFIRM the correct parcel before trusting
--     any zone)
--   gis.osceola.org/hosting/rest/services/Zoning_Parcels/FeatureServer/0
--     (PRIM_ZON field, queried by EXACT PARCELNO=Strap -- not spatial nearest --
--     to avoid the shared-common-area-parcel trap described below)
--
-- Kissimmee (jurisdiction_id=957):
--   cw.kissimmee.gov/arcgis/rest/services/Zoning_Districts/MapServer/10
--     (ZONING_COD field, spatial point query by lat/lon; layer also carries
--     LOT_WIDTH_/LOT_DEPTH_/HEIGHT/FAR standards data, not persisted here --
--     G is a separate work item in this same shard per dispatch instructions,
--     left for that work item to pick up)
--
-- St Cloud (jurisdiction_id=894):
--   arcgisweb.stcloud.org/arcgis/rest/services/Referenced_Layers/Zoning/
--     FeatureServer/2 (Zoning field, queried by EXACT Strap)
--   Discovered via the City of St Cloud's own "Community Development" ArcGIS
--   web app config (arcgis.com item 836d3f44869c4434862ec6165c404314's Search
--   widget source URL), NOT a guess -- the naive `services.arcgis.com/
--   lQySeXwbBg53XWDi/.../zoning_districts` and `services2.arcgis.com/
--   Q6Lq3evZUGfPrN7o/.../Planning and Development` FeatureServers that surfaced
--   in initial web search were CHECKED and REJECTED: the former's zone-code
--   domain list includes "Guadalupe" (a Texas district name) and the latter's
--   extent resolves to British Columbia, Canada -- neither is St Cloud FL.
--
-- COMMERCIAL-COMPLEX TRAP AVOIDED: cases 53772024/53942024 (2145 E Irlo Bronson
-- Memorial Hwy, Kissimmee) already had distinct, correctly-formatted 18-char
-- STRAPs on file (...011070 / ...011720). A naive spatial point-in-polygon
-- lookup on their stored lat/lon resolved BOTH to the same shared common-area
-- parcel 30253049710001COMM (AssessedVa=CurrJust=0 -- a tell). Instead of
-- collapsing both auction rows onto that one shared parcel, this session
-- queried Zoning_Parcels by the EXISTING, more-specific stored STRAPs directly
-- (exact PARCELNO match) and both independently resolved to zone_code=CT --
-- parcel_id was left UNCHANGED for these two cases.
--
-- DUPLICATE-PARCEL CLUSTER: cases 48482022/52562018/53252018 (3630 Allegra Cir,
-- St Cloud) all share stored prefix 262630061300 and resolved to the SAME real
-- full STRAP 262630061300011310 (confirmed by exact address match "3630
-- ALLEGRA CIR" in the St Cloud Zoning FeatureServer) -- one lookup, one
-- parcel_zones row, fixes three multi_county_auctions rows.
--
-- ================================================================================
-- VALUE CROSS-CHECK (spot check, not a gate): 14 of 23 resolved parcels had an
-- exact match between our stored assessed_value/market_value and the GIS
-- record's AssessedVa or CurrJust field (e.g. case 2132023: 196200 == 196200;
-- case 77492018: 9600 == 9600) -- strong independent corroboration that the
-- spatial/STRAP match is the correct parcel, not a false-positive. The 9
-- non-matching-value rows were still trusted on the strength of the point-in-
-- polygon spatial containment itself (a stored lat/lon is BY DEFINITION inside
-- exactly one parcel polygon) plus street-name corroboration where checked
-- (e.g. case 1212023: stored "DAKOTA AVE" == resolved "1030 DAKOTA AVE").
-- multi_county_auctions.assessed_value/market_value were NOT modified by this
-- migration for any row -- only parcel_id (18 rows, truncated prefix -> real
-- full STRAP) and the new parcel_zones/zoning_districts rows.
--
-- ================================================================================
-- G SIDE EFFECT (DISCLOSURE, not a fix -- G is out of scope, owned by a
-- separate work item in this same shard per dispatch instructions):
-- ================================================================================
-- v_zoning_gold_standard_kpi_v3 is NOT scoped to a specific county's auctions --
-- it aggregates over ALL parcel_zones rows grouped by jurisdiction county. The
-- 21 new parcel_zones rows this migration adds (9 new zoning_districts, ZERO
-- new zone_standards -- deliberately, standards backfill is G's job) increase
-- that view's denominator with no matching new standards rows, moving G's
-- reported osceola metric from 90.0 to 75.9 (VERIFIED via pencil_dod_evaluate_
-- county before/after). G was FAIL both before (90.0<95) and after (75.9<95) --
-- no pass-to-fail flip occurred, and no zoning_districts row was left with nulls
-- that would misrepresent a standards backfill as already done (the documented
-- seminole regression pattern this campaign guards against). Logged to
-- gold_standard_ultraloop_audit (letter='G', claim tagged as DISCLOSURE) for the
-- G work item to see via the coordinate-through-DB protocol.
--
-- ================================================================================
-- RESULT (VERIFIED via pencil_dod_evaluate_county('osceola') after apply):
-- I: 75.9 (104/137) -> 92.7 (127/137). Still FAIL (<95 threshold, needs 131/137).
-- 10 rows remain residual -- see comment block above. No other letter's PASS/FAIL
-- flipped (A/B/C/D/E/F/H/J untouched, confirmed identical before/after; G stayed
-- FAIL both times per the disclosure above).
--
-- Audit trail: 2 rows inserted into public.gold_standard_ultraloop_audit
-- (dispatch_id 41bd7ce3-a9f5-465d-99a1-a3ed447d8ce4, letters I and G(disclosure),
-- ultraloop_mode='fallback', survived=true -- id 12092 + one more).

-- ================================================================================
-- New zoning_districts (jurisdiction_id/code did not already exist)
-- ================================================================================
INSERT INTO public.zoning_districts (jurisdiction_id, code, name)
SELECT * FROM (VALUES
  (894::int,  'R-1',   'St Cloud Residential R-1'),
  (894::int,  'R-2',   'St Cloud Residential R-2'),
  (1186::int, 'RS-3',  'Residential Single Family'),
  (1186::int, 'R-1',   'Rural R-1'),
  (957::int,  'RA-2',  'RA-2 (Single Family Residential)'),
  (957::int,  'RA-1',  'RA-1 (Single Family Residential)'),
  (957::int,  'T4-R',  'T4-R (Neighborhood Restricted)'),
  (957::int,  'T5-U',  'T5-U (Mixed-Use Urban Core)'),
  (957::int,  'MUPUD', 'MUPUD (Mixed Use Planned Unit Development)')
) AS v(jurisdiction_id, code, name)
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts zd
  WHERE zd.jurisdiction_id = v.jurisdiction_id AND zd.code = v.code
);

-- ================================================================================
-- New parcel_zones rows (real STRAP + real zone_code, GIS-source-verified)
-- ================================================================================
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  ('012630000101520110', 894::int,  'R-2',   'St Cloud Residential R-2',                           'gs4_osceola_stcloud_gis_live_verified'),
  ('242528105500010240', 957::int,  'SRPUD', 'SRPUD (Short Term Rental Planned Unit Development)',  'gs4_osceola_kissimmee_gis_live_verified'),
  ('252628610006000090', 1186::int, 'PD',    'Plan Development',                                    'gs4_osceola_county_gis_live_verified'),
  ('012630495000013260', 894::int,  'R-1',   'St Cloud Residential R-1',                             'gs4_osceola_stcloud_gis_live_verified'),
  ('172529213500010340', 957::int,  'RA-2',  'RA-2 (Single Family Residential)',                    'gs4_osceola_kissimmee_gis_live_verified'),
  ('152529152000120060', 957::int,  'T4-R',  'T4-R (Neighborhood Restricted)',                      'gs4_osceola_kissimmee_gis_live_verified'),
  ('182529227600011615', 957::int,  'SRPUD', 'SRPUD (Short Term Rental Planned Unit Development)',  'gs4_osceola_kissimmee_gis_live_verified'),
  ('182527494100011590', 1186::int, 'PD',    'Plan Development',                                    'gs4_osceola_county_gis_live_verified'),
  ('022529408000680200', 1186::int, 'RS-3',  'Residential Single Family',                           'gs4_osceola_county_gis_live_verified'),
  ('022529408000760090', 1186::int, 'RS-3',  'Residential Single Family',                           'gs4_osceola_county_gis_live_verified'),
  ('19252900U001860000', 957::int,  'T5-U',  'T5-U (Mixed-Use Urban Core)',                         'gs4_osceola_kissimmee_gis_live_verified'),
  ('192529000002500000', 957::int,  'RA-1',  'RA-1 (Single Family Residential)',                    'gs4_osceola_kissimmee_gis_live_verified'),
  ('2025291830000F0140', 957::int,  'RA-2',  'RA-2 (Single Family Residential)',                    'gs4_osceola_kissimmee_gis_live_verified'),
  ('222529105000180036', 957::int,  'T5-M',  'T5-M (Mixed-Use Center)',                             'gs4_osceola_kissimmee_gis_live_verified'),
  ('2625314410000A0300', 1186::int, 'RS-2',  'Residential Single Family',                           'gs4_osceola_county_gis_live_verified'),
  ('262630061300011310', 894::int,  'R-3',   'Multi-Family Dwelling District',                      'gs4_osceola_stcloud_gis_live_verified'),
  ('302530497100011070', 1186::int, 'CT',    'Commercial Tourist',                                  'gs4_osceola_county_gis_live_verified'),
  ('302530497100011720', 1186::int, 'CT',    'Commercial Tourist',                                  'gs4_osceola_county_gis_live_verified'),
  ('032530420800010220', 1186::int, 'PD',    'Plan Development',                                    'gs4_osceola_county_gis_live_verified'),
  ('1332342780000C0200', 1186::int, 'R-1',   'Rural R-1',                                            'gs4_osceola_county_gis_live_verified'),
  ('052529152400012050', 957::int,  'MUPUD', 'MUPUD (Mixed Use Planned Unit Development)',          'gs4_osceola_kissimmee_gis_live_verified')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id
);

-- ================================================================================
-- multi_county_auctions.parcel_id: truncated ~12-digit STRAP prefix -> real full
-- STRAP, case-number-keyed (only rows where the resolved STRAP differs from what
-- was on file; the 2 foreclosure cases and 53772024/53942024 already had the
-- correct full STRAP and are NOT included here -- see comment block above).
-- ================================================================================
UPDATE public.multi_county_auctions m
SET parcel_id = v.new_pid
FROM (VALUES
  ('1212023',  '012630000101520110'),
  ('2132023',  '012630495000013260'),
  ('28152023', '172529213500010340'),
  ('29162024', '152529152000120060'),
  ('31152023', '182529227600011615'),
  ('33772024', '182527494100011590'),
  ('3432023',  '022529408000680200'),
  ('3452023',  '022529408000760090'),
  ('35192022', '19252900U001860000'),
  ('38582021', '192529000002500000'),
  ('38742024', '2025291830000F0140'),
  ('42202021', '222529105000180036'),
  ('47142022', '2625314410000A0300'),
  ('48482022', '262630061300011310'),
  ('52562018', '262630061300011310'),
  ('53252018', '262630061300011310'),
  ('77492018', '1332342780000C0200'),
  ('8642023',  '052529152400012050')
) AS v(case_number, new_pid)
WHERE m.case_number = v.case_number AND lower(m.county) = 'osceola';

SELECT public.pencil_dod_evaluate_county('osceola');
