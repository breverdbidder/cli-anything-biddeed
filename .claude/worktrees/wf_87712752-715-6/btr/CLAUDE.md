# BTR Squad — CLAUDE.md

## Identity
You are the AI Engineer for **cli-anything-btr**, the Build-to-Rent + Distressed Assets squad in the BidDeed.AI CLI-Anything Agent Army.

## Squad: EVEREST-BTR
- **10 agents** across 4 scenarios (Land / Construction / Permanent / Rehab) + shared intelligence
- **3 property type tabs**: SFR | Duplex | Multifamily
- **MAI Valuation Engine**: 3-approach method (Income, Sales Comp, Cost)
- **HBU Agent**: 4-test Highest & Best Use analysis

## Agent Registry
| ID | Name | Status |
|---|---|---|
| cli_btr.commander | Squad Commander | 🔨 Scaffold |
| cli_btr.land | Land Acquisition Agent | 🔨 Scaffold |
| cli_btr.con | Construction Funding Agent | 🔨 Scaffold |
| cli_btr.perm | Permanent Funding Agent | 🔨 Scaffold |
| cli_btr.rehab | Distressed Asset Rehab Agent | 🔨 Scaffold |
| cli_btr.mai | MAI Valuation Engine | 🔨 Scaffold |
| cli_btr.hbu | Highest & Best Use Agent | 🔨 Scaffold |
| cli_btr.cost | Construction Cost Estimator | 🔨 Scaffold |
| cli_btr.lv | Lender Vetting & Scoring | 🔨 Scaffold |
| cli_btr.proforma | Pro Forma Generator | 🔨 Scaffold |

## Rules
1. Follow HARNESS.md 7-phase pipeline for every agent
2. All agents output JSON to stdout for piping
3. State persists to Supabase (mocerqjnksmhcjzxrewo)
4. Tests required before any push (target: 20+ per agent)
5. Weekly health check → Telegram (Sun 9AM EST)
6. NEVER use paid Claude API — use Hetzner claude CLI or Gemini Flash
7. $10/session MAX cost discipline

## Open-Source Dependencies
- OpenMud (MIT) — construction cost estimation
- OpenConstructionEstimate — multilingual cost DB
- ai-real-estate-assistant — RAG + valuation
- ai-underwriting — document extraction
- LangGraph — multi-agent orchestration
- ZoneWise Scraper V4 — zoning intelligence (internal)
- cli-anything-spatial — Shapely STRtree (internal)

## Key Formulas
- **Max Bid (Rehab)**: (ARV × 70%) - Repairs - $10K - MIN($25K, 15% × ARV)
- **DCR**: NOI / Annual Debt Service (target: 1.20-1.30)
- **Cap Rate**: NOI / Property Value
- **MAI Reconciliation**: Weighted average of 3 approaches by property type

## Deployment
- Repo: breverdbidder/cli-anything-biddeed/btr/
- CLI: `cli-anything-btr`
- Namespace: `cli_anything.btr.*`
- GitHub Actions: `btr_health_check.yml`
