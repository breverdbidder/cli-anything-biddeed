-- ULTRALOOP audit rows for dispatch 04888cc3 (miami_dade/indian_river/calhoun/martin/liberty), 2026-08-03
-- All claims below FAILED adversarial survival vote — logged as false-positive ledger, not certifications.

INSERT INTO public.gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived) VALUES
('04888cc3-410a-4878-969b-d994a0a31d2e', 'fallback', 'indian_river', 'I',
 'Root cause: indian_river has zero rows in v_zoning_gold_standard_card, so zone_code can never match.',
 jsonb_build_object('method', 'direct DB query by orchestrator', 'finding', 'FALSE — indian_river has 92 rows in v_zoning_gold_standard_card. Real root cause: sparse ingestion (92 parcels) that does not cover the 7 failing case parcel_ids.'),
 false),
('04888cc3-410a-4878-969b-d994a0a31d2e', 'fallback', 'martin', 'E',
 'Case 23001555CCAXMX parcel_id = 27-37-41-036-000-00400-3, sourced from court.martinclerk.com case detail page.',
 jsonb_build_object('method', 'independent refetch via WebFetch + curl', 'finding', 'Source URL returns Access Denied on independent re-fetch (session-bound digest token). Cannot be confirmed from the cited source.'),
 false),
('04888cc3-410a-4878-969b-d994a0a31d2e', 'fallback', 'calhoun', 'B',
 'Sale outcomes for cases 621 OF 2026, 171 OF 2023, 25-56CA not found on calhounclerk.com.',
 jsonb_build_object('method', 'independent refetch of both cited pages', 'finding', 'Confirmed: neither page lists any of the three case numbers. Genuinely unresolved/not posted, not a scraper miss (as far as could be determined with available tooling).'),
 false),
('04888cc3-410a-4878-969b-d994a0a31d2e', 'fallback', 'calhoun', 'F',
 'Same as B — tier1 sold amount cannot be sourced for the 3 past-due calhoun cases.',
 jsonb_build_object('method', 'independent refetch of both cited pages', 'finding', 'Same as B row.'),
 false),
('04888cc3-410a-4878-969b-d994a0a31d2e', 'fallback', 'liberty', 'A',
 'No tax-deed case exists for Liberty County (libertyclerk.com tax-deeds page shows zero).',
 jsonb_build_object('method', 'independent refetch + records-search page check', 'finding', 'Source only proves "nothing currently scheduled", not "no case exists ever" — claim overreaches its evidence. Downgraded VERIFIED to UNKNOWN.'),
 false),
('04888cc3-410a-4878-969b-d994a0a31d2e', 'fallback', 'liberty', 'B',
 'Sale outcome for case 24-CA-22 (sale date 2026-07-21, now past) not found on libertyclerk.com.',
 jsonb_build_object('method', 'independent refetch of cited page', 'finding', 'Researcher already labeled UNKNOWN; confirmed genuinely no posted result found with available tooling.'),
 false),
('04888cc3-410a-4878-969b-d994a0a31d2e', 'fallback', 'liberty', 'F',
 'Same as B — tier1 sold amount for case 24-CA-22 unresolved.',
 jsonb_build_object('method', 'independent refetch of cited page', 'finding', 'Same as B row.'),
 false);

UPDATE public.gold_standard_campaign
SET
  criteria_passed = jsonb_build_object(
    'miami_dade',   jsonb_build_object('A',true,'B',true,'C',true,'D',true,'E',true,'F',true,'G',true,'H',true,'I',true,'J',true),
    'indian_river', jsonb_build_object('A',true,'B',true,'C',true,'D',true,'E',true,'F',true,'G',true,'H',true,'I',false,'J',true),
    'calhoun',      jsonb_build_object('A',true,'B',false,'C',true,'D',true,'E',true,'F',false,'G',true,'H',true,'I',true,'J',true),
    'martin',       jsonb_build_object('A',true,'B',true,'C',true,'D',true,'E',false,'F',true,'G',true,'H',true,'I',false,'J',true),
    'liberty',      jsonb_build_object('A',false,'B',false,'C',true,'D',true,'E',true,'F',false,'G',true,'H',true,'I',true,'J',true)
  ),
  criteria_total = 10,
  exit_reason = 'diagnosed_no_verified_fix_survived_adversarial_check',
  session_end_at = now()
WHERE dispatch_id = '04888cc3-410a-4878-969b-d994a0a31d2e';
