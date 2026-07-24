-- Gold Standard shard-2 (nassau, st_johns) — loop run 6080
-- dispatch_id: ffe1aa89-758e-42a2-8ac2-73ceeee9d290
--
-- st_johns I: two auctions were missing a zoning-card match because their
-- parcels were absent from parcel_zones entirely (spatial coverage gap, not
-- an evaluator bug -- G already passes for st_johns's existing coverage).
--
-- Both zone codes VERIFIED live via St. Johns County's official ArcGIS REST
-- GIS services (gis.sjcfl.us/portal_sjcgis/rest/services), point-in-polygon
-- against each parcel's own real geometry, independently re-queried and
-- confirmed by an adversarial refuter agent before this write:
--   - parcel 0733220860 (742 Pullman Cir, Saint Augustine) -> ZONING='PUD'
--     (Northridge Lakes PUD subdivision, per parcel legal description)
--   - parcel 0263350890 (201 Rambling Brook Trl, St Johns)  -> ZONING='PUD'
--     (Brookside Preserve PUD, per parcel legal description)
-- Jurisdiction: "Unincorporated St. Johns County" (id=1364) -- the county's
-- Zoning MapServer layer's own metadata states it covers unincorporated
-- land, and jurisdiction_id=1364/zoning_districts code='PUD' (id=12040)
-- already exists from prior st_johns zoning ingestion, so no new district
-- row is needed.

SET statement_timeout = 0;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, 1364, 'PUD', 'Planned Unit Development', 'gis.sjcfl.us_arcgis:shard2_run6080'
FROM (VALUES
  ('0733220860'),
  ('0263350890')
) AS v(parcel_id)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 1364
);

-- Verification
SELECT parcel_id, jurisdiction_id, zone_code, zone_name, source
FROM public.parcel_zones
WHERE parcel_id IN ('0733220860', '0263350890');
