-- Gold Standard shard-6 (dispatch 091fb9f9-f5a4-49b3-ad21-2472b3cc9f4a):
-- santa_rosa (10/10) freshness refresh + osceola (8/10) ghost-success purge.
--
-- SANTA_ROSA: no data change. All 10 letters independently re-verified live
-- and adversarially checked (ULTRALOOP); fresh survived=true audit rows
-- written to gold_standard_ultraloop_audit for all 9 letters that were at
-- the 7-day staleness edge (A,B,C,D,E,F,G,H,J last audited 2026-07-24; I
-- already had a fresh 2026-07-31 row). No regression found.
--
-- OSCEOLA GHOST-SUCCESS PURGE (letter I):
-- CONFIRMED (adversarially verified) that 410 public.parcel_zones rows with
-- source='shard4_run5153_osceola_i_default:INCORP_or_nomatch' were a blind
-- zone_code='PD' fallback default written whenever a live gis.osceola.org
-- lookup returned INCORP/empty/unrecognized -- not a real zoning
-- determination. Live spot-check against gis.osceola.org's own
-- Zoning_Parcels FeatureServer for 3 sample parcels contradicted the
-- uniform 'PD' value (real leaf zones were E-1/PD/PD/CR, INCORP x5, and
-- RS-3 x4/INCORP x1 respectively).
--
-- ROOT CAUSE (fixed in code, this commit): scripts/shard5_run1524_osceola_cd_fix.py
-- unconditionally calls run_i_enrichment() -> shard4_run5153_osceola_i_enrichment.py
-- main() every time the daily 05:00Z cron (.github/workflows/shard5-run1524-daily.yml)
-- fires, which is what kept re-inserting this fabrication after at least one
-- prior purge attempt. scripts/shard4_run5153_osceola_i_enrichment.py's
-- step2_parcel_zones_backfill now SKIPS parcels with no real GIS zone match
-- instead of defaulting to 'PD' -- no code/workflow change needed beyond
-- that, since the daily job now calls the corrected function.
--
-- Executed live (this session, in order):
--   1. DELETE FROM parcel_zones WHERE source = '...INCORP_or_nomatch' (410 rows)
--   2. Real geo/value backfill for 4 multi_county_auctions rows (live Osceola
--      GIS + property appraiser data, cited per row below)
--   3. Real zone_code backfill for 1 of those 4 parcels (062629000000 -> RS-2,
--      confirmed genuinely unincorporated via City_Limits point-in-polygon
--      cross-check against the row's own lat/lon)
--   3 of the 4 geo/value-backfilled rows remain zone-unlinked: point-in-polygon
--   confirms they are genuinely inside Kissimmee/St Cloud municipal limits
--   (PRIM_ZON=INCORP, cross-checked against the City_Limits GIS layer), not
--   unincorporated county jurisdiction_id=1186 -- a real structural gap
--   (needs jurisdiction reassignment + that municipality's own zoning layer),
--   left unlinked rather than fabricated. Flagged for a future session.
--
-- NET EFFECT: letter I moved from a ghost-inflated 89.8% (123/137) to an
-- honest 75.9% (104/137) -- still FAIL both before and after, so no
-- certification was ever mis-issued on this number, but the daily
-- fabrication is now stopped and the number is now real.
--
-- SIDE EFFECT ON LETTER G (measured, not assumed): purging the 410 rows
-- also changed G's applicable-parcel set -- density 93.0->90.9,
-- pk1000 69.2->64.3 (far unchanged at 0.0). G was FAIL before and after;
-- this corrects an initial research-agent claim that G was unaffected by
-- the purge, which live re-measurement after applying the delete disproved.
--
-- G (letter, still FAIL, investigation-only this session, no data written):
-- root-cause narrowed to exactly 3 parcels (2x Kissimmee T3, 1x Kissimmee
-- T5-M, jurisdiction_id=957) with zero matching zoning_districts row at all,
-- causing v_zoning_gold_standard_kpi_v3's join-miss to default them to
-- applicable=true with NULL standards. Real T3/T5-M dimensional standards
-- (Kissimmee LDC Ch 14-5 Table 5-2) and the citywide parking table (Ch 14-7)
-- remain UNKNOWN -- Municode/kissimmee.gov/PDF mirrors all returned HTTP 403
-- to WebFetch this session (4th firing to hit this exact block), Firecrawl
-- confirmed still out of API credits. No values fabricated.

DELETE FROM public.parcel_zones
WHERE source = 'shard4_run5153_osceola_i_default:INCORP_or_nomatch';

UPDATE public.multi_county_auctions
SET latitude = 28.257067, longitude = -81.452248, assessed_value = 90792, market_value = 194400
WHERE id = 'db9183ab-5d0e-412b-804f-439c67893498'; -- case 10902023, parcel 062629000000600000, 4286 S Orange Blossom Trl, Kissimmee

UPDATE public.multi_county_auctions
SET latitude = 28.251312, longitude = -81.26598, assessed_value = 196200, market_value = 196200
WHERE id = 'eaf28dba-572b-4707-b776-6aef79372dfa'; -- case 2132023, parcel 012630495000013260, 705 Grape Ave, Saint Cloud

UPDATE public.multi_county_auctions
SET latitude = 28.305764, longitude = -81.395083, assessed_value = 188635, market_value = 195900
WHERE id = '20a65825-812e-4233-bd6c-354bad14ca4d'; -- case 29162024, parcel 152529152000120060, 1005 Lehigh St, Kissimmee

UPDATE public.multi_county_auctions
SET latitude = 28.30367, longitude = -81.42477, assessed_value = 171570, market_value = 231000
WHERE id = 'e4135141-cad2-42e2-8c39-97cf1eb5949c'; -- case 38742024, parcel 2025291830000F0140, 2006 W Orange Blvd, Kissimmee

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES ('062629000000', 1186, 'RS-2', 'shard6_santarosa_osceola_091fb9f9_i_real_gis_fix:RS-2 (point-in-polygon at 28.257067,-81.452248, confirmed outside all City_Limits polygons)');
