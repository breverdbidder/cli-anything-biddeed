#!/usr/bin/env python3
"""
CompetitorLens Sprint 2 — AUTOLOOP Eval Runner
Tests assertions 26-42 from eval.json (analyze, generate, validate stages).

Usage:
    python harnesses/competitorlens/eval/run_eval_s2.py

Pass rate must be 100% before Sprint 2 is marked DONE.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add harness to path
HARNESS_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(HARNESS_DIR))

# No real API keys in tests
os.environ.pop("FIRECRAWL_API_KEY", None)
os.environ.pop("DEEPSEEK_API_KEY", None)
os.environ.pop("SUPABASE_SERVICE_KEY", None)
os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)

RESULTS = []


def assert_true(assertion_id: int, description: str, actual: bool, notes: str = ""):
    status = "PASS" if actual else "FAIL"
    RESULTS.append({
        "id": assertion_id,
        "status": status,
        "assertion": description,
        "notes": notes,
    })
    icon = "✓" if actual else "✗"
    print(f"  {icon} [{assertion_id:02d}] {description}")
    if not actual and notes:
        print(f"       FAIL — {notes}")


# ─── Shared fixtures ──────────────────────────────────────────────────────────

VALID_BLUEPRINT = {
    "competitor": "PropertyOnion",
    "component_type": "calendar",
    "sections": [{"name": "header", "type": "navigation", "elements": ["logo", "menu"], "position": "top"}],
    "navigation": {"type": "top-bar", "items": ["Search", "About"], "hasAuth": True},
    "filters": [{"name": "county", "type": "dropdown", "options": ["Brevard"], "position": "top"}],
    "dataDisplayPatterns": ["calendar-grid"],
    "ctaPlacement": {"primary": "top-right register button", "secondary": "per-property view"},
    "colorScheme": {"primary": "#ff6b00", "background": "#f5f5f5"},
    "layoutType": "calendar",
    "mobileApproach": "responsive",
    "keyUXPatterns": ["calendar-grid"],
    "dataFields": ["address", "sale_date", "opening_bid"],
    "interactiveFeatures": ["calendar navigation"],
    "url": "https://propertyonion.com/property_search/Brevard%20county?view_type=calendar",
    "screenshot": "",
    "crawled_at": datetime.now(timezone.utc).isoformat(),
    "extractedAt": datetime.now(timezone.utc).isoformat(),
}

VALID_UX_REPORT = {
    "competitor": "PropertyOnion",
    "component_type": "calendar",
    "analyzed_at": datetime.now(timezone.utc).isoformat(),
    "summary": "PropertyOnion presents a clean calendar grid with county filtering and sale type color coding.",
    "navigation_flow": {
        "type": "top-bar",
        "description": "Simple top navigation with county selector as primary control",
        "steps": ["Select county", "View calendar", "Click date", "Browse listings"],
        "pain_points": ["No ML scoring", "No lien warnings"],
        "biddeed_opportunity": 5,
    },
    "filter_mechanics": {
        "filters": [
            {"name": "county", "type": "dropdown", "position": "top", "default_value": None, "ux_notes": "67 FL counties"}
        ],
        "filter_count": 1,
        "filter_layout": "horizontal-bar",
        "biddeed_opportunity": 4,
    },
    "data_display": {
        "primary_pattern": "calendar-grid",
        "secondary_patterns": ["property-cards"],
        "density": "medium",
        "data_fields_shown": ["auction_date", "property_count", "sale_type"],
        "visual_hierarchy": "Calendar date is primary, property count secondary",
        "biddeed_opportunity": 5,
    },
    "cta_analysis": {
        "primary_cta": {"text": "Register to bid", "position": "top-right", "style": "button"},
        "secondary_ctas": [{"text": "View details", "position": "per-listing"}],
        "conversion_pattern": "Registration gate before bidding details",
        "biddeed_opportunity": 3,
    },
    "mobile_approach": {
        "type": "responsive",
        "breakpoints": ["sm", "md", "lg"],
        "touch_targets": "adequate",
        "notes": "Calendar collapses to list on mobile",
        "biddeed_opportunity": 2,
    },
    "key_patterns": [
        {
            "name": "auction-calendar-grid",
            "description": "7-column calendar grid showing auctions per day with count badges",
            "adapt_for_biddeed": "Add ML score overlay and BID/REVIEW/SKIP color coding per date",
            "priority": "high",
        }
    ],
    "biddeed_enhancements": [
        "ML probability score overlay per auction date",
        "BID/REVIEW/SKIP color coding per property",
        "ZoneWise zoning data per parcel",
        "Lien priority warning badges",
        "Max bid calculation shown inline",
    ],
    "reusable_patterns_for_library": [
        {
            "pattern_name": "auction-calendar-grid",
            "description": "Calendar grid with auction count per date",
            "implementation_notes": "Use CSS grid 7 columns, badge per day",
        }
    ],
    "source_blueprint_url": "https://propertyonion.com/property_search/Brevard%20county?view_type=calendar",
}

MINIMAL_JSX = """import { useState, useEffect } from 'react';

export default function AuctionCalendar() {
  const [data, setData] = useState([]);
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/rest/v1/auctions_free`, {
      headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY }
    }).then(r => r.json()).then(setData);
  }, []);
  return (
    <div className="bg-[#020617] text-slate-50 font-[Inter]">
      <h1 className="text-[#1E3A5F]">Auctions</h1>
      <button className="bg-[#F59E0B] text-[#020617]">View deals</button>
    </div>
  );
}
"""

OFF_BRAND_JSX = """import { useState } from 'react';
export default function BadComponent() {
  return (
    <div className="bg-purple text-white" style={{ background: '#7C3AED' }}>
      <button className="bg-blue-500">Click me</button>
    </div>
  );
}
"""


# ═══════════════════════════════════════════════════════════════
# ANALYZE STAGE TESTS (26–30)
# ═══════════════════════════════════════════════════════════════
print("\n── STAGE: analyze ───────────────────────────────────────")

from analyze import analyze_blueprint, validate_report, extract_patterns_for_library

# 26. validate_report catches missing fields
incomplete_report = {"competitor": "PropertyOnion"}
missing = validate_report(incomplete_report)
assert_true(26, "validate_report returns non-empty list for incomplete report",
            len(missing) > 0)

# 27. validate_report passes complete report
missing_complete = validate_report(VALID_UX_REPORT)
assert_true(27, "validate_report returns empty list for complete UXPatternReport",
            len(missing_complete) == 0)

# 28. analyze_blueprint returns error for empty input
result28 = analyze_blueprint({})
assert_true(28, "analyze_blueprint returns error dict for empty blueprint",
            isinstance(result28, dict) and "error" in result28)

# 29. analyze_blueprint returns error for blueprint with error key
error_blueprint = {"error": "upstream failure", "url": "https://test.com"}
result29 = analyze_blueprint(error_blueprint)
assert_true(29, "analyze_blueprint returns error dict when blueprint has error key",
            isinstance(result29, dict) and "error" in result29)

# 30. extract_patterns_for_library returns list
patterns = extract_patterns_for_library(VALID_UX_REPORT)
assert_true(30, "extract_patterns_for_library returns a list",
            isinstance(patterns, list))


# ═══════════════════════════════════════════════════════════════
# GENERATE STAGE TESTS (31–34)
# ═══════════════════════════════════════════════════════════════
print("\n── STAGE: generate ──────────────────────────────────────")

from generate import (
    generate_jsx, _strip_markdown_fences, _validate_jsx_structure, _component_name_from_report
)

# 31. _strip_markdown_fences removes ```jsx fences
fenced = "```jsx\nimport React from 'react';\nexport default function Foo() { return <div />; }\n```"
stripped = _strip_markdown_fences(fenced)
assert_true(31, "_strip_markdown_fences removes ```jsx ... ``` wrappers",
            "```" not in stripped and "import React" in stripped)

# 32. _validate_jsx_structure catches missing export default
no_export = "import React from 'react';\nfunction Foo() { return (<div />); }\n"
validation = _validate_jsx_structure(no_export)
assert_true(32, "_validate_jsx_structure returns valid=False when export default missing",
            not validation["valid"])

# 33. _component_name_from_report returns correct name
report_calendar = {"component_type": "calendar"}
name = _component_name_from_report(report_calendar)
assert_true(33, "_component_name_from_report returns 'AuctionCalendar' for calendar type",
            name == "AuctionCalendar")

# 34. generate_jsx returns error for empty report
result34 = generate_jsx({})
assert_true(34, "generate_jsx returns error dict for empty report",
            isinstance(result34, dict) and "error" in result34)


# ═══════════════════════════════════════════════════════════════
# VALIDATE / BRANDGUARD TESTS (35–42)
# ═══════════════════════════════════════════════════════════════
print("\n── STAGE: validate (BrandGuard) ─────────────────────────")

from validate import validate_jsx, validate_file

# 35. Brand-compliant JSX → PASS
result35 = validate_jsx(MINIMAL_JSX)
assert_true(35, "validate_jsx returns PASS for brand-compliant JSX",
            result35["status"] == "PASS",
            f"Got {result35['status']}: {result35.get('summary', '')}")

# 36. Off-brand JSX (purple) → BLOCK
result36 = validate_jsx(OFF_BRAND_JSX)
assert_true(36, "validate_jsx returns BLOCK for JSX with purple color violation",
            result36["status"] == "BLOCK",
            f"Got {result36['status']}, violations: {result36.get('violations', [])}")

# 37. Empty content → BLOCK
result37 = validate_jsx("")
assert_true(37, "validate_jsx returns BLOCK for empty JSX content",
            result37["status"] == "BLOCK")

# 38. AuctionCalendar.jsx passes with score >= 90
auction_cal_path = HARNESS_DIR / "output" / "AuctionCalendar.jsx"
result38 = validate_file(str(auction_cal_path))
assert_true(38, "AuctionCalendar.jsx passes BrandGuard with score >= 90",
            result38["status"] == "PASS" and result38["score"] >= 90,
            f"Status={result38['status']}, Score={result38['score']}")

# 39. BrandGuard detects missing navy as violation
no_navy_jsx = """import { useState } from 'react';
export default function NoNavy() {
  const [d, setD] = useState([]);
  return (
    <div className="bg-[#020617] font-[Inter]">
      <button className="bg-[#F59E0B] text-[#020617]">CTA</button>
    </div>
  );
}
"""
result39 = validate_jsx(no_navy_jsx)
has_navy_violation = any(
    "Navy" in v.get("description", "") or "1E3A5F" in v.get("description", "")
    for v in result39.get("violations", [])
)
assert_true(39, "BrandGuard detects missing navy (#1E3A5F) as violation",
            result39["status"] == "BLOCK" or has_navy_violation,
            f"Status={result39['status']}, violations={result39.get('violations', [])}")

# 40. AuctionCalendar.jsx earns at least 4 bonus features
assert_true(40, "AuctionCalendar.jsx earns at least 4 bonus feature points",
            len(result38.get("bonus_features", [])) >= 4,
            f"Bonus features: {result38.get('bonus_features', [])}")

# 41. validate_file returns BLOCK for nonexistent file
result41 = validate_file("/tmp/this_file_does_not_exist_competitorlens.jsx")
assert_true(41, "validate_file returns BLOCK when file does not exist",
            result41["status"] == "BLOCK")

# 42. BrandGuard detects missing Supabase integration as violation
no_supabase_jsx = """import { useState } from 'react';
export default function StaticOnlyComponent() {
  return (
    <div className="bg-[#020617] font-[Inter]">
      <h1 className="text-[#1E3A5F]">Hello</h1>
      <button className="bg-[#F59E0B] text-[#020617]">CTA</button>
    </div>
  );
}
"""
result42 = validate_jsx(no_supabase_jsx)
has_supabase_violation = any(
    "Supabase" in v.get("description", "") or "hooks" in v.get("description", "")
    for v in result42.get("violations", [])
)
assert_true(42, "BrandGuard detects missing Supabase integration as violation",
            result42["status"] == "BLOCK" or has_supabase_violation,
            f"Status={result42['status']}, violations={result42.get('violations', [])}")


# ═══════════════════════════════════════════════════════════════
# RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════
print("\n" + "═" * 55)
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
total = len(RESULTS)

print(f"CompetitorLens Sprint 2 Eval: {passed}/{total} passed")

if failed:
    print(f"\nFAILED ({failed}):")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"  [{r['id']:02d}] {r['assertion']}")
            if r["notes"]:
                print(f"        {r['notes']}")
    sys.exit(1)
else:
    print("ALL ASSERTIONS PASSED ✓")
    print("Sprint 2 analyze + generate + validate stages are solid.")
    sys.exit(0)
