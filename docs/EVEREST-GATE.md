# EVEREST GATE — Enterprise-Grade 16-Point Verification (EG14 v2)

**Status:** PERMANENT • Authoritative • SSOT for all SUMMIT shipping criteria
**Owner:** Claude AI Architect
**Established:** Mar 30 2026 • Codified: Apr 8 2026 • **v2: Apr 9 2026 (SUMMIT #272)**
**Supersedes:** All prior "shipped" / "WIP" / "verified" definitions

---

## Definition

**EVEREST GATE (EG14 v2)** is the 16-point enterprise-grade verification every SUMMIT must pass before claiming task satisfaction. No SUMMIT closes without **16/16 PASS** against the **production domain** (zonewise.ai or biddeed.ai), evidenced by Playwright screenshots stored in Supabase and posted as a comment on the originating issue.

**Verified delivery is the moat.** Anything less = WIP=0, SUMMIT reopens.

---

## The 14 Points

| # | Check | Criterion | Evidence |
|---|-------|-----------|----------|
| 1 | **HTTP Status** | Production URL returns 200, valid SSL, no redirect chains | curl -I + screenshot |
| 2 | **Lighthouse** | Performance ≥90, SEO ≥90, A11y ≥90, Best Practices ≥90 | Lighthouse JSON in Supabase |
| 3 | **SEO** | metadata export, robots.ts, sitemap.ts, schema.org JSON-LD | Source files + curl /robots.txt /sitemap.xml |
| 4 | **Accessibility** | axe-core WCAG 2.1 AA pass, alt text, aria-labels, focus-visible, contrast 4.5:1 | axe JSON report |
| 5 | **Mobile Responsive** | No overflow at 375/768/1280, touch targets ≥44px | Mobile Playwright screenshot |
| 6 | **Security Headers** | HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP | curl -I parse |
| 7 | **Custom 404** | app/not-found.tsx renders branded 404 | curl /nonexistent + screenshot |
| 8 | **Zero Console Errors** | No JS errors on /, primary routes, target feature route | Playwright console capture |
| 9 | **House Brand Compliance** | Navy #1E3A5F, Orange #F59E0B, Inter font, bg #020617, no banned colors | BrandGuard scan report |
| 10 | **Conversion Flow** | Primary user funnel works end-to-end (e.g. 5-click → modal → CTA) | Playwright user flow trace |
| 11 | **Feature Functional** | The new feature itself works as specified (interactive, data flows, no broken state) | Playwright interaction test |
| 12 | **API Health** | All /api/* routes touched by the feature return 200 with valid payload | curl loop log |
| 13 | **Supabase Integrity** | Required tables exist, RLS policies set, RPCs callable | psql/REST verification |
| 14 | **Cross-Browser** | Chromium + Firefox + WebKit at 1920x1080 — no layout breaks, feature works in all 3 | 3 Playwright screenshots |
| 15 | **Supply-Chain Clean** | `npm audit --omit=dev --audit-level=high` exits 0. No high/critical vulnerabilities in production dependencies. | CI job output (SUMMIT #272) |
| 16 | **RLS Coverage** | `select count(*) from public.zw_rls_audit()` returns 0. Every public table has RLS enabled with at least one policy. | psql query result (SUMMIT #272) |

**Bonus (mandatory but not numbered):** Core Web Vitals — LCP <2.5s, CLS <0.1, INP <200ms.

---

## Pass / Fail Rules

- **PASS = 16/16**, no exceptions. 15/16 = WIP=0, reopens automatically.
- Any FAIL on points 1, 6, 8, 11, 15, 16 = **CRITICAL**, blocks all promotion.
- Points 2 (Lighthouse) and 4 (axe) require numerical evidence files in Supabase.
- All screenshots must be of the **production domain** (zonewise.ai / biddeed.ai), NOT vercel.app preview, NOT /labs/*.

---

## Workflow

```
SUMMIT dispatch
  → Build feature
  → Deploy to Vercel preview (smoke test only)
  → PR opened
  → Promote to production via promote-now.yml
  → EVEREST GATE runs (14-point Playwright suite)
  → 16/16? → comment screenshots + close SUMMIT
  → <14? → AUTOLOOP V2: signal_detector → evolver → patch → redeploy → re-run gate (max 3 loops)
  → Still <14 after 3 loops? → BLOCKED comment, escalate
```

---

## Storage

- Screenshots → Supabase bucket `summit-screenshots/<summit-id>/eg14/<point-N>.png`
- Lighthouse / axe reports → `summit-screenshots/<summit-id>/eg14/reports/`
- Pass/fail row → `eg14_runs` table (`summit_id`, `point_id`, `status`, `evidence_url`, `ran_at`)

---

## Standard SUMMIT spec template (mandatory section)

Every SUMMIT spec MUST include:

```markdown
## EVEREST GATE Requirements (EG14)

**Production URL:** https://<domain>/<route>
**Feature-specific functional test (Point 11):** <describe what Playwright must click/verify>
**Brand compliance scope (Point 9):** <which components BrandGuard scans>
**API routes touched (Point 12):** <list /api/* endpoints>
**Supabase dependencies (Point 13):** <list tables + RPCs>
**Cross-browser scope (Point 14):** Chromium + Firefox + WebKit
```

---

## Naming

- Long form: **EVEREST GATE**
- Short form: **EG14**
- Reference in commits: `eg14:` prefix (e.g., `eg14: pass 12/14, mobile overflow + lighthouse 87`)
- Reference in SUMMIT comments: `EVEREST GATE 16/16 ✅` or `EVEREST GATE 11/14 — see eg14_runs`

---

*This document is the single source of truth. If memory conflicts with this file, this file wins.*
