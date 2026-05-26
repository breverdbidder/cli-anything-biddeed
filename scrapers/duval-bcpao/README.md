# Duval BCPAO Harvest Scraper

Production scraper for Duval County Property Appraiser data (`paopropertysearch.coj.net`). Feeds the Shapira V4.0 discount-to-assessed-value ratio computation in BidDeed.AI.

## Status (2026-05-26)

- ✅ Schema deployed to Supabase (`mocerqjnksmhcjzxrewo`)
- ✅ Queue seeded: **2,648 parcels** (362 top-20-priority, 325 recent, 1,961 normal)
- ✅ Parser validated: **5/5 + 27/30 = 32/35 real BCPAO pages parsed successfully** (3 no_record, parcels retired at BCPAO)
- ✅ First V4.0 metrics live: bid-to-assessed-value ratio + bid-to-market discount per buyer

## Deployment path

### Option A — GitHub Actions (recommended)

1. Push these files to `breverdbidder/cli-anything-biddeed`:
   - `scrapers/duval-bcpao/duval_bcpao_scraper.py`
   - `scrapers/duval-bcpao/requirements.txt`
   - `.github/workflows/duval-bcpao-harvest.yml`

2. Add GitHub secret `SUPABASE_DB_URL` (Postgres connection string from Supabase Dashboard → Settings → Database → Connection string → URI).

3. Add optional `USER_AGENT_EMAIL` secret (your contact email — polite to the BCPAO host).

4. The workflow runs every 2 hours from 9am to 9pm ET. At ~1.5 req/sec × 40 iters × 50 batch = 2,000 parcels/run cap. Should drain the 2,648 queue in 2 scheduled runs.

5. Manual trigger via Actions tab → "Duval BCPAO Harvest" → Run workflow.

### Option B — Hetzner / local

```bash
export SUPABASE_DB_URL="postgresql://postgres.mocerqjnksmhcjzxrewo:****@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
export USER_AGENT_EMAIL="research@everestcapital.us"

python -m pip install -r requirements.txt
python duval_bcpao_scraper.py --batch 100 --rate 1.5 --max-iters 200
```

## Why a new workflow (not claude-code-direct.yml)

Per the documented infrastructure quarantine (`claude-code-direct.yml` blocked since 2026-05-06 with 99.88% dead dispatch rows), this scraper deploys as an independent workflow. It does not write to `summit_chat_dispatch` and does not depend on the quarantined dispatcher.

## Tables

- `public.duval_bcpao_assessments` — output, one row per parcel, ON CONFLICT merge
- `public.duval_bcpao_harvest_queue` — work queue, claimed atomically via `FOR UPDATE SKIP LOCKED`

## Honesty markers

Each row in `duval_bcpao_assessments` carries a `honesty_marker` column per Honesty Protocol V3:

- `VERIFIED` — 4/4 core fields (assessed, market, land, use_code) populated cleanly
- `INFERRED` — 2-3/4 core fields, partial parse
- `UNKNOWN` — failed parse (sets `parse_status=failed`)

## Backfill order

Priority ordering in the queue is set at seed time:

- **priority 10** — parcels acquired by top-20 leaderboard buyers (362 rows)
- **priority 30** — recent acquisitions, 2024-01-01 onward (325 rows)
- **priority 100** — everything else (1,961 rows)

The scraper claims by `priority ASC, queued_at ASC`, so top-20 parcels finish first. Within ~4 hours of first run, the V4.0 top-20 analysis can be fully recomputed with real assessed-value joins.

## Next steps after harvest completes

1. **Recompute the V4.0 top-20 metrics** with real `bid_to_assess_ratio` per buyer
2. **Train `shapira_formula_params`** — compute `optimal_bid_pct_of_assessed`, `bid_floor_pct`, `bid_ceiling_pct` per county/property_use_code
3. **Backfill `opening_bid` in `flynn_winning_bids`** — separate RealAuction scraper (Track B, requires `summit-cli` unblock first)
4. **V4.0 anchor retraining** — feed 16 unmatched top-20 entities (BCEL family, Hoose family, etc.) into anchor classifier with new feature set

## Verified URL pattern

```
GET https://paopropertysearch.coj.net/Basic/Detail.aspx?RE={parcel_id_without_dash}
```

- Parcel ID `167758-1005` → `RE=1677581005` (strip the dash)
- HTTP 200 + redirect to `Results.aspx?Results=None` = parcel not found at BCPAO
- HTTP 200 + Detail page = record present, parse it

## Parsed fields (per row in `duval_bcpao_assessments`)

| Column | BCPAO label ID | Notes |
|---|---|---|
| `assessed_value` | `lblAssessedValueA10Certified` | Last certified (Oct 2025 tax roll); fallback `InProgress` |
| `just_market_value` | `lblJustMarketValueCertified` | Fair market value per appraiser |
| `total_building_value` | `lblBuildingValueCertified` | All structures combined |
| `land_value_market` | `lblLandValueMarketCertified` | Land-only market value |
| `taxable_value` | `lblTaxableValueCertified` | Post-exemption taxable basis |
| `property_use_code` | `lblPropertyUse` | 4-digit code (0100, 0200, 0800, 9600 etc.) |
| `property_use_desc` | (parsed from `lblPropertyUse`) | "Single Family", "Mobile Home", "Multi-Family Units 2-9", "Waste Land", etc. |
| `total_area_sqft` | `lblTotalArea1` | GIS-calculated parcel area |
| `year_built` | first building repeater | If applicable (residential) |

## Verification queries

```sql
-- Top buyers by bid-to-assessed-value (lowest = best deal)
SELECT c.buyer,
       COUNT(*) AS deeds_with_assess,
       ROUND(AVG(c.purchase_price / NULLIF(b.assessed_value,0))::numeric, 3) AS avg_ratio,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY c.purchase_price / NULLIF(b.assessed_value,0))::numeric, 3) AS median_ratio
FROM duval_tax_deed_conveyances_unified c
JOIN duval_bcpao_assessments b ON b.parcel_id_raw = c.parcel_pin_extracted
WHERE b.parse_status='parsed' AND b.assessed_value > 0
GROUP BY c.buyer
HAVING COUNT(*) >= 3
ORDER BY median_ratio;

-- Queue status snapshot
SELECT status, COUNT(*) FROM duval_bcpao_harvest_queue GROUP BY status;
```
