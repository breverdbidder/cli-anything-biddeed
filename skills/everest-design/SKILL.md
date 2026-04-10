---
name: everest-design
description: Everest Capital brand design system for BidDeed.AI and ZoneWise.AI. Use this skill whenever building or styling any UI component, page, dashboard, landing page, map interface, or data visualization for the Everest ecosystem. Applies the canonical Navy/Amber/Void dark-mode design tokens, Inter + JetBrains Mono typography, component specs, and layout principles. Always read this BEFORE the frontend-design skill — this overrides generic aesthetic choices with Everest brand-specific tokens.
license: MIT
---

# Everest Design System Skill

This skill provides the canonical design tokens, component specifications, and brand guidelines for all Everest Capital products (BidDeed.AI and ZoneWise.AI).

## When to Use

Apply this skill BEFORE writing any UI code for:
- BidDeed.AI dashboards, auction tables, bid interfaces
- ZoneWise.AI choropleth maps, spatial views, property panels
- Landing pages for either product
- Shared components (nav, cards, badges, buttons, inputs, tables)
- Data visualizations (charts, scores, metrics)
- Email templates or marketing assets using Everest branding

## How to Use

1. Read `DESIGN.md` in this directory FIRST
2. Extract the relevant section for your task (e.g., Section 4 for components, Section 9 for agent prompts)
3. Apply tokens exactly — do not substitute fonts, colors, or radius values
4. If also using the `frontend-design` skill, Everest tokens OVERRIDE its generic aesthetic guidance

## Key Quick Reference

| Token | Value | Use |
|-------|-------|-----|
| Background | `#020617` | Page canvas (void) |
| Card Surface | `#1E3A5F` | Cards, panels, nav |
| Accent | `#F59E0B` | CTAs, links, key data |
| Primary Text | `#F8FAFC` | Headings, primary content |
| Secondary Text | `#94A3B8` | Descriptions, labels |
| Border | `#1E293B` | Dividers, card borders |
| Success | `#10B981` | BID badge, positive ROI |
| Danger | `#EF4444` | Errors, overbid, expired |
| Font Primary | Inter | All UI text |
| Font Data | JetBrains Mono | Dollar amounts, IDs, scores |
| Radius | 6-8px | Buttons 6px, cards 8px |

## Brand Rules (Non-Negotiable)

- Dark mode ONLY — no light mode variants unless explicitly requested
- Never use pill-shaped buttons (9999px radius)
- Never use gradients on buttons — flat fills only
- Always pair BidDeed.AI + ZoneWise.AI — they are one ecosystem
- Always pair foreclosures + tax deeds — never separate them
- JetBrains Mono for ALL financial figures — no exceptions
- Amber is the ONLY warm color — never introduce orange, yellow, or red accents for decoration

## File Structure

```
everest-design/
├── SKILL.md          # This file — skill metadata and quick reference
└── DESIGN.md         # Full 9-section design system specification
```
