# AUCTION.md — Project-Specific Analysis & SOP

## Architecture Summary

The Auction Analyzer is a foreclosure auction intelligence platform for Brevard County, FL.
It discovers upcoming auctions, analyzes cases (liens, ARV, repairs), and produces
BID/REVIEW/SKIP recommendations with full DOCX reports.

```
┌──────────────────────────────────────────────┐
│           External Data Sources               │
│  ┌──────────────┐ ┌───────┐ ┌─────────────┐  │
│  │ RealForeclose│ │ BCPAO │ │ AcclaimWeb  │  │
│  │ (auctions)   │ │(props)│ │ (liens)     │  │
│  └──────┬───────┘ └───┬───┘ └──────┬──────┘  │
└─────────┼─────────────┼────────────┼──────────┘
          │             │            │
   ┌──────┴─────────────┴────────────┴──────┐
   │       Analysis Pipeline                 │
   │  Discover → Liens → ARV → Max Bid      │
   │  → Recommend (BID/REVIEW/SKIP)          │
   └──────────────────┬─────────────────────┘
                      │
   ┌──────────────────┴─────────────────────┐
   │        cli-anything-auction             │
   │  Click CLI + REPL + --json + DOCX       │
   │  --persist → Supabase                   │
   └─────────────────────────────────────────┘
```

## Backend Strategy

All backends are public HTTP endpoints (no API keys required):

1. **RealForeclose** — brevard.realforeclose.com: auction calendar, case lists, bidding
2. **BCPAO** — Brevard County Property Appraiser: property data, photos, sales history
3. **AcclaimWeb** — Brevard Clerk of Courts: recorded documents, liens, mortgages

## Data Model

### Case Analysis
```json
{
  "case_number": "2024-CA-001234",
  "property_address": "123 Ocean Ave, Satellite Beach, FL 32937",
  "judgment_amount": 223000,
  "arv": 285000,
  "repairs": 35000,
  "max_bid": 142000,
  "bid_ratio": 0.637,
  "recommendation": "REVIEW",
  "liens": [...],
  "plaintiff": "Bank of America"
}
```

### Max Bid Formula
`(ARV × 70%) - Repairs - $10K - MIN($25K, 15% × ARV)`

### Recommendation Thresholds
- BID: bid_ratio ≥ 0.75
- REVIEW: 0.60 ≤ bid_ratio < 0.75
- SKIP: bid_ratio < 0.60
