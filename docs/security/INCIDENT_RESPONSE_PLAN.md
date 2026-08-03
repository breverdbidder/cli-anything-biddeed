# BidDeed.AI Incident Response Plan (IRP)

**Status:** Internal — GitHub only. Do not publish playbook detail to biddeed.ai.
**Last reviewed:** August 3, 2026
**Confidence:** Table/endpoint names in this document were verified live against
`mocerqjnksmhcjzxrewo.supabase.co` on 2026-08-03 (anon-key REST HEAD checks) and
against `src/worker.js` / `packages/biddeed-mcp/`. Anything not directly
verified this session is marked `INFERRED`.

This is not legal advice.

---

## 1. Overview

- **Product:** BidDeed.AI MCP platform (`mcp.biddeed.ai`, Vercel) + marketing/chat
  site (`biddeed.ai`, Cloudflare Worker) + ZoneWise.AI
- **Incident Commander:** Ariel Shapira — sole owner, sole responder
- **Contact:** security@biddeed.ai
- **Infrastructure:** GitHub (`breverdbidder/cli-anything-biddeed`) → Vercel
  (`mcp.biddeed.ai`) + Supabase (`mocerqjnksmhcjzxrewo`) + Cloudflare Worker
  (`biddeed.ai`, worker name `worker-damp-snowflake-cead`)
- **Last tested:** August 3, 2026 (document creation — see §7 for the testing
  schedule going forward)

Because this is a solo-founder operation, there is no handoff between shifts
and no separate security team. Every playbook below assumes Ariel is the one
executing it, which is why each step names the exact dashboard, table, or CLI
command rather than "notify the security team."

---

## 2. Severity Classification

| Severity | Definition | Example | Response SLA |
|---|---|---|---|
| P0 — Critical | Data breach, service down, active attack | Supabase breach, API key exfiltration, successful prompt injection | 1 hour |
| P1 — High | Security control bypassed, suspicious bulk access | Valid key used anomalously, cert-gate bypass attempt | 4 hours |
| P2 — Medium | Rate limit hit, failed-auth spike | 429 storm, repeated invalid API keys | 24 hours |
| P3 — Low | Unusual pattern, informational | New-county anomaly, off-hours S5 (report-checkout) call | 72 hours |

---

## 3. Detection Sources

| Source | What it covers | Verified |
|---|---|---|
| Telegram bot alerts | Ops/security alerting via `scripts/sentinel.sh` + `sentinel-patrol.sh` | VERIFIED (scripts exist in repo, per `.claude/rules/scripts.md`) |
| `security_events` (Supabase table) | Structured security event log | VERIFIED — table exists live (REST HEAD 200, 2026-08-03) |
| `security_scan_results` (Supabase table) | Semgrep/Gitleaks/npm-audit findings from `.github/workflows/security-scan.yml` | VERIFIED — table exists live (REST HEAD 200, 2026-08-03) |
| `.github/workflows/security-scan.yml` | Per-PR SAST/secret/dependency gate (Semgrep, Gitleaks, npm/pip audit) | VERIFIED — file present in repo |
| `taxi_meter_streams` / `taxi_meter_tools` | Per-call MCP tool usage and billing metering — the closest live equivalent to a "usage log" for anomaly review | VERIFIED — tables exist live (REST HEAD 200); protected under CLAUDE.md non-goals, **read-only during incident response** |
| `mcp_api_keys` | API key registry, `is_active` flag used to kill a compromised key | VERIFIED — table exists live (REST HEAD 200) |
| `honesty_violations` | Logs VERIFIED-tier claims later disproved (SHIP GATE) — useful when an incident traces back to a false "fixed" claim | VERIFIED — table exists live (REST HEAD 200) |
| Vercel deployment logs | MCP server runtime errors, `mcp.biddeed.ai` | INFERRED — standard Vercel dashboard feature, not queried this session |
| Cloudflare dashboard | Worker errors, WAF events, `biddeed.ai` edge traffic | INFERRED — standard Cloudflare feature, not queried this session |

**Correction from the original brief:** a table named `mcp_usage_log` does not
exist in the live schema (REST HEAD → 404). The real per-call metering tables
are `taxi_meter_streams` and `taxi_meter_tools`. A `sweep_security_alerts`
pg_cron job was referenced in project context but was not directly located in
this session's grep of `migrations/` and `supabase/migrations/` — treat any
claim about its exact cadence as `INFERRED`, not `VERIFIED`, until confirmed
against `cron.job`.

---

## 4. Response Playbooks

### P0-A: Suspected Data Breach

1. Rotate the Supabase service-role key (Dashboard → Settings → API).
2. Rotate the Cloudflare deploy token (Dashboard → My Profile → API Tokens).
3. Rotate the Anthropic API key (console.anthropic.com) if the breach could
   have exposed it. If the exposure could reach the Worker's chat-routing
   path specifically, also rotate `vault.router_proxy_key` (the
   Cloudflare Worker secret documented in `wrangler.toml` as
   `ROUTER_PROXY_KEY`, used to call the `anthropic-proxy` Supabase edge
   function) via `wrangler secret put ROUTER_PROXY_KEY`.
4. Disable affected API keys:
   ```sql
   UPDATE mcp_api_keys SET is_active = false WHERE api_key_hash = '<hash>';
   ```
5. Notify affected customers within 72 hours if Florida residents' personal
   information was involved (FS 501.171 — see §6 template).
6. Document the timeline in `docs/security/incidents/YYYY-MM-DD-incident.md`.
7. Re-run the Supabase security advisor and note any new findings.
8. Never pull a raw secret value into a chat session or shell command to
   investigate — per the CREDENTIAL HANDLING rule (GTM-22D), use masked
   GitHub Actions runs (`cc-runner-ghonly.yml`) for anything that must touch a
   live credential.

### P0-B: Prompt Injection Success (guardrails bypassed)

Context: `packages/biddeed-mcp/src/security/guardrails.js` runs pattern-based
prompt-injection and secret-leak scanning at the single canonical
`handleToolCall` chokepoint in `packages/biddeed-mcp/src/server.js` — scanning
both caller arguments and tool results before they are cached for idempotent
replay.

1. Pull MCP server logs from the Vercel dashboard for the affected time window.
2. Identify the exact tool call and input that bypassed the guardrail.
3. Add the bypassing pattern to `guardrails.js` and to
   `packages/biddeed-mcp/test/guardrails.test.js` as a regression test.
4. Redeploy the MCP server (Vercel).
5. Review all tool calls from the same API key in `taxi_meter_streams` /
   `taxi_meter_tools` for the prior 24h window for further exploitation.
6. Log the incident to `agent_ops_log` (task tag: `security-incident-<date>`).

### P1-A: Bulk Sweep / Data Exfiltration Attempt

1. Disable the API key immediately:
   ```sql
   UPDATE mcp_api_keys SET is_active = false WHERE api_key_hash = '<hash>';
   ```
2. Review `taxi_meter_streams` / `taxi_meter_tools` for that key — document
   exactly what was accessed and the row/tool-call volume.
3. Distinguish attempted vs. successful access (look for tool-call error
   states vs. successful billed calls) before concluding data was exfiltrated.
4. Re-enable the key only after the investigation is complete and documented.

### P1-B: Invalid API Key Spike (brute force)

1. Query `security_events` for the source IP address(es) behind the spike.
2. Add the IP to the Cloudflare WAF block list.
3. Monitor for 24h — if the spike stops, close the incident as P1. If it
   continues, escalate to Cloudflare support.

---

## 5. Customer Notification Template

> **Subject:** Important Security Notice from BidDeed.AI
>
> Dear [Customer],
>
> On [date], we detected [what happened] affecting [what data was involved —
> be specific: email address, name, no payment card data (Stripe holds that),
> etc.].
>
> **What we did:** [containment steps — key rotation, access revocation, fix
> deployed].
>
> **What you should do:** [password reset if applicable; watch for phishing
> referencing BidDeed.AI; no action needed if data was non-sensitive].
>
> We take this seriously and are available at security@biddeed.ai for any
> questions.
>
> — Ariel Shapira, Founder, BidDeed.AI / Everest Capital USA

This is not legal advice — have Florida counsel review before sending if the
incident involves >500 FL residents (triggers FS 501.171 formal notice
obligations to the FL Department of Legal Affairs).

---

## 6. Post-Incident Review

Within 7 days of any P0/P1, document in
`docs/security/incidents/YYYY-MM-DD-<slug>.md` covering: timeline, root
cause, fix applied, and prevention (what changed so this class of incident
cannot recur — e.g., a new guardrail pattern, a new WAF rule, a new alert).

---

## 7. Testing Schedule

- **Tabletop review:** quarterly — Ariel re-reads every playbook above and
  updates any table/endpoint name that has drifted from the live schema.
- **Automated test:** monthly — manually insert a synthetic P0-severity row
  into `security_events`, verify the Telegram alert fires within 15 minutes,
  then delete the test row.
- **Next tabletop due:** November 2026 (quarterly from this document's
  creation date).

---

*This document is internal operational material. Do not publish incident
playbook detail (exact remediation steps, table names, rotation procedures)
to the public biddeed.ai website — only the existence of an IRP and the
security contact belong on `/security`.*
