-- Sumter County shard4 (dispatch 3b3e322c): E/I zoning-card linkage for 7 of the
-- 8 newly-scraped multi_county_auctions rows (created 2026-08-26).
--
-- CONTEXT (VERIFIED live via pencil_dod_evaluate_county('sumter') before this session):
--   auctions_total grew 24 -> 32 since the 2026-08-26 session (8 new foreclosure
--   rows scraped, only case_number populated -- no parcel_id/address/geo/value).
--   E FAIL 75.0% (24/32), I FAIL 75.0% (24/32), J FAIL 75.0% (24/32).
--
-- RESOLUTION (this session, live-sourced, 2026-08-27):
--   Of the 8 new rows, 7 were located to a real address via
--   https://www.sumterclerk.com/courts/foreclosures/foreclosure-sales/ (live HTML,
--   case_number/parties/judgment_amount/address columns). The 8th
--   (2026-CA-000129, KENNETH STRONG -VS- JOHNATHON YOUNG) has NO address field
--   populated on the clerk's own page -- genuine source gap, left untouched.
--
--   The 7 addresses were geocoded via the Sumter County government's own
--   ArcGIS geocoder (https://gis.sumtercountyfl.gov/sumtergis/rest/services/
--   Operations/Sumter_Geocoder/GeocodeServer/findAddressCandidates, scores
--   87.7-92.9), then the geocoded point was used for a point-in-polygon spatial
--   query against the FL DOR statewide cadastral FeatureServer
--   (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0),
--   the SAME source used by every prior sumter shard session (parcel_id is
--   unknown until this step for foreclosure cases with no clerk-scraped parcel
--   number).
--
--   OWNER-NAME CROSS-CHECK (per repo methodology -- OWN_NAME on the returned
--   DOR feature vs the clerk-scraped defendant/party name):
--     2026-CA-000099 CARTLEDGE MARY ANN        == DOR "CARTLEDGE MARY ANN"      MATCH
--     2025-CA-000475 LARRY WILKINSON           == DOR "WILKINSON LARRY LEE..."  MATCH
--     2025-CA-000394 WILLIAM HOMER BRAY JR TTEE== DOR "BRAY WILLIAM HOMER JR"   MATCH
--     2025-CA-000294 SHERRY TERRAMOCCIA        == DOR "TERRAMOCCIA SHERRY A..." MATCH
--     2025-CA-000515 BRICE HENRY BOULET        == DOR "BOULET BRICE HENRY"     MATCH
--     2026-CA-000074 MARC G. RATLIFF           != DOR "WHEELER DALE N & SHARON R" MISMATCH
--     2026-CA-000090 MARY MCLEAN               != DOR "FRISKE ROBERTA M"          MISMATCH
--   5 of 7 geocode+PIP results independently cross-match the clerk-scraped
--   defendant name -- same confirmation standard as every prior sumter session.
--   The 2 mismatches (000074, 000090) are NOT linked in this migration --
--   their geocode scores (89.35 / 87.72) were also the two lowest of the batch,
--   consistent with an imprecise interpolated match landing on a neighboring
--   parcel rather than the actual subject property. No independent third
--   source (Sumter Clerk official-records/OR-book search returned HTTP 404;
--   Sumter PA public parcel/owner-name search has no queryable ArcGIS REST
--   endpoint beyond the geocoder) was reachable within this session to break
--   the tie. Per BLANK > WRONG these 2 rows are left unenriched rather than
--   force-matched to a plausibly-wrong parcel. Residual, not fabricated.
--
--   ZONE CODES (Sumter County GIS FLU_Zoning FeatureServer, SAME source as
--   every prior sumter I-fix; layer 11 = unincorporated county, field Parcel;
--   layer 10 = Wildwood municipal, field PIN):
--     D13D081 (2026-CA-000074) -- NOT LINKED (owner mismatch, see above)
--     D28E030 (2026-CA-000090) -- NOT LINKED (owner mismatch, see above)
--     D03J031 (2026-CA-000099) RPUD  (layer 11, jurisdiction 1325) -- code
--       already registered w/ zone_standards.max_density_du_acre=5.4 (id 11471)
--     D29C059 (2025-CA-000475) R2C   (layer 11, jurisdiction 1325) -- code
--       already registered w/ zone_standards.max_density_du_acre=2.0 (id 11473)
--     G03C159 (2025-CA-000394) RPUD  (layer 11, jurisdiction 1325) -- as above
--     D13K044 (2025-CA-000294) RPUD  (layer 11, jurisdiction 1325) -- as above
--     G04N163 (2025-CA-000515) CMU   (layer 10, Wildwood, jurisdiction 950) --
--       NOT LINKED this migration. CMU is a genuinely NEW code to jurisdiction
--       950 with no existing zone_standards row. Its only documented source
--       (wildwood-fl.gov LDR PDF, Table 3-4C Mixed-Use Zoning Districts) 403s
--       on direct fetch and on WebFetch (same WAF block already documented for
--       this domain in prior sumter/leon/walton sessions); web.archive.org is
--       unreachable from this sandbox; municode.com's Wildwood mirror is a
--       JS-only shell (no static table content) and 403s WebFetch; zoneomics.com
--       has no CMU entry. Per the repo's own precedent (this same migration's
--       sibling RMU code, id 11477, category='mixed_use' with a real 5.0
--       du/acre value already on file), inserting a CMU parcel_zones row with
--       category='mixed_use' and NO zone_standards row would make
--       v_zoning_district_applicability default density_applicable=TRUE with
--       no value present -- the EXACT G-regression failure mode already hit
--       and fixed for R4C/R6M/A10C in the 2026-08-12 shard3 migration
--       (density 100.0->72.7). G is currently 100% PASS and out of scope for
--       this dispatch; reclassifying CMU as category='commercial' to dodge the
--       applicability default would be a guess (CMU explicitly implies a
--       residential mixed-use component) and is not done. G04N163's
--       multi_county_auctions row IS still enriched (address/geo/value, see
--       companion Python script) -- only the zoning-district linkage half of
--       I is deferred here as a genuine, honestly-labeled residual.
--
-- NET EXPECTED EFFECT: E parcel_linked 24->29 of 32 (90.6%, still FAIL --
--   PASS threshold is 31/32); I card_complete depends on E plus a real
--   zoning-card row -- 4 of the 5 newly parcel_id'd rows (D03J031, D29C059,
--   G03C159, D13K044) gain a real v_zoning_gold_standard_card row via this
--   migration; G04N163 gains parcel_id/address/geo/value (via the companion
--   Python script) but NOT a card row this session (see CMU note above).
--
-- NOT WRITTEN / explicitly out of scope this migration:
--   - 2026-CA-000074, 2026-CA-000090 (owner-name mismatch, unresolved)
--   - 2026-CA-000129 (no address on clerk page at all, unresolved)
--   - zone_standards for CMU (genuine source dead-end, see above)
--   - bid_decisions / J-criterion rows (companion Python script, scoped to
--     only the case numbers with a confirmed parcel_id this session)

SET statement_timeout = 0;

-- ── parcel_zones — link the 4 RPUD/R2C parcels to their pre-existing,
--    density-safe zone codes (jurisdiction 1325, NOT G04N163/CMU) ────────────

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
    ('D03J031', 'D03J031', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=D03J031:2026-08-27'),
    ('D29C059', 'D29C059', 1325, 'R2C', 'Residential 2 - Conventional',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=D29C059:2026-08-27'),
    ('G03C159', 'G03C159', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=G03C159:2026-08-27'),
    ('D13K044', 'D13K044', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=D13K044:2026-08-27')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET
    zone_code = EXCLUDED.zone_code,
    zone_name = EXCLUDED.zone_name,
    source    = EXCLUDED.source;

-- ── Verification ────────────────────────────────────────────────────────────

SELECT 'parcel_zones sumter shard4 new-4' AS check_name, pz.parcel_id, pz.jurisdiction_id, pz.zone_code, pz.source
FROM parcel_zones pz
WHERE pz.parcel_id IN ('D03J031','D29C059','G03C159','D13K044')
ORDER BY pz.parcel_id;

SELECT 'card_view sumter all after shard4' AS check_name, county, parcel_id, tax_account, zone_code
FROM v_zoning_gold_standard_card
WHERE lower(county) = 'sumter'
ORDER BY parcel_id;
