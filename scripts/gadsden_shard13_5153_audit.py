#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-13 — gadsden county audit + fix session (run 5153)
dispatch_id: 47974994-0d84-4a27-a865-6429cab3303d

Current state (from issue brief): 7/10
- PASSING: A(7), B(100%), C(95.7%), D(95.7%), F(100%), H(19.4h), J(100%)
- FAILING: E(91.3% — need ≥95%), G(null — zoning), I(0% — property cards)

Known history from prior session reports:
- E: 23 gadsden MCA rows total. 21 parcel-linked. 3 remaining unlinked:
  - 25000901CA "Ramon's Construction" (PLSS-only, genuinely ambiguous)
  - 25000696CA "Est. of Booker-Barnes" (PLSS-only, 557 parcels in section)
  - 25000942CA "Woods" (mobile home, no address match in fl_parcels)
  - E needs ≥95% of 23 = ≥21.85 = ≥22 rows linked
  - Current 21/23 = 91.3% — need AT LEAST 1 more to hit 95.65% = PASS
- G: zoning_districts exists (Quincy R-1 synthetic HYPOTHESIS) but
  v_zoning_gold_standard_kpi_v3 returns null because parcel_zones has
  real TD parcel_ids but no per-parcel zone_standards populated that
  the KPI view can evaluate against.
- I: 0% because property cards require parcel_id + zone_code.

Strategy:
1. Query live DB to confirm current E/G/I state
2. E: try remaining 3 unlinked rows via alternate approaches:
   - 25000901CA: Ramon's Construction - two parcels on Ridgewood Rd.
     The foreclosure judgment was $56,245. Can we look at sale amounts 
     in fl_parcels to see if one of the two Ridgewood parcels has a
     more recent sale more consistent with this amount? PLSS-only but
     if one parcel shows a 2024 foreclosure sale and the other doesn't,
     that's a distinguishing signal.
   - 25000696CA: Booker-Barnes - could try looking for "BOOKER-BARNES"
     as a combined hyphenated name (exact hyphen might be in fl_parcels)
   - 25000942CA: Woods + "Live Oak Manufactured Home" - manufactured home
     parks might have a specific address "Live Oak" in Gadsden county
3. G: Load real Gadsden zoning from the county's GIS/ArcGIS REST API.
   Known barrier: gadsdencountyfl.gov returns 403. Try alternate sources:
   - FDOT/FDEP ArcGIS open data
   - FL GeoPlan Center
   - Direct Gadsden county ArcGIS server endpoint probe
4. I: Fix property cards after parcel linkage
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
COUNTY = "gadsden"
DISPATCH_ID = "47974994-0d84-4a27-a865-6429cab3303d"

DRY_RUN = "--dry-run" in sys.argv


def ts() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str = "") -> List[Dict]:
    sep = "&" if params else "?"
    url = f"{BASE}/{table}{'?' + params if params else ''}{'&' if params else '?'}limit=1000"
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  GET {table} HTTP {e.code}: {e.read().decode()[:200]}")
        return []
    except Exception as e:
        log(f"  GET {table} ERROR: {e}")
        return []


def sb_rpc(func: str, params: Dict) -> Dict:
    body = json.dumps(params).encode()
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    req = urllib.request.Request(f"{BASE}/rpc/{func}", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"  RPC {func} HTTP {e.code}: {e.read().decode()[:300]}")
        return {}
    except Exception as e:
        log(f"  RPC {func} ERROR: {e}")
        return {}


def sb_post(table: str, data, prefer: str = "resolution=merge-duplicates,return=minimal") -> Tuple[int, str]:
    if isinstance(data, dict):
        data = [data]
    if not data:
        return 200, "no-op"
    body = json.dumps(data).encode()
    headers = {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": prefer,
    }
    req = urllib.request.Request(f"{BASE}/{table}", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_patch(table: str, filters: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    headers = {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "return=representation",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def evaluate() -> Dict:
    return sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})


if not SUPABASE_KEY:
    log("ERROR: No Supabase key found in environment. Check SUPABASE_SERVICE_ROLE_KEY.")
    sys.exit(1)

log("=" * 70)
log(f"GADSDEN SHARD-13 RUN 5153 AUDIT — {ts()}")
log(f"dispatch_id: {DISPATCH_ID}")
log("=" * 70)

# ── Step 1: Live evaluation ────────────────────────────────────────────────
log("\n=== STEP 1: LIVE pencil_dod_evaluate_county ===")
before_eval = evaluate()
log(f"BEFORE eval: {json.dumps(before_eval, indent=2)}")

# ── Step 2: Audit current parcel linkage state ─────────────────────────────
log("\n=== STEP 2: AUDIT PARCEL LINKAGE STATE ===")
mca_rows = sb_get("multi_county_auctions", "county=eq.gadsden&select=id,case_number,parcel_id,sale_type,auction_status,property_address,last_seen_at")
log(f"  Total gadsden MCA rows: {len(mca_rows)}")
linked = [r for r in mca_rows if r.get("parcel_id")]
unlinked = [r for r in mca_rows if not r.get("parcel_id")]
log(f"  Linked: {len(linked)}, Unlinked: {len(unlinked)}")
for r in unlinked:
    log(f"    UNLINKED: {r['case_number']} | {r['sale_type']} | {r['property_address'][:60]}")

# ── Step 3: Probe remaining unlinked rows ─────────────────────────────────
log("\n=== STEP 3: PROBE REMAINING UNLINKED ROWS ===")

# Ramon's Construction (25000901CA) — 2 Ridgewood Rd parcels in same PLSS section
# Try: check sale_yr1/sale_prc1 to see if one matches the $56,245 judgment more closely
# Also try exact entity name match
log("\n  --- 25000901CA (Ramon's Construction) ---")
ramons_cases = [r for r in mca_rows if r.get("case_number") == "25000901CA"]
if ramons_cases:
    log(f"    MCA row: {ramons_cases[0]}")

ramons_q = urllib.parse.quote("*RAMONS CONSTRUCTION*")
ramons_parcels = sb_get("fl_parcels", f"own_name=ilike.{ramons_q}&co_no=eq.30&select=parcel_id,own_name,phy_addr1,phy_city,jv,sale_yr1,sale_prc1,sale_yr2,sale_prc2,dor_uc&limit=20")
log(f"    fl_parcels RAMONS CONSTRUCTION co_no=30: {len(ramons_parcels)} rows")
for p in ramons_parcels:
    log(f"      {p['parcel_id']} | {p['own_name']} | {p['phy_addr1']}, {p['phy_city']} | jv={p['jv']} | sale_yr1={p.get('sale_yr1')} prc1={p.get('sale_prc1')} | dor_uc={p.get('dor_uc')}")

# Booker-Barnes (25000696CA) — try hyphenated exact name
log("\n  --- 25000696CA (Est. of Booker-Barnes) ---")
bb_cases = [r for r in mca_rows if r.get("case_number") == "25000696CA"]
if bb_cases:
    log(f"    MCA row: {bb_cases[0]}")

# Try exact hyphenated "BOOKER-BARNES" and "BOOKER BARNES" 
for name_q_str in ["*BOOKER-BARNES*", "*BOOKER BARNES*"]:
    name_q = urllib.parse.quote(name_q_str)
    bb_parcels = sb_get("fl_parcels", f"own_name=ilike.{name_q}&co_no=eq.30&select=parcel_id,own_name,phy_addr1,phy_city,jv&limit=10")
    log(f"    fl_parcels '{name_q_str}' co_no=30: {len(bb_parcels)} rows")
    for p in bb_parcels:
        log(f"      {p['parcel_id']} | {p['own_name']} | {p['phy_addr1']}, {p['phy_city']} | jv={p['jv']}")

# Woods (25000942CA) — manufactured home "Live Oak"
log("\n  --- 25000942CA (Woods - Live Oak MH) ---")
woods_cases = [r for r in mca_rows if r.get("case_number") == "25000942CA"]
if woods_cases:
    log(f"    MCA row: {woods_cases[0]}")

# Try searching for "LIVE OAK" in phy_addr1 for co_no=30
live_oak_q = urllib.parse.quote("*LIVE OAK*")
lo_parcels = sb_get("fl_parcels", f"phy_addr1=ilike.{live_oak_q}&co_no=eq.30&select=parcel_id,own_name,phy_addr1,phy_city,jv,dor_uc&limit=20")
log(f"    fl_parcels 'LIVE OAK' in phy_addr1 co_no=30: {len(lo_parcels)} rows")
for p in lo_parcels:
    log(f"      {p['parcel_id']} | {p['own_name']} | {p['phy_addr1']}, {p['phy_city']} | dor_uc={p.get('dor_uc')}")

# Also try WOODS with dor_uc=002 (mobile home)
woods_mh_q = urllib.parse.quote("*WOODS*")
woods_mh = sb_get("fl_parcels", f"own_name=ilike.{woods_mh_q}&co_no=eq.30&dor_uc=eq.002&select=parcel_id,own_name,phy_addr1,phy_city,jv&limit=10")
log(f"    fl_parcels WOODS + dor_uc=002 co_no=30: {len(woods_mh)} rows")
for p in woods_mh:
    log(f"      {p['parcel_id']} | {p['own_name']} | {p['phy_addr1']}, {p['phy_city']} | jv={p['jv']}")

# ── Step 4: Audit G (zoning) state ─────────────────────────────────────────
log("\n=== STEP 4: AUDIT G/I ZONING STATE ===")
jurs = sb_get("jurisdictions", "county=ilike.*Gadsden*&select=id,name,county,co_no,state&limit=20")
log(f"  Gadsden jurisdictions: {len(jurs)}")
for j in jurs:
    log(f"    {j}")

if jurs:
    for jur in jurs:
        jur_id = jur["id"]
        zd = sb_get("zoning_districts", f"jurisdiction_id=eq.{jur_id}&select=id,code,name,category&limit=30")
        log(f"  zoning_districts for jur_id={jur_id} ({jur['name']}): {len(zd)} rows")
        for z in zd:
            log(f"    {z}")
            # Check zone_standards
            zs = sb_get("zone_standards", f"zoning_district_id=eq.{z['id']}&select=*&limit=5")
            log(f"      zone_standards: {zs}")

# Check parcel_zones for gadsden
pz = sb_get("parcel_zones", "select=count&county=eq.gadsden")
log(f"  parcel_zones county=gadsden: {pz}")

# Check parcel_zones via TD parcel_ids
td_parcel_ids = [r["parcel_id"] for r in mca_rows if r.get("parcel_id") and r.get("sale_type") == "tax_deed"]
log(f"  TD parcel_ids: {td_parcel_ids}")
if td_parcel_ids:
    # Check first one
    pid_q = urllib.parse.quote(td_parcel_ids[0])
    pz_check = sb_get("parcel_zones", f"parcel_id=eq.{pid_q}&select=*&limit=5")
    log(f"  parcel_zones for first TD parcel {td_parcel_ids[0]}: {pz_check}")

# ── Step 5: Check I (property card) state ─────────────────────────────────
log("\n=== STEP 5: AUDIT I PROPERTY CARD STATE ===")
# I requires: parcel_id IS NOT NULL AND 
# (geo info: lat/lng not null AND value: assessed_value not null AND zone_code exists)
for r in mca_rows[:5]:
    log(f"  Sample row: {r['case_number']} parcel={r['parcel_id']} status={r['auction_status']}")

log("\n=== COMPLETED AUDIT ===")
log("Next: write fixes based on audit results above")
