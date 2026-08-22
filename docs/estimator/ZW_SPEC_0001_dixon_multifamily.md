# TECHNICAL SPECIFICATION — CONCEPTUAL STAGE
## Multifamily Development, 620 Dixon Blvd, Cocoa, FL
**Doc ID:** ZW-SPEC-0001 · **Rev:** A · **Date:** 2026-08-21
**Status:** SAMPLE FIXTURE — site/zoning data VERIFIED; program and performance figures are ILLUSTRATIVE SAMPLE VALUES for estimator testing, not a real project commitment.

This document is the "user-uploaded Technical Specification" input to the ZoneWise Conceptual Estimator (see ZONEWISE_ESTIMATOR_METAPROMPT.md). It defines the section structure the ingestion step (INGEST → CLASSIFY → SCOPE) must be able to parse. Real client specs may run hundreds of pages; the estimator must handle this same structure at any length.

---

## 1. PROJECT IDENTIFICATION
- Project name: Dixon Multifamily (working title)
- Owner/Developer: Everest Capital Development
- Delivery method: Design-Build (assumed at conceptual stage)
- Estimate class: Conceptual / Class 4 (AACE), ±30-50% expected accuracy
- Currency: USD · Tax basis: FL sales tax on materials; no VAT

## 2. SITE DATA (VERIFIED — ZoneWise GIS)
- Parcel: 24 3621-BM-*-3, Brevard County (co_no 15), Cocoa FL
- Site area: 4.96 acres (216,058 sf)
- Zoning: RU-1-7 (verified GIS zoning, trust_level=verified)
- Utilities: central water/sewer status per ZoneWise parcel_utilities layer; where UNDETERMINED, the estimator carries a LOW-confidence allowance line, not an assumed connection
- Geotech: no report available — foundation lines to be flagged LOW confidence with "geotech pending" source note
- Flood/environmental: to be confirmed; carry allowance lines only if a sourced basis exists

## 3. ZONING ENVELOPE (authoritative source: zw_zoning fields)
The estimator must pull zoning_max_ht, zoning_min_lot, zoning_setbacks, zoning_permitted from ZoneWise for this parcel and treat THOSE values as governing. Any program element below that conflicts with the verified envelope must be flagged in the workbook Summary as a scope exception — not silently priced.

## 4. PROGRAM (ILLUSTRATIVE SAMPLE VALUES)
- Building type: garden-style multifamily, wood frame over slab-on-grade
- Unit count: per MassingEngine output for this parcel (estimator consumes the engine's number; the figure 48 units used in prior mockups is a sample, not a spec requirement)
- Unit mix (sample): 40% 1BR/1BA (~700 sf), 45% 2BR/2BA (~950 sf), 15% 3BR/2BA (~1,150 sf)
- Stories: 2-3, subject to zoning_max_ht
- Parking: surface, ratio per Cocoa LDC requirement for the verified zone (estimator sources the ratio; if not sourced, LOW confidence)
- Amenity: leasing office + mail kiosk (~1,200 sf), no pool in base scope

## 5. SCOPE OF WORK BY DIVISION
Each division below maps to zw_cost_standard trades. Quantities derive from site area, massing output, and unit mix. Every priced line requires a cost_standard row id in the Source column.

**Div 02 — Sitework & Earthwork:** clearing/grubbing full site; rough grading; stormwater per SJRWMD requirements (allowance if unengineered); site utilities trenching.
**Div 03 — Concrete:** slab-on-grade per building footprint; sidewalks; dumpster pads.
**Div 04-06 — Structure & Envelope:** wood frame; truss roof, architectural shingle; fiber-cement + stucco mix exterior; impact-rated windows (FL wind-borne debris region — code-driven, HIGH confidence on requirement, cost per sourced rate).
**Div 07-09 — Interiors:** Level 2 finish standard (LVP living areas, carpet bedrooms, quartz counters, shaker cabinets); drywall/paint throughout.
**Div 21-23 — MEP:** individual split-system HVAC per unit; electric water heaters; NFPA 13R sprinklers (3+ story trigger — estimator must check story count and include/exclude with a code citation).
**Div 26 — Electrical:** per-unit metering; site lighting.
**Div 31-33 — Site Improvements:** asphalt parking + drives; landscaping to Cocoa LDC minimum; site signage allowance.

## 6. QUALITY & PERFORMANCE STANDARDS
- Florida Building Code, current edition; Energy Code compliance path prescriptive
- Wind design per ASCE 7, Brevard County exposure — cost impact must be carried in envelope lines
- No LEED/green certification in base scope

## 7. EXCLUSIONS (do not price)
Land cost; financing/carry; impact fees UNLESS a sourced Brevard/Cocoa fee schedule row exists in zw_cost_standard (then include, HIGH confidence); FF&E; marketing; developer fee; offsite improvements beyond utility connection points.

## 8. ESTIMATOR INSTRUCTIONS (binds the skill)
1. Cross-check every Section 4 program value against the verified zoning envelope (Section 3). Conflicts → Summary tab exceptions list.
2. Quantities: show derivation basis in Source (e.g., "216,058 sf site × clearing rate", "MassingEngine units × sf/unit").
3. Costs: zw_cost_standard rows only. No row → cost NULL, confidence LOW, Source = "NO SOURCED RATE".
4. Confidence rubric: HIGH = sourced rate + measured/verified quantity; MED = sourced rate + derived quantity; LOW = either missing.
5. Contingency: design contingency 15% (Class 4 standard, cite AACE class), escalation excluded at conceptual stage — state so on Summary.
