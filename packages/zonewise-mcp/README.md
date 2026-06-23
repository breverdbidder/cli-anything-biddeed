# zonewise-mcp

**ZoneWise MCP Server** — 771K+ FL parcel zoning data for Claude, Cursor, ChatGPT.

Instant zone code, FAR, setbacks, and permitted use lookup for any FL parcel.

## Quick Start

```json
{
  "mcpServers": {
    "zonewise": {
      "command": "npx",
      "args": ["-y", "zonewise-mcp"],
      "env": {
        "BIDDEED_API_KEY": "zw_live_...",
        "SUPABASE_URL": "https://mocerqjnksmhcjzxrewo.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "eyJ..."
      }
    }
  }
}
```

Get your ZoneWise key: https://zonewise.ai/api

## Tools (3)

| Tool | Description |
|------|-------------|
| `check_zoning` | Zone code, district, FAR, setbacks, max height, entitlement verdict |
| `get_zoning_districts` | All zones in a county with standards |
| `bulk_check_zoning` | Check up to 50 parcels in one call |

## Coverage

- 771K+ FL parcels across Brevard, Duval, Orange, and 40+ more counties
- Zone source: FL GIO + county GIS overrides + Municode ordinance extraction

## Auth

Keys start with `zw_live_` (Pro tier required — S3 tool).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BIDDEED_API_KEY` | Yes | ZoneWise API key (`zw_live_xxx`) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |

## License

MIT — BidDeed.AI / ZoneWise / Everest Capital USA
