# ZONEWISE CONQUEST — Autonomous Operations Architecture

**Date:** 2026-03-20
**Decisions:** Real-time dashboard, Full Telegram bot, Cron + On-demand, Modal parallel
**Quality Gate:** 85%+ parcel ID match rate per county or REJECT
**Zero-HITL:** Everything automated. Ariel monitors via Telegram + Dashboard.

---

## SYSTEM TOPOLOGY

```
┌──────────────────── TRIGGER LAYER ──────────────────────┐
│                                                          │
│  TELEGRAM BOT          NIGHTLY CRON        SENTINEL      │
│  /conquer orange       2AM EST auto-pick   every 5min    │
│  /status brevard       next priority       auto-heal     │
│  /gaps                 county              failures      │
│  /quality 48                                             │
│                                                          │
└────────┬───────────────────┬──────────────────┬──────────┘
         │                   │                  │
         ▼                   ▼                  ▼
┌──────────────────── EXECUTION LAYER ────────────────────┐
│                                                          │
│  GitHub Actions (cli-anything-biddeed)                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │ summit-conquest-engine.yml (MASTER ORCHESTRATOR)    │  │
│  │  Stage 1: DOR baseline via FL GIO    → zone_conf=LOW│  │
│  │  Stage 2: Modal parallel GIS spatial → zone_conf=HI │  │
│  │  Stage 3: Firecrawl gap fill         → zone_conf=MED│  │
│  │  Stage 4: Quality gate (85%+ or REJECT)             │  │
│  │  Stage 5: Write to Supabase + notify                │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │ MODAL.COM — Parallel Spatial Engine                 │  │
│  │                                                     │  │
│  │  multi_county_orchestrator()                        │  │
│  │    ├── county_orchestrator(orange)  ← 5K chunk .map │  │
│  │    │     ├── spatial_zoner(chunk_0) ← STRtree       │  │
│  │    │     ├── spatial_zoner(chunk_1)                  │  │
│  │    │     └── ... (N containers)                      │  │
│  │    ├── county_orchestrator(duval)                    │  │
│  │    └── ... parallel per county                      │  │
│  │                                                     │  │
│  │  Performance: 78K parcels ~5 min, 67 counties ~15min│  │
│  │  Cost: ~$0.02/county ($1.50 total for all 67)       │  │
│  │  Quality: 85%+ match_rate or REJECT + notify        │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                          │
│  Hetzner 87.99.129.125 — SUMMIT dispatch for Claude Code │
│  (GIS endpoint discovery, complex spatial joins)          │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────── DATA LAYER ─────────────────────────┐
│                                                          │
│  Supabase (mocerqjnksmhcjzxrewo.supabase.co)            │
│                                                          │
│  TABLES:                                                 │
│  ┌──────────────────────────────────────────────────┐    │
│  │ fl_counties (67)           ← static reference     │    │
│  │ county_conquest_status (67)← live stats per county│    │
│  │ county_jurisdictions (N)   ← per-municipality     │    │
│  │ zoning_assignments (→10M)  ← core zoning data     │    │
│  │ sample_properties (→10M)   ← FL GIO parcel data   │    │
│  │ conquest_events (NEW)      ← audit log + webhook   │    │
│  │ gis_endpoint_registry (NEW)← county GIS URLs       │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  REALTIME ENABLED:                                       │
│  → county_conquest_status (dashboard live updates)       │
│  → conquest_events (triggers Telegram notifications)     │
│                                                          │
│  RPC FUNCTIONS:                                          │
│  → get_county_dashboard(co_no)                           │
│  → refresh_county_stats(co_no)                           │
│  → get_next_conquest_target() ← auto-pick priority       │
│  → log_conquest_event(co_no, event, data)                │
│  → get_quality_report(co_no) ← match rate + gaps         │
│                                                          │
└────────────────────────┬─────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ DASHBOARD    │  │ TELEGRAM     │  │ SUPABASE     │
│ zonewise.ai  │  │ Notifier     │  │ Edge Func    │
│ /conquest    │  │              │  │              │
│              │  │ Post-run:    │  │ Webhook:     │
│ Supabase     │  │ Rich stats   │  │ /conquer     │
│ Realtime     │  │ + match rate │  │ /status      │
│ client-side  │  │ + gap count  │  │ /gaps        │
│ subscript.   │  │ + dashboard  │  │ /quality     │
│              │  │   link       │  │ Dispatches   │
│ Auto-update  │  │              │  │ GHA via API  │
│ no refresh   │  │ Quality fail:│  │              │
│              │  │ ⚠️ ALERT     │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## QUALITY GATE: 85%+ MATCH RATE

The most critical component. Every county conquest MUST pass this gate before data is committed.

### Definition
```
match_rate = (parcels_with_real_zone_code / total_parcels_in_county) × 100

PASS:   match_rate >= 85%  → Write to Supabase, notify success
REVIEW: match_rate 70-84%  → Write to Supabase with flag, notify warning  
REJECT: match_rate < 70%   → DO NOT write, notify failure, log to conquest_events
```

### What counts as "real zone code":
- GIS-sourced zone code (from county/municipal ArcGIS endpoint) → HIGH confidence
- STRtree spatial join match (parcel centroid inside zoning polygon) → HIGH confidence
- DOR USE_CODE crosswalk → LOW confidence (does NOT count toward 85% gate)

### Quality flow in Modal:
```python
@app.function(timeout=600)
def county_orchestrator(county, chunk_size, ...):
    # ... run all spatial_zoner chunks ...
    
    match_rate = total_matched / total_parcels * 100
    
    result = {
        "county": county,
        "total_parcels": total_parcels,
        "gis_matched": gis_count,         # HIGH confidence
        "spatial_matched": spatial_count,  # HIGH confidence  
        "usecode_only": usecode_count,     # LOW confidence (backup)
        "unmatched": unmatched_count,
        "match_rate_pct": match_rate,      # gis + spatial only
        "quality_gate": "PASS" if match_rate >= 85 else "REVIEW" if match_rate >= 70 else "REJECT",
    }
    
    if result["quality_gate"] == "REJECT":
        # DO NOT write to production tables
        log_conquest_event(county, "QUALITY_REJECT", result)
        telegram_alert(f"⚠️ {county}: REJECTED — {match_rate:.1f}% match rate (need 85%+)")
        return result
    
    # Write results
    supabase_bulk_writer.remote(all_results, ...)
    
    # For REVIEW, also write DOR baseline as fallback for unmatched
    if result["quality_gate"] == "REVIEW":
        write_dor_fallback_for_unmatched(county, ...)
    
    return result
```

### Per-county quality tracking (Supabase):
```sql
-- In county_conquest_status
ALTER TABLE county_conquest_status ADD COLUMN IF NOT EXISTS
  match_rate_pct    NUMERIC(5,1) DEFAULT 0,
  quality_gate      TEXT DEFAULT 'pending',  -- pass/review/reject/pending
  gis_matched       INTEGER DEFAULT 0,
  spatial_matched   INTEGER DEFAULT 0,
  usecode_fallback  INTEGER DEFAULT 0,
  last_run_at       TIMESTAMPTZ,
  last_run_duration INTEGER;  -- seconds
```

---

## COMPONENT 1: TELEGRAM COMMAND BOT

### Implementation: Supabase Edge Function + Telegram Webhook

Edge function responds in <500ms. Dispatches GHA for heavy work.

### Commands:

| Command | Action | Response |
|---------|--------|----------|
| `/conquer orange` | Dispatch full conquest pipeline for Orange County | "🏔️ Conquering Orange County... Stage 1/5 starting" |
| `/conquer 48 --full` | Same, by DOR number with full pipeline | Same |
| `/status brevard` | Query county_conquest_status | "Brevard: 93.3% (327,882/351,424) — 3 gaps remaining" |
| `/status` | All counties with >0% progress | Compact table of active conquests |
| `/gaps` | Counties with lowest coverage | "Top gaps: Orange 0%, Duval 0%, Hillsborough 0%..." |
| `/gaps brevard` | Jurisdictions with gaps in Brevard | "Melbourne: 10,626 gap, Uninc: 19,303 gap..." |
| `/quality 48` | Quality report for last Orange run | "Orange: 87.2% PASS — 456K GIS, 23K spatial, 12K gaps" |
| `/next` | Show auto-pick priority queue | "Next: Orange (1.4M pop) → Duval (1M) → Hillsborough (1.5M)" |
| `/cost` | Modal + API spend this month | "Modal: $1.23, Firecrawl: $4.50, Total: $5.73" |

### Edge Function (Supabase):
```typescript
// supabase/functions/conquest-bot/index.ts
import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'

const GITHUB_PAT = Deno.env.get('GITHUB_PAT')!
const TG_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN')!

serve(async (req) => {
  const { message } = await req.json()
  const text = message?.text || ''
  const chatId = message?.chat?.id
  
  if (text.startsWith('/conquer ')) {
    const county = text.replace('/conquer ', '').trim()
    // Dispatch GHA workflow
    await fetch('https://api.github.com/repos/breverdbidder/cli-anything-biddeed/actions/workflows/summit-conquest-engine.yml/dispatches', {
      method: 'POST',
      headers: { Authorization: `token ${GITHUB_PAT}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'main', inputs: { county } })
    })
    return reply(chatId, `🏔️ Conquering ${county}... Pipeline dispatched.`)
  }
  
  if (text.startsWith('/status')) { /* query county_conquest_status */ }
  if (text.startsWith('/gaps'))   { /* query county_jurisdictions */ }
  if (text.startsWith('/quality')){ /* query conquest_events */ }
  if (text === '/next')           { /* call get_next_conquest_target() RPC */ }
})
```

### Setup:
1. Deploy edge function: `supabase functions deploy conquest-bot`
2. Set Telegram webhook: `https://api.telegram.org/bot{TOKEN}/setWebhook?url={EDGE_FUNC_URL}`
3. Secrets: GITHUB_PAT, TELEGRAM_BOT_TOKEN in Supabase vault

---

## COMPONENT 2: NIGHTLY CRON AUTO-CONQUEST

### GHA Workflow: `zonewise-nightly.yml`

Runs at 2AM EST every night. Auto-picks next priority county and conquers it.

```yaml
name: "ZoneWise Nightly Auto-Conquest"
on:
  schedule:
    - cron: '0 7 * * *'  # 2AM EST = 7AM UTC
  workflow_dispatch: {}

jobs:
  auto-conquer:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install httpx modal
      
      - name: "Pick next county"
        id: pick
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          NEXT=$(python -c "
          import httpx, json, os
          h = {'apikey': os.environ['SUPABASE_KEY'], 'Authorization': f'Bearer {os.environ[\"SUPABASE_KEY\"]}'}
          r = httpx.post(f'{os.environ[\"SUPABASE_URL\"]}/rest/v1/rpc/get_next_conquest_target', headers=h, json={})
          data = r.json()
          print(json.dumps(data))
          ")
          echo "county=$(echo $NEXT | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"slug\"])')" >> $GITHUB_OUTPUT
          echo "co_no=$(echo $NEXT | python3 -c 'import sys,json; print(json.load(sys.stdin)[\"co_no\"])')" >> $GITHUB_OUTPUT

      - name: "Stage 1: DOR Baseline"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/ingest_county.py --county ${{ steps.pick.outputs.co_no }} --full

      - name: "Stage 2: Modal Parallel Spatial"
        env:
          MODAL_TOKEN_ID: ${{ secrets.MODAL_TOKEN_ID }}
          MODAL_TOKEN_SECRET: ${{ secrets.MODAL_TOKEN_SECRET }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: |
          cd modal-spatial
          modal run modal_app.py --county ${{ steps.pick.outputs.county }}

      - name: "Stage 3: Quality Gate"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/quality_gate.py --county ${{ steps.pick.outputs.co_no }}
```

### Priority algorithm (`get_next_conquest_target` RPC):
```sql
CREATE OR REPLACE FUNCTION get_next_conquest_target()
RETURNS JSON AS $$
  SELECT row_to_json(t) FROM (
    SELECT c.co_no, c.name, c.slug, c.total_parcels,
           COALESCE(s.coverage_pct, 0) as current_pct,
           COALESCE(s.quality_gate, 'pending') as quality_gate
    FROM fl_counties c
    LEFT JOIN county_conquest_status s ON c.co_no = s.co_no
    WHERE COALESCE(s.status, 'pending') != 'complete'
      AND COALESCE(s.quality_gate, 'pending') != 'reject'
    ORDER BY 
      -- Priority 1: In-progress counties (finish what we started)
      CASE WHEN COALESCE(s.status, 'pending') = 'in_progress' THEN 0 ELSE 1 END,
      -- Priority 2: Orange (48) and Duval (16) explicitly next
      CASE WHEN c.co_no IN (48, 16) THEN 0 ELSE 1 END,
      -- Priority 3: Largest population first
      c.total_parcels DESC NULLS LAST
    LIMIT 1
  ) t;
$$ LANGUAGE sql SECURITY DEFINER;
```

---

## COMPONENT 3: REAL-TIME DASHBOARD (zonewise.ai/conquest)

### Stack:
- **Framework:** Next.js 16 (already in zonewise-web)
- **Real-time:** `@supabase/supabase-js` Realtime subscriptions (already installed v2.95.3)
- **Styling:** Tailwind (existing) + House brand colors
- **Deployment:** Vercel Pro auto-deploy on push

### Real-time wiring:
```typescript
// lib/conquest-realtime.ts
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

export function subscribeToConquest(onUpdate: (payload: any) => void) {
  return supabase
    .channel('conquest-live')
    .on('postgres_changes', {
      event: '*',
      schema: 'public', 
      table: 'county_conquest_status'
    }, onUpdate)
    .on('postgres_changes', {
      event: 'INSERT',
      schema: 'public',
      table: 'conquest_events'
    }, onUpdate)
    .subscribe()
}
```

### Pages:
```
zonewise.ai/conquest              → 67-county statewide overview
zonewise.ai/conquest/brevard      → Brevard detail + jurisdictions
zonewise.ai/conquest/orange       → Orange detail (live during conquest)
```

### What the dashboard shows in real-time:
- County cards with live % updating as Modal writes batches
- Quality gate badge (PASS/REVIEW/REJECT) after each run
- Active conquest indicator (pulsing dot when GHA running)
- Last run timestamp + duration + match rate
- Jurisdiction-level drill-down with gap analysis

---

## COMPONENT 4: GIS ENDPOINT REGISTRY

For Modal to use real GIS zoning (not just DOR baseline), each county needs discovered endpoints.

### New table:
```sql
CREATE TABLE IF NOT EXISTS gis_endpoint_registry (
  id              SERIAL PRIMARY KEY,
  co_no           INTEGER NOT NULL REFERENCES fl_counties(co_no),
  jurisdiction    TEXT NOT NULL,
  endpoint_url    TEXT NOT NULL,
  endpoint_type   TEXT DEFAULT 'arcgis_rest',  -- arcgis_rest, wfs, geojson
  zone_field      TEXT NOT NULL,               -- field name containing zone code
  parcel_field    TEXT,                         -- field for parcel/tax ID matching
  verified        BOOLEAN DEFAULT false,
  record_count    INTEGER,
  last_tested     TIMESTAMPTZ,
  notes           TEXT,
  UNIQUE(co_no, jurisdiction, endpoint_url)
);
```

### Brevard endpoints (already known):
```sql
INSERT INTO gis_endpoint_registry (co_no, jurisdiction, endpoint_url, zone_field, parcel_field, verified, record_count) VALUES
(5, 'palm_bay', 'https://gis.palmbayflorida.org/arcgis/rest/services/GrowthManagement/Zoning/MapServer/0', 'ZONING', NULL, true, 78660),
(5, 'melbourne', 'https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/128', 'ZONE_ALL', 'TaxAcct', true, 113070),
(5, 'titusville', NULL, NULL, NULL, false, NULL),  -- needs discovery
(5, 'cocoa', NULL, NULL, NULL, false, NULL);
```

### Auto-discovery workflow (Hetzner SUMMIT):
Claude Code sessions discover new GIS endpoints by:
1. Search county/city website for "GIS", "zoning map", "ArcGIS"
2. Test candidate URLs for `/query` support
3. Identify zone field name
4. Register in `gis_endpoint_registry`
5. Modal picks up new endpoints on next run

---

## MODAL PARALLEL CONQUEST PIPELINE (UPDATED)

### Per-county execution flow:
```
┌─── STAGE 1: DOR BASELINE (GHA, ~5 min per county) ───┐
│  FL GIO API → sample_properties + zoning_assignments    │
│  zone_source='dor_use_code', zone_confidence='low'      │
│  ALL 10.8M parcels available immediately                 │
└───────────────────────┬─────────────────────────────────┘
                        │
┌─── STAGE 2: MODAL PARALLEL GIS (Modal, ~5 min) ────────┐
│                                                          │
│  For each jurisdiction with GIS endpoint:                │
│    1. Fetch zoning polygons from gis_endpoint_registry   │
│    2. Build STRtree index                                │
│    3. Fetch parcel centroids from sample_properties      │
│    4. .map() across 5K-parcel chunks                     │
│    5. Spatial join: centroid ∈ polygon → zone_code        │
│    6. Aggregate results                                  │
│                                                          │
│  For jurisdictions WITHOUT GIS endpoint:                 │
│    → Keep DOR baseline (counted separately)              │
│    → Flag for Firecrawl/Claude Code discovery             │
│                                                          │
│  Output: match_rate = GIS_matched / total_parcels        │
└───────────────────────┬─────────────────────────────────┘
                        │
┌─── STAGE 3: QUALITY GATE ───────────────────────────────┐
│                                                          │
│  match_rate >= 85%  → PASS  → write + notify ✅          │
│  match_rate 70-84%  → REVIEW → write + flag + notify ⚠️  │
│  match_rate < 70%   → REJECT → skip write + notify ❌    │
│                                                          │
│  For REVIEW/REJECT:                                      │
│    → Log to conquest_events with full diagnostics        │
│    → Queue Claude Code session for GIS endpoint discovery│
│    → DOR baseline remains as fallback (visible on dash)  │
│                                                          │
└───────────────────────┬─────────────────────────────────┘
                        │
┌─── STAGE 4: SUPABASE WRITE + DASHBOARD UPDATE ──────────┐
│                                                          │
│  supabase_bulk_writer() → zoning_assignments             │
│  refresh_county_stats() → county_conquest_status         │
│  log_conquest_event()   → conquest_events → Realtime     │
│                                                          │
│  Dashboard auto-updates via Realtime subscription        │
│  Telegram gets rich notification with stats + link       │
└──────────────────────────────────────────────────────────┘
```

### Modal cost ceiling:
- Per county: $0.02-0.05 (well within $30/mo free tier)
- All 67 counties: ~$1.50 total
- Quality gate prevents wasted writes on bad data

---

## FULL DATABASE PER COUNTY

Every county gets the SAME data structure as Brevard:

| Table | Content | Scale |
|-------|---------|-------|
| `sample_properties` | FL GIO parcel (address, use_code, values, geometry) | ~10.8M rows total |
| `zoning_assignments` | Zone code + jurisdiction + source + confidence | ~10.8M rows total |
| `county_jurisdictions` | Per-municipality stats and GIS endpoint status | ~2,000 rows total |
| `gis_endpoint_registry` | Discovered GIS URLs per jurisdiction | ~500 rows total |

Indexed by `co_no` for fast per-county queries. Dashboard shows the same jurisdiction drill-down for every county that Brevard currently has.

---

## NEW FILES TO CREATE

### cli-anything-biddeed repo:

| File | Purpose |
|------|---------|
| `scripts/quality_gate.py` | Post-Modal quality check + Telegram notify |
| `scripts/conquest_telegram_notify.py` | Rich Telegram messages with stats |
| `supabase/functions/conquest-bot/index.ts` | Edge function for Telegram webhook |
| `.github/workflows/summit-conquest-engine.yml` | Master 5-stage pipeline |
| `.github/workflows/zonewise-nightly-v2.yml` | Nightly auto-conquest cron |
| `migrations/20260320_conquest_ops.sql` | conquest_events + gis_endpoint_registry + RPCs |
| `modal-spatial/modal_67.py` | Updated Modal app with quality gate + multi-source |
| `modal-spatial/configs/county_gis_registry.json` | Static fallback for GIS endpoints |

### zonewise-web repo:

| File | Purpose |
|------|---------|
| `app/conquest/page.tsx` | Statewide 67-county grid with Realtime |
| `app/conquest/[county]/page.tsx` | County detail + jurisdiction table |
| `components/conquest/CountyGrid.tsx` | Grid of county cards |
| `components/conquest/CountyDetail.tsx` | Detail view with quality badge |
| `components/conquest/QualityBadge.tsx` | PASS/REVIEW/REJECT indicator |
| `components/conquest/LiveIndicator.tsx` | Pulsing dot during active conquest |
| `lib/conquest.ts` | Supabase queries + Realtime subscription |

---

## EXECUTION ORDER FOR CLAUDE CODE

### Session 1: Brevard 100% (cli-anything-biddeed)
1. Run `20260320_multi_county_schema.sql` migration
2. Run `20260320_conquest_ops.sql` migration (new tables)
3. Create + run Melbourne gap fill (10,626)
4. Create + run USE_CODE gap fill (19,986)
5. Normalize jurisdictions (22→17)
6. Dedup + validate
7. Report COUNT(*) — must show 351,424 ±50

### Session 2: Dashboard (zonewise-web)
1. Create conquest pages + components
2. Wire Supabase Realtime subscriptions
3. Push → auto-deploy → verify at zonewise.ai/conquest

### Session 3: Telegram Bot (cli-anything-biddeed)
1. Create conquest-bot edge function
2. Deploy to Supabase
3. Set Telegram webhook
4. Test all 6 commands

### Session 4: Conquest Engine + Nightly Cron
1. Create `summit-conquest-engine.yml` (5-stage master pipeline)
2. Create `zonewise-nightly-v2.yml` (auto-pick cron)
3. Create `quality_gate.py`
4. Update `modal_app.py` with quality gate integration

### Session 5: Orange + Duval (first real conquests)
1. Dispatch conquest engine for Orange (CO_NO=48)
2. Dispatch conquest engine for Duval (CO_NO=16)
3. Monitor quality gate results
4. If REVIEW: dispatch Claude Code GIS discovery session
5. Verify dashboard shows live progress

---

## CONSTRAINTS

- **$10/session MAX** for Claude Code sessions
- **Modal free tier** $30/mo — all 67 counties fit in ~$1.50
- **85%+ quality gate** — no exceptions, DOR baseline doesn't count
- **NEVER-LIE** — every pipeline reports COUNT(*) before AND after
- **ZERO-HITL** — Ariel only watches Telegram + Dashboard
- **HOUSE BRAND** — Navy/Orange/Inter on dashboard
- **Sentinel integration** — existing 5-min self-heal covers new workflows
