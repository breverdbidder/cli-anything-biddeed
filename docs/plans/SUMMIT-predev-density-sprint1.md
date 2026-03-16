# SUMMIT DISPATCH: Pre-Dev Squad — Sprint 1 (Density Agent)

**Dispatched:** 2026-03-16
**Priority:** P0
**Repo:** breverdbidder/cli-anything-biddeed
**Branch:** feature/predev-density-agent
**Spec Doc:** predev-squad-spec.docx (attached)
**Session Budget:** $10 max

---

## OBJECTIVE

Build `cli_anything.density` — a Density Study Agent that takes a parcel ID and returns what can be built by-right under current zoning. This is the first of 4 Pre-Dev Squad agents. It must work both as a standalone CLI tool AND as an injectable BidDeed pipeline Stage 13.

---

## MANDATORY: SESSION HYGIENE

1. Load CLAUDE.md from repo root first
2. Install plugins: Context7 (`/plugin→context7`) + CC Status Line (`npx cc-status-line@latest`)
3. Kill session at 50% context. NEVER `/compact`.
4. Load TODO.md, find current unchecked task, execute, mark `[x]`, push.

---

## WHAT TO BUILD

### 1. Fork Harness
- Fork from existing cli-anything harness (follow HARNESS.md 7-phase pipeline)
- Module: `cli_anything/density/`
- Entry: `cli_anything.density`
- Do NOT build from scratch

### 2. CLI Interface
```bash
npx cli_anything.density --parcel 2612345 --county brevard
npx cli_anything.density --address "123 Main St, Melbourne FL" --county brevard
```

### 3. Input/Output Contract

**Input:** `parcel_id` (BCPAO account#) OR `address` string + `county` (default: brevard)

**Output JSON:**
```json
{
  "parcel_id": "2612345",
  "county": "brevard",
  "municipality": "Melbourne",
  "zoning_code": "R-2",
  "zoning_description": "Residential Two-Family",
  "max_units": 2,
  "max_height_ft": 35,
  "max_lot_coverage_pct": 40,
  "far": 0.5,
  "setbacks": {
    "front_ft": 25,
    "rear_ft": 20,
    "side_ft": 7.5
  },
  "parking_required": 2,
  "allowed_uses": ["single_family", "duplex", "home_occupation"],
  "building_envelope_sqft": 4200,
  "density_per_acre": 8,
  "signal": "PASS",
  "signal_reason": "max_units >= 2, supports duplex development",
  "source_url": "https://library.municode.com/fl/melbourne/codes/code_of_ordinances?nodeId=...",
  "cached": false,
  "timestamp": "2026-03-16T14:30:00Z"
}
```

**Signal Logic:**
- `max_units < 2` OR `allowed_uses` excludes target → `SKIP` with reason
- `max_units >= target` → `PASS`, feeds into devpro agent
- Zoning = PUD or conditional use required → `REVIEW` with details

### 4. Data Pipeline (3 Steps)

**Step 1: Resolve Parcel → Zoning Code**
- FIRST: Check ZoneWise Supabase `zoning_results` table for parcel
- FALLBACK: Query BCPAO parcel API (SR2881) at `gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5`
- Extract: zoning_code, municipality, lot_size_sf, lot_dimensions

**Step 2: Zoning Code → LDC Text**
- Scrape municipality's Land Development Code via Firecrawl
- Brevard municipalities on Municode:
  - Brevard County (unincorporated): `municode.com/library/fl/brevard-county` → Ch. 62
  - Melbourne: `municode.com/library/fl/melbourne` → Ch. 30
  - Palm Bay: `municode.com/library/fl/palm-bay` → Ch. 185
  - Satellite Beach: `municode.com/library/fl/satellite-beach` → Ch. 102
  - Cocoa Beach: `municode.com/library/fl/cocoa-beach` → Ch. 7
  - Titusville: `municode.com/library/fl/titusville` → Ch. 28
- Cache raw LDC text in Supabase (TTL 90 days) to avoid re-scraping

**Step 3: LDC Text → Structured Density JSON**
- Gemini Flash (FREE via CLIProxy gateway at 87.99.129.125:8317) parses LDC text
- Prompt extracts: max_units, height, lot_coverage, FAR, setbacks, parking, allowed_uses
- Claude (via CLIProxy DeepSeek tier) validates edge cases: PUD overlays, special districts, conditional use
- Store result in Supabase `density_studies` table

### 5. Supabase Table

```sql
CREATE TABLE IF NOT EXISTS density_studies (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  parcel_id TEXT NOT NULL,
  county TEXT NOT NULL DEFAULT 'brevard',
  municipality TEXT,
  zoning_code TEXT NOT NULL,
  zoning_description TEXT,
  max_units INTEGER,
  max_height_ft NUMERIC,
  max_lot_coverage_pct NUMERIC,
  far NUMERIC,
  setbacks JSONB,
  parking_required INTEGER,
  allowed_uses TEXT[],
  building_envelope_sqft NUMERIC,
  density_per_acre NUMERIC,
  signal TEXT CHECK (signal IN ('PASS', 'REVIEW', 'SKIP')),
  signal_reason TEXT,
  source_url TEXT,
  raw_ldc_text TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '90 days'),
  UNIQUE(parcel_id, county)
);

-- RLS: service role full access, anon read-only
ALTER TABLE density_studies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_density" ON density_studies FOR SELECT TO anon USING (true);
CREATE POLICY "service_write_density" ON density_studies FOR ALL TO service_role USING (true);

-- Index for lookups
CREATE INDEX idx_density_parcel ON density_studies(parcel_id, county);
CREATE INDEX idx_density_expiry ON density_studies(expires_at);
```

### 6. LLM Routing (MANDATORY)
1. MAX Claude CLI (FREE) — for local dev/test
2. Gemini Flash via CLIProxy (FREE) — for LDC text parsing in production
3. DeepSeek V3.2 via CLIProxy — for edge case validation
4. NEVER paid Claude API tokens

### 7. Tests
- Must pass existing 176-test baseline (no regressions)
- Add new tests:
  - Test parcel resolution (BCPAO API mock)
  - Test LDC scraping for each municipality (cached fixtures)
  - Test Gemini extraction prompt against 5 known zoning districts
  - Test signal logic (PASS/REVIEW/SKIP thresholds)
  - Test Supabase CRUD + cache expiry
  - Test CLI argument parsing
  - Integration test: end-to-end on 3 real Brevard parcels
- Target: 20+ new tests, all green

### 8. Validation Parcels (Test Against These)
Run against these known parcels to validate accuracy:

| Parcel | Municipality | Expected Zoning | Expected Max Units |
|--------|-------------|----------------|-------------------|
| Pick 5 SFH-zoned parcels from BCPAO | Various | R-1/RS-x | 1 |
| Pick 5 MF-zoned parcels | Various | R-2/R-3/RM-x | 2-20+ |
| Pick 5 commercial-zoned parcels | Various | C-1/BU-x | Varies |
| Pick 3 PUD parcels | Various | PUD | REVIEW signal |
| Pick 2 parcels in target zips (32937, 32940) | Sat Beach, Melbourne | Various | Validate |

### 9. BidDeed Pipeline Hook
- Add optional Stage 13 entry point in pipeline config
- Trigger condition: `exit_strategy IN ('development', 'ADU', 'subdivision')`
- Output feeds into future Stage 14 (utilities) and Stage 16 (devpro)
- If Stage 13 returns SKIP, skip Stages 14-16 entirely

---

## WHAT NOT TO DO

- Do NOT rewrite existing cli-anything infrastructure
- Do NOT build agents 2-4 (utilities, permits, devpro) — Sprint 1 is density ONLY
- Do NOT use paid Claude API tokens
- Do NOT spend >$10
- Do NOT ask Ariel questions — solve autonomously, try 3 alternatives if blocked
- Do NOT build a UI — CLI only for now

---

## DEFINITION OF DONE

- [ ] `cli_anything.density` module exists in cli-anything-biddeed repo
- [ ] CLI invocation works with --parcel and --address flags
- [ ] Supabase density_studies table created with RLS
- [ ] Successfully processes parcels from 4+ Brevard municipalities
- [ ] All new tests pass + 176 baseline tests pass
- [ ] BidDeed Stage 13 hook wired (disabled by default, flag to enable)
- [ ] README updated with density agent docs
- [ ] Merged to main, GHA deploys automatically
- [ ] Health check reports density agent status in Sunday Telegram
