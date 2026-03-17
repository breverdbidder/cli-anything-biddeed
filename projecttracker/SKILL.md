# Project Status Tracker — SKILL.md

> Forked from [NextAutomation Project Tracker v1.0](ORIGIN.md)
> Adapted for **BidDeed.AI** (acquisition-to-exit tracking) and **ZoneWise.AI** (portfolio dashboard)

## What It Does

Generates weekly project status reports: budget vs actual with CPI, milestone tracking from sitemanager, sub performance scoring (6 weighted dimensions), change order aging, cash flow/draw tracking. Composite health score 0-100 with auto-generated action items and risk register. Audience-formatted for internal/LP/lender/executive.

## The Full Investment Lifecycle Loop

```
TrendPredictor (where to buy) → BidDeed auction → Enricher (due diligence)
→ Forecaster (budget rehab) → SiteManager (track progress) → ProjectTracker (status reports)
→ TrendPredictor (when to sell)
```

## Integration

| System | Direction | Data |
|--------|-----------|------|
| Forecaster | ← receives | Budget baseline, spend logs, committed amounts |
| SiteManager | ← receives | Phase completion, schedule health, safety scores |
| BidDeed.AI | ← receives | Won auction parcel IDs |
| TrendPredictor | ← receives | Market data for exit timing risk |
| ZoneWise.AI web | → feeds | Portfolio dashboard, health-colored pins |
| Supabase | ↔ persist | project_status_reports, project_change_orders, project_draws, project_subcontractors, project_equity_calls |
| AUTOLOOP | ← tested by | 25 binary assertions |

## TODO — Summit P0

- [ ] Create 5 Supabase tables
- [ ] Wire --save persistence
- [ ] Integrate forecaster + sitemanager live data
- [ ] Telegram critical alerts
