-- GOLD STANDARD shard-5 gulf-only (dispatch 9e12d062-b309-4def-b6f5-130798862110)
-- Letters E and I. gulf has only 14 total auctions; the campaign's 95% threshold means
-- E/I each effectively require ALL 14 rows linked/complete (13/14=92.9% still fails).
--
-- ROOT CAUSE (verified fresh this session): case 232024CA000072CAAXMX (id
-- ab84aca0-37c8-4c61-86c2-67d697c07560) had its parcel_id and property_address wiped back to
-- NULL/'' by a live scraper re-run between 2026-07-30 (when it was correctly resolved to
-- '06248405R' by dispatch 0ba2502a shard9 run7519, migrations/20260730_gold_standard_shard9_
-- gulf_cdei_run7519.sql) and this session. Confirmed this is an ISOLATED regression, not a
-- full re-scrape wipe: last_changed_at=2026-08-06 for THIS row only, while its two sibling
-- rows from the same 2026-07-30 migration (232019CA000060CAAXMX -> 03501201R,
-- 232024CC000157CCAXMX -> 04276175R) both still carry their correct parcel_id today
-- (last_changed_at=2026-08-02, unaffected). lat/long/assessed_value/judgment_amount on the
-- target row were untouched by the scrape -- only parcel_id/property_address were cleared.
--
-- Independently re-verified the parcel match fresh this session (not just trusting the prior
-- migration comment) via arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer/12
-- ("Parcels" layer), querying PIN_NODELIM LIKE '%06248405%':
--   PIN_DSP='06248-405R' / PIN_NODELIM='06248405R', HOUSE_NO=118, STREET='SHALLOW REED DR',
--   ST_CITY='PORT ST JOE', OWNER_NAME='R & R DEVELOPMENT & HOLDING',
--   LEGL1='SHALLOW REED PHASE ONE PB 6 PG', LOT=41
-- Matches the prior session's double-corroborated evidence (legal description "LOT 41 SHALLOW
-- REED PHASE ONE" + defendant "R AND R DEVELOPMENT AND HOLDING GROUP LLC") exactly and
-- uniquely. That prior finding was itself adversarially verified (ULTRALOOP refuter,
-- survived=true, gold_standard_ultraloop_audit ids 10948-10952) before being written.
--
-- Explicitly did NOT use the shared fallback centroid (lat=29.9163, lng=-85.1588) present on
-- this row for a point-in-polygon spatial match against the parcels layer -- that coordinate
-- pair is IDENTICAL across all 5 gulf foreclosure rows (confirmed this session) and resolves
-- to an unrelated rural Wewahitchka parcel (Deseret Ranches, Doc Whitfield Rd), which would
-- have been a fabricated parcel_id. Restoring the previously-verified '06248405R' from the
-- authenticated-RealForeclose + GIS owner/legal-description cross-match lever instead.
--
-- parcel_zones row for '06248405R' (zone_code='Mixed_Comm/Res', jurisdiction_id=1507, backed
-- by zone_standards for zoning_district_id=12294) was NOT touched by the scrape regression and
-- is still present -- this migration only restores the multi_county_auctions.parcel_id/
-- property_address columns; no new zoning work, zero regression risk to letter G.

update public.multi_county_auctions
set parcel_id = '06248405R',
    property_address = 'Address On File - Port St Joe FL 32456'
where lower(county) = 'gulf'
  and case_number = '232024CA000072CAAXMX'
  and id = 'ab84aca0-37c8-4c61-86c2-67d697c07560'
  and parcel_id is null;
