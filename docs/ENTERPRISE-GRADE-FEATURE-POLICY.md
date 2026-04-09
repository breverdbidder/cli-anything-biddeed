# ENTERPRISE-GRADE FEATURE POLICY

**Status:** PERMANENT STANDING RULE
**Locked:** 2026-04-09
**Directive from:** Ariel Shapira
**Applies to:** All feature work on zonewise-web, chat.zonewise.ai, and any future Everest Capital USA production surface

---

## The Rule

Every feature built from competitive weakness analysis must preserve or improve the EG14 16/16 lock on the production domain. No feature is considered shipped until the live homepage passes all 16 enterprise-grade checks post-merge.

**`<16/16 = WIP = 0`**

## What triggers this gate

Any SUMMIT, PR, or direct commit that:
- Adds or modifies files under `app/`, `lib/`, `components/`, `middleware.ts`, or `next.config.mjs` on zonewise-web
- Adds new API routes or modifies existing route handlers
- Touches the data fetching layer (Supabase clients, external API calls)
- Modifies rendering pathways that affect the homepage or any top-level marketing route
- Changes dependencies in `package.json`
- Was dispatched as a response to a competitor battle card gap analysis

## The 14 checks (SSOT)

See `docs/EVEREST-GATE.md` for the canonical list. As of 2026-04-09 the 16 checks are:

1. HTTP 200 on `/`
2. Lighthouse Performance ≥ 90
3. Lighthouse Accessibility ≥ 90
4. Lighthouse Best Practices ≥ 90
5. Lighthouse SEO ≥ 90
6. Security Headers grade A+
7. Brand Guard pass (house brand colors, fonts, logo)
8. API Health (`/api/health` returns ok)
9. Zero console errors (Chrome, Firefox, Safari)
10. Cross-browser parity 3/3
11. Mobile viewport responsive
12. Meta tags valid (Open Graph, Twitter, canonical)
13. Structured data valid (JSON-LD)
14. Sitemap + robots valid and served
15. Supply-chain clean (`npm audit --omit=dev --audit-level=high` exits 0)
16. RLS coverage (`select count(*) from public.zw_rls_audit()` returns 0)

## Enforcement Protocol

### For SUMMIT dispatches

Every SUMMIT issue body MUST include a **Deliverable N — EG14 16/16 Gate** section as the final blocking deliverable. The gate section must specify:

- Exact workflow dispatch command
- Poll interval and timeout
- Supabase query for `eg14_runs` verification
- Three outcome branches (A: 16/16 complete, B: regression fix loop, C: timeout retry)
- No Telegram report until EG14 has a verdict

### For direct commits

Any developer (human or AI) committing to zonewise-web main must:

1. Before commit: run EG14 locally or dispatch against a preview deployment
2. After merge: dispatch EG14 within 10 minutes
3. If EG14 regresses: rollback or fix within 2 hours
4. No multiple features stacked on a broken EG14 — fix first, then continue

### For Claude Code autonomous runs

When Claude Code is building from a SUMMIT issue, it must:

1. Commit each deliverable separately
2. Dispatch EG14 after the final deliverable lands
3. Wait for the verdict (do not mark the SUMMIT complete mid-verdict)
4. Execute outcome branch A, B, or C based on the result
5. Only send the completion Telegram after EG14 returns 16/16 or after 3 failed retries

### For emergency rollbacks

If a regression is discovered on the live site:

1. Identify the commit that introduced it (git bisect against EG14 run history)
2. Revert that commit on main
3. Re-dispatch EG14
4. Only then investigate the root cause in a feature branch

## Rationale

The competitive weakness analysis process (PropZone, Algoma, MapWise, Zoneomics, etc.) continuously generates new feature requirements. Each new feature touches the production surface. Without an enforcement gate, incremental drift from the 16/16 lock is inevitable — new console errors from third-party dependencies, bundle size growth from new components, security header drift from middleware edits, brand guard violations from hasty UI work.

The alternative — "ship moat, fix quality later" — produces exactly the opposite of an enterprise-grade product. PropZone can be beaten on KPI count. It cannot be beaten on KPI count AND broken pages AND 60-perf Lighthouse. We compete on the entire experience.

## Related SSOT

- `docs/EVEREST-GATE.md` — canonical 14-check definitions
- `.github/workflows/eg14-summit-398.yml` — the EG14 workflow
- Supabase `eg14_runs` table — execution history
- `.claude/rules/data.md` (zonewise-web) — data discipline rules
- `data/competitors/*.ts` (zonewise-web) — competitive weakness sources

## Exceptions

**None.** The rule applies to all production domains. Local development, preview deployments, and non-production experiments are exempt.

## Revision history

| Date | Change | Author |
|---|---|---|
| 2026-04-09 | Initial policy locked as standing rule | Ariel Shapira |


---

## Battle Card Refresh Discipline

**Locked:** 2026-04-09 (addendum)
**Applies to:** all SUMMITs that close gaps identified in `zonewise-web/data/competitors/*.ts`

### The Rule

When a SUMMIT closes a gap listed in any competitor battle card, the card MUST be refreshed in the same SUMMIT commit, **before** the EG14 16/16 gate. The refresh happens in the same branch as the feature so the live card reflects the new reality the moment EG14 passes.

### What "refresh" means concretely

Six required edits to `data/competitors/{slug}.ts`:

1. **Remove the closed code from `gap_kpi_codes`** — the array should shrink by exactly the number of gaps closed
2. **Add matching codes to `parity_kpi_codes` OR `advantage_kpi_codes`** — parity if the competitor already has it, advantage if we shipped something they don't have
3. **Update the three integer counters numerically:**
   - `zonewise_wins` = `advantage_kpi_codes.length`
   - `competitor_wins` = `gap_kpi_codes.length`
   - `ties` = `parity_kpi_codes.length`
   The three counts must match the array lengths. Mismatches are a Honesty Protocol violation.
4. **Append a dated source citation** to the `sources` array with format:
   ```typescript
   {
     label: 'SUMMIT #{number} — {one-line description of what shipped}',
     url: 'https://github.com/breverdbidder/zonewise-web/commit/{commit-sha}',
     date: 'YYYY-MM-DD',
   }
   ```
5. **Update `their_strengths`** — remove any bullet that described a capability we now have (it is no longer a strength relative to ZoneWise)
6. **Update `our_edge`** — add a new bullet reflecting the shipped capability if it materially changes our positioning
7. **Update `verdict_line`** — only if the closure materially changes the positioning story. Leave unchanged for incremental closures.

### Why this is a discipline, not a checklist

Competitor battle cards are **living scoreboards**. They drive:
- Marketing copy and landing page positioning
- Sales conversations ("we match PropZone on X, beat them on Y")
- Product roadmap prioritization (visible gaps attract build pressure)
- Honest competitive intelligence for the team

Stale battle cards — where the card still lists "water setback" as a gap after we've shipped it — are **lying about our moat**. That is a direct Honesty Protocol violation (VERIFIED claims must match reality). Customers, investors, and internal team members read these cards and make decisions based on them. Stale data corrupts every downstream decision.

### Enforcement

Every SUMMIT issue body MUST include:

- A deliverable titled **"Battle card refresh"** as the penultimate deliverable (immediately before the EG14 gate)
- Explicit acceptance criteria referencing the numeric counters and the removed/added codes
- Verification via `curl https://zonewise.ai/competitors/{slug}` + DOM grep for the updated counts

SUMMITs that ship features without refreshing the relevant battle card are marked INCOMPLETE regardless of whether the feature itself works. The missing refresh is a ghost-success pattern and triggers the 3× Honesty Protocol penalty.

### Example — PropZone sprint arithmetic

| SUMMIT | Starting | Action | Ending |
|---|---|---|---|
| Pre-#402 (b1aff5d1) | 40W / 4L / 26T | — | 40W / 4L / 26T |
| #402 OSINT | 40W / 4L / 26T | +10 advantage (OWN-001..010) | 50W / 4L / 26T |
| #403 Property card | 50W / 4L / 26T | -3 gap, +3 parity (ZON-019, 020, 021) | 50W / 1L / 29T |
| #404 Mapbox tiles | 50W / 1L / 29T | +1 parity (ZON-022) | 50W / 1L / 30T |
| #405 Water setback | 50W / 1L / 30T | -1 gap, +1 parity (ZON-023) | **50W / 0L / 31T** |

Each row reflects a battle card commit in the same SUMMIT as the feature ship. No SUMMIT is marked complete until both the feature AND the card update are live AND EG14 returns 16/16.

### Applies to all 11 competitors

This rule is not PropZone-specific. As the 10 remaining battle cards (Algoma, Zoneomics, MapWise, PropertyOnion, Forma+Zoneomics, TestFit, Reventure, Foreclosure.com, AI Topia, CoreLogic/ATTOM) are built and as their gaps are closed in future sprints, the same refresh discipline applies identically.
