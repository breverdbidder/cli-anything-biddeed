# CONFIDENTIAL ASSETS — Everest Capital USA / BidDeed.AI

**Classification:** INTERNAL — NDA Required
**Owner:** Ariel Shapira
**Last Updated:** 2026-03-31

---

## Asset Registry

| # | Asset | Location | Classification | Access |
|---|---|---|---|---|
| 1 | Shapira Formula core (ARV × 70% − repairs − $10K − MIN($25K, 15%×ARV)) | `auction/agent-harness/cli_anything/auction/core/analysis.py` | TRADE SECRET | NDA only |
| 2 | XGBoost scorer (model weights + retraining pipeline) | `modal/xgboost_scorer.py` | TRADE SECRET | NDA only |
| 3 | ML Priority Engine (3-tier scoring: XGBoost + Gemini + heuristic) | `scripts/ml_priority_engine.py` | TRADE SECRET | NDA only |
| 4 | CMA Analyst (per-feature dollar adjustments, comps logic) | `envelope/agent-harness/agents/analyst/cma_analyst.js` | TRADE SECRET | NDA only |
| 5 | Rehab Cost Forecaster (Brevard-specific coefficients) | `forecaster/agent.py` | TRADE SECRET | NDA only |
| 6 | BTR (Buy-to-Rent) scoring engine | `btr/agent-harness/cli_anything/btr/btr_cli.py` | TRADE SECRET | NDA only |
| 7 | Auction enrichment pipeline (behavioral signals) | `auction/agent-harness/cli_anything/auction/core/enrichment.py` | CONFIDENTIAL | NDA only |
| 8 | Auction analysis report generator | `auction/agent-harness/cli_anything/auction/core/report.py` | CONFIDENTIAL | NDA only |
| 9 | Opportunity scoring (jurisdiction thresholds) | `scripts/chat_intelligence_pipeline.py` | TRADE SECRET | NDA only |
| 10 | Historical training dataset | Supabase: `multi_county_auctions` (245K+ rows) | TRADE SECRET | Founder only |
| 11 | Agent skill library (accumulated operational knowledge) | `.claude/skills/` | CONFIDENTIAL | NDA only |

---

## Classification Levels

| Level | Meaning |
|---|---|
| **TRADE SECRET** | Core competitive advantage. Never disclosed without written approval + NDA. |
| **CONFIDENTIAL** | Internal use only. Disclosed to contractors under NDA. |
| **INTERNAL** | Not public but not competitively sensitive. |

---

## Repository Security Status

| Repo | Visibility | Trade Secret Code? | Action Required |
|---|---|---|---|
| `cli-anything-biddeed` | PUBLIC | YES — auction analysis, XGBoost, CMA, forecaster | ⚠️ REVIEW: contains trade secret logic |
| `biddeed-ai` | PUBLIC | YES — ML models, prediction pipeline | ⚠️ REVIEW: make private |
| `biddeed-ai-ui` | PUBLIC | No — UI only | Low risk |
| `zonewise-scraper-v4` | PRIVATE | YES — scraper logic | OK |
| `biddeed-brain` | PRIVATE | YES — core brain | OK |
| `zonewise-web` | PUBLIC | No — public-facing web | Low risk |
| `zonewise` | PUBLIC | Possible — zoning logic | Review needed |
| `cliproxy-gateway` | PUBLIC | No — infrastructure | Low risk |
| `everest-nexus` | PUBLIC | Possible — nexus tasks | Review needed |
| `everest-stack` | PUBLIC | No — stack configs | Low risk |
| `hermes-agent` | PUBLIC | Possible — agent logic | Review needed |

---

## NDA Requirement

All employees, contractors, and investors who access trade secret assets must sign the
Everest Capital USA NDA (covering ML model weights, parameters, historical datasets,
proprietary algorithms, and customer behavioral data) before receiving access.

Contact: Ariel Shapira (founder@biddeed.ai)

---

*This document must be updated whenever a new trade secret asset is created or a
repo visibility setting changes.*
