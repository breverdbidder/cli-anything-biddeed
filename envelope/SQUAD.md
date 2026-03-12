# 🏔️ ENVELOPE SQUAD — 7 AI Agents

> **Mission:** From raw municipal data → 3D building envelopes → CMA + highest-and-best-use → max bid recommendation. For every parcel in Brevard County.

## The A-Team

```
┌──────────────────────────────────────────────────────────────────────┐
│                   ENVELOPE SQUAD — 7 AGENTS                         │
│                   cli-anything harness · 8 phases                    │
│                   "From Raw Data to Max Bid"                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  🔍 SCOUT             📐 SURVEYOR                                   │
│  Zoning setbacks       Parcel geometry        ← PARALLEL FETCH      │
│  24 zone districts     BCPAO SR2881                                  │
│       │                     │                                        │
│       └──────┬──────────────┘                                        │
│              ▼                                                       │
│       🏗️ ARCHITECT                                                   │
│       Join + compute envelope                 ← TRANSFORM           │
│       GFA / floors / volume                                          │
│              ▼                                                       │
│       🔎 INSPECTOR                                                   │
│       10 QA rules · 70% gate                  ← VALIDATE            │
│              ▼                                                       │
│       💰 CMA ANALYST  ★ THE MONEY AGENT                             │
│       9 HBU scenarios ranked                  ← ANALYZE             │
│       Comps + ARV + NOI + max bid                                    │
│       Confidence scoring                                             │
│              │                                                       │
│       ┌──────┴──────┐                                                │
│       ▼             ▼                                                │
│  🎨 RENDERER   📄 REPORTER                                          │
│  3D scene       CMA one-pagers                ← RENDER + REPORT     │
│  configs        Auction day briefs                                   │
│       │             │                                                │
│       └──────┬──────┘                                                │
│              ▼                                                       │
│         💾 SUPABASE                                                  │
│         envelope_cache + cma_reports          ← LOAD + SERVE        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## 9 HBU Scenarios (Agent 6: CMA Analyst)

| # | Scenario | Method | When It Wins |
|---|----------|--------|-------------|
| 1 | SFR New Build | Sales Comparison | Vacant lot, RS-1 zone, A-grade zip |
| 2 | SFR Rehab/Flip | Sales Comparison | Existing structure, distressed, B+ area |
| 3 | Duplex Development | Income Approach | RM-6+ zone, 7,500+ sf lot |
| 4 | Small Multifamily (3-8 units) | Income Approach | RM-10/15, large lot, high rent area |
| 5 | Mid-Term Rental (Third Sword) | Income Approach | Optimal zips (32937/40/53/03), SFR |
| 6 | Commercial Retail/Office | Income Approach | BU-1/2 zone, main corridor frontage |
| 7 | Mixed Use (Commercial + Resi) | Income Approach | BU-2/CC/TU, downtown/walkable |
| 8 | Vacant Land Hold | Land Residual | Appreciation play, speculative |
| 9 | Tear Down & Rebuild | Land Residual | Obsolete improvement, high land value |

## Max Bid Formula

```
Max Bid = (ARV × 70%) − Development Cost − $10K − MIN($25K, 15% × ARV)
```

Applied per scenario. The winning scenario's max bid becomes the recommended bid.

## Files

```
cli-anything-envelope/
├── cli_anything.envelope.sh          # Main harness (8 phases)
├── SQUAD.md                          # This file
├── agents/
│   ├── scout/zoning_scout.js         # Agent 1: Municipal GIS setbacks
│   ├── surveyor/parcel_surveyor.js   # Agent 2: BCPAO parcel geometry
│   ├── architect/envelope_compute.js # Agent 3: Buildable volume calc
│   ├── renderer/render_samples.js    # Agent 4: Three.js scene configs
│   ├── inspector/qa_inspector.js     # Agent 5: QA validation
│   ├── analyst/cma_analyst.js        # Agent 6: CMA + HBU (THE MONEY AGENT)
│   ├── reporter/report_producer.js   # Agent 7: CMA reports + auction briefs
│   └── loader/supabase_loader.js     # Supabase batch upsert
├── migrations/
│   └── 001_envelope_cache.sql        # Supabase schema + RLS + functions
└── .github/workflows/
    └── envelope-squad.yml            # Weekly automation + Telegram
```

## Cost: $0 incremental
