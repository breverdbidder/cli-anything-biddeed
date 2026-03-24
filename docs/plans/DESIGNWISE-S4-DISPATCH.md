# DesignWise S4 — Parity Sprint Dispatch

## SCORE: 4.2/10 → TARGET 8.5+/10

## PHASE 1: CRITICAL FIXES (30min)

### P1A: Fix missing exports — `lib/explorer/constants.ts`
ExplorerV2.tsx imports these but they DON'T EXIST in the file:
- `ZONING_FILTERS` (array of filter options)
- `FREE_PARCEL_CLICKS` (number: 5)
- `FREE_CHAT_MESSAGES` (number: 3)
- `ChoroplethMetric` (type: 'zhvi' | 'zori' | 'yoy')
- `ZoningFilter` (type: 'all' | 'RU' | 'BU' | ...)
- `CHOROPLETH_COLOR_STOPS` (array of [value, color])

ADD all missing exports to `lib/explorer/constants.ts`.
This is the #1 reason Explorer shows infinite spinner — JS crash on missing import.

### P1B: Fix /demo.html 404
Homepage hero links to `/demo.html` which returns 404.
In `next.config.mjs` add rewrite: `{ source: '/demo.html', destination: '/explorer' }`
Also add: `{ source: '/demo', destination: '/explorer' }`

### P1C: Fix AnimatedSection opacity:0
All `<AnimatedSection>` render with `style="opacity:0;transform:translateY(40px)"`.
If framer-motion fails to hydrate, ALL CONTENT IS INVISIBLE.
Add CSS fallback:
```css
@media (prefers-reduced-motion: reduce) {
  [style*="opacity: 0"] { opacity: 1 !important; transform: none !important; }
}
```
And add a `useEffect` that sets opacity:1 after 3s as safety net.

### P1 GATE: `npm run build` must pass with zero errors.

## PHASE 2: EXPLORER FULL STACK (45min)

### P2A: Verify ExplorerMap renders
After P1A fix, ExplorerV2 should stop crashing.
- `NEXT_PUBLIC_MAPBOX_TOKEN` is in Vercel env ✅
- `getMapboxToken()` in `lib/feasibility/constants.ts` reads it ✅
- Open /explorer → map tiles load → choropleth colors ZIP codes
- If still failing: check browser console for errors, fix one by one

### P2B: Chat → Claude API streaming
Route exists: `app/api/explorer/chat/route.ts`
- Uses `import Anthropic from '@anthropic-ai/sdk'`
- `ANTHROPIC_API_KEY` in Vercel env ✅
- System prompt already has Brevard County context + MAP commands
- ExplorerChat.tsx needs to POST to `/api/explorer/chat` and stream
- Test: type "What zoning is Satellite Beach?" → streaming response

### P2C: MAP command parsing in ExplorerChat.tsx
Chat route outputs `[MAP:FLY 28.18,-80.59,13]` commands.
ExplorerChat needs regex parser to extract and call:
```typescript
const MAP_CMD = /\[MAP:(FLY|CHOROPLETH|FILTER)\s+([^\]]+)\]/g
```
Then call `mapRef.current?.flyTo()` etc.

### P2D: Wire quick-action chips on landing page
Chips: "View 3D Envelope", "Check HBU", "Run CMA"
Change from `<span>` to `<a href="/explorer?q=view+3d+envelope">` 
Or seed chat: `<a href="/explorer?chat=What+is+the+building+envelope+for+this+parcel">`

### P2 GATE: E2E test — open /explorer, click parcel, send chat, verify map action.

## PHASE 3: LANDING PAGE POLISH (30min)

### P3A: Counter animation
Values hardcoded in page.tsx: `<AnimatedCounter end={67} />`
Uses framer-motion `useInView`. Should work once JS hydrates.
If not: add `setTimeout(() => setCount(end), 3000)` fallback.

### P3B: Hero opacity fix
All `<AnimatedSection>` start at opacity:0. If JS fails, page is blank.
FIX: Remove inline `style="opacity:0"` and use framer-motion's `initial/animate` props.
Or add global CSS: `.hydrated [data-animated] { opacity: 1; }`

### P3C: Chat demo skeleton
The static chat mockup is good but add a subtle typing indicator animation.

### P3D: Link cleanup
- Pricing link in nav: verify `/pricing` → confirm 
- Demo link: now redirects to /explorer (P1B)
- All CTAs: verify href targets resolve

### P3 GATE: All sections visible, counters animate, no dead buttons.

## PHASE 4: SEO (20min)

### P4A: JSON-LD structured data
Add to `app/layout.tsx`:
```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "ZoneWise.AI",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web",
  "description": "AI-powered zoning intelligence for Florida real estate",
  "url": "https://zonewise.ai",
  "author": { "@type": "Organization", "name": "Everest Capital USA" }
}
```

### P4B: Unique meta descriptions per route
- / : "AI-powered zoning intelligence for all 67 Florida counties..."
- /explorer : "Interactive map of 262K+ Brevard County parcels with AI chat..."
- /pricing : "ZoneWise.AI pricing — Free, Starter $39/mo, Pro $99/mo..."

### P4C: OG images per route (use existing opengraph-image)

### P4D: Google Search Console — programmatic verification
- `google-site-verification` meta tag already exists in HTML ✅
- Submit sitemap URL: https://zonewise.ai/sitemap.xml

### P4 GATE: Lighthouse SEO > 90.

## PHASE 5: SPLIT-SCREEN UX PARITY (30min)

### P5A: Resizable chat panel
Add CSS `resize: horizontal` or a drag handle with mouse event.
Claude AI / Manus both have resizable panels.

### P5B: Chat ↔ Map bidirectional sync
When chat says `[MAP:FLY ...]` → map moves.
When user clicks parcel on map → inject context into chat:
"You're looking at parcel [ID] at [address]. Zoning: [code]."

### P5C: Report/artifact panel
When chat generates analysis (multi-parcel comparison, CMA):
Show in a right-side panel or expandable section.

### P5D: Keyboard shortcuts
- `Cmd+K` or `/` → focus chat input
- `Esc` → close modals/panels
- `Tab` → switch between map and chat

### P5 GATE: Split-screen feels like Claude AI chat interface.

## PHASE 6: BUILD + DEPLOY (15min)

1. `npm run build` → ZERO errors
2. Git commit per phase (6+ commits)
3. `vercel alias set [READY_URL] zonewise.ai`
4. Telegram heartbeat every 10min during session
5. Re-run benchmark evaluation → score 8.5+/10

## SCORING RUBRIC (target per dimension)

| Dimension | Current | Target | Notes |
|-----------|---------|--------|-------|
| Explorer functionality | 0/10 | 9/10 | Map + chat + commands |
| Landing page | 5/10 | 9/10 | Animations + counters + no dead links |
| Chat/AI | 0/10 | 8/10 | Streaming Claude + map commands |
| SEO | 2/10 | 9/10 | Structured data + meta + sitemap |
| UX parity | 3/10 | 8/10 | Split-screen + resize + keyboard |
| Brand | 8/10 | 9/10 | Already strong |
| Auth | 8/10 | 8/10 | Clerk works |
| Performance | 7/10 | 8/10 | TTFB < 0.5s already |
| Mobile | 5/10 | 8/10 | Bottom sheet exists, needs testing |
| Pricing | 9/10 | 9/10 | Free/$39/$99 live |
| **TOTAL** | **4.7** | **8.5** | |
