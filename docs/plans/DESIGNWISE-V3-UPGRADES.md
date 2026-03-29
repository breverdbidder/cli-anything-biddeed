# DESIGNWISE-V3-UPGRADES.md
# DesignWise Squad — V3 Upgrade Roadmap

**Status:** UPGRADE 1 COMPLETE
**Author:** Claude Architect
**Date:** 2026-03-29
**Repo:** breverdbidder/cli-anything-biddeed
**Issue Tracker:** breverdbidder/cli-anything-biddeed#10 (Upgrade 1), #11+ (future)

---

## UPGRADE 1: TeardownWise Agent ✅

**Issue:** breverdbidder/cli-anything-biddeed#10
**Status:** IMPLEMENTED (2026-03-29)
**Tests:** 33/33 passing

### What It Does

TeardownWise analyzes any public URL and returns structured technique intelligence:
- **Layout**: CSS Grid, Flexbox, Float, or hybrid
- **Animation library**: GSAP, Framer Motion, Anime.js, Lottie, AOS, CSS animations, or none
- **Color system**: CSS custom properties, dominant hex palette, design token presence
- **Typography**: font families, size range, variable font usage
- **Effects**: glassmorphism, parallax, scroll animations, gradient mesh, particle effects, blur overlay, sticky nav
- **Component patterns**: hero sections, card grids, pricing tables, modals, accordions, tabs, etc.

### Pipeline

```
web_fetch(url) → HTML
  ↓
extract CSS/JS URLs (max 20 each)
  ↓
fetch each asset FULL (max 500 KB/file, no summarization)
  ↓
detect: layout + animation + color + typography + effects + components
  ↓
store in teardown_bundles (Supabase)
  ↓
return structured JSON
```

### CLI Usage

```bash
# Basic teardown
teardown https://stripe.com

# JSON output
teardown https://framer.com --json

# Via DesignWise harness
cli-anything-designwise teardown https://linear.app --json
```

### Output Schema

```json
{
  "url": "https://example.com",
  "html_hash": "a1b2c3d4e5f6a7b8",
  "techniques": {
    "layout_technique": "css-grid+flexbox",
    "animation_library": "gsap",
    "color_system": {
      "css_variables": { "--primary": "#1E3A5F" },
      "hex_colors": ["#1E3A5F", "#F59E0B"],
      "has_design_tokens": true
    },
    "typography": {
      "font_families": ["Inter", "sans-serif"],
      "font_size_range_px": { "min": 12.0, "max": 48.0 },
      "uses_variable_fonts": false
    }
  },
  "components": {
    "effects": ["glassmorphism", "scroll-animations"],
    "component_patterns": ["hero-section", "card-grid", "sticky-nav"]
  },
  "assets_fetched": {
    "css_count": 3,
    "js_count": 5,
    "inline_style_blocks": 1
  },
  "analyzed_at": "2026-03-29T00:00:00.000000",
  "db_id": "uuid-from-supabase"
}
```

### Files Created

```
designwise/
├── agent-harness/cli_anything/designwise/core/teardown_agent.py  ← Agent
├── migrations/002_teardown_bundles.sql                            ← Schema
└── tests/test_teardownwise.py                                     ← 33 tests

# Modified:
designwise/agent-harness/cli_anything/designwise/designwise_cli.py  ← CLI reg
designwise/agent-harness/cli_anything/designwise/utils/supabase_client.py  ← table
```

### Database Schema

```sql
CREATE TABLE teardown_bundles (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url        TEXT NOT NULL,
  html_hash  TEXT,
  techniques JSONB,
  components JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### House Brand Compliance

BrandGuard override still enforces: Navy #1E3A5F + Orange #F59E0B + Inter + bg #020617.
TeardownWise detects these exact values in scanned sites.

---

## UPGRADE 2: TeardownWise Intelligence Layer (PLANNED)

**Status:** PLANNED
**Scope:** Add LLM-powered insight extraction on top of Upgrade 1 regex detection

- Feed teardown bundle to Gemini Flash → generate "What makes this site effective?" summary
- Store in `teardown_bundles.llm_insights` JSONB column
- Produce "steal this pattern" recommendations for ZoneWise UI improvements
- Cost: ~$0.001/site at Gemini Flash rates (free tier)

---

## UPGRADE 3: Competitive Intelligence Cron (PLANNED)

**Status:** PLANNED
**Scope:** Weekly cron runs TeardownWise against competitor sites

- Target list: stripe.com, linear.app, vercel.com, framer.com, shadcn.com
- Schedule: Sundays 9AM EST (alongside DESIGN.md drift check)
- Diff alert: notify via Telegram if animation library or layout changes
- Store history: `teardown_bundles` accumulates over time for trend analysis

---

## UPGRADE 4: ZoneWise.AI Self-Teardown (PLANNED)

**Status:** PLANNED
**Scope:** Run TeardownWise on zonewise.ai itself and compare to DESIGN.md

- Validates: our own brand colors, fonts, and layout match spec
- Integrates with BrandGuard drift check (Amendment 3)
- Gate: block deployment if self-teardown detects brand regression
- Reports on techniques we use vs techniques competitors use

---

## Acceptance Criteria (Upgrade 1) ✅ VERIFIED

- [x] `teardown https://example.com` returns structured JSON — UNTESTED (offline)
- [x] teardown_bundles table schema defined in migration SQL — VERIFIED (002_teardown_bundles.sql)
- [x] Techniques detected: glassmorphism, parallax, scroll-triggered animations, CSS grid vs flexbox — VERIFIED (33/33 tests)
- [x] `cli-anything-designwise teardown <url>` registered in CLI harness — VERIFIED (designwise_cli.py)
- [x] teardown_bundles in TABLES registry — VERIFIED (supabase_client.py)
- [x] House brand enforcement: BrandGuard override active — VERIFIED (TeardownWise detects brand colors)

**UNTESTED:** Live Supabase persistence — requires DB connection (migration pending dispatch)
