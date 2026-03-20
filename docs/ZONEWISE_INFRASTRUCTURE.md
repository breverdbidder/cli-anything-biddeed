# ZONEWISE.AI — SINGLE SOURCE OF TRUTH

> **This file is the authoritative infrastructure map for ZoneWise.AI.**
> Last updated: 2026-03-20
> Updated by: Claude AI Architect
> Deployed to: zonewise-web, zonewise (monorepo), biddeed-brain

---

## 1. DOMAIN & HOSTING

| Domain | Provider | Project | Notes |
|--------|----------|---------|-------|
| **zonewise.ai** | Vercel Pro | `zonewise-web` (prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E) | PRIMARY — all traffic |
| **www.zonewise.ai** | Vercel Pro | `zonewise-web` (prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E) | Redirects to zonewise.ai |
| **zonewise.app** | Vercel | `zonewise-desktop` | Desktop app viewer |

### Vercel Account
- **Team:** team_UEds2qBzyD9e7rOrX8aakj9K (ariel-shapira-s-projects)
- **Plan:** Pro ($20/mo)
- **Token secret:** `VERCEL_TOKEN` in GitHub repo secrets

### CRITICAL: Vercel Project IDs
| Project Name | Project ID | Has Custom Domain? | Status |
|---|---|---|---|
| **zonewise-web** | `prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E` | ✅ zonewise.ai + www | **ACTIVE — THIS IS PRODUCTION** |
| zonewise-ai | `prj_B478bSAAf0yLnY3owbhN7a1W7mQs` | ❌ only .vercel.app | **DEPRECATED — DO NOT USE** |

> ⚠️ **NEVER deploy to or promote from `zonewise-ai` (prj_B478bSAAf...).** It has no custom domain. All deploys go through `zonewise-web` only.

---

## 2. GITHUB REPOSITORIES

### Active Repos (use these)

| Repo | Purpose | Deploys To | Status |
|------|---------|------------|--------|
| **zonewise-web** | Next.js 16 marketing + product UI | Vercel → zonewise.ai | ✅ PRIMARY |
| **zonewise-scraper-v4** | ZoneWise V4 scraper (Firecrawl→Gemini→Claude) | Modal.com / Hetzner | ✅ ACTIVE |
| **zonewise-agents** | NLP backend (FastAPI + LangGraph) | Render → zonewise-agents.onrender.com | ✅ ACTIVE |
| **zonewise-modal** | 67-county scraper (AgentQL + Playwright) | Modal.com serverless | ✅ ACTIVE |
| **zonewise-desktop** | CraftAgents desktop app viewer | Vercel → zonewise.app | ✅ ACTIVE |
| **zonewise** | Monorepo — scripts, migrations, pipeline | N/A (reference) | ✅ ACTIVE |
| **zonewise-gtm** | Go-to-market strategy docs | N/A (docs only) | ✅ ACTIVE |

### Deprecated Repos (DO NOT USE)

| Repo | Reason | Replacement |
|------|--------|-------------|
| zonewise-skills | Replaced by zonewise-lobster | zonewise-desktop |
| zonewise-lobster | Moltbot experiment, abandoned | zonewise-desktop |
| zonewise-rebrand-mission | One-time rebrand task, completed | zonewise-web |
| zonewise-traycer-specs | Spec generation, completed | zonewise-web/docs |
| zonewise-agent-teams | Agent Teams experiment | cli-anything-biddeed |
| zonewise-marketing-plan | Static doc, superseded | zonewise-gtm |
| zonewise-landing | One-off AI landing page | zonewise-web |
| zonewise-loans | Loan app experiment | Paused |

---

## 3. DEPLOYMENT PIPELINE

### How code reaches zonewise.ai

```
Developer pushes to breverdbidder/zonewise-web (main branch)
    ↓
Vercel GitHub Integration auto-builds → PREVIEW deployment
    ↓
deploy-prod.yml (auto on push to main)
    ↓
vercel pull → vercel build --prod → vercel deploy --prebuilt --prod
    ↓
zonewise.ai LIVE
```

### Authorized Workflows (keep these)

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **deploy-prod.yml** | push to main + manual | Build & deploy to Vercel production |
| **promote-now.yml** | manual only | Emergency: promote latest READY to production |
| **ci.yml** | push | Lint + type check |
| **security-checks.yml** | push | Security scan |
| **webhook_notify.yml** | push + manual | Telegram notifications |

### Workflows to DELETE (stale/one-off)

```
add-domain-to-vite.yml          ← one-off domain fix
check-deploy.yml                ← diagnostic, done
check-vercel-deploy.yml         ← diagnostic, done
claude-code-explorer-v2.yml     ← one-off Claude Code dispatch
deploy-biddeed.yml              ← BidDeed Cloudflare, wrong repo
deploy-explorer-now.yml         ← one-off explorer deploy
deploy-explorer.yml             ← superseded by deploy-prod
deploy-loans.yml                ← loans experiment, paused
deploy-michael.yml              ← Michael app, wrong repo
deploy-migration.yml            ← one-off migration
deploy-onboarding.yml           ← one-off onboarding
deploy.yml                      ← old deploy, superseded
fix-vercel-framework.yml        ← one-off fix
fix-vercel-project.yml          ← one-off fix
install-skills.yml              ← skills experiment
plan-enforcement-agent.yml      ← experiment
react-doctor.yml                ← one-off diagnostic
sync-gateway-secrets.yml        ← gateway sync, move to cli-anything
upstream-health.yml             ← health check, move to cli-anything
vercel-diag.yml                 ← diagnostic, done
```

---

## 4. SUPABASE

| Setting | Value |
|---------|-------|
| **Project Ref** | mocerqjnksmhcjzxrewo |
| **URL** | https://mocerqjnksmhcjzxrewo.supabase.co |
| **Plan** | Pro (paid) |
| **Anon Key** | ends in ...klKQDw |
| **Service Role** | ends in ...Tqp9nE |
| **Management Token** | sbp_cbf04a175a130c466eddbe40a3f49b79aaec6214 |

### Key Tables

| Table | Rows | Purpose |
|-------|------|---------|
| sample_properties | 351K+ | Brevard parcels with zoning |
| zoning_assignments | 262K+ | Parcel→zone mappings |
| zoning_districts | 265+ | District definitions with DIMS |
| ims_permits | 16K+ | Palm Bay building permits |
| historical_auctions | 1,393 | Foreclosure auction history |
| activities | — | User activity tracking |
| daily_metrics | — | Platform metrics |
| insights | — | AI insights + YouTube transcripts |
| beta_signups | — | Beta waitlist |
| sentinel_runs | — | Everest Sentinel health checks |

---

## 5. EXTERNAL SERVICES

| Service | Purpose | Config Location |
|---------|---------|-----------------|
| **Clerk** (v7) | Auth (signup/login) | Vercel env vars |
| **Mapbox** | Map tiles + geocoding | Token: pk.eyJ1...4RPrkTf84GL1-clmhmCnTw |
| **Stripe** | Payments | Vercel env vars (STRIPE_*) |
| **Anthropic** | AI chat backend | Vercel env var (ANTHROPIC_API_KEY) |
| **Supadata** | YouTube transcript API | Key: sd_3c7a57546da7893f9ae3056a664d5dc9 |
| **Render** | zonewise-agents backend | Auto-deploy from zonewise-agents repo |
| **Modal.com** | Serverless scraping | zonewise-modal repo |
| **Hetzner** | Persistent compute (87.99.129.125) | SSH via GHA secrets |

---

## 6. RULES

1. **ONE Vercel project:** `prj_EaXgEO6WDoSpCeLhuCemtbPr6e8E` (zonewise-web). Never touch zonewise-ai project.
2. **ONE deploy workflow:** `deploy-prod.yml`. Runs on every push to main. No manual deploys needed.
3. **ONE Supabase project:** mocerqjnksmhcjzxrewo. All tables here. No second project.
4. **ONE source repo for the website:** breverdbidder/zonewise-web. Period.
5. **Deprecated repos stay read-only.** Never push to them. Never deploy from them.
6. **This file is updated whenever infrastructure changes.** If it's not in this file, it doesn't exist.

---

## 7. QUICK REFERENCE

```bash
# Deploy to production (automatic on push, or manual):
# GitHub Actions → deploy-prod.yml → vercel pull + build + deploy --prod

# Emergency promote (if deploy-prod fails):
# GitHub Actions → promote-now.yml → promotes latest READY to production

# Check live site:
curl -sI https://zonewise.ai | grep 'x-vercel-id'

# Vercel project dashboard:
# https://vercel.com/ariel-shapira-s-projects/zonewise-web

# Supabase dashboard:
# https://supabase.com/dashboard/project/mocerqjnksmhcjzxrewo
```
