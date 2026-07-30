-- Gold Standard shard-6 broward, dispatch 3bb96d0d-0de5-4f6f-b933-2a95d7168f3d
-- Letter G fix: 34 of 702 broward auction parcels carry parcel_zones.zone_code='RS-1'
-- (Broward County Unincorporated, jurisdiction_id=628) with no matching zoning_districts
-- row, so v_zoning_gold_standard_kpi_v3 counted them as "applicable, no standard" for
-- density/FAR/parking, holding far/pk1000 at 0.0% (their only applicable parcels) and
-- density at 93.9%.
--
-- RS-1 = "One Family Detached, 1 unit per acre" per Broward's Ch.39 RS-N naming
-- convention, where N is the max density in du/acre — already confirmed live for the
-- two sibling rows below (RS-4=4, RS-6=6, both source_url=bcgishub.broward.org
-- ZoningOfficial/2, confidence_score=0.95). RS-1 corroborated independently via web
-- search (steadily.com Fort Lauderdale zoning guide: "RS-1 is for single-family homes
-- at one unit per acre" in unincorporated Broward). The live ZoningOfficial FeatureServer
-- returned 403/500 at insert time (could not re-pull directly), so confidence_score is
-- set lower than the sibling rows to mark this as convention-plus-secondary-source
-- rather than a fresh direct GIS pull. HONESTY: INFERRED, not VERIFIED against primary
-- ordinance text (Municode blocked the fetch; Firecrawl credits exhausted at time of
-- session). FAR and parking-per-1000sf are intentionally left NULL/not-applicable here,
-- matching the existing RS-4/RS-6/RM-10 rows -- single-family/multi-family residential
-- districts in this jurisdiction are not FAR- or parking-per-1000sf-regulated.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (628, 'RS-1', 'One Family Detached, 1 unit per acre', 'residential', NULL, true, false, 'Broward County Code of Ordinances Ch. 39')
ON CONFLICT DO NOTHING
RETURNING id;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 1.00,
       'https://bcgishub.broward.org/server/rest/services/PSD/ZoningOfficial/FeatureServer/2 (pattern match vs sibling RS-4/RS-6 rows) + https://www.steadily.com/blog/residential-zoning-laws-regulations-fort-lauderdale',
       'Broward County Code of Ordinances Ch. 39',
       0.75,
       now()
FROM zoning_districts
WHERE jurisdiction_id = 628 AND code = 'RS-1';
