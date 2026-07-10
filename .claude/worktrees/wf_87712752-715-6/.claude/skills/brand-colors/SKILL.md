---
name: brand-colors
description: Use when generating UI components, checking color compliance, or designing frontend elements for BidDeed.AI or ZoneWise. Triggers on: brand colors, Navy #1E3A5F, Orange #F59E0B, Inter font, dark background #020617, UI component, Tailwind, frontend design, brand compliance.
---

# Brand Colors

## Role
Own visual identity as pixel-exact brand enforcement, not approximate color matching.

## Working Mode
Map component -> Apply brand tokens -> Validate hex values exact match -> Check font -> Validate dark bg.

## Focus Areas
1. Primary color -- Navy #1E3A5F (exact hex, no approximations)
2. Accent color -- Orange #F59E0B (exact hex, not yellow, not amber-400)
3. Background -- #020617 (near-black, not pure black #000000)
4. Typography -- Inter font family (Google Fonts or system fallback: sans-serif)
5. Tailwind mapping -- navy=custom, orange=amber-400 (#F59E0B), bg=slate-950 (#020617)
6. Component compliance -- buttons, cards, navbars, badges must use brand tokens
7. Dark theme default -- all components start with dark background unless override
8. Contrast ratio -- text on #020617 bg must pass WCAG AA (4.5:1 minimum)

## Quality Gates
- verify: Primary color hex is exactly #1E3A5F (not #1E3B5F, not #1D3A5F)
- confirm: Accent color hex is exactly #F59E0B (not #F59E0C, not amber-500 #F59E0B)
- check: Font-family includes 'Inter' as first or second value
- ensure: Background uses #020617 for dark-mode components
- call_out: Any hardcoded color that doesn't match brand palette

## Output Format
When generating a component, include a brand audit block:
```
Brand Audit:
- Primary: #1E3A5F [PASS/FAIL]
- Accent: #F59E0B [PASS/FAIL]
- Background: #020617 [PASS/FAIL]
- Font: Inter [PASS/FAIL]
- Contrast (text on bg): X.X:1 [PASS/FAIL - WCAG AA >= 4.5:1]
```

## Constraints
- NEVER use approximate colors (e.g., tailwind blue-900 #1e3a8a != brand navy #1E3A5F)
- NEVER use pure black #000000 as background
- NEVER use amber-500 (#F59E0B ambiguity check: amber-400 IS #FBBF24, amber-500 IS #F59E0B)
- Inter font must be loaded via Google Fonts or local bundle before use
- Brand colors must be defined as CSS variables or Tailwind config, not inline hex

## Guard Rail
Do not generate any UI component without running the brand audit block, even for quick prototypes.
