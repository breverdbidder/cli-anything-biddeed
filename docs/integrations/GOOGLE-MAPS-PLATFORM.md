# Google Maps Platform — Setup Guide (Phase 1)

**Provenance:** Summit `ZW-MAPS-MCP-D4D` v2 (May 17, 2026 refresh).
**Status:** Config-only — awaiting Demo Key from human owner.

## TL;DR

Google Maps Platform is registered as MCP server in Supabase (`mcp_servers.id = 2`), wired into Smart Router `flash` tier. Two endpoints are GA (Maps Grounding Lite, Maps Imagery Grounding), one is Private Preview (Routing Grounding), one needs BigQuery setup (Street View Insights — Phase 2 anchor).

## Human Action Items (you, Ariel)

1. **Claim Demo Key** — https://mapsplatform.google.com/maps-demo-key/ — no credit card required. Paste into Supabase vault:
   ```sql
   SELECT vault.create_secret('<paste-key>', 'google_maps_demo_key', 'GMP Demo Key, no-CC, rate-limited');
   ```
2. **Routing Preview waitlist** — https://mapsplatform.google.com/maps-products/grounding/ — fill form.
3. **Street View Insights decision (Phase 2 gate)** — billed tier, >$10. Decide by 2026-05-21.

## Smart Router Wiring

- Tier: `flash` (Gemini Flash 2.5, $0.15/1M tokens)
- Both products consume: `biddeed` + `zonewise`
- Rationale: Grounding Lite returns structured place/route JSON; flash tier is enough to orchestrate. Escalate only on multi-source synthesis.

## Phase 1 Exit Criteria

| Criterion | Target | Measurement |
|---|---|---|
| Demo Key active | true | vault.secrets check |
| cost_per_lookup | ≤ 1.2× current | `public.v_gmp_phase1_exit` |
| latency_p99 | ≤ 800 ms | `public.v_gmp_phase1_exit` |
| sample size | ≥ 200 queries / product | `public.gmp_grounding_benchmarks` |

## Phase 1 Benchmark Schema

```
public.gmp_grounding_benchmarks
  id, product (biddeed|zonewise),
  query_text, provider (google_maps_grounding_lite|existing_geocoding|baseline_static),
  latency_ms, freshness_seconds, cost_micro_usd,
  returned_payload jsonb, recorded_at, source_summit_id, notes

public.v_gmp_phase1_exit  -- rolling 7d aggregate, p99 + cost + pass%
```

## Endpoints Map

| Endpoint | Transport | Status | Used For |
|---|---|---|---|
| `grounding_lite_mcp` | MCP | GA May 2026 | choropleth search, D4D NLP, parcel queries |
| `routing_grounding` | REST | Private Preview | D4D route optimization (Phase 3) |
| `street_view_insights` | BigQuery | GA | D4D pre-route distress scoring (Phase 2) |
| `places_insights` | BigQuery | GA | Bulk parcel POI enrichment (Phase 4) |
| `address_validation` | REST | GA | Foreclosure/tax-deed data quality |

## Cost Posture

- Phase 1–2: **$0** (Demo Key only)
- Phase 3–5: **$10 max per summit** — hard breaker, halt & surface
- Production key: separate approval gate, `GOOGLE_MAPS_API_KEY` env var

## Hetzner Bypass Note

This config was authored **directly from a Claude chat session via Supabase MCP + GitHub API**, bypassing the standard Hetzner dispatch path (OAuth on `87.99.129.125` expired 2026-05-17; second occurrence). Pattern: when Hetzner OAuth is blocked, Phase 1-style config & schema work can be executed via this short-circuit path. Phases involving sustained code generation still require Hetzner.

## Files

- `config/mcp/google-maps-platform.json` — canonical config (this file's sibling)
- `docs/integrations/GOOGLE-MAPS-PLATFORM.md` — this doc
- Supabase: `public.mcp_servers id=2`, `public.gmp_grounding_benchmarks`, `public.v_gmp_phase1_exit`
