# Dell MCP Runbook — biddeed-mcp HTTP server + Cloudflare Tunnel

**Status:** canonical. Companion to `BIDDEED_SSOT.md` §1/§2 — this is the
procedure for standing up the real product surface (`mcp.biddeed.ai`) on the
local Dell, replacing the legacy CC-runner deployment.
**Owner:** Ariel Shapira. **Authored:** 2026-07-20.

The npm package `biddeed-mcp` is unpublished (registry 404, `NPM_TOKEN`
absent — see `BIDDEED_SSOT.md` §1, §5). Run the server **from a clone of this
repo**, not via `npx`, until publish is a separate owner decision.

---

## 0. Prerequisites

- Linux machine (the Dell), Node.js `>=18` (`packages/biddeed-mcp/package.json`
  `engines.node`), `git`, `systemd`.
- A Cloudflare account that owns the `biddeed.ai` zone (Ariel's).
- The env var values listed in §2 (never paste raw values into a shell
  history file or a chat — see `CLAUDE.md` CREDENTIAL HANDLING).

## 1. Install the server

```bash
sudo mkdir -p /opt/biddeed-mcp
sudo chown "$(whoami)" /opt/biddeed-mcp
git clone https://github.com/breverdbidder/cli-anything-biddeed.git /opt/biddeed-mcp/repo
cd /opt/biddeed-mcp/repo/packages/biddeed-mcp
npm install --production
```

To update later: `cd /opt/biddeed-mcp/repo && git pull && cd packages/biddeed-mcp && npm install --production && sudo systemctl restart biddeed-mcp-http`.

## 2. Environment variables (sourced from repo, not memory)

Required — the server will not read Supabase without one of each pair:

| Var | Source | Notes |
|---|---|---|
| `SUPABASE_URL` (or `BIDDEED_SUPABASE_URL`) | `packages/biddeed-mcp/src/supabase.js:2` | `SUPABASE_URL` takes precedence if both set |
| `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_KEY`, or `BIDDEED_SUPABASE_KEY`) | `packages/biddeed-mcp/src/supabase.js:3` | first non-empty wins, in that order |
| `PORT` | `packages/biddeed-mcp/bin/biddeed-mcp-http.js` (default `3000` if unset), `src/http.js:69` | use `3000` locally; the tunnel maps the public hostname to this port, so `:3031` is not required and should not be reused (legacy CC-runner port — see SSOT §1) |

Optional:

| Var | Source | Notes |
|---|---|---|
| `MCP_PUBLIC_URL` | `packages/biddeed-mcp/src/http.js:109,119` | defaults to `https://biddeed.ai/api/mcp` if unset — **must be set to `https://mcp.biddeed.ai/mcp`** on the Dell, or OAuth protected-resource metadata will advertise the wrong resource URL |
| `STRIPE_SECRET_KEY` | `packages/biddeed-mcp/src/billing.js:13` | billing/metering disabled (returns `null` client) if absent |
| `WORKOS_API_KEY` / `WORKOS_CLIENT_ID` | `packages/biddeed-mcp/src/oauth.js:17-18` | OAuth disabled if absent; API-key auth still works |
| `BIDDEED_API_KEY` (or `ZONEWISE_API_KEY`) | `packages/biddeed-mcp/src/auth.js:79` | fallback key source when a caller doesn't pass one via env |
| `STRIPE_WEBHOOK_SECRET` | `packages/biddeed-mcp/src/webhook.js` | only needed if Stripe webhooks are pointed at this box |

Write these to `/opt/biddeed-mcp/.env` (mode `600`, owned by the service user) — never commit it, never echo it.

## 3. systemd unit — the server

`/etc/systemd/system/biddeed-mcp-http.service`:

```ini
[Unit]
Description=BidDeed MCP HTTP Server (Dell — mcp.biddeed.ai origin)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/biddeed-mcp/repo/packages/biddeed-mcp
EnvironmentFile=/opt/biddeed-mcp/.env
ExecStart=/usr/bin/node bin/biddeed-mcp-http.js
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now biddeed-mcp-http
curl -s http://localhost:3000/health   # expect HTTP 200 — endpoint defined src/http.js:94
```

## 4. Cloudflare Tunnel

Install `cloudflared` (see https://pkg.cloudflarewarp.com or the distro package for the Dell's OS), then:

```bash
cloudflared tunnel login          # ⚠ ARIEL-ONLY — opens a browser to authenticate
                                   # against the Cloudflare account that owns the
                                   # biddeed.ai zone. This is the one step that
                                   # cannot be delegated; everything after uses
                                   # the resulting cert.
cloudflared tunnel create biddeed-mcp
cloudflared tunnel route dns biddeed-mcp mcp.biddeed.ai
```

`tunnel create` writes a credentials JSON under `~/.cloudflared/`; note its path for the config below.

`/etc/cloudflared/config.yml`:

```yaml
tunnel: biddeed-mcp
credentials-file: /root/.cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: mcp.biddeed.ai
    service: http://localhost:3000
  - service: http_status:404
```

## 5. systemd unit — the tunnel

```bash
sudo cloudflared service install
```

This installs `/etc/systemd/system/cloudflared.service` pointed at `/etc/cloudflared/config.yml`. Then:

```bash
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
```

## 6. Smoke test

```bash
curl -s https://mcp.biddeed.ai/health
# expect: HTTP 200, same body as the localhost check in §3

curl -s -H "Authorization: Bearer bd_live_..." https://mcp.biddeed.ai/mcp
# expect: an MCP protocol response (or a 401 with a WWW-Authenticate header
# pointing at /.well-known/oauth-protected-resource if the bearer token is
# wrong — both prove the tunnel + server chain is live end-to-end)
```

## 7. What this replaces

Once §1–§6 are live and smoke-tested, `mcp.biddeed.ai` is the product surface.
The legacy service on the CC runner (`87.99.129.125:3031`, unit
`biddeed-mcp-http.service`) is stopped and disabled — see `BIDDEED_SSOT.md`
§1. Do not point any client config at `87.99.129.125:3031` going forward.
