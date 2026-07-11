-- ============================================================
-- Collier I fix -- REAL zoning wiring from Collier County GIS
-- Dispatch: Gold Standard shard-1 (collier), run3713 continuation
-- Counties: collier only
-- ============================================================
--
-- CONTEXT (VERIFIED live 2026-07-11):
--   property_address / latitude / longitude / assessed_value / market_value
--   were backfilled for 204 of 212 real collier multi_county_auctions rows
--   in this same session (scripts/gold_standard_shard1_collier_i_enrichment.py,
--   source: FL DOR statewide cadastral FeatureServer). Confirmed live:
--   pencil_dod_evaluate_county('collier') still showed I: card_complete=0 of
--   212 even after that enrichment, because v_zoning_gold_standard_card had
--   only 6 collier rows total, ALL of which are SYNTHETIC placeholders
--   (parcel_id like 'COLLIER-FC-000%' / 'COLLIER-TD-000%',
--   source='shard5_bootstrap_collier', zone_code hardcoded 'RSF-3' for
--   every row) -- zero real parcel_zones linkage existed for our actual 212
--   collier auction parcels. THIS is the true I blocker, not the
--   enrichment (which is separately correct and necessary but not
--   sufficient).
--
-- FIX (this migration): insert REAL parcel_zones rows for 190 of the 204
-- lat/lon-enriched collier parcels, sourced LIVE via point-in-polygon query
-- against Collier County's own public ArcGIS Zoning_General FeatureServer
-- (ground-truth authority, same class of source as BCPAO/FL DOR used
-- elsewhere in this project):
--
--   https://services2.arcgis.com/SlIq32SqARUHIhSx/arcgis/rest/services/
--     Zoning_General_(Editable)_view/FeatureServer/1
--   (fields: ZONING, DISTRICT, MUNICODE, BASE)
--
-- Every one of the 204 lat/lon-bearing collier parcels was queried live by
-- point-in-polygon (geometry=parcel centroid lon,lat) against this layer.
-- 190 landed inside a genuine unincorporated-Collier zoning polygon with a
-- real BASE code (16 distinct codes: A, C-1, C-4, C-5, CON, E, I, MH, PUD,
-- RMF-12, RMF-6, RSF-3, RSF-4, RSF-5, RT, VR). All 190 are written below,
-- linked to jurisdiction_id=632 ("Collier County (Unincorporated)").
--
-- NOT LINKED in this migration (deliberately, not a fabrication gap):
--   14 of the 204 parcels physically sit inside an INCORPORATED city
--   (Naples, Marco Island, or Everglades City) and this county-maintained
--   layer returns BASE='CITY', DISTRICT='Incorporated Area',
--   ZONING='CITY OF NAPLES' (or similar) for those points instead of a real
--   zoning code -- Collier County does not track city-level zoning detail
--   in this layer. This is a genuine platform limitation, not a query
--   error (all 14 were independently confirmed to have a real situs
--   address inside Naples/Marco Island/Everglades City city limits). Real
--   city-level zoning layers for these 3 municipalities were NOT
--   discovered/scraped this pass -- sized as a residual for a future
--   session. These 14 rows remain in v_zoning_gold_standard_card's
--   denominator gap (no parcel_zones row) and are correctly excluded here
--   rather than fabricating a zone code.
--   8 of the 212 total collier auction parcels never resolved a FL DOR
--   cadastral match at all (see enrichment script docstring) and therefore
--   have no lat/lon to point-in-polygon query in the first place -- also
--   correctly excluded.
--
-- NOT WRITTEN in this migration (deliberately out of scope):
--   zone_standards (setbacks/height/density/FAR/parking) for the 16 real
--   zone codes above. The v_zoning_gold_standard_card view LEFT JOINs
--   zone_standards, and I's card_complete definition only requires
--   zone_code IS NOT NULL from parcel_zones (NOT any zone_standards
--   field) -- so this migration is sufficient for I on its own merits
--   without fabricating setback/density numbers not scraped from a real
--   ordinance. Scraping Collier's actual LDC (Land Development Code)
--   per-district standards for these 16 codes is a real, larger task
--   (Phase 4 of the county-expansion pipeline) sized as a residual for a
--   future session -- this migration does NOT touch zone_standards, only
--   zone_code linkage (parcel_zones + zoning_districts registration).
--   The 6 pre-existing SYNTHETIC 'COLLIER-FC-000%'/'COLLIER-TD-000%' rows
--   in parcel_zones are NOT deleted here (out of scope / no destructive
--   ops without explicit approval per CLAUDE.md) -- they simply do not
--   match any real auction parcel_id so they do not affect I's numerator
--   either way.
-- ============================================================

SET statement_timeout = 0;

-- ── Step 1: zoning_districts ── real zone codes from Collier GIS Zoning_General ──
INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
VALUES
    ('A', 'Agricultural', 632, 'agricultural',
     'Real zone code (BASE=A) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('C-1', 'Commercial Professional', 632, 'commercial',
     'Real zone code (BASE=C-1) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('C-4', 'General Commercial', 632, 'commercial',
     'Real zone code (BASE=C-4) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('C-5', 'Heavy Commercial', 632, 'commercial',
     'Real zone code (BASE=C-5) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('CON', 'Conservation', 632, 'open_space',
     'Real zone code (BASE=CON) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('E', 'Estates', 632, 'agricultural',
     'Real zone code (BASE=E) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('I', 'Industrial', 632, 'industrial',
     'Real zone code (BASE=I) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('MH', 'Mobile Home', 632, 'residential',
     'Real zone code (BASE=MH) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('PUD', 'Planned Unit Development', 632, 'mixed_use',
     'Real zone code (BASE=PUD) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RMF-12', 'Residential Multi-Family 12', 632, 'residential',
     'Real zone code (BASE=RMF-12) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RMF-6', 'Residential Multi-Family 6', 632, 'residential',
     'Real zone code (BASE=RMF-6) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RSF-3', 'Residential Single Family 3', 632, 'residential',
     'Real zone code (BASE=RSF-3) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RSF-4', 'Residential Single Family 4', 632, 'residential',
     'Real zone code (BASE=RSF-4) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RSF-5', 'Residential Single Family 5', 632, 'residential',
     'Real zone code (BASE=RSF-5) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('RT', 'Residential Tourist', 632, 'residential',
     'Real zone code (BASE=RT) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.'),
    ('VR', 'Village Residential', 632, 'residential',
     'Real zone code (BASE=VR) from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1, point-in-polygon queried live by parcel centroid 2026-07-11.')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── Step 2: parcel_zones ── link 190 real collier folios to their real zone ──
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
    ('24207200100', '24207200100', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.704639,26.156605:2026-07-11'),
    ('50890640002', '50890640002', 632, 'VR', 'Village Residential', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.772787,26.097704:2026-07-11'),
    ('60700000803', '60700000803', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.706524,26.075360:2026-07-11'),
    ('81626920004', '81626920004', 632, 'MH', 'Mobile Home', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.661053,26.044804:2026-07-11'),
    ('41616280008', '41616280008', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.529153,26.160865:2026-07-11'),
    ('41615280009', '41615280009', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.529702,26.160859:2026-07-11'),
    ('40476000005', '40476000005', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.519752,26.260757:2026-07-11'),
    ('35762880009', '35762880009', 632, 'RSF-3', 'Residential Single Family 3', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.697219,26.196852:2026-07-11'),
    ('28431080008', '28431080008', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.726378,26.142982:2026-07-11'),
    ('38783560004', '38783560004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.542895,26.349678:2026-07-11'),
    ('00135840009', '00135840009', 632, 'RSF-4', 'Residential Single Family 4', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.425194,26.398301:2026-07-11'),
    ('00444240002', '00444240002', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.730005,26.076185:2026-07-11'),
    ('63850680002', '63850680002', 632, 'C-1', 'Commercial Professional', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.431941,26.440747:2026-07-11'),
    ('41042560004', '41042560004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.534786,26.200758:2026-07-11'),
    ('40579440009', '40579440009', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.545850,26.256357:2026-07-11'),
    ('39272160008', '39272160008', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.575051,26.243105:2026-07-11'),
    ('38501200009', '38501200009', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.606285,26.296551:2026-07-11'),
    ('37227000102', '37227000102', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.595026,26.221041:2026-07-11'),
    ('00120160008', '00120160008', 632, 'MH', 'Mobile Home', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.411610,26.414641:2026-07-11'),
    ('60576007205', '60576007205', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.784305,26.239081:2026-07-11'),
    ('40073080004', '40073080004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.516560,26.291239:2026-07-11'),
    ('00445520006', '00445520006', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.729646,26.076382:2026-07-11'),
    ('41508160003', '41508160003', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511421,26.169674:2026-07-11'),
    ('41614200006', '41614200006', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.532242,26.162175:2026-07-11'),
    ('65070760001', '65070760001', 632, 'VR', 'Village Residential', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.423780,26.410374:2026-07-11'),
    ('65070800000', '65070800000', 632, 'VR', 'Village Residential', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.423972,26.410371:2026-07-11'),
    ('66930120007', '66930120007', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.420896,26.410101:2026-07-11'),
    ('66880320009', '66880320009', 632, 'VR', 'Village Residential', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.422051,26.413416:2026-07-11'),
    ('39592560003', '39592560003', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.591514,26.310781:2026-07-11'),
    ('40302040003', '40302040003', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.548833,26.274799:2026-07-11'),
    ('00861480005', '00861480005', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.370167,26.050345:2026-07-11'),
    ('37541200002', '37541200002', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.621578,26.250964:2026-07-11'),
    ('00515640007', '00515640007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.405189,26.076985:2026-07-11'),
    ('00821360000', '00821360000', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.416397,26.062765:2026-07-11'),
    ('00808040000', '00808040000', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.363831,26.054845:2026-07-11'),
    ('00810240005', '00810240005', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.379911,26.057421:2026-07-11'),
    ('00861760000', '00861760000', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.369974,26.048346:2026-07-11'),
    ('00905800004', '00905800004', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.388391,26.020255:2026-07-11'),
    ('00911760002', '00911760002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.375081,26.011311:2026-07-11'),
    ('00921240004', '00921240004', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.361669,26.001800:2026-07-11'),
    ('00959120002', '00959120002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.438928,25.979879:2026-07-11'),
    ('01073440007', '01073440007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.380811,25.974802:2026-07-11'),
    ('00928640005', '00928640005', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.394525,26.005750:2026-07-11'),
    ('01076560007', '01076560007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.377499,25.977711:2026-07-11'),
    ('00930720007', '00930720007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.396443,25.999433:2026-07-11'),
    ('00979040007', '00979040007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.366868,25.984817:2026-07-11'),
    ('01075520006', '01075520006', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.381850,25.972001:2026-07-11'),
    ('01082560004', '01082560004', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.393499,25.965099:2026-07-11'),
    ('01126240002', '01126240002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.378211,25.963222:2026-07-11'),
    ('01130440005', '01130440005', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.362821,25.963290:2026-07-11'),
    ('01195080002', '01195080002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.670069,25.865118:2026-07-11'),
    ('38909720000', '38909720000', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.516882,26.351966:2026-07-11'),
    ('71842500881', '71842500881', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.725712,26.102760:2026-07-11'),
    ('00450200007', '00450200007', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.633460,26.144739:2026-07-11'),
    ('24370120007', '24370120007', 632, 'C-4', 'General Commercial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.417624,26.414323:2026-07-11'),
    ('24370160009', '24370160009', 632, 'C-4', 'General Commercial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.417697,26.414234:2026-07-11'),
    ('38848040003', '38848040003', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.551006,26.344555:2026-07-11'),
    ('38843120106', '38843120106', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.558095,26.349510:2026-07-11'),
    ('41507720004', '41507720004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511197,26.162571:2026-07-11'),
    ('37921960001', '37921960001', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.703124,26.202207:2026-07-11'),
    ('00116040006', '00116040006', 632, 'C-5', 'Heavy Commercial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.411523,26.419101:2026-07-11'),
    ('26033040008', '26033040008', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.810014,26.221484:2026-07-11'),
    ('22623600001', '22623600001', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.764248,26.110450:2026-07-11'),
    ('00348320002', '00348320002', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.598866,26.155771:2026-07-11'),
    ('35776760005', '35776760005', 632, 'RMF-12', 'Residential Multi-Family 12', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.689815,26.197768:2026-07-11'),
    ('67956500066', '67956500066', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.764106,26.240927:2026-07-11'),
    ('62428240105', '62428240105', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.807602,26.271787:2026-07-11'),
    ('48530080002', '48530080002', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.427454,26.428816:2026-07-11'),
    ('41229400000', '41229400000', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.523790,26.191488:2026-07-11'),
    ('37340560008', '37340560008', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.669543,26.206493:2026-07-11'),
    ('40688760007', '40688760007', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.531919,26.242195:2026-07-11'),
    ('35930720001', '35930720001', 632, 'C-4', 'General Commercial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.688139,26.186792:2026-07-11'),
    ('65171080004', '65171080004', 632, 'RSF-4', 'Residential Single Family 4', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.423764,26.398893:2026-07-11'),
    ('37491520007', '37491520007', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.604350,26.258276:2026-07-11'),
    ('69280500387', '69280500387', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.740545,26.207696:2026-07-11'),
    ('39590440002', '39590440002', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.593228,26.313123:2026-07-11'),
    ('39775360004', '39775360004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.539785,26.314952:2026-07-11'),
    ('40350800004', '40350800004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.544181,26.268986:2026-07-11'),
    ('66220880002', '66220880002', 632, 'MH', 'Mobile Home', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.410923,26.411582:2026-07-11'),
    ('00845560006', '00845560006', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.416295,26.045107:2026-07-11'),
    ('64702100244', '64702100244', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.506770,25.962767:2026-07-11'),
    ('63920002646', '63920002646', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.729412,26.164408:2026-07-11'),
    ('38724200006', '38724200006', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.524762,26.342455:2026-07-11'),
    ('41441400008', '41441400008', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.520546,26.171733:2026-07-11'),
    ('62361600006', '62361600006', 632, 'MH', 'Mobile Home', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.738811,26.148473:2026-07-11'),
    ('00752680008', '00752680008', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.606485,26.032750:2026-07-11'),
    ('56339002846', '56339002846', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.722802,26.130647:2026-07-11'),
    ('41509520008', '41509520008', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.509216,26.164822:2026-07-11'),
    ('00229480003', '00229480003', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.432654,26.251976:2026-07-11'),
    ('00230640007', '00230640007', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.438531,26.253562:2026-07-11'),
    ('00520040003', '00520040003', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.390635,26.076459:2026-07-11'),
    ('00867040009', '00867040009', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.369114,26.025789:2026-07-11'),
    ('00871640000', '00871640000', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.382972,26.036629:2026-07-11'),
    ('00904560002', '00904560002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.389213,26.011206:2026-07-11'),
    ('01073840005', '01073840005', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.380522,25.968021:2026-07-11'),
    ('67985000812', '67985000812', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.820393,26.307464:2026-07-11'),
    ('75115301166', '75115301166', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.689215,26.254428:2026-07-11'),
    ('01115080008', '01115080008', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.406378,25.954626:2026-07-11'),
    ('00510040000', '00510040000', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.414994,26.081280:2026-07-11'),
    ('00872040007', '00872040007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.391974,26.031806:2026-07-11'),
    ('00878920008', '00878920008', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.421408,26.034165:2026-07-11'),
    ('00917600001', '00917600001', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.369291,26.004091:2026-07-11'),
    ('01093360002', '01093360002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.429181,25.969722:2026-07-11'),
    ('40688840105', '40688840105', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.532416,26.242189:2026-07-11'),
    ('00825440007', '00825440007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.425465,26.063110:2026-07-11'),
    ('39785800004', '39785800004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.531307,26.307784:2026-07-11'),
    ('39836240005', '39836240005', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.554165,26.315076:2026-07-11'),
    ('39954880004', '39954880004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.539968,26.291694:2026-07-11'),
    ('40073321006', '40073321006', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.517304,26.288820:2026-07-11'),
    ('40360560004', '40360560004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.534138,26.273619:2026-07-11'),
    ('40359200003', '40359200003', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.536727,26.262697:2026-07-11'),
    ('40361720005', '40361720005', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.533020,26.262738:2026-07-11'),
    ('63911040002', '63911040002', 632, 'RSF-3', 'Residential Single Family 3', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.430124,26.435255:2026-07-11'),
    ('39831400002', '39831400002', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.559509,26.307667:2026-07-11'),
    ('39833560005', '39833560005', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.556894,26.307581:2026-07-11'),
    ('00936320003', '00936320003', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.421643,25.994385:2026-07-11'),
    ('01115040006', '01115040006', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.405864,25.954628:2026-07-11'),
    ('38845880004', '38845880004', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.553769,26.348017:2026-07-11'),
    ('39952920005', '39952920005', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.541829,26.296775:2026-07-11'),
    ('00094640007', '00094640007', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.603089,26.368012:2026-07-11'),
    ('39717720000', '39717720000', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.518778,26.313779:2026-07-11'),
    ('56404880003', '56404880003', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.414669,26.411456:2026-07-11'),
    ('29817017908', '29817017908', 632, 'A', 'Agricultural', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.451323,26.304012:2026-07-11'),
    ('51215000802', '51215000802', 632, 'RSF-5', 'Residential Single Family 5', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.429007,26.424936:2026-07-11'),
    ('82710001582', '82710001582', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.729232,26.162463:2026-07-11'),
    ('68310000240', '68310000240', 632, 'RT', 'Residential Tourist', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511017,25.958053:2026-07-11'),
    ('27778000289', '27778000289', 632, 'RMF-12', 'Residential Multi-Family 12', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.716657,26.197726:2026-07-11'),
    ('37286040006', '37286040006', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.597943,26.237488:2026-07-11'),
    ('41821240008', '41821240008', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.717362,26.238982:2026-07-11'),
    ('54670000428', '54670000428', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.742286,26.151828:2026-07-11'),
    ('68270002139', '68270002139', 632, 'C-4', 'General Commercial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511021,25.957340:2026-07-11'),
    ('68270002317', '68270002317', 632, 'C-4', 'General Commercial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511021,25.957340:2026-07-11'),
    ('68270002333', '68270002333', 632, 'C-4', 'General Commercial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511021,25.957340:2026-07-11'),
    ('68310000428', '68310000428', 632, 'RT', 'Residential Tourist', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511017,25.958053:2026-07-11'),
    ('82537400007', '82537400007', 632, 'RSF-3', 'Residential Single Family 3', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.763173,26.278069:2026-07-11'),
    ('36963681006', '36963681006', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.648222,26.225873:2026-07-11'),
    ('72650012421', '72650012421', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.716338,26.259176:2026-07-11'),
    ('81681120001', '81681120001', 632, 'VR', 'Village Residential', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.418871,26.419132:2026-07-11'),
    ('24830480009', '24830480009', 632, 'RSF-4', 'Residential Single Family 4', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.775338,26.141681:2026-07-11'),
    ('52651560002', '52651560002', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.423848,26.420791:2026-07-11'),
    ('39261800007', '39261800007', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.586078,26.230840:2026-07-11'),
    ('71825002429', '71825002429', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.755881,26.270704:2026-07-11'),
    ('46686002664', '46686002664', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.697331,26.085512:2026-07-11'),
    ('68310001265', '68310001265', 632, 'RT', 'Residential Tourist', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511017,25.958053:2026-07-11'),
    ('74413400003', '74413400003', 632, 'RSF-4', 'Residential Single Family 4', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.764291,26.121919:2026-07-11'),
    ('68310001362', '68310001362', 632, 'RT', 'Residential Tourist', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511017,25.958053:2026-07-11'),
    ('68310001003', '68310001003', 632, 'RT', 'Residential Tourist', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511017,25.958053:2026-07-11'),
    ('33140001240', '33140001240', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.709086,26.167594:2026-07-11'),
    ('80445100158', '80445100158', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.784592,26.237266:2026-07-11'),
    ('34640280007', '34640280007', 632, 'RMF-12', 'Residential Multi-Family 12', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.699181,26.192447:2026-07-11'),
    ('33380360000', '33380360000', 632, 'RMF-12', 'Residential Multi-Family 12', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.732168,26.096033:2026-07-11'),
    ('61550000463', '61550000463', 632, 'I', 'Industrial', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.751196,26.160275:2026-07-11'),
    ('50880001266', '50880001266', 632, 'MH', 'Mobile Home', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.693472,26.054638:2026-07-11'),
    ('26145004181', '26145004181', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.660688,26.274049:2026-07-11'),
    ('40809280007', '40809280007', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.511193,26.215324:2026-07-11'),
    ('00865400007', '00865400007', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.369762,26.052167:2026-07-11'),
    ('00932800006', '00932800006', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.394835,26.001309:2026-07-11'),
    ('40301400000', '40301400000', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.548386,26.266173:2026-07-11'),
    ('62834200001', '62834200001', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.816606,26.262779:2026-07-11'),
    ('31155005929', '31155005929', 632, 'MH', 'Mobile Home', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.688947,26.049558:2026-07-11'),
    ('64539006964', '64539006964', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.773764,26.226616:2026-07-11'),
    ('27635200009', '27635200009', 632, 'RSF-3', 'Residential Single Family 3', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.822538,26.270310:2026-07-11'),
    ('00927000002', '00927000002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.390796,26.001196:2026-07-11'),
    ('01073400005', '01073400005', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.390363,25.964908:2026-07-11'),
    ('01086120000', '01086120000', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.416013,25.970746:2026-07-11'),
    ('40684200008', '40684200008', 632, 'E', 'Estates', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.538928,26.238768:2026-07-11'),
    ('81320760007', '81320760007', 632, 'RMF-6', 'Residential Multi-Family 6', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.441565,26.425276:2026-07-11'),
    ('22600002402', '22600002402', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.806997,26.248173:2026-07-11'),
    ('81621200004', '81621200004', 632, 'MH', 'Mobile Home', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.660437,26.044054:2026-07-11'),
    ('82280120003', '82280120003', 632, 'PUD', 'Planned Unit Development', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.785166,26.178755:2026-07-11'),
    ('00503200006', '00503200006', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.384253,26.093822:2026-07-11'),
    ('00509840004', '00509840004', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.423175,26.082835:2026-07-11'),
    ('00514040006', '00514040006', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.402313,26.076124:2026-07-11'),
    ('00515760000', '00515760000', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.395515,26.080808:2026-07-11'),
    ('00519360008', '00519360008', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.382118,26.067388:2026-07-11'),
    ('00805160006', '00805160006', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.363818,26.057381:2026-07-11'),
    ('00806920009', '00806920009', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.372820,26.064500:2026-07-11'),
    ('00820440002', '00820440002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.423315,26.058392:2026-07-11'),
    ('00946920008', '00946920008', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.451787,25.993822:2026-07-11'),
    ('00998760009', '00998760009', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.014413,26.048050:2026-07-11'),
    ('00822520001', '00822520001', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.416388,26.056855:2026-07-11'),
    ('00846520003', '00846520003', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.411285,26.038829:2026-07-11'),
    ('00859040004', '00859040004', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.385064,26.040953:2026-07-11'),
    ('00875320009', '00875320009', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.381071,26.033028:2026-07-11'),
    ('00893280008', '00893280008', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.449880,26.011233:2026-07-11'),
    ('00922720002', '00922720002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.388302,26.003106:2026-07-11'),
    ('00930320009', '00930320009', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.405700,26.000036:2026-07-11'),
    ('00948720002', '00948720002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.443791,26.004176:2026-07-11'),
    ('00965800002', '00965800002', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.415351,25.985627:2026-07-11'),
    ('01072440008', '01072440008', 632, 'CON', 'Conservation', 'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.373329,25.968779:2026-07-11')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET
    zone_code = EXCLUDED.zone_code,
    zone_name = EXCLUDED.zone_name,
    source    = EXCLUDED.source;

-- ── Verification ─────────────────────────────────────────────────────────────

SELECT 'parcel_zones collier real' AS check_name, count(*) AS n
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE lower(COALESCE(j.county_name, j.county)) = 'collier'
  AND pz.source LIKE 'collier_gis_live%';

SELECT 'card_view collier real' AS check_name, count(*) AS n
FROM v_zoning_gold_standard_card
WHERE lower(county) = 'collier'
  AND parcel_id NOT LIKE 'COLLIER-%';
