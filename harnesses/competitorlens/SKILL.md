# CompetitorLens — DesignWise Agent #14

## Identity
- **Agent:** CompetitorLens (#14)
- **Squad:** DesignWise
- **Tier:** Lab → BrandGuard validates → Preview deploys
- **LLMs:** DeepSeek V3.2 (HTML parsing, $0.28/1M) + Sonnet 4.5 (analysis + JSX gen, free)
- **Cost target:** < $0.50 per competitor page analysis

## Purpose
Reverse-engineers competitor UX patterns (PropertyOnion, Foreclosure.com) and
rebuilds them as BidDeed.AI branded JSX components with live Supabase data binding.

## Pipeline (7 Stages)
```
CRAWL → EXTRACT → ANALYZE → GENERATE → VALIDATE → DIFF → DEPLOY
```

| Stage | Script | LLM | Output |
|-------|--------|-----|--------|
| 1. Crawl | crawl.py | — | Raw HTML + screenshot URL |
| 2. Extract | extract.py | DeepSeek V3.2 | ComponentBlueprint JSON |
| 3. Analyze | analyze.py | Sonnet 4.5 | UXPatternReport |
| 4. Generate | generate.py | Sonnet 4.5 | Branded .jsx component |
| 5. Validate | validate.py | BrandGuard #13 | PASS/BLOCK |
| 6. Diff | diff_report.py | — | CompetitorDiffReport.md |
| 7. Deploy | — | — | Vercel preview URL |

## Usage

```bash
# Crawl a competitor URL
python harnesses/competitorlens/crawl.py \
  --url "https://propertyonion.com/property_search/Brevard%20county?view_type=calendar" \
  --output /tmp/competitor_raw.json

# Extract layout blueprint
python harnesses/competitorlens/extract.py \
  --input /tmp/competitor_raw.json \
  --output /tmp/blueprint.json

# Full pipeline (Sprint 4+)
python harnesses/competitorlens/cli_anything.competitorlens.py \
  analyze "https://propertyonion.com/..." --component calendar
```

## Environment Variables
- `FIRECRAWL_API_KEY` — Firecrawl API key
- `DEEPSEEK_API_KEY` — DeepSeek API key (or use CLIProxyAPI)
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_KEY` — Supabase service role key (bypasses RLS)
- `CLIPROXY_URL` — CLIProxyAPI base URL (default: http://127.0.0.1:8317)

## ComponentBlueprint Schema
```json
{
  "url": "https://...",
  "competitor": "PropertyOnion",
  "component_type": "calendar",
  "sections": [
    {"name": "header", "type": "navigation", "elements": [...]}
  ],
  "navigation": {"type": "top-bar", "items": [...]},
  "filters": [{"name": "county", "type": "dropdown", "options": [...]}],
  "dataDisplayPatterns": ["calendar-grid", "property-cards"],
  "ctaPlacement": {"primary": "top-right", "secondary": "per-card"},
  "colorScheme": {"primary": "#...", "background": "#..."},
  "layoutType": "grid|list|map|calendar",
  "mobileApproach": "responsive|separate",
  "extractedAt": "2026-03-22T..."
}
```

## Supabase Tables
- `competitor_analyses` — Full analysis records per crawl
- `ux_pattern_library` — Reusable patterns extracted from analyses

## Target Competitors (Phase 1)
1. **PropertyOnion** — Auction calendar grid
   - URL: `propertyonion.com/property_search/{county}?view_type=calendar`
   - Output: `AuctionCalendar.jsx`
2. **Foreclosure.com** — Search/filter interface
   - URL: `foreclosure.com` (search UI)
   - Output: `PropertySearchGrid.jsx`

## Brand Rules (enforced by BrandGuard #13)
- Navy: `#1E3A5F`
- Orange: `#F59E0B`
- Background: `#020617` (slate-950)
- Font: Inter
- Framework: Tailwind CSS utility classes
