# Everest Capital Design System — BidDeed.AI & ZoneWise.AI

## 1. Visual Theme & Atmosphere

Everest Capital's ecosystem is a dark-mode-native real estate intelligence platform that projects institutional authority through deep navy surfaces and strategic amber accents. The page opens on an ultra-dark slate canvas (`#020617`) — not pure black, but a blue-black that reads as midnight command-center. The primary navy (`#1E3A5F`) functions as the mid-tone anchor: card surfaces, elevated panels, and section backgrounds all live in this register, creating a layered depth system where content floats above the void on navy platforms.

The amber-orange accent (`#F59E0B`) is the signal color — it marks every actionable element, every data point that demands attention, every call-to-action. In an interface dominated by cool blues and slate grays, this warm frequency cuts through with urgency. It references the gold of institutional finance, the amber of auction gavels, the warmth of profit in a sea of analytical cold. Used sparingly: CTAs, active states, key metrics, bid indicators, and the Everest summit mark.

Inter is the typographic backbone — a variable font designed for screens with a tall x-height that maximizes legibility at small sizes where data-dense auction tables live. At display sizes (48px+), Inter runs at weight 700 with tight tracking (-0.02em), creating dense, authoritative headlines that project confidence. At body sizes, weight 400 with relaxed line-height (1.6) ensures readability across long property descriptions and legal text. The monospace companion (JetBrains Mono) appears in data tables, parcel IDs, and financial figures — the "terminal aesthetic" that signals precision.

The dual-brand system serves two audiences from one visual language: **BidDeed.AI** targets professional auction investors with dense data dashboards and analytical tools; **ZoneWise.AI** serves the broader market with choropleth maps, spatial intelligence, and a freemium funnel. Both share the same design tokens — the difference is density, not identity.

**Key Characteristics:**
- Dark-mode-native: ultra-dark slate background (`#020617`) — never pure black, never gray
- Navy (`#1E3A5F`) as the primary structural color — cards, panels, elevated surfaces
- Amber-orange (`#F59E0B`) as the sole warm accent — CTAs, active states, key data
- Inter variable font — tall x-height, optimized for data-dense UI at all sizes
- JetBrains Mono for data, parcel IDs, financial figures, and code
- Institutional restraint: no gradients, no playful colors, no rounded pills
- Data-forward: tables, maps, and metrics are first-class citizens, not afterthoughts
- Dual-brand coherence: BidDeed.AI (dense/pro) and ZoneWise.AI (spatial/freemium) share one system
- Navy-tinted shadows for depth that reinforces brand atmosphere
- Border system using dark navy variants (`#1E3A5F` at low alpha)

## 2. Color Palette & Roles

### Brand Primary
- **Everest Navy** (`#1E3A5F`): Primary structural color. Card backgrounds, panel surfaces, nav bars, section fills. The visual signature of institutional authority.
- **Everest Amber** (`#F59E0B`): Primary accent. CTAs, active indicators, bid signals, key metrics, links on dark backgrounds. The only warm color in the system.
- **Void** (`#020617`): Page background, deepest canvas. A blue-black that creates atmospheric depth.

### Amber Scale
- **Amber 50** (`#FFFBEB`): Light amber surface for light-mode alerts/badges
- **Amber 100** (`#FEF3C7`): Subtle amber wash for highlighted rows
- **Amber 200** (`#FDE68A`): Hover state for amber elements
- **Amber 300** (`#FCD34D`): Secondary amber for charts/data viz
- **Amber 400** (`#FBBF24`): Warm amber for emphasis text
- **Amber 500** (`#F59E0B`): PRIMARY — CTAs, active states, key metrics
- **Amber 600** (`#D97706`): Hover/pressed state for primary CTAs
- **Amber 700** (`#B45309`): Dark amber for text on light surfaces
- **Amber 800** (`#92400E`): Deep amber for dark-on-dark accents
- **Amber 900** (`#78350F`): Deepest amber, used sparingly

### Navy Scale
- **Navy 50** (`#EFF6FF`): Lightest navy wash (light-mode surfaces)
- **Navy 100** (`#DBEAFE`): Subtle blue surface
- **Navy 200** (`#BFDBFE`): Secondary borders on light mode
- **Navy 300** (`#93C5FD`): Muted interactive on light backgrounds
- **Navy 400** (`#60A5FA`): Chart lines, secondary data viz
- **Navy 500** (`#3B82F6`): Information badges, secondary links
- **Navy 600** (`#2563EB`): Strong blue accent for special callouts
- **Navy 700** (`#1E3A5F`): PRIMARY — structural surfaces, cards, panels
- **Navy 800** (`#172D4A`): Darker panel variant, nested surfaces
- **Navy 900** (`#0F1D32`): Near-void for deep nesting, modal overlays

### Neutral Scale (Slate)
- **Slate 50** (`#F8FAFC`): Lightest surface, input backgrounds
- **Slate 100** (`#F1F5F9`): Secondary surface, table alternating rows
- **Slate 200** (`#E2E8F0`): Borders on light surfaces
- **Slate 300** (`#CBD5E1`): Disabled text, muted icons
- **Slate 400** (`#94A3B8`): Placeholder text, tertiary labels
- **Slate 500** (`#64748B`): Secondary body text, descriptions
- **Slate 600** (`#475569`): Labels, metadata on dark surfaces
- **Slate 700** (`#334155`): Heavy secondary text
- **Slate 800** (`#1E293B`): Card borders on dark mode, dividers
- **Slate 900** (`#0F172A`): Near-background, subtle separation from void

### Semantic
- **Success** (`#10B981`): Profitable bids, positive ROI, task complete
- **Success Surface** (`rgba(16, 185, 129, 0.15)`): Success badge background
- **Success Border** (`rgba(16, 185, 129, 0.3)`): Success badge border
- **Danger** (`#EF4444`): Overbid warnings, errors, auction expired
- **Danger Surface** (`rgba(239, 68, 68, 0.15)`): Error badge background
- **Danger Border** (`rgba(239, 68, 68, 0.3)`): Error badge border
- **Warning** (`#F59E0B`): Caution signals — shares the amber accent intentionally
- **Info** (`#3B82F6`): Informational badges, neutral callouts

### Data Visualization
- **Chart Primary** (`#F59E0B`): Primary data series — amber
- **Chart Secondary** (`#3B82F6`): Secondary data series — blue
- **Chart Tertiary** (`#10B981`): Third series — green
- **Chart Quaternary** (`#8B5CF6`): Fourth series — purple
- **Chart Quinary** (`#EC4899`): Fifth series — pink
- **Chart Grid** (`rgba(30, 58, 95, 0.3)`): Grid lines on dark background
- **Chart Axis** (`#64748B`): Axis labels and ticks

## 3. Typography Rules

### Font Family
- **Primary**: `Inter`, with fallback: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Monospace**: `"JetBrains Mono"`, with fallback: `"SF Mono", "Fira Code", "Cascadia Code", Consolas, monospace`
- **Font Features**: `"cv01"` on Inter for alternate `1` glyph (disambiguation from `l`/`I`); `"tnum"` for tabular figures in financial data; `"ss01"` for alternate forms where available.

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing | Notes |
|------|------|------|--------|-------------|----------------|-------|
| Display Hero | Inter | 56px (3.5rem) | 800 | 1.05 | -0.025em | Landing page heroes, splash screens |
| Display Large | Inter | 48px (3rem) | 700 | 1.08 | -0.02em | Section heroes, dashboard titles |
| H1 | Inter | 36px (2.25rem) | 700 | 1.12 | -0.015em | Page titles, major section heads |
| H2 | Inter | 28px (1.75rem) | 600 | 1.15 | -0.01em | Section headings, card group titles |
| H3 | Inter | 22px (1.375rem) | 600 | 1.2 | -0.005em | Sub-section heads, panel titles |
| H4 | Inter | 18px (1.125rem) | 600 | 1.3 | normal | Card titles, widget headers |
| Body Large | Inter | 18px (1.125rem) | 400 | 1.6 | normal | Intro text, feature descriptions |
| Body | Inter | 16px (1rem) | 400 | 1.6 | normal | Standard reading text, property descriptions |
| Body Small | Inter | 14px (0.875rem) | 400 | 1.5 | normal | Secondary text, table cells |
| Caption | Inter | 13px (0.8125rem) | 500 | 1.4 | 0.01em | Labels, metadata, timestamps |
| Micro | Inter | 11px (0.6875rem) | 500 | 1.3 | 0.02em | Badges, status indicators, axis labels |
| Button Large | Inter | 16px (1rem) | 600 | 1.0 | 0.01em | Primary CTA buttons |
| Button | Inter | 14px (0.875rem) | 600 | 1.0 | 0.01em | Standard buttons |
| Button Small | Inter | 12px (0.75rem) | 600 | 1.0 | 0.02em | Compact/toolbar buttons |
| Data Value | JetBrains Mono | 14px (0.875rem) | 500 | 1.4 | normal | Parcel IDs, dollar amounts, coordinates |
| Data Value Large | JetBrains Mono | 20px (1.25rem) | 600 | 1.2 | -0.01em | Key metric values, bid amounts |
| Data Label | JetBrains Mono | 11px (0.6875rem) | 400 | 1.3 | 0.05em | Uppercase table headers, axis labels |
| Code | JetBrains Mono | 13px (0.8125rem) | 400 | 1.6 | normal | Code blocks, API responses |

### Principles
- **Weight as hierarchy**: 800/700 for display, 600 for headings, 400 for body — clean separation with no ambiguous weights.
- **Tight display, relaxed body**: Display text tracks tight (-0.025em) for density and authority; body text tracks normal or slightly positive for sustained readability.
- **Mono for money**: Any dollar amount, parcel ID, coordinate, percentage, or financial metric uses JetBrains Mono with `"tnum"` — this signals "precision data" vs. narrative text.
- **No italic abuse**: Italics are used only for legal citations and property addresses inside prose — never for emphasis (use weight instead).
- **Color carries hierarchy**: On dark surfaces, primary text is `#F8FAFC` (slate-50), secondary is `#94A3B8` (slate-400), tertiary is `#64748B` (slate-500). Never use opacity for text hierarchy — alpha-blended text renders poorly on dark backgrounds.

## 4. Component Stylings

### Buttons

**Primary (Amber)**
- Background: `#F59E0B`
- Text: `#020617` (void — dark text on bright surface)
- Padding: 10px 20px
- Radius: 6px
- Font: Inter 14px weight 600, letter-spacing 0.01em
- Hover: `#D97706` background
- Active: `#B45309` background, scale(0.98)
- Focus: `2px solid #F59E0B` outline, 2px offset
- Use: Primary CTA ("Place Bid", "Start Free", "Upgrade", "Analyze")

**Secondary (Navy)**
- Background: `#1E3A5F`
- Text: `#F8FAFC`
- Padding: 10px 20px
- Radius: 6px
- Border: `1px solid rgba(30, 58, 95, 0.5)`
- Hover: `#172D4A` background
- Use: Secondary actions ("View Details", "Export", "Filter")

**Ghost**
- Background: transparent
- Text: `#94A3B8`
- Padding: 10px 20px
- Radius: 6px
- Border: `1px solid #1E293B`
- Hover: `rgba(30, 58, 95, 0.2)` background, text brightens to `#F8FAFC`
- Use: Tertiary actions ("Cancel", "Reset", "Skip")

**Danger**
- Background: `rgba(239, 68, 68, 0.15)`
- Text: `#EF4444`
- Padding: 10px 20px
- Radius: 6px
- Border: `1px solid rgba(239, 68, 68, 0.3)`
- Hover: `rgba(239, 68, 68, 0.25)` background
- Use: Destructive actions ("Remove Bid", "Delete")

### Cards & Containers

**Standard Card**
- Background: `#1E3A5F`
- Border: `1px solid rgba(30, 58, 95, 0.4)`
- Radius: 8px
- Padding: 24px
- Shadow: `rgba(0, 0, 0, 0.3) 0px 10px 30px -10px, rgba(2, 6, 23, 0.5) 0px 5px 15px -5px`
- Hover: border brightens to `rgba(245, 158, 11, 0.3)` (amber hint)

**Elevated Card (Featured Property / Active Auction)**
- Background: `linear-gradient(135deg, #1E3A5F 0%, #172D4A 100%)`
- Border: `1px solid rgba(245, 158, 11, 0.2)`
- Radius: 8px
- Shadow: `rgba(0, 0, 0, 0.4) 0px 20px 40px -15px, rgba(245, 158, 11, 0.05) 0px 0px 30px`
- Use: Featured auctions, BID-rated properties, premium content

**Surface Card (Nested)**
- Background: `#0F172A`
- Border: `1px solid #1E293B`
- Radius: 6px
- Shadow: none (flat within parent card)
- Use: Sub-panels within cards, nested data sections

**Glass Panel (Map Overlay)**
- Background: `rgba(2, 6, 23, 0.85)`
- Border: `1px solid rgba(30, 58, 95, 0.3)`
- Radius: 8px
- Backdrop: `blur(12px)`
- Use: Map info panels, floating controls, choropleth legend

### Badges / Status Indicators

**BID (Strong Buy)**
- Background: `rgba(16, 185, 129, 0.15)`
- Text: `#10B981`
- Border: `1px solid rgba(16, 185, 129, 0.3)`
- Padding: 2px 8px
- Radius: 4px
- Font: JetBrains Mono 11px weight 600, uppercase, letter-spacing 0.05em

**REVIEW (Evaluate)**
- Background: `rgba(245, 158, 11, 0.15)`
- Text: `#F59E0B`
- Border: `1px solid rgba(245, 158, 11, 0.3)`
- Same structure as BID

**SKIP (Pass)**
- Background: `rgba(100, 116, 139, 0.15)`
- Text: `#64748B`
- Border: `1px solid rgba(100, 116, 139, 0.2)`
- Same structure as BID

**ACTIVE (Live Auction)**
- Background: `rgba(239, 68, 68, 0.15)`
- Text: `#EF4444`
- Border: `1px solid rgba(239, 68, 68, 0.3)`
- Animated: subtle pulse glow every 2s
- Same structure as BID

### Data Tables

- Header row: `#0F172A` background, `#94A3B8` text, JetBrains Mono 11px uppercase weight 500, letter-spacing 0.05em
- Body row: `transparent` background, `#F8FAFC` text (primary cols), `#94A3B8` (secondary cols)
- Alternating: every even row `rgba(30, 58, 95, 0.08)`
- Hover: `rgba(30, 58, 95, 0.15)` background
- Selected: `rgba(245, 158, 11, 0.1)` background, left border `2px solid #F59E0B`
- Border between rows: `1px solid #1E293B`
- Dollar amounts: JetBrains Mono, `"tnum"`, right-aligned, `#F59E0B` if positive ROI, `#EF4444` if negative
- Parcel IDs: JetBrains Mono, `#94A3B8`, left-aligned

### Inputs & Forms

- Background: `#0F172A`
- Border: `1px solid #1E293B`
- Radius: 6px
- Padding: 10px 14px
- Text: `#F8FAFC`, Inter 14px weight 400
- Placeholder: `#64748B`
- Focus: `1px solid #F59E0B`, `0 0 0 3px rgba(245, 158, 11, 0.15)` ring
- Label: `#94A3B8`, Inter 13px weight 500, margin-bottom 6px
- Error: border `1px solid #EF4444`, helper text `#EF4444` 13px

### Navigation

- Background: `rgba(2, 6, 23, 0.9)`
- Backdrop: `blur(12px) saturate(180%)`
- Border bottom: `1px solid #1E293B`
- Height: 56px
- Logo: BidDeed.AI or ZoneWise.AI wordmark, left-aligned
- Links: Inter 14px weight 500, `#94A3B8`, hover `#F8FAFC`, active `#F59E0B`
- CTA: Amber primary button, right-aligned
- Mobile: hamburger icon, `#94A3B8`, 44px tap target

### Map Components (ZoneWise-specific)

**Choropleth Legend**
- Glass panel overlay, bottom-left
- Gradient bar: 5-stop from `#020617` (low) through `#1E3A5F` to `#F59E0B` (high)
- Labels: JetBrains Mono 11px, `#94A3B8`
- Title: Inter 13px weight 600, `#F8FAFC`

**Property Pin**
- Default: `#1E3A5F` fill, `#F8FAFC` stroke, 24px
- BID: `#10B981` fill
- REVIEW: `#F59E0B` fill
- SKIP: `#64748B` fill
- Selected: 2px `#F59E0B` ring, scale(1.2) with 200ms ease

**Info Panel**
- Glass panel, max-width 360px
- Property photo: radius 6px, aspect 16:9
- Address: Inter 16px weight 600, `#F8FAFC`
- Key metrics row: JetBrains Mono 14px, grid of label/value pairs
- Shapira Score: JetBrains Mono 20px weight 700, color by rating (BID/REVIEW/SKIP)

## 5. Layout Principles

### Spacing System
- Base unit: 4px
- Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128
- Component internal: 8-16px
- Component gaps: 16-24px
- Section padding: 64-96px vertical, 16-64px horizontal (responsive)

### Grid & Container
- Max content width: 1280px, centered with auto margins
- Dashboard: 12-column grid, 24px gap
- Landing page: max 1080px for prose content, full-width for hero/map sections
- Sidebar: 280px fixed, collapsible to 64px icon rail on mobile
- Map view: full-viewport with glass panel overlays

### Whitespace Philosophy
- **Data density over decoration**: Auction data is inherently complex — the layout prioritizes scan-ability over visual breathing room. Tables are tight, cards are compact, whitespace exists to separate functional groups, not for aesthetic padding.
- **Progressive disclosure**: The default view shows summary metrics; expanding a row reveals full detail. This prevents the "wall of data" problem without hiding information behind extra clicks.
- **Map-first on ZoneWise**: The map is always the largest element. Panels, filters, and data tables are overlaid or docked to edges, never competing for primary viewport space.
- **Dark section rhythm**: On landing pages, sections alternate between void (`#020617`) and navy (`#1E3A5F`) backgrounds, creating depth layers that guide scrolling without introducing arbitrary color.

### Border Radius Scale
- Micro (2px): Inline badges, tiny status dots
- Small (4px): Table cells, compact badges, inner elements
- Standard (6px): Buttons, inputs, nested cards
- Medium (8px): Cards, panels, modals
- Large (12px): Hero cards, featured sections, map overlays
- Never pill (9999px): Pill shapes are explicitly prohibited — they read as consumer/playful, not institutional

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Sunken (Level -1) | Inset: `inset 0 1px 3px rgba(0,0,0,0.3)` | Input fields, embedded panels |
| Flat (Level 0) | No shadow | Page background, inline elements |
| Subtle (Level 1) | `rgba(0,0,0,0.2) 0px 2px 8px -2px` | Hover hints, subtle card lift |
| Standard (Level 2) | `rgba(0,0,0,0.3) 0px 10px 30px -10px, rgba(2,6,23,0.5) 0px 5px 15px -5px` | Cards, panels, dropdowns |
| Elevated (Level 3) | `rgba(0,0,0,0.4) 0px 20px 40px -15px, rgba(2,6,23,0.6) 0px 10px 25px -10px` | Modals, floating panels, popovers |
| Amber Glow | `rgba(245,158,11,0.05) 0px 0px 30px` | Featured/active auction cards |
| Focus Ring | `0 0 0 3px rgba(245,158,11,0.15)` | Keyboard focus on interactive elements |

**Shadow Philosophy**: On a dark canvas (`#020617`), traditional gray shadows are invisible. Everest's shadow system uses concentrated black shadows with large negative spread values to keep shadows tight and vertical — elements lift straight up rather than casting wide penumbras. The amber glow on featured cards is the only colored shadow in the system, used exclusively to mark the current highest-value opportunity. This restraint ensures the glow carries real signal weight rather than being decorative noise.

## 7. Do's and Don'ts

### Do
- Use `#020617` (void) as the page background — it's the canvas everything lives on
- Use `#1E3A5F` (navy) for card and panel surfaces — never white cards on dark backgrounds
- Use `#F59E0B` (amber) exclusively for interactive elements and key data — it's the signal color
- Keep border-radius between 4px-8px — conservative, institutional, never playful
- Use JetBrains Mono with `"tnum"` for every dollar amount, percentage, and parcel ID
- Apply `font-feature-settings: "cv01"` on Inter to disambiguate 1/l/I in data contexts
- Use opacity-based surfaces (`rgba(30,58,95,0.15)`) for selected/hover states — never solid color swaps
- Pair BidDeed.AI and ZoneWise.AI branding together — they are one ecosystem
- Test all text contrast ratios: primary text (`#F8FAFC`) on navy (`#1E3A5F`) must exceed 4.5:1 WCAG AA
- Use semantic badges (BID/REVIEW/SKIP/ACTIVE) consistently across both products

### Don't
- Don't use pure black (`#000000`) for backgrounds — always `#020617` or darker navy variants
- Don't use white (`#ffffff`) as a card/panel surface in dark mode — use navy scale
- Don't use amber for large surface fills — it's an accent, not a surface color
- Don't use pill-shaped buttons (border-radius: 9999px) — they undermine institutional credibility
- Don't use gradients on buttons — flat solid fills only (gradients are reserved for data viz and hero decorations)
- Don't use more than 5 colors in a single chart — the palette is designed for 5 series max
- Don't use colored text for emphasis in body copy — use weight 600 Inter instead
- Don't reference "foreclosures" and "tax deeds" separately — always pair them together per brand rules
- Don't use opacity/alpha for text color hierarchy — use the explicit slate scale values
- Don't round map pins or data markers beyond 4px — geometric precision signals analytical rigor

## 8. Responsive Behavior

### Breakpoints
| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile | <640px | Single column, sidebar collapses to bottom sheet, map full-screen with sheet overlay |
| Tablet | 640-1024px | 2-column grid, sidebar as slide-over, map with side panel |
| Desktop | 1024-1440px | Full layout, sidebar visible, 12-col grid |
| Large Desktop | >1440px | Max-width 1280px centered, generous margins, split-screen map+table |

### Touch Targets
- All interactive elements: minimum 44px × 44px touch target
- Map pins: 44px tap zone regardless of visual pin size (24px)
- Table rows: minimum 48px height for comfortable row selection
- Buttons: minimum padding 10px 20px, never smaller than 36px height
- Spacing between adjacent interactive elements: minimum 8px

### Collapsing Strategy
- Hero: 56px display → 36px on tablet → 28px on mobile, weight maintained at 700
- Navigation: horizontal links → hamburger with slide-out panel
- Dashboard sidebar: 280px → icon rail (64px) → bottom sheet
- Data tables: all columns → priority columns + horizontal scroll → card layout (stacked key-value pairs)
- Map + table split view: side-by-side → map full + table as pull-up sheet
- Section padding: 96px → 64px → 40px vertical
- Card grids: 3-col → 2-col → single column stacked
- Choropleth legend: bottom-left panel → collapsed toggle

### Image Behavior
- Property photos: maintain 16:9 aspect, `object-fit: cover`, radius 6px at all sizes
- Map tiles: full-bleed, no border-radius
- Charts: responsive width, fixed minimum height (200px mobile, 300px desktop)
- Logo: SVG, scales from 32px (mobile nav) to 40px (desktop nav)

## 9. Agent Prompt Guide

### Quick Color Reference
- Primary CTA: Amber (`#F59E0B`)
- CTA Hover: Amber Dark (`#D97706`)
- CTA Text: Void (`#020617`)
- Background: Void (`#020617`)
- Card Surface: Navy (`#1E3A5F`)
- Nested Surface: Slate 900 (`#0F172A`)
- Primary Text: Slate 50 (`#F8FAFC`)
- Secondary Text: Slate 400 (`#94A3B8`)
- Tertiary Text: Slate 500 (`#64748B`)
- Border: Slate 800 (`#1E293B`)
- Link: Amber (`#F59E0B`)
- Success: Emerald (`#10B981`)
- Danger: Red (`#EF4444`)
- Data Mono: JetBrains Mono

### Example Component Prompts
- "Create a hero section on void (#020617) background. Headline at 48px Inter weight 700, line-height 1.08, letter-spacing -0.02em, color #F8FAFC. Subtitle at 18px Inter weight 400, line-height 1.6, color #94A3B8. Amber CTA button (#F59E0B bg, #020617 text, 6px radius, 10px 20px padding) and ghost button (transparent, 1px solid #1E293B, #94A3B8 text, 6px radius)."
- "Design an auction card: #1E3A5F background, 1px solid rgba(30,58,95,0.4) border, 8px radius. Shadow: rgba(0,0,0,0.3) 0px 10px 30px -10px. Title (address) at 16px Inter weight 600, #F8FAFC. Parcel ID at 14px JetBrains Mono, #94A3B8. Key metrics (Est. Value, Opening Bid, Shapira Score) in a 3-column grid, values in JetBrains Mono 14px weight 500, amber (#F59E0B) for the score. BID/REVIEW/SKIP badge top-right."
- "Build a data table: header row #0F172A, JetBrains Mono 11px uppercase #94A3B8. Body rows on transparent, 1px solid #1E293B borders. Dollar amounts right-aligned JetBrains Mono 14px, #10B981 for profit, #EF4444 for loss. Selected row: rgba(245,158,11,0.1) background, 2px solid #F59E0B left border."
- "Create navigation: sticky, rgba(2,6,23,0.9) background, backdrop-filter blur(12px). Inter 14px weight 500 links, #94A3B8 default, #F8FAFC hover, #F59E0B active. Amber CTA 'Start Free' right-aligned. 56px height. 1px solid #1E293B bottom border."
- "Design a Shapira Score display: large central number in JetBrains Mono 48px weight 700. Color: #10B981 for BID (70-100), #F59E0B for REVIEW (40-69), #64748B for SKIP (0-39). Label below: Inter 13px weight 500 uppercase #94A3B8. Container: #0F172A background, 8px radius, 32px padding."

### Iteration Guide
1. Always use Inter with `font-feature-settings: "cv01"` — the alternate 1 glyph prevents ambiguity in parcel/financial data
2. Weight 700 for display headings, 600 for section heads and buttons, 400 for body — never use weight 300 (too light for data-heavy UIs)
3. Shadow formula for cards: `rgba(0,0,0,0.3) 0px Y1 B1 -S1, rgba(2,6,23,0.5) 0px Y2 B2 -S2` where Y1/B1 are larger (far) and Y2/B2 are smaller (near)
4. Text hierarchy uses explicit colors, not opacity: `#F8FAFC` (primary) → `#94A3B8` (secondary) → `#64748B` (tertiary)
5. Amber (`#F59E0B`) is reserved for interactivity and key data — never use it for decorative fills or backgrounds
6. All financial numbers use JetBrains Mono with `"tnum"` and right-alignment
7. Card surfaces are `#1E3A5F` on `#020617` background — the layered navy creates depth without shadows
8. Border-radius stays 4px-8px — conservative rounding projects institutional credibility
9. Map components use glass panels: `rgba(2,6,23,0.85)` with `backdrop-filter: blur(12px)`
10. BidDeed.AI (dense dashboard) and ZoneWise.AI (map-first spatial) share this exact token set — only layout density differs
