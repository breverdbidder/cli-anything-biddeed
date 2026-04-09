# ENTERPRISE-GRADE FEATURE POLICY

**Status:** PERMANENT STANDING RULE
**Locked:** 2026-04-09
**Directive from:** Ariel Shapira
**Applies to:** All feature work on zonewise-web, chat.zonewise.ai, and any future Everest Capital USA production surface

---

## The Rule

Every feature built from competitive weakness analysis must preserve or improve the EG14 14/14 lock on the production domain. No feature is considered shipped until the live homepage passes all 14 enterprise-grade checks post-merge.

**`<14/14 = WIP = 0`**

## What triggers this gate

Any SUMMIT, PR, or direct commit that:
- Adds or modifies files under `app/`, `lib/`, `components/`, `middleware.ts`, or `next.config.mjs` on zonewise-web
- Adds new API routes or modifies existing route handlers
- Touches the data fetching layer (Supabase clients, external API calls)
- Modifies rendering pathways that affect the homepage or any top-level marketing route
- Changes dependencies in `package.json`
- Was dispatched as a response to a competitor battle card gap analysis

## The 14 checks (SSOT)

See `docs/EVEREST-GATE.md` for the canonical list. As of 2026-04-09 the 14 checks are:

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

## Enforcement Protocol

### For SUMMIT dispatches

Every SUMMIT issue body MUST include a **Deliverable N — EG14 14/14 Gate** section as the final blocking deliverable. The gate section must specify:

- Exact workflow dispatch command
- Poll interval and timeout
- Supabase query for `eg14_runs` verification
- Three outcome branches (A: 14/14 complete, B: regression fix loop, C: timeout retry)
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
5. Only send the completion Telegram after EG14 returns 14/14 or after 3 failed retries

### For emergency rollbacks

If a regression is discovered on the live site:

1. Identify the commit that introduced it (git bisect against EG14 run history)
2. Revert that commit on main
3. Re-dispatch EG14
4. Only then investigate the root cause in a feature branch

## Rationale

The competitive weakness analysis process (PropZone, Algoma, MapWise, Zoneomics, etc.) continuously generates new feature requirements. Each new feature touches the production surface. Without an enforcement gate, incremental drift from the 14/14 lock is inevitable — new console errors from third-party dependencies, bundle size growth from new components, security header drift from middleware edits, brand guard violations from hasty UI work.

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
