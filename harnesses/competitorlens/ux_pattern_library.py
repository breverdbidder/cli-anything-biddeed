#!/usr/bin/env python3
"""
CompetitorLens — Stage 7: UX Pattern Library
Extracts reusable patterns from competitor analyses and stores in ux_pattern_library table.

Patterns from both PropertyOnion and Foreclosure.com are consolidated here.

Usage:
    python3 ux_pattern_library.py --populate   # Insert all patterns to Supabase
    python3 ux_pattern_library.py --list       # Print all patterns
    python3 ux_pattern_library.py --export /tmp/patterns.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from supabase_client import save_ux_pattern, get_pattern_library

# ─── PATTERN DEFINITIONS ──────────────────────────────────────────────────────

UX_PATTERNS = [
    # ── From PropertyOnion ────────────────────────────────────────────────────
    {
        "pattern_name": "auction-calendar-grid",
        "source_competitor": "PropertyOnion",
        "description": (
            "Monthly/weekly calendar grid showing auction dates. Each cell displays "
            "property count for that day. Clicking a date opens a modal list of properties "
            "scheduled for that auction date. Color-coded by sale type."
        ),
        "implementation_notes": (
            "BidDeed.AI enhancement: overlay ML deal score on date cell (e.g. '3 props · BID 82'). "
            "Use Supabase multi_county_auctions grouped by sale_date. "
            "Color intensity maps to avg bid_score for the day. "
            "See AuctionCalendar.jsx for reference implementation."
        ),
        "component_type": "calendar",
        "reuse_count": 1,
        "tags": ["calendar", "auction", "data-display", "date-grouped"],
    },
    {
        "pattern_name": "county-multi-select",
        "source_competitor": "PropertyOnion",
        "description": (
            "Dropdown or searchable multi-select for filtering by Florida county. "
            "PropertyOnion supports all 67 FL counties. Defaults to user's last-used county."
        ),
        "implementation_notes": (
            "Use FL_COUNTIES const array. Default to 'Brevard' for BidDeed.AI (primary market). "
            "Store user preference in localStorage. "
            "Consider county_auction_config table for active county list."
        ),
        "component_type": "calendar",
        "reuse_count": 2,
        "tags": ["filter", "florida", "county", "multi-select"],
    },
    {
        "pattern_name": "sale-type-color-coding",
        "source_competitor": "PropertyOnion",
        "description": (
            "Color-coded badges distinguishing foreclosure types: "
            "Foreclosure (red/orange), Tax Deed (blue), REO (gray). "
            "Applied to calendar cells and property card headers."
        ),
        "implementation_notes": (
            "BidDeed.AI expands to: Foreclosure/MTG (orange), Tax Deed (navy), "
            "HOA (amber warning — senior mortgage risk), REO (slate). "
            "Add lien_status warning overlay for HOA cases."
        ),
        "component_type": "calendar",
        "reuse_count": 2,
        "tags": ["badge", "sale-type", "color-coding", "status"],
    },
    {
        "pattern_name": "calendar-list-view-toggle",
        "source_competitor": "PropertyOnion",
        "description": (
            "Toggle control switching between calendar grid view and chronological list view "
            "of the same auction data. Single state, two render modes."
        ),
        "implementation_notes": (
            "React useState('calendar' | 'list'). "
            "Persist preference in localStorage. "
            "List view: table with case_number, address, sale_date, opening_bid, bid_score."
        ),
        "component_type": "calendar",
        "reuse_count": 1,
        "tags": ["toggle", "view-switch", "calendar", "list"],
    },

    # ── From Foreclosure.com ──────────────────────────────────────────────────
    {
        "pattern_name": "multi-filter-search",
        "source_competitor": "Foreclosure.com",
        "description": (
            "Location + property type + price range + foreclosure stage filter panel "
            "in sidebar with live results update. Supports 5+ concurrent filter dimensions. "
            "Save search and email alerts per filter configuration."
        ),
        "implementation_notes": (
            "BidDeed.AI adds: Deal Score slider, Lien Status filter — two dimensions no "
            "competitor offers. Use Supabase .filter() chaining. "
            "React useReducer for filter state. "
            "Save search → Supabase saved_searches table (Sprint 4). "
            "See PropertySearchGrid.jsx FilterPanel component."
        ),
        "component_type": "search",
        "reuse_count": 1,
        "tags": ["filter", "sidebar", "search", "multi-dimension"],
    },
    {
        "pattern_name": "property-card-grid",
        "source_competitor": "Foreclosure.com",
        "description": (
            "3-column responsive photo card grid. Each card: property photo, "
            "address, price, beds/baths/sqft stats, foreclosure stage badge, "
            "days on market, save/bookmark icon."
        ),
        "implementation_notes": (
            "BidDeed.AI replaces photo (no image API yet) with ML score header band. "
            "Add: Max Bid, ARV, Lien status, Auction date with urgency badge. "
            "Remove investor-irrelevant: beds/baths/sqft for search results (keep in detail). "
            "CSS: grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4. "
            "See PropertySearchGrid.jsx PropertyCard component."
        ),
        "component_type": "search",
        "reuse_count": 1,
        "tags": ["card", "grid", "property", "responsive"],
    },
    {
        "pattern_name": "status-badge-system",
        "source_competitor": "Foreclosure.com",
        "description": (
            "Color-coded status badges on property cards indicating foreclosure stage. "
            "Foreclosure.com: Pre-Foreclosure (red), Auction (yellow), Bank-Owned (blue). "
            "Badges communicate passive stage information."
        ),
        "implementation_notes": (
            "BidDeed.AI replaces passive stage badges with action-oriented BID/REVIEW/SKIP. "
            "Stage info becomes secondary (smaller badge). "
            "Primary badge: emerald=BID, amber=REVIEW, red=SKIP with numeric score. "
            "This is the core UX differentiation vs all competitors. "
            "See getScoreBadge() in PropertySearchGrid.jsx and AuctionCalendar.jsx."
        ),
        "component_type": "search",
        "reuse_count": 2,
        "tags": ["badge", "status", "action-signal", "ml-score"],
    },
    {
        "pattern_name": "save-track-export",
        "source_competitor": "Foreclosure.com",
        "description": (
            "Save search configuration for re-use, track individual properties to watchlist, "
            "export current results to CSV. Email alerts for new matches per saved search."
        ),
        "implementation_notes": (
            "BidDeed.AI CSV export: implemented in PropertySearchGrid.jsx exportCSV(). "
            "Save search + watchlist: Sprint 4 — requires Supabase saved_searches table. "
            "Email alerts: Sprint 4 — Supabase Edge Function + Resend. "
            "Export includes ML score, max bid, lien status columns (competitor advantage)."
        ),
        "component_type": "search",
        "reuse_count": 2,
        "tags": ["save", "watchlist", "export", "alerts"],
    },
    {
        "pattern_name": "results-toolbar",
        "source_competitor": "Foreclosure.com",
        "description": (
            "Sticky toolbar above results showing: total count, sort dropdown, "
            "grid/list toggle, export button. Stays visible during scroll."
        ),
        "implementation_notes": (
            "BidDeed.AI adds: Deal Score sort option (unique differentiator). "
            "position: sticky top-0 with backdrop-blur. "
            "Show filter count badge when filters are active. "
            "See PropertySearchGrid.jsx toolbar section."
        ),
        "component_type": "search",
        "reuse_count": 1,
        "tags": ["toolbar", "sort", "view-toggle", "sticky"],
    },
    {
        "pattern_name": "map-cluster-view",
        "source_competitor": "Foreclosure.com",
        "description": (
            "Interactive map (Google Maps or Mapbox) showing property pins with "
            "geographic clustering. Cluster badges show count. "
            "Hover over cluster/pin for property preview tooltip."
        ),
        "implementation_notes": (
            "Deferred to Sprint 4. Use Mapbox GL JS. "
            "BidDeed.AI enhancement: cluster badge color maps to avg ML score in area. "
            "Green cluster = high deal area. Red cluster = skip area. "
            "Property preview tooltip: address + bid_score + opening_bid."
        ),
        "component_type": "map",
        "reuse_count": 0,
        "tags": ["map", "cluster", "mapbox", "geographic", "deferred"],
    },
]


def print_patterns():
    """Print all patterns in a readable format."""
    print(f"\n{'═' * 60}")
    print(f"  UX Pattern Library — {len(UX_PATTERNS)} patterns")
    print(f"{'═' * 60}\n")

    by_competitor = {}
    for p in UX_PATTERNS:
        c = p["source_competitor"]
        by_competitor.setdefault(c, []).append(p)

    for competitor, patterns in by_competitor.items():
        print(f"[{competitor}] — {len(patterns)} patterns\n")
        for p in patterns:
            print(f"  • {p['pattern_name']}")
            print(f"    {p['description'][:80]}...")
            print(f"    Tags: {', '.join(p.get('tags', []))}")
            print()


def populate_supabase() -> int:
    """Insert all patterns to ux_pattern_library. Returns count of successful inserts."""
    success = 0
    skipped = 0

    for pattern in UX_PATTERNS:
        record = {
            "pattern_name": pattern["pattern_name"],
            "source_competitor": pattern["source_competitor"],
            "description": pattern["description"],
            "implementation_notes": pattern["implementation_notes"],
            "component_type": pattern.get("component_type"),
            "reuse_count": pattern.get("reuse_count", 0),
            "tags": pattern.get("tags", []),
        }

        result = save_ux_pattern(record)

        if "error" in str(result):
            error_detail = result.get("detail", "") if isinstance(result, dict) else str(result)
            # 409 = duplicate, skip gracefully
            if "409" in str(result) or "duplicate" in error_detail.lower() or "unique" in error_detail.lower():
                print(f"[patterns] SKIP (exists): {pattern['pattern_name']}")
                skipped += 1
            else:
                print(f"[patterns] ERROR: {pattern['pattern_name']} — {result}")
        else:
            print(f"[patterns] SAVED: {pattern['pattern_name']} (ID: {result.get('id', '?')[:8]}...)")
            success += 1

    print(f"\n[patterns] Done: {success} saved, {skipped} skipped (already exist)")
    return success


def export_patterns(output_path: str):
    """Export all patterns to a JSON file."""
    now = datetime.now(timezone.utc).isoformat()
    export = {
        "generated_at": now,
        "version": "1.0",
        "total": len(UX_PATTERNS),
        "patterns": UX_PATTERNS,
    }
    with open(output_path, "w") as f:
        json.dump(export, f, indent=2)
    print(f"[patterns] Exported {len(UX_PATTERNS)} patterns to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UX Pattern Library — CompetitorLens")
    parser.add_argument("--populate", action="store_true", help="Insert patterns to Supabase")
    parser.add_argument("--list", action="store_true", help="Print all patterns")
    parser.add_argument("--export", metavar="PATH", help="Export patterns to JSON file")
    args = parser.parse_args()

    if args.list:
        print_patterns()
    elif args.populate:
        count = populate_supabase()
        print(f"\n✅ Pattern library populated: {count} new patterns")
    elif args.export:
        export_patterns(args.export)
    else:
        parser.print_help()
