# anthropic-proxy

Anthropic Messages API-compatible HTTP proxy in front of the in-Postgres Smart Router.

## What this is

A Supabase Edge Function that accepts requests in Anthropic's Messages API format, forwards them to `public.anthropic_messages_proxy` (which calls `ecu_route_chat_llm`), and returns Anthropic-shaped responses. The Smart Router decides whether each request goes to Claude (via Max OAuth bearer) or Gemini (free tier fallback), per the ariel-rule.

## Architecture

```
claude-code-action (GHA)
        |
        | POST /v1/messages
        | x-api-key: $ROUTER_PROXY_KEY
        v
Supabase Edge Function (this)
        |
        | supabase.rpc('anthropic_messages_proxy', {p_request, p_proxy_key})
        v
public.anthropic_messages_proxy (Postgres)
        |
        | validates proxy key, calls...
        v
public.ecu_route_chat_llm
        |
        +--> tier 1: ecu_invoke_claude (vault.anthropic_oauth_bearer)
        |       on failure (401/etc):
        +--> tier 2: ecu_invoke_gemini (vault.gemini_api_key)
        |
        | NEVER: ANTHROPIC_API_KEY (BLOCKED at ecu_invoke_claude)
```

## Authentication

The Edge Function does NOT use Anthropic credentials. Callers authenticate with a router-issued bearer token stored in `vault.router_proxy_key`. The actual Claude OAuth bearer and Gemini API key live in the same vault but are only used by the in-Postgres router.

## Endpoints

- `POST /v1/messages` — Anthropic Messages API. Accepts standard request body, returns standard response (or SSE stream if `stream: true`).
- `GET /health` — health check, no auth required.

## Deployment

```bash
# From the repo root
supabase functions deploy anthropic-proxy --no-verify-jwt
```

The function uses these env vars (set automatically by Supabase):
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

No additional secrets needed in the Edge Function environment.

## GitHub Actions cutover

After deployment, set these in the repo:

1. **GitHub repo secret:** `ROUTER_PROXY_KEY` = value of `vault.router_proxy_key` (retrieve via `SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name='router_proxy_key'`).

2. **Workflow YAML** (`.github/workflows/claude-code-action.yml`):
   ```yaml
   env:
     ANTHROPIC_BASE_URL: https://<project_ref>.supabase.co/functions/v1/anthropic-proxy
   with:
     claude_code_oauth_token: ${{ secrets.ROUTER_PROXY_KEY }}
   ```
   The action thinks it's calling Anthropic. It's actually calling this proxy, which routes via the Smart Router.

3. Drop the `CLAUDE_CODE_OAUTH_TOKEN` GitHub secret dependency — that token now lives only in `vault.anthropic_oauth_bearer` and is rotated there.

## Smoke tests

```bash
# 1. Health
curl https://<project_ref>.supabase.co/functions/v1/anthropic-proxy/health

# 2. Non-streaming Messages API
curl https://<project_ref>.supabase.co/functions/v1/anthropic-proxy/v1/messages \
  -H "x-api-key: $ROUTER_PROXY_KEY" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 100,
    "messages": [{"role":"user","content":"Reply with exactly: PROXY_OK"}]
  }'

# 3. Verify routing decision
psql ... -c "SELECT tier_chosen, final_status, notes FROM ecu_router_decisions ORDER BY created_at DESC LIMIT 1;"
```

If `vault.anthropic_oauth_bearer` is set and valid: response routes via Claude. If missing or returning 401: response routes via Gemini and `x_router.fallback_used = true` in the response envelope.

## Observability

Every request lands in:
- `llm_requests` / `llm_responses` (full payloads + cost)
- `ecu_router_decisions` (routing decision + reason)
- `v_smart_router_health` (daily breakdown + FREE-tier % vs target)

## Rollback

Remove `ANTHROPIC_BASE_URL` from the workflow YAML. The action falls back to calling `api.anthropic.com` directly. Edge Function can stay deployed; just unreferenced.
