---
name: designwise
description: Use when reverse-engineering UI designs (TeardownWise), generating AI-designed components (StitchWise), or running the DesignWise pipeline. Triggers on: teardown, teardown UI, reverse engineer website, extract CSS/JS techniques, designwise, stitch design, generate UI, animation library detection, glassmorphism, parallax, cli-anything-designwise.
---

# DesignWise

## Role
Own design intelligence as evidence-extracted technique detection, not visual guesswork.

## Working Mode
Web fetch URL -> Extract CSS/JS artifacts -> Detect techniques via pattern matching -> Persist to teardown_bundles -> Return structured JSON.

## Focus Areas
1. TeardownWise pipeline -- fetch URL → extract CSS/JS → detect layout/animation/effects/components → persist → return JSON
2. Layout detection -- css-grid, flexbox, css-grid+flexbox, float (from CSS source, not inference)
3. Animation library detection -- gsap, framer-motion, anime-js, lottie, aos, css-animations, none (from script src/imports)
4. Effect detection -- glassmorphism, parallax, scroll-animations, gradient-mesh, particle-effects, blur-overlay, sticky-nav
5. Component detection -- hero-section, card-grid, pricing-table, testimonials, modal, accordion, tabs, infinite-scroll, toast-notifications
6. StitchWise integration -- pass teardown output as design brief to Stitch SDK for brand-compliant regeneration
7. Brand guard enforcement -- BrandGuard ALWAYS overrides: Navy #1E3A5F, Orange #F59E0B, Inter, bg #020617
8. Supabase persistence -- teardown_bundles table, url as dedup key, run 002_teardown_bundles.sql migration first

## Quality Gates
- verify: Output contains layout_technique, animation_library, effects[], component_patterns[] fields
- confirm: Detection sources are extracted from actual CSS/JS, not inferred from visual description
- check: Brand guard applied — any generated output uses Navy #1E3A5F + Orange #F59E0B + Inter + bg #020617
- ensure: teardown_bundles row persisted with url, techniques, detected_at timestamp
- call_out: Report UNTESTED if Supabase migration 002_teardown_bundles.sql has not been run

## Output Format
```json
{
  "url": "https://example.com",
  "layout_technique": "css-grid+flexbox",
  "animation_library": "gsap",
  "color_system": {"primary": "#hex", "accent": "#hex", "bg": "#hex"},
  "typography": {"font_family": "Inter", "scale": "fluid"},
  "effects": ["glassmorphism", "scroll-animations"],
  "component_patterns": ["hero-section", "card-grid", "sticky-nav"],
  "detected_at": "2026-03-29T00:00:00Z",
  "source_verified": true
}
```

## Constraints
- NEVER infer animation library from visual appearance -- detect from script tags or import statements
- NEVER generate brand-non-compliant colors -- BrandGuard override is mandatory
- Fetch cap: 500KB max per URL (skip oversized assets, log as truncated)
- Use cli-anything-designwise teardown <url> as canonical CLI -- do not create alternatives
- Migration dependency: designwise/migrations/002_teardown_bundles.sql must run before persistence

## Guard Rail
Do not report detected techniques as CONFIRMED without extracting from actual CSS/JS source -- visual inspection is always HYPOTHESIS.
