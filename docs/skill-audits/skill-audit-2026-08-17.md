# Skill Audit — 2026-08-17

Window audited: 2026-08-10 → 2026-08-17 (7 days), by `created_at` on
`public.agent_ops_log`. Live rows observed span `2026-08-10 22:35:31 UTC` →
`2026-08-17 18:00:00 UTC`. Operating contract: `CC_META_PROMPT.md`.

Connectivity used: `mgmt_sql.py` (Supabase Management API,
`SUPABASE_ACCESS_TOKEN`), per CC_META_PROMPT.md §4 fallback ladder — direct
psql/pooler was not attempted first since the prior two audits (2026-07-27,
and this window's own findings below) already show `SUPABASE_DB_PASSWORD`
stale on that path; going straight to the sanctioned no-HITL path avoided
burning a retry on a known-bad credential.

This is the second audit of this kind. Prior report:
`docs/skill-audits/skill-audit-2026-07-27.md` (14-day window, closed
2026-07-27). Diffed against it below where relevant.

---

## 1. `agent_ops_log`, past 7 days — headline numbers

`SELECT status, severity, count(*) ... WHERE created_at >= now() - interval '7 days' GROUP BY 1,2`

| status | severity | count |
|---|---|---|
| VERIFIED | info | 163 |
| VERIFIED | warn | 48 |
| PARTIAL | info | 28 |
| PARTIAL | warn | 20 |
| BLOCKED | blocker | 13 |
| SKIPPED | info | 13 |
| BLOCKED | warn | 10 |
| BLOCKED | info | 9 |
| VERIFIED | blocker | 6 |
| PARTIAL | blocker | 2 |

**Total: 312 rows, 159 distinct `dispatch_id`s.** `status = 'BLOCKED' OR
severity = 'blocker'` (the task-1 filter): **40 rows** (32 `BLOCKED` + 6
`VERIFIED/blocker` + 2 `PARTIAL/blocker`; `VERIFIED/blocker` rows are root-cause
writeups logged after a blocker was found and fixed, e.g. the SRID repair and
the Telegram token investigation below — real finding, not a contradiction).

Volume is heavily back-loaded: 2026-08-10 through 08-13 totaled 18 rows;
08-14 through 08-17 totaled 294 rows (94% of the window). This tracks a
concentrated burst of `gold-standard`/`zoning-shard-*` and `zonewise-web`
dispatch activity in the last 3–4 days, not a steady daily cadence — worth
noting for anyone reading day-over-day trend into this table.

Negative-test note per the brief: dispatches **did** occur in this window
(159 distinct, not zero), so this is not the empty-window case — the
sub-findings below are grounded in real rows, not invented.

---

## 2. Top 3 friction patterns

### F1 — `SUPABASE_DB_PASSWORD` is still stale, a month after being documented, and still causes real `BLOCKED` outcomes

**Tag: VERIFIED**

CC_META_PROMPT.md §4 documents this credential as "found stale on all three
DB endpoints on 2026-07-19." It is not fixed. In this window:

- `issue-19161` / task `gist-index-only`, **BLOCKED, blocker**, 2026-08-16:
  "GiST index NOT built... Root cause: SUPABASE_DB_PASSWORD is a stale/wrong
  credential, confirmed FATAL pa[ssword auth failed]..." — a single-index
  `CREATE INDEX CONCURRENTLY` task, blocked outright by the credential rather
  than falling back to the Management API path (which cannot run
  `CONCURRENTLY` inside its query wrapper the way a direct connection can —
  a genuine capability gap in the sanctioned fallback, not just a skipped
  step).
- The same string appears in 5 distinct dispatches this window
  (`exa_tam_expansion_20260817`, `issue-19161`, `pp-ci-engine-gemini-swap-20260814`,
  `zonewise-urgent-issue-19067`, `zw-secret-verify-20260814`) — most routed
  around it successfully via the Management API per the documented fallback
  ladder, but `issue-19161` shows the ladder has at least one real gap
  (long-running/`CONCURRENTLY` DDL).

This is a process/credential friction pattern, not a one-off: it has now
surfaced in two consecutive audit windows a month apart with no rotation.

### F2 — The Platform Skill catalog (`.claude/skills/`) had zero measurable footprint in 7 days of real dispatch activity

**Tag: VERIFIED.** See full per-skill table in §3. Every one of the 312 rows
in this window belongs to an ad-hoc, issue-numbered or `gold-standard-shardN`
task label (`zoning-shard-5`, `issue-19161`, `zonewise_gis_srid_corruption_fix`,
etc.) — none map to any of the 42 documented `SKILL.md` files. Grepping
`task`/`evidence`/`dispatch_id` for every skill's directory name returns 0
hits for all 42 (a 14-hit match on `search` is a substring false positive —
"research", "search snippets", "search_sites" — confirmed by inspecting all
14 rows, none reference the `/search` skill). Git commit history for the
window shows the same shape: 245 commits since 2026-08-10, and grepping
those for skill names returns only 6 hits, all from a single vendoring
commit set (`writing-for-agents`, `wizard` — adding the skill files, not
invoking them). This is the same shape as P3-3 in the 2026-07-27 audit,
just measured from the opposite direction this time (there, the
*assistant-facing* Skill list had ~30 entries with no matching `SKILL.md`;
here, the *repo's* `SKILL.md` catalog has 42 entries with no matching
dispatch activity). Together they describe one underlying gap: real GHA
dispatch work and the documented Skill system are running on two
disconnected tracks.

### F3 — The same spatial/SRID corruption class recurs even after a large repair

**Tag: VERIFIED**

`19155` / `zonewise_gis_srid_corruption_fix`, **VERIFIED, blocker**,
2026-08-16: `ST_SetSRID(...,3086)` bug on FDOR geometry writes (FDOR's
`f=geojson` output is always EPSG:4326, not 3086) corrupted 182,726 rows
across 11 counties (Pasco, Columbia, Washington, DeSoto, Dixie, Jefferson,
Calhoun, Lafayette, Walton, Sarasota, Jackson); fixed via
`migrations/20260816_repair_fdor_srid_corruption.sql`. Hours later the same
day, `issue-19126` / `zoning-shard-5`, **BLOCKED, blocker**: "desoto co_no=24:
... 3213 polys ingested ... but zw_parcels.geom/centroid for co_no=24 is
corrupted upstream (same Gulf-of-Mexico bug) — spatial join impossible, 0
assignments written." DeSoto is one of the 11 counties named in the same
day's repair migration, which means either the repair's coverage claim needs
re-checking against this specific county/table, or `zw_parcels` (as opposed
to whatever table the repair targeted) is a second, unrepaired source of the
same corruption class. Flagging as **UNKNOWN which** — I did not re-run the
repair migration or re-query `zw_parcels.geom` for co_no=24 live in this
session (out of scope for a skill-triggering audit vs. a data-quality
dispatch), but the two same-day log lines are close enough in time and
description that this deserves a direct look, not just a note.

### Called out separately (not counted in the "top 3" — single incident, not a recurring pattern, but severity=blocker and worth surfacing on its own)

`telegram_optin_channel`, **BLOCKED, blocker**, 2026-08-17 02:55: the
`TELEGRAM_BOT_TOKEN` present in-session did **not** belong to a BidDeed-branded
bot — `getMe` returned `first_name='BEST CASINO MINI-APP @Xstakerobot'`,
`username='AgentRemote_bot'`, with an **active third-party webhook** already
registered (`https://ssh.inkognit.org:8443/...`). Correctly not used — the
dispatch stopped rather than sending through an unknown third party's
webhook. Follow-up dispatch `telegram_token_security_investigation`,
**VERIFIED, blocker**, 2026-08-17 03:20: root-caused to two genuinely
distinct GH secret pairs (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` created
2026-04-06, vs. `BIDDEED_BOT_TOKEN`/`BIDDEED_BOT_CHAT_ID` created
2026-03-20) that `deploy-agentremote.yml` (created 2026-03-18) had been
pointed at incorrectly. This is a credential-hygiene finding, correctly
self-contained (no message sent to the wrong bot), but Ariel should confirm
the `TELEGRAM_BOT_TOKEN` secret's actual provenance — a token controlled by
an unrelated casino mini-app sitting in this repo's secrets at all is worth
independently confirming isn't itself compromised infrastructure rather than
just a copy-paste mislabel.

---

## 3. Per-skill invocation table — `.claude/skills/` (42 skills, excluding `LICENSE-*`/`README.md`)

Method: `task ILIKE '%name%' OR evidence ILIKE '%name%' OR dispatch_id ILIKE
'%name%'` against every `agent_ops_log` row in the 7-day window, per skill
directory name, cross-checked against `git log --since="7 days ago"` commit
subjects touching `.claude/skills/`.

| Skill | Fired in window? | Evidence |
|---|---|---|
| api-design-principles | **No** | 0 `agent_ops_log` hits, 0 commit hits |
| architecture-patterns | **No** | 0 hits |
| auction-brief | **No** | 0 hits — notable given CLAUDE.md lists this as a daily-run command |
| brainstorming | **No** | 0 hits |
| brand-colors | **No** | 0 hits |
| browser-use | **No** | 0 hits |
| cost-discipline | **No** | 0 hits |
| county-setup | **No** | 0 hits |
| deal-intel | **No** | 0 hits |
| designwise | **No** | 0 hits |
| dispatching-parallel-agents | **No** | 0 hits |
| dream | **No** | 0 hits |
| exa-discovery | **No** | 0 hits — but note `exa_tam_expansion_20260817` (F1) does real Exa-style lead-discovery work under a different task label, so the *capability* may be exercised without going through this Skill |
| executing-plans | **No** | 0 hits |
| finishing-a-development-branch | **No** | 0 hits |
| firecrawl-agent | **No** | 0 hits |
| firecrawl-browser | **No** | 0 hits |
| firecrawl-map | **No** | 0 hits |
| firecrawl-scrape | **No** | 0 hits |
| firecrawl-search | **No** | 0 hits |
| honesty-protocol | **No** | 0 hits by name — but its *rules* are clearly being followed in spirit throughout the window (VERIFIED/BLOCKED/PARTIAL discipline, negative-test callouts, refuted-claim commits like `03337586 catch+revert fabricated fix`); the skill itself was never invoked as a Skill, the discipline is baked into CC_META_PROMPT.md instead |
| nodejs-backend-patterns | **No** | 0 hits |
| playwright-best-practices | **No** | 0 hits |
| python-performance-optimization | **No** | 0 hits |
| react-best-practices | **No** | 0 hits |
| receiving-code-review | **No** | 0 hits |
| requesting-code-review | **No** | 0 hits |
| search | **No** | 14 raw text hits, all confirmed substring false positives ("research", "search snippets", "search_sites", "fl-parcels-search-index") on manual inspection of all 14 rows — none reference the `/search` skill |
| ship-gate | **No** | 0 hits — notable; several rows this window claim `VERIFIED`/PR-merged outcomes (e.g. `gha-31916708402` zonewise Stripe e2e) without a `ship-gate`-labeled row |
| skill-creator | **No** | 0 hits |
| subagent-driven-development | **No** | 0 hits |
| supabase-postgres-best-practices | **No** | 0 hits — notable given the volume of raw SQL/migration work in this exact window (SRID repair, GiST index, RLS fixes) |
| systematic-debugging | **No** | 0 hits |
| test-driven-development | **No** | 0 hits |
| tldr | **No** | 0 hits — no `.claude/session-logs/*.yml` files dated in-window either (2 files touch 2026-08-1x: `2026-08-12-charlotte-CD-fix.yml`, `2026-08-14-gold-standard-shard2-run11435-5f3a88a5.yml`; both predate 08-15, where 89% of this window's volume actually is) |
| transcript | **No** | 0 hits |
| ui-ux-pro-max | **No** | 0 hits |
| using-git-worktrees | **No** | 0 hits — see F2; `.claude/worktrees/` orphan cleanup (`c752d818`) happened this window without this skill |
| verification-before-completion | **No** | 0 hits by name, same as honesty-protocol — the *behavior* (evidence-before-claims) is broadly present in commit messages, the *skill* was not invoked |
| vet | **No** | 0 hits |
| wizard | **No** (vendored, not used) | Added this window (`0fa09906`, `3f7bda28`) via a skills-vendoring commit; zero evidence of it being invoked for actual provisioning/setup work in-window |
| writing-for-agents | **No** (vendored, not used) | Same as `wizard` — added `31d57785`/`6a9328aa`, not invoked |
| writing-plans | **No** | 0 hits |
| zonewise-scraper | **No** | 0 hits — despite `zonewise_gis_srid_corruption_fix`, multiple `zoning-shard-*` dispatches, and BCPAO/FL GIO work all happening in-window, none logged under this skill's name |

**42/42 skills: zero observed invocation evidence in this window.** This is
the single largest finding of this audit (F2 above) — restated per-skill
here per the task-3 instruction that a skill with zero observed invocations
is itself a finding, not a clean bill of health.

One caveat, stated per HONESTY PROTOCOL: absence-of-evidence in
`agent_ops_log`/git is not proof that the Skill tool was never invoked
inside some interactive chat session this week — `agent_ops_log` is
populated by dispatched CC sessions per CC_META_PROMPT.md §6, and this audit
has no visibility into ad-hoc chat sessions that never logged a row or
committed anything. **Tag: CONFIRMED for the dispatched/logged population,
UNKNOWN for any unlogged interactive usage.**

---

## 4. CC_META_PROMPT.md drift check

Compared the document's rules against observed behavior this window and
against the outstanding items from the 2026-07-27 audit.

- **§0 Prime directive / VERIFIED discipline: no drift.** The
  status/severity distribution in §1 (VERIFIED/PARTIAL/BLOCKED/SKIPPED, never
  a bare "done") and multiple explicit refutation commits (`03337586` "catch+
  revert fabricated fix", `433fb7fa` "no-fix, evidence-backed FAIL",
  `0c0901e8` "claim did not survive adversarial verify") show the rule being
  actively exercised, not just present in the doc.
- **§4 credential fallback ladder: partial drift — a real gap, not
  documentation drift.** The ladder (pooler → direct host → Management API)
  is followed correctly in 4 of 5 `SUPABASE_DB_PASSWORD`-stale encounters
  this window, but `issue-19161` (F1) shows the Management API path cannot
  serve `CREATE INDEX CONCURRENTLY` the way a direct connection can. The doc
  doesn't currently say what to do when the *sanctioned fallback itself* is
  insufficient for a specific DDL shape — worth an addition, flagged here
  for `skill-meta-updater`, not made directly per this task's non-goals.
- **§2.4 "errored is not failed" / four-bucket discipline: followed.** The
  `agent_ops_log` `status` check constraint only allows
  `VERIFIED|BLOCKED|PARTIAL|SKIPPED` — `SKIPPED` (13 rows this window) is
  the errored/not-applicable bucket, kept distinct from `BLOCKED`.
- **§5 concurrency / no self re-dispatch: followed, with a good example.**
  `zonewise-urgent-issue-19067` explicitly logs: "Re-dispatch of issue
  #19067 (~4 min after prior run). Verified prior session's work is still
  valid instead of duplicating it." — this is the *correct* handling of a
  near-duplicate dispatch (check first, don't blindly redo), not a §5
  violation.
- **Prior audit's outstanding items — still open, re-confirmed live this
  session:**
  - P0-2 (autoloop OAuth expired on Hetzner): masking fix from 2026-07-27
    still holds — `gh run list --workflow=autoloop.yml` shows real
    `conclusion: failure` on all 7 scheduled runs 2026-08-08 through
    2026-08-16 (previously these silently reported success). Root cause is
    **not fixed**: run `31933266445` (2026-08-16) log still contains
    `Failed to authenticate. API Error: 401 ... "OAuth access token has
    expired."` verbatim — same string as the 07-27 finding, unresolved a
    further 3 weeks. Ariel-only per CC_META_PROMPT.md §4.
  - P1-1 (`skills-health-check.yml` blocked on stale `GH_PAT`): still
    failing — `gh run list` shows `conclusion: failure` on all 5 most recent
    scheduled runs including 2026-08-16. Not re-diagnosed line-by-line this
    session (would duplicate the 07-27 finding without new information);
    confirmed only that it remains red.
  - P2-1 (autoloop covers 1 of 16 dispatchable skills nightly): **still
    unfixed**, confirmed live — `DEFAULT_SKILL: zonewise` is still the only
    value ever used on the `schedule` trigger (`autoloop.yml` line 47).
    Moot in practice while P0-2's credential is broken (0 real iterations
    either way), but the rotation gap itself hasn't been addressed.
- **New this window:** `skill-meta-updater.yml` (added 2026-08-03, commit
  `b75b3ea7`) now triggers on push to `docs/skill-audits/**` and is meant to
  turn each audit into an `AUTO-LEARNINGS` append to `CC_META_PROMPT.md`.
  Per this task's own non-goals, this report does not edit
  `CC_META_PROMPT.md` — committing this file should trigger that workflow,
  which is the intended path for F1/F2/F3 above to actually change future
  dispatch behavior. Worth Ariel confirming after commit that the workflow
  actually fires and produces a sane append (not verified live in this
  session — would require watching a post-commit trigger this audit itself
  causes, which is out of order to check before the commit exists).

---

## Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| F1 | `SUPABASE_DB_PASSWORD` still stale a month after documentation; Management-API fallback has a real gap for `CONCURRENTLY` DDL | P1 | Documented, not fixed (credential — Ariel-only) |
| F2 | 42/42 Platform Skills show zero invocation evidence in 312 dispatch rows / 245 commits this window | P1 | Documented — systemic, not a single bug to patch |
| F3 | SRID/geometry corruption recurs same-day as a large repair (DeSoto); unclear if repair missed a table or `zw_parcels` is a second source | P2 | Flagged as UNKNOWN which — needs a direct data-quality look, out of scope here |
| — | Telegram bot token points at unrelated third-party casino-bot infra with an active foreign webhook | P0 (single incident) | Root-caused and self-contained this session; Ariel should independently confirm the secret's provenance |
| — | P0-2/P1-1/P2-1 from 2026-07-27 audit | carry-over | All three still open, re-confirmed live (not re-worked — no new in-repo, non-credential fix available beyond what 07-27 already applied) |

## Outstanding items for Ariel (cannot be closed by an agent session)

1. Re-authenticate Claude Code on Hetzner (`claude /login` on 87.99.129.125) — unblocks autoloop entirely (P0-2, 3 weeks unresolved past the 07-27 fix).
2. Rotate/rescope `GH_PAT` for `claude-skills-library` access — unblocks `skills-health-check.yml` (P1-1).
3. Rotate `SUPABASE_DB_PASSWORD` — unblocks the one confirmed fallback-ladder gap (F1, `CREATE INDEX CONCURRENTLY`-class DDL).
4. Independently confirm `TELEGRAM_BOT_TOKEN`'s provenance — a foreign casino-bot webhook was live behind this repo's secret.
5. Decide whether F2 (Skills catalog vs. real dispatch traffic fully disjoint) reflects an intentional operating model (ad-hoc issue dispatch is the real interface, `.claude/skills/` is reference material for interactive sessions only) or a genuine gap Ariel wants closed — this audit surfaces the fact, not a fix, since it's a product/workflow decision.

## DoD check

- [x] `docs/skill-audits/skill-audit-2026-08-17.md` — this file, to be committed to `main`.
- [x] Per-skill invocation table present (§3, all 42 skills).
- [x] Outcome to be logged to `agent_ops_log` (`task='skill-audit'`, `status='VERIFIED'`) — see commit log / next tool call for the row contents.
