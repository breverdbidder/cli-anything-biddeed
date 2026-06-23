#!/usr/bin/env python3
"""
Municode Source Map Discovery — 6-County Beta Launch
Beta-launch campaign issue #8144

Auto-discovers zoning chapter nodeIds from Municode for each jurisdiction,
then seeds zoning_jurisdiction_xwalk + zoning_source_map in Supabase.

This script must run BEFORE zoning-extract.yml for new counties.
Requires FIRECRAWL_API_KEY (best-effort — falls back to placeholder if unavailable).

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (required)
  FIRECRAWL_API_KEY (optional — enables live nodeId discovery)
  COUNTY (optional — run only one county; default = all 5)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
from typing import Optional

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

FC_KEY  = os.environ.get("FIRECRAWL_API_KEY", "")
TARGET  = os.environ.get("COUNTY", "").lower().strip() or None

def log(msg: str, tag: str = "INFO") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {tag}: {msg}", flush=True)

# ── Jurisdiction seed map ─────────────────────────────────────────────────────
# Known Municode municipality slugs per county.
# node_hint will be populated via Firecrawl discovery, or left as placeholder.
JURISDICTIONS: dict[str, list[dict]] = {
    "sarasota": [
        {"slug": "sarasota_county",  "municode_city": "sarasota_county",  "display": "Sarasota County (unincorp)"},
        {"slug": "sarasota_city",    "municode_city": "sarasota",          "display": "City of Sarasota"},
        {"slug": "venice",           "municode_city": "venice",            "display": "City of Venice"},
        {"slug": "north_port",       "municode_city": "north_port",        "display": "City of North Port"},
        {"slug": "longboat_key",     "municode_city": "longboat_key",      "display": "Town of Longboat Key"},
    ],
    "palm_beach": [
        {"slug": "palm_beach_county", "municode_city": "palm_beach_county", "display": "Palm Beach County (unincorp)"},
        {"slug": "west_palm_beach",   "municode_city": "west_palm_beach",   "display": "West Palm Beach"},
        {"slug": "boca_raton",        "municode_city": "boca_raton",        "display": "City of Boca Raton"},
        {"slug": "delray_beach",      "municode_city": "delray_beach",      "display": "City of Delray Beach"},
        {"slug": "boynton_beach",     "municode_city": "boynton_beach",     "display": "City of Boynton Beach"},
        {"slug": "lake_worth_beach",  "municode_city": "lake_worth_beach",  "display": "Lake Worth Beach"},
        {"slug": "wellington",        "municode_city": "wellington",        "display": "Village of Wellington"},
        {"slug": "jupiter",           "municode_city": "jupiter",           "display": "Town of Jupiter"},
    ],
    "broward": [
        {"slug": "broward_county",   "municode_city": "broward_county",   "display": "Broward County (unincorp)"},
        {"slug": "fort_lauderdale",  "municode_city": "fort_lauderdale",  "display": "Fort Lauderdale"},
        {"slug": "hollywood",        "municode_city": "hollywood",        "display": "City of Hollywood"},
        {"slug": "pembroke_pines",   "municode_city": "pembroke_pines",   "display": "Pembroke Pines"},
        {"slug": "miramar",          "municode_city": "miramar",          "display": "City of Miramar"},
        {"slug": "coral_springs",    "municode_city": "coral_springs",    "display": "City of Coral Springs"},
        {"slug": "pompano_beach",    "municode_city": "pompano_beach",    "display": "City of Pompano Beach"},
        {"slug": "deerfield_beach",  "municode_city": "deerfield_beach",  "display": "City of Deerfield Beach"},
    ],
    "orange": [
        {"slug": "orange_county",    "municode_city": "orange_county",    "display": "Orange County (unincorp)"},
        {"slug": "orlando",          "municode_city": "orlando",          "display": "City of Orlando"},
        {"slug": "winter_park",      "municode_city": "winter_park",      "display": "City of Winter Park"},
        {"slug": "apopka",           "municode_city": "apopka",           "display": "City of Apopka"},
        {"slug": "ocoee",            "municode_city": "ocoee",            "display": "City of Ocoee"},
        {"slug": "winter_garden",    "municode_city": "winter_garden",    "display": "City of Winter Garden"},
        {"slug": "maitland",         "municode_city": "maitland",         "display": "City of Maitland"},
    ],
    "volusia": [
        {"slug": "volusia_county",   "municode_city": "volusia_county",   "display": "Volusia County (unincorp)"},
        {"slug": "daytona_beach",    "municode_city": "daytona_beach",    "display": "City of Daytona Beach"},
        {"slug": "deltona",          "municode_city": "deltona",          "display": "City of Deltona"},
        {"slug": "port_orange",      "municode_city": "port_orange",      "display": "City of Port Orange"},
        {"slug": "ormond_beach",     "municode_city": "ormond_beach",     "display": "City of Ormond Beach"},
        {"slug": "new_smyrna_beach", "municode_city": "new_smyrna_beach", "display": "New Smyrna Beach"},
        {"slug": "deland",           "municode_city": "deland",           "display": "City of DeLand"},
    ],
}

COUNTY_NAME_MAP = {
    "sarasota": "Sarasota",
    "palm_beach": "Palm Beach",
    "broward": "Broward",
    "orange": "Orange",
    "volusia": "Volusia",
}

# ── Supabase helpers ──────────────────────────────────────────────────────────
def _hdrs(extra: dict = None) -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
         "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h

def sb_upsert_rows(table: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    body = json.dumps(rows).encode()
    req  = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}", data=body,
        headers=_hdrs({"Prefer": "resolution=merge-duplicates,return=minimal"}),
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        return len(rows)
    except urllib.error.HTTPError as e:
        log(f"sb_upsert {table} HTTP {e.code}: {e.read()[:200]}", "WARN")
        return 0

def sb_get_existing(table: str, filter_qs: str) -> list[dict]:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}", headers=_hdrs()
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()) or []
    except Exception:
        return []

# ── Firecrawl discovery ───────────────────────────────────────────────────────
MUNICODE_BASE = "https://library.municode.com/fl"
ZONING_KEYWORDS = [
    "zoning", "land development", "land use", "planning and zoning",
    "development regulation", "unified development", "udc", "udr", "ldc"
]

def _firecrawl_scrape(url: str) -> str | None:
    """Use Firecrawl to render a Municode page and return the HTML."""
    if not FC_KEY:
        return None
    body = json.dumps({"url": url, "formats": ["html"], "onlyMainContent": False}).encode()
    req  = urllib.request.Request(
        "https://api.firecrawl.dev/v1/scrape",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FC_KEY}",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data.get("data", {}).get("html", "")
    except Exception as e:
        log(f"Firecrawl error for {url}: {e}", "WARN")
        return None

def discover_node_id(municode_city: str) -> Optional[str]:
    """
    Attempt to discover the zoning chapter nodeId from Municode.
    Returns nodeId string or None if not found.
    """
    if not FC_KEY:
        log(f"  No FIRECRAWL_API_KEY — skipping live discovery for {municode_city}", "WARN")
        return None

    url = f"{MUNICODE_BASE}/{municode_city}"
    log(f"  Discovering zoning nodeId for {municode_city} via {url}...")

    html = _firecrawl_scrape(url)
    if not html:
        log(f"  {municode_city}: Firecrawl returned empty", "WARN")
        return None

    # Search for links containing zoning-related text and extract nodeId
    # Municode URLs look like: ...?nodeId=COOR_CH140ZO or similar
    # Also check anchor tags with href containing nodeId

    # Pattern 1: <a ... href="...?nodeId=XXX">...zoning...</a>
    link_pattern = re.compile(
        r'href="[^"]*\?nodeId=([A-Z0-9_]+)[^"]*"[^>]*>[^<]*(?:' +
        '|'.join(re.escape(k) for k in ZONING_KEYWORDS) +
        r')[^<]*<',
        re.IGNORECASE
    )
    m = link_pattern.search(html)
    if m:
        node_id = m.group(1)
        log(f"  {municode_city}: found nodeId={node_id} (pattern 1)")
        return node_id

    # Pattern 2: nodeId=XXX anywhere near zoning text
    # Find all nodeIds, then pick the one nearest to a zoning keyword
    all_node_ids = re.findall(r'nodeId=([A-Z0-9_]{6,})', html)
    if all_node_ids:
        # Try to find which is closest to "zoning" in the text
        html_lower = html.lower()
        for kw in ZONING_KEYWORDS:
            kw_pos = html_lower.find(kw)
            if kw_pos < 0:
                continue
            # Find nearest nodeId reference
            best_node, best_dist = None, float("inf")
            for nid in all_node_ids:
                nid_pos = html.find(f"nodeId={nid}")
                if nid_pos >= 0:
                    dist = abs(nid_pos - kw_pos)
                    if dist < best_dist:
                        best_dist = dist
                        best_node = nid
            if best_node and best_dist < 2000:
                log(f"  {municode_city}: found nodeId={best_node} near '{kw}' (dist={best_dist})")
                return best_node

    log(f"  {municode_city}: no zoning nodeId found in page", "WARN")
    return None

# ── Seed functions ────────────────────────────────────────────────────────────
def seed_xwalk(county_slug: str, jurisdictions: list[dict]) -> int:
    county_display = COUNTY_NAME_MAP[county_slug]
    rows = [
        {
            "assignment_jurisdiction": j["slug"],
            "codes_jurisdiction":      j["slug"],
            "county":                  county_display,
        }
        for j in jurisdictions
    ]
    n = sb_upsert_rows("zoning_jurisdiction_xwalk", rows)
    log(f"  zoning_jurisdiction_xwalk: {n} rows upserted for {county_slug}")
    return n

def seed_source_map(county_slug: str, jurisdictions: list[dict]) -> int:
    county_display = COUNTY_NAME_MAP[county_slug]
    rows = []
    for priority, j in enumerate(jurisdictions, start=1):
        base_url = f"{MUNICODE_BASE}/{j['municode_city']}"
        node_id  = discover_node_id(j["municode_city"])

        row: dict = {
            "assignment_jurisdiction": j["slug"],
            "platform":                "municode",
            "base_url":                base_url,
            "priority":                priority,
            "county":                  county_display,
        }
        if node_id:
            row["node_hint"] = node_id
            row["dimensional_locator"] = node_id
        else:
            # Placeholder — extractor will fail gracefully without node_hint
            # A human/next-run can update after manual Municode inspection
            row["node_hint"] = "DISCOVERY_PENDING"
            row["dimensional_locator"] = "DISCOVERY_PENDING"

        rows.append(row)
        log(f"  {j['slug']}: base_url={base_url} node_hint={row['node_hint']}")

    n = sb_upsert_rows("zoning_source_map", rows)
    log(f"  zoning_source_map: {n} rows upserted for {county_slug}")
    return n

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    log("=" * 60)
    log("MUNICODE DISCOVERY — 6-County Beta Launch #8144")
    fc_status = "LIVE" if FC_KEY else "SKIPPED (no API key)"
    log(f"Firecrawl discovery: {fc_status}")
    log("=" * 60)

    counties = [TARGET] if TARGET else list(JURISDICTIONS.keys())
    total_xwalk = total_smap = 0

    for county in counties:
        if county not in JURISDICTIONS:
            log(f"Unknown county: {county}", "ERROR")
            continue

        jurisdictions = JURISDICTIONS[county]
        log(f"\n── {county.upper()} ({len(jurisdictions)} jurisdictions) ──")

        # Check if already seeded
        existing = sb_get_existing(
            "zoning_source_map",
            f"county=eq.{COUNTY_NAME_MAP[county]}&select=assignment_jurisdiction"
        )
        existing_slugs = {r.get("assignment_jurisdiction") for r in existing}
        pending = [j for j in jurisdictions if j["slug"] not in existing_slugs]

        if not pending:
            log(f"  All {len(jurisdictions)} jurisdictions already in source_map — skipping")
            continue

        log(f"  {len(pending)} of {len(jurisdictions)} jurisdictions need seeding")

        n_xwalk = seed_xwalk(county, pending)
        n_smap  = seed_source_map(county, pending)
        total_xwalk += n_xwalk
        total_smap  += n_smap

    log(f"\n=== DISCOVERY COMPLETE ===")
    log(f"Total xwalk rows: {total_xwalk}")
    log(f"Total source_map rows: {total_smap}")
    log("\nNext step: gh workflow run zoning-extract.yml --field county=<county>")
    log("UNTESTED: node_hints marked DISCOVERY_PENDING need manual Municode inspection")
    return 0

if __name__ == "__main__":
    sys.exit(main())
