# ZoneWise Modal Spatial Agents

## What This Is
Modal.com-powered parallel spatial zoning agents for BidDeed.AI / ZoneWise.AI.
Part of the cli-anything agent army: `breverdbidder/cli-anything-biddeed`.

## Architecture

```
cli_anything_modal_spatial.py  ← CLI harness (7-phase pipeline)
modal_app.py                   ← Modal serverless app
  ├── spatial_zoner()          ← Agent 1: STRtree parcel→zone matching (per chunk)
  ├── county_orchestrator()    ← Agent 2: Split→fan out→aggregate (per county)
  ├── supabase_bulk_writer()   ← Agent 3: Bulk upsert results
  └── multi_county_orchestrator() ← Agent 4: 67-county parallel launcher
```

## Agents

| # | Agent | Role | Modal Pattern |
|---|-------|------|---------------|
| 1 | SpatialZoner | Match parcels to zones via STRtree | `@app.function` + `.map()` |
| 2 | CountyOrchestrator | Chunk parcels, fan out Zoners | `@app.function` calling `.map()` |
| 3 | SupabaseWriter | Bulk upsert results | `@app.function` |
| 4 | MultiCountyOrchestrator | Parallel county-level runs | `@app.function` calling `.map()` |

## Performance

| Mode | 78K Brevard Parcels | 67 Counties |
|------|--------------------:|------------:|
| Sequential (current) | ~30 min | N/A |
| Modal parallel | ~3-4 min | ~10-15 min total |

## Commands

```bash
# Single county
modal run modal_app.py --county brevard

# All counties
modal run modal_app.py --multi

# CLI harness (with validation + reporting)
python cli_anything_modal_spatial.py --county brevard
python cli_anything_modal_spatial.py --health
```

## Secrets Required

Set via `modal secret create zonewise-secrets`:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

GitHub Actions secrets:
- `MODAL_TOKEN_ID`
- `MODAL_TOKEN_SECRET`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`

## Rules
- NEVER exceed $0.50/run cost ceiling
- ALWAYS validate match rate > 85% before writing
- Polygon cache persists in Modal Volume (no re-download)
- STRtree rebuilt per container (Shapely objects can't serialize across)
- Add new county GIS endpoints to `_fetch_zoning_polygons()` registry
