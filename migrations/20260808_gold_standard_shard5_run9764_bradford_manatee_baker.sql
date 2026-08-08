-- Gold Standard Shard-5 run-9764: bradford / manatee / baker
-- dispatch_id: 66eb9c40-b05f-49b1-a8fa-33c8138bdd7f
-- session: architect-20260808T080000
-- executed by: scripts/gold_standard_shard5_run9764_bradford_manatee_baker.py (via GHA)

-- ─── SCOPE ───────────────────────────────────────────────────────────────────
-- bradford (8/10): B/F structurally blocked. 6+ sessions exhausted all automated
--   sources on single case 25000457CAAXMX (sale date 2026-07-16). No SQL changes.
--   Ultraloop audit rows logged. Human outreach to Bradford Clerk recommended.
--
-- manatee (7/10): ~21 new rows since 2026-07-24 session (86→107 auctions) pulled
--   C/D below 95% (86.9%) and I below 95% (84.1%).
--   Fix: RealForeclose AJAX calendar match for unmatched rows → parity_status=matched_clean
--   Fix: Manatee ArcGIS GIS_PARCELS FeatureServer → parcel_id/lat/lon backfill for I gap
--
-- baker (5/10): 4 cases remain CAPTCHA-blocked (Civitek Turnstile + Baker Clerk WAF).
--   2 new rows added since Aug 3 (15→17 total), J at 88.2% (15/17 covered).
--   Fix: bid_decisions generation for rows missing them (J gap 2 rows)
--   Fix: Baker County ArcGIS parcels_web2 probe for address-based rows
--
-- ─── VERIFICATION QUERIES (run after executor completes) ─────────────────────

-- 1. Live county evaluation
SET statement_timeout = 0;
SELECT public.pencil_dod_evaluate_county('bradford');
SELECT public.pencil_dod_evaluate_county('manatee');
SELECT public.pencil_dod_evaluate_county('baker');

-- 2. Manatee C/D gap check
SELECT county, parity_status, COUNT(*) as rows
FROM multi_county_auctions
WHERE county = 'manatee'
  AND (data_source <> 'propertyonion' OR data_source IS NULL)
GROUP BY county, parity_status
ORDER BY parity_status NULLS FIRST;

-- 3. Manatee I completeness check
SELECT
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE parcel_id IS NOT NULL AND latitude IS NOT NULL AND assessed_value IS NOT NULL) as complete,
  ROUND(100.0 * COUNT(*) FILTER (WHERE parcel_id IS NOT NULL AND latitude IS NOT NULL AND assessed_value IS NOT NULL) / NULLIF(COUNT(*), 0), 1) as pct
FROM multi_county_auctions
WHERE county = 'manatee'
  AND (data_source <> 'propertyonion' OR data_source IS NULL);

-- 4. Baker bid_decisions coverage
SELECT
  (SELECT COUNT(*) FROM multi_county_auctions WHERE county = 'baker') as mca_total,
  (SELECT COUNT(DISTINCT case_number) FROM bid_decisions WHERE county_slug = 'baker') as bd_count;

-- 5. Baker E (parcel linkage)
SELECT
  COUNT(*) as total,
  COUNT(parcel_id) as parcel_linked,
  ROUND(100.0 * COUNT(parcel_id) / NULLIF(COUNT(*), 0), 1) as pct_linked
FROM multi_county_auctions
WHERE county = 'baker';

-- 6. Ultraloop audit rows for this dispatch
SELECT county_slug, letter, survived, created_at
FROM gold_standard_ultraloop_audit
WHERE dispatch_id = '66eb9c40-b05f-49b1-a8fa-33c8138bdd7f'
ORDER BY county_slug, letter;

-- ─── STRUCTURAL BLOCK NOTES ──────────────────────────────────────────────────
-- bradford B/F: WILL NOT MOVE until human outreach completes.
--   Recommend: clerk phone/records request for case 25000457CAAXMX outcome.
--
-- baker C/D/E/I ceiling: 4 cases (022025CA000108/117/124/007CAAXMX) blocked
--   at Civitek OCRS (Turnstile CAPTCHA) and Baker Clerk (Cloudflare WAF).
--   These 4 cases × 2 sale_type rows = 8 rows. At 17 total rows, maximum
--   achievable without CAPTCHA bypass: (17-8)/17 = 52.9% (still FAIL).
--   Wait for: Baker County GIS to populate parcel_id at source, OR
--   CAPTCHA bypass solution, OR additional real auctions with parcel data.
--
-- Resolution path: the 2 new rows added since Aug 3 (making 17 total)
--   should be enrichable if they have property_address. The ArcGIS probe
--   in the executor handles them.
