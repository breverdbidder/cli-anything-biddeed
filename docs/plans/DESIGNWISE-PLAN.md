# DESIGNWISE-PLAN.md
# DesignWise Squad — Implementation Plan (Claude Code Handoff)
# Date: 2026-03-21 | Sprints: 4 weeks | Version: 1.1.0
# Repo: breverdbidder/cli-anything-biddeed
# Target: breverdbidder/zonewise-web + breverdbidder/cli-anything-biddeed
# Patch: Stitch 2.0 amendments applied 2026-03-21 (DESIGNWISE-SPEC-PATCH.md)

---

## PRE-FLIGHT (Ariel HITL — ONE TIME ONLY)

These are the ONLY manual steps. Everything after is Zero-HITL.

- [ ] Create Google Cloud project for Stitch 2.0
- [ ] Run: `gcloud auth login && gcloud config set project <PROJECT_ID>`
- [ ] Run: `gcloud beta services mcp enable stitch.googleapis.com`
- [ ] Run: `gcloud auth application-default login`
- [ ] Add `lab.zonewise.ai` subdomain in Vercel project settings (branch: lab)
- [ ] Enable branch protection on zonewise-web main: require 4 status checks

---

## SPRINT 1 — FOUNDATION (Week 1)

### S1.1 — Scaffold designwise/ harness
- [ ] Fork from cli-anything-biddeed zonewise/ pattern
- [ ] Create directory structure per SPEC §6
- [ ] Create setup.py with entry point: `cli-anything-designwise`
- [ ] Create designwise_cli.py with 13 subcommands (stubs)
- [ ] Create shared utils: supabase_client.py, brand_tokens.py, vercel_api.py
- [ ] Write 15 unit tests (CLI invocation, JSON output, config loading)
- [ ] Push to cli-anything-biddeed/designwise/

### S1.2 — BrandGuard Agent (P0)
- [ ] Implement brandguard_agent.py
- [ ] Playwright scanner: crawl all routes, extract all CSS colors + fonts + font sizes
- [ ] DESIGN.md parser: load color tokens, font stack, banned colors list
- [ ] Comparator: flag violations with page_url, violation_type, expected, actual, file:line
- [ ] WCAG contrast checker: compute ratios for all text/bg pairs
- [ ] Link checker: crawl all internal links, flag 404s
- [ ] Nav checker: verify consistent navbar component across all routes
- [ ] CLI: `cli-anything-designwise brandguard --url https://zonewise.ai --json`
- [ ] Output: JSON report + Supabase brand_violations insert
- [ ] Write brandguard-pr-check.yml GitHub Action
- [ ] Write 20 unit tests (color validation, contrast calc, link check)
- [ ] Run against current zonewise.ai — capture baseline violations

### S1.3 — Commander Agent (P0)
- [ ] Implement commander.py as LangGraph state machine
- [ ] States: RECEIVE → CLASSIFY → DISPATCH → MONITOR → COMPLETE
- [ ] Task classification: new_screen, fix_bug, brand_audit, deploy, etc.
- [ ] Agent dispatch: route to correct agent based on classification
- [ ] Supabase: create design_tasks table + insert/update/query
- [ ] Telegram integration: /design command → Commander → dispatch
- [ ] CLI: `cli-anything-designwise commander --task "fix landing page hero"`
- [ ] Write 10 tests (classification, dispatch routing, state transitions)

### S1.4 — Supabase Schema
- [ ] Create all 10 tables per SPEC §4
- [ ] Create RLS policies
- [ ] Create pg_cron for cleanup (design_tasks, deploy_log: 90-day retention)
- [ ] Create views: active_violations, daily_funnel, deploy_history
- [ ] Verify with curl queries
- [x] **PATCH:** Run migration `supabase/migrations/20260321_designwise_stitch_patch.sql` (stitch_usage + figma_url column)

### S1.5 — Fix CRITICAL Bugs (existing site)
- [ ] Delete /public/demo.html (standalone file)
- [ ] Create /app/demo/page.tsx (Next.js route with shared layout)
- [ ] Port demo animation into Next.js component using brand colors only
- [ ] Fix /kpis page: ensure 298 KPIs load server-side (not client-only)
- [ ] Create /app/page.tsx as split-screen app shell (placeholder content)
- [ ] Fix /explorer: redirect to /app or create proper route
- [ ] Fix Terms/Privacy: "ZoneWise.AI 2026" → "ZoneWise.AI" (remove double year)
- [ ] Add consistent navbar to ALL pages via layout.tsx
- [ ] Add consistent footer to ALL pages
- [ ] Run BrandGuard → verify 0 violations

### S1.6 — Eval Framework
- [ ] Create designwise/eval/eval.json (25 assertions per SPEC §5)
- [ ] Create eval runner script (same pattern as zonewise/auction)
- [ ] Create autoloop-designwise.yml (nightly 2AM)
- [ ] Verify L1 activation on all 4 P0 agents

---

## SPRINT 2 — STITCH + BUILD (Week 2)

### S2.1 — StitchWise Agent (P0)
- [x] **PATCH:** Implement stitch_agent.py (Amendment 1 — @google/stitch-sdk MCP)
- [ ] Stitch MCP client wrapper (stitch_mcp.py)
- [x] **PATCH:** Load DESIGN.md as context for every Stitch generation
- [x] **PATCH:** Intent-based vibe prompts for all 8 screens (Amendment 1)
- [x] **PATCH:** Batch generation 5+3 via generate_all_screens() (Amendment 1)
- [x] **PATCH:** Flash/Pro mode selection (Amendment 1)
- [x] **PATCH:** Quota check before every generation (Amendment 1)
- [x] **PATCH:** generate_prototype() for interactive flow (Amendment 2)
- [x] **PATCH:** export_to_figma() optional method (Amendment 6)
- [ ] Generate 8 screens in order per DESIGN.md §Stitch Instructions:
  1. Landing page hero + heatmap section
  2. Split-screen app (chat left, map right)
  3. 67-county calendar view
  4. 298-KPI report panel
  5. Pricing page (Free / $39 / $99)
  6. Mobile layout with bottom sheet
  7. Conversion gate modal
  8. Demo page (agent pipeline + live report)
- [ ] Validate each screen against brand tokens before accepting
- [ ] Save screenshots to Supabase Storage
- [ ] CLI: `cli-anything-designwise stitch --screen "landing-hero" --json`
- [x] **PATCH:** 7 quota tests (test_stitch_quota.py)

### S2.2 — CodeWise Agent (P0)
- [ ] Implement codewise_agent.py
- [ ] Stitch HTML → Next.js converter:
  - Extract Tailwind classes → map to DESIGN.md CSS variables
  - Replace hardcoded colors → CSS variable references
  - Wrap in proper Next.js page component with TypeScript types
  - Add shadcn/ui components where applicable
- [ ] Git workflow: create feature branch → commit → create PR
- [ ] ESLint + TypeScript validation before PR creation
- [ ] CLI: `cli-anything-designwise code --input stitch-output.html --route /app`
- [ ] Write 10 tests (HTML parsing, color replacement, TS output)

### S2.3 — DeployWise Agent (P1)
- [ ] Implement deploywise_agent.py
- [ ] Lab deploy: push to `lab` branch → auto-deploys to lab.zonewise.ai
- [ ] Preview: create PR → Vercel auto-generates preview URL
- [ ] Gate: wait for BrandGuard + QAWise + A11y + SEO checks
- [ ] Promote: merge PR → auto-deploys to production
- [ ] Smoke test: Playwright hits 5 critical URLs within 60s of deploy
- [ ] Rollback: if smoke fails → `git revert HEAD` → force push → Telegram alert
- [ ] Supabase: insert deploy_log for every deploy
- [ ] CLI: `cli-anything-designwise deploy --tier lab|preview|production`
- [ ] Write 8 tests (deploy flow, gate logic, rollback)

### S2.4 — Implement Core Pages
- [ ] Landing page: hero + Reventure-style heatmap (full-width, always free)
- [ ] Split-screen app: chat left (380px) + map right (flex)
- [ ] Map: Mapbox choropleth with 67 counties, zoom-adaptive layers
- [ ] Chat: AI chat panel with message history + inline artifacts
- [ ] Conversion gate: modal after 5 free parcel clicks
- [ ] Configure lab.zonewise.ai Vercel branch deploy
- [ ] Deploy all new pages to lab first → BrandGuard pass → promote

---

## SPRINT 3 — QUALITY + INTELLIGENCE (Week 3)

### S3.1 — QAWise Agent (P1)
- [ ] Implement qawise_agent.py
- [ ] Visual regression: Playwright screenshots at 3 viewports × all routes
- [ ] Baseline capture: store current screenshots in Supabase visual_baselines
- [ ] Pixelmatch diff: compare PR screenshots vs baseline, threshold 1%
- [ ] E2E flows: landing → heatmap → click → gate → signup → app → chat → map
- [ ] Lighthouse CI: Performance ≥80, Accessibility ≥90, SEO ≥80
- [ ] CLI: `cli-anything-designwise qa --url lab.zonewise.ai --json`
- [ ] Create qa-visual-regression.yml GitHub Action
- [ ] Write 12 tests

### S3.2 — AnalyticsWise Agent (P1)
- [ ] Deploy PostHog on Hetzner (Docker container, port 8100)
- [ ] Add PostHog JS snippet to zonewise-web layout.tsx
- [ ] Implement analytics_agent.py
- [ ] Daily aggregation: PostHog → Supabase page_analytics
- [ ] Funnel tracking: custom events at each conversion step
- [ ] Weekly digest: top pages, worst bounce, funnel drop-offs → Telegram
- [ ] Conversion alert: if any step drops >15% vs 7-day avg → immediate Telegram
- [ ] CLI: `cli-anything-designwise analytics --report daily|weekly|funnel`
- [ ] Write 8 tests

### S3.3 — SEOWise Agent (P1)
- [ ] Implement seo_agent.py
- [ ] Meta tag scanner: title length, description, og:image, twitter:card
- [ ] Sitemap generator: auto-generate /sitemap.xml from Next.js routes
- [ ] Structured data: add Schema.org WebApplication + Organization
- [ ] Lighthouse SEO score check
- [ ] Core Web Vitals monitoring
- [ ] CLI: `cli-anything-designwise seo --url zonewise.ai --json`
- [ ] Create weekly-seo.yml cron workflow
- [ ] Write 10 tests

### S3.4 — AccessibilityWise Agent (P1)
- [ ] Implement a11y_agent.py
- [ ] axe-core integration: full WCAG 2.1 AA automated scan
- [ ] Keyboard navigation test: tab order, focus visible, no traps
- [ ] ARIA audit: all interactive elements, map controls, modals, charts
- [ ] Screen reader text: alt attributes, aria-labels, role attributes
- [ ] CLI: `cli-anything-designwise a11y --url zonewise.ai --json`
- [ ] Add as required GitHub check on PRs
- [ ] Write 10 tests

### S3.5 — Implement Remaining Pages
- [ ] 67-county calendar view (/app/calendar)
- [ ] 298-KPI report panel (/app/report/:id)
- [ ] Pricing page (/pricing) — Free / Starter $39 / Pro $99
- [ ] Mobile bottom sheet layout
- [ ] Signup flow (Supabase Auth)
- [ ] All pages pass BrandGuard before production deploy

---

## SPRINT 4 — SELF-IMPROVEMENT + LAUNCH (Week 4)

### S4.1 — SupportWise Agent (P2)
- [ ] Implement support_agent.py
- [ ] In-app widget: Supabase insert on submit
- [ ] Classification: Claude Sonnet categorizes (ui_bug, feature_request, data, billing, general)
- [ ] Auto-response: template responses per category
- [ ] GitHub Issue creation for ui_bug classification
- [ ] Telegram escalation for billing classification
- [ ] CLI: `cli-anything-designwise support --process-new`
- [ ] Write 8 tests

### S4.2 — IterateWise Agent (P2)
- [ ] Implement iterate_agent.py
- [ ] Hypothesis generator: analyze AnalyticsWise data → identify lowest performers
- [ ] Variant requester: dispatch StitchWise with variant specs
- [ ] A/B configuration: Vercel Edge Config feature flags
- [ ] Traffic splitter: 33/33/34 for 3 variants
- [ ] Significance calculator: chi-squared test, 95% confidence
- [ ] Winner promoter: winning variant → default, losers archived
- [ ] DESIGN.md updater: if pattern emerges, update tokens
- [ ] CLI: `cli-anything-designwise iterate --page / --metric conversion_rate`
- [ ] Write 10 tests

### S4.3 — CompetitorWise Agent (P2)
- [ ] Implement competitor_agent.py
- [ ] Weekly scan: screenshot + DOM hash for 5 competitors
- [ ] Pricing extractor: detect price changes
- [ ] New route detector: diff sitemap/routes week over week
- [ ] Tech stack: Wappalyzer headers analysis
- [ ] Supabase: insert competitor_snapshots
- [ ] Weekly digest → Telegram with changes highlighted
- [ ] CLI: `cli-anything-designwise competitor --target propertyonion --json`
- [ ] Write 8 tests

### S4.4 — ContentWise Agent (P2)
- [ ] Implement content_agent.py
- [ ] Landing page copy generator (uses DESIGN.md tone)
- [ ] Blog post generator (market analysis template)
- [ ] Email sequence: 4-email onboarding drip
- [ ] SEO optimization: pass content through SEOWise before publish
- [ ] Brand tone check: pass through BrandGuard
- [ ] CLI: `cli-anything-designwise content --type blog --topic "foreclosure trends Q1 2026"`
- [ ] Write 6 tests

### S4.5 — Launch Readiness
- [ ] Run full eval suite (25 assertions) — target 100% pass
- [ ] Run BrandGuard full-site scan — 0 violations
- [ ] Run QAWise visual regression — all routes baselined
- [ ] Run Lighthouse — Performance ≥80, Accessibility ≥90, SEO ≥80
- [ ] Run CompetitorWise — baseline competitor snapshots
- [ ] Enable all cron workflows (nightly audit, weekly competitor/SEO, daily analytics)
- [ ] Telegram: weekly digest operational
- [ ] PostHog: dashboard with funnel visualization
- [ ] Watch dashboard: DesignWise tasks visible on watch.biddeed.ai
- [ ] Beta launch: enable Starter $39 tier Stripe checkout
- [ ] Announce to beta users

---

## DEFINITION OF DONE

Sprint is DONE when:
1. All checkboxes in the sprint section are checked
2. All new agents respond to `--json` CLI invocation
3. All new tests pass (target: 130+ new tests across squad)
4. BrandGuard reports 0 violations on lab.zonewise.ai AND zonewise.ai
5. Eval score ≥ 20/25 (Sprint 1-2) → 25/25 (Sprint 4)
6. All GitHub Action workflows fire successfully
7. TODO.md updated and pushed to GitHub

---

## CLAUDE CODE SESSION COMMANDS

```bash
# Sprint 1 start
cd ~/cli-anything-biddeed
git checkout -b feat/designwise-squad
# Read this plan
cat docs/plans/DESIGNWISE-PLAN.md
cat docs/plans/DESIGNWISE-SPEC.md
# Begin S1.1

# Sprint 1 critical bug fixes (separate session)
cd ~/zonewise-web
git checkout -b fix/critical-ui-bugs
# Read audit
cat DESIGN.md
# Fix demo.html, /kpis, /explorer, nav, footer

# Lab branch setup
cd ~/zonewise-web
git checkout -b lab
git push origin lab
# Vercel auto-deploys to lab.zonewise.ai
```

---

---

## STITCH 2.0 PATCH TASKS (V1.1.0 — Sprints updated)

### Patch Sprint S1 (Week 1 additions)
- [x] Create `stitch_usage` quota table (migration written, needs Supabase Dashboard run)
- [x] Commander quota check before StitchWise dispatch (Amendment 1)
- [x] Telegram alert at 280/350 used (80%) — Amendment 1

### Patch Sprint S2 (Week 2 additions)
- [x] Intent-based vibe prompts for all 8 screens — Amendment 1
- [x] Project-wide context threading (zonewise-production) — Amendment 1
- [x] @google/stitch-sdk MCP config — Amendment 1
- [x] Stitch Skills Library react-component-conversion skill — Amendment 1
- [x] BrandGuard URL extraction + DESIGN.md drift diff — Amendment 3
- [x] CodeWise direct Stitch MCP pipeline (primary + fallback) — Amendment 4

### Patch Sprint S3 (Week 3 additions)
- [x] Interactive prototype flow: generate_prototype() — Amendment 2
- [x] Parallel exploration dispatch: parallel_stitch_dispatch() — Amendment 5

### Patch Sprint S4 (Week 4 additions)
- [x] Figma archive: export_to_figma() + design_tasks.figma_url column — Amendment 6

### New GitHub Actions Workflows (Patch)
| Workflow | Schedule | Agent | Amendment |
|----------|----------|-------|-----------|
| `weekly-designmd-drift.yml` | Sunday 8AM EST (0 13 * * 0) | BrandGuard drift check | 3 |

### Updated Cron Table (Full)
| Workflow | Schedule | Agent |
|----------|----------|-------|
| `nightly-audit.yml` | 2AM EST daily | BrandGuard full-site scan |
| `autoloop-designwise.yml` | 3AM EST daily | 25-assertion eval loop |
| `weekly-competitor.yml` | Sunday 6AM EST | CompetitorWise scan |
| `weekly-seo.yml` | Sunday 7AM EST | SEOWise audit |
| `weekly-designmd-drift.yml` | Sunday 8AM EST | BrandGuard drift check (NEW) |
| `daily-analytics.yml` | 6AM EST daily | AnalyticsWise aggregation |

---

*Plan ready for Claude Code handoff. 2026-03-21.*
*V1.1.0 Stitch 2.0 patch tasks added 2026-03-21.*
