#!/usr/bin/env python3
"""
USE_CODE Gap Fill Final — Melbourne Village (683) + Unincorporated (19,303).

Algorithm:
1. Set-difference for Melbourne Village and unincorporated subcommunities
2. Fetch use_code from sample_properties for each missing parcel
3. Map use_code → zone_code via DOR_UC_MAP
4. Upsert with zone_source=use_code_crosswalk
5. Report COUNT(*) before and after

NEVER-LIE: Reports actual COUNT(*) values.
"""
import httpx, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

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

# jurisdiction_id from sample_properties → (za_jurisdiction, display_name)
# Melbourne Village = jurisdiction_id 15 (need to verify via query)
# Unincorporated subcommunities use jurisdiction_id=0 or null
TARGETS = [
    # (sp_jurisdiction_id_filter, za_jurisdiction, display_name)
    # Melbourne Village
    ("jurisdiction_id=eq.15", "melbourne_village", "Melbourne Village"),
    # Unincorporated subcommunities — stored as various jurisdiction values in ZA
    # We fetch all unincorporated from SP (jurisdiction_id=0 or null)
    # and diff against all unincorporated ZA entries
]

# Unincorporated ZA jurisdictions to check
UNINC_ZA_VALUES = [
    "unincorporated", "merritt_island", "mims", "barefoot_bay", "micco", "fellsmere"
]

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


def fetch_pids(table, filter_str):
    pids = set()
    offset = 0
    page_size = 1000
    h = sb_headers()
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=parcel_id&{filter_str}&offset={offset}&limit={page_size}"
        try:
            resp = client.get(url, headers=h)
            data = resp.json()
            if not isinstance(data, list) or not data:
                break
            for r in data:
                pid = r.get("parcel_id")
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


def fetch_pids_multi_filter(table, filter_list):
    """Fetch pids matching any of the filters (OR via multiple requests, then union)."""
    all_pids = set()
    for f in filter_list:
        pids = fetch_pids(table, f)
        print(f"  {f}: {len(pids):,} pids", flush=True)
        all_pids |= pids
    return all_pids


def fetch_sp_use_codes(parcel_ids_list):
    """Fetch use_code for parcel_ids from sample_properties."""
    data = {}
    h = sb_headers()
    for i in range(0, len(parcel_ids_list), 100):
        batch = parcel_ids_list[i:i+100]
        id_filter = ",".join(batch)
        url = f"{SUPABASE_URL}/rest/v1/sample_properties?select=parcel_id,use_code&parcel_id=in.({id_filter})"
        try:
            resp = client.get(url, headers=h)
            rows = resp.json()
            if isinstance(rows, list):
                for r in rows:
                    pid = str(r.get("parcel_id", ""))
                    if pid:
                        data[pid] = str(r.get("use_code") or "").strip()
        except Exception as e:
            print(f"  [sp use_code fetch error] {e}", file=sys.stderr)
        time.sleep(0.1)
    return data


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


def discover_jurisdiction_id(display_name):
    """Query sample_properties to find the jurisdiction_id for a given city name."""
    h = sb_headers()
    url = f"{SUPABASE_URL}/rest/v1/sample_properties?select=jurisdiction_id,jurisdiction_name&jurisdiction_name=ilike.*{display_name.replace(' ', '%20')}*&limit=1"
    try:
        resp = client.get(url, headers=h)
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("jurisdiction_id")
    except Exception:
        pass
    return None


def get_sp_jurisdiction_ids():
    """Get all jurisdiction_id/name mappings from sample_properties."""
    h = sb_headers()
    url = f"{SUPABASE_URL}/rest/v1/sample_properties?select=jurisdiction_id,jurisdiction_name&limit=1000"
    try:
        resp = client.get(url, headers=h)
        data = resp.json()
        if isinstance(data, list):
            jmap = {}
            for r in data:
                jid = r.get("jurisdiction_id")
                jname = r.get("jurisdiction_name", "")
                if jid is not None:
                    jmap[jid] = jname
            return jmap
    except Exception as e:
        print(f"  [jmap error] {e}", file=sys.stderr)
    return {}


def main():
    start_time = __import__("time").time()
    telegram("🏔️ USE_CODE GAP FILL FINAL: Melbourne Village + Unincorporated")

    # BEFORE count
    before_total = sb_count("zoning_assignments", "county=eq.brevard")
    telegram(f"📊 BEFORE: zoning_assignments brevard total={before_total:,}")

    # Discover jurisdiction IDs
    print("Discovering jurisdiction IDs from sample_properties...", flush=True)
    jmap = get_sp_jurisdiction_ids()
    print(f"  Found {len(jmap)} jurisdiction mappings", flush=True)

    # Find Melbourne Village jurisdiction_id
    mel_vil_jid = None
    uninc_jids = []
    for jid, jname in jmap.items():
        jname_lower = jname.lower().strip()
        if "melbourne village" in jname_lower:
            mel_vil_jid = jid
            print(f"  Melbourne Village: jurisdiction_id={jid}", flush=True)
        elif any(x in jname_lower for x in ["unincorporat", "merritt island", "mims", "barefoot bay", "micco", "fellsmere"]):
            uninc_jids.append(jid)
            print(f"  Unincorporated ({jname}): jurisdiction_id={jid}", flush=True)

    total_upserted = 0
    results_log = []

    # === Melbourne Village ===
    if mel_vil_jid is not None:
        print(f"\n--- Melbourne Village (jid={mel_vil_jid}) ---", flush=True)
        sp_pids = fetch_pids("sample_properties", f"jurisdiction_id=eq.{mel_vil_jid}")
        za_pids = fetch_pids("zoning_assignments", "jurisdiction=eq.melbourne_village")
        missing = list(sp_pids - za_pids)
        print(f"  SP={len(sp_pids):,} ZA={len(za_pids):,} missing={len(missing):,}", flush=True)

        if missing:
            use_codes = fetch_sp_use_codes(missing)
            rows = []
            for pid in missing:
                zone = map_use_code(use_codes.get(pid, ""))
                if zone:
                    rows.append({
                        "parcel_id": pid,
                        "zone_code": zone,
                        "jurisdiction": "melbourne_village",
                        "county": "brevard",
                        "zone_source": "use_code_crosswalk",
                    })
            upserted = sb_upsert(rows) if rows else 0
            total_upserted += upserted
            results_log.append(f"  Melbourne Village: {len(sp_pids):,} SP, {len(za_pids):,} ZA, {len(missing):,} missing → {upserted:,} upserted")
            telegram(f"🏔️ Melbourne Village: +{upserted:,} upserted ({len(missing):,} was missing)")
    else:
        print("  WARNING: Could not find Melbourne Village jurisdiction_id", flush=True)
        # Fallback: try jurisdiction_id=15 as per plan
        sp_pids = fetch_pids("sample_properties", "jurisdiction_id=eq.15")
        if sp_pids:
            za_pids = fetch_pids("zoning_assignments", "jurisdiction=eq.melbourne_village")
            missing = list(sp_pids - za_pids)
            print(f"  (fallback jid=15) SP={len(sp_pids):,} ZA={len(za_pids):,} missing={len(missing):,}", flush=True)
            if missing:
                use_codes = fetch_sp_use_codes(missing)
                rows = []
                for pid in missing:
                    zone = map_use_code(use_codes.get(pid, ""))
                    if zone:
                        rows.append({
                            "parcel_id": pid,
                            "zone_code": zone,
                            "jurisdiction": "melbourne_village",
                            "county": "brevard",
                            "zone_source": "use_code_crosswalk",
                        })
                upserted = sb_upsert(rows) if rows else 0
                total_upserted += upserted
                results_log.append(f"  Melbourne Village (jid=15): +{upserted:,} upserted")
                telegram(f"🏔️ Melbourne Village (jid=15): +{upserted:,}")

    # === Unincorporated Brevard ===
    print(f"\n--- Unincorporated Brevard ---", flush=True)
    # Get all unincorporated SP parcel_ids
    if uninc_jids:
        sp_uninc_pids = set()
        for jid in uninc_jids:
            pids = fetch_pids("sample_properties", f"jurisdiction_id=eq.{jid}")
            print(f"  jid={jid}: {len(pids):,} parcels", flush=True)
            sp_uninc_pids |= pids
    else:
        # Fallback: assume jurisdiction_id=0 for unincorporated
        print("  No unincorporated jids found, trying jid=0...", flush=True)
        sp_uninc_pids = fetch_pids("sample_properties", "jurisdiction_id=eq.0")

    # Get all unincorporated ZA parcel_ids (from all 6 sub-values)
    za_uninc_pids = set()
    for jval in UNINC_ZA_VALUES:
        pids = fetch_pids("zoning_assignments", f"jurisdiction=eq.{jval}")
        print(f"  ZA {jval}: {len(pids):,}", flush=True)
        za_uninc_pids |= pids

    missing_uninc = list(sp_uninc_pids - za_uninc_pids)
    print(f"  SP uninc={len(sp_uninc_pids):,} ZA uninc={len(za_uninc_pids):,} missing={len(missing_uninc):,}", flush=True)
    telegram(f"🔍 Uninc: {len(sp_uninc_pids):,} SP, {len(za_uninc_pids):,} ZA, {len(missing_uninc):,} missing")

    if missing_uninc:
        # Fetch use_codes for missing
        print(f"  Fetching use_codes for {len(missing_uninc):,} missing uninc parcels...", flush=True)
        use_codes = fetch_sp_use_codes(missing_uninc)
        rows = []
        for pid in missing_uninc:
            zone = map_use_code(use_codes.get(pid, ""))
            if zone:
                rows.append({
                    "parcel_id": pid,
                    "zone_code": zone,
                    "jurisdiction": "unincorporated_brevard",
                    "county": "brevard",
                    "zone_source": "use_code_crosswalk",
                })
        upserted = sb_upsert(rows) if rows else 0
        total_upserted += upserted
        results_log.append(f"  Unincorporated: {len(sp_uninc_pids):,} SP, {len(za_uninc_pids):,} ZA, {len(missing_uninc):,} missing → {upserted:,} upserted")
        telegram(f"🏔️ Unincorporated: +{upserted:,} upserted")

    # AFTER count
    import time as _time
    _time.sleep(2)
    after_total = sb_count("zoning_assignments", "county=eq.brevard")
    elapsed = int(__import__("time").time() - start_time)

    results_text = "\n".join(results_log) if results_log else "  (no gaps found)"

    telegram(f"""🏔️ USE_CODE GAP FILL FINAL COMPLETE

📊 RESULTS:
{results_text}
  Total upserted: {total_upserted:,}

📈 COUNT(*):
  BEFORE: {before_total:,}
  AFTER:  {after_total:,}
  Delta: +{after_total - before_total:,}

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")


if __name__ == "__main__":
    main()
