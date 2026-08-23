# MAS SOP v1.2 — ADDENDUM A: Execution Substrate Standard

**Status:** ADOPTED (founder-approved, Aug 22 2026)
**Amends:** MAS_SOP_META_PROMPT.md v1.2 (commit 429e8659, breverdbidder/cli-anything-biddeed)
**Decision register row:** `mas_execution_substrate_addendum_a` → public.unified_context
**Supersedes:** nothing — additive. No prior decision is reopened by this addendum.

---

## A.1 Decision

The Everest MAS runs on exactly **two orchestration substrates plus MCP tool
transport**. No third framework may be introduced without a full EG14 gate.

| Layer | Standard | Role in MAS |
|---|---|---|
| Programmatic agents | **Claude Agent SDK** (`anthropics/claude-agent-sdk-python`, TS twin `@anthropic-ai/claude-agent-sdk`) | The harness that already powers Claude Code / GH Actions workers, now used deliberately: subagent spawning (≤3 levels), lifecycle hooks, per-agent cost attribution, scoped permissions, fallback model chains |
| Stateful pipelines | **LangGraph** (`langchain-ai/langgraph`) + **`langchain-ai/langchain-mcp-adapters`** | Long-running, checkpointed workflows (scraper → analysis → report → QA) with Supabase state persistence, exactly as already declared in the SOP orchestration layer |
| Tool transport | **MCP** via repo-level `.mcp.json` | Every vendor and internal capability is an MCP server. Agents never embed vendor REST logic directly when an MCP surface exists |

**Explicitly NOT adopted** (studied, rejected for this stack — do not re-litigate
without a deliberate-reversal case per the External-Input Gate):

- CrewAI — duplicates the SOP role registry (D1–D6) it would sit beside
- claude-flow (ruvnet) — pattern reference only; its swarm conventions conflict with SPI gate discipline
- Microsoft Agent Framework, Google ADK, OpenAI Agents SDK — wrong provider center of gravity for a Claude-native fleet

## A.2 Vendor MCP servers (approved list additions)

| Vendor | Surface | Auth | Billing model | Primary consumer |
|---|---|---|---|---|
| **Tracerfy** | Hosted remote MCP: `https://mcp.tracerfy.com/<trmcp_...>` + REST API | Connector link (chat/ad-hoc) / Bearer `tracerfy_api_key` from vault (product) | Pay-per-hit credits; misses free; instant lookup 5 cr ($0.10), batch 1 cr ($0.02) | D2 Data (skip trace), D3 GTM (DNC/TCPA compliance flags) |
| **Bright Data** | Official MCP server repo `brightdata/brightdata-mcp` (npx `@brightdata/mcp`) + Scraping Browser CDP endpoint | `BRIGHTDATA_API_KEY`, `BRIGHTDATA_BROWSER_WSS` (GH secrets) | Usage-based; $25 starter credit | D2 Data (winning-bidder harvest #18527, JS-rendered clerk calendars) |

Cascade posture unchanged: Tracerfy primary skip trace; Endato/EnformionGO
reserved tier-2 (EG14 before adoption). BatchData excluded.

## A.3 `.mcp.json` standard (cli-anything-biddeed, repo root)

```json
{
  "mcpServers": {
    "tracerfy": {
      "type": "http",
      "url": "${TRACERFY_MCP_URL}"
    },
    "brightdata": {
      "command": "npx",
      "args": ["-y", "@brightdata/mcp"],
      "env": { "API_TOKEN": "${BRIGHTDATA_API_KEY}" }
    }
  }
}
```

**Secret hygiene (hard rule):** the committed `.mcp.json` contains **only
`${VAR}` references** — never a literal `trmcp_` link or API token. The
Tracerfy connector link is a bearer credential to the credit balance; it lives
in GitHub Actions secrets (`TRACERFY_MCP_URL`) and Supabase vault
(`tracerfy_api_key` for REST). A leaked link is revoked in the Tracerfy
dashboard (5-slot link management) and regenerated; the product integration
uses the API key, not the connector link, so chat-link revocation never breaks
production.

## A.4 Department mapping

- **D1 Engineering:** owns `.mcp.json`, SDK scaffold, adapter code; all agents it ships declare which substrate they run on (SDK agent vs LangGraph node) in the task registry entry
- **D2 Data:** consumes both vendor MCPs; skip-trace and harvest pipelines are LangGraph graphs with Supabase checkpoints; single-shot enrichments may be SDK subagents
- **D3 GTM:** reads Tracerfy DNC/TCPA/litigator flags from lead records only — never calls the vendor directly; hard-block rule from the skip-trace integration issue applies fleet-wide
- **D6 QA/Sentinel:** MCP server availability + credit-balance checks join the watchdog surface; Tracerfy balance below 100 credits or Bright Data zone failure opens a gate in `spi_gates`

## A.5 HITL tier assignment (three-tier model, v1.1)

- Adding/rotating vendor MCP secrets: **T1 (founder)** — existing Always-Ask category (API keys)
- Agents calling Tracerfy/Bright Data within budget guardrails: **T2** (autonomous, mandatory `agent_ops_log` audit rows incl. credit cost per call → taxi meter)
- Introducing any new MCP server or third substrate: **T1 + EG14 + License V2**

## A.6 License status (License V2)

- LangGraph, langchain-mcp-adapters: MIT (verified previously in stack)
- Claude Agent SDK (Python + TS), `brightdata/brightdata-mcp`: expected MIT/permissive — **CC must verify LICENSE files at dispatch and record result in the PR body before adoption is final** (External-Input Gate step (a))
- Tracerfy: hosted service, no code adoption — ToS apply, no license scan needed

## A.7 Rollout (single CC dispatch)

One issue to breverdbidder/cli-anything-biddeed:

1. Add `.mcp.json` per §A.3 (env-var form only) + `TRACERFY_MCP_URL`, `BRIGHTDATA_API_KEY` to workflow env plumbing
2. Add `agents/` scaffold: one example Claude Agent SDK subagent (skip-trace enrichment) + one LangGraph graph stub wired through `langchain-mcp-adapters` with Supabase checkpointer
3. Verify licenses per §A.6; record in PR
4. Append this addendum reference line to MAS_SOP_META_PROMPT.md and BIDDEED_SSOT.md (clears the deferred SSOT deviation from CP4)
5. Upsert decision row `mas_execution_substrate_addendum_a` to unified_context
6. DoD: a CC session lists both MCP servers' tools successfully; SDK example agent runs one Tracerfy lookup end-to-end with taxi-meter row (blocked until credits funded — respect gate)

**Blocking founder gates before step 6:** Tracerfy credits funded + API key in
vault; Bright Data account + zone + secrets (already tracked under #18527
prep). Neither blocks steps 1–5.
