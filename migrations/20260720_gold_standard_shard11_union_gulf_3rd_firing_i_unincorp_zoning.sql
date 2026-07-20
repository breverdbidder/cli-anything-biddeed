-- Gold Standard shard-11 (union, gulf) — 3rd firing of dispatch 1a211136-77c7-4125-b70c-06b26ad13ebe
--
-- Union: re-verified live, zero drift (8/10, B/F genuinely time-gated on a real auction closing
-- 2026-08-13). No writes for union.
--
-- Gulf letter I: the prior (2nd) firing found Gulf County's own Land Development Regulations (LDR)
-- PDF is directly accessible from the county's own CDN (bypassing the perpetual Municode 403), and
-- that unincorporated Gulf County regulates by 8 Future Land Use districts, not conventional
-- lettered zone codes -- CONFIRMED by an independent adversarial refuter (byte-identical PDF re-fetch,
-- independent OCR reproducing the same Article 3.01.03 district list). That closed the "no accessible
-- source" blocker but, by itself, could not flip any parcel because no jurisdiction/zoning_districts
-- row existed yet for unincorporated Gulf County.
--
-- This session closes the loop for ONE parcel: 06248-410R (112 Shallow Reed Dr), already confirmed
-- unincorporated in the 2nd firing (audit row 7535). A direct esriSpatialRelIntersects query of the
-- parcel's own polygon geometry (fetched from Gulf GIS layer 12/Parcels by PIN) against Gulf GIS
-- layer 40/Land Use returns Type='Mixed_Comm/Res' (1420.02 ac polygon), matching the LDR's "MIXED
-- COMMERCIAL/RESIDENTIAL (R/MCR)" district. Methodology validated against 3 known in-city control
-- parcels (06051-008R, 05004050R, 05762000R), which all correctly return Type='Municipal' (the
-- layer's placeholder for areas where the city's own zoning applies instead of county FLU) -- proving
-- the layer's semantics are real, not a spurious constant. Independently reproduced by an adversarial
-- refuter agent (bit-for-bit: same geometry, same Type, same control result, same city-limits-exclusion
-- result). survived=true.
--
-- 05004050R and 05762000R are NOT touched here: this same spatial check confirms both are INSIDE Port
-- St Joe city limits (Type='Municipal'), so they remain gated on the same unresolved City of Port St
-- Joe zoning-map ambiguity documented in the 2nd firing (identical residential-subdistrict fill colors,
-- no georeferencing in the vector zoning-map PDF) -- out of scope for this migration.
--
-- No zone_standards rows are written: the LDR's density figures for Mixed_Comm/Res are multi-tier
-- (1-4 DU/acre depending on Gulf-side vs bayside/lagoon-side overlay, itself parcel-specific and not
-- yet determined for 06248-410R) -- writing a single max_density_du_acre value would be a guess.
-- pencil_dod_evaluate_county's I criterion only requires parcel_zones.zone_code IS NOT NULL, which
-- this migration satisfies honestly without fabricating a standards number. G is unaffected (gulf G
-- already passes at 100%).

insert into public.jurisdictions (name, county, county_name, state, co_no)
values ('Gulf County Unincorporated', 'Gulf', 'Gulf', 'FL', 23)
returning id;

-- capture the new jurisdiction id via a DO block so the rest of this migration is self-contained
do $$
declare
  v_jid bigint;
begin
  select id into v_jid from public.jurisdictions
    where name = 'Gulf County Unincorporated' and county = 'Gulf' and state = 'FL';

  insert into public.zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section)
  values
    (v_jid, 'Residential', 'Residential', 'residential',
     'Unincorporated Gulf County Future Land Use district. Per Gulf County LDR Article III Sec. 3.01.03.',
     'Gulf County LDR Art. III Sec. 3.01.03'),
    (v_jid, 'Commercial', 'Commercial', 'commercial',
     'Unincorporated Gulf County Future Land Use district. Per Gulf County LDR Article III Sec. 3.01.03.',
     'Gulf County LDR Art. III Sec. 3.01.03'),
    (v_jid, 'Mixed_Comm/Res', 'Mixed Commercial/Residential (Low Density)', 'mixed_use',
     'Unincorporated Gulf County Future Land Use district (R/MCR). Density 1-4 DU/acre: max 3 DU/acre on the Gulf-side of Highway 30 corridor roads, max 2 DU/acre bayside/lagoon side, per Gulf County LDR Art. III Sec. 3.01.03 density table (PDF p.67). Coastal overlay caps: 2 DU/acre St. Joseph Bay/Indian Pass Lagoon, 3 DU/acre Gulf-side.',
     'Gulf County LDR Art. III Sec. 3.01.03'),
    (v_jid, 'Agriculture', 'Agricultural', 'agricultural',
     'Unincorporated Gulf County Future Land Use district. Density: Low 1 DU/40-acre, Medium 1 DU/15-acre, High 1 DU/2.5-acre, per Gulf County LDR Art. III Sec. 3.01.03 density table (PDF p.67).',
     'Gulf County LDR Art. III Sec. 3.01.03'),
    (v_jid, 'Public', 'Public', 'public',
     'Unincorporated Gulf County Future Land Use district. Per Gulf County LDR Article III Sec. 3.01.03.',
     'Gulf County LDR Art. III Sec. 3.01.03'),
    (v_jid, 'Recreation', 'Recreation', 'recreation',
     'Unincorporated Gulf County Future Land Use district. Per Gulf County LDR Article III Sec. 3.01.03.',
     'Gulf County LDR Art. III Sec. 3.01.03'),
    (v_jid, 'Conservation', 'Conservation', 'conservation',
     'Unincorporated Gulf County Future Land Use district. Per Gulf County LDR Article III Sec. 3.01.03.',
     'Gulf County LDR Art. III Sec. 3.01.03'),
    (v_jid, 'Industrial', 'Industrial', 'industrial',
     'Unincorporated Gulf County Future Land Use district. Per Gulf County LDR Article III Sec. 3.01.03.',
     'Gulf County LDR Art. III Sec. 3.01.03');

  insert into public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, future_land_use, source)
  values (
    '06248-410R',
    v_jid,
    'Mixed_Comm/Res',
    'Mixed Commercial/Residential (Low Density)',
    'Mixed_Comm/Res',
    'gulf_gis_flu_spatial_intersect:arcgis5.roktech.net/gulf/GoMaps4/MapServer/40 (Type=Mixed_Comm/Res, Acreage=1420.02) x Gulf_County_LDR_Complete_09-2019.pdf Art.III Sec.3.01.03 -- dispatch 1a211136 3rd firing'
  );
end $$;

insert into public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
values
  (
    '1a211136-77c7-4125-b70c-06b26ad13ebe',
    'native',
    'gulf',
    'I',
    'Gulf County''s unincorporated Land Development Regulations (LDR) document is directly accessible (HTTP 200, 53,579,518 bytes) from the county''s own CDN (cdnsm5-hosted.civiclive.com), bypassing the perpetual Municode 403. Unincorporated Gulf County regulates by 8 Future Land Use districts (RESIDENTIAL, COMMERCIAL, MIXED COMMERCIAL/RESIDENTIAL, AGRICULTURAL, PUBLIC, RECREATION, CONSERVATION, INDUSTRIAL) per LDR Article III Sec. 3.01.03 -- not conventional lettered zone codes.',
    jsonb_build_object(
      'refuter', 'Independent re-fetch of the LDR PDF (byte-identical: 53,579,518 bytes, HTTP 200), independent OCR (pdftoppm+tesseract) reproducing the cover page, table of contents ("ARTICLE 3 LAND USE PAGES 53-68"), and Article III Sec. 3.01.03 district list verbatim (same 8 districts, zero lettered codes found in a full-text grep). Reproduced the Municode 403 (via WebFetch) and the web.archive.org unreachability. survived=true.',
      'session', 'gtm22j-shard11-refire-3rd (dispatch 1a211136 3rd firing; workflow wf_f26f1183-011)'
    ),
    true
  ),
  (
    '1a211136-77c7-4125-b70c-06b26ad13ebe',
    'native',
    'gulf',
    'I',
    'Parcel 06248-410R (112 Shallow Reed Dr) has Future Land Use = Mixed_Comm/Res per a real esriSpatialRelIntersects query of its own polygon geometry (fetched from Gulf GIS layer 12/Parcels by PIN) against Gulf GIS layer 40/Land Use (Type=Mixed_Comm/Res, Acreage=1420.02). Methodology validated against 3 known in-city control parcels (06051-008R, 05004050R, 05762000R) which all correctly return Type=Municipal, confirming the layer''s semantics are real and not a spurious constant. This parcel is written to parcel_zones with jurisdiction_id pointing at the new "Gulf County Unincorporated" jurisdiction and zone_code=''Mixed_Comm/Res'', flipping this parcel''s I card from incomplete to complete (gulf I: 6/14 -> 7/14, still fails the 95% threshold but is real, verified progress). 05004050R and 05762000R are confirmed by this same check to be INSIDE Port St Joe city limits (Type=Municipal), so they remain gated on the separate unresolved City zoning-map ambiguity and are NOT written here.',
    jsonb_build_object(
      'refuter', 'Independently re-fetched parcel 06248-410R geometry from live ArcGIS layer 12 and re-ran the spatial intersect against layer 40 from scratch: reproduced Type=Mixed_Comm/Res, Acreage=1420.02 exactly. Reproduced the control-parcel check (06051-008R -> Municipal) and the city-limits-exclusion check (06248-410R has zero intersecting features against layer 7/City Limits of Port St Joe, while the control parcel correctly intersects). All reproducible facts checked out. survived=true.',
      'session', 'gtm22j-shard11-refire-3rd (dispatch 1a211136 3rd firing; workflow wf_f26f1183-011 + follow-up refuter agent a98b642642c28ade2)'
    ),
    true
  );
