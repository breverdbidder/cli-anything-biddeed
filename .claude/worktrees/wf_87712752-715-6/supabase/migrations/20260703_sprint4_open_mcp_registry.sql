-- SPRINT4 H1: publish BidDeed MCP to the Official MCP Registry (registry.modelcontextprotocol.io)
-- dispatch_id: 94eee2f0-871a-487e-b0c8-8325e0902099
--
-- Already applied live via direct REST insert during this session (see chat evidence).
-- This file persists the same idempotent inserts to the repo for history/replay.
--
-- Live proof: GET https://registry.modelcontextprotocol.io/v0/servers?search=biddeed
--   -> name=ai.biddeed/biddeed-mcp, version=1.0.0, status=active, isLatest=true
--   (verified 2026-07-03T12:24Z)

INSERT INTO public.directory_readiness (item, status, evidence)
SELECT
  'open_mcp_registry',
  'pass',
  'Published ai.biddeed/biddeed-mcp v1.0.0 to registry.modelcontextprotocol.io via mcp-publisher CLI '
  '(DNS auth). Namespace ai.biddeed DNS-verified: TXT record "v=MCPv1; k=ed25519; '
  'p=mITg4ND6VyEgb6a7nNTlzuOHQUkFsIdyNBhtqPEZFHw=" added to Cloudflare zone '
  'dcb6876f057e0bb88be181d6e8d0dcbc (record id 25507628e1fd42ba74e4c3e3fd301a5d) at biddeed.ai apex, '
  'propagated instantly (confirmed via dig @1.1.1.1 and @8.8.8.8). mcp-publisher login dns succeeded, '
  'publish succeeded. VERIFIED via GET https://registry.modelcontextprotocol.io/v0/servers?search=biddeed '
  'at 2026-07-03T12:24Z: returns 1 result, name=ai.biddeed/biddeed-mcp, version=1.0.0, status=active, '
  'isLatest=true. HONEST CAVEAT ON URL CHOICE: remotes[0].url = https://biddeed.ai/api/mcp. Tested '
  'http://87.99.129.125:3031/mcp first (the live, working Hetzner MCP HTTP server -- curl-verified '
  '/health=200, /mcp=401-auth-required same session) but registry semantic validation rejected it '
  '(error: "invalid remote URL", ref invalid-remote-url) because the host does not match the '
  'DNS-verified biddeed.ai namespace/domain -- confirmed empirically via mcp-publisher validate, not '
  'assumed. No Vercel deployment URL exists to use as the mission-anticipated fallback either: '
  'mcp-vercel-deploy.yml has 0 GHA runs and gh api .../deployments returns empty (VERCEL_ORG_ID/'
  'VERCEL_PROJECT_ID secrets missing, same finding as the pre-existing human_needed directory_readiness '
  'row for "Production /api/mcp endpoint reachable"). So https://biddeed.ai/api/mcp was the only URL '
  'that both (a) passes registry validation and (b) is the documented canonical connector URL already '
  'referenced in README/connect-guide/other directory_readiness rows. HONEST CAVEAT ON FUNCTION: this '
  'registry entry is metadata-only proof of a correctly-formed, DNS-verified listing. The URL itself '
  'does not yet route to the MCP server end-to-end -- confirmed live 2026-07-03T12:18Z: GET '
  'https://biddeed.ai/api/mcp returns HTTP 200 marketing SPA HTML (not JSON-RPC), POST returns HTTP 405. '
  'This is the SAME pre-existing routing gap already tracked (root cause: mcp-vercel-deploy.yml never '
  'run). A version-bump republish (mcp-publisher publish with version incremented) is required once '
  'that routing fix ships so the registry metadata reflects a live endpoint value -- no new URL is '
  'needed since biddeed.ai/api/mcp is already the fixed target. This row certifies the OPEN MCP '
  'REGISTRY LISTING task (SPRINT4) is complete and verified; it does NOT certify end-to-end connector '
  'function, which remains gated on the pre-existing human_needed row for Vercel routing. Live server '
  'code was not touched, per mission rule.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.directory_readiness
  WHERE item = 'open_mcp_registry' AND status = 'pass'
);

INSERT INTO public.decision_log (
  session_id, task_id, decision_type, decision, reasoning,
  alternatives_considered, outcome, was_correct, correction_note
)
SELECT
  'claude-app-2026-07-03-sprint4-mcp-registry',
  '94eee2f0-871a-487e-b0c8-8325e0902099',
  'distribution',
  'Published BidDeed MCP as a remote streamable-http server to the Official MCP Registry '
  '(registry.modelcontextprotocol.io) under DNS-verified namespace ai.biddeed/biddeed-mcp v1.0.0, '
  'remotes[0].url=https://biddeed.ai/api/mcp.',
  'Mission required a public, agent-discoverable MCP registry listing distinct from the deferred '
  'Claude Connectors Directory decision. DNS verification requires the remotes[].url host to match '
  'the verified domain (biddeed.ai) -- confirmed empirically: mcp-publisher validate rejected the '
  'actually-live, working Hetzner endpoint (http://87.99.129.125:3031/mcp, curl-verified 200/401) with '
  'error invalid-remote-url, while https://biddeed.ai/api/mcp (the pre-existing canonical but '
  'not-yet-routed connector URL) passed. The mission-anticipated fallback (a working Vercel deployment '
  'URL) does not exist: mcp-vercel-deploy.yml has 0 runs and there are no GitHub deployments, so no '
  'alternate biddeed.ai-hosted URL was available either.',
  ARRAY[
    'Publish with the live Hetzner IP URL (rejected: fails registry domain-match validation, confirmed via mcp-publisher validate error invalid-remote-url)',
    'Stand up a biddeed.ai subdomain reverse-proxying to Hetzner with Cloudflare-terminated TLS (rejected: Cloudflare free/pro proxy only forwards standard ports 80/443, origin listens on 3031 -- would require touching the live MCP server/infra, out of mission scope)',
    'Defer publish entirely pending the Vercel routing fix (rejected: mission explicitly authorized using the current canonical URL now and republishing after the fix)',
    'Publish with https://biddeed.ai/api/mcp and document the routing gap explicitly (CHOSEN)'
  ],
  'success_with_caveat',
  true,
  'Registry listing is metadata-only proof at this point. Version-bump republish needed once '
  'mcp-vercel-deploy.yml deploys api/mcp.js to production.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.decision_log
  WHERE task_id = '94eee2f0-871a-487e-b0c8-8325e0902099' AND decision_type = 'distribution'
);
