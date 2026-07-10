# Cost Forecaster — SKILL.md

> Forked from [NextAutomation Cost Forecaster v1.0](ORIGIN.md)
> Adapted for **BidDeed.AI** (rehab budgets) and **ZoneWise.AI** (renovation ROI)

## What It Does

Predicts total rehab cost for Brevard County residential properties. Takes a budget + optional spend log → returns forecast, overrun alerts, and best/base/worst scenarios with max bid recalculation.

## 6-Stage Pipeline

```
BUDGET → VELOCITY → HISTORY → FORECAST → ALERTS → SCENARIOS
```

## Three Budget Templates

| Template | Budget Range | Use Case |
|----------|-------------|----------|
| `light_rehab` | $15-40K | Cosmetic flip — paint, flooring, fixtures |
| `medium_rehab` | $40-100K | Systems + cosmetic — roof, HVAC, plumbing, kitchen |
| `heavy_rehab` | $100-250K | Full gut — structural + everything |

## Integration

| System | Direction | Data |
|--------|-----------|------|
| Enricher pipeline | ← receives | ARV, assessed value, permits, parcel data |
| BidDeed.AI auctions | ← feeds into | Repair estimates for max bid formula |
| ZoneWise.AI leads | → feeds into | Renovation ROI for off-market analysis |
| Supabase `rehab_projects` | ↔ persist | Project budgets and forecasts |
| Supabase `rehab_spend_log` | ↔ persist | Expense tracking per project |
| AUTOLOOP eval | ← tested by | 25 binary assertions |

## TODO

- [ ] Create Supabase tables (rehab_projects, rehab_spend_log)
- [ ] --save flag to persist forecasts
- [ ] update-spend subcommand for expense logging
- [ ] Wire historical query with actual repair cost data
- [ ] Enricher integration (accept enricher JSON as input)
- [ ] DOCX report with budget vs actual
- [ ] Weekly Telegram digest for active projects
- [ ] Material price tracking (lumber, concrete in FL)
