# Property Profile Enricher — SKILL.md

> Forked from [NextAutomation Property Profile Enricher v1.0](01-property-profile-enricher.md)  
> Enhanced for **BidDeed.AI** (foreclosure + tax deed) and **ZoneWise.AI** (off-market + zoning overlay)

## What It Does

Single-pass property due diligence for Brevard County, FL. Takes an address, parcel ID, or case number and returns a complete enriched profile: owner, tax, liens, permits, comps, and an actionable recommendation (BID/REVIEW/SKIP/CONTACT).

## Three Sale Modes

| Mode | Channel | Key Question | Output |
|------|---------|-------------|--------|
| `foreclosure` | Courthouse auction (Titusville) | What liens survive? | Max bid + BID/REVIEW/SKIP |
| `tax_deed` | Online (brevard.realforeclose.com) | Clean title? Surplus? | Max bid + BID/REVIEW/SKIP |
| `off_market` | ZoneWise.AI pipeline | Owner motivation? | Motivation score + CONTACT/MONITOR |

## 6-Stage Pipeline

```
OWNER → TAX → LIENS → PERMITS → COMPS → SYNTHESIZE
```

| Stage | Source | What's New vs BidDeed V13 |
|-------|--------|--------------------------|
| OWNER | BCPAO API + GIS | Entity type classification, photo URL |
| TAX | BCPAO + Tax Collector | Delinquency amount, 3yr trend, exemption tracking |
| LIENS | AcclaimWeb + RealTDM | Same as BECA Scraper V2.0 patterns |
| PERMITS | **Brevard PermitsPlus** | **NEW** — building permits, code violations, CO status |
| COMPS | BCPAO GIS spatial query | Radius-based comp pull with $/sqft |
| SYNTHESIZE | All stages | Max bid formula + motivation score + red/green flags |

## What's NEW (Not in BidDeed V13)

1. **Permit History** — Detect unpermitted work, open permits (liability), recent renovations
2. **Off-Market Mode** — Motivation scoring (0-100) for ZoneWise.AI lead generation
3. **Tax Deed Support** — Separate analysis path for online tax deed auctions
4. **Batch Enrichment** — CSV input, rate-limited, Supabase persistence, Telegram notifications
5. **Confidence Scoring** — Per-stage and overall confidence (0.0-1.0)
6. **Red/Green Flags** — Automated flag detection across all stages

## CLI Usage

```bash
# Single property — foreclosure
python -m enricher.agent enrich --parcel "25-37-22-00-00123.0-0000.00" --mode foreclosure --judgment 150000

# Single property — tax deed
python -m enricher.agent enrich --address "123 Main St, Melbourne, FL 32901" --mode tax_deed --depth deep

# Single property — off-market (ZoneWise.AI)
python -m enricher.agent enrich --parcel "25-37-22-00-00456.0-0000.00" --mode off_market --depth deep

# Batch enrichment
python -m enricher.agent batch --file parcels.csv --mode foreclosure --depth standard

# Status check
python -m enricher.agent status
```

## Dependencies

- `httpx` — async HTTP client
- `shapely` — spatial queries (optional, for comp radius)
- BECA Scraper V2.0 regex patterns (for liens stage)
- Supabase credentials (for persistence)
- Telegram bot (for batch notifications)

## Integration Points

| System | Direction | Data |
|--------|-----------|------|
| BidDeed.AI auction pipeline | ← feeds into | Foreclosure + tax deed profiles |
| ZoneWise.AI scraper | ← receives from | Parcel lists with zoning data |
| ZoneWise.AI lead gen | → feeds into | Off-market motivation scores |
| Supabase `property_profiles` | ↔ persist | All enrichment results |
| AUTOLOOP eval | ← tested by | 25 binary assertions |

## TODO (Claude Code Sessions)

- [ ] Full AcclaimWeb HTML parsing with BECA V2.0 regex patterns
- [ ] RealTDM tax certificate integration
- [ ] Brevard PermitsPlus scraper (Tyler Technologies / Munis)
- [ ] Tax Collector delinquency scraper
- [ ] BCPAO 3-year assessment history for trend analysis
- [ ] Spatial comp query with Shapely STRtree
- [ ] ZoneWise.AI zoning overlay in synthesis stage
- [ ] DOCX report generation (reuse reports/ skill)
- [ ] GHA workflow for nightly batch enrichment
