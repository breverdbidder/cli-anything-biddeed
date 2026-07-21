-- Sarasota gold-standard letter I (property card completeness) -- zone_code linkage extension
-- Dispatch: run5361 shard6 continuation. Session date 2026-07-21.
--
-- CONTEXT: at session start, live query (matching CLAUDE.md task spec exactly) returned 176
-- candidate rows (property_address + lat/lng + assessed/market value present, zone_code missing)
-- -- not 48 as originally referenced in the dispatch context, because DB state has moved since
-- that number was written (a prior commit 492fe43e already backfilled geo/value fields for
-- other rows, growing the eligible pool). Live DB is authoritative; proceeded with the real 176.
--
-- Of the 176: 28 shared an identical placeholder coordinate (27.3364,-82.5307) which independent
-- verification confirmed is a bad/default centroid, NOT a real geocode (proven by querying scgov
-- ags3.scgov.net at that exact point -- it returns municipality='CS' zoningcode='SARASOTA', the
-- documented placeholder-string pattern). All 28 were excluded before any source query (BLANK >
-- WRONG) leaving 148 rows with plausible real coordinates.
--
-- Sources queried per row, in this trust order:
--   1. Address contains 'VENICE' -> SKIPPED entirely, zero queries. Prior session proved
--      geoport.venicefl.gov/server/rest/services/pz/Zoning/MapServer/1 returns wrong ACCOUNT
--      matches for real Venice test parcels (geometry artifact). Not re-tested this session.
--   2. Address contains 'NORTH PORT' -> npgis.northportfl.gov/cnpserver/rest/services/Hosted/
--      Current_Zoning/FeatureServer/241, point-in-polygon, inSR=4326, fields zone_abbr/zone_des.
--      jurisdiction_id=941. Verified live and working (test point -82.2374,27.0448 near North
--      Port City Hall returned zone_abbr='AC-1' with full attribute set -- see per-row comments).
--   3. All other addresses -> ags3.scgov.net/server/rest/services/Hosted/CountyZoning/
--      FeatureServer/0 queried FIRST. Result trusted ONLY when returned municipality='SC'
--      (confirmed unincorporated-county field value; verified live -- e.g. point
--      -82.332939,27.267504 returned municipality='SC' zoningcode='OUE-1'). jurisdiction_id=824,
--      source='scgov_arcgis'.
--      If scgov municipality != 'SC' (i.e. any placeholder muni code: CS=City of Sarasota,
--      CV=City of Venice, TLK=Town of Longboat Key, or no feature at all) -> fell back to a
--      NEWLY DISCOVERED City of Sarasota zoning layer:
--      services3.arcgis.com/AWDwYUpli8WqpWxQ/arcgis/rest/services/Zoning_Districts_(View_Only)/
--      FeatureServer/0 (fields ZONECLASS, ZONEDESC, ORD_NO). Found via WebSearch ->
--      data-sarasota.opendata.arcgis.com open-data catalog entry 'Zoning Districts (View Only)'.
--      Verified live: point -82.5015829,27.3463145 (3381 RAMBLEWOOD PL, inside City of Sarasota,
--      previously only matched the CS placeholder on the county layer) returned real
--      ZONECLASS='RMF-2' ZONEDESC='Residential Multiple Family 2' -- consistent with the
--      existing jurisdiction_id=824 Article VI naming convention already in parcel_zones (RSF-2,
--      RSF-3, RMF-1, RMF-2, CG, CSC etc). jurisdiction_id=824, source='cos_zoning_arcgis'.
--      CV (City of Venice) and TLK (Town of Longboat Key) placeholder hits were NOT resolved by
--      any confirmed-reliable source this session -- left blank per BLANK > WRONG (CV overlaps
--      the address-based Venice skip already in place; TLK has no vetted source at all).
--
-- RESULT: 126 real, verified point-in-polygon matches inserted out of 148 candidates
-- with plausible coordinates (6 skipped as Venice-addressed,
-- 13 scgov placeholder/no-feature with no working fallback,
-- 3 North Port addressed but outside all mapped zoning polygons).
-- 28 additional rows excluded pre-query for placeholder coordinates (not counted above).

-- ============================================================
-- Per-row source queries and real API responses (VERIFIED)
-- ============================================================

-- parcel_id=0042150004 address="1906 ANDREA PL, SARASOTA, FL- 34235" lat=27.354014 lon=-82.501643
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RSF-3", "zoningcode": "RSF-3", "zoninggroup": "Residential Single Family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0042150004', '0042150004', 824, 'RSF-3', 'Residential Single Family', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0043030031 address="2222 DR MARTIN LUTHER KING JR, SARASOTA, FL- 34234" lat=27.359428 lon=-82.525473
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "CN", "zoningcode": "CN", "zoninggroup": "Commercial"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0043030031', '0043030031', 824, 'CN', 'Commercial', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0090130005 address="3801 CLOVER LN, SARASOTA, 34233" lat=27.270449 lon=-82.493857
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RSF-3", "zoningcode": "RSF-3", "zoninggroup": "Residential Single Family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0090130005', '0090130005', 824, 'RSF-3', 'Residential Single Family', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0091010009 address="4825 VICTORIA AVE, SARASOTA, FL- 34233" lat=27.283258 lon=-82.466812
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RC", "zoningcode": "RC", "zoninggroup": "Residential Conservation, Estate, Planned Unit Development"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0091010009', '0091010009', 824, 'RC', 'Residential Conservation, Estate, Planned Unit Development', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0142050014 address="3752 GLEN OAKS MANOR DR" lat=27.3486922 lon=-82.4966305
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RMF-1", "ZONEDESC": "Residential Multiple Family 1", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0142050014', '0142050014', 824, 'RMF-1', 'Residential Multiple Family 1', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0165100074 address="91 MALER DR, NOKOMIS, FL- 34275" lat=27.14095 lon=-82.455027
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RSF-2", "zoningcode": "RSF-2", "zoninggroup": "Residential Single Family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0165100074', '0165100074', 824, 'RSF-2', 'Residential Single Family', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0259030001 address="3968 ETON PL, SARASOTA, 34241" lat=27.296851 lon=-82.425345
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RSF-3", "zoningcode": "RSF-3", "zoninggroup": "Residential Single Family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0259030001', '0259030001', 824, 'RSF-3', 'Residential Single Family', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0285010011 address="5790 ROCK DOVE DR, SARASOTA, 34241" lat=27.269402 lon=-82.436919
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RSF-1", "zoningcode": "RSF-1", "zoninggroup": "Residential Single Family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0285010011', '0285010011', 824, 'RSF-1', 'Residential Single Family', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0405020050 address="312 RAVENNA ST S, NOKOMIS, FL- 34275" lat=27.121961 lon=-82.439124
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RC", "zoningcode": "RC", "zoninggroup": "Residential Conservation, Estate, Planned Unit Development"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0405020050', '0405020050', 824, 'RC', 'Residential Conservation, Estate, Planned Unit Development', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0405090032 address="BARNES PKWY, NOKOMIS, FL- 34275" lat=27.118933 lon=-82.436998
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "MP", "zoningcode": "MP", "zoninggroup": "Marine Park"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0405090032', '0405090032', 824, 'MP', 'Marine Park', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0457010084 address="1868 LAUREL ST" lat=27.33254 lon=-82.5330318
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSM-9", "ZONEDESC": "Residential Single Multiple 9 units per acre", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0457010084', '0457010084', 824, 'RSM-9', 'Residential Single Multiple 9 units per acre', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0471110001 address="3161 BAHIA VISTA ST" lat=27.3229182 lon=-82.5067083
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSF-3", "ZONEDESC": "Residential Single Family 3", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0471110001', '0471110001', 824, 'RSF-3', 'Residential Single Family 3', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0488030012 address="1711 BAYSHORE DR, ENGLEWOOD, FL- 34223" lat=26.9975 lon=-82.395112
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "RE-2", "zoningcode": "RE-2", "zoninggroup": "Residential Conservation, Estate, Planned Unit Development"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0488030012', '0488030012', 824, 'RE-2', 'Residential Conservation, Estate, Planned Unit Development', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0609020441 address="5850 VANDERIPE RD, SARASOTA, 34241" lat=27.267504 lon=-82.332939
-- source=scgov_arcgis jurisdiction_id=824
-- API response: {"attributes": {"municipality": "SC", "zoningdesignation": "OUE-1", "zoningcode": "OUE-1", "zoninggroup": "Open Use Estate, Planned Unit Devlopment"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0609020441', '0609020441', 824, 'OUE-1', 'Open Use Estate, Planned Unit Devlopment', 'scgov_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0944150414 address="5981 GALAMBOS ST, NORTH PORT, 34291" lat=27.111387 lon=-82.215947
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0944150414', '0944150414', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0949136822 address="BRISTOL AVE, NORTH PORT, FL- 34291" lat=27.106191 lon=-82.248263
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0949136822', '0949136822', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0950135901 address="CHORLEY AVE, NORTH PORT, FL- 34291" lat=27.098604 lon=-82.253668
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0950135901', '0950135901', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0951145620 address="5260 BOBWHITE ST, NORTH PORT, 34291" lat=27.103578 lon=-82.227415
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0951145620', '0951145620', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0952123324 address="LOFFREDA AVE, NORTH PORT, FL- 34291" lat=27.09896 lon=-82.229482
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0952123324', '0952123324', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0952125008 address="POMEROY ST, NORTH PORT, FL- 34291" lat=27.09373 lon=-82.22383
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0952125008', '0952125008', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0953151601 address="GADSHAW AVE, NORTH PORT, FL- 34291" lat=27.103425 lon=-82.213856
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0953151601', '0953151601', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0953152303 address="GRIGGS AVE, NORTH PORT, FL- 34291" lat=27.103344 lon=-82.210956
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0953152303', '0953152303', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0953152304 address="GRIGGS AVE, NORTH PORT, FL- 34291" lat=27.103391 lon=-82.210859
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0953152304', '0953152304', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0955155001 address="JAREMKO ST, NORTH PORT, FL- 34286" lat=27.100401 lon=-82.19923
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0955155001', '0955155001', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0957117603 address="SULTAN AVE, NORTH PORT, FL- 34286" lat=27.099636 lon=-82.173395
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0957117603', '0957117603', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0958066822 address="SHOREWOOD ST, NORTH PORT, FL- 34286" lat=27.092821 lon=-82.186442
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0958066822', '0958066822', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0958112505 address="WELLS AVE, NORTH PORT, FL- 34286" lat=27.093014 lon=-82.173014
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0958112505', '0958112505', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0959116110 address="N CHAMBERLAIN BLVD, NORTH PORT, FL- 34286" lat=27.10363 lon=-82.161989
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0959116110', '0959116110', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0959119320 address="0 NOWATNEY AVE, NORTH PORT, FL- 34286" lat=27.103504 lon=-82.169189
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0959119320', '0959119320', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0961111933 address="CINDERELLA RD, NORTH PORT, FL- 34286" lat=27.090785 lon=-82.166565
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0961111933', '0961111933', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0962089939 address="SAN MARIA CIR, NORTH PORT, FL- 34286" lat=27.082952 lon=-82.169392
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "CT", "zone_des": "Corridor, Transitional"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0962089939', '0962089939', 941, 'CT', 'Corridor, Transitional', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0962092423 address="OCEANSIDE ST, NORTH PORT, FL- 34286" lat=27.078954 lon=-82.162659
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0962092423', '0962092423', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0965054038 address="LA FRANCE AVE, NORTH PORT, FL- 34286" lat=27.087847 lon=-82.201995
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0965054038', '0965054038', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0967060208 address="GIMLET AVE, NORTH PORT, FL- 34291" lat=27.086858 lon=-82.218428
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0967060208', '0967060208', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0968061429 address="ALPEN AVE, NORTH PORT, FL- 34291" lat=27.079732 lon=-82.221442
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0968061429', '0968061429', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0969122727 address="COUCH TER, NORTH PORT, FL- 34291" lat=27.091538 lon=-82.229791
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0969122727', '0969122727', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0969122728 address="COUCH TER, NORTH PORT, FL- 34291" lat=27.091724 lon=-82.229707
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0969122728', '0969122728', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0970061218 address="ALPEN AVE, NORTH PORT, FL- 34291" lat=27.079344 lon=-82.223756
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0970061218', '0970061218', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0971131602 address="7873 MCPHAIL AVE, NORTH PORT, 34291" lat=27.089277 lon=-82.247358
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0971131602', '0971131602', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0972064619 address="AMERICANA AVE, NORTH PORT, FL- 34291" lat=27.081759 lon=-82.238618
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0972064619', '0972064619', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0972169157 address="0 RAOUL AVE, NORTH PORT, FL- 34291" lat=27.079208 lon=-82.25278
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0972169157', '0972169157', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0972171913 address="SKAGWAY TER, NORTH PORT, FL- 34291" lat=27.080441 lon=-82.242676
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0972171913', '0972171913', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0974182705 address="MALACARA TER, NORTH PORT, FL- 34287" lat=27.066228 lon=-82.252974
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0974182705', '0974182705', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0974183042 address="WAWANA RD, NORTH PORT, FL- 34287" lat=27.06529 lon=-82.251231
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0974183042', '0974183042', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0981040919 address="3041 WYOLA AVE, NORTH PORT, 34286" lat=27.072674 lon=-82.184764
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0981040919', '0981040919', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0984046914 address="0 W PRICE BLVD, NORTH PORT, FL- 34286" lat=27.068185 lon=-82.170067
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "CT", "zone_des": "Corridor, Transitional"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0984046914', '0984046914', 941, 'CT', 'Corridor, Transitional', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0985023413 address="SALMISTA TER, NORTH PORT, FL- 34286" lat=27.054841 lon=-82.167625
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0985023413', '0985023413', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0992186115 address="3372 CUNLIFFE RD, NORTH PORT, 34287" lat=27.054214 lon=-82.206995
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0992186115', '0992186115', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=0996183301 address="2972 STATE RD 776" lat=27.33744 lon=-82.510355
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "G", "ZONEDESC": "Governmental", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('0996183301', '0996183301', 824, 'G', 'Governmental', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1000030026 address="6871 OCEAN CT, NORTH PORT, FL- 34287" lat=27.035912 lon=-82.231018
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "MH", "zone_des": "Manufactured Housing"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1000030026', '1000030026', 941, 'MH', 'Manufactured Housing', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1000040038 address="6812 HOLO CT, NORTH PORT, FL- 34287" lat=27.033739 lon=-82.222462
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "MH", "zone_des": "Manufactured Housing"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1000040038', '1000040038', 941, 'MH', 'Manufactured Housing', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1000040323 address="5092 PALENA BLVD, NORTH PORT, FL- 34287" lat=27.033315 lon=-82.226341
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "MH", "zone_des": "Manufactured Housing"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1000040323', '1000040323', 941, 'MH', 'Manufactured Housing', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1000040509 address="6883 HIKINA DR, NORTH PORT, FL- 34287" lat=27.034321 lon=-82.223845
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "MH", "zone_des": "Manufactured Housing"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1000040509', '1000040509', 941, 'MH', 'Manufactured Housing', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1001276511 address="120 ROSE ST" lat=27.3067298 lon=-82.5319081
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSF-3", "ZONEDESC": "Residential Single Family 3", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1001276511', '1001276511', 824, 'RSF-3', 'Residential Single Family 3', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1004019716 address="SARAH TER, NORTH PORT, FL- 34286" lat=27.037977 lon=-82.191079
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1004019716', '1004019716', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1004019717 address="SARAH TER, NORTH PORT, FL- 34286" lat=27.037821 lon=-82.191284
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1004019717', '1004019717', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1004020213 address="AFAR AVE, NORTH PORT, FL- 34286" lat=27.035558 lon=-82.193
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1004020213', '1004020213', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1006021116 address="CORNSILK TER, NORTH PORT, FL- 34286" lat=27.034863 lon=-82.185584
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1006021116', '1006021116', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1094003500 address="PANACEA BLVD, NORTH PORT, FL- 34289" lat=27.092445 lon=-82.141611
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-4", "zone_des": "Activity Center 4"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1094003500', '1094003500', 941, 'AC-4', 'Activity Center 4', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1123232615 address="BIGNAY RD, NORTH PORT, FL- 34288" lat=27.07 lon=-82.090783
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-3", "zone_des": "Residential, Multi-family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1123232615', '1123232615', 941, 'R-3', 'Residential, Multi-family', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1123233334 address="LANGLAIS DR, NORTH PORT, FL- 34288" lat=27.069835 lon=-82.092506
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-3", "zone_des": "Residential, Multi-family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1123233334', '1123233334', 941, 'R-3', 'Residential, Multi-family', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1124207136 address="BARCELONA DR, NORTH PORT, FL- 34288" lat=27.064187 lon=-82.094173
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1124207136', '1124207136', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125229401 address="BURDEKIN ST, NORTH PORT, FL- 34288" lat=27.07213 lon=-82.080064
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125229401', '1125229401', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125229417 address="KAMAIN RD, NORTH PORT, FL- 34288" lat=27.074441 lon=-82.077702
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125229417', '1125229417', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125229431 address="KAMAIN RD, NORTH PORT, FL- 34288" lat=27.071851 lon=-82.079513
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125229431', '1125229431', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125229519 address="KAMAIN RD, NORTH PORT, FL- 34288" lat=27.074389 lon=-82.076928
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125229519', '1125229519', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125229520 address="KAMAIN RD, NORTH PORT, FL- 34288" lat=27.074471 lon=-82.076648
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125229520', '1125229520', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125231002 address="LANGLAIS DR, NORTH PORT, FL- 34288" lat=27.075231 lon=-82.083532
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125231002', '1125231002', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125231833 address="BIGNAY RD, NORTH PORT, FL- 34288" lat=27.074384 lon=-82.090407
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125231833', '1125231833', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1125232904 address="GUIANA AVE, NORTH PORT, FL- 34288" lat=27.069365 lon=-82.087165
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-3", "zone_des": "Residential, Multi-family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1125232904', '1125232904', 941, 'R-3', 'Residential, Multi-family', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1126233240 address="LANGLAIS DR, NORTH PORT, FL- 34288" lat=27.065933 lon=-82.088617
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-3", "zone_des": "Residential, Multi-family"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1126233240', '1126233240', 941, 'R-3', 'Residential, Multi-family', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1127225902 address="BIGFLOWER AVE, NORTH PORT, FL- 34288" lat=27.06954 lon=-82.059151
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1127225902', '1127225902', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1127227701 address="LANCEWOOD RD, NORTH PORT, FL- 34288" lat=27.072998 lon=-82.068648
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1127227701', '1127227701', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1127227908 address="PIMENTO CIR, NORTH PORT, FL- 34288" lat=27.07208 lon=-82.064295
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1127227908', '1127227908', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1127227923 address="SILVERLEAF RD, NORTH PORT, FL- 34288" lat=27.070917 lon=-82.064517
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1127227923', '1127227923', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1128225508 address="OLD WINE RD, NORTH PORT, FL- 34288" lat=27.066611 lon=-82.058954
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1128225508', '1128225508', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1128226912 address="SILVERLEAF RD, NORTH PORT, FL- 34288" lat=27.061948 lon=-82.0685
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-6", "zone_des": "Activity Center 6"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1128226912', '1128226912', 941, 'AC-6', 'Activity Center 6', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1128227227 address="LONGAN RD, NORTH PORT, FL- 34288" lat=27.064714 lon=-82.071496
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-6", "zone_des": "Activity Center 6"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1128227227', '1128227227', 941, 'AC-6', 'Activity Center 6', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1129220904 address="EWEN DR, NORTH PORT, FL- 34288" lat=27.056937 lon=-82.058529
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1129220904', '1129220904', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1129221202 address="EWEN CIR, NORTH PORT, FL- 34288" lat=27.059704 lon=-82.059751
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1129221202', '1129221202', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1130218602 address="FIREGLOW CIR, NORTH PORT, FL- 34288" lat=27.047879 lon=-82.06266
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1130218602', '1130218602', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1132212412 address="IRONSIDE ST, NORTH PORT, FL- 34288" lat=27.050622 lon=-82.079907
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-6", "zone_des": "Activity Center 6"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1132212412', '1132212412', 941, 'AC-6', 'Activity Center 6', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1132212903 address="MARLBOROUGH AVE, NORTH PORT, FL- 34288" lat=27.048461 lon=-82.076415
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-6", "zone_des": "Activity Center 6"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1132212903', '1132212903', 941, 'AC-6', 'Activity Center 6', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1133207123 address="BANNOCK CIR, NORTH PORT, FL- 34288" lat=27.060424 lon=-82.093111
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1133207123', '1133207123', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1134201420 address="PILGRIM RD, NORTH PORT, FL- 34288" lat=27.047644 lon=-82.10084
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1134201420', '1134201420', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1134201602 address="GOVAN RD, NORTH PORT, FL- 34288" lat=27.047654 lon=-82.098691
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1134201602', '1134201602', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1134201717 address="ANTIQUE CIR, NORTH PORT, FL- 34288" lat=27.04865 lon=-82.092233
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1134201717', '1134201717', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1134209603 address="EASTMAN CIR, NORTH PORT, FL- 34288" lat=27.05188 lon=-82.090726
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1134209603', '1134209603', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1147200405 address="WINTERVILLE CIR, NORTH PORT, FL- 34288" lat=27.040727 lon=-82.099108
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1147200405', '1147200405', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1147202712 address="VINEYARD CIR, NORTH PORT, FL- 34288" lat=27.044344 lon=-82.092411
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1147202712', '1147202712', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1147203405 address="WHALING RD, NORTH PORT, FL- 34288" lat=27.041083 lon=-82.095196
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1147203405', '1147203405', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1147203424 address="0 VINEYARD CIR, NORTH PORT, FL- 34288" lat=27.040688 lon=-82.094596
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1147203424', '1147203424', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1147203507 address="VINEYARD CIR, NORTH PORT, FL- 34288" lat=27.040188 lon=-82.095272
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1147203507', '1147203507', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1148199006 address="PENNY CIR, NORTH PORT, FL- 34288" lat=27.034308 lon=-82.104705
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1148199006', '1148199006', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1148199403 address="MATTOX CIR, NORTH PORT, FL- 34288" lat=27.036949 lon=-82.106131
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "R-1", "zone_des": "Residential, Low"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1148199403', '1148199403', 941, 'R-1', 'Residential, Low', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1148204314 address="TWISDALE CIR, NORTH PORT, FL- 34288" lat=27.035322 lon=-82.101
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1148204314', '1148204314', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149211727 address="GRENARD CIR, NORTH PORT, FL- 34288" lat=27.04658 lon=-82.085761
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149211727', '1149211727', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149211729 address="GRENARD CIR, NORTH PORT, FL- 34288" lat=27.046171 lon=-82.085959
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149211729', '1149211729', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149211738 address="GRENARD CIR, NORTH PORT, FL- 34288" lat=27.04388 lon=-82.08623
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149211738', '1149211738', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149211750 address="GRENARD CIR, NORTH PORT, FL- 34288" lat=27.045167 lon=-82.087638
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149211750', '1149211750', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149211812 address="GRENARD CIR, NORTH PORT, FL- 34288" lat=27.04668 lon=-82.08683
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149211812', '1149211812', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149214003 address="HOLLISTER AVE, NORTH PORT, FL- 34288" lat=27.042876 lon=-82.083329
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149214003', '1149214003', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149214707 address="HARCOURT CIR, NORTH PORT, FL- 34288" lat=27.044856 lon=-82.078383
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149214707', '1149214707', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149215110 address="NEWMAN DR, NORTH PORT, FL- 34288" lat=27.040631 lon=-82.083069
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149215110', '1149215110', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149216236 address="NET CT, NORTH PORT, FL- 34288" lat=27.042484 lon=-82.076366
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149216236', '1149216236', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149216239 address="NEWMAN DR, NORTH PORT, FL- 34288" lat=27.042645 lon=-82.076154
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149216239', '1149216239', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149216511 address="HAMPSHIRE CIR, NORTH PORT, FL- 34288" lat=27.045687 lon=-82.07729
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-6", "zone_des": "Activity Center 6"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149216511', '1149216511', 941, 'AC-6', 'Activity Center 6', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1149216703 address="MANSFIELD CIR, NORTH PORT, FL- 34288" lat=27.043488 lon=-82.07491
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1149216703', '1149216703', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1150216203 address="NORTON DR, NORTH PORT, FL- 34288" lat=27.038006 lon=-82.07882
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1150216203', '1150216203', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1150234319 address="JASPER TER, NORTH PORT, FL- 34288" lat=27.033959 lon=-82.077711
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1150234319', '1150234319', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1150247721 address="VETERANS BLVD, NORTH PORT, FL- 34288" lat=27.032523 lon=-82.08355
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1150247721', '1150247721', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1151217009 address="MANSFIELD CIR, NORTH PORT, FL- 34288" lat=27.042649 lon=-82.073286
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1151217009', '1151217009', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1151217302 address="AUTUMNLEAF TER, NORTH PORT, FL- 34288" lat=27.04057 lon=-82.059842
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1151217302', '1151217302', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1151217712 address="FLAMBEAU AVE, NORTH PORT, FL- 34288" lat=27.042644 lon=-82.059331
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1151217712', '1151217712', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1151226508 address="BLUELEAF DR, NORTH PORT, FL- 34288" lat=27.039887 lon=-82.06028
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1151226508', '1151226508', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1151226511 address="BLUELEAF DR, NORTH PORT, FL- 34288" lat=27.040386 lon=-82.060906
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1151226511', '1151226511', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1151235515 address="ALLISON CIR, NORTH PORT, FL- 34288" lat=27.040375 lon=-82.070847
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1151235515', '1151235515', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1151235519 address="ALLISON CIR, NORTH PORT, FL- 34288" lat=27.040374 lon=-82.071408
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1151235519', '1151235519', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=1152236811 address="RICHBRIAR DR, NORTH PORT, FL- 34288" lat=27.034408 lon=-82.062594
-- source=northport_gis_arcgis jurisdiction_id=941
-- API response: {"attributes": {"zone": null, "zone_abbr": "AC-10", "zone_des": "Activity Center 10"}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('1152236811', '1152236811', 941, 'AC-10', 'Activity Center 10', 'northport_gis_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=2004020016 address="46TH ST, SARASOTA, FL- 34234" lat=27.373549 lon=-82.552043
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSF-3", "ZONEDESC": "Residential Single Family 3", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('2004020016', '2004020016', 824, 'RSF-3', 'Residential Single Family 3', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=2021030097 address="3752 GLEN OAKS MANOR DR" lat=27.3486922 lon=-82.4966305
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RMF-1", "ZONEDESC": "Residential Multiple Family 1", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('2021030097', '2021030097', 824, 'RMF-1', 'Residential Multiple Family 1', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=2022151182 address="3381 RAMBLEWOOD PL, SARASOTA, 34237" lat=27.3463145 lon=-82.5015829
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RMF-2", "ZONEDESC": "Residential Multiple Family 2", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('2022151182', '2022151182', 824, 'RMF-2', 'Residential Multiple Family 2', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=2024020086 address="1762 25TH ST, SARASOTA, FL- 34234" lat=27.358878 lon=-82.535117
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSF-4", "ZONEDESC": "Residential Single Family 4", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('2024020086', '2024020086', 824, 'RSF-4', 'Residential Single Family 4', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=2024080009 address="2106 N OSPREY AVE, SARASOTA, FL- 34234" lat=27.356185 lon=-82.534528
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSF-4", "ZONEDESC": "Residential Single Family 4", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('2024080009', '2024080009', 824, 'RSF-4', 'Residential Single Family 4', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=2033130048 address="413 GOLDEN SANDS DR, SARASOTA, FL- 34232" lat=27.331649 lon=-82.496792
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSF-3", "ZONEDESC": "Residential Single Family 3", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('2033130048', '2033130048', 824, 'RSF-3', 'Residential Single Family 3', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- parcel_id=2035030040 address="2370 BAHIA VISTA ST, SARASOTA, 34239" lat=27.322587 lon=-82.522433
-- source=cos_zoning_arcgis jurisdiction_id=824
-- API response: {"attributes": {"ZONECLASS": "RSF-4", "ZONEDESC": "Residential Single Family 4", "ORD_NO": " "}}
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES ('2035030040', '2035030040', 824, 'RSF-4', 'Residential Single Family 4', 'cos_zoning_arcgis') ON CONFLICT (tax_account, jurisdiction_id) DO NOTHING;

-- ============================================================
-- Rows investigated but NOT inserted (BLANK > WRONG)
-- ============================================================
--
-- Venice-addressed rows skipped without querying (prior-session-proven unreliable source):
--   0409101101  228 OUTER DR E, VENICE, FL- 34285
--   0433060013  1791 FAUN RD, VENICE, 34293
--   0436010038  1250 CAMBRIDGE DR, VENICE, FL- 34293
--   0449010115  1065 DARWIN RD, VENICE, FL- 34293
--   0452090065  0 DEVON RD, VENICE, FL- 34293
--   0758150021  11881 HUNTERS CREEK RD, VENICE, 34293
--
-- scgov placeholder-municipality / no-feature rows with no working fallback this session:
--   0104010003  1945 GULF OF MEXICO DR #M2-504  (NO_MATCH (scgov_municipality=TLK))
--   0410070004  1215 CYPRESS AVE  (NO_MATCH (scgov_municipality=CV))
--   0410150030  417 BEACH RD #4  (NO_MATCH (scgov_municipality=CV))
--   0441074012  3254 ELLIOTT ST  (NO_MATCH (scgov_municipality=None))
--   1125231001  N HOLLOWAY AVE  (NO_MATCH (scgov_municipality=None))
--   1130216726  CAPE COD RD  (NO_MATCH (scgov_municipality=None))
--   1130222110  GRIGGS AVE  (NO_MATCH (scgov_municipality=None))
--   1135101314  GEORGIA AVE  (NO_MATCH (scgov_municipality=None))
--   1147201006  HAYWARD AVE  (NO_MATCH (scgov_municipality=None))
--   1147202717  MANGROVE AVE  (NO_MATCH (scgov_municipality=None))
--   1147205625  MANGROVE AVE  (NO_MATCH (scgov_municipality=None))
--   1148206317  JULIANNA ST  (NO_MATCH (scgov_municipality=None))
--   1151217604  COURTLAND AVE  (NO_MATCH (scgov_municipality=None))
--
-- North-Port-addressed rows with a live query returning zero features (point falls outside
-- all mapped zoning polygons in the North Port layer -- not a source failure, a real gap):
--   0769160031  421 CALBIRA AVE, NORTH PORT, 34287
--   0789011099  99 LAKEVIEW DR, NORTH PORT, FL- 34287
--   0790013665  640 FAIRMOUNT DR, NORTH PORT, FL- 34287
