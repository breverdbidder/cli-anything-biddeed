---
name: exa-discovery
description: Use when running semantic web discovery for Florida county data sources, auction intel, or GTM research. Triggers on: exa search, discovery harness, find county GIS, find auction data, semantic search, county data sources, exa-discovery, exa_client, discovery pipeline, zonewise discovery, auction discovery, gtm research.
---

# Exa Discovery

## Role
Own semantic web discovery as evidence-grounded source ranking, not link collection theater.

## Working Mode
Build queries -> Exa semantic search -> Filter and rank results -> Persist to discovery_results -> Optional Firecrawl handoff.

## Focus Areas
1. Query building -- mode-specific queries: zonewise (GIS/parcel), auction (foreclosure/clerk), gtm (market/vertical)
2. Exa API -- semantic search with livecrawl=true, 20-25 results/query, EXA_API_KEY required
3. Result ranking -- relevance score threshold 0.6, deduplicate by domain
4. Supabase persistence -- discovery_results table (run migrations/20260327_discovery_results.sql first)
5. Cost discipline -- estimate before batch runs, log token spend per query
6. Firecrawl handoff -- pass ranked URLs to Firecrawl for full content extraction when score >= 0.8
7. Batch mode -- all 67 FL counties at ~.38 total (within 0 cap)
8. Dry run -- estimate cost and show query plan without executing API calls

## Quality Gates
- verify: Each result has url, relevance_score, county, mode fields
- confirm: Cost estimate logged before any batch run (67-county ~.38)
- check: No duplicate domains in final ranked list
- ensure: discovery_results row persisted with source, query, score, discovered_at
- call_out: Flag if EXA_API_KEY is missing or Exa returns 0 results for a county

## Output Format


## Constraints
- NEVER run batch mode without logging estimated cost first
- NEVER mark a source as CONFIRMED without verifying the URL returns HTTP 200
- EXA_API_KEY must be set (GitHub secrets or env var) before any live search
- Use node discovery/src/index.js as canonical CLI -- do not create alternatives
- Migration dependency: migrations/20260327_discovery_results.sql must run before persistence
- Max 25 results per query (Exa rate limits), min relevance 0.6 for inclusion

## Guard Rail
Do not include discovery results with relevance_score < 0.6 in ranked output -- low-signal sources pollute downstream analysis.
