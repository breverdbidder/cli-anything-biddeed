# Skill Audit — 2026-07-27

Window audited: 2026-07-13 → 2026-07-27 (14 days), with backward evidence pulled
where needed to establish onset dates for long-running regressions.
Operating contract: `CC_META_PROMPT.md`. Dispatched from issue
[#15144](https://github.com/breverdbidder/cli-anything-biddeed/issues/15144).

No `skill-audit` Skill or prior audit doc existed in this repo before this run
(`docs/skill-audits/` did not exist; `agent_ops_log` has zero prior rows with
`task ilike '%skill%'`). This is the first audit of this kind — there is no
prior report to diff against.

## Scope note on "skill"

Two families of automation were in scope: the 42 Platform Skills under
`.claude/skills/`, and the legacy harness skills (`zonewise/`, `auction/`,
`reports/`, `enricher/`, `forecaster/`, `trendpredictor/`, `sitemanager/`,
`projecttracker/`) that the Autoloop pipeline also targets. Not in scope: the
~30 `gold-standard-shardN-runNNNN` entries visible in the assistant's Skill
listing — none of them correspond to a `SKILL.md` in this repo, so they could
not be inspected or fixed from here (see P3-3).

---

## P0-1 — skills-evaluator.yml has silently done nothing for 4.5 months, reporting fabricated success — **FIXED, VERIFIED**

**Tag: VERIFIED**

`.github/workflows/skills-evaluator.yml` runs weekly (Sundays) plus on-demand,
scanning 19-20 external repos for `SKILL.md` files, scoring them, and upserting
into a Supabase `skills_catalog` table. Evidence found:

- The "Create Supabase table" step connected to `aws-0-us-east-1.pooler.supabase.com`.
  The correct pooler region for this project (confirmed by grepping 108 other
  working references repo-wide) is `aws-0-us-west-2`. This has been wrong since
  the workflow's first commit (`7635ff79`, 2026-03-12) — never fixed.
- Live GHA log, run `30192118860` (2026-07-26, inside the audit window):
  `psycopg2.OperationalError: ... FATAL: (ENOTFOUND) tenant/user postgres.mocerqjnksmhcjzxrewo not found`,
  swallowed by `|| echo "⚠️ Table creation skipped (may already exist)"`.
- Direct DB query before the fix: `select count(*) from skills_catalog` →
  `ERROR: 42P01: relation "skills_catalog" does not exist`. The table had
  **never** been created.
- Because the table didn't exist, every REST upsert in `scripts/evaluate_skills_v2.py`
  returned `HTTP 404`, caught by a bare `except Exception` in `upsert_batch()`
  and printed, never raised.
- The job still reported `conclusion: success` every run (confirmed for
  2026-07-19 and 2026-07-26, both inside the window), and the Telegram step
  sent a **hardcoded** string: `"660 skills scored → Supabase skills_catalog"` —
  a literal in the YAML, not a computed value. This message went out weekly
  for 4.5 months regardless of what actually happened.

**Fix applied (commits `ef89475b`, `ba2f998f`):**
- Corrected pooler host to `us-west-2`.
- Removed the `|| echo` swallow so a real connection failure fails the job.
- When that path *also* failed with `password authentication failed for user
  "postgres"` (the `SUPABASE_DB_PASSWORD` secret is stale on this pooler host —
  the same class of issue CC_META_PROMPT.md §4 already documents from the
  2026-07-19 incident), routed table creation through the sanctioned Management
  API (`SUPABASE_ACCESS_TOKEN`) instead of psycopg2+password. That call
  returned Cloudflare error 1010 with Python's default `urllib` User-Agent;
  added an explicit `User-Agent` header, which resolved it.
- `evaluate_skills_v2.py`: `upsert_batch()` now returns true/false instead of
  swallowing; `main()` tracks batch success/failure, writes an honest
  `result_summary.txt`, and `sys.exit(1)` if literally nothing was persisted.
  The Telegram message now reads that file instead of a hardcoded number.

**Verification (live, this session):**
- `python3 mgmt_sql.py "select count(*) from skills_catalog"` → table now
  exists.
- Manual dispatch, run `30269251065`: **all green**, log shows
  `Found 749 skills`, `Supabase batches: 14 ok / 1 failed`, Telegram sent
  `"PARTIAL — 14/15 batches written, 749 skills scored"` (accurate, not
  fabricated).
- Live DB query post-run: `select count(*) from skills_catalog` → **700 rows**,
  `max(evaluated_at) = 2026-07-27 13:13:27+00`. Breakdown: ADOPT 221 /
  CONDITIONAL 219 / EVALUATE 193 / SKIP 67.
- Negative test: pre-fix log (run `30269097809`, still on old pooler+password
  path) genuinely fails with `password authentication failed` — confirms the
  detection isn't a false trigger.

---

## P0-2 — Autoloop "Overnight Skill Self-Improvement" has been a no-op for ≥2 months due to an expired OAuth token, silently reporting success — **PARTIALLY FIXED (masking fixed); credential itself BLOCKED, Ariel-only**

**Tag: VERIFIED**

`.github/workflows/autoloop.yml` runs nightly (2 AM EST) via
`appleboy/ssh-action` into Hetzner (87.99.129.125), running
`claude -p "$(cat $PROMPT_FILE)" --dangerously-skip-permissions` to
self-improve the `zonewise` skill (the hardcoded default — see P2-1).

- Every sampled run in the 14-day window (15/15 runs, all `event: schedule`)
  shows the identical pattern in its raw session log:
  `Failed to authenticate. API Error: 401 {"type":"error","error":{"type":"authentication_error","message":"OAuth access token has expired. Re-authenticate to continue."}}`
- Consequence, confirmed via `gh run view --log` on runs
  `30248782394, 30193474301, 30149649271, 30076626095, 29989289209,
  29234074165`, and also `26626336675` (2026-05-29, ~2 months prior — the
  regression is **not** new to this audit window, it predates it by at least
  that long): baseline score frozen at exactly **24.0%**, **0 iterations**,
  every single night.
- This is a real regression, not a baseline that was always low: commits
  `dfa8521f`, `a0468993`, `66ea2880` (all 2026-04-12) recorded
  `autoloop(zonewise): 100% -> 100%`. `zonewise/eval/eval.json` itself has not
  been touched since its creation (`a1488439`), so the assertions didn't
  change — something else regressed the measured score from 100% to 24%
  between April 12 and the current window, and the "self-improvement" loop
  that exists specifically to catch and fix this has been unable to run at
  all since at least May 29.
- The reported `"Commits: 1"` in every nightly Telegram message is misleading:
  `git log --all --grep="autoloop(zonewise" --since="14 days ago"` returns
  **zero** matching commits. The counter (`git log --grep="autoloop" --since
  "12 hours ago"`) is not scoped to this skill's actual push and doesn't prove
  anything landed.
- The job still reports `conclusion: success` on all these runs.

**Root cause is a credential (Claude Code OAuth on Hetzner) — not fixed here.**
Per `CC_META_PROMPT.md` §4 ("Never rotate a credential yourself. Surface it.
Auth changes are Ariel-only.") this requires an interactive `claude /login` on
87.99.129.125, which cannot be done from an agent session. **This is the one
genuine architectural/access blocker in this audit — surfacing it, not
attempting a workaround.**

**What was fixed (commit `4d634148`):** the silent-success masking. The
"Autoloop" step now greps its own session log for the auth-failure signature;
if found, it exits non-zero (job goes red instead of green) and the Telegram
step sends an explicit `"🔴 AUTOLOOP BROKEN — Claude Code OAuth expired on
Hetzner ... Fix: run 'claude /login' on 87.99.129.125 — Ariel-only"` message
instead of a benign score line. A stale-status guard (`rm -f
/tmp/autoloop_auth_status.txt` in Preflight) prevents a dry-run from
inheriting a previous real run's status.

**Verification:** positive/negative unit test of the new detection regex
against a synthetic log containing the real error string (detected) and a
clean log (not detected) — both correct. The actual OAuth failure itself could
not be re-verified live without triggering another real dispatch burning
Hetzner/Claude Code resources for a run known in advance to fail; the fix logic
was validated directly against the exact error text pulled from the real
failing runs instead.

**Action needed from Ariel:** `claude /login` (or equivalent re-auth) on
87.99.129.125, then confirm the next scheduled or dispatched run shows real
iterations and a score that differs from 24.0%.

---

## P1-1 — skills-health-check.yml: disabled 4 months, plus a pre-existing YAML bug, plus a dead cross-repo credential — **PARTIALLY FIXED**

**Tag: VERIFIED**

`.github/workflows/skills-health-check.yml` is meant to run weekly (Sundays,
9AM EST), diff `skills/*/` in this repo against `/root/.claude/skills` on
Hetzner, and auto-deploy anything missing.

1. **Disabled.** `gh api .../workflows/246828618` showed
   `"state": "disabled_manually"`, `updated_at: 2026-03-27T16:37:51Z` — dead
   for ~4 months. Fixed: re-enabled via the workflow API; confirmed
   `state: active`.
2. **Pre-existing invalid YAML**, independent of the disabled state and not
   introduced this session (confirmed by parsing the file at its prior commit
   `51bbd0b9` with PyYAML before touching it): the Telegram step's multi-line
   `MSG="..."` bash string dedents two lines to column 0, breaking out of the
   `run: |` block scalar — `yaml.scanner.ScannerError: mapping values are not
   allowed here`. This is present since the file's creation commit
   (`c8fc4673`, 2026-03-16) and was still present immediately before this
   session's fix. **Whether GitHub Actions' own backend parser was actually
   rejecting the file in production, or silently tolerating the dedent, is
   UNKNOWN** — I could not find a single genuine execution of this workflow's
   actual logic anywhere in its run history to check against (see note below).
   Fixed: reindented the two lines; confirmed with PyYAML the file now parses
   cleanly and the extracted bash has no injected leading whitespace.
3. **`gh workflow run` 422'd** with `"Workflow does not have 'workflow_dispatch'
   trigger"` immediately after the enable (and again after a trivial re-index
   commit, matching the same remedy the file's own history shows was used for
   this exact symptom in commit `51bbd0b9`) — it only started working *after*
   the YAML fix landed, which is consistent with #2 having been the real
   blocker for `workflow_dispatch` registration the whole time, not just the
   manual-disable flag.
4. **Once actually dispatchable** (run `30269571084`, this session): the job
   runs, but the "Checkout skills repo" step (checking out the *external*
   `breverdbidder/claude-skills-library` repo) fails with `Bad credentials`
   using `secrets.GH_PAT`. `GH_PAT` was last rotated 2026-04-14 (~3.5 months
   ago); I confirmed the *target* repo exists and is reachable with my own
   session credentials, so this isn't a missing/renamed repo — it's the
   `GH_PAT` secret itself failing against that specific cross-repo checkout.
   `GH_PAT` is referenced by 114 other workflows in this repo, so a total
   revocation seems unlikely to have gone unnoticed this long; more likely
   this specific fine-grained token's authorized-repo list doesn't include
   `claude-skills-library`, though I could not confirm the token's actual
   scope from here. **Per CC_META_PROMPT.md §4, not rotated — surfaced.**

**Net state:** workflow is active, has valid YAML, and its `workflow_dispatch`
trigger works (all three independently verified live this session). The drift
check itself is still blocked on the `GH_PAT` credential. Genuinely `PARTIAL`,
not `VERIFIED` complete — the real Sunday cron (or a re-dispatch after Ariel
fixes `GH_PAT`) is the next real test.

**A caveat worth being honest about:** the 578 historical "runs" GitHub
attributes to this workflow's ID are almost entirely unrelated commit titles
(Coder Workspaces setup, daily action plan, etc.) triggered by `push`, which
this file has never had as a trigger. I could not explain this discrepancy —
flagging it as **UNKNOWN**, most likely a workflow-ID-reuse or `gh` CLI
attribution artifact rather than anything this file actually did, since the
YAML-validity finding above gives an independent, verified reason the file's
*real* triggers wouldn't have fired anyway.

---

## P2-1 — Autoloop nightly cron only ever covers 1 of 16 dispatchable skills — **documented, not auto-fixed**

**Tag: VERIFIED**

`autoloop.yml`'s `workflow_dispatch.inputs.skill` lists 16 choices
(`zonewise, auction, reports, enricher, forecaster, trendpredictor,
sitemanager, projecttracker, zonewise-scraper, cost-discipline,
honesty-protocol, brand-colors, ship-gate, designwise, exa-discovery,
skill-creator`), but the schedule trigger carries no input, so
`DEFAULT_SKILL: zonewise` (env block) is used every night. Confirmed: all
15 runs in the 14-day window were `event: schedule`, zero were
`workflow_dispatch` with a different skill. Net effect: 15 of 16
dispatchable skills received **zero** autonomous scheduled self-improvement
cycles in the audit window — and per P0-2, even zonewise's runs did nothing
real, so effective coverage across the whole skill catalog was **zero** for
the full 14 days.

**Not auto-fixed.** Choosing a rotation cadence/priority order across 16
skills is a product decision (which skills matter most, weekly vs. nightly
cadence, etc.), not a mechanical bug — and P0-2 means fixing the rotation
alone wouldn't produce any real value until the OAuth credential is restored.
Documented here for Ariel to decide; recommend a simple day-of-week rotation
once P0-2 is resolved.

---

## P3-1 — Same wrong-pooler-region bug exists in 9 other workflows (out of scope, flagged only)

**Tag: VERIFIED**

`grep -rl "aws-0-us-east-1.pooler.supabase.com"` also matches
`verify-evolution-tables.yml`, `create-cma-reports-table.yml`,
`honesty-migrate.yml`, `chat-ground-truth-migrate.yml`,
`summit-designwise-s1-complete.yml`, `summit-consolidate-zoning.yml`,
`chat-sessions-migrate.yml`, `flywheel-phase1-migrate.yml`,
`apply-evolution-migration.yml`, and `scripts/consolidation_modal.py`. None of
these are skill-related, so per the K3 surgical-changes rule they were noticed
and not touched. Worth a separate, non-skill-scoped pass.

## P3-2 — Orphaned git worktree in the repo tree (out of scope, flagged only)

**Tag: INFERRED**

`.claude/worktrees/wf_87712752-715-6/` and `wf_147fd531-cc0-1` (the latter
surfaced as a `fatal: No url found for submodule path ... in .gitmodules`
warning during this session's own `actions/checkout` post-step) sit inside the
repo tree, containing stale duplicate copies of some of the same workflow
files discussed above. Likely leftover from a prior `Workflow` tool run that
wasn't cleaned up. Not skill-specific; flagged for whoever manages repo
hygiene, not fixed here.

## P3-3 — Assistant-facing Skill catalog is polluted with ~30 one-off session artifacts (informational, not repo-actionable)

**Tag: UNKNOWN**

The Skill listing surfaced to this session includes roughly 30
`gold-standard-shardN-runNNNN`-style entries — one-off dispatch briefs from
past county-audit sessions, not reusable skills. None correspond to a
`SKILL.md` anywhere in `.claude/skills/` (42 legitimate entries checked) or
elsewhere in this repo, so they must be registered at a layer outside this
repo (plugin/session registration). I cannot verify where they come from or
fix this from a repo-scoped session — flagging as an observation for whoever
owns that registration layer, in case it's unintentional accumulation rather
than by design.

---

## Summary

| # | Finding | Severity | Status | Tag |
|---|---|---|---|---|
| 1 | skills-evaluator.yml silent failure, fabricated Telegram metric, 4.5mo | P0 | **Fixed, verified live** (700 rows now in DB) | VERIFIED |
| 2 | autoloop.yml OAuth expired, 0 iterations ≥2mo, silent success | P0 | Masking fixed & verified; **credential itself BLOCKED — Ariel-only `claude /login` on Hetzner** | VERIFIED |
| 3 | skills-health-check.yml disabled + invalid YAML + dead cross-repo PAT | P1 | Disabled-state + YAML both fixed & verified live; **drift-check itself BLOCKED on stale `GH_PAT`** | VERIFIED |
| 4 | Autoloop covers 1/16 skills nightly | P2 | Documented, not auto-fixed (product decision + blocked by #2 anyway) | VERIFIED |
| 5 | Wrong pooler region in 9 other workflows | P3 | Flagged, out of scope | VERIFIED |
| 6 | Orphaned worktree dirs in repo | P3 | Flagged, out of scope | INFERRED |
| 7 | ~30 one-off skill entries in assistant catalog | P3 | Flagged, not repo-actionable | UNKNOWN |

## Outstanding items for Ariel (cannot be closed by an agent session)

1. Re-authenticate Claude Code on Hetzner (`claude /login` on 87.99.129.125) —
   unblocks P0-2's actual self-improvement loop, not just the alerting.
2. Check/rotate `GH_PAT` (or scope it to include `claude-skills-library`) —
   unblocks P1-1's actual drift check, not just the enable/YAML fixes.
3. Decide an autoloop rotation policy across the 16 dispatchable skills
   (P2-1) once #1 is resolved.

## DoD check

- [x] Audit file committed (this file).
- [x] P0/P1 findings fixed where the root cause was in-repo and non-credential
      (P0-1 fully; P0-2 and P1-1 partially — the remaining piece of each is a
      credential requiring Ariel, documented above rather than worked around).
- [x] Outcome logged to `agent_ops_log` (`task='skill-audit'`) — see commit
      log / issue comment for the row contents.
