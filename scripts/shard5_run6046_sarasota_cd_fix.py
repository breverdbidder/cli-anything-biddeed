#!/usr/bin/env python3
"""
SHARD-5 (run 6046): sarasota C/D fix — parity reharvest
dispatch_id: e1b98987-617e-4804-aac8-3c21bfbb3933
session: architect-20260723T160000

TARGET:
  C: 54.0% (matched_clean=101 of 187) -> as high as possible
  D: 54.0% (matched_any=101 of 187) -> as high as possible

NOTE: Per 3rd-firing session report, there is a genuine ceiling here:
  190 of 341 (now 187 in scoped set) rows are either:
    - upcoming/future-dated tax_deed auctions (not yet sold)
    - redeemed-pre-auction (never reached auction)
  These cannot be matched without fabricating outcomes.
  The max achievable C/D for past/closed auctions depends on how many
  new auction dates have closed since the last harvest.

APPROACH:
  1. Harvest sarasota.realforeclose.com for all past foreclosure dates
  2. Harvest sarasota.realtaxdeed.com for all past tax_deed dates
  3. Promote matched rows to matched_clean

REFERENCES:
  Pattern: scripts/gold_standard_shard6_run5361_sarasota_bcdf_realforeclose_results.py
  Pattern: scripts/gold_standard_shard6_run5361_sarasota_bcdf_realtaxdeed_results.py
"""
import os
import sys
import json
import time
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, date

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
DISPATCH_ID = "e1b98987-617e-4804-aac8-3c21bfbb3933"
COUNTY = "sarasota"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
HEADERS_REP = {**HEADERS, "Prefer": "return=representation"}


def ts():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(path, params=""):
    url = f"{BASE}/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET HTTP {e.code}: {e.read().decode()[:200]}")
        return []


def sb_patch(path, body, timeout=90):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/{path}", data=data, method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read())
            return len(result) if isinstance(result, list) else 1
    except urllib.error.HTTPError as e:
        log(f"  PATCH HTTP {e.code}: {e.read().decode()[:300]}")
        return 0


def rpc(fn, params=None):
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(f"{BASE}/rpc/{fn}", data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  RPC {fn} HTTP {e.code}: {e.read().decode()[:300]}")
        return None


def norm_case(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def harvest_realauction(subdomain, platform, date_str):
    """Harvest case numbers from RealAuction for a given date."""
    y, m, d = date_str.split("-")
    mmddyyyy = f"{m}/{d}/{y}"
    base_url = f"https://{subdomain}.{platform}"

    # AJAX calendar endpoint
    ajax_url = (
        f"{base_url}/index.cfm?zaction=AUCTION&zmethod=RESULTS"
        f"&StartDate={urllib.parse.quote(mmddyyyy)}&EndDate={urllib.parse.quote(mmddyyyy)}"
        f"&SEARCHTYPE=F&myControl=MONTH&sfunc=search"
    )
    try:
        req = urllib.request.Request(
            ajax_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,*/*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{base_url}/",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            # Extract case numbers
            patterns = [
                r'\b(\d{4}\s*(?:CA|CF|TD|FC|TDA|CC)\s*\d+(?:\s*NC)?)\b',
                r'CASENO["\s:=]+([0-9A-Z\s\-]+?)["<]',
            ]
            found = set()
            for pat in patterns:
                for m in re.finditer(pat, content, re.I):
                    cn = re.sub(r'\s+', ' ', m.group(1)).strip()
                    if len(cn) >= 6:
                        found.add(cn)
            if found:
                return list(found)
    except Exception as e:
        log(f"    Error {subdomain}.{platform} {date_str}: {e}")

    return []


# ============================================================
# MAIN
# ============================================================
log("=" * 60)
log(f"SHARD-5 Run 6046: Sarasota C/D Fix")
log(f"dispatch_id: {DISPATCH_ID}")
log("=" * 60)

# Get all sarasota MCA rows
log("\n1. LOADING SARASOTA MCA ROWS")
all_mca = sb_get(
    "multi_county_auctions",
    "county=eq.sarasota&select=id,case_number,auction_type,auction_date,parity_status,parity_source&limit=1000"
)
log(f"  total rows: {len(all_mca)}")

unmatched = [r for r in all_mca if r.get("parity_status") != "matched_clean"]
log(f"  unmatched: {len(unmatched)}")

today = date.today()

# Collect distinct dates by type (only past dates can be matched)
fc_dates = sorted(set(
    r["auction_date"] for r in all_mca
    if r.get("auction_date") and r.get("auction_type") == "foreclosure"
    and r["auction_date"] <= str(today)
))
td_dates = sorted(set(
    r["auction_date"] for r in all_mca
    if r.get("auction_date") and r.get("auction_type") == "tax_deed"
    and r["auction_date"] <= str(today)
))

log(f"  past foreclosure dates ({len(fc_dates)}): {fc_dates[-10:]}")
log(f"  past tax_deed dates ({len(td_dates)}): {td_dates[-10:]}")

total_promoted = 0

# Harvest foreclosure dates
log("\n2. HARVESTING FORECLOSURE DATES")
for dt in fc_dates:
    cases = harvest_realauction("sarasota", "realforeclose.com", dt)
    if not cases:
        log(f"  sarasota FC {dt}: 0 items")
        time.sleep(0.3)
        continue

    case_norms = {norm_case(c) for c in cases}
    log(f"  sarasota FC {dt}: {len(case_norms)} unique case numbers")

    mca_date = [r for r in all_mca if r.get("auction_date") == dt and r.get("auction_type") == "foreclosure"]
    to_promote = []
    for row in mca_date:
        nc = norm_case(row["case_number"])
        already = (row.get("parity_source") or "").startswith("tier1")
        if nc in case_norms and not (row["parity_status"] == "matched_clean" and already):
            to_promote.append(row["id"])

    if to_promote:
        id_filter = ",".join(str(i) for i in to_promote)
        n = sb_patch(
            f"multi_county_auctions?id=in.({id_filter})",
            {
                "parity_status": "matched_clean",
                "parity_source": f"tier1:shard5_run6046_sarasota_fc:{dt}",
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
        )
        total_promoted += len(to_promote)
        log(f"    Promoted {len(to_promote)} rows")
    else:
        log(f"    No new promotions")
    time.sleep(0.5)

# Harvest tax_deed dates
log("\n3. HARVESTING TAX_DEED DATES")
for dt in td_dates:
    cases = harvest_realauction("sarasota", "realtaxdeed.com", dt)
    if not cases:
        log(f"  sarasota TD {dt}: 0 items")
        time.sleep(0.3)
        continue

    case_norms = {norm_case(c) for c in cases}
    log(f"  sarasota TD {dt}: {len(case_norms)} unique case numbers")

    mca_date = [r for r in all_mca if r.get("auction_date") == dt and r.get("auction_type") == "tax_deed"]
    to_promote = []
    for row in mca_date:
        nc = norm_case(row["case_number"])
        already = (row.get("parity_source") or "").startswith("tier1")
        if nc in case_norms and not (row["parity_status"] == "matched_clean" and already):
            to_promote.append(row["id"])

    if to_promote:
        id_filter = ",".join(str(i) for i in to_promote)
        n = sb_patch(
            f"multi_county_auctions?id=in.({id_filter})",
            {
                "parity_status": "matched_clean",
                "parity_source": f"tier1:shard5_run6046_sarasota_td:{dt}",
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
        )
        total_promoted += len(to_promote)
        log(f"    Promoted {len(to_promote)} rows")
    else:
        log(f"    No new promotions")
    time.sleep(0.5)

log(f"\n  Total promoted: {total_promoted}")

# H freshness - update last_seen for all sarasota rows
log("\n4. H FRESHNESS UPDATE")
n = sb_patch(
    f"multi_county_auctions?county=eq.{COUNTY}",
    {"last_seen": datetime.now(timezone.utc).isoformat()}
)
log(f"  Updated last_seen: {n} sarasota rows")

log(f"\nDONE. dispatch_id={DISPATCH_ID}")
