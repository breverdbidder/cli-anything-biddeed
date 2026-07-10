# CLAUDE.md — Property Profile Enricher

> Harness: `cli-anything-biddeed/enricher/`
> Origin: Forked from NextAutomation Property Profile Enricher v1.0
> Owner: Ariel Shapira — BidDeed.AI + ZoneWise.AI

## What This Is

6-stage property due diligence pipeline for Brevard County, FL. Takes an address, parcel ID, or case number → returns enriched profile with actionable BID/REVIEW/SKIP/CONTACT recommendation.

Three modes: `foreclosure` (courthouse), `tax_deed` (realforeclose.com), `off_market` (ZoneWise.AI leads).

## Pipeline

```
OWNER → TAX → LIENS → PERMITS → COMPS → SYNTHESIZE
```

| Stage | Source | Status |
|-------|--------|--------|
| OWNER | BCPAO API + GIS | ✅ Working |
| TAX | BCPAO API | ✅ Basic (needs Tax Collector scraper) |
| LIENS | AcclaimWeb + RealTDM | ⚠️ Stubbed (needs BECA V2.0 regex) |
| PERMITS | Brevard PermitsPlus | ⚠️ Stubbed (needs endpoint discovery) |
| COMPS | BCPAO GIS spatial | ⚠️ Stubbed (needs STRtree impl) |
| SYNTHESIZE | All stages | ✅ Working (max bid + motivation) |

## Key Files

- `agent.py` — Main pipeline, all 6 stages, CLI entry point
- `eval/eval.json` — 25 binary assertions for AUTOLOOP
- `SKILL.md` — Docs and integration map
- `ORIGIN.md` — Original NextAutomation spec (reference only)

## Data Sources

| Source | URL | Auth |
|--------|-----|------|
| BCPAO API | `https://www.bcpao.us/api/v1` | None (public) |
| BCPAO GIS | `https://gis.brevardfl.gov/gissrv/rest/services` | None (public) |
| AcclaimWeb | `https://vaclmweb1.brevardclerk.us` | None (public, rate-limited) |
| RealTDM | `https://brevard.realtdm.com` | None (public) |
| Tax Collector | `https://brevardtc.com` | None (public) |
| PermitsPlus | `https://bfrhost.brevardfl.gov/PermitsPlus` | TBD — needs discovery |
| Supabase | `$SUPABASE_URL` | `$SUPABASE_KEY` |

## Secrets (from GHA / env)

```
SUPABASE_URL          — mocerqjnksmhcjzxrewo.supabase.co
SUPABASE_KEY          — Service role key
TELEGRAM_BOT_TOKEN    — Notifications
TELEGRAM_CHAT_ID      — Notifications
```

## Max Bid Formula

```
max_bid = (ARV × 0.70) - repairs - $10,000 - MIN($25,000, ARV × 0.15)
```

Thresholds (bid ÷ judgment):
- **≥75%** → BID
- **60-74%** → REVIEW
- **<60%** → SKIP

## Supabase Table: `property_profiles`

```sql
CREATE TABLE IF NOT EXISTS property_profiles (
  id BIGSERIAL PRIMARY KEY,
  parcel_id TEXT UNIQUE NOT NULL,
  owner_name TEXT,
  owner_type TEXT,          -- individual | entity | trust | government
  assessed_value BIGINT,
  market_value BIGINT,
  delinquent BOOLEAN DEFAULT FALSE,
  sale_type TEXT,            -- foreclosure | tax_deed | off_market
  action TEXT,               -- BID | REVIEW | SKIP | CONTACT | MONITOR
  max_bid BIGINT,
  motivation_score INT,
  confidence FLOAT,
  enriched_at TIMESTAMPTZ,
  raw_json JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pp_action ON property_profiles(action);
CREATE INDEX idx_pp_sale_type ON property_profiles(sale_type);
CREATE INDEX idx_pp_enriched ON property_profiles(enriched_at);
```

## Development Rules

1. **Read SKILL.md first** — it has the TODO list with priorities
2. **Read ORIGIN.md** — original spec has edge cases and best practices
3. **One stage at a time** — finish one stage completely before moving to next
4. **Test with real parcels** — use known Brevard parcels, never mock data
5. **BECA V2.0 patterns** — reuse existing regex from `src/scrapers/beca_scraper.py` for liens
6. **Rate limit all scrapers** — 2s between requests minimum for AcclaimWeb
7. **Confidence scores** — every stage must set confidence 0.0-1.0
8. **Run eval after changes** — `python scripts/eval_runner.py --eval-file enricher/eval/eval.json --outputs-dir enricher/eval_outputs/`

## Session Priorities (Ordered)

### P0 — Wire up working data
1. AcclaimWeb lien search with BECA regex patterns → populate `liens` stage
2. RealTDM tax certificate lookup → populate `tax_certificates` in liens
3. Tax Collector delinquency scraper → populate `delinquent` + `delinquent_amount` in tax

### P1 — New capability
4. Discover Brevard PermitsPlus API/scraping path → implement permits stage
5. BCPAO 3-year assessment history → implement `assessment_trend_3yr`

### P2 — Spatial comps
6. STRtree spatial join for comp radius (reuse `spatial/` patterns from zonewise)
7. BCPAO sales history cross-reference for $/sqft analysis

### P3 — Integration
8. ZoneWise zoning overlay → add zone_code + zone_desc to synthesis
9. DOCX report output (reuse `reports/` SKILL.md patterns)
10. Nightly batch GHA workflow with CSV input from Supabase

## CLI Quick Reference

```bash
# Enrich single property
python -m enricher.agent enrich --parcel "25-37-22-00-00123.0-0000.00" --mode foreclosure --judgment 150000 --depth deep --json

# Enrich by address
python -m enricher.agent enrich --address "123 Main St, Melbourne, FL 32901" --mode off_market --depth standard

# Batch from CSV
python -m enricher.agent batch --file parcels.csv --mode tax_deed --depth standard

# Status check
python -m enricher.agent status
```

## AUTOLOOP Integration

Eval: `enricher/eval/eval.json` (25 assertions, 5 tests)
Runner: `python scripts/eval_runner.py --eval-file enricher/eval/eval.json`
GHA: `autoloop.yml` with `--skill enricher`

## Context Hygiene

- 50% rule: kill and restart at ~50% context
- Never /compact
- Checkpoint between stages if context is growing
- One stage per session if scraper discovery is needed
