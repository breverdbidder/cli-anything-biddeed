"""
SHARD-6 hendry, this-session follow-up to a concurrent session's A+I fix
(commit 2790ad50, dispatch e9951859-29fe-4c2e-aa04-ca05ced1d0c7).

Context: that concurrent session ingested 3 foreclosure rows from the Hendry
Clerk's official MuniDocs foreclosure sale docket (data_source
'hendry_clerk_munidocs') to fix letter A (fc=0 -> fc=3, PASS). Those 3 rows
were inserted WITHOUT a parcel_id (the docket source publishes case number +
plaintiff + property address, not a parcel number), which dropped letter E
from a would-be 100% to 85% (17/20) and left them out of the zoning
substrate (contributing to I's low card_complete).

This script (executed live via REST PATCH + Management API SQL, not as a
batch job) resolves parcel_id + real per-parcel lat/lon + zoning for those
3 rows using Hendry County's own public ArcGIS Online organization
(services7.arcgis.com/8l7Qq5t0CPLAJwJK), the SAME authoritative source the
concurrent session used for the 14-parcel zoning substrate build.

Method: exact LOCADD (site address) match against the county's own
Hendry_County_Parcels FeatureServer/0 layer, to resolve each foreclosure
row's property_address into a real PARCELNO + LAT/LON:

  case 22000726CAAXMX  "6208 HOB COURT, LABELLE FL"
    -> PARCELNO '4 29 43 10 060 2198-009.0', owner THADDIES JAMES & CASSONDRA
       LAT 26.752 LON -81.3777

  case 25000526CAAXMX  "4028 RAINBOW CIR, LABELLE FL 33935"
    -> PARCELNO '4 29 43 10 040 2159-017.0', owner SAMMS WILFRED C EST
       LAT 26.7526 LON -81.3987

  case 26000017CAAXMX  "1095 N SR 29 & 120 CR 78, LABELLE FL" (dual address,
  single commercial property -- both address halves resolved to separate
  parcels under the SAME owner, GLADES VETERINARIAN SERVICES LLC, confirming
  this is one property spanning two parcels; primary parcel recorded)
    -> PARCELNO '1 29 42 32 A00 0016.0000' (1095 N SR 29 half)
       LAT 26.7774 LON -81.4384

Then queried the county's Zoning FeatureServer/1 (PARCELNO -> Current_Zo,
same source/method as the concurrent I fix) for these 3 parcels:
  '4 29 43 10 060 2198-009.0' -> RG-3 (Residential General)
  '4 29 43 10 040 2159-017.0' -> RG-3 (Residential General)
  '1 29 42 32 A00 0016.0000'  -> C-1  (Commercial)

All 3 matched with real zoning codes; inserted into parcel_zones under the
existing "Hendry County (Unincorporated)" jurisdiction (id 1399, created by
the concurrent session's I-fix migration).

RESULT:
  E: 85.0 (17/20 parcel_linked) -> 100.0 (20/20) -- PASSES.
  I: held at 60.0 (12/20 card_complete) -- the SAME 3 rows are now correctly
     linked into v_zoning_gold_standard_card (parcel_id present, zone_code
     present) but still fail card_complete because assessed_value AND
     market_value remain NULL for all 3. The Hendry Property Appraiser's
     Beacon/Schneider Corp property search (beacon.schneidercorp.com) is
     behind a Cloudflare challenge (HTTP 403) even with a standard browser
     User-Agent -- no non-browser-automation path found this session to
     pull real assessed/market values. Reported as residual, not fabricated.

Endpoints used (read-only, live, verified this session):
  https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/ArcGIS/rest/services/Hendry_County_Parcels/FeatureServer/0/query
  https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/ArcGIS/rest/services/Zoning/FeatureServer/1/query

Writes performed (via REST PATCH to multi_county_auctions, and direct SQL
INSERT to parcel_zones via the Management API -- no schema change, no
migration file required per campaign rules):
  PATCH multi_county_auctions SET parcel_id, latitude, longitude
    WHERE id IN (8720dc76-c2fc-4852-95ba-dc1d1e57d131,
                 404eb247-7283-43b2-83dd-efac9d2f4837,
                 22f60bb5-bb3b-4c32-bb87-dbb27b151bda)
  INSERT INTO parcel_zones (jurisdiction_id=1399, parcel_id, zone_code,
    zone_name, source) for the same 3 parcels, ON CONFLICT DO NOTHING.

Audit: 5 rows in gold_standard_ultraloop_audit (ids 5237-5241),
dispatch_id=e9951859-29fe-4c2e-aa04-ca05ced1d0c7.
"""
