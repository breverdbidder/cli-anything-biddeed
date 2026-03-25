---
name: ui-ux-pro-max
description: Design intelligence engine for DesignWise Squad. BM25 search over 161 color palettes, 85 styles, 99 UX guidelines, 57 font pairings, 162 product types, 25 chart types. Zero external dependencies. Use for any UI/UX design task — style selection, color systems, typography pairing, UX anti-pattern detection, landing page patterns, chart selection. Generates complete design systems from a single prompt.
allowed-tools:
  - "Bash"
  - "Read"
  - "Write"
---

# UI/UX Design Intelligence — DesignWise Integration

Local BM25 search engine over curated design databases. No API keys. No network calls. Pure local intelligence.

## When To Use

- Choosing styles, colors, typography for any page/component
- Generating a complete design system (DESIGN.md)
- Validating UX patterns against best practices
- Selecting chart types for data visualization
- Landing page layout pattern selection
- React performance optimization guidance

## House Brand Override

**ALWAYS apply House Brand before any recommendation:**
- Primary: Navy `#1E3A5F`
- Accent/CTA: Orange `#F59E0B`
- Font: Inter
- Background: `#020617` (slate-950)
- Source: `globals.css` + `BRAND_COLORS.md`

Use design intelligence to ENHANCE House Brand, never replace it. Search results inform decisions; House Brand constrains the palette.

## Quick Reference

### Generate Complete Design System
```bash
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "real estate zoning analytics SaaS" --design-system -p "ZoneWise"
```

### Domain Searches
```bash
# Style recommendations
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "dark dashboard analytics" --domain style

# Color palette ideas (filter through House Brand)
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "real estate professional" --domain color

# Typography pairings
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "modern data-heavy" --domain typography

# UX best practices
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "map interaction loading" --domain ux

# Chart type selection
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "comparison ranking" --domain chart

# Landing page patterns
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "SaaS freemium conversion" --domain landing

# Product type matching
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "analytics dashboard" --domain product

# React performance
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "virtualization large list" --domain react-performance
```

### Persist Design System
```bash
# Save global design system
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "real estate SaaS" --design-system --persist -p "ZoneWise"

# Add page-specific overrides
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "heatmap explorer" --design-system --persist -p "ZoneWise" --page "explorer"
```

## Integration with DesignWise Agents

| Agent | Usage |
|:---|:---|
| StitchWise | Run `--design-system` before every Stitch generation. Feed output into prompt enhancement. |
| BrandGuard | Use `--domain color` + `--domain typography` to validate choices against professional standards. |
| CodeWise | Use `--domain react-performance` for optimization. `--domain style` for Tailwind class selection. |
| ContentWise | Use `--domain landing` for conversion-optimized copy placement. |
| SEOWise | Use `--domain ux` for Core Web Vitals-related UX decisions. |
| IterateWise | Use `--design-system` to generate A/B test variant styles. |

## Data Coverage

| Domain | File | Records | Content |
|:---|:---|:---|:---|
| style | styles.csv | 85 | UI styles with keywords, effects, accessibility, complexity |
| color | colors.csv | 161 | Complete palettes (primary→ring) per product type |
| typography | typography.csv | 74 | Font pairings with mood, heading/body, scale |
| ux | ux-guidelines.csv | 99 | Do/Don't with code examples per platform |
| chart | charts.csv | 25 | Data type → chart type mapping with a11y |
| landing | landing.csv | 35 | Conversion patterns with section order, CTA placement |
| product | products.csv | 162 | Product type → style/color/layout recommendations |
| app-interface | app-interface.csv | 30 | App-specific interface patterns |
| icons | icons.csv | 105 | Icon usage guidelines |
| ui-reasoning | ui-reasoning.csv | 162 | Design decision rationale |
| react-performance | react-performance.csv | 45 | React optimization patterns |

## Architecture

```
ui-ux-pro-max/
├── SKILL.md           ← This file
├── scripts/
│   ├── search.py      ← CLI entry point
│   ├── core.py        ← BM25 + regex hybrid search engine
│   └── design_system.py ← Design system generator
└── data/
    ├── styles.csv
    ├── colors.csv
    ├── typography.csv
    ├── ux-guidelines.csv
    ├── charts.csv
    ├── landing.csv
    ├── products.csv
    ├── app-interface.csv
    ├── icons.csv
    ├── ui-reasoning.csv
    ├── react-performance.csv
    └── stacks/         ← Stack-specific guidelines
```

## Origin

Forked from `nextlevelbuilder/ui-ux-pro-max-skill` v2.1.0 (MIT License).
Adapted for DesignWise Squad with House Brand integration.
Non-essential data (Chinese translations, 1900-row font dump) removed for context efficiency.
