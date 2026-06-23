# biddeed-mcp

**BidDeed.AI MCP Server** — FL foreclosure intelligence for Claude, Cursor, ChatGPT, and any MCP client.

25 tools across 7 revenue streams: auction search, Shapira underwriting, zoning, lien stacks, co-living analysis, skip trace, and more.

## Quick Start

```json
{
  "mcpServers": {
    "biddeed": {
      "command": "npx",
      "args": ["-y", "biddeed-mcp"],
      "env": {
        "BIDDEED_API_KEY": "bd_live_...",
        "SUPABASE_URL": "https://mocerqjnksmhcjzxrewo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "eyJ..."
      }
    }
  }
}
```

Get your API key: https://biddeed.ai/dashboard

## HTTP Mode

```bash
PORT=3000 SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... npx biddeed-mcp-http
```

Then configure your MCP client with:
```
URL: http://localhost:3000/mcp
Authorization: Bearer bd_live_xxx
```

Production endpoint: `https://biddeed.ai/api/mcp`

## Tools (25 total)

### S1 Discovery — $0.05/call (free tier)
| Tool | Description |
|------|-------------|
| `search_auctions` | FL foreclosure + tax deed auction calendar |
| `get_auction_detail` | Full detail by case number |
| `browse_deals` | Pre-scored deals ranked by Shapira discount |
| `get_deposit_requirements` | Exact deposit: max($200, 5% × opening_bid) |
| `find_local_partners` | Title companies, attorneys, contractors |
| `get_interest_rate` | FRED mortgage rates |
| `search_properties` | FL property search by address/parcel |

### S2 Qualification — $0.40/call (Investor tier)
| Tool | Description |
|------|-------------|
| `search_distressed` | Lis pendens, tax delinquent, pre-foreclosure |
| `get_owner_intel` | Owner name, defendant, entity type |
| `get_lien_stack` | FL lien survival rules (FS 197/45) |
| `get_rent_estimate` | HUD FMR + co-living per-room uplift |
| `analyze_market` | County auction volume, avg bid, distress rate |
| `get_zip_market_data` | Zip-level rents + auction overlay |
| `get_property_detail` | Folio, DOR code, BCPAO data, zoning |

### S3 Fusion — $5.00/call (Pro tier)
| Tool | Description |
|------|-------------|
| `check_zoning` | ZoneWise 771K+ FL parcels — zone, FAR, setbacks |
| `underwrite_deal` | Shapira Formula: ARV×70%−Repairs−$10K−MIN($25K,15%×ARV) |
| `analyze_coliving` | Config C 14-suite model, OSTDS flag, uplift |
| `get_sales_comps` | Arm-length vs distressed split, ARV |
| `generate_deal_memo` | 1-page markdown: auction+underwriting+zoning+liens |
| `get_bid_package` | RealForeclose link + deposit + max bid + lien summary |
| `get_title_chain` | O&E chain + title company referral |
| `get_market_data` | National rates + FL auction overlay |
| `skip_trace` | REISkip/BatchData $0.07–$0.15 (vs Investra $0.98) |

### S4 Monitoring — subscription (Pro tier)
| Tool | Description |
|------|-------------|
| `watch_auction` | 24hr + morning-of + postpone/cancel alerts |

### S5 Shapira Formula — $25.00/call (Pro tier + CERT required)
| Tool | Description |
|------|-------------|
| `predict_auction_outcome` | XGBoost+LGBM+CatBoost→RF, 82.6% accuracy on Gold Standard counties |

## Investra Parity

BidDeed matches all 17 Investra tools plus 8 exclusives:
- **predict_auction_outcome** — 82.6% accuracy ML ensemble (Investra has no equivalent)
- **get_bid_package** — Complete package: links + deposit + max bid + lien + zoning
- **get_deposit_requirements** — FL-specific formula, clerk links
- **get_lien_stack** — FL FS 197/45 lien survival rules
- **get_title_chain** — O&E chain from BidDeed outcomes DB
- **analyze_coliving** — Config C 14-suite model with OSTDS flag
- **check_zoning** — 771K+ FL parcels via ZoneWise
- **generate_deal_memo** — Integrated 1-page deal brief

## Revenue Streams

| Stream | Price | Gate | Tools |
|--------|-------|------|-------|
| S1 Discovery | $0.05/call | Free | 7 tools |
| S2 Qualification | $0.40/call | Investor | 7 tools |
| S3 Fusion | $5.00/call | Pro | 9 tools |
| S4 Monitoring | subscription | Pro | watch_auction |
| S5 Shapira | $25.00/call | Pro+CERT | predict_auction_outcome |

## Auth

API keys: `bd_live_xxx` (BidDeed) or `zw_live_xxx` (ZoneWise)

Tiers: free → investor → pro → proplus → enterprise

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BIDDEED_API_KEY` | stdio | API key for stdio mode |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `STRIPE_SECRET_KEY` | S5 only | For metered S5 billing |
| `REISKIP_API_KEY` | skip_trace | REISkip integration |
| `BATCHDATA_API_KEY` | skip_trace | BatchData fallback |
| `PORT` | HTTP mode | HTTP server port (default: 3000) |

## License

MIT — BidDeed.AI / Everest Capital USA
