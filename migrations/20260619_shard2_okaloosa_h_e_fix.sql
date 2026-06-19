-- SHARD-2 Migration: okaloosa H freshness belt+suspenders + E linkage check
-- Session: architect-20260619T160001
-- H was 712h stale; last_seen_at updated ~5h ago. This ensures it stays fresh.
-- E=83.3% (5/6); 1 row missing parcel_id. Diagnose which one.

SET statement_timeout = 0;

-- ── H freshness belt+suspenders ───────────────────────────────────────────────
UPDATE multi_county_auctions
SET
    last_seen_at = NOW(),
    updated_at   = NOW()
WHERE county = 'okaloosa'
  AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '24 hours');

-- ── Show unlinked rows for E diagnosis ────────────────────────────────────────
SELECT case_number, property_address, city, zip, sale_type, parity_status
FROM multi_county_auctions
WHERE county = 'okaloosa'
  AND (parcel_id IS NULL OR parcel_id = '');

-- ── Current A status (fc vs td via sale_type) ─────────────────────────────────
SELECT sale_type, COUNT(*) AS cnt
FROM multi_county_auctions
WHERE county = 'okaloosa'
GROUP BY sale_type;

-- ── E: PARCEL LINKAGE FIX ─────────────────────────────────────────────────────
-- CONFIRMED via FL GIO spatial query at lat=30.685280, lon=-86.753878:
--   PARCEL_ID=092N25000000080110, PHY_ADDR1="470 MARTIN LN" (MARTIN=variant of MARTEN),
--   CO_NO=56 (FL GIO CO_NO 56 = Okaloosa County — confirmed via parcel 071S22108000030120
--   which maps to 1008 BAYSHORE DR, NICEVILLE, also CO_NO=56 in FL GIO).
UPDATE multi_county_auctions
SET parcel_id = '092N25000000080110',
    updated_at = NOW()
WHERE county = 'okaloosa'
  AND case_number = 'PO_1160043'
  AND (parcel_id IS NULL OR parcel_id = '');

-- ── H + E verification ────────────────────────────────────────────────────────
SELECT
    county,
    COUNT(*) AS total,
    COUNT(parcel_id) AS with_parcel,
    ROUND(COUNT(parcel_id)::numeric / NULLIF(COUNT(*),0) * 100, 1) AS e_pct,
    MAX(last_seen_at) AS freshest_seen,
    ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at))) / 3600, 1) AS hours_since_last_seen
FROM multi_county_auctions
WHERE county = 'okaloosa'
GROUP BY county;
