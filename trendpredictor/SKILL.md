# Market Trend Predictor — SKILL.md

> Forked from [NextAutomation Market Trend Predictor v1.0](ORIGIN.md)
> Adapted for **ZoneWise.AI** (Mapbox heatmaps) and **BidDeed.AI** (auction timing)

## What It Does

Scores 15 Brevard County submarkets on a -10 to +10 direction scale using the SIGNAL framework. Generates Mapbox GL JS heatmaps for ZoneWise.AI showing where to BUY/BUILD/HOLD/SELL.

## 6-Stage Pipeline

```
RENTS → VELOCITY → SUPPLY → INDICATORS → CYCLE → PREDICT
```

## Mapbox Heatmap Output

- Dark map style with BidDeed brand gradient (navy → blue → orange → red)
- Click-to-inspect popups: score, action, cycle phase, confidence
- Standalone HTML or GeoJSON for embedding in ZoneWise.AI

## Integration

| System | Direction | Data |
|--------|-----------|------|
| ZoneWise.AI web | → feeds into | Mapbox heatmap GeoJSON |
| BidDeed.AI auctions | ← receives | Foreclosure volume as distress signal |
| Enricher pipeline | → feeds into | Market context for valuation |
| Forecaster pipeline | → feeds into | Timing for rehab decisions |
| Supabase `market_trends` | ↔ persist | Historical trend tracking |
| AUTOLOOP eval | ← tested by | 25 binary assertions |
