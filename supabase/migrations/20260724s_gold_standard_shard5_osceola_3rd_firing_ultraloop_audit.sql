-- Gold Standard Shard-5 osceola, dispatch ac5f5206, 3rd firing.
-- ULTRALOOP audit trail: one row per claim this firing's workflow (wf_cb376b9e-744)
-- produced, tagged with the independent refuter's survived/refuted verdict.

BEGIN;

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case 19892023 / parcel 112529181100010210 -> zone_code=RA-3 (Kissimmee cw.kissimmee.gov Zoning_Districts/10, single unambiguous spatial match). Applied.',
   '{"refuted": false, "method": "fresh re-fetch of cited URL + independent county-layer re-derivation via correct hosting/rest path + 9-point grid boundary sweep + DocumentLink cross-check"}'::jsonb, true),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case 19952023 / parcel 112529235700010830 -> zone_code=RA-3 (Kissimmee, same source). Applied.',
   '{"refuted": false, "method": "fresh re-fetch + manual point-in-polygon geometry check + independent FL GIO cadastral cross-check + independent Osceola-County-Zoning FeatureServer cross-check"}'::jsonb, true),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case 31152023 / parcel 182529227600011636 -> zone_code=SRPUD (Kissimmee). REFUTED on campaign-provenance grounds (finding absent from an older, unrelated session''s committed artifacts); the raw GIS data itself was independently confirmed clean by the same refuter (Part A). Per ULTRALOOP protocol, refuted claims are not counted even when this session''s author disagrees with the refuter''s reasoning -- NOT applied. Flagged for next-session re-verification with a refuter prompt that does not conflate "new work" with "must pre-exist in an older document".',
   '{"refuted": true, "concern": "provenance/category-error -- raw ArcGIS data independently reproduced and confirmed accurate (Part A); refutation rests on absence from a prior, unrelated session''s addendum, not on any data contradiction"}'::jsonb, false),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case 36212023 / parcel 212529181600 -> zone_code=T5-M (Kissimmee, spatial point-in-polygon; county-layer PARCELNO ambiguous but zoning determination is location-based, independent of which stacked parcel record applies). Applied.',
   '{"refuted": false, "method": "fresh re-fetch + independent manual ray-casting point-in-polygon + PUD-layer override check (zero features) + independent OSM/Nominatim jurisdiction cross-check"}'::jsonb, true),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case 8642023 / parcel 052529152400 -> zone_code=MUPUD (Kissimmee). REFUTED: "052529152400" is a synthetic shared 12-digit prefix across 24 condo units + 1 COMM parcel, not a real standalone parcel; case-to-specific-unit linkage unverified from any public source. NOT applied.',
   '{"refuted": true, "concern": "truncated-prefix parcel identity + unverified case-to-unit linkage, real substantive ambiguity"}'::jsonb, false),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case 52962018 / parcel 262630061300011010 -> zone_code=R-3 (Saint Cloud, arcgisweb.stcloud.org, PIN-keyed exact match, address 3433 Allegra Cir). Applied. The other 3 cases sharing truncated parcel_id 262630061300 (48482022, 52562018 -- no address at all; 53252018 -- address 3630 Allegra Cir does not match this or the already-fixed sibling parcel 262630061300011440''s address) left untouched, not fabricated.',
   '{"refuted": false, "method": "fresh re-fetch of St Cloud FeatureServer + independent correct-path Osceola county-layer re-derivation + 262-parcel shared-prefix subdivision disambiguation check + sibling-parcel distinctness confirmation"}'::jsonb, true),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case "2011 CA 003872 MF" / parcel 072530272401950380 -> geo (28.3400831,-81.3659249) + zone_code=PD (Osceola unincorp.) + assessed_value=401100 + market_value=412100, via FL GIO exact PARCEL_ID + Osceola Parcels/Zoning_Parcels FeatureServer address match. Applied.',
   '{"refuted": false, "method": "fresh re-fetch of 3 cited ArcGIS endpoints, independent centroid recomputation from raw ring geometry, full-polygon (not just centroid) City_Limits non-incorporation check, control-point sanity test"}'::jsonb, true),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'I',
   'case "2019 CA 000153 MF" / parcel 3026315130000D0070 -> geo (28.1889407,-81.2438048) + zone_code=E-1 (Osceola unincorp.) + assessed_value=128517 (homestead-capped) + market_value=425400 (JV), via FL GIO exact PARCEL_ID + Osceola Parcels/Zoning_Parcels FeatureServer address match. Applied.',
   '{"refuted": false, "method": "fresh re-fetch of all cited endpoints, independent centroid recomputation, dual query-path zoning confirmation, HX exemption cross-check corroborating assessed/market-value gap, live Supabase case-linkage confirmation"}'::jsonb, true),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'G',
   'Kissimmee T3: is_codified=false (form-based SmartCode, Table 5-2 has no FAR/density column). REFUTED: refuter independently corroborated the primary, mechanically-checkable claim (Table 5-2 lacks FAR/density rows for any transect zone) but could not locate one supporting quoted sentence about future-land-use-driven density caps in 4 fetch attempts. NOT applied -- 4th correct decline for G this campaign.',
   '{"refuted": true, "concern": "secondary supporting citation not independently locatable, though primary structural claim was corroborated"}'::jsonb, false),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'G',
   'Kissimmee SRPUD: is_codified=false (PUD-type, density/FAR set per development order via Sec 14-4-8.C referencing RPUD standards at 14-4-8.B.4). Survived refutation but reported at HYPOTHESIS confidence only (no browser/Playwright rendering tool available in this sandbox to read primary Municode text directly -- both researcher and refuter relied on third-party mirrors/search snippets). NOT applied to zoning_districts -- campaign precedent requires CONFIRMED-level, directly-read ordinance text before a production applicability-flag write.',
   '{"refuted": false, "note": "HYPOTHESIS confidence, held back from production pending primary-source read with a browser-capable tool next session"}'::jsonb, true),

  ('ac5f5206-a862-494e-a345-f6b0eb4cbd09', 'native', 'osceola', 'G',
   'St Cloud R-3: max_density_du_acre=10 (UDC Sec 3.5.3.C/F.1). REFUTED: refuter could not independently render the JS-only Municode page (no Playwright available) and found an unresolved Oct-2025 St Cloud comprehensive-plan/zoning-update cycle that may or may not have amended this section after the claim''s cited Nov-2023 ordinance. NOT applied.',
   '{"refuted": true, "concern": "could not independently re-render primary source; unresolved 2025 amendment-cycle freshness risk"}'::jsonb, false);

COMMIT;
