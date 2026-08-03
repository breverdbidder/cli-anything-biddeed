-- GOLD STANDARD ADVERSARIAL-9/10 (dispatch 00406956-2df6-4aa4-9acf-331beebeeb20)
-- hillsborough, orange, seminole, volusia — attempted the "last adversarial pass" to
-- reach 10/10. All four FAILED genuine re-verification. Recording honest survived=false
-- audit rows with concrete evidence; NOT forcing certification.
--
-- Findings (live-queried against multi_county_auctions on 2026-08-03):
--
-- hillsborough I (card completeness): 740 of 907 lat/lon-populated rows (81.6%) share
--   the IDENTICAL coordinate (27.9506, -82.4572) across 8+ visibly distinct street
--   addresses (2319 S 50TH ST, 225 S VALRICO RD, 8641 FANCY FINCH DR, 8511 N 48TH ST,
--   111 N 12TH ST, 312 N MANHATTAN AVE, 711 E SKAGWAY AVE, 3925 W PALMETTO ST, ...).
--   That coordinate is the Tampa/Hillsborough centroid, not a per-parcel geocode.
--   The "I" metric (96.6%, card_complete=861/891) is satisfied by a placeholder
--   fallback lat/lon, not real geocoding.
--
-- orange I (card completeness): 830 of 859 lat/lon-populated rows (96.6%) share the
--   IDENTICAL coordinate (28.5383, -81.3792) across distinct addresses (7828 BARDMOOR
--   HILL CIR, 806 SPRINGVIEW DR, ANNA CATHERINE DR, 1158 MARTIN BLVD, 1002 SANTA
--   BARBARA RD, 6321 REDWOOD OAKS DR, ...). Same pattern: Orange County centroid used
--   as a geocode placeholder, not a real per-parcel lookup.
--
-- seminole F (sale-outcome authenticity): 60 of 63 tier1_sold rows (95.2%) have
--   tier1_sold_amount == judgment_amount * 0.65 EXACTLY (4-decimal ratio match),
--   overwhelmingly on data_source='realforeclose'. This is the same formula-derived
--   placeholder flagged in the 2026-07-29 refutation (dispatch producing
--   gold_standard_ultraloop_audit id 8512-series) — NOT a genuine clerk-recorded
--   winning bid. Unresolved since that finding.
--
-- volusia H (freshness authenticity): all 396 in-scope rows share one IDENTICAL
--   last_seen_at (2026-08-03 15:56:48.440507+00). Per-row GREATEST(last_changed_at,
--   last_seen_at, scraped_at, scrape_timestamp, created_at) is dominated by this bulk
--   value for the majority of rows (369/396), i.e. the H metric reported at the
--   16:59:19 evaluation (1.0h) was driven by this bulk touch, not a genuine scrape.
--   scripts/duval_orange_h_freshness_fix.py demonstrates this exact bulk-PATCH
--   pattern exists in this codebase (targets duval/orange today; volusia shows the
--   identical signature). Matches the 2026-07-31 refutation almost exactly.
--
-- Action: record fresh survived=false adversarial audit rows (evidence attached) so
-- v_gold_cert_health continues to correctly report ADVERSARIAL_INCOMPLETE / blocked,
-- and so future sessions inherit accurate, current evidence instead of stale (7d+)
-- audit rows. No row in gold_standard_certifications is touched.

insert into public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
values
  (
    '00406956-2df6-4aa4-9acf-331beebeeb20', 'native', 'hillsborough', 'I',
    'hillsborough letter I: card_complete=861 of 891 (metric=96.6, pass=True) -- REFUTED: lat/lon populated via county-centroid placeholder, not real geocoding',
    jsonb_build_object(
      'finding', 'centroid_fallback_geocode',
      'centroid', jsonb_build_object('lat', 27.9506, 'lon', -82.4572),
      'affected_rows', 740,
      'lat_lon_populated_rows', 907,
      'pct_affected', 81.6,
      'sample_distinct_addresses_same_point', jsonb_build_array(
        '2319 S 50TH ST', '225 S VALRICO RD', '8641 FANCY FINCH DR 104, TAMPA, FL- 33614',
        '8511 N 48TH ST', '111 N 12TH ST 1520', '312 N MANHATTAN AVE',
        '711 E SKAGWAY AVE', '3925 W PALMETTO ST, TAMPA, FL- 33607'),
      'audit_timestamp', now()
    ),
    false, now()
  ),
  (
    '00406956-2df6-4aa4-9acf-331beebeeb20', 'native', 'orange', 'I',
    'orange letter I: card_complete=791 of 832 (metric=95.1, pass=True) -- REFUTED: lat/lon populated via county-centroid placeholder, not real geocoding',
    jsonb_build_object(
      'finding', 'centroid_fallback_geocode',
      'centroid', jsonb_build_object('lat', 28.5383, 'lon', -81.3792),
      'affected_rows', 830,
      'lat_lon_populated_rows', 859,
      'pct_affected', 96.6,
      'sample_distinct_addresses_same_point', jsonb_build_array(
        '7828 BARDMOOR HILL CIR', '806 SPRINGVIEW DR', 'ANNA CATHERINE DR',
        '1158 MARTIN BLVD', '1002 SANTA BARBARA RD', '6321 REDWOOD OAKS DR'),
      'audit_timestamp', now()
    ),
    false, now()
  ),
  (
    '00406956-2df6-4aa4-9acf-331beebeeb20', 'native', 'seminole', 'F',
    'seminole letter F: tier1_sold=63 of 63 closed_sold (metric=100.0, pass=True) -- REFUTED: tier1_sold_amount is formula-derived (judgment_amount*0.65), not a genuine clerk-recorded price',
    jsonb_build_object(
      'finding', 'formula_derived_sold_amount',
      'formula', 'tier1_sold_amount = judgment_amount * 0.65',
      'affected_rows', 60,
      'total_tier1_sold_rows', 63,
      'pct_affected', 95.2,
      'dominant_data_source', 'realforeclose',
      'prior_refutation', 'gold_standard_ultraloop_audit id~8512-series, 2026-07-29 -- unresolved',
      'audit_timestamp', now()
    ),
    false, now()
  ),
  (
    '00406956-2df6-4aa4-9acf-331beebeeb20', 'native', 'volusia', 'H',
    'volusia letter H: 1.0h since last_seen (metric pass=True, SLA 48h) -- REFUTED: freshness driven by a bulk last_seen_at touch shared by all in-scope rows, not a genuine per-row scrape',
    jsonb_build_object(
      'finding', 'bulk_last_seen_at_touch',
      'identical_last_seen_at', '2026-08-03T15:56:48.440507+00:00',
      'affected_rows', 396,
      'total_in_scope_rows', 396,
      'pct_affected', 100.0,
      'codebase_precedent', 'scripts/duval_orange_h_freshness_fix.py PATCHes last_seen_at/last_changed_at to now() fleet-wide with no real scrape -- same signature observed live on volusia',
      'prior_refutation', '2026-07-31 -- unresolved',
      'audit_timestamp', now()
    ),
    false, now()
  );

insert into public.agent_ops_log (id, dispatch_id, task, status, evidence, severity, created_at)
values (
  gen_random_uuid(),
  '00406956-2df6-4aa4-9acf-331beebeeb20',
  'gold-adversarial-9-shard',
  'BLOCKED',
  'hillsborough/orange letter I and seminole letter F and volusia letter H all FAILED genuine adversarial re-verification (fresh live-query evidence, not stale): hillsborough+orange I use a county-centroid placeholder lat/lon shared by hundreds of distinct-address rows instead of real per-parcel geocoding; seminole F sold-amount is a judgment_amount*0.65 formula for 95% of tier1_sold rows, not a clerk-recorded price; volusia H freshness is driven by a bulk last_seen_at PATCH shared by all 396 in-scope rows (matches scripts/duval_orange_h_freshness_fix.py pattern), not a genuine scrape. Recorded honest survived=false rows in gold_standard_ultraloop_audit with full evidence. Did NOT force certification. Real fixes required: genuine per-parcel geocoding (hillsborough/orange), genuine clerk sale-price capture (seminole), genuine scrape-driven freshness (volusia) before these letters can honestly reach adversarial_ok=true.',
  'blocker',
  now()
);
