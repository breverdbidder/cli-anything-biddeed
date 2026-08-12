-- Gold Standard shard-2 (dispatch a1884f7f-816e-4b36-bfb6-e4a65f77ebba)
-- baker letter E: parcel_id backfill for case 022025CC000132CCAXMX
--
-- CONTEXT: fix-phase agent for baker-CDEIJ reported this case as BLOCKED
-- ("both viable lookup paths non-functional from this environment": ArcGIS
-- quoted-string filter timeout + bakerpa.com HTTP 521). The adversarial
-- verify-phase agent REFUTED that verdict (gold_standard_ultraloop_audit
-- ids 14923-14927, survived=false) by finding an unchecked third path:
-- fl_parcels (statewide FL GIO cadastral cache, co_no=12=Baker), already
-- the standard precedent pattern used by numerous prior gold-standard fixes
-- (gadsden/franklin/hamilton/miami-dade/broward). Exactly one unambiguous
-- candidate matches the case's known parties (Fernando & Jessica Dunn) and
-- address:
--   fl_parcels: parcel_id=073S22023800001000, own_name='DUNN FERNANDO',
--   phy_addr1='8669 NEWNAN LAKE DR', phy_city='Macclenny', phy_zipcd=32063,
--   jv=279706, centroid_lat=30.2557169, centroid_lng=-82.1373726
--
-- Independently re-confirmed by the session orchestrator (not the refuter,
-- not the fix agent) before applying: multi_county_auctions row
-- d00fcb28-fe2b-4395-ba0d-63878935c5ce had parcel_id/property_address/
-- lat/lon/assessed_value all NULL, and the fl_parcels address filter
-- returned exactly one row (no ambiguity risk). Applied live via a
-- conditional UPDATE (parcel_id IS NULL guard, so this migration is a
-- no-op if re-run).
--
-- RESULT: baker E parcel_linked 8->9 of 10 (80.0% -> 90.0%), still FAIL
-- (this county's auctions_total=10 means 95% requires 10/10). C/D/I are
-- UNAFFECTED by this write — they require parity_status / zoned-parcel
-- card-completion separately, not just parcel_id.
--
-- RESIDUAL: the second flagged case, 022025CA000117CAAXMX, was
-- independently re-checked in this same session and genuinely has no
-- address/owner in fl_parcels or any other source yet (no legal notice
-- filed, consistent with normal FL Ch.45 foreclosure timing) — this one
-- remains a real structural blocker, not a missed lever.

UPDATE public.multi_county_auctions
SET
  parcel_id = '073S22023800001000',
  property_address = '8669 NEWNAN LAKE DR, MACCLENNY, FL 32063',
  latitude = 30.2557169,
  longitude = -82.1373726,
  assessed_value = 279706
WHERE county = 'baker'
  AND case_number = '022025CC000132CCAXMX'
  AND parcel_id IS NULL;
