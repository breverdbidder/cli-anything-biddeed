# CI V6.5 Artillery

Replaces the deprecated `claude-code-direct.yml` (denylisted 2026-05-06 after 100%-fail at 576/day for 13 days).

## Architecture

```
chat session (Claude AI)
  → INSERT INTO summit_chat_dispatch (kind='pg_net_request', target=GH workflow_dispatch endpoint)
  → chat_bypass_auto_consumer fires pg_net.http_post
  → GitHub Actions repository_dispatch → ci-v65-artillery.yml
  → Self-hosted Hetzner runner: clones repo, installs deps, runs runner.py
  → runner.py checkpoints to ci_v65_phases and writes findings to ci_v65_event_log / ci_v65_pages / ci_v65_screenshots
  → Final step annotates summit_chat_dispatch with workflow_run_id + status
```

No `push` or `schedule` triggers — invocation is **explicit only** to prevent runaway.

## Why this design avoids the May 6 disaster

| Symptom of claude-code-direct.yml | Mitigation here |
|---|---|
| Runaway 576/day fires | `repository_dispatch` only, no `push` or `schedule` |
| 100% fail rate, no signal back | Checkpoint to `ci_v65_phases` at start AND end (even on failure via `if: always()`) |
| Watchdog kills (30min) | Hard `timeout-minutes: 25` per job |
| Concurrent thrash | `concurrency.group` per dossier+phase |
| Credential leak risk | Pre-flight grep blocks any `ghp_`, `sbp_`, `service_role`, `AIza` in ci/v65/ |

## Subcommands

```bash
python ci/v65/runner.py checkpoint --status running --note "starting"
python ci/v65/runner.py execute --phase P1_RECON --mode canary
python ci/v65/runner.py annotate-dispatch --dispatch-id <uuid> --workflow-run-id <id> --status success
```

## Modes

- **canary** (default): logs a synthetic `V`-marked event to `ci_v65_event_log` and exits 0. Proves round-trip.
- **full**: dispatches to per-phase handlers in `runner.py` (P1_RECON, P2_TECH_FOOTPRINT, P5_API_CAPTURE). Implementation expands per SUMMIT package phase brief.

## Required GH secrets

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Self-hosted runner labels: `[self-hosted, hetzner]`.

## Honesty Protocol V3

All artillery findings include `honesty_marker` in `{V, U, I, A, UNK}` per the Everest protocol. Wrong VERIFIED markers carry 3× penalty in `honesty_violations`.

## Status

- 2026-05-23 — v0.1 canary scaffold shipped. Replaces dead `claude-code-direct.yml`.
