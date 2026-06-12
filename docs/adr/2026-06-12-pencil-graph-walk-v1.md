# ADR-2026-06-12 — PENCIL Graph Walk V1 (adopted pattern: agents walk the graph via MCP)

**Status:** ADOPTED (owner-ratified 2026-06-12) | SHIPPED LIVE same day
**Origin:** Pattern observed in HelixDB (github.com/HelixDB/helix-db). AGPL-3.0 →
HARD-REJECT for code per LICENSE V2. Architecture adopted, zero code reuse.
**Infra:** Supabase only (DEFAULT INFRA). No new services. No schema changes — additive
read-only functions over existing tables.

## Decision
PENCIL MCP agents traverse a typed property graph instead of generating SQL.
Two Postgres RPCs are the primitive layer; pencil-mcp wraps them as MCP tools.

- `pencil_graph_node(p_type, p_id)` — typed node fetch, whitelisted fields only.
  Types V1: auction (case_number) | parcel (parcel_id) | decision (case_number).
- `pencil_graph_neighbors(p_type, p_id, p_edge, p_limit<=50)` — typed edge traversal.
  Edges V1: auction->{parcel, outcomes, decision} | parcel->{auctions, zoning, comps}.

Both STABLE, SECURITY DEFINER, search_path locked, bounded limits, jsonb out,
unknown type/edge returns a structured error listing valid moves (agent-discoverable).

## Why
1. Safety: agents never compose SQL — no injection surface, no runaway scans.
2. Token economy: whitelisted compact nodes vs 50-80 col row dumps.
3. Discoverability: error payload teaches the agent the graph schema.
4. The relational corpus already IS a graph (auctions-parcels-zoning-outcomes-decisions);
   this names the edges instead of re-platforming onto a graph DB.

## Live verification (Honesty Protocol V3 — all VERIFIED 2026-06-12)
Walk chain on real case PO-212106 (Rockledge tax deed, sold $203,000):
- node(auction) -> full auction card
- auction->parcel -> enriched parcel (GU code, centroid, JV $342,410)
- parcel->zoning -> R-1A Rockledge, standards NULL  [= WS1 hit-list district #3, live]
- auction->outcomes -> []  [= PO-key root cause, live]
- parcel->comps -> 3 same-zip/same-use comps incl. 2025 sale $650,000

Defect found+fixed pre-test: outcomes branch self-overwrite (migration
pencil_graph_walk_v1_outcomes_fix2). UNION arms parenthesized for LIMIT.

## V2 backlog (deferred, not committed work)
- spatial comps via centroid radius (PostGIS) replacing zip+dor_uc heuristic
- outcome edge match via brevard_case_rekey crosswalk for PO-keyed cases
- jurisdiction + ordinance-vault node types
- pencil-mcp tool wrappers (WorkOS-authed) exposing node/neighbors + a walk macro
