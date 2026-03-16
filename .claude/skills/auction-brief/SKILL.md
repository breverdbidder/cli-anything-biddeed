---
name: auction-brief
description: Morning auction briefing. Queries Supabase for upcoming auctions, pulls latest metrics, surfaces priority deals, and generates a daily summary. Run this every morning.
---

# Auction Brief — Daily BidDeed.AI Briefing

Query Supabase `multi_county_auctions` for auctions in the next 7 days. Query `daily_metrics` for yesterday's pipeline stats. Check `insights` for any unresolved flags.

Generate a briefing:

```markdown
# 🔨 Auction Brief — [today's date]

## Today's Auctions
[list auctions happening TODAY with county, case, judgment, property address, recommendation]

## This Week (next 7 days)
[count by county, total judgment value, BID/REVIEW/SKIP breakdown]

## Pipeline Health
- Auctions scraped: [count from daily_metrics]
- New properties: [count]
- Data freshness: [last scrape timestamp]
- Alerts: [any stale data, failed scrapes, or anomalies]

## Priority Deals
[Top 3 BID-recommended properties with key numbers: ARV, max bid, bid/judgment ratio]

## What needs attention?
[Unresolved insights, pending reviews, upcoming deadlines]
```

If Supabase is unreachable, say so and offer to run with cached data. Never invent numbers.
