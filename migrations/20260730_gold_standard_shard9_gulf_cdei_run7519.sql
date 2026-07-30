-- GOLD STANDARD shard-9 gulf-only (dispatch 0ba2502a-8ac3-408e-9fb0-255fae137aaf, loop run 7519)
-- Letters C/D/E/I. gulf has only 14 total auctions, and the campaign's 95% threshold means
-- C/D/E/I each effectively require ALL 14 rows matched/linked/complete (13/14=92.9% still fails).
--
-- E (parcel_linked=11 of 14): 3 foreclosure cases had parcel_id=NULL. Resolved via authenticated
-- gulf.realforeclose.com case-detail pages (REALFORECLOSE_EMAIL/PASSWORD login, same mechanism
-- already proven for B/F in this county) which reveal Case Details -> Party Details (defendant name)
-- and, where present, Legal Description -- neither field is visible on the anonymous splash page,
-- which is why 4+ prior sessions treated this as blocked. Cross-referenced against Gulf County
-- Property Appraiser GIS (arcgis5.roktech.net/.../gulf/GoMaps4/MapServer/12, "Parcels" layer) by
-- legal description and/or unique owner-name match:
--   232024CA000072CAAXMX -> 06248405R  (Legal Desc "LOT 41 SHALLOW REED PHASE ONE" + defendant
--                                        "R AND R DEVELOPMENT AND HOLDING GROUP LLC" both match
--                                        PIN 06248405R exactly and uniquely)
--   232019CA000060CAAXMX -> 03501201R  (defendant "DEBRA K STEVENS" matches the only
--                                        "...STEVENS ROBERT J & DEBRA K..." parcel countywide)
--   232024CC000157CCAXMX -> 04276175R  (defendant "KARR Properties LLC" matches the only KARR
--                                        PROPERTIES LLC parcel countywide, corroborated by its
--                                        subdivision "WINDMARK SUB" matching the plaintiff,
--                                        Windmark Beach Community Association Inc)
-- Adversarially verified independently before this migration was written (see session report).
--
-- C/D (matched_clean=13 of 14): the only unmatched row was 232024CC000157CCAXMX (upcoming
-- auction_date 2026-09-10, never run through parcel matching because it's newly scraped). Now that
-- its parcel_id is resolved above, mark it matched_clean via the same tier1 convention this county's
-- other 13 rows already use.
--
-- I (card_complete=9 of 14): the 3 rows above already have property_address/lat/long/assessed_value
-- populated; they only failed I because parcel_id was null (couldn't join to the zoning card). Two of
-- the three parcels (06248405R, 04276175R) fall inside the SAME already-verified unincorporated Gulf
-- County "Mixed_Comm/Res" FLU polygon used for parcel 06248-410R in a prior session (confirmed via the
-- same ArcGIS layer-40 Future-Land-Use spatial intersect: Type=Mixed_Comm/Res) -- reusing the existing
-- zoning_districts row (id=12294) which already has a zone_standards row, so this is zero regression
-- risk to letter G. The third parcel (03501201R) falls in the unincorporated "Residential" FLU polygon
-- (zoning_districts id=12292, code='Residential') which has NO zone_standards row yet -- adding a
-- parcel_zones row against it without first adding zone_standards would reproduce the exact P0 G
-- regression from migration 20260720_gold_standard_shard11_gulf_g_regression_fix.sql (new district,
-- density_applicable=true by default, no zone_standards -> "applicable but missing"). Fixed by adding
-- zone_standards for district 12292 FIRST, sourced from the same Gulf County LDR ordinance page
-- (independently OCR-verified this session): PDF p.66 table header "RESIDENTIAL AND MIXED
-- COMMERCIAL/RESIDENTIAL" governs a single COMBINED table row on PDF p.67, "R/MCR  1-4 DU/Acre" --
-- i.e. the Residential district shares the identical 1-4 DU/acre base figure already verified and
-- stored for Mixed_Comm/Res (district 12294). Even after this fix, I remains below the 95% threshold
-- (12 of 14) because 2 unrelated parcels (05762000R, 05004050R) remain a genuine, repeatedly-
-- documented dead end -- confirmed City of Port St Joe zoning, ambiguous vector zoning-map fill colors,
-- no georeferencing, requires a human phone call to City of Port St Joe Planning (850-229-8261) that
-- no automated session can make. Not re-guessed here.

-- E: parcel linkage
update public.multi_county_auctions
set parcel_id = '06248405R'
where lower(county) = 'gulf' and case_number = '232024CA000072CAAXMX';

update public.multi_county_auctions
set parcel_id = '03501201R'
where lower(county) = 'gulf' and case_number = '232019CA000060CAAXMX';

update public.multi_county_auctions
set parcel_id = '04276175R'
where lower(county) = 'gulf' and case_number = '232024CC000157CCAXMX';

-- C/D: parity match for the one previously-unmatched row, now that its parcel_id is known
update public.multi_county_auctions
set parity_status = 'matched_clean',
    parity_source = 'tier1_gulf_official_platform_parcel_shard9_run7519'
where lower(county) = 'gulf' and case_number = '232024CC000157CCAXMX';

-- I: zone_standards for the Residential district FIRST (avoids repeating the 2026-07-20 G regression)
insert into public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
values (
  12292,
  4,
  'https://cdnsm5-hosted.civiclive.com/UserFiles/Servers/Server_6500990/File/County%20Government/Planning%20Dept/LDR%20Complete%2009-2019.pdf',
  'Gulf County LDR Art. III Sec. 3.02.04 (density table, PDF p.67, combined "R/MCR" row per table header on PDF p.66)',
  0.75,
  now()
);

-- I: parcel_zones linkage for the 3 newly-parcel-linked rows
insert into public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
values (
  '06248405R', '06248405R', 1507, 'Mixed_Comm/Res', 'Mixed Commercial/Residential (Low Density)',
  'gulf_gis_flu_spatial_intersect:arcgis5.roktech.net/gulf/GoMaps4/MapServer/40 (Type=Mixed_Comm/Res) -- dispatch 0ba2502a shard9 run7519'
);

insert into public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
values (
  '04276175R', '04276175R', 1507, 'Mixed_Comm/Res', 'Mixed Commercial/Residential (Low Density)',
  'gulf_gis_flu_spatial_intersect:arcgis5.roktech.net/gulf/GoMaps4/MapServer/40 (Type=Mixed_Comm/Res) -- dispatch 0ba2502a shard9 run7519'
);

insert into public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
values (
  '03501201R', '03501201R', 1507, 'Residential', 'Residential',
  'gulf_gis_flu_spatial_intersect:arcgis5.roktech.net/gulf/GoMaps4/MapServer/40 (Type=Residential) -- dispatch 0ba2502a shard9 run7519'
);
