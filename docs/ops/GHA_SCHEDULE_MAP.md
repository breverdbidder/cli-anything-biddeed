# GHA Schedule Map — LAUNCH-E DB stampede diet (#20039, 2026-09-05)

Scope: every scheduled GitHub Actions workflow in this repo that was touched to
reduce simultaneous load on Supabase (mocerqjnksmhcjzxrewo) before launch.
Schedules/matrix/timeouts only — zero business-logic edits. See
`docs/intent/20039.md` and `docs/spec/20039.md` for full context.

## Changed schedules

| Workflow | Before | After | Why |
|---|---|---|---|
| `fl-parcel-centroids-all.yml` | matrix limit=8, page_size=1000, cron `20 */2 * * *` (unchanged) | matrix limit=**2**, page_size=**500**, **pre-flight skip if a DB restart was observed <10min ago**, `timeout-minutes: 10` added to `pick-counties` job | 6/7 recent runs failed under an 8-way matrix hammering PostgREST (1000 rows × 300 pages × 8 workers) |
| `centroid-watchdog.yml` | `*/20 * * * *` | `11 */2 * * *` (temporary, revert after 2026-09-10) | was re-arming/redispatching every ~20min, compounding the centroid-matrix load |
| `sentinel-v2.yml` | `*/5 * * * *` | `7,37 * * * *` — **now canonical** for the sentinel trio | consolidates 3 independent schedules into 1 |
| `sentinel.yml` | `*/5 * * * *` | **schedule removed**, workflow_dispatch-only | superseded by sentinel-v2.yml's canonical schedule |
| `everest-sentinel-5-repos-deploy.yml` | `*/10 * * * *` | **schedule removed**, workflow_dispatch-only | consolidated into the sentinel trio's canonical schedule |
| `supabase-summit-verifier.yml` | `*/30 * * * *` | `41 * * * *` — **now canonical** for the SUMMIT-verifier pair | consolidates 2 independent schedules into 1 |
| `summit-verifier.yml` | `0 * * * *` | **schedule removed**, workflow_dispatch + repository_dispatch only | superseded by supabase-summit-verifier.yml's canonical schedule |
| `continuous-executor.yml` | `*/30 * * * *` | `9,39 * * * *` | off quarter-hour, cadence unchanged |
| `task-lifecycle.yml` | `*/30 * * * *` | `14,44 * * * *` | off quarter-hour, cadence unchanged |
| `sync-credentials-to-vault.yml` | `*/15 * * * *` | `6,21,36,51 * * * *` | off quarter-hour; NOT disabled (see below) |
| `gold-standard-tick-watcher.yml` | `*/20 * * * *` | `3,23,43 * * * *` | off the :00 mark, cadence unchanged |
| `s5-meter-emit.yml` | `15 * * * *` | `19 * * * *` | off quarter-hour, cadence unchanged |
| `cmo-factory-distribution-scheduler.yml` | `23 */2 * * *` | **schedule removed**, workflow_dispatch-only | 7/7 recent runs failed on `spi_gates.gtm_factory_halt-open` — gate is Ariel's stop button, by design, not a bug |

## Explicitly left untouched (per hard constraints)

- `cc-runner-ghonly.yml`, `cc-oauth-keepalive.yml`, `winnerdata-ff-send-approved.yml` — named exclusions in the intent file.
- `hetzner-watchdog.yml` (`*/15 * * * *`) and `watchdog-stuck-runs.yml` (`*/15 * * * *`) — both hit quarter-hour marks but neither queries Supabase (SSH ping + GH Actions API + Telegram only), so out of scope for a "DB stampede" diet.
- The ~140 other `schedule:`-bearing workflows in this repo that fire once (or a handful of times) per day at a fixed hour — not part of the sub-hourly/hourly polling set that the issue's measured context (Sentinel, Sentinel V2, sentinel-5-repos-deploy, Sync Credentials, Watchdog, Gold Standard Tick Watcher, centroid-watchdog, SUMMIT Verifier, Continuous Executor, Task Lifecycle, fl-parcel-centroids-all) identifies as the actual stampede contributors. Retiming all ~140 would be a large, low-value diff against K2/K3 surgical-change guidance; flagged here rather than silently skipped.

## Notable trade-off called out for Ariel

Consolidating the sentinel trio down to one active schedule means
`sentinel.yml`'s patrol script and `everest-sentinel-5-repos-deploy.yml`'s
queued-deploy poller **no longer run on autopilot** — only
`sentinel-v2.yml`'s patrol fires on the canonical `7,37 * * * *` schedule.
Queued five-repo deploys will sit until manually dispatched. This is exactly
what issue #20039 scope item 2 asked for ("keep all three workflow files;
only one carries `schedule:`"), but it is a real reduction in autonomous
coverage, not just a reschedule — flagging per Honesty Protocol rather than
letting it pass as a no-op change.
