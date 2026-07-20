-- Gold Standard shard-11 (union, gulf) — re-fire of dispatch 1a211136-77c7-4125-b70c-06b26ad13ebe
-- This exact dispatch already ran and shipped fixes (commit 7ffd8c88, 2026-07-19 21:30Z). This
-- re-fire found zero drift on live pencil_dod_evaluate_county for both counties, so no county-status
-- writes are made here. The only new artifact is a corrected, adversarially-verified jurisdiction
-- finding for gulf parcel 06248-410R, which the prior session attempted and REFUTED (audit row 7445)
-- on weak sourcing (a mismatched real-estate listing). This session re-derived the same conclusion
-- from Gulf County's own live GIS spatial-intersection data (City Limits of Port St Joe layer vs the
-- parcel polygon), independently reproduced by 2 separate refuters -- a materially different, stronger
-- evidence chain, not a retry of the same refuted source. Does NOT flip letter I: unincorporated Gulf
-- County has no jurisdiction/zoning_districts row in our system yet (Municode 403'd again this
-- session, consistent with every prior session's SSOT note on that blocker), so no zone_code exists
-- to assign. This is scoping/substrate progress for a future ordinance-research session, not a card
-- completion.

insert into public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
values
  (
    '1a211136-77c7-4125-b70c-06b26ad13ebe',
    'native',
    'gulf',
    'I',
    'CORRECTED (supersedes refuted audit row 7445): parcel 06248-410R (112 Shallow Reed Dr) is confirmed unincorporated Gulf County, NOT City of Port St Joe. Verified via live esriSpatialRelIntersects query of the parcel polygon against Gulf County GIS''s own "City Limits of Port St Joe" layer (arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer/7), which returned zero intersecting features; methodology validated against a known in-city control parcel (200 Reid Ave, PIN 04660-000R) which correctly returned a match. Does not by itself complete the I card: unincorporated Gulf County has no jurisdiction/zoning_districts entry in this system, so no zone_code can be assigned yet (Municode library.municode.com/fl/gulf_county returned 403 again this session -- same blocker documented across all prior sessions'' SSOT notes). Next-session action: find an accessible source for Gulf County''s unincorporated zoning/land development code (Municode alternative or a direct county PDF, per the Port St Joe LDR-PDF precedent from the prior session) before this can flip.',
    jsonb_build_object(
      'refuter_1', 'Independently queried arcgis5.roktech.net/arcgis/rest/services/gulf/GoMaps4/MapServer/7 (City Limits of Port St Joe) and /12 (Parcels); reproduced exact parcel attributes (HOUSE_NO=112, STREET=SHALLOW REED DR, LEGL1/LEGL2 match), geometry Y-range match, zero-intersection result, and control-parcel validation (200 Reid Ave correctly returns Port St Joe). survived=true.',
      'refuter_2', 'Second independent re-fetch of the same live ArcGIS services, reproduced identical layer names, parcel attributes, geometry, zero-intersection result, city-limits layer acreage (7660.729 ac), and control-parcel validation. survived=true.',
      'session', 'gtm22j-shard11-refire-2nd (dispatch 1a211136 re-fired 2026-07-20; workflow wf_d6d27498-922)'
    ),
    true
  );
