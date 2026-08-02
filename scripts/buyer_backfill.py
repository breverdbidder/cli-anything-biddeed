#!/usr/bin/env python3
"""
Buyer backfill scraper — fetches RealForeclose Auction Details pages
for all July 2026 SOLD rows missing winning_bidder, extracts:
  - winning_bidder (Name On Title)
  - plaintiff (Party Details)
  - tier1_buyer_type (third_party / plaintiff)
Writes directly to multi_county_auctions via Supabase REST.
"""
import json, os, re, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone

SB_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NDUzMjUyNiwiZXhwIjoyMDgwMTA4NTI2fQ.sNmIFhUGbBfMPHKxU2MjCn2wjXIKUnxcMU2RYTqp9nE"

THROTTLE = 2.5
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"

SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# County subdomain map for RealForeclose/RealTaxDeed
RF_SUBDOMAINS = {
    "marion":       "marion.realforeclose.com",
    "lee":          "lee.realtaxdeed.com",
    "putnam":       "putnam.realforeclose.com",
    "miami_dade":   "miamidade.realtaxdeed.com",
    "highlands":    "highlands.realforeclose.com",
    "bay":          "bay.realforeclose.com",
    "charlotte":    "charlotte.realforeclose.com",
    "broward":      "broward.realforeclose.com",
    "duval":        "duval.realforeclose.com",
    "pinellas":     "pinellas.realforeclose.com",
    "hendry":       "hendry.realforeclose.com",
    "volusia":      "volusia.realforeclose.com",
    "pasco":        "pasco.realforeclose.com",
    "polk":         "polk.realforeclose.com",
    "palm_beach":   "palmbeach.realforeclose.com",
    "hillsborough": "hillsborough.realforeclose.com",
    "escambia":     "escambia.realforeclose.com",
    "leon":         "leon.realforeclose.com",
    "seminole":     "seminole.realforeclose.com",
    "alachua":      "alachua.realforeclose.com",
    "clay":         "clay.realforeclose.com",
    "indian_river": "indian-river.realforeclose.com",
    "st_lucie":     "stlucie.realforeclose.com",
    "walton":       "walton.realforeclose.com",
    "flagler":      "flagler.realforeclose.com",
    "manatee":      "manatee.realforeclose.com",
    "orange":       "orange.realtaxdeed.com",
    "washington":   "washington.realtaxdeed.com",
    "jackson":      "jackson.realforeclose.com",
    "sarasota":     "sarasota.realforeclose.com",
    "lake":         "lake.realforeclose.com",
    "okaloosa":     "okaloosa.realforeclose.com",
    "collier":      "collier.realtaxdeed.com",
    "calhoun":      "calhoun.realtaxdeed.com",
}

def sb_get(path):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}",
        headers={**SB_HEADERS, "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  SB GET error: {e}")
        return []

def sb_patch(row_id, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH", headers=SB_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except Exception as e:
        print(f"  SB PATCH error: {e}")
        return 0

def fetch_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            time.sleep(THROTTLE if attempt == 0 else THROTTLE * 2)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == 2:
                print(f"  fetch failed {url}: {e}")
    return None

def extract_winner_plaintiff(html):
    result = {"winning_bidder": None, "plaintiff": None, "tier1_buyer_type": None}
    if not html:
        return result

    # ── Name On Title (winning_bidder) ────────────────────────────────────
    patterns_winner = [
        r'Name\s+On\s+Title[^<]*</td>\s*<td[^>]*>([^<]{2,80})',
        r'Name\s+On\s+Title.*?<span[^>]*>([^<]{2,80})',
        r'(?:Winner|Successful\s+Bidder)[^<]*</td>\s*<td[^>]*>([^<]{2,80})',
        r'<td[^>]*>\s*Name\s+On\s+Title\s*</td>\s*<td[^>]*>\s*([^<]{2,80})',
    ]
    for pat in patterns_winner:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip().rstrip('</').strip()
            if val and len(val) > 1 and val.lower() not in ('n/a','pending','none',''):
                result["winning_bidder"] = val
                break

    # ── Plaintiff ─────────────────────────────────────────────────────────
    patterns_plaintiff = [
        r'<td[^>]*>\s*Plaintiff\s*</td>\s*<td[^>]*>\s*([^<]{5,200}?)\s*</td>',
        r'Plaintiff[^<]{0,20}</td>\s*<td[^>]*>([^<]{5,200})',
    ]
    for pat in patterns_plaintiff:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            val = m.group(1).strip().replace("&amp;","&").replace("&#39;","'")
            if val and len(val) > 3:
                result["plaintiff"] = val
                break

    # ── buyer_type from winner vs plaintiff ───────────────────────────────
    w = result["winning_bidder"]
    p = result["plaintiff"]
    if w and p:
        wn = w.lower().strip()
        pn = p.lower().strip()
        result["tier1_buyer_type"] = (
            "plaintiff" if (wn[:20] == pn[:20] or wn in pn or pn in wn)
            else "third_party"
        )
    elif w:
        result["tier1_buyer_type"] = "third_party"  # named winner, no plaintiff → assume 3rd party

    return result

def build_detail_url(row):
    """Build the Auction Details page URL from available data."""
    # Priority 1: source_url already has AID
    src = row.get("source_url","") or ""
    if "AID=" in src:
        return src

    # Priority 2: realforeclose_url domain + CASENUM
    county = row.get("county","").lower()
    subdomain = RF_SUBDOMAINS.get(county)
    case = row.get("case_number","")

    if subdomain and case:
        case_enc = urllib.parse.quote(case.strip())
        return f"https://{subdomain}/index.cfm?zaction=AUCTION&Zmethod=DETAIL&CASENUM={case_enc}"

    return None

def main():
    print("=" * 60)
    print("BUYER BACKFILL — July 2026 SOLD rows missing Name On Title")
    print("=" * 60)

    # Fetch all July SOLD rows missing winner
    rows = sb_get(
        "multi_county_auctions"
        "?auction_date=gte.2026-07-01&auction_date=lt.2026-08-01"
        "&or=(tier1_sale_status.eq.SOLD,auction_status.in.(completed,sold))"
        "&or=(winning_bidder.is.null,winning_bidder.in.(3rd%20Party%20Bidder,Cert%20Holder,Unknown))"
        "&select=id,case_number,county,sale_type,property_address,"
        "auction_date,tier1_sold_amount,source_url,realforeclose_url"
        "&limit=500&order=county.asc"
    )
    print(f"Found {len(rows)} rows to enrich\n")

    stats = {"fetched": 0, "winner_found": 0, "plaintiff_found": 0,
             "third_party": 0, "skipped_no_url": 0, "errors": 0}

    for i, row in enumerate(rows):
        county  = row.get("county","?")
        case    = row.get("case_number","?")
        addr    = row.get("property_address","?")
        row_id  = row["id"]
        sold_amt = row.get("tier1_sold_amount","?")

        url = build_detail_url(row)
        if not url:
            print(f"[{i+1}/{len(rows)}] {county}/{case} — NO URL, skipping")
            stats["skipped_no_url"] += 1
            continue

        print(f"[{i+1}/{len(rows)}] {county} | {addr} | ${sold_amt}")
        print(f"  → {url}")

        html = fetch_page(url)
        stats["fetched"] += 1

        extracted = extract_winner_plaintiff(html)
        winner    = extracted["winning_bidder"]
        plaintiff = extracted["plaintiff"]
        btype     = extracted["tier1_buyer_type"]

        if not winner and not plaintiff:
            print(f"  ✗ No data extracted")
            stats["errors"] += 1
            continue

        patch = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if winner:
            patch["winning_bidder"] = winner
            stats["winner_found"] += 1
            print(f"  ✅ Winner: {winner}")
        if plaintiff:
            patch["plaintiff"] = plaintiff
            stats["plaintiff_found"] += 1
            print(f"  ✅ Plaintiff: {plaintiff}")
        if btype:
            patch["tier1_buyer_type"] = btype
            if btype == "third_party":
                stats["third_party"] += 1
            print(f"  ✅ Type: {btype}")

        sb_patch(row_id, patch)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for k,v in stats.items():
        print(f"  {k}: {v}")
    print(f"\n  3rd-party buyers found: {stats['third_party']}")
    print(f"  Lead funnel additions: {stats['third_party']} new buyer profiles")

if __name__ == "__main__":
    main()
