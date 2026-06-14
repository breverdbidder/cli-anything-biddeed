#!/usr/bin/env python3
"""
Zoning ordinance extractor — orchestrator.

Flow per jurisdiction:
  source_map row -> render node (Playwright) -> LLM extract -> validate -> upsert staging

County-agnostic. To onboard a new county: populate zoning_jurisdiction_xwalk and
zoning_source_map for it (the discovery step), then run with --county <name>.

Writes ONLY to zoning_codes_staging. Promotion to zoning_codes is a separate, gated step.

Usage:
  python main.py --county brevard
  python main.py --county brevard --jurisdiction palm_bay
  python main.py --county brevard --dry-run
"""
import argparse
import sys
import traceback

import config
import db as dbmod
from render import render_node, node_url
from extract import extract_standards
from validate import validate_row


def run(county: str, only: str | None, dry_run: bool, render_only: bool = False) -> int:
    db = dbmod.client()
    jurisdictions = dbmod.load_jurisdictions(db, county, only)
    if not jurisdictions:
        print(f"[!] No source-map rows for county={county}"
              f"{f', jurisdiction={only}' if only else ''}. "
              f"Run discovery first (populate zoning_source_map).")
        return 1

    grand = {"jurisdictions": 0, "codes": 0, "staged": 0, "errors": 0}

    for j in jurisdictions:
        aj   = j["assignment_jurisdiction"]
        cj   = j["codes_jurisdiction"]
        plat = j["platform"]
        url  = node_url(plat, j["base_url"], j["node_hint"])
        try:
            codes = dbmod.target_codes(db, county, aj)
            if not codes:
                print(f"[-] {aj}: no assigned codes; skipping")
                continue
            print(f"[>] {aj} ({plat}) — {len(codes)} codes — {url}")

            text = render_node(url, plat)
            if render_only:
                print(f"    rendered {len(text)} chars | sample: {text[:140]!r}")
                grand["jurisdictions"] += 1
                continue
            records = extract_standards(text, codes, cj)

            rows = []
            for r in records:
                r = validate_row(r)
                rows.append({
                    "county": county,  # lowercase, matches zoning_codes.county convention
                    "jurisdiction": cj,
                    "zoning_code": r.get("zoning_code"),
                    "zoning_desc": r.get("zoning_desc"),
                    "max_density": r.get("max_density_raw"),
                    "max_density_num": r.get("max_density_num"),
                    "far": r.get("far"),
                    "parking_per_1000": r.get("parking_per_1000"),
                    "max_height_ft": r.get("max_height_ft"),
                    "min_lot_size": r.get("min_lot_size"),
                    "is_site_specific": bool(r.get("is_site_specific")),
                    "density_basis": r.get("density_basis"),
                    "source_url": url,
                    "source_section": r.get("source_section"),
                    "extraction_confidence": r.get("confidence"),
                    "extraction_notes": r.get("notes"),
                    "gated": False,
                })

            hi = sum(1 for x in rows if x["extraction_confidence"] == "high")
            print(f"    extracted {len(rows)} ({hi} high-confidence)"
                  + (" [dry-run, not written]" if dry_run else ""))
            if not dry_run:
                grand["staged"] += dbmod.stage(db, rows)
            grand["jurisdictions"] += 1
            grand["codes"] += len(rows)

        except Exception as e:
            grand["errors"] += 1
            print(f"[x] {aj} FAILED: {e}")
            traceback.print_exc()
            # continue to next jurisdiction; never let one source sink the run

    print(f"\n=== {county}: {grand['jurisdictions']} jurisdictions, "
          f"{grand['codes']} codes, {grand['staged']} staged, {grand['errors']} errors ===")
    print("Review staged rows, then promote gated=true rows to zoning_codes separately.")
    return 0 if grand["errors"] == 0 else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", required=True)
    ap.add_argument("--jurisdiction", default=None, help="assignment_jurisdiction filter (e.g. palm_bay)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--render-only", action="store_true",
                    help="render pages and report content size only; no LLM, no writes")
    args = ap.parse_args()
    sys.exit(run(args.county.lower(), args.jurisdiction, args.dry_run, args.render_only))


if __name__ == "__main__":
    main()
