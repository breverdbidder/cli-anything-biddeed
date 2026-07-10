# Site Manager / Rehab Monitor — SKILL.md

> Forked from [NextAutomation Site Manager v1.0](ORIGIN.md)
> Adapted for **ZoneWise.AI** (post-acquisition rehab tracking) and **BidDeed.AI** (flip project monitoring)

## What It Does

Tracks active rehab projects: 16-phase progress monitoring, contractor accountability via photo docs, 10 Brevard-specific safety auto-checks, composite site health score (0-100), Mapbox pins for the ZoneWise.AI property map.

## The ZoneWise.AI Post-Acquisition Loop

```
BidDeed.AI wins auction → Enricher profiles property → Forecaster budgets rehab
→ Site Manager tracks progress → Forecaster updates spend → TrendPredictor validates exit timing
```

## Integration

| System | Direction | Data |
|--------|-----------|------|
| BidDeed.AI | ← receives | Won auction parcel IDs |
| Enricher | ← receives | Property profile, year built, sqft |
| Forecaster | ↔ sync | Budget categories = rehab phases; spend tracking |
| TrendPredictor | ← receives | Market timing for sell/hold decision |
| ZoneWise.AI web | → feeds | Mapbox GeoJSON pins (health-colored) |
| Supabase | ↔ persist | rehab_site_reports, rehab_site_photos |
| AUTOLOOP | ← tested by | 25 binary assertions |
