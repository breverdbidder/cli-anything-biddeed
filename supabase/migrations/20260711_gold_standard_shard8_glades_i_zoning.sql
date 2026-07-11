-- ============================================================
-- Glades I fix -- REAL zoning wiring from Glades County GIS
-- Dispatch: Gold Standard shard-8 (glades), run3713 continuation
-- Counties: glades only
-- ============================================================
--
-- CONTEXT (VERIFIED live 2026-07-11):
--   A parallel agent in this same run backfilled property_address /
--   latitude / longitude / assessed_value / market_value for 68 of glades'
--   70 real multi_county_auctions rows (scripts/gold_standard_shard8_glades_i_enrichment.py,
--   source: FL DOR statewide cadastral FeatureServer, dash-stripped
--   PARCEL_ID match). Confirmed live: pencil_dod_evaluate_county('glades')
--   still showed I: card_complete=0 of 70 after that enrichment, because
--   v_zoning_gold_standard_card had only 2 glades rows total, BOTH of which
--   are SYNTHETIC placeholders (parcel_id 'SYN-GLD-TD-001' /
--   'SYN-GLD-FC-001', source='shard9_synthetic_20260624/glades', zone_code
--   hardcoded 'R-1' for both) -- zero real parcel_zones linkage existed for
--   our actual 70 glades auction parcels. THIS is the true I blocker, not
--   the enrichment (which is separately correct and necessary but not
--   sufficient).
--
-- FIX (this migration): insert REAL parcel_zones rows for all 65 unique
-- lat/lon-enriched glades parcels (68 lat/lon-enriched auction rows collapse
-- to 65 unique parcel_ids -- 3 parcels are shared by 2 case_numbers each,
-- e.g. re-noticed/re-scheduled tax deed sales of the same property),
-- sourced LIVE via point-in-polygon query against Glades County's own
-- public ArcGIS Zoning MapServer (ground-truth authority, same class of
-- source as Collier's Zoning_General FeatureServer used earlier this
-- session):
--
--   https://gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer
--     layer 1 = MH_Zoning     (City of Moore Haven zoning, field Z010_ZONG,
--                               2 codes seen: R1='Low', R2='Med')
--     layer 2 = county_zoning (unincorporated Glades zoning, fields
--                               Zoning/ZonDistNam, 5 codes seen: AR, OUA,
--                               RG, RM, RS)
--   (hosted on the Hendry County Property Appraiser's GIS server --
--   gis1.hcpao.org -- under a "Glades" services folder; this is a real,
--   live, public ArcGIS REST endpoint returning genuine per-parcel zoning
--   polygons for Glades County, discovered via web search 2026-07-11 and
--   confirmed by cross-referencing 5 MH_Zoning matches against their
--   independently-sourced property_address, all 5 of which read
--   "... Moore Haven, FL" -- consistent, not coincidental.)
--
-- Every one of the 65 unique lat/lon-bearing glades parcels was queried
-- live by point-in-polygon (geometry=parcel centroid lon,lat, inSR=4326)
-- against layer 2 first (covers the whole county per its fullExtent),
-- falling back to layer 1 only when layer 2 returned zero features. ALL 65
-- landed inside a genuine zoning polygon -- 5 in Moore Haven (jurisdiction
-- 899, layer 1 MH_Zoning) and 60 in unincorporated Glades (jurisdiction
-- 1153, layer 2 county_zoning). Query script (read-only, prints results,
-- does not write): scripts/gold_standard_shard8_glades_i_zoning_query.py.
--
-- NOT LINKED in this migration (deliberately, not a fabrication gap):
--   5 of the 70 total glades auction rows never resolved a FL DOR cadastral
--   match in the upstream enrichment step (2 rows: parcel_id NULL /
--   FeatureServer zero-match, per that script's own docstring) and
--   therefore have no lat/lon to point-in-polygon query in the first place.
--   Additionally 3 of the 68 lat/lon-bearing rows share a parcel_id with
--   another row already counted (same physical parcel, re-noticed tax deed
--   sale) -- those 3 duplicate case_numbers still get their own
--   parcel_zones linkage credit via the SAME zone_code (correct, since it
--   is genuinely the same real-world parcel), not double-counted as a new
--   query.
--
-- NOT WRITTEN in this migration (deliberately out of scope):
--   zone_standards (setbacks/height/density/FAR/parking) for the 7 real
--   zone codes above (R1, R2, AR, OUA, RG, RM, RS). The
--   v_zoning_gold_standard_card view LEFT JOINs zone_standards, and I's
--   card_complete definition only requires zone_code IS NOT NULL from
--   parcel_zones (NOT any zone_standards field) -- so this migration is
--   sufficient for I on its own merits without fabricating setback/density
--   numbers not scraped from a real ordinance. Scraping Glades County's
--   actual Land Development Code per-district standards for these 7 codes
--   is a real, larger task sized as a residual for a future session -- this
--   migration does NOT touch zone_standards, only zone_code linkage
--   (parcel_zones + zoning_districts registration).
--   The 2 pre-existing SYNTHETIC 'SYN-GLD-TD-001'/'SYN-GLD-FC-001' rows in
--   parcel_zones are NOT deleted here (out of scope / no destructive ops
--   without explicit approval per CLAUDE.md) -- they simply do not match
--   any real auction parcel_id so they do not affect I's numerator either
--   way.
-- ============================================================

SET statement_timeout = 0;

-- ── Step 1: zoning_districts ── real zone codes from Glades County GIS ──
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
VALUES
    ('R1', 'Low Density Residential', 899, 'residential',
     'Real zone code (Z010_ZONG=R1, Z020_FLUM=Low) from City of Moore Haven MH_Zoning layer, Glades County Zoning ArcGIS MapServer (gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer/1), point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('R2', 'Medium Density Residential', 899, 'residential',
     'Real zone code (Z010_ZONG=R2, Z020_FLUM=Med) from City of Moore Haven MH_Zoning layer, Glades County Zoning ArcGIS MapServer (gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer/1), point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('AR', 'Agricultural Residential', 1153, 'agricultural',
     'Real zone code (Zoning=AR, ZonDistNam=Agricultural Residential) from Glades County county_zoning layer, Glades County Zoning ArcGIS MapServer (gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer/2), point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('OUA', 'Open Use Agricultural', 1153, 'agricultural',
     'Real zone code (Zoning=OUA, ZonDistNam=Open Use Agricultural) from Glades County county_zoning layer, Glades County Zoning ArcGIS MapServer (gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer/2), point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RG', 'Residential General', 1153, 'residential',
     'Real zone code (Zoning=RG, ZonDistNam=Residential General) from Glades County county_zoning layer, Glades County Zoning ArcGIS MapServer (gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer/2), point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RM', 'Residential Mixed', 1153, 'residential',
     'Real zone code (Zoning=RM, ZonDistNam=Residential Mixed) from Glades County county_zoning layer, Glades County Zoning ArcGIS MapServer (gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer/2), point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RS', 'Residential Single-family', 1153, 'residential',
     'Real zone code (Zoning=RS, ZonDistNam=Residential Single-family) from Glades County county_zoning layer, Glades County Zoning ArcGIS MapServer (gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer/2), point-in-polygon queried live by parcel centroid 2026-07-11.')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── Step 2: parcel_zones ── link 65 real glades parcels to their real zone ──
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
    ('S11-42-32-003-0168-0110', 'S11-42-32-003-0168-0110', 899, 'R2', 'Medium Density Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/1:point=-81.0972491139271,26.8407077904047:2026-07-11'),
    ('S36-38-34-004-0000-00A0', 'S36-38-34-004-0000-00A0', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-80.8882824296351,27.1261594110621:2026-07-11'),
    ('A01-42-28-A00-001D-0000', 'A01-42-28-A00-001D-0000', 1153, 'AR', 'Agricultural Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4684146301164,26.8555555396327:2026-07-11'),
    ('S34-40-30-002-0091-0140', 'S34-40-30-002-0091-0140', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3108881580706,26.9425904187509:2026-07-11'),
    ('A23-40-32-U03-0000-0180', 'A23-40-32-U03-0000-0180', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0903566064972,26.9815990195029:2026-07-11'),
    ('A23-40-32-U03-0000-0230', 'A23-40-32-U03-0000-0230', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0903512985474,26.9812426390589:2026-07-11'),
    ('S31-42-30-102-0042-0030', 'S31-42-30-102-0042-0030', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3624827017061,26.7746837183703:2026-07-11'),
    ('S31-42-30-102-0063-0500', 'S31-42-30-102-0063-0500', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3552674620988,26.7801427599382:2026-07-11'),
    ('A22-42-32-U02-0000-005A', 'A22-42-32-U02-0000-005A', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.1173800884571,26.805601421069:2026-07-11'),
    ('S31-42-30-102-0050-0170', 'S31-42-30-102-0050-0170', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.355947622165,26.770226205532:2026-07-11'),
    ('A02-42-32-U04-0000-0120', 'A02-42-32-U04-0000-0120', 1153, 'AR', 'Agricultural Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0999135564059,26.8428538971547:2026-07-11'),
    ('S34-40-30-002-0071-0140', 'S34-40-30-002-0071-0140', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3057125410451,26.9441242361178:2026-07-11'),
    ('A35-38-34-A00-001B-0030', 'A35-38-34-A00-001B-0030', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-80.8903763890862,27.134596354212:2026-07-11'),
    ('S02-42-32-001-0006-0010', 'S02-42-32-001-0006-0010', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0989609524581,26.8423021375857:2026-07-11'),
    ('S02-42-32-001-0009-0090', 'S02-42-32-001-0009-0090', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0971129389679,26.841533249155:2026-07-11'),
    ('S02-42-32-002-0008-0170', 'S02-42-32-002-0008-0170', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0957396591721,26.8411860341024:2026-07-11'),
    ('S31-42-30-102-0030-0020', 'S31-42-30-102-0030-0020', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3636095237691,26.7737947080856:2026-07-11'),
    ('S31-42-30-102-0033-0040', 'S31-42-30-102-0033-0040', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3690115135902,26.7717592502705:2026-07-11'),
    ('S31-42-30-102-0063-0320', 'S31-42-30-102-0063-0320', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3576430234754,26.7793525118764:2026-07-11'),
    ('S31-42-30-102-0063-0430', 'S31-42-30-102-0063-0430', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.356546909391,26.7811247776304:2026-07-11'),
    ('S31-42-30-102-0038-0220', 'S31-42-30-102-0038-0220', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3624045350639,26.7698632597266:2026-07-11'),
    ('S31-42-30-102-0022-0360', 'S31-42-30-102-0022-0360', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3692468758506,26.7762057131742:2026-07-11'),
    ('S28-42-31-002-000B-0060', 'S28-42-31-002-000B-0060', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.2235938410746,26.7846883380101:2026-07-11'),
    ('S28-42-31-002-000B-0100', 'S28-42-31-002-000B-0100', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.2230678027904,26.7851752618219:2026-07-11'),
    ('S14-42-32-005-000C-0010', 'S14-42-32-005-000C-0010', 899, 'R1', 'Low Density Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/1:point=-81.0984337556146,26.8238720848718:2026-07-11'),
    ('S02-42-32-001-0009-0060', 'S02-42-32-001-0009-0060', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0970801836286,26.8417675808615:2026-07-11'),
    ('S31-42-30-102-0066-0060', 'S31-42-30-102-0066-0060', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3590485909472,26.780618139552:2026-07-11'),
    ('S31-42-30-102-0068-0390', 'S31-42-30-102-0068-0390', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.357681471739,26.7831535388285:2026-07-11'),
    ('S02-42-32-001-0007-0050', 'S02-42-32-001-0007-0050', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.098306278184,26.8418622285831:2026-07-11'),
    ('S11-42-32-003-0072-0010', 'S11-42-32-003-0072-0010', 899, 'R2', 'Medium Density Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/1:point=-81.1000165878319,26.83691733629:2026-07-11'),
    ('S18-40-33-001-0000-0270', 'S18-40-33-001-0000-0270', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0559757237427,27.0039289208826:2026-07-11'),
    ('S01-42-28-001-0002-0280', 'S01-42-28-001-0002-0280', 1153, 'AR', 'Agricultural Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4730638854517,26.8540722338121:2026-07-11'),
    ('S01-42-28-001-0003-0470', 'S01-42-28-001-0003-0470', 1153, 'AR', 'Agricultural Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4714344820568,26.8549073518263:2026-07-11'),
    ('S01-42-28-001-0006-0070', 'S01-42-28-001-0006-0070', 1153, 'AR', 'Agricultural Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4746805129892,26.8558811861667:2026-07-11'),
    ('S29-42-28-002-0008-0290', 'S29-42-28-002-0008-0290', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.5467510665103,26.7898151376476:2026-07-11'),
    ('S29-42-28-004-0017-0050', 'S29-42-28-004-0017-0050', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.5430717846847,26.7843371572158:2026-07-11'),
    ('S31-42-30-102-0044-0040', 'S31-42-30-102-0044-0040', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3615428320097,26.7770934620922:2026-07-11'),
    ('S31-42-30-102-0039-0070', 'S31-42-30-102-0039-0070', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3639153694051,26.7698479296585:2026-07-11'),
    ('S31-42-30-102-0068-0640', 'S31-42-30-102-0068-0640', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.355779733378,26.784975127484:2026-07-11'),
    ('A01-42-28-U02-000A-0080', 'A01-42-28-U02-000A-0080', 1153, 'AR', 'Agricultural Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4761922975828,26.848041816805:2026-07-11'),
    ('A28-40-32-A00-012B-002B', 'A28-40-32-A00-012B-002B', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.1276015268649,26.9673090109037:2026-07-11'),
    ('A12-42-32-A00-019A-0030', 'A12-42-32-A00-019A-0030', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0879594782236,26.8319460406586:2026-07-11'),
    ('S11-42-32-001-0016-0060', 'S11-42-32-001-0016-0060', 899, 'R2', 'Medium Density Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/1:point=-81.1033720748896,26.8396649048822:2026-07-11'),
    ('S31-42-30-102-0040-0510', 'S31-42-30-102-0040-0510', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3616277919601,26.7740904277946:2026-07-11'),
    ('S36-38-34-016-000A-0030', 'S36-38-34-016-000A-0030', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-80.8992463762587,27.1290579200886:2026-07-11'),
    ('S11-42-32-003-0049-0090', 'S11-42-32-003-0049-0090', 899, 'R2', 'Medium Density Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/1:point=-81.0996131404367,26.8382820587244:2026-07-11'),
    ('A23-42-28-A00-0020-0000', 'A23-42-28-A00-0020-0000', 1153, 'OUA', 'Open Use Agricultural', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4981643629918,26.8063395559478:2026-07-11'),
    ('S34-40-30-002-0105-0170', 'S34-40-30-002-0105-0170', 1153, 'RM', 'Residential Mixed', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3085336842285,26.9401988652162:2026-07-11'),
    ('A07-42-28-A00-0040-0000', 'A07-42-28-A00-0040-0000', 1153, 'AR', 'Agricultural Residential', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.5542094718334,26.8290691686496:2026-07-11'),
    ('A25-42-28-U01-0007-3350', 'A25-42-28-U01-0007-3350', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4731210621792,26.7949693053696:2026-07-11'),
    ('A25-42-28-U01-0004-2000', 'A25-42-28-U01-0004-2000', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.4792481204389,26.7864939449842:2026-07-11'),
    ('S31-42-30-102-0046-0060', 'S31-42-30-102-0046-0060', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3642415601244,26.7796062139196:2026-07-11'),
    ('S31-42-30-102-0046-0070', 'S31-42-30-102-0046-0070', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3641185649928,26.7797966065433:2026-07-11'),
    ('S31-42-30-102-0049-0160', 'S31-42-30-102-0049-0160', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3557039825847,26.7693730270589:2026-07-11'),
    ('S31-42-30-102-0052-0010', 'S31-42-30-102-0052-0010', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3564838511597,26.7731800685315:2026-07-11'),
    ('S31-42-30-102-0052-0110', 'S31-42-30-102-0052-0110', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3547634805562,26.7717674242291:2026-07-11'),
    ('S28-42-31-002-000C-0240', 'S28-42-31-002-000C-0240', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.2275361856986,26.7833663852327:2026-07-11'),
    ('S28-41-30-002-0126-0020', 'S28-41-30-002-0126-0020', 1153, 'OUA', 'Open Use Agricultural', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3292055782913,26.8712006485423:2026-07-11'),
    ('S31-42-30-102-0023-0370', 'S31-42-30-102-0023-0370', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3662848921068,26.7738997574378:2026-07-11'),
    ('S31-42-30-102-0024-0040', 'S31-42-30-102-0024-0040', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3677257518282,26.7741136716278:2026-07-11'),
    ('S31-42-30-102-0040-0160', 'S31-42-30-102-0040-0160', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3606400667467,26.7713396953709:2026-07-11'),
    ('S31-42-30-102-0040-0210', 'S31-42-30-102-0040-0210', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3601050685811,26.7720243307738:2026-07-11'),
    ('S23-40-32-006-0000-005A', 'S23-40-32-006-0000-005A', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.0991457014024,26.9861836517429:2026-07-11'),
    ('S29-42-28-004-0007-0110', 'S29-42-28-004-0007-0110', 1153, 'RG', 'Residential General', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.5420572617334,26.7864086830249:2026-07-11'),
    ('S31-42-30-102-0042-0180', 'S31-42-30-102-0042-0180', 1153, 'RS', 'Residential Single-family', 'glades_gis_live:GladesCounty_Zoning/MapServer/2:point=-81.3629082490973,26.7749837363502:2026-07-11')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET
    zone_code = EXCLUDED.zone_code,
    zone_name = EXCLUDED.zone_name,
    source    = EXCLUDED.source;

-- ── Verification ─────────────────────────────────────────────────────────────

SELECT 'parcel_zones glades real' AS check_name, count(*) AS n
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE lower(COALESCE(j.county_name, j.county)) = 'glades'
  AND pz.source LIKE 'glades_gis_live%';

SELECT 'card_view glades real' AS check_name, count(*) AS n
FROM v_zoning_gold_standard_card
WHERE lower(county) = 'glades'
  AND parcel_id NOT LIKE 'SYN-GLD-%';
