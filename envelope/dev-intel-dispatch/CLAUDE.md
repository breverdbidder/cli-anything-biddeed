# CLAUDE.md — Development Intelligence Tab Integration

## Identity
You are the Agentic AI Engineer integrating the Development Intelligence tab into zonewise-web.
Repo: `breverdbidder/zonewise-web`
Artifact source: `zonewise-dev-intel-v3.jsx` (947 lines, attached)

## Mission
Ship the ZoneWise.AI Development Intelligence tab — 3D buildable envelope + HBU analysis + max bid calculator — as a production route in zonewise-web with Supabase data, Mapbox maps, BCPAO photos, and split-screen chatbot integration.

## Architecture Context
```
zonewise-web/
├── apps/viewer/src/           ← Vite SPA entry
│   ├── App.tsx
│   ├── main.tsx
│   └── components/
├── packages/ui/src/
│   └── components/
│       ├── chat/              ← SessionViewer, TurnCard
│       └── envelope/          ← ZoneWiseApp, EnvelopeViewer (EXISTING)
├── zonewise/
│   ├── components/web/        ← CraftAgentLayout, AIChatBox, MapboxSatellite
│   ├── hooks/                 ← useChatSessions, useAuth, useMobile
│   ├── pages/                 ← CraftAgent.tsx, Dashboard.tsx, Home.tsx
│   ├── skills/                ← 12 skill files
│   └── lib/development-analysis/
├── vercel.json
└── package.json
```

## Critical Resources

### Supabase
- URL: `https://mocerqjnksmhcjzxrewo.supabase.co`
- Anon key ends: `...klKQDw`
- Service Role ends: `...Tqp9nE`
- Table: `envelope_cache` (migration: `cli-anything-biddeed/envelope/agent-harness/migrations/001_envelope_cache.sql`)
- Views: `envelope_free` (anon), `envelope_pro` (authenticated)

### Mapbox
- Token: `${MAPBOX_TOKEN} (stored in GitHub secrets)`
- Account: everest18
- NOT URL-restricted

### BCPAO Photos
- Pattern: `https://www.bcpao.us/photos/{prefix}/{account}011.jpg`
- prefix = first 4 chars of parcel_id
- account = parcel_id with dashes/dots removed
- Fallback: gradient placeholder

### Brand
- Navy: #1E3A5F
- Orange: #F59E0B
- Slate bg: #020617
- Font: Inter (Google Fonts)

### GitHub
- PAT4: `${GH_PAT} (stored in GitHub secrets)` (no expiry)
- Repo: `breverdbidder/zonewise-web`

## 6 Deliverables (from TODO.md)

1. **Wire Supabase envelope_cache** — Replace demo data with real Supabase queries
2. **Add Mapbox mini-map** — Static API image on detail view + interactive GL on grid
3. **Connect CMA Analyst agent** — Real HBU scores from envelope squad output
4. **Add BCPAO photo URLs** — Card thumbnails from BCPAO masterPhotoUrl
5. **Deploy as /explore route** — New page in zonewise-web SPA routing
6. **Integrate split-screen** — Right panel with chatbot on left

## Execution Rules
1. **TODO.md is law.** Load it. Find current unchecked task. Execute. Mark [x]. Push.
2. **Zero human actions.** Ariel does NOTHING.
3. **$10/session max.** No paid API calls beyond Max plan.
4. **Test before push.** `bun run build` must pass before any commit.
5. **Exact values only.** No invented data. No fake parcel IDs.
6. **NEVER-LIE.** Don't say "done" without proving it with a build log or screenshot.
7. **SESSION HYGIENE:** Mandatory plugins Context7 + CC Status Line. Kill at 50% context.

## File Placement Guide

| Component | Target Path |
|-----------|-------------|
| DevIntelPage (route) | `zonewise/pages/Explore.tsx` |
| DevIntelTab (main) | `packages/ui/src/components/envelope/DevIntelTab.tsx` |
| HBUEngine | `zonewise/lib/development-analysis/hbu-engine.ts` |
| EnvelopeRenderer | `packages/ui/src/components/envelope/Envelope3D.tsx` |
| ParcelCard | `packages/ui/src/components/envelope/ParcelCard.tsx` |
| ComparePanel | `packages/ui/src/components/envelope/ComparePanel.tsx` |
| Supabase fetch | `zonewise/hooks/useEnvelopeData.ts` |
| Types | `zonewise/lib/development-analysis/types.ts` |

## HBU Engine Spec (from V3 artifact)

The artifact contains a fully working `calculateHBU()` function. Extract it to `hbu-engine.ts` with these data tables:
- `CONSTRUCTION_COSTS` — 10 building types × low/mid/high $/sf (Brevard 2025-2026)
- `MARKET_DATA` — rent $/sf, cap rates, ARV multipliers by use type
- `ZONE_PERMITTED` — permitted/conditional/prohibited uses per zone
- `MIN_LOT_REQS` — minimum lot width/area/frontage per use type

The 4-test scoring:
- **Legal** = zoning permits (95 permitted, 60 conditional) - flood penalty
- **Physical** = lot dims vs minimums + aspect ratio + utilities + topography
- **Financial** = NOI/capRate projected value vs total investment → ROI brackets
- **Maximal** = weighted composite (20% legal + 20% physical + 60% financial)

Max bid formula per scenario: `(ARV × 0.7) - repairs - $10K - MIN($25K, ARV × 0.15)`

## Split-Screen Integration Pattern

```
┌──────────────────────┬───────────────────────────────────────────────┐
│                      │  ┌─────────┬──────────┬──────────┐           │
│  🤖 AI CHATBOT       │  │ 3D ENV  │ HBU      │ FACTS    │  ← tabs  │
│  (Left Panel)        │  ├─────────┴──────────┴──────────┤           │
│                      │  │                                │           │
│  "What can I build   │  │  [DevIntelTab Component]      │           │
│   at 625 Ocean St?"  │  │                                │           │
│                      │  │  3D envelope + sliders +       │           │
│  ZoneWise: Based on  │  │  HBU scenarios + max bid +     │           │
│  R-1 zoning...       │  │  comparison mode               │           │
│                      │  │                                │           │
├──────────────────────┤  │                                │           │
│  🎤 Type or speak... │  └────────────────────────────────┘           │
└──────────────────────┴───────────────────────────────────────────────┘
```

Chat events trigger tab updates:
- User asks about a parcel → right panel loads that parcel's detail view
- User asks "compare 625 Ocean and 1200 S Patrick" → comparison mode activates
- User asks "what if height was 80ft" → slider adjusts automatically

## CMA Analyst Agent Connection

The Envelope Squad's CMA Analyst (`cli-anything-biddeed/envelope/agent-harness/agents/analyst/cma_analyst.js`) outputs JSON to `cma_reports` Supabase table. Schema:

```sql
-- If cma_reports doesn't exist yet, create it:
CREATE TABLE IF NOT EXISTS cma_reports (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  parcel_id TEXT NOT NULL,
  hbu_scenarios JSONB NOT NULL,  -- array of scenario objects
  best_use TEXT,
  best_score INTEGER,
  max_bid_amount NUMERIC,
  computed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(parcel_id)
);
```

When `cma_reports` has data for a parcel, use those scores instead of client-side calculateHBU(). Client-side engine is the fallback for parcels not yet processed by the squad.

```typescript
// In useEnvelopeData.ts:
async function fetchHBU(parcelId: string) {
  const { data } = await supabase
    .from('cma_reports')
    .select('hbu_scenarios, best_use, best_score, max_bid_amount')
    .eq('parcel_id', parcelId)
    .single()
  if (data?.hbu_scenarios) return data.hbu_scenarios // Server-computed
  // Fallback to client-side engine
  return calculateHBU(parcel, envelope)
}
```
