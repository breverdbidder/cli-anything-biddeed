# EVEREST-BTR Squad Specification

## CLI-Anything Agent Army — Build-to-Rent + Distressed Assets

**Codename:** EVEREST-BTR
**Date:** March 11, 2026
**Author:** Claude AI Architect
**Repo:** `breverdbidder/cli-anything-biddeed/btr/`

---

## Agent Registry (10 Agents)

| # | Agent ID | Name | Scenario |
|---|----------|------|----------|
| 1 | cli_btr.commander | Squad Commander | Orchestrator |
| 2 | cli_btr.land | Land Acquisition Agent | Scenario 1 |
| 3 | cli_btr.con | Construction Funding Agent | Scenario 2 |
| 4 | cli_btr.perm | Permanent Funding Agent | Scenario 3 |
| 5 | cli_btr.rehab | Distressed Asset Rehab Agent | Scenario 4 |
| 6 | cli_btr.mai | MAI Valuation Engine | Shared Intelligence |
| 7 | cli_btr.hbu | Highest & Best Use Agent | Shared Intelligence |
| 8 | cli_btr.cost | Construction Cost Estimator | Shared Intelligence |
| 9 | cli_btr.lv | Lender Vetting & Scoring | Shared Intelligence |
| 10 | cli_btr.proforma | Pro Forma Generator | Shared Intelligence |

## Property Type Tabs

- **SFR** — Single Family Residential
- **Duplex** — 2-Unit
- **Multifamily** — 5+ Units

## 4 Investment Scenarios

1. **Land Acquisition** — Raw land evaluation, zoning, entitlements
2. **Construction Funding** — Budget modeling, draw schedules, lender terms
3. **Permanent Funding** — DCR analysis, rate lock, prepay structure
4. **Distressed Asset Rehab** — Foreclosure + major renovation + HBU conversion

## MAI Valuation Engine

3-approach method: Income (Direct Cap + DCF), Sales Comparison, Cost Approach.
Reconciliation weights vary by property type.

## Open-Source Integrations

- OpenMud (MIT) — Construction cost estimation
- OpenConstructionEstimate — Multilingual cost DB
- ai-real-estate-assistant — RAG + valuation
- ai-underwriting — Document extraction
- LangGraph — Multi-agent orchestration
- ZoneWise Scraper V4 — Zoning intelligence (internal)
- cli-anything-spatial — Shapely STRtree (internal)

## Tests

23/23 passing. Covers all 10 agents with decision logic, formula verification, and CLI integration tests.

## Deployment Roadmap

- Phase 1 (W1-2): Commander + MAI + HBU
- Phase 2 (W3-4): Land + Cost Estimator
- Phase 3 (W5-6): Construction + Perm Funding
- Phase 4 (W7-8): Rehab + Lender Vet
- Phase 5 (W9-10): Pro Forma + Full Integration

See `BTR_Squad_Spec.docx` for full ASCII architecture diagrams and detailed agent cards.
