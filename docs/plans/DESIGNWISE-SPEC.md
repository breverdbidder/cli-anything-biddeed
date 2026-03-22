# DESIGNWISE-SPEC.md
# DesignWise Squad — Full Specification
# Version: 1.0.0 | Date: 2026-03-21
# Status: APPROVED by Product Owner
# Repo: breverdbidder/cli-anything-biddeed → designwise/

---

## 1. MISSION

Permanently manage the ZoneWise.AI UI lifecycle: design → code → test → deploy → monitor → improve → redesign. 13 AI agents operating as a self-improving team with zero human intervention for routine operations.

## 2. TEAM STRUCTURE

### Humans
- **Ariel Shapira** — Product Owner + PM. 20 min/day. Telegram commands + weekly review. Approves major pivots only.
- **Claude Sonnet** — AI Architect. BRAINSTORM protocol. DESIGN.md ownership. Squad performance review.

### 13 AI Agents

#### ORCHESTRATOR TIER (1 agent)

**Agent 01: DesignWise Commander** 🎖️
- CLI: `cli-anything-designwise commander`
- Role: LangGraph state machine. Receives all tasks, classifies, dispatches to correct agent, tracks completion.
- Triggers: Telegram /design, GHA cron, Watch dashboard, support tickets, agent-to-agent handoff
- State: Supabase `design_tasks` table
- Outputs: Agent dispatch, status updates to Telegram, weekly digest
- Tools: Supabase API, GitHub Actions dispatch, Telegram Bot API
- Priority: P0 Sprint 1

#### DESIGN TIER (2 agents)

**Agent 02: StitchWise** 🎨
- CLI: `cli-anything-designwise stitch`
- Role: Google Stitch 2.0 MCP wrapper. Generates high-fidelity UI designs from DESIGN.md context.
- Triggers: Commander dispatch, manual /stitch, DESIGN.md change
- Outputs: Screen HTML/CSS, screenshot PNG, design token validation report
- Tools: @_davideast/stitch-mcp (proxy), Stitch API (generate, get_screen_code, get_screen_image), brand validator
- MCP Config:
  ```json
  {
    "mcpServers": {
      "stitch": {
        "command": "npx",
        "args": ["@_davideast/stitch-mcp", "proxy"]
      }
    }
  }
  ```
- Deploys to: LAB tier only (lab.zonewise.ai)
- Priority: P0 Sprint 2

**Agent 03: BrandGuard** 🛡️
- CLI: `cli-anything-designwise brandguard`
- Role: Design system enforcer. Scans every PR and deploy for violations. BLOCKS deploys that fail.
- Triggers: Every PR (GHA check), every deploy (post-deploy hook), nightly full-site scan, manual /brandguard
- Checks:
  - Colors: All hex values against DESIGN.md palette. Flag any banned color.
  - Fonts: All font-family declarations. Flag anything not Inter or JetBrains Mono.
  - Contrast: All text/bg pairs against WCAG AA (4.5:1 body, 3:1 large).
  - Navigation: Consistent navbar on all pages. No orphan pages.
  - Links: All internal links resolve (no 404s).
  - Font size: Nothing below 11px.
  - Layout: Split-screen renders at 1280px, 768px, 375px viewports.
- Outputs: Brand compliance report (pass/fail with file:line), PR comment, Telegram alert on violations
- Tools: Playwright (DOM scan + screenshots), CSS parser, WCAG contrast checker, DESIGN.md token validator
- **CRITICAL: BrandGuard BLOCKS production deploys on ANY violation. Non-negotiable.**
- Priority: P0 Sprint 1

#### BUILD TIER (3 agents)

**Agent 04: CodeWise** ⚙️
- CLI: `cli-anything-designwise code`
- Role: Converts Stitch HTML → production Next.js/React components using shadcn/ui + Tailwind.
- Triggers: StitchWise output ready, manual code review request
- Rules:
  - All components use CSS variables from DESIGN.md (no hardcoded hex values)
  - All components are TypeScript (.tsx)
  - All components use shadcn/ui primitives where possible
  - ESLint + TypeScript checks must pass
  - Creates feature branch, never commits directly to main
- Outputs: Next.js components (.tsx), Tailwind config updates, PR on GitHub
- Tools: Claude Code session (Hetzner), GitHub API, ESLint, TypeScript compiler
- Priority: P0 Sprint 2

**Agent 05: DeployWise** 🚀
- CLI: `cli-anything-designwise deploy`
- Role: 3-tier deployment gatekeeper + rollback controller.
- Triggers: PR approved + checks pass, manual /deploy, hotfix escalation
- Pipeline:
  ```
  Feature branch → PR
    → BrandGuard check (MUST pass)
    → QAWise visual regression (MUST pass)
    → Vercel preview URL (auto-generated)
    → Smoke test (Playwright)
    → IF all pass → merge to main → auto-deploy to production
    → IF any fail → stays in lab, Telegram alert
    → Post-deploy: smoke test production
    → IF production smoke fails → auto-rollback to last good commit
  ```
- Outputs: Vercel preview URL, production deploy confirmation, rollback if smoke fails, deploy log
- Tools: Vercel CLI/API, GitHub Actions, Playwright smoke tests, Supabase deploy_log
- Priority: P1 Sprint 2

**Agent 06: QAWise** 🔍
- CLI: `cli-anything-designwise qa`
- Role: Visual regression + E2E testing.
- Triggers: Every PR, post-deploy smoke test, nightly regression suite
- Tests:
  - Visual: Capture screenshots at 1280px, 768px, 375px for every route. Diff against baseline (Pixelmatch, threshold 1%).
  - E2E flows: Landing → heatmap → parcel click → gate → signup → app → chat → map → calendar
  - Performance: Lighthouse CI (Performance ≥80, Accessibility ≥90, SEO ≥80)
- Outputs: Visual diff report, E2E results, Lighthouse scores, screenshot archive
- Tools: Playwright, Pixelmatch, Lighthouse CI, Supabase Storage
- Priority: P1 Sprint 3

#### INTELLIGENCE TIER (4 agents)

**Agent 07: AnalyticsWise** 📊
- CLI: `cli-anything-designwise analytics`
- Role: Customer behavior monitor using PostHog (self-hosted, privacy-first).
- Triggers: Daily 6AM EST aggregation, weekly Sunday digest, realtime conversion drop alert
- Tracks:
  - Page views per route (daily)
  - Conversion funnel: heatmap_view → parcel_click → gate_shown → signup → trial_start → paid
  - Feature adoption: chat usage, calendar views, report downloads, map interactions
  - Session duration, bounce rate by page
  - Heatmap click patterns (PostHog session recordings)
- Outputs: Daily metrics to Supabase, funnel report, feature scores, churn risk, improvement suggestions
- Tools: PostHog (self-hosted on Hetzner, free), Supabase page_analytics, conversion_funnel tables
- PostHog setup:
  ```bash
  # On Hetzner 87.99.129.125
  docker run -d --name posthog \
    -p 8100:8000 \
    -e SECRET_KEY=<generated> \
    -e DATABASE_URL=postgresql://... \
    posthog/posthog:latest
  ```
- Priority: P1 Sprint 3

**Agent 08: SupportWise** 💬
- CLI: `cli-anything-designwise support`
- Role: Auto-classify and respond to customer issues.
- Triggers: New support message (in-app widget), email to support@zonewise.ai
- Classification:
  - UI_BUG → Creates GitHub Issue → tags BrandGuard → auto-responds ETA
  - FEATURE_REQUEST → Logs to backlog → auto-responds acknowledgment
  - DATA_QUESTION → Routes to ZoneWise chat agent → auto-responds with data
  - BILLING → Escalates to Ariel via Telegram (HITL required)
  - GENERAL → Claude Sonnet auto-responds
- Outputs: Auto-response, GitHub Issue, backlog entry, escalation
- Tools: Supabase support_tickets, Claude Sonnet (classification + response), GitHub Issues API, Telegram
- Priority: P2 Sprint 4

**Agent 09: IterateWise** 🔄
- CLI: `cli-anything-designwise iterate`
- Role: Karpathy self-improvement loop for UI. A/B tests design variants automatically.
- Triggers: Weekly Monday 2AM cron, conversion drop below threshold, manual /iterate
- Loop:
  ```
  1. AnalyticsWise: "Page X conversion dropped Y%"
  2. IterateWise: Analyze → generate hypothesis
  3. IterateWise → StitchWise: "Generate 3 variants of Page X hero"
  4. BrandGuard: Validate all variants
  5. CodeWise: Implement as feature-flagged variants
  6. DeployWise: Deploy with traffic split (33/33/34)
  7. AnalyticsWise: Monitor 7 days → statistical significance
  8. IterateWise: Winner → default. Losers → archive.
  9. If new pattern → update DESIGN.md
  ```
- Tools: AnalyticsWise data, StitchWise, Vercel Edge Config (feature flags), stats calculator
- **All experiments deploy to LAB first. Only proven winners reach production.**
- Priority: P2 Sprint 4

#### SPECIALIST TIER (4 agents — NEW)

**Agent 10: SEOWise** 🔎
- CLI: `cli-anything-designwise seo`
- Role: Search engine optimization automation.
- Triggers: Every deploy, weekly audit, new page created
- Checks & Actions:
  - Meta tags: title (≤60 chars), description (≤160 chars), og:image, twitter:card on ALL pages
  - Sitemap: Auto-generate /sitemap.xml on every deploy. Submit to Google Search Console.
  - Structured data: Schema.org WebApplication, Organization, Product on relevant pages
  - robots.txt: Proper allow/disallow. No accidental noindex on production.
  - Internal linking: All pages reachable within 3 clicks from landing.
  - Page speed: Core Web Vitals via Lighthouse (LCP <2.5s, FID <100ms, CLS <0.1)
  - Index monitoring: Weekly check Google Search Console for deindexed pages
- Outputs: SEO audit report, auto-fix meta tags, sitemap generation, Search Console alerts
- Tools: Playwright (meta extraction), Google Search Console API, Lighthouse CI, sitemap-generator
- Priority: P1 Sprint 3

**Agent 11: AccessibilityWise** ♿
- CLI: `cli-anything-designwise a11y`
- Role: Dedicated WCAG 2.1 AA compliance + screen reader testing.
- Triggers: Every PR, weekly full audit, new component created
- Checks:
  - WCAG 2.1 AA: All 50 success criteria automated via axe-core
  - Screen reader: ARIA labels on all interactive elements, map controls, charts, modals
  - Keyboard: Tab order correct, focus visible, no keyboard traps
  - Color: Not relying on color alone for information (patterns/icons for BID/REVIEW/SKIP)
  - Motion: Prefers-reduced-motion respected. No auto-play without pause.
  - Forms: Labels, error messages, focus management on signup/login
  - Map: Alt text for static maps, keyboard-navigable interactive map controls
- Outputs: Accessibility score (target ≥90), violation list with WCAG criteria reference, auto-fix ARIA labels
- Tools: axe-core, Playwright (keyboard + focus testing), pa11y, Supabase a11y_audit table
- Priority: P1 Sprint 3

**Agent 12: CompetitorWise** 🕵️
- CLI: `cli-anything-designwise competitor`
- Role: Auto-monitor PropertyOnion, Reventure, Dono.ai, Gridics weekly.
- Triggers: Weekly Sunday 6AM cron, manual /competitor command
- Monitors:
  - Homepage changes (visual diff + DOM structure)
  - Pricing changes (scrape pricing pages)
  - New features (detect new routes/pages)
  - Technology stack changes (Wappalyzer headers)
  - SimilarWeb traffic estimates (monthly)
  - SEO position changes (target keywords)
- Competitors:
  - propertyonion.com (primary — 96 KPIs, $49-99/mo)
  - reventure.app (heatmap lead magnet, 30K premium users)
  - dono.ai (AI property analysis)
  - gridics.com / zoneomics.com (zoning data)
  - testfit.io (building envelope)
- Outputs: Weekly competitor digest to Telegram, change alerts, feature gap analysis, pricing intelligence
- Tools: Playwright (screenshots + DOM), Wappalyzer, SimilarWeb API, Supabase competitor_snapshots table
- Priority: P2 Sprint 4

**Agent 13: ContentWise** ✍️
- CLI: `cli-anything-designwise content`
- Role: Generate marketing content, landing page copy, blog posts, case studies.
- Triggers: Commander dispatch, manual /content, new feature launch
- Content types:
  - Landing page copy: Hero text, feature descriptions, CTAs (uses DESIGN.md tone guidelines)
  - Blog posts: Market analysis, feature announcements, investor guides
  - Case studies: "How [persona] saved $X using ZoneWise" — templated from real data patterns
  - Email sequences: Onboarding drip (Day 1, 3, 7, 14) for free → paid conversion
  - Social media: Twitter/LinkedIn posts for feature launches
- Rules:
  - All copy reviewed by BrandGuard for tone consistency
  - All claims backed by real data (Supabase queries, not invented)
  - NEVER mention competitors by name in public content
  - All blog posts SEO-optimized (SEOWise validates before publish)
- Outputs: Markdown content, HTML email templates, social media posts
- Tools: Claude Sonnet (generation), SEOWise (optimization), BrandGuard (tone check), Supabase (data for claims)
- Priority: P2 Sprint 4

---

## 3. THREE-TIER DEPLOYMENT ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  TIER 1: LAB                    TIER 2: PREVIEW         TIER 3: PROD│
│  lab.zonewise.ai                Vercel PR previews      zonewise.ai │
│                                                                     │
│  ┌─────────────────┐          ┌─────────────┐        ┌────────────┐│
│  │ StitchWise       │          │ BrandGuard   │        │ DeployWise ││
│  │ experiments here │──PR──►   │ validates    │──OK──► │ promotes   ││
│  │ IterateWise      │          │ QAWise diffs │        │ or BLOCKS  ││
│  │ variants here    │          │ A11y checks  │        │            ││
│  │                  │          │ SEO checks   │        │ Auto-      ││
│  │ CAN BE BROKEN    │          │              │        │ rollback   ││
│  │ No real users    │          │ MUST PASS    │        │ if smoke   ││
│  │                  │          │ ALL CHECKS   │        │ test fails ││
│  └─────────────────┘          └─────────────┘        └────────────┘│
│                                                                     │
│  Git branch: lab               Git: PR branches        Git: main   │
│  Vercel: branch deploy         Vercel: preview          Vercel: prod│
│  Domain: lab.zonewise.ai       Domain: auto-generated   zonewise.ai│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Rules:
1. **No agent writes directly to production. EVER.**
2. StitchWise and IterateWise deploy ONLY to lab branch.
3. CodeWise creates PRs from lab → main (never direct push).
4. BrandGuard + QAWise + AccessibilityWise + SEOWise run as required GitHub checks on every PR.
5. ALL four checks must pass before merge is allowed.
6. DeployWise auto-deploys main to production via Vercel.
7. Post-deploy smoke test runs within 60 seconds.
8. If smoke fails → auto-revert to previous commit → Telegram alert.

### Vercel Configuration:
```
Project: prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E (zonewise-web)
Production: zonewise.ai + www.zonewise.ai (main branch)
Lab: lab.zonewise.ai (lab branch, Vercel branch deploy)
Previews: Auto-generated per PR (existing Vercel behavior)
```

---

## 4. SUPABASE SCHEMA (10 tables)

### New Tables

```sql
-- Task registry for all squad operations
CREATE TABLE design_tasks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  task_type TEXT NOT NULL CHECK (task_type IN (
    'new_screen', 'fix_bug', 'brand_audit', 'visual_regression',
    'a_b_test', 'seo_audit', 'a11y_audit', 'competitor_scan',
    'content_generation', 'deploy', 'support_ticket'
  )),
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
    'queued', 'dispatched', 'running', 'success', 'failed', 'blocked'
  )),
  agent_id TEXT NOT NULL,
  input_spec JSONB,
  output_url TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

-- Brand compliance audit log
CREATE TABLE brand_violations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  scan_id UUID NOT NULL,
  page_url TEXT NOT NULL,
  violation_type TEXT NOT NULL CHECK (violation_type IN (
    'banned_color', 'wrong_font', 'contrast_fail', 'missing_nav',
    'broken_link', 'font_too_small', 'missing_alt', 'missing_aria'
  )),
  expected TEXT,
  actual TEXT,
  file_path TEXT,
  line_number INT,
  severity TEXT CHECK (severity IN ('critical', 'high', 'medium', 'low')),
  fixed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Screenshot baselines for visual regression
CREATE TABLE visual_baselines (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  route TEXT NOT NULL,
  viewport TEXT NOT NULL CHECK (viewport IN ('desktop', 'tablet', 'mobile')),
  screenshot_url TEXT NOT NULL,
  captured_at TIMESTAMPTZ DEFAULT NOW(),
  is_current BOOLEAN DEFAULT true
);

-- Daily page analytics (PostHog aggregation)
CREATE TABLE page_analytics (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  route TEXT NOT NULL,
  date DATE NOT NULL,
  views INT DEFAULT 0,
  unique_users INT DEFAULT 0,
  avg_time_sec NUMERIC(8,2),
  bounce_rate NUMERIC(5,4),
  cta_clicks INT DEFAULT 0,
  conversion_rate NUMERIC(5,4),
  UNIQUE(route, date)
);

-- Conversion funnel tracking
CREATE TABLE conversion_funnel (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  date DATE NOT NULL,
  step TEXT NOT NULL CHECK (step IN (
    'heatmap_view', 'parcel_click', 'gate_shown',
    'signup_start', 'signup_complete', 'trial_start', 'paid'
  )),
  count INT DEFAULT 0,
  drop_rate NUMERIC(5,4),
  UNIQUE(date, step)
);

-- Customer support tracking
CREATE TABLE support_tickets (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  channel TEXT NOT NULL CHECK (channel IN ('in_app', 'email', 'chat')),
  user_id UUID,
  message TEXT NOT NULL,
  classification TEXT CHECK (classification IN (
    'ui_bug', 'feature_request', 'data_question', 'billing', 'general'
  )),
  auto_response TEXT,
  github_issue_url TEXT,
  escalated_to TEXT,
  resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- A/B test tracking
CREATE TABLE ab_tests (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  test_name TEXT NOT NULL,
  page_route TEXT NOT NULL,
  variant_a JSONB NOT NULL,
  variant_b JSONB NOT NULL,
  variant_c JSONB,
  metric TEXT NOT NULL,
  traffic_split JSONB DEFAULT '{"a":34,"b":33,"c":33}',
  start_date DATE,
  end_date DATE,
  winner TEXT,
  significance NUMERIC(5,4),
  status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'running', 'complete', 'cancelled')),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Deployment audit trail
CREATE TABLE deploy_log (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  commit_sha TEXT NOT NULL,
  branch TEXT NOT NULL,
  vercel_deploy_id TEXT,
  tier TEXT NOT NULL CHECK (tier IN ('lab', 'preview', 'production')),
  status TEXT NOT NULL CHECK (status IN ('deploying', 'success', 'failed', 'rolled_back')),
  brand_check_passed BOOLEAN,
  qa_check_passed BOOLEAN,
  a11y_check_passed BOOLEAN,
  seo_check_passed BOOLEAN,
  smoke_test_passed BOOLEAN,
  lighthouse_scores JSONB,
  rolled_back BOOLEAN DEFAULT false,
  deployed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Competitor monitoring snapshots
CREATE TABLE competitor_snapshots (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  competitor TEXT NOT NULL CHECK (competitor IN (
    'propertyonion', 'reventure', 'dono', 'gridics', 'testfit'
  )),
  scan_date DATE NOT NULL,
  screenshot_url TEXT,
  dom_hash TEXT,
  pricing JSONB,
  new_routes TEXT[],
  tech_stack JSONB,
  traffic_estimate INT,
  changes_detected BOOLEAN DEFAULT false,
  UNIQUE(competitor, scan_date)
);

-- SEO monitoring
CREATE TABLE seo_audits (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  route TEXT NOT NULL,
  scan_date DATE NOT NULL,
  title TEXT,
  title_length INT,
  description TEXT,
  description_length INT,
  has_og_image BOOLEAN,
  has_structured_data BOOLEAN,
  lighthouse_seo_score INT,
  core_web_vitals JSONB,
  indexed_by_google BOOLEAN,
  UNIQUE(route, scan_date)
);
```

### RLS Policies
```sql
-- All tables: service_role has full access (agents use service key)
-- page_analytics, conversion_funnel: read-only for authenticated users (dashboard)
-- support_tickets: users can read/write their own tickets
-- Everything else: service_role only
```

---

## 5. EVAL FRAMEWORK

### designwise/eval.json — 25 Binary Assertions

```json
{
  "name": "designwise",
  "version": "1.0.0",
  "assertions": [
    {"id": 1,  "test": "All pages use #1E3A5F as primary navy",       "agent": "brandguard"},
    {"id": 2,  "test": "All pages use #F59E0B as accent orange",      "agent": "brandguard"},
    {"id": 3,  "test": "All pages use #020617 as background",         "agent": "brandguard"},
    {"id": 4,  "test": "Zero banned colors detected anywhere",        "agent": "brandguard"},
    {"id": 5,  "test": "All text uses Inter font family",             "agent": "brandguard"},
    {"id": 6,  "test": "No font size below 11px anywhere",            "agent": "brandguard"},
    {"id": 7,  "test": "All pages have consistent navbar",            "agent": "brandguard"},
    {"id": 8,  "test": "All pages have consistent footer",            "agent": "brandguard"},
    {"id": 9,  "test": "Zero 404 pages linked from any page",         "agent": "brandguard"},
    {"id": 10, "test": "All WCAG AA contrast ratios pass",            "agent": "a11y"},
    {"id": 11, "test": "/app split-screen renders correctly",         "agent": "qa"},
    {"id": 12, "test": "Chat panel sends and receives messages",      "agent": "qa"},
    {"id": 13, "test": "Map loads with choropleth heatmap",           "agent": "qa"},
    {"id": 14, "test": "Calendar shows auction events",               "agent": "qa"},
    {"id": 15, "test": "Conversion gate triggers after 5 clicks",     "agent": "qa"},
    {"id": 16, "test": "Signup flow completes end-to-end",            "agent": "qa"},
    {"id": 17, "test": "Mobile bottom sheet swipes correctly",        "agent": "qa"},
    {"id": 18, "test": "Demo page has play/pause controls",           "agent": "qa"},
    {"id": 19, "test": "KPI page loads all 298 KPIs",                 "agent": "qa"},
    {"id": 20, "test": "Pricing shows Free/$39/$99 tiers",            "agent": "qa"},
    {"id": 21, "test": "Lighthouse Performance ≥ 80",                 "agent": "seo"},
    {"id": 22, "test": "Lighthouse Accessibility ≥ 90",               "agent": "a11y"},
    {"id": 23, "test": "Visual regression diff < 1% vs baseline",     "agent": "qa"},
    {"id": 24, "test": "No console errors on any page",               "agent": "qa"},
    {"id": 25, "test": "All 67 county heatmap data loads",            "agent": "qa"}
  ]
}
```

### AutoLoop Integration
- GHA: `autoloop-designwise.yml` nightly 2AM EST
- Runner: `scripts/eval_runner.py` (same pattern as zonewise/auction/reports)
- L1 = activation (agent responds to command)
- L2 = binary output quality (25 assertions)
- Score improvement → git commit. Score regression → git reset. Max 50 iterations.

---

## 6. CLI HARNESS STRUCTURE

```
cli-anything-biddeed/
├── designwise/
│   ├── agent-harness/
│   │   ├── cli_anything/
│   │   │   └── designwise/
│   │   │       ├── __init__.py
│   │   │       ├── designwise_cli.py          # Main CLI entry point
│   │   │       ├── core/
│   │   │       │   ├── commander.py           # LangGraph orchestrator
│   │   │       │   ├── stitch_agent.py        # Stitch 2.0 MCP wrapper
│   │   │       │   ├── brandguard_agent.py    # Brand compliance scanner
│   │   │       │   ├── codewise_agent.py      # Stitch → Next.js converter
│   │   │       │   ├── deploywise_agent.py    # 3-tier deploy controller
│   │   │       │   ├── qawise_agent.py        # Visual regression + E2E
│   │   │       │   ├── analytics_agent.py     # PostHog + funnel tracking
│   │   │       │   ├── support_agent.py       # Ticket classifier + responder
│   │   │       │   ├── iterate_agent.py       # A/B test self-improvement
│   │   │       │   ├── seo_agent.py           # SEO automation
│   │   │       │   ├── a11y_agent.py          # WCAG compliance
│   │   │       │   ├── competitor_agent.py    # Competitor monitoring
│   │   │       │   └── content_agent.py       # Content generation
│   │   │       ├── utils/
│   │   │       │   ├── brand_tokens.py        # DESIGN.md parser
│   │   │       │   ├── stitch_mcp.py          # MCP client wrapper
│   │   │       │   ├── vercel_api.py          # Vercel deploy + preview
│   │   │       │   ├── posthog_client.py      # PostHog API client
│   │   │       │   └── supabase_client.py     # Shared Supabase helper
│   │   │       └── tests/
│   │   │           ├── test_brandguard.py      # Brand check unit tests
│   │   │           ├── test_deploy_pipeline.py # Deploy flow tests
│   │   │           ├── test_stitch_mcp.py      # MCP integration tests
│   │   │           └── test_commander.py       # Orchestrator tests
│   │   └── setup.py
│   ├── eval/
│   │   └── eval.json                           # 25 assertions
│   └── workflows/
│       ├── brandguard-pr-check.yml             # Runs on every PR
│       ├── qa-visual-regression.yml            # Runs on every PR
│       ├── deploy-lab.yml                      # Deploys lab branch
│       ├── deploy-production.yml               # Promotes main → prod
│       ├── nightly-audit.yml                   # Full site scan
│       ├── weekly-competitor.yml               # Sunday 6AM competitor scan
│       ├── weekly-seo.yml                      # SEO audit
│       └── autoloop-designwise.yml             # Nightly 2AM eval loop
```

---

## 7. GITHUB ACTIONS WORKFLOWS

### Required Checks on Every PR (lab → main)
1. `brandguard-pr-check` — Color, font, contrast, nav, links
2. `qa-visual-regression` — Screenshot diff vs baseline
3. `a11y-check` — axe-core scan
4. `seo-check` — Meta tags, structured data

ALL FOUR must pass. Branch protection enforces this.

### Cron Workflows
| Workflow | Schedule | Agent |
|----------|----------|-------|
| `nightly-audit.yml` | 2AM EST daily | BrandGuard full-site scan |
| `autoloop-designwise.yml` | 3AM EST daily | 25-assertion eval loop |
| `weekly-competitor.yml` | Sunday 6AM EST | CompetitorWise scan |
| `weekly-seo.yml` | Sunday 7AM EST | SEOWise audit |
| `daily-analytics.yml` | 6AM EST daily | AnalyticsWise aggregation |

---

## 8. COST ANALYSIS

| Item | Cost | Notes |
|------|------|-------|
| Stitch 2.0 | $0 | Free (Google Labs) |
| PostHog (self-hosted) | $0 | Docker on Hetzner (existing) |
| Claude Code (Max plan) | $0 | Already paid |
| Supabase (10 new tables) | $0 | Existing plan, well within limits |
| Vercel Pro (lab subdomain) | $0 | Branch deploys included |
| GitHub Actions | $0 | Free for public repos / within limits |
| Playwright | $0 | Open source |
| axe-core | $0 | Open source |
| **TOTAL** | **$0/month** | All on existing infrastructure |

---

*Specification approved 2026-03-21. Ready for PLAN phase.*
