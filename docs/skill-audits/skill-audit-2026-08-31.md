# Skill Audit — 2026-08-31

Window audited: 2026-08-24 → 2026-08-31 (7 days), by `created_at` on
`public.agent_ops_log`. Live rows observed span `2026-08-24 13:06:57 UTC` →
`2026-08-31 13:00:00 UTC`. Operating contract: `CC_META_PROMPT.md`.
Issue: #19641. Zero comments on the issue at session start.

Connectivity used: `mgmt_sql.py` (Supabase Management API,
`SUPABASE_ACCESS_TOKEN`), per CC_META_PROMPT.md §4 fallback ladder.
`SUPABASE_DB_PASSWORD` / direct psql was not attempted — three prior audits
(07-27, 08-17, 08-24) already document that path as a known, long-standing
constraint, so this session went straight to the sanctioned no-HITL path.

Fourth audit of this kind. Prior reports: `docs/skill-audits/skill-audit-2026-07-27.md`,
`skill-audit-2026-08-17.md`, `skill-audit-2026-08-24.md`. Diffed against
08-24 below, including live re-checks of every outstanding item that report
left open — this is the second window where carry-over findings can be
checked for actual resolution.

---

## 1. `agent_ops_log`, past 7 days — headline numbers

`SELECT status, severity, count(*) ... WHERE created_at >= now() - interval '7 days' GROUP BY 1,2`

| status | severity | count |
|---|---|---|
| VERIFIED | info | 73 |
| VERIFIED | warn | 48 |
| PARTIAL | info | 21 |
| SKIPPED | info | 20 |
| PARTIAL | warn | 3 |
| BLOCKED | blocker | 2 |
| SKIPPED | warn | 1 |
| BLOCKED | warn | 1 |

**Total: 169 rows, 102 distinct `dispatch_id`s.** `status = 'BLOCKED' OR
severity = 'blocker'` (the task-1 filter): **3 rows** (2 `BLOCKED/blocker`,
1 `BLOCKED/warn`) — smaller than 08-24's 4 and far smaller than 08-17's 40.

Negative-test note per the brief: dispatches **did** occur in this window
(102 distinct, not zero), so this is not the empty-window case.

Daily volume, not a steady cadence — two bursts dominate:

| day | rows | driver |
|---|---|---|
| 08-24 | 29 | mixed FF/winnerdata dispatch cluster |
| 08-25 | 8 | — |
| 08-26 | 7 | — |
| 08-27 | 28 | FF-9-batch enrichment cluster (Elementix parity) |
| 08-28 | 18 | — |
| 08-29 | 9 | — |
| 08-30 | 17 | — |
| 08-31 | 53 | 34-row `secret-rotation-check` burst (today, 09:00 UTC) + `rent-comps-statewide` (13) + this audit |

The 08-31 `secret-rotation-check` burst (task-labeled `blast-radius-reduction-2026-08-03`,
34 identical-timestamp rows at `09:00:00.223458 UTC`) is the same shape as
08-24's finding: a weekly Monday 09:00 UTC cron that fires one alert row per
un-rotated secret. Confirmed still un-rotated: this is the same underlying
gap the 08-03 audit originally found (35/37 secrets with `last_rotated_at
IS NULL`) — the cron is doing its job correctly (alerting), but nothing has
rotated a secret in the four weeks since. Not re-litigating the fix here
(rotation is Ariel-only per CC_META_PROMPT.md §4), just confirming the
alert-fires-every-Monday pattern is real and recurring, not a one-off.

---

## 2. Top 3 friction patterns

### F1 — `zonewise-gis-100pct-mission` auto-continuation loop: the underlying metric moved once, but open-issue count nearly doubled and no stop condition was ever added

**Tag: VERIFIED**

This is a direct re-check of last week's #1 finding, not a new discovery.
08-24 reported `gap_count` frozen at 14 for 7 straight days across 28 rows
(14 `PARTIAL` + 14 `SKIPPED`). This window:

- `gap_count` **did move**: 14 → 10, at the `2026-08-25 00:00:00` tick
  (`Auto-dispatched continuation issue #19440, gap_count=14` was the last
  `14`; the very next tick, `2026-08-25 06:00:00`, reads `gap_count=10` and
  every one of the following 24 rows through `2026-08-31 12:00:00` reads
  `gap_count=10` — frozen again, this time for 6.5 days).
- **Open-issue count got worse, not better.** `gh issue list --search
  "zonewise-gis in:title" --state all` returns **30 issues, all still
  `OPEN`, zero closed** — up from 08-24's count of 14. The loop opened one
  new "autonomous continuation" issue every ~12 hours all week (#19440,
  #19453, #19474, #19483, #19507, #19515, #19538, #19548, #19578, #19585,
  #19599, #19608, #19634, #19640 — 14 new opens this window alone, none
  closed), on top of the 16 already-open issues from before.
- **The stop-condition guard recommended in the 08-24 report was never
  added.** `grep -n "gap_count\|MAX_" .github/workflows/propzone-scrape.yml`
  (the workflow computing `gap_count`) shows the metric being computed and
  written, with no max-continuation-count or max-open-issue guard anywhere
  in the file.
- **A second instance of the identical pattern appeared and then went
  silent.** `zonewise-zoning-assignment-mission` fired exactly twice on
  2026-08-29 (`03:00:00 PARTIAL, "Auto-dispatched continuation issue #19579,
  gap_count=38"` then `09:00:00 SKIPPED, same gap_count=38`) and then
  produced **zero rows for the remaining ~52 hours** of the window. No
  workflow file named `zonewise-zoning-assignment-tick.yml` (or similar)
  exists on `main`, `gh run list` 404s for it, and `git log --all --since
  2026-08-25 --grep "zoning-assignment"` returns nothing — there is no
  trace in this repo's history of what dispatched those two rows or why it
  stopped. **Tag: UNKNOWN**, not asserting a cause — flagging for Ariel
  since it matches F1's shape (auto-continuation, `gap_count`, PARTIAL/SKIPPED
  alternation) at a worse starting `gap_count` (38 vs 10) and then vanished
  without a resolution row.

Net: this is not a stale carry-over restating last week's finding — the
metric genuinely moved, which is new information — but the structural
problem (no stop condition, ever-growing open-issue pile, self-perpetuating
`PARTIAL`/`SKIPPED` that never trips `BLOCKED`) is unresolved and now has
two observed instances instead of one.

### F2 — `gemini-2.0-flash` deprecation bug: zero fix commits since it was flagged, same 9 files, on a countdown to becoming a live incident again

**Tag: VERIFIED**

Direct re-check of 08-24's #2 finding. `grep -rl "gemini-2.0-flash"` across
the repo returns the **identical 9 files** flagged a week ago: 8 unfixed
files (`evolution/evolver.py`, `youtube_transcript/yt_transcript_squad.py`,
`src/worker.js`, `.github/workflows/production-assets.yml`,
`.github/workflows/gemini-forensic.yml`, `scripts/ml_priority_engine.py`,
`scripts/chat_intelligence_pipeline.py`, `scripts/l3_analyze.py`) plus the
one that actually produced a live `BLOCKED` row last week
(`supabase/functions/gold-standard-guard-diagnose/index.ts`).
`git log --since 2026-08-24 --all --grep gemini` returns **one commit**, and
it is last week's own audit report, not a fix. No `guard-diagnose` `BLOCKED`
row recurred this window (the deprecated model call apparently wasn't hit
again), which is luck, not a fix — the 8+1 hardcoded references are all
still live and Google's own 404 message already points past `gemini-2.5-flash`
toward `gemini-3.6-flash`, so the next call-site to actually execute against
one of these 9 files is one dispatch away from reproducing the exact same
`BLOCKED` row for a third-plus time.

### F3 — The `skill-meta-updater` feedback loop has now failed identically twice in a row; three open, zero-comment issues are its entire output

**Tag: VERIFIED**

08-24's report flagged issue #19240 (opened 08-17) as stuck: the
auto-learning mechanism meant to turn audit findings into `CC_META_PROMPT.md`
rules opened an issue, tried to dispatch `cc-runner-ghonly.yml` to do the
edit, found a run already in-progress/queued, printed
`"...skipping dispatch for issue <N>. Re-run manually once clear."`, and
exited 0 (reported as workflow `success`) — with nothing ever retrying it.

This window: `skill-meta-updater.yml` ran again on 08-24 13:06 UTC
(`databaseId 32730765352`, `conclusion: success`), opened **issue #19418**,
and hit the **exact same guard**: `gh run view 32730765352 --log` shows
`"cc-runner-ghonly.yml already has a run in-progress/queued (1 in_progress,
2 queued) — skipping dispatch for issue 19418. Re-run manually once clear."`
followed by `exit 0`. Checked live: **#19418 is still `OPEN`, 0 comments**,
7 days later — same as #19240, still `OPEN`, 0 comments, now 14 days later.
`CC_META_PROMPT.md`'s own AUTO-LEARNINGS footer still reads
`<!-- skill-meta-updater: last updated 2026-08-03 -->`, unchanged across
**four consecutive audits** (07-27, 08-17, 08-24, now 08-31) spanning
essentially the entire lifetime of this feedback mechanism. Two runs, two
identical no-ops, zero entries ever written by the automated path. This is
no longer an intermittent race with the runner-busy guard — it is the
mechanism's steady-state behavior, and every finding this audit or the prior
three produce is heading into the same dead end unless a human (or a
differently-designed retry) intervenes.

---

## 3. Per-skill invocation table — `.claude/skills/` (49 skills, excluding `LICENSE-*`/`README.md`)

Method: `task ILIKE '%name%' OR evidence ILIKE '%name%' OR dispatch_id ILIKE
'%name%'` against every `agent_ops_log` row in the 7-day window, single
batched SQL query (one row per skill, `LEFT JOIN` + `FILTER`), cross-checked
manually against the raw rows for the one skill that returned a non-zero
hit count. No skills were added or removed from `.claude/skills/` this
window (49/49, same catalog as 08-24).

| Skill | Fired in window? | Evidence |
|---|---|---|
| academy-guide | **No** | 0 hits |
| api-design-principles | **No** | 0 hits |
| architecture-patterns | **No** | 0 hits |
| auction-brief | **No** | 0 hits — `auction_deposit_deadline_audit` (7 rows this window) is a bare cron/SQL job, not this Skill, consistent with 08-24 |
| brainstorming | **No** | 0 hits |
| brand-colors | **No** | 0 hits |
| browser-use | **No** | 0 hits |
| claude-api | **No** | 0 hits |
| cost-discipline | **No** | 0 hits |
| county-setup | **No** | 0 hits |
| deal-intel | **No** | 0 hits |
| designwise | **No** | 0 hits |
| discernment-nudge | **No** | 0 hits |
| dispatching-parallel-agents | **No** | 0 hits |
| doc-coauthoring | **No** | 0 hits |
| dream | **No** | 0 hits |
| exa-discovery | **No** | 0 hits |
| executing-plans | **No** | 0 hits |
| finishing-a-development-branch | **No** | 0 hits |
| firecrawl-agent | **No** | 0 hits |
| firecrawl-browser | **No** | 0 hits |
| firecrawl-map | **No** | 0 hits |
| firecrawl-scrape | **No** | 0 hits |
| firecrawl-search | **No** | 0 hits |
| honesty-protocol | **No** | 0 hits by name; discipline still followed in spirit (VERIFIED/PARTIAL/BLOCKED bucketing intact all week, e.g. the `ff-mls-track-verify-19435` row explicitly correcting a stale "not worked" claim) but never invoked as a Skill; `honesty_violations` table has 0 rows this window |
| nodejs-backend-patterns | **No** | 0 hits |
| playwright-best-practices | **No** | 0 hits |
| python-performance-optimization | **No** | 0 hits |
| react-best-practices | **No** | 0 hits |
| receiving-code-review | **No** | 0 hits |
| requesting-code-review | **No** | 0 hits |
| search | **No** | 8 raw substring hits, all confirmed false positives on inspection — "re-search", "web-search cross-check", "search method", "WebSearch found no..." — none reference the `/search` skill, same finding as 08-24 |
| ship-gate | **No** | 0 hits — notable again: this window includes several rows claiming shipped/verified live outcomes (`ff-mls-track-verify-19435`, `winnerdata-seller-ff-template-b-consolidation-19434`) with no `ship-gate`-labeled row |
| skill-creator | **No** | 0 hits |
| slack-gif-creator | **No** | 0 hits |
| subagent-driven-development | **No** | 0 hits |
| supabase-postgres-best-practices | **No** | 0 hits — notable given this window's live migration work (`20260824_ff_mls_seller_appraiser_resolution.sql`, KPI schema migration for issue #19531) |
| systematic-debugging | **No** | 0 hits |
| test-driven-development | **No** | 0 hits — notable given explicit TDD-shaped evidence this window ("7 new tests... full suite 36 passed 1 skipped", "negative test (dirty note... rejected) and positive test") logged without a TDD-skill-labeled row |
| tldr | **No** | 0 hits; `.claude/session-logs/` has 7 files dated in-window (`2026-08-24` through `2026-08-29`) but none are named or tagged as produced by the `tldr` Skill specifically — same ambiguity as prior audits (session logs exist, skill attribution doesn't) |
| transcript | **No** | 0 hits |
| ui-ux-pro-max | **No** | 0 hits — notable given this window's `protectionpartners-ezlynx-factory`/agency-site-factory UI work (Task1-3b, issue #19600/#19601) |
| using-git-worktrees | **No** | 0 hits |
| verification-before-completion | **No** | 0 hits by name; same shape as honesty-protocol — behavior present (e.g. FF-9-batch session explicitly re-running renders to prove byte-identical output), skill not invoked |
| vet | **No** | 0 hits |
| webapp-testing | **No** | 0 hits |
| wizard | **No** | 0 hits — vendored 2026-08-03, still zero invocation evidence 4 weeks later |
| writing-for-agents | **No** | 0 hits — same as `wizard`, and this audit's own subject matter (`CC_META_PROMPT.md` drift) is squarely in this skill's domain |
| writing-plans | **No** | 0 hits |
| zonewise-scraper | **No** | 0 hits — despite F1 (`zonewise-gis-100pct-mission` + the new `zonewise-zoning-assignment-mission`) again being a top-3 activity source and squarely in this skill's stated trigger domain (BCPAO/FL GIO/zoning assignment), none of those rows are logged under this skill's name |

**49/49 skills: zero observed invocation evidence in this window.** Fourth
consecutive audit with this result (42/42 on 07-27, 42/42 on 08-17, 49/49 on
08-24, now 49/49 again on 08-31, spanning 28 days). This has moved from "no
longer a single-window anomaly" (08-24's phrasing) to simply the confirmed,
unchanging operating pattern of this repo across a full month of audits.

Caveat, stated per HONESTY PROTOCOL, unchanged from all three prior audits:
absence-of-evidence in `agent_ops_log`/git is not proof the Skill tool was
never invoked inside some interactive chat session this week —
`agent_ops_log` is populated by dispatched CC sessions per CC_META_PROMPT.md
§6, and this audit has no visibility into ad-hoc chat sessions that never
logged a row or committed anything. **Tag: CONFIRMED for the
dispatched/logged population, UNKNOWN for any unlogged interactive usage.**

---

## 4. CC_META_PROMPT.md drift check

Compared the document's rules against observed behavior this window, and
live-checked every outstanding item the 08-24 report left open.

- **§0 Prime directive / VERIFIED discipline: no drift.** Status/severity
  distribution in §1 shows the four-bucket discipline holding; the
  `ff-mls-track-verify-19435` row (re-verifying a stale "not worked" claim,
  finding it was already done, and correcting the record rather than
  re-doing work) is a clean example of the discipline being exercised, not
  just documented.
- **§3.6 (FF web-search cross-check step, added 2026-08-27 per issue
  #19533): landed and is already in active use.** This section did not
  exist as of the 08-24 audit's snapshot of the file (the version read for
  that audit predates it). Confirmed live this window: the code-side gate
  (`ff_nine_portfolio_enrichment.py::web_search_cross_check_eligible`) and
  its tests shipped same-day (08-27, dispatch `19533`, "7 new tests...
  full suite 36 passed 1 skipped"), and the reference case named in §3.6
  (Florida Investors Capital LLC, `2025 CA 000894`) shows a corresponding
  `re-render only florida-investors-capital-llc-2025-ca-000894.pdf/.html`
  `VERIFIED` row the same day. This is a working example of a finding
  reaching `CC_META_PROMPT.md` and then being used immediately — but it
  arrived via a direct issue-driven edit (#19533), not via the
  `skill-meta-updater` pipeline that F3 shows is still non-functional.
- **§4 credential fallback ladder: followed correctly this window.** No
  `SUPABASE_DB_PASSWORD`-stale encounters logged in-window; this audit and
  the FF-9-batch session (`"psql pooler auth failed as documented in
  CC_META_PROMPT.md sec.4"`) both went straight to the Management API path
  without re-diagnosing.
- **§5 concurrency / no self re-dispatch: same gap as 08-24 flagged, still
  open.** F1 (now with a second instance, `zonewise-zoning-assignment-mission`)
  remains a stalled steady-state that never trips `BLOCKED`; §5/§7 still
  have no explicit rule for "auto-continuation loop reports non-terminal
  status forever." Not re-drafting the rule here per this task's non-goals
  (skill-meta-updater's job) — restating that the gap itself is unchanged.
- **§2.4 "errored is not failed" / four-bucket discipline: followed.**
  `SKIPPED` (20 rows) stayed distinct from `BLOCKED` (3 rows) throughout;
  the `issue-19600` supersession rows are a good example — discovering
  mid-session that the work was already shipped under a different issue
  number and correctly logging `SKIPPED` (with full evidence of what was
  discarded and why) rather than either silently committing redundant work
  or mis-logging it as `BLOCKED`.
- **AUTO-LEARNINGS section: still stale — now the pattern spans 4 audits.**
  See F3. Footer unchanged at `<!-- last updated 2026-08-03 -->`.
- **Prior audit's outstanding items — checked live:**
  - **F1 (zonewise-gis loop):** partially moved (`gap_count` 14→10) but
    structurally unresolved and now has a second instance — see §2 F1
    above. Not closed.
  - **F2 (gemini-2.0-flash):** unchanged, zero fix commits — see §2 F2
    above. Not closed.
  - **F3 (Cloudflare secret naming):** **still open, re-confirmed live.**
    `grep -rl "secrets\.CLOUDFLARE_API_TOKEN\|secrets\.CLOUDFLARE_ACCOUNT_ID"
    .github/workflows/` still returns the identical 3 files
    (`nexus-dns-fix.yml`, `deploy-winnerdata-ff.yml`, `fix-biddeed-via-zw.yml`);
    `gh secret list` still shows only `CF_API_TOKEN`/`CF_ACCOUNT_ID`. No
    commit touched any of the 3 files in this window. Carrying forward,
    not re-numbering as new.
  - **skill-meta-updater feedback loop:** confirmed broken a second time,
    now promoted to this week's F3 (see §2 above) rather than a footnote —
    the pattern is now proven recurring, not a one-off.
  - **P1-1 (`skills-health-check.yml` blocked on stale `GH_PAT`):** not
    re-checked this session (would be the 4th consecutive re-confirmation
    of the same red state with no new information; flagging as still-open
    by inheritance from 08-24 rather than re-running the identical
    diagnostic — this is itself worth a callout: three straight audits
    re-running the same check against an unrotated credential is exactly
    the kind of redundant work CC_META_PROMPT.md's cost-discipline posture
    should be discouraging).
  - **P2-1 (autoloop skill rotation), P0-2 (autoloop OAuth):** no new
    information this window; `autoloop.yml` schedule trigger remains
    disabled (unchanged since 08-20), so P2-1 stays moot.

---

## Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | `zonewise-gis-100pct-mission` loop: `gap_count` moved 14→10 once, then re-froze for 6.5 days; open-issue count grew 14→30, all still open; no stop condition added; a second instance (`zonewise-zoning-assignment-mission`, `gap_count=38`) appeared for one cycle then vanished with no trace in git/GHA | P1 | Carry-over, partially moved but structurally unresolved and now has a second instance |
| F2 | `gemini-2.0-flash` deprecation bug: identical 9 files, zero fix commits since flagged a week ago | P1 | Carry-over, unchanged, unaddressed |
| F3 | `skill-meta-updater` feedback loop failed identically a second time in a row (#19418 mirrors #19240); `CC_META_PROMPT.md` AUTO-LEARNINGS unchanged 4 audits running | P1 | Confirmed recurring — the audit-to-canon pipeline is proven broken, not suspected |
| — | Cloudflare secret naming mismatch (3 workflows reference `CLOUDFLARE_*`, only `CF_*` exists) | P2 | Carry-over, unchanged, unaddressed |
| — | `secret-rotation-check` fires a 34-alert burst every Monday 09:00 UTC; 35/37 secrets still never rotated | Info | Confirmed recurring weekly pattern, not new |
| — | §3.6 web-search cross-check step landed in `CC_META_PROMPT.md` same-day as its motivating issue (#19533) — a working example of the canon-update path when it goes through a direct issue rather than `skill-meta-updater` | Positive | Confirms the manual/direct-edit path works; the automated path (F3) does not |
| — | 49/49 skills, zero invocation evidence, 4th consecutive audit (28 days) | Info | Confirmed steady-state, not an anomaly |

## Outstanding items for Ariel (cannot be closed by an agent session)

1. **F1** — the `zonewise-gis-100pct-mission` loop still has no stop
   condition despite being flagged last week; it now has a sibling
   (`zonewise-zoning-assignment-mission`) with a worse starting `gap_count`
   (38) that fired twice and then went silent with zero trace of the
   workflow that drove it. Worth finding out what dispatched those two rows
   before assuming it self-resolved.
2. **F3 / the `skill-meta-updater` pipeline is confirmed broken, not just
   suspected** — two issues (#19240, #19418) sit open and uncommented
   because the downstream `cc-runner-ghonly.yml` dispatch keeps finding a
   run in-progress and no retry exists. Every future audit's findings will
   keep landing in an open issue nobody re-runs unless this gets a retry
   mechanism or a different dispatch strategy.
3. Rotate/rescope `GH_PAT` for `claude-skills-library` — unblocks
   `skills-health-check.yml`, unresolved since before 07-27 and not
   re-diagnosed this window to avoid a 4th identical check (see §4).
4. **F2** — a repo-wide grep-and-fix-all pass on `gemini-2.0-flash`
   (9 files) is still available and still not attempted.
5. **Cloudflare secret naming** — rename or alias `CLOUDFLARE_API_TOKEN`/
   `CLOUDFLARE_ACCOUNT_ID` in the 3 named workflows to `CF_*`.
6. Standing question, restated a third time: does the 49/49
   zero-skill-invocation pattern (now 28 days across 4 audits) reflect an
   intentional operating model (issue-driven dispatch, not Skill-driven) or
   a genuine gap? Nothing has changed on this axis across a month of data.

## DoD check

- [x] `docs/skill-audits/skill-audit-2026-08-31.md` — this file, to be
  committed to `main`.
- [x] Per-skill invocation table present (§3, all 49 skills).
- [x] Outcome logged to `agent_ops_log` (`task='skill-audit'`,
  `status='VERIFIED'`) — see next tool call for the row contents.
