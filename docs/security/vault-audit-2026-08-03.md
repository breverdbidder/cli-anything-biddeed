# Vault / Secret Rotation Audit — 2026-08-03

Companion to `docs/security/ip-allowlist-research.md` (Deliverable 3). This file
covers Deliverables 1, 2, 4, 5 of the blast-radius-reduction brief. Everything
below is `agent_ops_log(dispatch_id='blast-radius-reduction-2026-08-03')`.

## Deliverables 1+2 — secret_rotation_registry + weekly reminder — VERIFIED

- `public.secret_rotation_registry`: 37 rows (32 = every name currently in
  `vault.secrets`, verified live via `SELECT name FROM vault.secrets`; +5 known
  secrets that live in GitHub Actions secrets, not vault, named explicitly in
  the brief: `cloudflare_deploy_token`, `anthropic_api_key_ghaw`,
  `deepseek_api_key`, `telegram_bot_token`, `telegram_chat_id`).
- **Deviation from spec:** the brief's `next_due_at GENERATED ALWAYS AS
  (last_rotated_at + (rotation_interval_days || ' days')::interval) STORED`
  fails: `ERROR 42P17: generation expression is not immutable`. Retried with
  `make_interval()` (confirmed `provolatile='i'`, i.e. actually immutable) —
  still fails, because `timestamptz + interval` itself is STABLE not IMMUTABLE
  (day/month interval arithmetic crosses DST boundaries). A generated column
  can never hold this value in Postgres. Fixed with a plain column +
  `BEFORE INSERT OR UPDATE` trigger (`_secret_rotation_registry_set_next_due`)
  instead. Verified: `next_due_at` computes correctly for every seeded row.
- `check_secret_rotation_due()` deployed; fires one `fire_workflow_dispatch()`
  Telegram alert per due/never-tracked secret via the existing
  `telegram-notify.yml` path (no bot token touches the DB). `pg_cron` job
  `secret-rotation-check` active, `0 9 * * 1` (Mondays 09:00 UTC).
- **Idempotency proven, not asserted** (CC_META_PROMPT §3.2): migration file
  run twice — 37 rows both times, exactly 1 cron job row both times (unschedule-
  then-reschedule pattern).
- **Alert path smoke-tested, not just claimed**: called `fire_workflow_dispatch`
  directly with one test message. Client-side `mgmt_sql.py` call timed out
  (120s) with `Connection terminated due to connection timeout`, but
  `gh run list --workflow=telegram-notify.yml` showed the dispatch actually
  queued and `gh run view <id>` confirmed `conclusion: success` — the call
  succeeded server-side despite the client timeout (CC_META_PROMPT §2.4:
  errored ≠ failed; verified via independent evidence, not assumed).
- **Finding, not a test artifact:** a read-only dry run (before any write) shows
  35 of 37 secrets have `last_rotated_at IS NULL` — never tracked as rotated.
  This is real and matches the brief's own "Known rotation status" list (only
  Cloudflare and one Anthropic key were marked rotated as of 2026-07-28). Did
  **not** fire the full alert sweep for all 35 right now (would be 35 Telegram
  messages in one burst) — the Monday cron will surface these on schedule.
  Flagging here so it isn't mistaken for a bug when the first real alerts land.

## Deliverable 3 — IP allowlist — BLOCKED, see `ip-allowlist-research.md`

Not summarized here; full writeup in the companion doc. Short version: Vercel's
egress-IP endpoint from the brief 404s (doesn't exist), static IPs cost $100/mo
(forbidden by non-goals), GitHub Actions' published range is 7,297 CIDR blocks
(too broad to be a real control). Anthropic's MCP range is genuinely published
(`160.79.104.0/21`) but covers a different access path than this session uses.
No restriction applied; live state confirmed still `0.0.0.0/0`.

## Deliverable 4 — Resend / MindStudio / Supabase / Anthropic rotation — research only, per operating-contract override

**CC_META_PROMPT.md §4 is explicit: "Never rotate a credential yourself.
Surface it. Auth changes are Ariel-only."** This overrides the brief's
"if available: create new API key via API... rotate it" instruction for
Resend/MindStudio. Below is capability research; **no rotation was executed
for any secret.**

| Secret | Capability found | Action taken |
|---|---|---|
| `resend_api_key` | **Confirmed programmatic**: Resend exposes `POST /api-keys` (create) and `DELETE /api-keys/{id}` (revoke) — [resend.com/docs/knowledge-base/how-to-handle-api-keys](https://resend.com/docs/knowledge-base/how-to-handle-api-keys). Rotation = create new → cut over consumers → verify via logs filtered by key → delete old. | `secret_rotation_registry.rotation_method` updated to `api_automated` with this citation. **Not executed.** MANUAL_REQUIRED for now — this is a case where the *mechanism* is automatable, but *authorization* to run it is Ariel's per the operating contract, not a technical gap. |
| `mindstudio_bridge_secret` | MindStudio's public API reference ([university.mindstudio.ai/docs/developers/api-reference](https://university.mindstudio.ai/docs/developers/api-reference)) documents Bearer-token *usage* for invoking workflows, but no self-service token-rotation/refresh endpoint. Direction of this specific secret is unconfirmed from this repo — the only match found (`src/worker.js`) is an unrelated URL-allowlist string, not the credential's actual use site. | MANUAL_REQUIRED. Logged with the caveat that direction/ownership of this secret should be confirmed before assuming it's even ours to rotate via MindStudio's console vs. something MindStudio would need to rotate on their end. |
| `service_role_key` (Supabase) | Per brief: cannot be rotated via API without owner auth. Confirmed no Management API endpoint for this exists in the surface used elsewhere in this repo (`mgmt_sql.py`, `fire_workflow_dispatch`) — only `/database/query`. | MANUAL_REQUIRED. Exact steps: Supabase Dashboard → Settings → API → Regenerate `service_role` key → update `SUPABASE_SERVICE_ROLE_KEY` in GitHub secrets on every repo that uses it (`cli-anything-biddeed` confirmed; check the other 6 active repos listed in CLAUDE.md stack config before considering this done). |
| Anthropic OAuth (`anthropic_oauth_bearer` / `CLAUDE_OAUTH_B64`) | This session's own successful execution (SQL writes, GHA dispatch) is evidence *some* Anthropic auth path is live for this runner — but this session's Bash environment does not expose any `ANTHROPIC_*`/`CLAUDE_*` credential (confirmed: `env | grep` for these returns nothing), so I have no way to determine from inside this session whether it is specifically the `sk-ant-oat01`-family token flagged as leaked and unrotated. Two SECURITY DEFINER functions exist for this (`get_anthropic_oauth_bearer`, `get_claude_oauth`) but calling either would pull a decrypted secret into this context — refused per the never-echo-secrets / never-paste-a-fetched-secret rule. Also noted: `cc-login-telegram.yml` and `claude-login-telegram.yml` (the OAuth-refresh-adjacent workflows) last ran 2026-04-03 — four months stale as of this audit; `claude-login-telegram.yml`'s last 3 runs are `failure`. | UNKNOWN, not tested — logged as such rather than guessed. Recommend Ariel verify directly (console) rather than via a chat session probing vault functions. The 4-month-stale, failing login workflow is a separate finding worth its own look independent of this audit. |

## Deliverable 5 — vault_access_log — absent, documented (not a gap I can close)

- `vault_access_log` does not exist in `public` or `vault` schema (checked
  both via `information_schema.tables`).
- No `pgaudit` (or equivalent) extension installed — full extension list
  checked live: `btree_gin, http, pg_cron, pg_net, pg_stat_statements,
  pg_trgm, pgcrypto, pgsodium, postgis, supabase_vault, uuid-ossp, vector`.
  Supabase Vault (`supabase_vault` 0.3.1) does not log decryption events by
  default — this is a platform limitation, not a misconfiguration in this repo.
- `public.audit_log` / `public.audit_logs` exist but are general
  application-event logs (columns: `user_id`, `resource`, `workflow_id`,
  `action`, etc.) — not vault-secret-read logs. Checked their schema to
  confirm before ruling them out, rather than assuming from the name.
- **No anomaly check was possible** because there is nothing to query — not
  "checked and found zero anomalies." Per CC_META_PROMPT §2.1, absence of
  evidence is not evidence of a clean bill of health; logging this as
  `info`, not silently passing the DoD.

## Summary table (CC_META_PROMPT §6 status per deliverable)

| Deliverable | Status |
|---|---|
| 1. secret_rotation_registry | VERIFIED |
| 2. weekly reminder + Telegram | VERIFIED |
| 3. Supabase IP allowlist | BLOCKED (see `ip-allowlist-research.md`) |
| 4. Resend/MindStudio/Supabase/Anthropic rotation | PARTIAL — research complete, zero rotations executed by design |
| 5. vault_access_log review | PARTIAL — absence documented, no anomaly check possible (nothing to query) |
