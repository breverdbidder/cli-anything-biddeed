# DESIGNWISE S3 DISPATCH — Quality + Intelligence + Core Pages
# Date: 2026-03-23 | Version: 1.0.0
# Prereqs: S1 ✅ (14 agents, 11 tables) | S2 ✅ (Stitch+Code+Deploy) | Gemini ✅
# Rule: NEVER-LIE. Verify every step. Wrong = "I was wrong".

## CONTEXT LOAD

```bash
cd /opt/biddeed/cli-anything-biddeed
git pull origin main
cat docs/plans/DESIGNWISE-PLAN.md | grep -A 60 "SPRINT 3"
cat docs/plans/DESIGNWISE-SPEC.md | head -100
```

Read CLAUDE.md for full project rules. Read designwise/ structure.

## ENVIRONMENT

```bash
export GEMINI_API_KEY="${GEMINI_API_KEY}"
export SUPABASE_URL="${SUPABASE_URL}"
export SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_KEY}"
export GH_PAT="${GH_PAT}"
```

## STEP 1: QAWise Agent (S3.1) — 20 min

Target: `designwise/agent-harness/cli_anything/designwise/core/qawise_agent.py`

1. Install Playwright: `pip install playwright && playwright install chromium`
2. Implement QAWise with:
   - `capture_baselines(url, viewports=[1440, 768, 375])` → screenshots to Supabase visual_baselines
   - `run_visual_regression(url, baseline_id)` → Pixelmatch diff, threshold 1%
   - `run_e2e_flow(url)` → landing → heatmap → click → gate → signup
   - `run_lighthouse(url)` → Performance ≥80, Accessibility ≥90, SEO ≥80
3. CLI entry: `cli-anything-designwise qa --url <URL> --json`
4. Write 12 tests in `designwise/tests/test_qawise.py`
5. Verify: `cd designwise && python -m pytest tests/test_qawise.py -v`
6. Commit: `git add -A && git commit -m "feat(designwise): S3.1 QAWise — visual regression + E2E + Lighthouse"`

## STEP 2: SEOWise Agent (S3.3) — 15 min

Target: `designwise/agent-harness/cli_anything/designwise/core/seo_agent.py`

1. Implement SEOWise with:
   - `scan_meta_tags(url)` → title length, description, og:image, twitter:card
   - `generate_sitemap(routes)` → /sitemap.xml from Next.js routes
   - `add_structured_data()` → Schema.org WebApplication + Organization
   - `check_core_web_vitals(url)` → LCP, FID, CLS thresholds
2. Create `weekly-seo.yml` cron workflow (Sundays 6AM EST)
3. CLI entry: `cli-anything-designwise seo --url <URL> --json`
4. Write 10 tests
5. Commit: `git add -A && git commit -m "feat(designwise): S3.3 SEOWise — meta scanner + sitemap + schema.org"`

## STEP 3: AccessibilityWise Agent (S3.4) — 15 min

Target: `designwise/agent-harness/cli_anything/designwise/core/a11y_agent.py`

1. Install: `pip install axe-playwright-python`
2. Implement A11yWise with:
   - `run_axe_scan(url)` → WCAG 2.1 AA full automated scan
   - `check_keyboard_nav(url)` → tab order, focus visible, no traps
   - `audit_aria(url)` → interactive elements, map controls, modals
3. Add as required check: create `a11y-check.yml` GitHub Action on PRs
4. CLI entry: `cli-anything-designwise a11y --url <URL> --json`
5. Write 10 tests
6. Commit: `git add -A && git commit -m "feat(designwise): S3.4 AccessibilityWise — axe-core WCAG 2.1 AA"`

## STEP 4: Core Pages — zonewise-web (S3.5) — 30 min

Target repo: `breverdbidder/zonewise-web`

```bash
cd /opt/biddeed
git clone https://${GH_PAT}@github.com/breverdbidder/zonewise-web.git 2>/dev/null || (cd zonewise-web && git pull)
cd zonewise-web && npm ci
```

### 4A: Reventure-style Choropleth Heatmap (Lead Magnet)
- Read `docs/plans/EXPLORER_V2_SPEC.md` for full spec
- Implement choropleth map at `/explorer` using Mapbox GL
- Zillow ZHVI data overlay at ZIP level (color-coded by YoY change)
- Zoom-adaptive: choropleth at county zoom, parcels at street zoom
- NO LOGIN required — this is the FREE lead magnet
- Use existing Mapbox token from env: NEXT_PUBLIC_MAPBOX_TOKEN

### 4B: Conversion Gate
- After 5 parcel clicks → show signup modal
- Free tier: 5 parcels/day
- Pro tier: unlimited
- Supabase RLS enforces limits

### 4C: Pricing Page (/pricing)
- Free / Starter $39/mo / Pro $99/mo
- House brand: Navy #1E3A5F, Orange #F59E0B, Inter font, bg #020617
- CTA buttons → Supabase Auth signup flow

### 4D: Mobile Bottom Sheet
- On mobile viewports (<768px), map is full screen
- Property details slide up as bottom sheet
- Touch-friendly: min 44x44px tap targets

### 4E: All pages pass BrandGuard
- Run BrandGuard check before commit
- Navy #1E3A5F primary, Orange #F59E0B accent, Inter font only
- Any violation = DO NOT COMMIT

Commit each sub-step separately to zonewise-web.

## STEP 5: Telegram Notification

```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_CHAT_ID}" \
  -d parse_mode="Markdown" \
  --data-urlencode "text=✅ *DESIGNWISE SPRINT 3 — COMPLETE*

🔍 *S3.1:* QAWise — Playwright + visual regression + E2E
📈 *S3.3:* SEOWise — meta scanner + sitemap + schema.org
♿ *S3.4:* A11yWise — axe-core WCAG 2.1 AA
🗺️ *S3.5:* Core pages — choropleth heatmap + conversion gate + pricing + mobile
🧪 *Tests:* 32+ new

_Sprint 4 ready._"
```

## VERIFICATION CHECKLIST

- [ ] QAWise: `python -c "from cli_anything.designwise.core.qawise_agent import QAWiseAgent; print('OK')"`
- [ ] SEOWise: `python -c "from cli_anything.designwise.core.seo_agent import SEOWiseAgent; print('OK')"`
- [ ] A11yWise: `python -c "from cli_anything.designwise.core.a11y_agent import A11yWiseAgent; print('OK')"`
- [ ] zonewise-web builds: `cd /opt/biddeed/zonewise-web && npm run build`
- [ ] /explorer route renders choropleth
- [ ] /pricing route renders 3 tiers
- [ ] All tests pass: `cd /opt/biddeed/cli-anything-biddeed/designwise && python -m pytest tests/ -v`
