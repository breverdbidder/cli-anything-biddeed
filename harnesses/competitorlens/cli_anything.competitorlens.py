#!/usr/bin/env python3
"""
CompetitorLens — DesignWise Agent #14
Main CLI entry point.

Usage:
    python cli_anything.competitorlens.py analyze <url> [--component <type>]
    python cli_anything.competitorlens.py crawl <url>
    python cli_anything.competitorlens.py extract <raw_json>
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add harness dir to path
HARNESS_DIR = Path(__file__).parent
sys.path.insert(0, str(HARNESS_DIR))


def cmd_crawl(args):
    from crawl import crawl_url
    print(f"[CompetitorLens] Crawling: {args.url}")
    result = crawl_url(args.url)
    if "error" in result:
        print(f"[ERROR] {result['error']}", file=sys.stderr)
        sys.exit(1)
    output_path = args.output or "/tmp/competitorlens_raw.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[OK] Raw crawl saved to: {output_path}")
    print(f"     HTML length: {len(result.get('html', ''))} chars")
    print(f"     Screenshot:  {result.get('screenshot', 'none')}")
    return result


def cmd_extract(args):
    from extract import extract_blueprint
    with open(args.input) as f:
        raw = json.load(f)
    print(f"[CompetitorLens] Extracting blueprint from: {args.input}")
    blueprint = extract_blueprint(raw)
    if "error" in blueprint:
        print(f"[ERROR] {blueprint['error']}", file=sys.stderr)
        sys.exit(1)
    output_path = args.output or "/tmp/competitorlens_blueprint.json"
    with open(output_path, "w") as f:
        json.dump(blueprint, f, indent=2)
    print(f"[OK] Blueprint saved to: {output_path}")
    print(f"     Sections:  {len(blueprint.get('sections', []))}")
    print(f"     Filters:   {len(blueprint.get('filters', []))}")
    print(f"     Layout:    {blueprint.get('layoutType', 'unknown')}")
    return blueprint


def cmd_analyze(args):
    """Full pipeline: crawl → extract → (analyze in Sprint 2)."""
    # Step 1: Crawl
    crawl_args = argparse.Namespace(url=args.url, output="/tmp/cl_raw.json")
    raw = cmd_crawl(crawl_args)

    # Step 2: Extract
    extract_args = argparse.Namespace(
        input="/tmp/cl_raw.json",
        output="/tmp/cl_blueprint.json"
    )
    blueprint = cmd_extract(extract_args)

    # Step 3: Save to Supabase
    try:
        from supabase_client import save_analysis
        record = {
            "competitor_name": _detect_competitor(args.url),
            "source_url": args.url,
            "component_type": args.component or blueprint.get("layoutType", "unknown"),
            "layout_skeleton": blueprint,
            "brand_guard_status": "PENDING",
        }
        saved = save_analysis(record)
        if "error" not in saved:
            print(f"[OK] Analysis saved to Supabase: id={saved.get('id', 'N/A')}")
    except Exception as e:
        print(f"[WARN] Supabase save skipped: {e}")

    print("\n[CompetitorLens] Sprint 1 pipeline complete.")
    print("     Next: Sprint 2 → analyze.py + generate.py")
    return blueprint


def _detect_competitor(url: str) -> str:
    if "propertyonion" in url.lower():
        return "PropertyOnion"
    if "foreclosure.com" in url.lower():
        return "Foreclosure.com"
    if "auction.com" in url.lower():
        return "Auction.com"
    return "Unknown"


def main():
    parser = argparse.ArgumentParser(
        description="CompetitorLens — DesignWise Agent #14",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Crawl PropertyOnion auction calendar
  python cli_anything.competitorlens.py crawl \\
    "https://propertyonion.com/property_search/Brevard%20county?view_type=calendar"

  # Full pipeline
  python cli_anything.competitorlens.py analyze \\
    "https://propertyonion.com/property_search/Brevard%20county?view_type=calendar" \\
    --component calendar
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # crawl subcommand
    crawl_p = subparsers.add_parser("crawl", help="Scrape competitor URL via Firecrawl")
    crawl_p.add_argument("url", help="Competitor URL to crawl")
    crawl_p.add_argument("--output", "-o", help="Output JSON path (default: /tmp/competitorlens_raw.json)")

    # extract subcommand
    extract_p = subparsers.add_parser("extract", help="Extract ComponentBlueprint from raw HTML")
    extract_p.add_argument("input", help="Input raw JSON from crawl step")
    extract_p.add_argument("--output", "-o", help="Output blueprint JSON path")

    # analyze subcommand (full pipeline)
    analyze_p = subparsers.add_parser("analyze", help="Full pipeline: crawl → extract → save")
    analyze_p.add_argument("url", help="Competitor URL to analyze")
    analyze_p.add_argument("--component", "-c", help="Component type hint: calendar, search, listing, map")
    analyze_p.add_argument("--output", "-o", help="Output directory for artifacts")

    args = parser.parse_args()

    if args.command == "crawl":
        cmd_crawl(args)
    elif args.command == "extract":
        cmd_extract(args)
    elif args.command == "analyze":
        cmd_analyze(args)


if __name__ == "__main__":
    main()
