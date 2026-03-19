# TODO.md — Development Intelligence Tab Integration

## Pre-Flight
- [ ] Clone zonewise-web repo, `bun install`, verify `bun run build` passes
- [ ] Verify Supabase connection: `curl -s -H "apikey: {ANON_KEY}" "https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1/envelope_cache?select=count" -H "Prefer: count=exact"`
- [ ] Verify envelope_cache table exists and has rows. If 0 rows, run envelope squad on Palm Bay first
- [ ] Copy `zonewise-dev-intel-v3.jsx` artifact into working directory as reference

---

## Deliverable 1: Wire Supabase envelope_cache
- [ ] Create `zonewise/lib/development-analysis/types.ts` — TypeScript interfaces for Parcel, Envelope, HBUScenario, CMAReport
- [ ] Create `zonewise/hooks/useEnvelopeData.ts` — Supabase fetch hook with:
  - `fetchParcels(search, limit)` → query envelope_cache with ilike search
  - `fetchParcelById(parcelId)` → single parcel fetch
  - `fetchHBU(parcelId)` → cma_reports with client-side fallback
  - Loading/error/retry state management
  - Column mapping from envelope_cache → Parcel type (use mapRow from V3 artifact)
- [ ] Create `zonewise/lib/development-analysis/hbu-engine.ts` — Extract from V3:
  - `CONSTRUCTION_COSTS` table (10 types × low/mid/high)
  - `MARKET_DATA` table (rent, cap rates, ARV multipliers)
  - `ZONE_PERMITTED` map (permitted/conditional/prohibited)
  - `MIN_LOT_REQS` map (min width/area/frontage)
  - `calculateHBU(parcel, envelope)` → HBUScenario[]
  - `computeEnvelope(params)` → Envelope
  - Max bid formula: `(ARV×0.7) - repairs - $10K - MIN($25K, ARV×0.15)`
- [ ] Verify: import useEnvelopeData in a test component, confirm data loads
- [ ] If cma_reports table doesn't exist, run migration SQL from CLAUDE.md
- [ ] `bun run build` passes
- [ ] Git commit: `feat(explore): wire Supabase envelope_cache + HBU engine`

---

## Deliverable 2: Add Mapbox mini-map
- [ ] Install mapbox-gl if not already: `bun add mapbox-gl @types/mapbox-gl`
- [ ] Create `packages/ui/src/components/envelope/MiniMap.tsx`:
  - Static API image for card grid (low bandwidth, fast load)
  - Interactive GL map for detail view with parcel pin
  - Token from env var `VITE_MAPBOX_TOKEN` or fallback to hardcoded
  - Dark style: `mapbox://styles/mapbox/dark-v11`
  - Orange pin marker at parcel lat/lng
  - Zoom 15 for detail, zoom 12 for grid overview
- [ ] Add to detail view header (above address, below nav)
- [ ] `bun run build` passes
- [ ] Git commit: `feat(explore): add Mapbox mini-map to parcel detail`

---

## Deliverable 3: Connect CMA Analyst agent
- [ ] Verify cma_reports table exists in Supabase
- [ ] In `useEnvelopeData.ts`, implement `fetchHBU()`:
  - Query cma_reports by parcel_id
  - If server data exists → use hbu_scenarios JSONB directly
  - If no server data → fall back to client-side calculateHBU()
  - Cache results in React state to avoid re-fetching
- [ ] Add visual indicator: "AI-Computed" badge when using server scores vs "Estimated" for client-side
- [ ] `bun run build` passes
- [ ] Git commit: `feat(explore): connect CMA analyst agent scores with client fallback`

---

## Deliverable 4: Add BCPAO photo URLs
- [ ] In `mapRow()` function, generate photo URL:
  ```typescript
  const prefix = parcel_id?.substring(0, 4) || ''
  const account = parcel_id?.replace(/[-.]/g, '') || ''
  const photo = row.bcpao_photo_url || `https://www.bcpao.us/photos/${prefix}/${account}011.jpg`
  ```
- [ ] In ParcelCard component, use `<img>` with:
  - `src={parcel.photo}`
  - `onError` fallback to gradient placeholder
  - `loading="lazy"` for performance
  - Object-fit cover, rounded top corners
- [ ] Test with known valid parcel IDs to verify URL pattern works
- [ ] `bun run build` passes
- [ ] Git commit: `feat(explore): BCPAO satellite photos on parcel cards`

---

## Deliverable 5: Deploy as /explore route
- [ ] Create `zonewise/pages/Explore.tsx`:
  ```typescript
  import { DevIntelTab } from '@craft-agent/ui/components/envelope/DevIntelTab'
  export default function ExplorePage() {
    return <DevIntelTab />
  }
  ```
- [ ] Split V3 artifact into component files per CLAUDE.md File Placement Guide:
  - `DevIntelTab.tsx` — main orchestrator (grid + detail + compare)
  - `Envelope3D.tsx` — Three.js renderer (extract from V3)
  - `ParcelCard.tsx` — grid card component
  - `ComparePanel.tsx` — multi-select comparison bottom panel
  - `ParamSliders.tsx` — What-If controls
  - `ScoreBar.tsx`, `Stat.tsx`, `MiniMap.tsx` — small shared components
- [ ] Add route to SPA router:
  - If React Router: add `<Route path="/explore" element={<ExplorePage />} />`
  - If React Router + parcel deep link: `<Route path="/explore/:parcelId" element={<ExplorePage />} />`
  - If file-based: create appropriate file in pages/
- [ ] Add "Explore" link to main navigation (CraftAgentLayout sidebar or header)
- [ ] Add Inter font import to root CSS or HTML head:
  ```html
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
  ```
- [ ] Verify route works: navigate to /explore, see parcel grid
- [ ] Verify deep link works: /explore/25-37-03-00-00123.0 loads that parcel's detail
- [ ] `bun run build` passes
- [ ] `bun run preview` — visual check on localhost
- [ ] Git commit: `feat(explore): deploy Development Intelligence as /explore route`
- [ ] Push to main → Vercel auto-deploys

---

## Deliverable 6: Integrate split-screen with chatbot
- [ ] Locate existing split-screen layout: `zonewise/components/web/CraftAgentLayout.tsx` or `SplitScreenLayout`
- [ ] Create `zonewise/components/web/ExploreWithChat.tsx`:
  - Left panel: AIChatBox (existing component)
  - Right panel: DevIntelTab
  - Communication via shared state or event bus:
    ```typescript
    // When chat mentions a parcel address:
    onChatMessage={(msg) => {
      const parcelMatch = extractParcelFromMessage(msg)
      if (parcelMatch) setSelectedParcel(parcelMatch)
    }}
    ```
- [ ] Wire chat intents to right panel actions:
  - "show envelope for {address}" → load parcel detail, 3D tab
  - "compare {address1} and {address2}" → activate comparison mode
  - "what if height was {N}" → adjust slider value
  - "what's the HBU for {address}" → load parcel detail, HBU tab
- [ ] Update /explore route to use ExploreWithChat as layout when screen > 1024px
  - Mobile: full-screen DevIntelTab with floating chat button
  - Desktop: 40/60 split (chat/content)
- [ ] `bun run build` passes
- [ ] Git commit: `feat(explore): split-screen chatbot + development intelligence`
- [ ] Push to main

---

## Post-Deploy Verification
- [ ] Visit production URL, navigate to /explore
- [ ] Search for a real address → verify Supabase data loads
- [ ] Click parcel card → verify 3D envelope renders
- [ ] Drag/rotate 3D model → verify orbit controls
- [ ] Adjust What-If sliders → verify 3D updates live
- [ ] Click Compare Scenarios → verify side-by-side
- [ ] Check HBU tab → verify 4-test scores + max bid
- [ ] Check Mapbox mini-map loads with parcel pin
- [ ] Check BCPAO photo on at least 1 card
- [ ] Test on mobile (responsive)
- [ ] Enable comparison mode (2+ checkboxes) → verify bottom panel
- [ ] Click Share → verify clipboard has full analysis text
- [ ] If split-screen: type "show envelope for 625 Ocean St" in chat → verify right panel updates
