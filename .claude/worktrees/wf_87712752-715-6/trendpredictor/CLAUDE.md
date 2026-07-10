# CLAUDE.md — Market Trend Predictor

> Harness: `cli-anything-biddeed/trendpredictor/`
> Origin: Forked from NextAutomation Market Trend Predictor v1.0
> Owner: Ariel Shapira — ZoneWise.AI + BidDeed.AI

## What This Is

Market intelligence engine for Brevard County submarkets. Generates direction scores (-10 to +10), cycle position mapping, and Mapbox heatmaps for ZoneWise.AI. Also informs BidDeed.AI auction timing decisions.

**THIS IS THE ZONEWISE.AI FLAGSHIP FEATURE.** Heatmap visualization of where to buy/build/hold/sell across Brevard County, updated nightly.

## Pipeline

```
RENTS → VELOCITY → SUPPLY → INDICATORS → CYCLE → PREDICT
```

| Stage | Source | Status |
|-------|--------|--------|
| RENTS | BCPAO GIS sales + Census ACS rent | ✅ Working (needs Zillow ZORI) |
| VELOCITY | Supabase auctions + Census vacancy | ✅ Working |
| SUPPLY | Census permits | ⚠️ Basic (needs Brevard PermitsPlus) |
| INDICATORS | BLS employment + Brevard defaults | ⚠️ Partial (needs Google Trends) |
| CYCLE | Mueller model from all stages | ✅ Working |
| PREDICT | SIGNAL framework + Mapbox GeoJSON | ✅ Working |

## Mapbox Integration

Token: `$MAPBOX_TOKEN` (account: everest18)
Style: `mapbox://styles/mapbox/dark-v11`
Center: `[-80.68, 28.24]` (Brevard County)
Brand colors in heatmap: Navy #1E3A5F → Blue → Orange #F59E0B → Red

## SIGNAL Framework Weights

| Signal | Weight | Source |
|--------|--------|--------|
| rent_trend | 20% | BCPAO + Census |
| absorption | 15% | Census vacancy |
| supply_pipeline | 15% | Census permits |
| employment | 15% | BLS + Space Coast |
| migration | 10% | Census |
| affordability | 10% | Rent/income ratio |
| foreclosure_volume | 10% | Supabase auctions (BidDeed) |
| interest_rates | 5% | Fed/SOFR |

## 15 Brevard Submarkets

Tier A (premium): 32937 Satellite Beach, 32940 Melbourne/Viera, 32953 Merritt Island, 32903 Indialantic, 32931 Cocoa Beach
Tier B (mid): 32905/32907 Palm Bay, 32780 Titusville, 32955 Rockledge, 32935 Melbourne East, 32901 Melbourne Downtown, 32904 Melbourne South
Tier C (value): 32908 Palm Bay South, 32927 Cocoa West, 32922 Cocoa

## Supabase Table: `market_trends`

```sql
CREATE TABLE IF NOT EXISTS market_trends (
  id BIGSERIAL PRIMARY KEY,
  zip_code TEXT NOT NULL,
  submarket_name TEXT,
  direction_score FLOAT,
  direction_label TEXT,
  timing_action TEXT,
  cycle_phase TEXT,
  vacancy_rate FLOAT,
  median_sale_price BIGINT,
  foreclosure_trend TEXT,
  signal_breakdown JSONB,
  geojson_feature JSONB,
  confidence FLOAT,
  horizon_months INT,
  analyzed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(zip_code, analyzed_at)
);
CREATE INDEX IF NOT EXISTS idx_mt_zip ON market_trends(zip_code);
CREATE INDEX IF NOT EXISTS idx_mt_analyzed ON market_trends(analyzed_at);
```

## Key Files

- `agent.py` — Full 6-stage pipeline + Mapbox heatmap generator + CLI
- `eval/eval.json` — 25 binary assertions for AUTOLOOP
- `SKILL.md` — Docs and integration map
- `ORIGIN.md` — Original NextAutomation spec

## Development Rules

1. All `print()` → `sys.stderr`. Only `--json` on stdout. ALREADY correct.
2. All `httpx.Client()` uses `headers=UA`. ALREADY correct.
3. Mapbox heatmap uses BidDeed brand colors: navy #1E3A5F, orange #F59E0B
4. Direction score always -10 to +10. heatmap_weight always 0 to 1.
5. GeoJSON output must be valid FeatureCollection with Point geometries
6. Rate limit all external APIs: 2s between requests

## Session Priorities

### P0 — Supabase + Persistence
1. Create `market_trends` table
2. Add `--save` flag to persist analysis results
3. Wire nightly pulse (all 15 ZIPs) → Supabase → Telegram summary

### P1 — Data Quality
4. Zillow ZORI CSV download + parse for rental rates by ZIP
5. Google Trends API for "apartments in Melbourne FL" etc.
6. BCPAO sales trend: compare 6-month windows for YoY growth calc
7. Brevard PermitsPlus for new construction pipeline count

### P2 — Heatmap Polish
8. Circle layer with popup details (in addition to heatmap)
9. Time-slider for historical heatmap animation
10. Choropleth alternative using ZIP boundary polygons
11. Embed in ZoneWise.AI web app (zonewise-web repo)

### P3 — Advanced
12. ARIMA time-series forecast for rent growth prediction
13. Comp market comparison (Orlando, Jacksonville, Tampa)
14. Alert system: Telegram when direction score crosses threshold

## CLI Quick Reference

```bash
# Single submarket
python3 -m trendpredictor.agent analyze --zip 32937 --horizon 12 --json

# Compare 4 submarkets
python3 -m trendpredictor.agent compare --zips 32937,32940,32953,32903 --json --heatmap-html heatmap.html

# Full county pulse with heatmap
python3 -m trendpredictor.agent pulse --county brevard --json --heatmap-html brevard_pulse.html

# Status
python3 -m trendpredictor.agent status
```
