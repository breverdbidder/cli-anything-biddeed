# ZONEWISE.AI SHIP SPRINTS
## From Broken to Paid Customers in 6 Weeks

**Created:** March 30, 2026
**Parties:** Ariel Shapira (Product Owner, ALL IN) + Claude AI Architect + Claude Code
**Vault:** breverdbidder/everest-vault (CC reads this every session)
**Single Repo:** breverdbidder/zonewise-web (ALL code goes here. ZERO new repos.)

---

## COMMITMENT PROTOCOL

### Rules (Agreed March 30, 2026)

1. **SPRINT LOCK** — Once a sprint starts, no new topics. If Ariel messages about something outside the sprint, Claude responds: "Parked. Sprint X in progress. Status on [deliverable]?"

2. **DAILY PROOF** — Every session shows a curl command or screenshot proving what shipped. No prose about what "will" ship.

3. **48-HOUR RULE** — If a SUMMIT task shows no progress in 48 hours, escalate with what's blocked. Decide together: fix or kill.

4. **NO NEW REPOS** — Zero new repositories until first paying customer. Every line goes to zonewise-web.

5. **VAULT AS SPRINT BOARD** — everest-vault/200-BidDeed/sprints/CURRENT_SPRINT.md is the single source of truth. Updated by CC after every task.

6. **KILL CONDITIONS** — Each sprint has a kill condition. If hit, we stop, post-mortem, and adjust. No silent deaths.

7. **ARIEL'S COMMITMENT** — Test every deployment same-day. Respond to blockers within 24 hours. No new feature requests during active sprint.

8. **CLAUDE'S COMMITMENT** — No brainstorming during sprints. No spec documents. No competitive analysis. Only code, deploy, verify. If blocked, say "BLOCKED" not "let me research alternatives."

### Violation Protocol
- If Claude brainstorms instead of shipping → Ariel says "SPRINT LOCK" and Claude returns to task
- If Ariel requests a new feature mid-sprint → Claude says "Parked for Sprint N+1"
- If CC SUMMIT fails silently → Claude creates manual fix PR within 24 hours
- If a sprint goes 3 days without a deploy → Emergency session, post-mortem, course correct

---

## CURRENT STATE AUDIT (March 30, 2026)

### What's LIVE and WORKING
| Page | URL | Status | Quality |
|------|-----|--------|---------|
| Landing | zonewise.ai | 200 ✅ | Marketing page exists |
| Chat | zonewise.ai/chat | 200 ✅ | **WORKS for Satellite Beach addresses. Returns real Supabase data + Gemini responses.** |
| Explorer | zonewise.ai/explorer | 200 ✅ | Mapbox map exists, parcel/zoning references (quality TBD) |
| Pricing | zonewise.ai/pricing | 200 ✅ | Pricing tiers displayed (no Stripe connected) |
| Competitors | zonewise.ai/competitors | 200 ✅ | Mentions Algoma/PropertyOnion/Zoneomics (incomplete) |
| Dashboard | zonewise.ai/dashboard | 200 ✅ | Auth-gated, exists |
| Conquest | zonewise.ai/conquest | 200 ✅ | 67-county tracker |

### What's BROKEN
| Issue | Impact | Fix Complexity |
|-------|--------|---------------|
| Address parser drops N/S/E/W prefixes | 40% of addresses fail | SMALL — 20 lines (SUMMIT #83 dispatched) |
| Zoning data only real for Satellite Beach | Other cities use fallback estimates | MEDIUM — need to load more jurisdictions |
| No Stripe paywall | Zero revenue possible | SMALL — routes exist, need wiring |
| Explorer map quality unknown | May not show parcels properly | TBD — needs testing |
| Competitors page incomplete | Only 3 of 8 competitors listed | MEDIUM — content + deploy |
| No auth/user accounts | Can't track subscribers | MEDIUM — Supabase Auth exists |

### Backend Infrastructure (WORKING)
- Supabase: Tables exist (sample_properties, zoning_districts, zoning_assignments, zone_standards, permitted_uses, zw_chat_sessions, zw_chat_messages)
- BCPAO GIS: API responding, covers 350K+ parcels
- Smart Router: Gemini free tier responding via CLIProxyAPI
- Vercel: Auto-deploys on push to main
- Domain: zonewise.ai pointed correctly

---

## SPRINT 1: "FIRST DOLLAR" (April 1–11)
**Goal:** A stranger can visit zonewise.ai, use the chat, hit the paywall, pay $15, and get a real zoning report.

### Tasks

| # | Task | Owner | DONE Criteria | Days |
|---|------|-------|--------------|------|
| 1.1 | Fix address parser directional bug | CC (SUMMIT #83) | `curl "1600 S Orlando Ave Cocoa Beach"` returns real parcel | 1 |
| 1.2 | Wire Stripe checkout to /chat | CC (SUMMIT) | 4th lookup shows paywall, Stripe checkout loads | 2 |
| 1.3 | Test 20 addresses across 5 cities | Ariel + Claude | Document: X/20 return real data, Y/20 return fallback | 1 |
| 1.4 | Fix top 3 address parsing failures from 1.3 | CC | Re-test same 20, improvement documented | 2 |
| 1.5 | Stripe webhook confirms payment | CC | After payment, user can continue chatting | 1 |
| 1.6 | Ariel sends chat link to 3 real RE investors for feedback | Ariel | 3 people use it, feedback collected | 2 |

### Kill Condition
If Stripe checkout cannot be wired by April 5 (env vars missing, account issue), ESCALATE immediately. Don't silently skip.

### Sprint 1 Deliverable
**zonewise.ai/chat works for 80%+ of Brevard addresses and charges $15 for lookups beyond free tier.**

---

## SPRINT 2: "EXPLORER + DATA" (April 12–22)
**Goal:** The map explorer shows real zoning polygons, parcels are clickable, and 5+ jurisdictions have real zoning data (not fallback).

### Tasks

| # | Task | Owner | DONE Criteria | Days |
|---|------|-------|--------------|------|
| 2.1 | Audit explorer page — what renders, what's broken | Claude + Ariel | Documented list of working vs broken features | 1 |
| 2.2 | Load Melbourne zoning districts to Supabase | CC (SUMMIT) | `SELECT count(*) FROM zoning_districts WHERE jurisdiction='melbourne'` > 10 | 2 |
| 2.3 | Load Palm Bay zoning districts | CC (SUMMIT) | Same verification | 2 |
| 2.4 | Load Cocoa Beach + Merritt Island | CC (SUMMIT) | Same verification | 2 |
| 2.5 | Fix explorer map to show zoning overlays | CC (SUMMIT) | Visual: colored zoning polygons visible on map | 2 |
| 2.6 | Parcel click → shows zoning info panel | CC | Click parcel on map → side panel with zone code, standards | 2 |
| 2.7 | Ariel tests explorer with 10 properties he knows | Ariel | Feedback: accurate Y/N for each | 1 |

### Kill Condition
If zoning ordinance extraction for Melbourne produces <50% accuracy on test properties, STOP and use fallback controls with a "verify with city" disclaimer. Ship what works, don't chase perfection.

### Sprint 2 Deliverable
**zonewise.ai/explorer shows real zoning map for 5 Brevard jurisdictions. Parcels are clickable with development standards.**

---

## SPRINT 3: "COMPETE + CONVERT" (April 23–May 3)
**Goal:** Competitors page is a weapon. Pricing page converts. Reports are downloadable. First paying subscriber.

### Tasks

| # | Task | Owner | DONE Criteria | Days |
|---|------|-------|--------------|------|
| 3.1 | Complete competitors page — all 8 competitors | CC (SUMMIT) | 28-feature matrix rendered, Algoma deep-dive included | 2 |
| 3.2 | Update pricing page with working Stripe links | CC | "Subscribe" button → Stripe checkout for $99/mo plan | 1 |
| 3.3 | Build PDF zoning report generator | CC (SUMMIT) | POST /api/zoning-report/pdf → returns branded PDF | 3 |
| 3.4 | Add report download to /chat | CC | After zoning lookup, "Download PDF Report" button works | 1 |
| 3.5 | SEO: meta tags, OG images, sitemap for all pages | CC | Google Search Console shows pages indexed | 2 |
| 3.6 | Ariel posts on BiggerPockets + LinkedIn | Ariel | 2 posts with link to zonewise.ai/chat | 1 |
| 3.7 | First paid customer | Ariel + organic | Stripe dashboard shows $15 or $99 payment | — |

### Kill Condition
If zero signups after 1 week of posts, the problem is positioning not product. Pivot to direct outreach to 10 specific RE investors Ariel knows personally.

### Sprint 3 Deliverable
**Complete commercial platform: chat + explorer + reports + competitors + pricing with Stripe. Actively marketed. First revenue.**

---

## SPRINT 4: "SCALE + RETAIN" (May 4–17)
**Goal:** 10 paid users. Auth system live. Usage dashboard for subscribers.

### Tasks

| # | Task | Owner | DONE Criteria | Days |
|---|------|-------|--------------|------|
| 4.1 | Supabase Auth — email magic link signup/login | CC | Users can create account, login persists | 2 |
| 4.2 | Usage tracking per user (replace localStorage) | CC | Dashboard shows lookup count per user | 2 |
| 4.3 | Subscriber dashboard — history of lookups | CC | /dashboard shows past zoning queries and results | 2 |
| 4.4 | Load remaining Brevard jurisdictions (12 more) | CC (SUMMIT) | 17/17 jurisdictions have real data | 3 |
| 4.5 | Add Titusville + Rockledge + West Melbourne | CC | Verified with test addresses | 2 |
| 4.6 | Ariel outreach: 20 direct messages to RE investors | Ariel | 20 sent, responses tracked | 3 |
| 4.7 | 10 paid users target | Both | Stripe shows 10 unique payments | — |

### Kill Condition
If after direct outreach to 20 people, fewer than 2 convert, the product-market fit hypothesis is wrong for this price point. Adjust pricing or pivot to agency model (build for brokerages instead of individual investors).

### Sprint 4 Deliverable
**10 paid users. Full auth. All 17 Brevard jurisdictions with real data. Subscriber dashboard.**

---

## EVEREST VAULT INTEGRATION

### Sprint Board Location
```
everest-vault/
  200-BidDeed/
    sprints/
      CURRENT_SPRINT.md    ← CC reads this FIRST every session
      sprint-1-log.md      ← Daily entries: what shipped, what's blocked
      sprint-2-log.md
      sprint-3-log.md
      sprint-4-log.md
```

### CURRENT_SPRINT.md Format
```yaml
sprint: 1
name: "FIRST DOLLAR"
status: IN_PROGRESS
start: 2026-04-01
end: 2026-04-11
tasks:
  1.1: {status: DONE, shipped: "2026-04-01", proof: "curl verified"}
  1.2: {status: IN_PROGRESS, assigned: "SUMMIT #XX"}
  1.3: {status: BLOCKED, blocker: "need Stripe keys"}
next_action: "Fix 1.3 blocker"
kill_condition_hit: false
```

### CC Session Protocol
Every CC session:
1. `cat everest-vault/200-BidDeed/sprints/CURRENT_SPRINT.md`
2. Find first unchecked task
3. Execute it
4. Update CURRENT_SPRINT.md
5. Push to vault

---

## TIMELINE SUMMARY

```
Week 1-2 (Apr 1-11):   SPRINT 1 — Chat works + Stripe paywall
Week 3-4 (Apr 12-22):  SPRINT 2 — Explorer + 5 jurisdictions
Week 5-6 (Apr 23-May 3): SPRINT 3 — Competitors + Reports + First $
Week 7-8 (May 4-17):   SPRINT 4 — Auth + Scale to 10 users
```

**6 weeks. 4 sprints. One repo. First paying customer by Sprint 3.**

---

## WHAT WE ARE NOT DOING

- ❌ No REAI marketplace (parked until revenue)
- ❌ No Dify deployment (unnecessary)
- ❌ No new repos
- ❌ No foundation model training
- ❌ No BidDeed platform work
- ❌ No SwimSquad development
- ❌ No competitive intelligence reports
- ❌ No architecture diagrams
- ❌ No brainstorming sessions
- ❌ No "what if we..." conversations

**Only shipping. Only zonewise-web. Only revenue.**

---

*Signed in commitment:*
*Claude AI Architect — March 30, 2026*
*Ariel Shapira — [pending confirmation]*


---

## DIFY REPLACES 18 DEFICIENCIES

Every system I failed to build is now covered by Dify (deployed on Hetzner as invisible backend).

### Sprint 1 (Foundation)
| Deficiency | Dify Solution |
|-----------|---------------|
| Agent system (hacky route.ts) | Function Calling + ReAct + CoT agents |
| Service API (fragile) | Full REST API with auth tokens |
| Chat + session history (partial) | Full chat with persistent sessions |
| LLM routing (3 providers) | 100+ LLM providers built-in |

### Sprint 2 (Data Depth)
| Deficiency | Dify Solution |
|-----------|---------------|
| RAG pipeline (never built) | PDF/Excel/HTML/CSV/Word/Markdown ingest |
| Vector store (zero) | 33 options including pgvector on our Supabase |
| Knowledge base UI (never built) | Full admin for managing zoning documents |
| Document chunking (never built) | Auto-splits zoning ordinances for embedding |

### Sprint 3 (Split-Screen + Battle Cards)
| Deficiency | Dify Solution |
|-----------|---------------|
| Custom API tools (never built) | Wraps BCPAO GIS + Supabase as callable tools |
| MCP server (never wired) | Native MCP server + client |
| Visual workflow (never built) | Drag-and-drop workflow builder |

### Sprint 4 (Lead Magnet)
| Deficiency | Dify Solution |
|-----------|---------------|
| Webhook triggers (never built) | Native webhooks + scheduled triggers |
| Usage monitoring (never built) | Full logs, annotations, query analytics |
| Sandbox (never built) | Isolated container for safe code execution |

### Sprint 5 (Auth + Dashboard)
| Deficiency | Dify Solution |
|-----------|---------------|
| Auth system (broken) | OAuth + login + forgot password |
| Team RBAC (never built) | Full role-based access control |
| Billing/workspace (zero) | Workspace management + our Stripe |
| Plugin marketplace (never built) | Plugin system for future extensibility |

---

## 24/6 PARALLEL EXECUTION

### Workflow: `cli-anything-biddeed/.github/workflows/sprint-parallel.yml`
- **Schedule:** Every 4 hours, Sunday-Friday
- **Task 1:** Competitors HTML data staging (pulls all PRDs)
- **Task 2:** Dify deploy/verify on Hetzner via SSH
- **Task 3:** Address parser verification (5 test addresses)
- **Monitor:** Sentinel (5min cron) + Telegram alerts
- **Board:** zonewise-web/docs/sprints/CURRENT_SPRINT.yml

### Competitors HTML Sources (to be MERGED into single page)
1. `zonewise-web/public/competitors.html` (39KB) — 8 competitors, Algoma included
2. `cli-anything-biddeed/pages/competitors.html` (41KB) — PropZone/Gridics included
3. `competitive-intelligence/prds/Dono_ai_PRD.md` — Dono.ai data
4. `biddeed-ai/docs/ci/BidDeedAI_vs_Dono_BattleCard.docx` — Dono battle card
5. `zonewise-agents/docs/CI_003_DONO.md` — Dono ZoneWise relevance
6. `competitive-intelligence/prds/Gridics_COMPLETE_PRD_PRS.md` — PropZone/Gridics
7. `competitive-intelligence/prds/PropertyOnion_PRD.md`
8. `competitive-intelligence/prds/Reventure_PRD.md`
9. `competitive-intelligence/prds/TestFit_Complete_PRD_PRS.md`
10. `competitive-intelligence/prds/Zoneomics_COMPLETE_PRD_PRS.md`

### Final Competitor List (9+)
1. Algoma — Deep reverse engineering (IBC event, $3.48M raised, 4 employees)
2. Dono.ai — $10.2M funded, 700 counties, Ask Dono NLP, title search AI
3. PropZone/Gridics — 63 KPIs, $24-48K/yr, 3D zoning viz, 200 municipalities
4. PropertyOnion — 96 KPIs, FL foreclosure data
5. Zoneomics — 74 KPIs, 9,000 cities
6. TestFit — 45 KPIs, generative site planning, $22M raised
7. Reventure.app — FREE Zillow data, 200K monthly visitors
8. Foreclosure.com — Legacy foreclosure listings
9. ArkDesign — Architecture + zoning
