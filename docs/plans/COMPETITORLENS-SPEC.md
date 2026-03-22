# COMPETITORLENS — DesignWise Agent #14

## Design Spec + Implementation Plan

**Version:** 1.0.0
**Author:** Claude AI Architect
**Date:** 2026-03-22
**Status:** READY FOR SUMMIT DISPATCH
**Squad:** DesignWise (3-tier: lab → preview → prod)

---

## 1. PROBLEM STATEMENT

BidDeed.AI competes against established platforms (PropertyOnion, Foreclosure.com, Auction.com) that have years of UI/UX iteration behind their interfaces. Rather than designing from scratch or guessing what works, CompetitorLens reverse-engineers proven competitor UX patterns and rebuilds them with BidDeed.AI house brand, our Supabase data layer, and ML intelligence baked in.

**Inspiration:** Matt Clark's "clone any webpage in 4 minutes" workflow (YouTube, Mar 20 2026) — but elevated from static HTML cloning to intelligent component generation with live data binding.

---

## 2. AGENT IDENTITY

| Field | Value |
|-------|-------|
| Agent Name | CompetitorLens |
| Agent Number | #14 |
| Squad | DesignWise |
| Tier | Lab (generates) → BrandGuard validates → Preview deploys |
| LLM | Sonnet 4.5 (layout analysis) + DeepSeek V3.2 (HTML parsing, cost: $0.28/1M) |
| Cost Target | < $0.50 per competitor page analysis |

---

## 3. ARCHITECTURE

### 3.1 Pipeline Flow

```
┌─────────────────────────────────────────────────────────┐
│                    COMPETITORLENS                         │
│                                                           │
│  INPUT                                                    │
│  ├── competitor_url (required)                            │
│  ├── target_component (optional: "calendar", "search")   │
│  └── data_source (optional: supabase table/view)         │
│                                                           │
│  STAGE 1: CRAWL                                          │
│  ├── Firecrawl scrape → raw HTML + screenshots           │
│  ├── DeepSeek V3.2 → extract layout skeleton (JSON)     │
│  └── Output: ComponentBlueprint                          │
│                                                           │
│  STAGE 2: ANALYZE                                        │
│  ├── Sonnet 4.5 → identify UX patterns                  │
│  │   ├── Navigation flow                                 │
│  │   ├── Filter/search mechanics                         │
│  │   ├── Data display patterns (cards, tables, calendar) │
│  │   ├── CTA placement & copy                            │
│  │   └── Mobile responsiveness approach                  │
│  └── Output: UXPatternReport                             │
│                                                           │
│  STAGE 3: GENERATE                                       │
│  ├── Sonnet 4.5 → BidDeed.AI branded JSX component     │
│  │   ├── House brand: Navy #1E3A5F + Orange #F59E0B     │
│  │   ├── Font: Inter                                     │
│  │   ├── bg: #020617 slate-950                           │
│  │   └── Tailwind utility classes                        │
│  ├── Data binding: Supabase hooks (real queries)         │
│  └── Output: BrandedComponent (.jsx)                     │
│                                                           │
│  STAGE 4: VALIDATE                                       │
│  ├── BrandGuard agent (#13) → PASS/BLOCK                │
│  │   ├── Color compliance check                          │
│  │   ├── Font compliance check                           │
│  │   └── Accessibility baseline (contrast ratios)        │
│  └── Output: ValidationResult                            │
│                                                           │
│  STAGE 5: DIFF REPORT                                    │
│  ├── Side-by-side comparison (competitor vs ours)        │
│  ├── UX improvements we added (ML scores, zoning, etc)  │
│  └── Output: CompetitorDiffReport (.md)                  │
│                                                           │
│  OUTPUT                                                   │
│  ├── /components/competitor-lens/{name}.jsx              │
│  ├── /reports/competitor-diff-{name}.md                  │
│  └── Preview URL → Vercel preview deployment             │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Data Model

```typescript
// Supabase table: competitor_analyses
interface CompetitorAnalysis {
  id: uuid;
  competitor_name: string;          // "PropertyOnion" | "Foreclosure.com"
  source_url: string;               // Original URL crawled
  component_type: string;           // "calendar" | "search" | "listing" | "map"
  layout_skeleton: jsonb;           // Extracted layout structure
  ux_patterns: jsonb;               // Identified patterns
  generated_component_path: string; // Path to .jsx output
  brand_guard_status: string;       // "PASS" | "BLOCK" | "PENDING"
  brand_guard_violations: jsonb;    // Array of violations if BLOCK
  diff_report_path: string;         // Path to diff report
  created_at: timestamptz;
  updated_at: timestamptz;
}

// Supabase table: ux_pattern_library
interface UXPattern {
  id: uuid;
  pattern_name: string;             // "auction-calendar-grid"
  source_competitor: string;        // Where we first saw it
  description: text;
  implementation_notes: text;
  reuse_count: integer;             // How many times we've adapted it
  created_at: timestamptz;
}
```

### 3.3 Integration Points

| System | Integration |
|--------|-------------|
| Firecrawl | Crawl competitor pages (existing key, $0 incremental for light usage) |
| DeepSeek V3.2 | HTML parsing + layout extraction ($0.28/1M — ULTRA_CHEAP) |
| Sonnet 4.5 | UX analysis + JSX generation (free on Max plan) |
| BrandGuard (#13) | Validates output against house brand rules |
| Stitch 2.0 | Polish pass if needed (@google/stitch-sdk) |
| Supabase | Store analyses + serve data to generated components |
| Vercel | Preview deployment of generated components |

---

## 4. TARGET COMPETITORS — PHASE 1

### 4.1 PropertyOnion — Auction Calendar

**URL:** `propertyonion.com/property_search/{county}?view_type=calendar`

**What they do well:**
- Calendar grid showing auction dates with property counts per day
- County-level filtering across all 67 FL counties
- Toggle between calendar view and list view
- Color-coded sale types (foreclosure vs tax deed)
- Daily updated listings with property details on click

**What BidDeed.AI adds:**
- ML probability scores (BidDeed ML) overlaid on calendar entries
- BID/REVIEW/SKIP color coding per property
- ZoneWise zoning data integrated per parcel
- Lien priority warnings (HOA foreclosure = senior mortgage survives)
- One-click deep-dive to full property report

**Component output:** `AuctionCalendar.jsx`

### 4.2 Foreclosure.com — Search Interface

**URL:** `foreclosure.com` (search/filter UI)

**What they do well:**
- Multi-filter search: location, property type, price, foreclosure stage
- Interactive map with geographic clustering
- Property cards with photos, price, beds/baths, status badges
- Save/track/export functionality
- Email alert subscriptions per search criteria

**What BidDeed.AI adds:**
- ML-powered "Deal Score" replacing simple listing display
- Max bid calculation shown per property (ARV formula)
- Demographic overlay from ZoneWise (income, vacancy rates)
- Lien discovery status indicator (clean/risky/unknown)
- Direct link to county auction platform (RealForeclose)

**Component output:** `PropertySearchGrid.jsx`

---

## 5. IMPLEMENTATION PLAN

### Sprint 1: Foundation (Days 1-2)

**Goal:** Crawl infrastructure + layout extraction pipeline

| Task | Details | Harness |
|------|---------|---------|
| S1.1 | Create `cli-anything-biddeed/harnesses/competitorlens/` following HARNESS.md 7-phase pipeline | Fork from zonewise harness |
| S1.2 | Firecrawl integration: scrape URL → HTML + screenshot | Existing Firecrawl key |
| S1.3 | DeepSeek V3.2 layout extractor: HTML → ComponentBlueprint JSON | CLIProxyAPI on 127.0.0.1:8317 |
| S1.4 | Supabase tables: `competitor_analyses` + `ux_pattern_library` + RLS | Standard RLS policies |
| S1.5 | Unit tests: 5 assertions per stage (crawl, extract) | eval.json format |

**Exit criteria:** Can crawl PropertyOnion calendar URL and produce valid ComponentBlueprint JSON.

### Sprint 2: Analysis + Generation (Days 3-5)

**Goal:** UX pattern analysis + branded JSX generation

| Task | Details | LLM |
|------|---------|-----|
| S2.1 | UX Pattern Analyzer: ComponentBlueprint → UXPatternReport | Sonnet 4.5 |
| S2.2 | JSX Generator: UXPatternReport + house brand rules → .jsx | Sonnet 4.5 |
| S2.3 | Data binding layer: Supabase hooks for auction data | N/A (code) |
| S2.4 | BrandGuard integration: submit generated JSX for validation | Agent #13 API |
| S2.5 | PropertyOnion calendar → `AuctionCalendar.jsx` (first real output) | Full pipeline |
| S2.6 | Unit tests: 10 assertions (pattern detection, brand compliance) | eval.json |

**Exit criteria:** Generated AuctionCalendar.jsx passes BrandGuard, renders with mock data.

### Sprint 3: Second Target + Diff Reports (Days 6-8)

**Goal:** Foreclosure.com search UI + comparison reporting

| Task | Details |
|------|---------|
| S3.1 | Crawl Foreclosure.com search interface |
| S3.2 | Generate `PropertySearchGrid.jsx` with BidDeed.AI data binding |
| S3.3 | Diff Report generator: side-by-side competitor vs BidDeed.AI |
| S3.4 | UX Pattern Library: extract reusable patterns to `ux_pattern_library` table |
| S3.5 | Preview deployment: both components to Vercel preview |
| S3.6 | Integration tests: 15 assertions across full pipeline |

**Exit criteria:** Both components deployed to preview, diff reports generated.

### Sprint 4: Production Polish (Days 9-10)

**Goal:** CLI integration, AUTOLOOP eval, documentation

| Task | Details |
|------|---------|
| S4.1 | CLI command: `competitorlens analyze <url> [--component <type>]` |
| S4.2 | AUTOLOOP eval: `competitorlens/eval/eval.json` (25 binary assertions) |
| S4.3 | GHA workflow: `competitorlens-analyze.yml` (manual dispatch) |
| S4.4 | SKILL.md for CompetitorLens harness |
| S4.5 | Update DESIGNWISE-SQUAD spec: add Agent #14 |
| S4.6 | Session summary + handoff doc |

**Exit criteria:** CLI operational, AUTOLOOP passing, GHA workflow deployable.

---

## 6. COST ANALYSIS

| Resource | Per-Analysis Cost | Monthly (est. 20 analyses) |
|----------|-------------------|---------------------------|
| Firecrawl | $0.00 (within existing quota) | $0.00 |
| DeepSeek V3.2 (parsing) | ~$0.05 | $1.00 |
| Sonnet 4.5 (analysis + gen) | $0.00 (Max plan) | $0.00 |
| Supabase storage | $0.00 (within existing plan) | $0.00 |
| Vercel preview deploys | $0.00 (Pro plan) | $0.00 |
| **Total** | **~$0.05** | **~$1.00** |

Well within $10/session cost discipline.

---

## 7. SUCCESS METRICS

| Metric | Target |
|--------|--------|
| Crawl-to-component time | < 5 minutes |
| BrandGuard pass rate | > 90% first attempt |
| UX pattern reuse | 3+ patterns extracted per competitor |
| Generated component renders | 100% (no broken JSX) |
| Data binding functional | Live Supabase queries working |

---

## 8. RISK REGISTER

| Risk | Mitigation |
|------|------------|
| Anti-scraping blocks on competitor sites | Firecrawl handles JS rendering + rotation; fallback to cached screenshots |
| Generated JSX too complex for BrandGuard | Limit component scope to single-purpose sections, not full pages |
| Layout extraction misses interactive elements | Screenshot comparison as validation step |
| Competitor redesigns break analysis | Store ComponentBlueprint as snapshot; re-crawl on demand |

---

## 9. FILE STRUCTURE

```
cli-anything-biddeed/
├── harnesses/
│   └── competitorlens/
│       ├── SKILL.md
│       ├── cli_anything.competitorlens.py    # Main CLI
│       ├── crawl.py                          # Firecrawl integration
│       ├── extract.py                        # DeepSeek layout extraction
│       ├── analyze.py                        # Sonnet UX pattern analysis
│       ├── generate.py                       # JSX generation + brand rules
│       ├── validate.py                       # BrandGuard submission
│       ├── diff_report.py                    # Competitor vs BidDeed comparison
│       └── eval/
│           └── eval.json                     # 25 binary assertions
│
biddeed-ai-ui/
├── src/components/competitor-lens/
│   ├── AuctionCalendar.jsx                   # From PropertyOnion
│   └── PropertySearchGrid.jsx                # From Foreclosure.com
│
docs/plans/
├── COMPETITORLENS-SPEC.md                    # This file
└── COMPETITORLENS-PLAN.md                    # Sprint breakdown (this file includes both)
```

---

## 10. SUMMIT DISPATCH INSTRUCTIONS

```bash
# From Ariel's machine or GHA workflow:
claude remote-control  # or /rc from mobile

# Summit dispatch command:
cd ~/repos/cli-anything-biddeed
git checkout -b feature/competitorlens-agent
# Claude Code reads this spec from docs/plans/COMPETITORLENS-SPEC.md
# Executes Sprint 1 → Sprint 4 autonomously
# Commits after each sprint
# Deploys preview after Sprint 3
```

**Claude Code directive:** Execute this spec end-to-end. Start with Sprint 1. Commit after each sprint with message `feat(competitorlens): S{N} - {description}`. Push to feature branch. Deploy preview after Sprint 3. Report blockers only after 3 retry attempts.

---

## 11. NEVER-LIE COMPLIANCE

- All cost figures are from verified rate cards (DeepSeek $0.28/1M documented)
- Firecrawl quota verified against existing account
- No invented metrics or success claims
- Components must render with real Supabase data before marking DONE
- BrandGuard validation must be actual API call, not assumed pass

---

*Spec authored by Claude AI Architect. Ready for Summit dispatch.*
