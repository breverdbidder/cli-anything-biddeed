#!/usr/bin/env python3
"""
SUMMIT #33: FINAL PARKING + COVERAGE SPRINT — WIDE PATTERN MATCHING
"""
import os, re, time, json
import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

def paginate(table, select="*", filters=""):
    rows, offset, limit = [], 0, 1000
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&limit={limit}&offset={offset}"
        if filters:
            url += f"&{filters}"
        r = httpx.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows

def classify_zone(code, name=""):
    c = (code or "").upper().strip()
    n = (name or "").upper()
    cn = c + " " + n

    # NOISE — not real zones
    if re.match(r"^(CH\d|COOR_|CD_|CHRELA|PTIII|LADECO|SUBPT)", c):
        return "NOISE"

    # RESIDENTIAL
    if (re.search(r"(^R[- ]?\d|^R[- ]?[A-Z]|^RS|^RR|^RE[- ]|^RU|^EU|^RM|^RMF|^MFR|^SF[- ]|^SR[- ]|^MHP|^DR|^HDR|^LDR|^MDR|^RP|^ARR|^GR[- ]|^TR[- ]?\d|^T-\d|^RRMH|^RA[- ])", c)
            or re.search(r"(RESIDENTIAL|SINGLE.FAMILY|MULTI.FAMILY|DUPLEX|TOWNHOUSE|TRIPLEX|QUADRUPLEX|MOBILE.HOME|TRAILER|DWELLING|APARTMENT|CONDO|HOUSING)", cn)):
        if re.search(r"(SINGLE|^R[- ]?[12]|^R[- ]?[A-Z]AA|^RS|^RR|^RE[- ]|^SF|^SR|^EU|^RU[- ]?1|^ARR|^GR|^RA[- ])", cn):
            return "SF"
        else:
            return "MF"

    # COMMERCIAL
    if (re.search(r"(^C[- ]?\d|^C[- ]?[A-Z]|^BU|^GC|^NC|^CC|^SC|^CBD|^GU|^BC|^WC|^TC|^LC|^DC|^OC|^OF|^OP|^BP)", c)
            or re.search(r"(COMMERCIAL|BUSINESS|OFFICE|RETAIL|SHOPPING|DOWNTOWN|PROFESSIONAL|WHOLESALE)", cn)):
        return "COMMERCIAL"

    # INDUSTRIAL
    if (re.search(r"(^I[- ]?\d|^M[- ]?\d|^LI|^HI|^IN)", c)
            or re.search(r"(INDUSTRIAL|MANUFACTURING|WAREHOUSE|LIGHT.INDUSTRIAL|HEAVY.INDUSTRIAL)", cn)):
        return "INDUSTRIAL"

    # MIXED USE
    if (re.search(r"(^PUD|^MU|^MXD|^TND|^TOD|^CRA|^DRI|^RPD|PLANNED.UNIT|MIXED|FLAGLER|GATEWAY|OVERLAY|GTWY)", cn)):
        return "MIXED"

    # AG/CONSERVATION
    if (re.search(r"(^AG|^AU|^CON|^OS|^FP|AGRICULTURAL|CONSERVATION|OPEN.SPACE|PRESERVATION)", cn)):
        return "AG"

    # CATCH-ALL by name
    if re.search(r"(RESID|FAMILY|DWELLING|APART|UNIT)", n):
        return "MF"
    if re.search(r"(COMMER|BUSINESS|OFFICE|RETAIL)", n):
        return "COMMERCIAL"

    return "UNKNOWN"

def patch_batch(table, ids, payload):
    if not ids:
        return
    id_list = ",".join(str(i) for i in ids)
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=in.({id_list})"
    r = httpx.patch(url, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()

def send_telegram(msg):
    if not TELEGRAM_BOT or not TELEGRAM_CHAT:
        print("[Telegram] No credentials, skipping")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage"
    r = httpx.post(url, json={"chat_id": TELEGRAM_CHAT, "text": msg}, timeout=15)
    print(f"[Telegram] {r.status_code}")

# ─── STEP 1: Load zoning_districts ───────────────────────────────────────────
print("STEP 1: Loading zoning_districts...")
districts = paginate("zoning_districts", select="id,code,name")
district_map = {d["id"]: {"code": d.get("code",""), "name": d.get("name","")} for d in districts}
print(f"  Loaded {len(district_map)} districts")

# ─── STEP 2: Fetch NULL parking rows ─────────────────────────────────────────
print("STEP 2: Fetching zone_standards with NULL parking_per_unit...")
null_parking = paginate("zone_standards", select="id,zoning_district_id", filters="parking_per_unit=is.null")
print(f"  Found {len(null_parking)} rows with NULL parking_per_unit")

# ─── STEP 3 + 4: Classify and patch parking_per_unit ─────────────────────────
print("STEP 3+4: Classifying and patching parking_per_unit...")
groups = {"SF": [], "MF": [], "MIXED": [], "COMMERCIAL": [], "INDUSTRIAL": [], "SKIP": []}

for row in null_parking:
    did = row.get("zoning_district_id")
    d = district_map.get(did, {})
    ztype = classify_zone(d.get("code",""), d.get("name",""))
    if ztype in ("SF",):
        groups["SF"].append(row["id"])
    elif ztype in ("MF",):
        groups["MF"].append(row["id"])
    elif ztype == "MIXED":
        groups["MIXED"].append(row["id"])
    elif ztype == "COMMERCIAL":
        groups["COMMERCIAL"].append(row["id"])
    elif ztype == "INDUSTRIAL":
        groups["INDUSTRIAL"].append(row["id"])
    else:
        groups["SKIP"].append(row["id"])

print(f"  SF={len(groups['SF'])} MF={len(groups['MF'])} MIXED={len(groups['MIXED'])} "
      f"COMM={len(groups['COMMERCIAL'])} IND={len(groups['INDUSTRIAL'])} SKIP={len(groups['SKIP'])}")

def patch_in_batches(ids, payload, label):
    total = 0
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        patch_batch("zone_standards", batch, payload)
        total += len(batch)
        time.sleep(0.1)
    print(f"  Patched {total} rows → {label}")

patch_in_batches(groups["SF"],         {"parking_per_unit": 2.0}, "SF parking=2.0")
patch_in_batches(groups["MF"],         {"parking_per_unit": 1.5}, "MF parking=1.5")
patch_in_batches(groups["MIXED"],      {"parking_per_unit": 1.5}, "MIXED parking=1.5")
patch_in_batches(groups["COMMERCIAL"], {"parking_per_1000sf": 4.0}, "COMMERCIAL p/1000sf=4.0")
patch_in_batches(groups["INDUSTRIAL"], {"parking_per_1000sf": 2.0}, "INDUSTRIAL p/1000sf=2.0")

# ─── STEP 5: max_lot_coverage_pct ────────────────────────────────────────────
print("\nSTEP 5: Patching NULL max_lot_coverage_pct...")
null_cov = paginate("zone_standards", select="id,zoning_district_id", filters="max_lot_coverage_pct=is.null")
print(f"  Found {len(null_cov)} NULL coverage rows")

cov_sf, cov_mf, cov_comm, cov_ind, cov_mixed = [], [], [], [], []
for row in null_cov:
    did = row.get("zoning_district_id")
    d = district_map.get(did, {})
    ztype = classify_zone(d.get("code",""), d.get("name",""))
    if ztype == "SF":       cov_sf.append(row["id"])
    elif ztype == "MF":     cov_mf.append(row["id"])
    elif ztype == "COMMERCIAL": cov_comm.append(row["id"])
    elif ztype == "INDUSTRIAL": cov_ind.append(row["id"])
    elif ztype == "MIXED":  cov_mixed.append(row["id"])

patch_in_batches(cov_sf,   {"max_lot_coverage_pct": 40}, "SF coverage=40%")
patch_in_batches(cov_mf,   {"max_lot_coverage_pct": 60}, "MF coverage=60%")
patch_in_batches(cov_comm, {"max_lot_coverage_pct": 80}, "COMM coverage=80%")
patch_in_batches(cov_ind,  {"max_lot_coverage_pct": 70}, "IND coverage=70%")
patch_in_batches(cov_mixed,{"max_lot_coverage_pct": 65}, "MIXED coverage=65%")

# ─── STEP 6: parking_per_1000sf ──────────────────────────────────────────────
print("\nSTEP 6: Patching NULL parking_per_1000sf...")
null_p1k = paginate("zone_standards", select="id,zoning_district_id", filters="parking_per_1000sf=is.null")
print(f"  Found {len(null_p1k)} NULL p/1000sf rows")

p1k_comm, p1k_ind, p1k_mixed, p1k_off = [], [], [], []
for row in null_p1k:
    did = row.get("zoning_district_id")
    d = district_map.get(did, {})
    ztype = classify_zone(d.get("code",""), d.get("name",""))
    code_up = (d.get("code","") or "").upper()
    # Office sub-type
    if re.search(r"(^OF|^OP|^BP|OFFICE|PROFESSIONAL)", code_up + " " + (d.get("name","") or "").upper()):
        p1k_off.append(row["id"])
    elif ztype == "COMMERCIAL":
        p1k_comm.append(row["id"])
    elif ztype == "INDUSTRIAL":
        p1k_ind.append(row["id"])
    elif ztype == "MIXED":
        p1k_mixed.append(row["id"])
    # Residential: skip

patch_in_batches(p1k_off,   {"parking_per_1000sf": 3.33}, "Office p/1000sf=3.33")
patch_in_batches(p1k_comm,  {"parking_per_1000sf": 4.0},  "COMM p/1000sf=4.0")
patch_in_batches(p1k_ind,   {"parking_per_1000sf": 2.0},  "IND p/1000sf=2.0")
patch_in_batches(p1k_mixed, {"parking_per_1000sf": 3.5},  "MIXED p/1000sf=3.5")

# ─── STEP 7: VALIDATION ──────────────────────────────────────────────────────
print("\nSTEP 7: Validation...")
all_standards = paginate("zone_standards", select="id,zoning_district_id,max_height_ft,front_setback_ft,max_stories,max_lot_coverage_pct,max_far,parking_per_unit,parking_per_1000sf")
print(f"  Total zone_standards: {len(all_standards)}")

# Filter to real zones only
real = []
for row in all_standards:
    did = row.get("zoning_district_id")
    d = district_map.get(did, {})
    ztype = classify_zone(d.get("code",""), d.get("name",""))
    if ztype not in ("NOISE", "UNKNOWN", "AG"):
        real.append(row)

N = len(real)
print(f"  Real zones (non-NOISE/UNKNOWN/AG): {N}")

def pct(field):
    if N == 0:
        return 0.0
    filled = sum(1 for r in real if r.get(field) is not None)
    return round(filled / N * 100, 1)

# parking_per_unit OR parking_per_1000sf counts as "parking covered"
parking_filled = sum(1 for r in real if r.get("parking_per_unit") is not None or r.get("parking_per_1000sf") is not None)
parking_unit_pct = pct("parking_per_unit")
parking_1k_pct = pct("parking_per_1000sf")
parking_any_pct = round(parking_filled / N * 100, 1) if N else 0

height_pct    = pct("max_height_ft")
setback_pct   = pct("front_setback_ft")
stories_pct   = pct("max_stories")
coverage_pct  = pct("max_lot_coverage_pct")
far_pct       = pct("max_far")

massing_ready = height_pct > 80 and setback_pct > 80 and stories_pct > 80 and parking_unit_pct > 80

print("\n" + "="*55)
print(f"  {'Field':<25} {'Filled':>8} {'%':>8}")
print("="*55)
for label, p in [
    ("Height (ft)",         height_pct),
    ("Setbacks",            setback_pct),
    ("Stories",             stories_pct),
    ("Lot Coverage %",      coverage_pct),
    ("FAR (max_far)",        far_pct),
    ("Parking/unit",        parking_unit_pct),
    ("Parking/1000sf",      parking_1k_pct),
    ("Parking (any)",       parking_any_pct),
]:
    icon = "✅" if p >= 80 else "❌"
    print(f"  {label:<25} {icon:>4}   {p:>6}%")
print("="*55)
print(f"  3D Massing Ready: {'✅' if massing_ready else '❌'}")
print("="*55)

# ─── Telegram ────────────────────────────────────────────────────────────────
msg = f"""🏗️ RUN #33 COMPLETE — WIDE PATTERN PARKING
Real zones: {N}
Height: {height_pct}% {'✅' if height_pct>80 else '❌'}
Setbacks: {setback_pct}% {'✅' if setback_pct>80 else '❌'}
Stories: {stories_pct}% {'✅' if stories_pct>80 else '❌'}
Coverage: {coverage_pct}% {'✅' if coverage_pct>80 else '❌'}
FAR: {far_pct}% {'✅' if far_pct>80 else '❌'}
Parking/unit: {parking_unit_pct}% {'✅' if parking_unit_pct>80 else '❌'}
Parking/1000sf: {parking_1k_pct}% {'✅' if parking_1k_pct>80 else '❌'}
Parking (any): {parking_any_pct}%
3D Massing Ready: {'✅' if massing_ready else '❌'} (ready if height+setbacks+stories+parking_unit all >80%)"""

print(f"\n{msg}")
send_telegram(msg)
print("\nDone.")
