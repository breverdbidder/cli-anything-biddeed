#!/usr/bin/env python3
"""
Melbourne Gap Fill v2 — fill the 10,626 missing Melbourne parcels.

Algorithm:
1. Fetch all Melbourne parcel_ids from sample_properties (jurisdiction_id=1, ~62,134)
2. Fetch all Melbourne parcel_ids from zoning_assignments (jurisdiction=melbourne, ~51,508)
3. Python set difference = missing parcel_ids
4. For each missing: fetch tax_account from sample_properties
5. Query Melbourne GIS by TaxAcct → get ZONE_ALL
6. Fallback: USE_CODE crosswalk from sample_properties.use_code
7. Upsert to zoning_assignments with zone_source
8. Report COUNT(*) before and after

NEVER-LIE: Reports actual COUNT(*) values, not estimates.
"""
import httpx, os, sys, time, json
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

MEL_GIS = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/128"

USE_CODE_MAP = {
    "00": "VAC-RES", "01": "SFR", "02": "MH", "03": "MFR-10",
    "04": "MFR-CONDO", "05": "COOP", "06": "RETIRE", "07": "MISC-RES",
    "08": "MFR", "09": "RES-COMMON", "10": "VAC-COM", "11": "RETAIL",
    "12": "MIXED-USE", "13": "DEPT-STORE", "14": "SUPER", "15": "REGIONAL",
    "16": "COMM-PARK", "17": "OFFICE", "18": "PROF-SVC", "19": "HOTEL",
    "20": "VAC-IND", "21": "LIGHT-IND", "22": "HEAVY-IND", "23": "LUMBER",
    "24": "PACKING", "25": "MINING", "26": "UTIL", "27": "AUTO-SVC",
    "28": "PARKING", "29": "WHOLESALE", "30": "VAC-AG", "31": "CROP",
    "32": "PASTURE", "33": "TIMBER", "34": "DAIRY", "35": "BEE",
    "36": "NURSERY", "37": "ORCHARD", "38": "POULTRY", "39": "AG-OTHER",
    "40": "VAC-INST", "41": "CHURCH", "42": "PRIVATE-SCHOOL",
    "43": "PRIVATE-HOSP", "44": "NURSING", "48": "CEMETERIES",
    "50": "GOV-OTHER", "70": "CHURCH", "71": "CHURCH", "72": "EDUCATION",
    "73": "HOSPITAL", "74": "NURSING-EX", "77": "MISC-EXEMPT",
    "80": "GOV-MUNI", "81": "GOV-COUNTY", "82": "GOV-STATE",
    "83": "GOV-FED", "84": "GOV-MILITARY", "85": "GOV-FOREST",
    "86": "SCHOOL-PUB", "87": "COLLEGE", "88": "HOSPITAL-PUB",
    "89": "GOV-OTHER", "90": "LEASEHOLD", "91": "UTIL-ELECT",
    "92": "UTIL-GAS", "93": "UTIL-PHONE", "94": "UTIL-WATER",
    "95": "RIGHTS", "96": "WATER-MGMT", "97": "OUTDOOR-REC",
    "98": "MINING-MIN", "99": "ACREAGE",
}

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})


def telegram(msg):
    print(msg)
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}, timeout=10)
        except Exception as e:
            print(f"  [telegram error] {e}", file=sys.stderr)


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def sb_count(table, filter_str=""):
    h = sb_headers()
    h["Prefer"] = "count=exact"
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=parcel_id&limit=0"
    if filter_str:
        url += f"&{filter_str}"
    resp = client.get(url, headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr and cr.split("/")[1] != "*" else -1


def fetch_all_parcel_ids(table, filter_str, id_field="parcel_id"):
    """Paginate through table and collect all IDs."""
    pids = set()
    offset = 0
    page_size = 1000
    h = sb_headers()
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={id_field}&{filter_str}&offset={offset}&limit={page_size}"
        try:
            resp = client.get(url, headers=h)
            data = resp.json()
            if not isinstance(data, list) or not data:
                break
            for r in data:
                pid = r.get(id_field)
                if pid:
                    pids.add(str(pid))
            if len(data) < page_size:
                break
            offset += page_size
            if offset % 10000 == 0:
                print(f"  fetched {offset:,} from {table}...", flush=True)
            time.sleep(0.2)
        except Exception as e:
            print(f"  [fetch error at {offset}] {e}", file=sys.stderr)
            time.sleep(3)
            break
    return pids


def fetch_melbourne_sp_data(parcel_ids_list):
    """Fetch tax_account + use_code for given parcel_ids from sample_properties."""
    data = {}
    h = sb_headers()
    for i in range(0, len(parcel_ids_list), 100):
        batch_ids = parcel_ids_list[i:i+100]
        id_filter = ",".join(batch_ids)
        url = f"{SUPABASE_URL}/rest/v1/sample_properties?select=parcel_id,tax_account,use_code&parcel_id=in.({id_filter})"
        try:
            resp = client.get(url, headers=h)
            rows = resp.json()
            if isinstance(rows, list):
                for r in rows:
                    pid = str(r.get("parcel_id", ""))
                    if pid:
                        data[pid] = {
                            "tax_account": str(r.get("tax_account") or "").strip(),
                            "use_code": str(r.get("use_code") or "").strip(),
                        }
        except Exception as e:
            print(f"  [sp fetch error] {e}", file=sys.stderr)
        time.sleep(0.1)
    return data


def query_melbourne_gis_bulk(tax_accounts):
    """Query Melbourne GIS for a batch of TaxAcct values. Returns {tax_acct: zone_code}."""
    if not tax_accounts:
        return {}
    results = {}
    # Build IN clause
    quoted = ",".join(f"'{t}'" for t in tax_accounts if t)
    if not quoted:
        return {}
    where = f"TaxAcct IN ({quoted})"
    try:
        resp = client.get(f"{MEL_GIS}/query", params={
            "where": where,
            "outFields": "TaxAcct,ZONE_ALL",
            "returnGeometry": "false",
            "resultRecordCount": "1000",
            "f": "json",
        })
        data = resp.json()
        if data.get("error"):
            return {}
        for f in data.get("features", []):
            a = f.get("attributes", {})
            tax = str(a.get("TaxAcct") or "").strip()
            zone = str(a.get("ZONE_ALL") or "").strip()
            if tax and zone:
                results[tax] = zone
    except Exception as e:
        print(f"  [GIS error] {e}", file=sys.stderr)
    return results


def map_use_code(use_code):
    if not use_code or len(use_code) < 2:
        return None
    return USE_CODE_MAP.get(use_code[:2], f"UC-{use_code[:2]}")


def sb_upsert(rows):
    h = sb_headers()
    total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
            headers=h, json=batch
        )
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"  [upsert error] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total


def main():
    start = time.time()
    telegram("🏔️ MELBOURNE GAP FILL v2: Starting...")

    # BEFORE count
    before = sb_count("zoning_assignments", "county=eq.brevard")
    mel_before = sb_count("zoning_assignments", "jurisdiction=eq.melbourne")
    telegram(f"📊 BEFORE: zoning_assignments total={before:,} | melbourne={mel_before:,}")

    # Step 1: Get all Melbourne parcel_ids from sample_properties (jurisdiction_id=1)
    print("Fetching Melbourne parcel_ids from sample_properties...", flush=True)
    sp_pids = fetch_all_parcel_ids("sample_properties", "jurisdiction_id=eq.1")
    print(f"  sample_properties Melbourne: {len(sp_pids):,}", flush=True)

    # Step 2: Get all Melbourne parcel_ids from zoning_assignments
    print("Fetching Melbourne parcel_ids from zoning_assignments...", flush=True)
    za_pids = fetch_all_parcel_ids("zoning_assignments", "jurisdiction=eq.melbourne")
    print(f"  zoning_assignments Melbourne: {len(za_pids):,}", flush=True)

    # Step 3: Set difference
    missing_pids = list(sp_pids - za_pids)
    print(f"  Missing: {len(missing_pids):,}", flush=True)
    telegram(f"🔍 Melbourne gap: {len(sp_pids):,} in BCPAO, {len(za_pids):,} in zoning → {len(missing_pids):,} missing")

    if not missing_pids:
        telegram("✅ No gap found. Melbourne already complete.")
        return

    # Step 4: Fetch tax_account + use_code for missing parcels
    print(f"Fetching SP data for {len(missing_pids):,} missing parcels...", flush=True)
    sp_data = fetch_melbourne_sp_data(missing_pids)
    print(f"  Got SP data for {len(sp_data):,} parcels", flush=True)

    # Step 5: Query Melbourne GIS in batches of 50 (URL length limit)
    gis_matched = {}
    tax_to_pid = {}
    # Build reverse map: tax_account → parcel_id
    for pid in missing_pids:
        d = sp_data.get(pid, {})
        tax = d.get("tax_account", "")
        if tax:
            tax_to_pid[tax] = pid

    tax_accounts = list(tax_to_pid.keys())
    print(f"Querying Melbourne GIS for {len(tax_accounts):,} tax accounts...", flush=True)
    gis_zone_by_tax = {}
    batch_size = 50
    for i in range(0, len(tax_accounts), batch_size):
        batch = tax_accounts[i:i+batch_size]
        result = query_melbourne_gis_bulk(batch)
        gis_zone_by_tax.update(result)
        if i % 500 == 0 and i > 0:
            print(f"  GIS queried {i:,}/{len(tax_accounts):,}, matched {len(gis_zone_by_tax):,}", flush=True)
        time.sleep(0.5)

    print(f"  GIS matched: {len(gis_zone_by_tax):,} / {len(tax_accounts):,}", flush=True)

    # Step 6: Build upsert rows
    rows = []
    gis_count = 0
    usecode_count = 0
    skipped = 0

    for pid in missing_pids:
        d = sp_data.get(pid, {})
        tax = d.get("tax_account", "")
        use_code = d.get("use_code", "")

        zone = None
        source = None

        # Try GIS match
        if tax and tax in gis_zone_by_tax:
            zone = gis_zone_by_tax[tax]
            source = "melbourne_gis"
            gis_count += 1
        else:
            # Fallback: USE_CODE crosswalk
            zone = map_use_code(use_code)
            if zone:
                source = "use_code_crosswalk"
                usecode_count += 1

        if zone:
            row = {
                "parcel_id": pid,
                "zone_code": zone,
                "jurisdiction": "melbourne",
                "county": "brevard",
                "zone_source": source,
            }
            # Only include co_no if column exists (migration may not be done yet)
            rows.append(row)
        else:
            skipped += 1

    print(f"  Rows to upsert: {len(rows):,} (gis={gis_count}, usecode={usecode_count}, skipped={skipped})", flush=True)
    telegram(f"🏗️ Melbourne: {len(rows):,} rows ready (GIS={gis_count:,}, USE_CODE={usecode_count:,}, skipped={skipped})")

    # Step 7: Upsert
    if rows:
        upserted = sb_upsert(rows)
        print(f"  Upserted: {upserted:,}", flush=True)
    else:
        upserted = 0

    # AFTER count
    time.sleep(2)
    after = sb_count("zoning_assignments", "county=eq.brevard")
    mel_after = sb_count("zoning_assignments", "jurisdiction=eq.melbourne")
    elapsed = int(time.time() - start)

    telegram(f"""🏔️ MELBOURNE GAP FILL v2 COMPLETE

📊 RESULTS:
  Missing parcel_ids found: {len(missing_pids):,}
  GIS matched: {gis_count:,}
  USE_CODE fallback: {usecode_count:,}
  Skipped (no zone): {skipped}
  Upserted: {upserted:,}

📈 COUNT(*):
  BEFORE: brevard total={before:,} | melbourne={mel_before:,}
  AFTER:  brevard total={after:,} | melbourne={mel_after:,}
  Delta: +{after-before:,}

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")


if __name__ == "__main__":
    main()
