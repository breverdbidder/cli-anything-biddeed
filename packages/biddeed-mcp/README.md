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
| `skip_trace` | REISkip/BatchData $0.07–$0.15 (vs Investra $0.98) |

### S4 Monitoring — subscription (Pro tier)
| Tool | Description |
|------|-------------|
| `watch_auction` | 24hr + morning-of + postpone/cancel alerts |

### S5 Shapira Formula — $25.00/call (Pro tier + CERT required)
| Tool | Description |
|------|-------------|
| `predict_auction_outcome` | XGBoost+LGBM+CatBoost→RF, 82.6% accuracy on Gold Standard counties |

### S6 Market Data — $0.05/call (Free tier)
| Tool | Description |
|------|-------------|
| `get_interest_rate` | FRED 30yr/15yr fixed + 10yr Treasury — live rates |
| `get_market_data` | National rates + Case-Shiller HPI + FL auction overlay |

### S7 Property Intel — $0.25/call (Investor tier)
| Tool | Description |
|------|-------------|
| `search_properties` | FL property search by address/parcel/zip |
| `get_property_detail` | Folio, DOR use code, BCPAO data, zoning, auction history |

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
| S1 Discovery | $0.05/call | Free | 5 tools |
| S2 Qualification | $0.40/call | Investor | 6 tools |
| S3 Fusion | $5.00/call | Pro | 8 tools |
| S4 Monitoring | subscription | Pro | 1 tool |
| S5 Shapira | $25.00/call | Pro+CERT | 1 tool |
| S6 Market Data | $0.05/call | Free | 2 tools |
| S7 Property Intel | $0.25/call | Investor | 2 tools |

## Auth

Two parallel auth paths on HTTP mode — either works, pick one per request:

- API keys: `bd_live_xxx` (BidDeed) or `zw_live_xxx` (ZoneWise) — `Authorization: Bearer bd_live_xxx`
- OAuth: a WorkOS AuthKit access token — `Authorization: Bearer eyJ...` (JWT).
  biddeed-mcp is a resource server only — it verifies tokens WorkOS issued, it
  never issues tokens itself. Clients discover the authorization server via
  `GET /.well-known/oauth-protected-resource`. On first OAuth login, the
  WorkOS user is upserted into `mcp_customers` (`tier_id='free'`,
  `stripe_customer_id=NULL` until linked in Sprint 3).

Tiers: free → investor → pro → proplus → enterprise

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BIDDEED_API_KEY` | stdio | API key for stdio mode |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `STRIPE_SECRET_KEY` | S5 only | For metered S5 billing |
| `WORKOS_API_KEY` | OAuth only | WorkOS secret key — required to accept OAuth bearer tokens |
| `WORKOS_CLIENT_ID` | OAuth only | WorkOS AuthKit client ID — derives the JWKS endpoint |
| `MCP_PUBLIC_URL` | No | Canonical MCP URL for OAuth metadata (default: `https://biddeed.ai/api/mcp`) |
| `REISKIP_API_KEY` | skip_trace | REISkip integration |
| `BATCHDATA_API_KEY` | skip_trace | BatchData fallback |
| `PORT` | HTTP mode | HTTP server port (default: 3000) |

## License

MIT — BidDeed.AI / Everest Capital USA
