# Skill Audit — 2026-08-24

Window audited: 2026-08-17 → 2026-08-24 (7 days), by `created_at` on
`public.agent_ops_log`. Live rows observed span `2026-08-17 13:35:06 UTC` →
`2026-08-24 13:00:00 UTC`. Operating contract: `CC_META_PROMPT.md`.

Connectivity used: `mgmt_sql.py` (Supabase Management API,
`SUPABASE_ACCESS_TOKEN`), per CC_META_PROMPT.md §4 fallback ladder.
`SUPABASE_DB_PASSWORD` / direct psql was not attempted first — the prior two
audits (2026-07-27, 2026-08-17) already document that path as unreliable, so
this session went straight to the sanctioned no-HITL path rather than
re-diagnosing a known, already-logged constraint.

This is the third audit of this kind. Prior reports:
`docs/skill-audits/skill-audit-2026-07-27.md` (14-day window) and
`docs/skill-audits/skill-audit-2026-08-17.md` (7-day window, immediately
prior). Diffed against the 08-17 report below where relevant — this is the
first window where prior findings can be checked for actual resolution
rather than just re-confirmed as still-open.

---

## 1. `agent_ops_log`, past 7 days — headline numbers

`SELECT status, severity, count(*) ... WHERE created_at >= now() - interval '7 days' GROUP BY 1,2`

| status | severity | count |
|---|---|---|
| VERIFIED | warn | 48 |
| VERIFIED | info | 30 |
| PARTIAL | info | 16 |
| SKIPPED | info | 15 |
| BLOCKED | blocker | 4 |
| PARTIAL | warn | 3 |

**Total: 116 rows, 57 distinct `dispatch_id`s.** `status = 'BLOCKED' OR
severity = 'blocker'` (the task-1 filter): **4 rows**, all `BLOCKED/blocker`
(no `VERIFIED/blocker` or `PARTIAL/blocker` rows this window — a smaller,
cleaner blocker set than the 08-17 window's 40).

Volume is back-loaded but less extremely than the prior window: 2026-08-17
through 08-23 totaled 61 rows (mostly the twice-daily `zonewise-gis-tick`
cron plus daily `acquisition_sprint_daily`/`auction_deposit_deadline_audit`
crons), and 2026-08-24 alone (the day this audit runs) totaled 55 rows —
driven by a single 34-row secret-rotation alert burst
(`secret-rotation-check`, 09:00 UTC) plus a cluster of `winnerdata-ff`/
`winnerdataai-web` dispatch activity. Not a steady daily cadence; do not read
day-over-day trend into this table without accounting for both bursts.

Negative-test note per the brief: dispatches **did** occur in this window
(57 distinct, not zero), so this is not the empty-window case — the
sub-findings below are grounded in real rows, not invented.

---

## 2. Top 3 friction patterns

### F1 — `zonewise-gis-100pct-mission` is a stuck auto-continuation loop: 7+ days of unchanged progress, 14+ never-closed GitHub issues

**Tag: VERIFIED**

This is the single largest source of rows in the window (28 of 116, 24%) and
the clearest recurring pattern. A cron (`zonewise-gis-tick-*`) fires every 6
hours. Every *other* tick logs `SKIPPED`: `"Likely session still running
(last dispatch <ts>); gap_count=14"`. The ticks in between log `PARTIAL`:
`"Auto-dispatched continuation issue #<N>, gap_count=14"`.

The critical detail: **`gap_count` is `14` on every single row in the
window**, from `zonewise-gis-tick-2026-08-17 18:00:00` through
`zonewise-gis-tick-2026-08-24 12:00:00` — seven days, 14 `PARTIAL` +
14 `SKIPPED` rows, zero observed change in the metric the loop exists to
close. Cross-checked against GitHub: `gh issue list --search "zonewise-gis
in:title"` returns issues #19083 (2026-08-15) through #19416 (2026-08-24) —
**every one of them is still `OPEN`**, none closed, none merged. The loop
predates this audit window (earliest matching issue is 08-15, two days
before this window starts) and has been auto-opening a new "autonomous
continuation" issue every 12 hours for at least 9 days with no observed
resolution and no visible mechanism that would ever stop it or escalate it.

This is exactly the failure shape CC_META_PROMPT.md §5 warns about
("Concurrency and runner health... burst dispatch takes down every
concurrent brief") from a different angle: not a burst taking down other
work, but an unbounded self-perpetuating backlog that never gets marked
`BLOCKED` and stopped — it just keeps reporting `PARTIAL`/`SKIPPED` forever
without ever tripping a stop condition. `agent_ops_log` faithfully records
this every 6 hours; nothing reads the 7-day flatline and calls it out.
**No prior audit flagged this** — it is new this window (or rather, was
present but below the two prior audits' higher-blocker-count noise floor).

### F2 — A previously-fixed model-deprecation bug class recurred a third time, in a file the prior fixes didn't touch

**Tag: VERIFIED**

`guard-diagnose-leon` / task `guard-diagnose`, **BLOCKED, blocker**,
2026-08-23 22:26: both configured Gemini keys
(`gemini_api_key_biddeed`, `gemini_api_key`) failed identically —
`Gemini 404: ... "This model models/gemini-2.0-flash is no longer
available. Please update your code to use models/gemini-3.6-flash..."`.

This is not a new bug class. `git log --all --grep="gemini.*404\|gemini.*
deprecat"` shows **two prior fix commits** already landed for exactly this:
`375b5dd8` ("fix: update worker Gemini direct call from gemini-2.0-flash
(deprecated) to gemini-2.5-flash") and `48d7e878` ("fix: update Gemini model
gemini-2.0-flash → gemini-2.5-flash"). Neither touched
`supabase/functions/gold-standard-guard-diagnose/index.ts`, which still
hardcodes `gemini-2.0-flash` today — confirmed live via `grep -rl
"gemini-2.0-flash"`, which additionally returns **8 more files** still on
the deprecated model: `evolution/evolver.py`,
`youtube_transcript/yt_transcript_squad.py`, `src/worker.js`,
`.github/workflows/production-assets.yml`,
`.github/workflows/gemini-forensic.yml`, `scripts/ml_priority_engine.py`,
`scripts/chat_intelligence_pipeline.py`, `scripts/l3_analyze.py`.

This is the identical failure shape already named in CC_META_PROMPT.md's own
AUTO-LEARNINGS section from 2026-08-03: *"A fixed pooler-region bug recurred
in 9 other workflows — grep repo-wide before closing bug class."* That
learning was written for a different bug (pooler region) but the process gap
it describes — fixing one call site without grepping for siblings — is
recurring with a new bug (model name). The upstream model has moved twice in
this incident's error message alone (`2.0` → `2.5` already fixed elsewhere,
now Google's 404 says to move to `3.6`), so a repo-wide fix today will likely
need repeating again unless it's done as a single grep-and-fix-all pass
rather than another one-off patch.

### F3 — `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` are referenced by 3 workflows but do not exist as secrets; only `CF_API_TOKEN`/`CF_ACCOUNT_ID` do

**Tag: VERIFIED**

`issue-19392` / `winnerdata-ff worker: Cloudflare deploy`, **BLOCKED,
blocker**, 2026-08-24 11:20: `"GHA run 32721188583 conclusion=failure. Guard
step: Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID (exact names). gh
secret list confirms absent; differently-named CF_API_TOKEN/CF_ACCOUNT_ID
exist but were not substituted per explicit dispatch instruction not to
route around missing secrets."` A second row in the same dispatch,
`winnerdata-ff: Cloudflare Access on /portal and /ff/*`, **BLOCKED,
blocker**, same timestamp, same root cause.

Verified independently: `gh secret list` confirms only `CF_ACCOUNT_ID` and
`CF_API_TOKEN` exist (created 2026-03-19). `grep -rl "secrets\.CLOUDFLARE_
API_TOKEN\|secrets\.CLOUDFLARE_ACCOUNT_ID" .github/workflows/` returns 3
files: `nexus-dns-fix.yml`, `deploy-winnerdata-ff.yml`,
`fix-biddeed-via-zw.yml` — all three reference a secret name that has never
existed in this repo. This is a naming-convention split baked into the repo
(some workflows correctly use `CF_*`, three use `CLOUDFLARE_*`), not a
one-off typo in a single dispatch, and it correctly blocked rather than
silently routing around the mismatch — the dispatch behavior here was
correct per CC_META_PROMPT.md §4 ("never rotate/route around a credential
yourself, surface it"). The fix is either renaming the 3 workflows to `CF_*`
or adding `CLOUDFLARE_*` as aliased secrets; either is a small, mechanical,
non-credential-rotation fix that doesn't require Ariel, but nothing in this
window's dispatches attempted it (out of scope for the specific brief that
hit it).

---

## 3. Per-skill invocation table — `.claude/skills/` (49 skills, excluding `LICENSE-*`/`README.md`)

Method: `task ILIKE '%name%' OR evidence ILIKE '%name%' OR dispatch_id ILIKE
'%name%'` against every `agent_ops_log` row in the 7-day window (single
batched SQL query, one row per skill), cross-checked against `git log
--since="7 days ago" -- .claude/skills/` and `.claude/session-logs/`
filenames dated in-window.

The skill catalog grew from 42 (08-17 audit) to 49 this window: 6 new skills
vendored via commit `2e053345` ("Add 6 skills from anthropics/skills fork":
`academy-guide`, `claude-api`, `discernment-nudge`, `doc-coauthoring`,
`slack-gif-creator`, `webapp-testing`).

| Skill | Fired in window? | Evidence |
|---|---|---|
| academy-guide | **No** | 0 hits — added this window (2e053345), not yet invoked |
| api-design-principles | **No** | 0 hits |
| architecture-patterns | **No** | 0 hits |
| auction-brief | **No** | 0 hits — notable given CLAUDE.md lists this as a daily-run command; the actual daily auction cron in-window (`auction_deposit_deadline_audit`, 7 rows) runs as a bare SQL/cron job, not through this Skill |
| brainstorming | **No** | 0 hits |
| brand-colors | **No** | 0 hits |
| browser-use | **No** | 0 hits |
| claude-api | **No** | 0 hits — added this window, not yet invoked |
| cost-discipline | **No** | 0 hits |
| county-setup | **No** | 0 hits |
| deal-intel | **No** | 0 hits |
| designwise | **No** | 0 hits |
| discernment-nudge | **No** | 0 hits — added this window, not yet invoked |
| dispatching-parallel-agents | **No** | 0 hits |
| doc-coauthoring | **No** | 0 hits — added this window, not yet invoked |
| dream | **No** | 0 hits |
| exa-discovery | **No** | 0 hits |
| executing-plans | **No** | 0 hits |
| finishing-a-development-branch | **No** | 0 hits |
| firecrawl-agent | **No** | 0 hits |
| firecrawl-browser | **No** | 0 hits |
| firecrawl-map | **No** | 0 hits |
| firecrawl-scrape | **No** | 0 hits |
| firecrawl-search | **No** | 0 hits |
| honesty-protocol | **No** | 0 hits by name — but its *rules* are followed in spirit throughout the window (the VERIFIED/PARTIAL/BLOCKED discipline itself, plus explicit correction rows like the Clerk dispatch's "[CORRECTION 2026-08-20 ... my first secrets check was WRONG TWICE]"); discipline is baked into CC_META_PROMPT.md rather than invoked as a Skill |
| nodejs-backend-patterns | **No** | 0 hits |
| playwright-best-practices | **No** | 0 hits |
| python-performance-optimization | **No** | 0 hits |
| react-best-practices | **No** | 0 hits |
| receiving-code-review | **No** | 0 hits |
| requesting-code-review | **No** | 0 hits |
| search | **No** | 2 raw text hits, both confirmed substring false positives on inspection ("confirmed via repo-wide search" in `ci_acres_battle_card`; the 08-17 audit's own logged row referencing "search"/"search snippets" text) — neither references the `/search` skill |
| ship-gate | **No** | 0 hits — notable; several rows this window claim `VERIFIED` shipped outcomes (e.g. `winnerdata-ff worker: RLS/RPC layer live-verified`, `biddeed.ai Clerk PRODUCTION instance live`) without a `ship-gate`-labeled row |
| skill-creator | **No** | 0 hits |
| slack-gif-creator | **No** | 0 hits — added this window, not yet invoked |
| subagent-driven-development | **No** | 0 hits |
| supabase-postgres-best-practices | **No** | 0 hits — notable given the volume of raw SQL/RLS/schema work this window (winnerdata RLS/RPC, PostgREST schema exposure attempt) |
| systematic-debugging | **No** | 0 hits |
| test-driven-development | **No** | 0 hits — notable given `winnerdata-momentum-delivery-bridge` logged "19 tests incl 3 negative tests, all green" as evidence without a TDD-skill-labeled row |
| tldr | **No** | 0 hits — no `.claude/session-logs/*.yml` files dated in-window (`2026-08-1[7-9]` / `2026-08-2[0-4]` prefixes both return empty against the current filename set) |
| transcript | **No** | 0 hits |
| ui-ux-pro-max | **No** | 0 hits — notable given two landing-page/website build dispatches this window (`winnerdataai-web scroll-craft`, `Ship v1 Protection Partners website`) |
| using-git-worktrees | **No** | 0 hits; `git worktree list` shows only the main checkout, no active worktrees this session |
| verification-before-completion | **No** | 0 hits by name, same shape as honesty-protocol — behavior present, skill not invoked |
| vet | **No** | 0 hits |
| webapp-testing | **No** | 0 hits — added this window, not yet invoked |
| wizard | **No** | 0 hits — vendored 2026-08-03, still zero invocation evidence 3 weeks later |
| writing-for-agents | **No** | 0 hits — same as `wizard` |
| writing-plans | **No** | 0 hits |
| zonewise-scraper | **No** | 0 hits — despite F1 (`zonewise-gis-100pct-mission`) being the single largest activity cluster in the entire window and squarely in this skill's stated trigger domain (BCPAO/FL GIO/zoning assignment), none of its 28 rows are logged under this skill's name |

**49/49 skills: zero observed invocation evidence in this window.** Third
consecutive audit with this result (42/42 on 07-27, 42/42 on 08-17, now
49/49 including 6 newly-vendored skills that have had zero opportunity to
prove otherwise yet). This is no longer a single-window anomaly — it is the
steady-state operating pattern of this repo: dispatched CC sessions run
against ad-hoc, issue-numbered task labels, and the `.claude/skills/`
catalog has never once shown up as the mechanism through which that work was
invoked, across three audits spanning 21 days.

Caveat, stated per HONESTY PROTOCOL, unchanged from prior audits:
absence-of-evidence in `agent_ops_log`/git is not proof the Skill tool was
never invoked inside some interactive chat session this week —
`agent_ops_log` is populated by dispatched CC sessions per CC_META_PROMPT.md
§6, and this audit has no visibility into ad-hoc chat sessions that never
logged a row or committed anything. **Tag: CONFIRMED for the
dispatched/logged population, UNKNOWN for any unlogged interactive usage.**

---

## 4. CC_META_PROMPT.md drift check

Compared the document's rules against observed behavior this window and
against the outstanding items from the 2026-08-17 audit.

- **§0 Prime directive / VERIFIED discipline: no drift.** Status/severity
  distribution in §1 and explicit self-correction rows (the Clerk dispatch's
  "[CORRECTION 2026-08-20 ... my first secrets check was WRONG TWICE]," which
  re-verified and reversed its own prior "zero GitHub Actions secrets" claim
  after an owner challenge) show the rule being actively exercised, not just
  documented.
- **§4 credential fallback ladder: followed correctly this window** — no
  `SUPABASE_DB_PASSWORD`-stale encounters logged in-window at all (unlike
  08-17's 5), and this audit itself used the sanctioned Management API path
  from the start rather than re-discovering the same staleness. F3's
  Cloudflare finding is the same *pattern* (missing/misnamed credential
  correctly surfaced rather than routed around) applied to a different
  secret.
- **§5 concurrency / no self re-dispatch: mostly followed, but F1 is a
  gap the document doesn't currently cover.** §5 warns about burst dispatch
  and self re-dispatch of *failed* runs; it does not address an
  auto-continuation loop that keeps reporting `PARTIAL` (not `BLOCKED`) and
  therefore never trips the "stop and report" behavior in §7 ("A dry run
  produces a result set you cannot fully explain" / "you have retried a
  transient failure 3 times" are the closest matches, but `gap_count`
  frozen at 14 for 7 straight days is neither a dry run nor a transient
  failure — it is a stalled steady state with no named stop condition).
  Worth an addition for `skill-meta-updater`, flagged here per this task's
  non-goals rather than edited directly.
- **§2.4 "errored is not failed" / four-bucket discipline: followed.**
  `SKIPPED` (15 rows, 14 of which are F1's own SKIPPED half) stayed distinct
  from `BLOCKED` (4 rows) throughout.
- **AUTO-LEARNINGS section: stale, and its own feedback loop is
  demonstrably broken.** The section footer still reads `<!-- last updated
  2026-08-03 -->` with no entries added since, despite `skill-meta-updater.
  yml` running (and reporting `conclusion: success`) on 2026-08-17 18:49,
  immediately after last week's audit commit landed. Traced the actual run
  (`32056896953`): it does not edit `CC_META_PROMPT.md` directly — it opens
  a GitHub issue (`#19240`, "[skill-meta-updater] Auto-learn from
  skill-audit 2026-08-17") and then tries to dispatch `cc-runner-ghonly.yml`
  to do the edit. That dispatch was skipped: `"cc-runner-ghonly.yml already
  has a run in-progress/queued (1 in_progress, 2 queued) — skipping
  dispatch... Re-run manually once clear."`, followed by `exit 0`. Checked
  issue `#19240` directly: **still `OPEN`, zero comments, 7 days later** —
  nothing ever re-ran it. So the mechanism that is supposed to turn last
  week's F1/F2/F3 findings into durable `CC_META_PROMPT.md` rules silently
  no-oped and nothing retried it. This is the same failure shape as F1 in
  reverse — a loop reports a soft non-terminal outcome (here: exit 0 /
  "success") that hides a real stall, rather than surfacing it as `BLOCKED`.
- **Prior audit's outstanding items — checked live, mixed result (first
  actual movement across three audits):**
  - **P0-2 (autoloop OAuth expired on Hetzner): RESOLVED, but by removal
    rather than repair.** `autoloop.yml`'s `schedule:` trigger is now
    commented out entirely (only `workflow_dispatch` remains); `git log -p`
    shows this landed 2026-08-20 with an explicit, owner-approved commit
    message: *"NIGHTLY SCHEDULE DISABLED 2026-08-20 (approved by Ariel).
    Reason: this ran an ungoverned Claude Code session on Max OAuth every
    night ... largest uncontrolled consumer of the weekly subscription
    limit. Also SSH-dependent on Hetzner 87.99.129.125, whose sshd has been
    down since ~Aug 10 ... To restore: rebuild GHA-only and gate on
    quota_gate_check('engineering')."* Confirmed live: `gh run list
    --workflow=autoloop.yml` shows no runs after 2026-08-20 (the last one,
    that day, was `failure`) — the cron genuinely stopped firing rather than
    continuing to fail silently. This closes P0-2 as "addressed" though the
    stated restore condition (GHA-only rebuild + quota gate) is not yet
    done — noting this as resolved-by-disabling, not resolved-by-fixing.
  - **P1-1 (`skills-health-check.yml` blocked on stale `GH_PAT`): still
    open, re-confirmed live.** Most recent run (`32644473558`, 2026-08-23)
    still `conclusion: failure`, failing at the same step — `actions/
    checkout@v4` against `repository: breverdbidder/claude-skills-library`.
    All 5 most recent scheduled runs (08-02 through 08-23) show the same
    failure. Not re-diagnosed byte-for-byte (would duplicate 07-27/08-17
    without new information); confirmed only that it remains red, 3 weeks
    after first flagged.
  - **P2-1 (autoloop covers 1 of 16 dispatchable skills nightly): now
    moot, not fixed.** `DEFAULT_SKILL: zonewise` is still the only value
    ever set on the (now-disabled) schedule trigger — the rotation gap was
    never addressed, but P0-2's resolution means it no longer matters in
    practice (0 scheduled iterations of any skill, not just skewed toward
    one). Worth re-raising if/when the schedule is restored per the P0-2
    commit's stated plan.

---

## Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | `zonewise-gis-100pct-mission` stuck at `gap_count=14` for 7+ days; 14+ auto-opened GitHub issues, all still open, no stop condition ever trips | P1 | New this window — needs a direct look, out of scope for a skill-triggering audit to fix |
| F2 | `gemini-2.0-flash` deprecation bug recurred a 3rd time (`guard-diagnose`), despite 2 prior fix commits; 8 more files repo-wide still reference the deprecated model | P1 | Documented — mechanical grep-and-fix-all available, not attempted this session (out of scope) |
| F3 | `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` referenced by 3 workflows, never existed as secrets; only `CF_API_TOKEN`/`CF_ACCOUNT_ID` do | P2 | Documented — correctly blocked rather than routed around; small non-credential fix available |
| — | `skill-meta-updater`'s own feedback loop silently no-oped on 08-17 (issue #19240 open, uncommented, 7 days) — the mechanism meant to close last week's findings never ran | P1 | New finding — the audit-to-CC_META_PROMPT.md pipeline is itself broken |
| — | P0-2 from 07-27/08-17 audits (autoloop OAuth) | Resolved | Schedule disabled 2026-08-20, owner-approved, confirmed live — not repaired, but no longer silently failing |
| — | P1-1 from 07-27/08-17 audits (`skills-health-check.yml` GH_PAT) | Carry-over | Still open, re-confirmed live, unresolved 3 weeks |
| — | P2-1 from 07-27/08-17 audits (autoloop skill rotation) | Carry-over, now moot | Never fixed; irrelevant while P0-2's schedule stays disabled |

## Outstanding items for Ariel (cannot be closed by an agent session)

1. **F1** — decide a stop condition for `zonewise-gis-100pct-mission`: either
   fix whatever is holding `gap_count` at 14, or add a max-continuation-count
   / max-open-issues guard so the loop reports `BLOCKED` instead of quietly
   opening a new issue every 12 hours forever.
2. **The `skill-meta-updater` feedback loop is broken** — issue #19240 has
   sat open and uncommented for 7 days because its downstream
   `cc-runner-ghonly.yml` dispatch was skipped (runner busy) and nothing
   retries a skipped skill-meta-update. Without a fix, every future audit's
   findings will keep silently failing to reach `CC_META_PROMPT.md`.
3. Rotate/rescope `GH_PAT` for `claude-skills-library` access — unblocks
   `skills-health-check.yml` (P1-1, unresolved 3 weeks).
4. **F2** — a repo-wide grep-and-fix-all pass on `gemini-2.0-flash`
   references (9 files total, one already caused a live `BLOCKED` this
   window) would prevent a 4th recurrence; two prior one-file-at-a-time
   fixes have already not held.
5. **F3** — rename `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` references
   in `nexus-dns-fix.yml`, `deploy-winnerdata-ff.yml`,
   `fix-biddeed-via-zw.yml` to the existing `CF_API_TOKEN`/`CF_ACCOUNT_ID`
   secret names (or add aliased secrets) — small, mechanical, not a
   credential rotation.
6. Decide whether the Skills-catalog-vs-real-dispatch-traffic gap (49/49
   zero-invocation, third consecutive audit) reflects an intentional
   operating model or a genuine gap to close — restating the standing
   question from the 08-17 audit since nothing has changed on this axis.

## DoD check

- [x] `docs/skill-audits/skill-audit-2026-08-24.md` — this file, to be
  committed to `main`.
- [x] Per-skill invocation table present (§3, all 49 skills).
- [x] Outcome to be logged to `agent_ops_log` (`task='skill-audit'`,
  `status='VERIFIED'`) — see next tool call for the row contents.
