-- SPRINT4 D1: DoD evidence row for the Connect-in-Claude onboarding guide.
-- dispatch_id: 34fcdc82-77b1-467c-aa74-2cef23ddb3bf
--
-- Idempotent: skips insert if a 'pass' row for this item already exists.

INSERT INTO public.directory_readiness (item, status, evidence)
SELECT
  'connect_guide_live',
  'pass',
  'Live at https://breverdbidder.github.io/everest-battle-cards/biddeed-mcp/start/connect/ '
  '(everest-battle-cards repo, commit f9d86f6, pushed 2026-07-03). Verified HTTP 200 + '
  'content check (hero copy, "Add custom connector" step, MCP URL, he/es query examples '
  'all present in the served HTML) after GH Pages build completed (build status=built on '
  'that commit). Linked from a new "Connect in Claude" section + both post-signup success '
  'messages on biddeed-mcp/start/index.html (verified same commit, signup POST/fetch logic '
  'untouched), and from the b2c_email_templates en row (cli-anything-biddeed migration '
  '20260703_b2c_email_connect_guide_link.sql, applied live, confirmed via '
  'b2c_render_email_template RPC for both en and a stub locale (he) — both return the new '
  'link). '
  'HONEST CAVEAT — page content only, not end-to-end connector function: the guide '
  'documents https://biddeed.ai/api/mcp as the connector URL (same canonical URL as '
  'README/docs/other pages), but that endpoint does not yet route to the MCP server '
  '(GET returns the marketing SPA, HTTP 200, confirmed live 2026-07-03 12:10 UTC — same '
  'gap as the existing "Production /api/mcp endpoint reachable" row, status human_needed, '
  'root cause: mcp-vercel-deploy.yml has 0 runs, VERCEL_ORG_ID/VERCEL_PROJECT_ID secrets '
  'missing). The mission asked to substitute a direct Vercel deployment URL if the canonical '
  'one was in doubt — checked via gh api repos/.../deployments (empty) and gh run list for '
  'mcp-vercel-deploy.yml (zero runs); no such URL exists to substitute. The WorkOS OAuth '
  'callback registration is also unverified (existing directory_readiness row, '
  'status=human_needed, no WorkOS dashboard access). The page itself is honest about this: '
  'it carries a visible "Beta rollout" status note and a troubleshooting entry, rather than '
  'promising a connection that cannot yet complete. This row certifies the guide asset is '
  'live and correct, not that the underlying connector is production-ready end to end — '
  'that remains gated on the two pre-existing human_needed rows above.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.directory_readiness
  WHERE item = 'connect_guide_live' AND status = 'pass'
);
