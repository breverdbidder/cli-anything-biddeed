# DESIGNWISE-SPEC-PATCH.md
# Stitch 2.0 Gap Analysis — Spec Amendments
# Date: 2026-03-21 | Source: Google Stitch 2.0 (March 18, 2026)
# Applies to: DESIGNWISE-SPEC.md V1.0.0

---

## AMENDMENT 1: StitchWise Agent (Agent 02) — Replace §2 Definition

### Updated MCP Configuration
```json
{
  "mcpServers": {
    "stitch": {
      "command": "npx",
      "args": ["@google/stitch-sdk", "serve"]
    }
  }
}
```

**Replaces** the previous `@_davideast/stitch-mcp` proxy reference with the official Google SDK.

### Generation Strategy
- **Mode Selection:** Use Gemini 3.0 Flash for iteration/exploration (fast, low quota). Use Gemini 3.1 Pro for final production screens (higher quality).
- **Batch Generation:** Stitch 2.0 supports 5 screens per prompt. Batch our 8 screens into 2 calls (5+3) instead of 8 sequential calls.
- **Intent-Based Prompting:** Every screen generation starts with intent, not wireframe spec:
  - Landing hero: "A premium landing page that builds trust, communicates AI-powered intelligence, and makes visitors feel they're accessing institutional-grade data"
  - Split-screen app: "A clean, trustworthy workspace that feels like Bloomberg Terminal meets modern AI chat — professional enough for investors, intuitive enough for first-time users"
  - 67-county calendar: "An organized, data-rich calendar that feels comprehensive without overwhelming — like Google Calendar meets financial analytics"
  - 298-KPI report: "A detailed analytical report that feels authoritative and data-driven — like a professional appraisal document"
  - Pricing page: "A clear, confident pricing page that communicates value progression without pressure — transparent and fair"
  - Mobile layout: "A responsive mobile experience that maintains the premium desktop feel in a thumb-friendly, bottom-sheet navigation pattern"
  - Conversion gate: "A non-intrusive gate that creates urgency and value perception — 'you've seen the free version, here's what Pro unlocks'"
  - Demo page: "An impressive live demonstration that shows the AI pipeline in action — like watching a Bloomberg terminal populate in real-time"

### Project-Wide Context Threading
- Create ONE Stitch project: `zonewise-production`
- All 8 screens live in this project. Screen 5 generation sees Screens 1-4 as context.
- Stitch's Design Agent reasons across entire project evolution for visual consistency.
- This is PROACTIVE consistency (complements BrandGuard's REACTIVE enforcement).

### Quota Management
- **FREE tier:** 350 generations/month
- **Budget allocation:** 200 production (Pro mode) | 100 A/B variants (Flash mode) | 50 hotfixes
- **New Supabase table:**
```sql
CREATE TABLE stitch_usage (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  date DATE NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('flash', 'pro')),
  screen_name TEXT,
  generation_count INT DEFAULT 1,
  remaining INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(date, mode, screen_name)
);
```
- Commander checks quota before dispatch. Alert at 80% (280 used).

### Stitch Skills Library Integration
- Use pre-built skills from Stitch Skills Library (2.4K GitHub stars):
  - `design-system-docs` — auto-generate design system documentation
  - `react-component-conversion` — convert Stitch output to React components
- CodeWise delegates to Skills Library instead of custom HTML-to-React conversion logic.

---

## AMENDMENT 2: Interactive Prototype Generation — Add to StitchWise Responsibilities

### New Capability: Prototype Flow
After all 8 screens are generated, StitchWise creates an interactive prototype:

**Flow:** Landing hero → CTA click → Heatmap → Parcel click → Gate modal → Signup → App dashboard → Chat → Map drill-down

- Stitch auto-generates transitions and intermediate states between screens
- Export as interactive HTML to `lab.zonewise.ai/prototype`
- QAWise tests the prototype flow as part of E2E suite
- Serves as investor demo and beta user onboarding

---

## AMENDMENT 3: design.md URL Extraction Loop — Add to BrandGuard (Agent 03)

### Weekly Drift Detection
- **Cron:** Every Sunday 8AM EST (after competitor scan at 6AM, before SEO audit at 7AM — actually rename to 8AM to avoid overlap)
- **Process:**
  1. StitchWise extracts design tokens from live `zonewise.ai` via Stitch URL extraction
  2. BrandGuard diffs extracted tokens against `DESIGN.md` in repo
  3. If drift detected: GitHub Issue + Telegram alert
- **Why:** Catches CSS drift from dynamic generation, theme overrides, or third-party widget injection that PR-level BrandGuard checks might miss.

### New workflow: `weekly-designmd-drift.yml`
```yaml
name: Weekly DESIGN.md Drift Check
on:
  schedule:
    - cron: '0 13 * * 0'  # Sunday 8AM EST (13:00 UTC)
  workflow_dispatch:
```

---

## AMENDMENT 4: CodeWise (Agent 04) — Stitch MCP Direct Pipeline

### Updated Workflow
**Old:** StitchWise generates HTML → CodeWise converts HTML → Next.js
**New:** Claude Code connects to Stitch MCP → references Stitch project directly → generates production React

**Implementation:**
- Configure Stitch SDK MCP server in Claude Code CLAUDE.md
- CodeWise dispatches Claude Code session with: `DESIGN.md` + Stitch project `zonewise-production` reference
- Claude Code: "Implement the dashboard screen from our Stitch project as a Next.js page using shadcn/ui and our DESIGN.md tokens"
- Claude Code pulls design context through MCP — no HTML export/conversion step needed

### Fallback
If Stitch MCP is unavailable (Google Labs outage), fall back to HTML export → conversion pipeline (original spec).

---

## AMENDMENT 5: Commander (Agent 01) — Parallel Exploration Support

### Agent Manager Integration
- When exploring design directions (A/B test setup, new page design), Commander dispatches multiple StitchWise calls in parallel using Stitch's Agent Manager.
- Example: "Generate 3 hero variants" → single Stitch canvas session with 3 parallel explorations, not 3 sequential API calls.
- Reduces quota usage (1 session vs 3 sessions) and improves cross-variant consistency.

---

## AMENDMENT 6: Figma Archive — Optional P2 Addition

### StitchWise Figma Export Step
- After production screen approval, optionally export to Figma format
- Store Figma link in `design_tasks.figma_url` column
- Purpose: design portfolio for investor demos, designer onboarding
- **Priority: P2 Sprint 4. Do NOT block any pipeline on this.**

### Schema addition:
```sql
ALTER TABLE design_tasks ADD COLUMN figma_url TEXT;
```

---

## AMENDMENT 7: Supabase Schema Update — 1 New Table + 1 Column

### New table: `stitch_usage` (see Amendment 1)
### Altered table: `design_tasks` ADD `figma_url TEXT` (see Amendment 6)

---

## SUMMARY: Patches by Sprint

| Sprint | Patches |
|--------|---------|
| S1 | Quota management table + Commander quota check |
| S2 | Intent prompting, project-wide context, SDK + Skills, URL extraction loop, Stitch-to-Claude-Code direct, **MCP tool mapping (A10), stitchmcp fallback (A10), stitch:design skill (A10)** |
| S3 | Interactive prototyping, parallel explorations |
| S4 | Figma archive (optional) |

**Total new tables: 1** (stitch_usage)
**Total altered tables: 1** (design_tasks +1 column)
**Total new workflows: 1** (weekly-designmd-drift.yml)
**Cost impact: $0**

---

## AMENDMENT 10: MCP Tool Mapping + Community Wrapper + stitch:design Skill (2026-03-21)

Source: Gap analysis from YouTube transcript (Jkcy4SfGL00) — "Google Stitch 2.0 + Claude Code Pipeline"

### Gap 1: MCP Tool Name Mapping

The @google/stitch-sdk MCP server exposes exactly **3 canonical tools**:

| MCP Tool | Purpose | Used By |
|----------|---------|---------|
| `build_sitemaps` | Maps Stitch screens to routes, returns HTML per page | DeployWise, prototype assembly |
| `get_screen_code` | Retrieves HTML+CSS for a specific screen by name | CodeWise, primary generation |
| `get_screen_image` | Retrieves screenshot as base64 (Claude can SEE the design) | BrandGuard visual validation, QAWise baselines |

Internal action → MCP tool resolution:
```python
ACTION_TO_MCP_TOOL = {
    "generate_screen": "get_screen_code",
    "get_screenshot": "get_screen_image",
    "map_routes": "build_sitemaps",
    "generate_prototype": "build_sitemaps",
    "export_figma": "get_screen_code",
}
```

New StitchWise methods (direct MCP tool access):
- `agent.build_sitemaps(routes)` → calls `build_sitemaps` MCP tool
- `agent.get_screen_code(screen_name)` → calls `get_screen_code` MCP tool
- `agent.get_screen_image(screen_name)` → calls `get_screen_image` MCP tool

New CLI commands:
- `cli-anything-designwise stitch --get-code landing-hero --json`
- `cli-anything-designwise stitch --get-image landing-hero --json`
- `cli-anything-designwise stitch --build-sitemaps --json`

### Gap 2: npx stitchmcp Community Wrapper (Fallback)

Primary MCP config (unchanged): `npx @google/stitch-sdk serve`
Fallback MCP config (NEW): `npx stitchmcp`

If official SDK unavailable, StitchWise falls back to community CLI wrapper. Both expose same 3 tools.

```python
STITCH_MCP_FALLBACK_CONFIG = {
    "mcpServers": {
        "stitch": {
            "command": "npx",
            "args": ["stitchmcp"],
        }
    }
}
```

### Gap 3: stitch:design Skill Pre-Processor

Google published official Stitch Skills Library with 2 skills:

| Skill | Purpose | Integration |
|-------|---------|-------------|
| `stitch:design` | Prompt enhancement + screen generation pre-processor | Runs BEFORE custom intent prompts |
| `react:component` | Stitch screens → React component system with design token alignment | CodeWise delegates (already in spec) |

Pipeline: `Raw intent → stitch:design skill → enhanced prompt + DESIGN.md → get_screen_code MCP → HTML/CSS`

New method: `agent.enhance_prompt_with_skill(screen_name, raw_intent)`
New CLI flag: `--no-skill` to skip stitch:design pre-processor

---

*Patch approved 2026-03-21. Apply to DESIGNWISE-SPEC.md V1.2.0 and DESIGNWISE-PLAN.md V1.2.0.*
*Amendment 10 (Gap Closure) applied 2026-03-21.*

