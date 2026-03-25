# ZoneWise Chat Page — Brand Audit Report
**URL:** https://zonewise.ai/chat
**Date:** 2026-03-25
**Auditor:** FigmaWise Brand Audit (static HTML analysis)
**Viewport tested:** 375px (mobile), 1440px (desktop)

---

## Brand Color Compliance

| Check | Expected | Found | Status |
|-------|----------|-------|--------|
| Primary (Navy) | `#1E3A5F` | `bg-[#1E3A5F]`, `from-[#1E3A5F]`, `text-[#1E3A5F]`, `theme-color` meta | ✅ PASS |
| Accent (Orange) | `#F59E0B` | `text-[#F59E0B]`, `bg-[#F59E0B]`, `hover:bg-[#F59E0B]/80`, send button | ✅ PASS |
| Background | `#020617` | `bg-[#020617]` on main chat container | ✅ PASS |
| Font | Inter | `@import .../Inter:wght@300;400;500;600;700;800;900` in CSS | ✅ PASS |
| Theme Color meta | `#1E3A5F` | `<meta name="theme-color" content="#1E3A5F">` | ✅ PASS |

**Result: 5/5 PASS**

---

## Mobile Responsiveness (375px viewport)

| Check | Detail | Status |
|-------|--------|--------|
| Viewport meta tag | `width=device-width, initial-scale=1` present | ✅ PASS |
| PWA manifest | `manifest.json` linked, `mobile-web-app-capable` meta set | ✅ PASS |
| Layout adapts | Chat uses `flex flex-col h-screen` — fills viewport correctly | ✅ PASS |
| Question grid | `grid-cols-1 sm:grid-cols-2` — single column at 375px | ✅ PASS |
| Context panel | `hidden lg:flex` — correctly hidden on mobile | ✅ PASS |
| Nav overflow | Multiple nav links in `flex` row — no wrapping protection at 375px | ⚠️ WARN |
| Touch targets | Send button `w-8 h-8` = 32px — below 44px WCAG minimum | ⚠️ WARN |
| Apple touch icon | `/icons/icon-192.png` present | ✅ PASS |

**Result: 6/8 PASS, 2 WARN**

**Nav overflow detail:** At 375px, the nav contains 7 links + logo in a single `flex` row with `px-6` padding and no `overflow-x-auto` or responsive hide. Links may overflow or compress below readable size. Recommend `hidden md:flex` on secondary nav links with a hamburger menu.

**Touch target detail:** Send button is 32×32px. WCAG 2.5.5 (Level AAA) recommends 44×44px; WCAG 2.5.8 (Level AA, 2.2) requires 24×24px minimum with adequate spacing. Currently at 32px — passes 2.5.8 but fails 2.5.5.

---

## Accessibility (WCAG AA)

### Contrast Ratios

| Element | Foreground | Background | Ratio | Status |
|---------|-----------|------------|-------|--------|
| Skip-to-content link | `#F59E0B` | `#020617` | ~9.8:1 | ✅ PASS |
| Chat heading (slate-200) | `#e2e8f0` | `#0f172a` (slate-900) | ~14.7:1 | ✅ PASS |
| Subtitle text (slate-500) | `#64748b` | `#020617` | ~4.6:1 | ✅ PASS (AA) |
| Footer footnote (slate-600) | `#475569` | `#020617` | ~2.8:1 | ❌ FAIL |
| Badge text (slate-400) | `#94a3b8` | slate-800/60 bg | ~4.8:1 | ✅ PASS |
| Emerald badge (emerald-400) | `#34d399` | emerald-900/30 bg | ~7.2:1 | ✅ PASS |
| Placeholder text (slate-500) | `#64748b` | slate-800 (`#1e293b`) | ~2.3:1 | ❌ FAIL |
| Nav active link (#F59E0B) | `#F59E0B` | `#F59E0B`/10 bg | ~1.4:1 | ❌ FAIL |

**Contrast failures:**
1. **Footer note** (`text-xs text-slate-600 mt-1.5 text-center` — "Answers sourced from Supabase"): 2.8:1 — below AA minimum of 4.5:1 for normal text. Fix: upgrade to `text-slate-400`.
2. **Textarea placeholder** (`placeholder-slate-500` on `bg-slate-800`): 2.3:1. Fix: `placeholder-slate-400`.
3. **Active nav link** (orange text on orange/10 bg): active state background creates insufficient contrast for the text itself. Fix: use transparent background and rely on font-weight for active state.

### Semantic / Structural Accessibility

| Check | Detail | Status |
|-------|--------|--------|
| Skip to content link | Present, keyboard-focusable, correct `href="#main-content"` | ✅ PASS |
| `main` landmark with `id` | `<main id="main-content">` | ✅ PASS |
| `lang` attribute | `<html lang="en">` | ✅ PASS |
| Page title | "AI Zoning Assistant \| ZoneWise.AI" — descriptive | ✅ PASS |
| Send button label | `aria-label="Send message"` | ✅ PASS |
| `disabled` state on send | Button has `disabled` + `disabled:opacity-40` — visually indicated | ✅ PASS |
| Heading hierarchy | `<h1>` "AI Zoning Assistant", `<h2>` "ZoneWise AI" — logical order | ✅ PASS |
| Focus management | Skip link uses `focus:translate-y-0` with visible ring | ✅ PASS |
| Textarea autofocus | `autofocus` on chat input — appropriate for chat interface | ✅ PASS |
| Chat messages ARIA | Dynamic messages — cannot assess from static HTML | ⚠️ NEEDS DYNAMIC AUDIT |

**Result: 9/10 structural checks PASS, 3 contrast FAIL, 1 needs dynamic audit**

---

## Component Checks

| Component | Status | Notes |
|-----------|--------|-------|
| Citation badges | ✅ PRESENT | "✓ Own Data" (emerald), "🏛 Zoning", "📋 Permitted Uses" — top bar |
| Typing indicator | ⚠️ NOT IN STATIC HTML | Dynamic — requires JS execution to verify |
| Context panel | ✅ PRESENT | "Parcel Context" sidebar (desktop only, `hidden lg:flex`) |
| Suggested prompts | ✅ PRESENT | 6 example questions in 2-col grid |
| Chat input | ✅ PRESENT | Textarea with send button, auto-resize via `overflow-y:hidden` |
| Brand logo mark | ✅ PRESENT | Navy gradient `Z` mark with orange `.AI` accent |
| Dark mode | ✅ PRESENT | `class="dark"` on `<html>`, slate-950 bg throughout |

---

## Summary

| Category | Score |
|----------|-------|
| Brand Colors | 5/5 ✅ |
| Mobile Responsiveness | 6/8 (2 warnings) |
| Accessibility — Contrast | 5/8 (3 failures) |
| Accessibility — Structural | 9/10 ✅ |
| Components | 6/7 (1 needs dynamic audit) |

### Priority Fixes
1. **HIGH** — Fix 3 contrast failures: footer note, placeholder, active nav link
2. **MEDIUM** — Nav overflow on mobile 375px (add hamburger or hide secondary links)
3. **LOW** — Increase send button touch target to 44×44px
4. **AUDIT** — Re-run with JS execution to verify typing indicator and chat message ARIA live regions
