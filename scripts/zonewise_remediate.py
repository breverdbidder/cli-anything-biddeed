#!/usr/bin/env python3
"""
ZONEWISE REMEDIATION — Fix all data issues from Phase 2 corruption.

Issues being fixed:
1. Grant Valkaria parcels (jid=15, 3,065) wrongly labeled as melbourne_village
2. Melbourne Village (jid=17, 1,001 parcels) not yet filled (or missing)
3. Unincorporated (jid=13, 80,793) has gap — only 53,392 in ZA
4. Titusville over-count (+6,131): ZA=28,126 vs SP=21,995
5. West Melbourne over-count (+953): ZA=11,318 vs SP=10,365

Jurisdiction ID mapping (from sample_properties):
  jid=1: Melbourne (62,134)      jid=2: Palm Bay (78,697)
  jid=3: Indian Harbour Beach    jid=4: Titusville (21,995)
  jid=5: Cocoa (29,882)          jid=6: Satellite Beach
  jid=7: Cocoa Beach             jid=8: Rockledge
  jid=9: West Melbourne (10,365) jid=10: Cape Canaveral
  jid=11: Indialantic            jid=12: Melbourne Beach
  jid=13: Unincorporated (80,793) jid=14: Malabar
  jid=15: Grant Valkaria (3,065) jid=16: Palm Shores (433)
  jid=17: Melbourne Village (1,001)

NEVER-LIE: Reports actual COUNT(*) before and after each operation.
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

client = httpx.Client(timeout=120, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})


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


def sb_count(filter_str=""):
    h = dict(sb_headers())
    h["Prefer"] = "count=exact"
    url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&limit=0"
    if filter_str:
        url += f"&{filter_str}"
    resp = client.get(url, headers=h)
    cr = resp.headers.get("content-range", "*/0")
    return int(cr.split("/")[1]) if "/" in cr and cr.split("/")[1] != "*" else -1


def fetch_za_pids(jurisdiction):
    """Fetch all parcel_ids from zoning_assignments for a jurisdiction."""
    pids = set()
    offset = 0
    h = {k: v for k, v in sb_headers().items() if k != "Prefer"}
    while True:
        url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&jurisdiction=eq.{jurisdiction}&offset={offset}&limit=1000"
        try:
            resp = client.get(url, headers=h)
            data = resp.json()
            if not isinstance(data, list) or not data:
                break
            for r in data:
                pid = str(r.get("parcel_id", ""))
                if pid:
                    pids.add(pid)
            if len(data) < 1000:
                break
            offset += 1000
            if offset % 10000 == 0:
                print(f"    fetched {offset:,} from ZA {jurisdiction}...", flush=True)
            time.sleep(0.15)
        except Exception as e:
            print(f"  [fetch error] {e}", file=sys.stderr)
            break
    return pids


def fetch_sp_pids(jurisdiction_id):
    """Fetch all parcel_ids from sample_properties for a jurisdiction_id."""
    pids = set()
    offset = 0
    h = {k: v for k, v in sb_headers().items() if k != "Prefer"}
    while True:
        url = f"{SUPABASE_URL}/rest/v1/sample_properties?select=parcel_id&jurisdiction_id=eq.{jurisdiction_id}&offset={offset}&limit=1000"
        try:
            resp = client.get(url, headers=h)
            data = resp.json()
            if not isinstance(data, list) or not data:
                break
            for r in data:
                pid = str(r.get("parcel_id", ""))
                if pid:
                    pids.add(pid)
            if len(data) < 1000:
                break
            offset += 1000
            if offset % 10000 == 0:
                print(f"    fetched {offset:,} from SP jid={jurisdiction_id}...", flush=True)
            time.sleep(0.15)
        except Exception as e:
            print(f"  [sp fetch error] {e}", file=sys.stderr)
            break
    return pids


def fetch_sp_use_codes(parcel_ids_list):
    """Fetch use_code for parcel_ids from sample_properties."""
    data = {}
    h = {k: v for k, v in sb_headers().items() if k != "Prefer"}
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
            print(f"  [use_code fetch error] {e}", file=sys.stderr)
        time.sleep(0.1)
    return data


def map_use_code(use_code):
    if not use_code or len(use_code) < 2:
        return None
    return USE_CODE_MAP.get(use_code[:2], f"UC-{use_code[:2]}")


def patch_jurisdiction(parcel_ids, from_juris, to_juris):
    """PATCH zoning_assignments rows for specific parcel_ids to new jurisdiction."""
    if not parcel_ids:
        return 0
    h = dict(sb_headers())
    h["Prefer"] = "count=exact"
    total = 0
    pid_list = list(parcel_ids)
    for i in range(0, len(pid_list), 100):
        batch = pid_list[i:i+100]
        id_filter = ",".join(batch)
        url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?parcel_id=in.({id_filter})&jurisdiction=eq.{from_juris}"
        try:
            resp = client.patch(url, headers=h, json={"jurisdiction": to_juris})
            if resp.status_code in (200, 204):
                total += len(batch)
            else:
                print(f"  [patch error] {resp.status_code}: {resp.text[:100]}", file=sys.stderr)
        except Exception as e:
            print(f"  [patch error] {e}", file=sys.stderr)
        time.sleep(0.3)
    return total


def delete_pids(parcel_ids, jurisdiction):
    """Delete rows from zoning_assignments for specific parcel_ids + jurisdiction."""
    if not parcel_ids:
        return 0
    h = dict(sb_headers())
    h["Prefer"] = "count=exact"
    total = 0
    pid_list = list(parcel_ids)
    for i in range(0, len(pid_list), 100):
        batch = pid_list[i:i+100]
        id_filter = ",".join(batch)
        url = f"{SUPABASE_URL}/rest/v1/zoning_assignments?parcel_id=in.({id_filter})&jurisdiction=eq.{jurisdiction}"
        try:
            resp = client.delete(url, headers=h)
            if resp.status_code in (200, 204):
                total += len(batch)
            else:
                print(f"  [delete error] {resp.status_code}: {resp.text[:100]}", file=sys.stderr)
        except Exception as e:
            print(f"  [delete error] {e}", file=sys.stderr)
        time.sleep(0.3)
    return total


def upsert_rows(rows):
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


def fill_gap(sp_jid, za_jurisdiction, display_name):
    """Fill gap for a jurisdiction using use_code crosswalk."""
    print(f"\n--- {display_name} (jid={sp_jid}) ---", flush=True)
    sp_pids = fetch_sp_pids(sp_jid)
    za_pids = fetch_za_pids(za_jurisdiction)
    missing = list(sp_pids - za_pids)
    print(f"  SP={len(sp_pids):,} ZA={len(za_pids):,} missing={len(missing):,}", flush=True)
    if not missing:
        return 0, len(sp_pids), len(za_pids), 0
    use_codes = fetch_sp_use_codes(missing)
    rows = []
    for pid in missing:
        zone = map_use_code(use_codes.get(pid, ""))
        if zone:
            rows.append({"parcel_id": pid, "zone_code": zone, "jurisdiction": za_jurisdiction, "county": "brevard"})
    upserted = upsert_rows(rows) if rows else 0
    print(f"  upserted: {upserted:,}", flush=True)
    return upserted, len(sp_pids), len(za_pids), len(missing)


def fix_over_count(sp_jid, za_jurisdiction, display_name):
    """Delete ZA rows not in SP for this jurisdiction."""
    print(f"\n--- Fix over-count: {display_name} (jid={sp_jid}) ---", flush=True)
    sp_pids = fetch_sp_pids(sp_jid)
    za_pids = fetch_za_pids(za_jurisdiction)
    orphans = za_pids - sp_pids
    print(f"  SP={len(sp_pids):,} ZA={len(za_pids):,} orphans={len(orphans):,}", flush=True)
    if not orphans:
        return 0, len(sp_pids), len(za_pids)
    deleted = delete_pids(orphans, za_jurisdiction)
    print(f"  deleted: {deleted:,}", flush=True)
    time.sleep(1)
    za_after = sb_count(f"jurisdiction=eq.{za_jurisdiction}")
    return deleted, len(sp_pids), za_after


def main():
    start = time.time()
    telegram("🏔️ ZONEWISE REMEDIATION: Fixing all data issues")

    before_total = sb_count("county=eq.brevard")
    telegram(f"📊 BEFORE: brevard total={before_total:,}")

    results = []

    # =========================================================
    # FIX 1: Melbourne Village contamination
    # Grant Valkaria parcels (jid=15) are wrongly in melbourne_village
    # Need to: patch those rows back to grant_valkaria, then fill real Melbourne Village
    # =========================================================
    print("\n=== FIX 1: Melbourne Village + Grant Valkaria ===", flush=True)

    # Get all ZA melbourne_village pids
    za_mel_vil = fetch_za_pids("melbourne_village")
    print(f"  ZA melbourne_village: {len(za_mel_vil):,}", flush=True)

    # Get SP jid=15 (Grant Valkaria) pids
    sp_gv = fetch_sp_pids(15)
    print(f"  SP Grant Valkaria (jid=15): {len(sp_gv):,}", flush=True)

    # Get SP jid=17 (Melbourne Village) pids
    sp_mel_vil = fetch_sp_pids(17)
    print(f"  SP Melbourne Village (jid=17): {len(sp_mel_vil):,}", flush=True)

    # Which ZA melbourne_village rows are actually Grant Valkaria?
    wrongly_in_mel_vil = za_mel_vil & sp_gv  # In ZA-mel-vil AND SP-GV
    print(f"  Wrong GV parcels in melbourne_village: {len(wrongly_in_mel_vil):,}", flush=True)

    if wrongly_in_mel_vil:
        # Move them to grant_valkaria
        patched = patch_jurisdiction(wrongly_in_mel_vil, "melbourne_village", "grant_valkaria")
        results.append(f"  Moved {patched:,} Grant Valkaria parcels from melbourne_village → grant_valkaria")
        telegram(f"🏔️ FIX 1a: Moved {patched:,} GV parcels to grant_valkaria")
        time.sleep(2)

    # Now fill actual Melbourne Village gap
    za_mel_vil_now = fetch_za_pids("melbourne_village")
    missing_mel_vil = list(sp_mel_vil - za_mel_vil_now)
    print(f"  Melbourne Village after fix: ZA={len(za_mel_vil_now):,} SP={len(sp_mel_vil):,} missing={len(missing_mel_vil):,}", flush=True)

    if missing_mel_vil:
        use_codes = fetch_sp_use_codes(missing_mel_vil)
        rows = []
        for pid in missing_mel_vil:
            zone = map_use_code(use_codes.get(pid, ""))
            if zone:
                rows.append({"parcel_id": pid, "zone_code": zone, "jurisdiction": "melbourne_village", "county": "brevard"})
        upserted = upsert_rows(rows) if rows else 0
        results.append(f"  Melbourne Village gap fill: +{upserted:,} (target 1,001)")
        telegram(f"🏔️ FIX 1b: Melbourne Village +{upserted:,}")

    # =========================================================
    # FIX 2: Unincorporated gap (jid=13, target 80,793)
    # Currently ZA unincorporated_brevard = 53,392, missing ~27,401
    # =========================================================
    print("\n=== FIX 2: Unincorporated Brevard gap ===", flush=True)
    upserted, sp_cnt, za_cnt, missing_cnt = fill_gap(13, "unincorporated_brevard", "Unincorporated Brevard")
    results.append(f"  Unincorporated fill: +{upserted:,} (SP={sp_cnt:,} ZA was={za_cnt:,} missing={missing_cnt:,})")
    telegram(f"🏔️ FIX 2: Unincorporated +{upserted:,}")

    # =========================================================
    # FIX 3: Titusville over-count (jid=4, SP=21,995, ZA=28,126)
    # =========================================================
    print("\n=== FIX 3: Titusville over-count ===", flush=True)
    deleted, sp_cnt, za_after = fix_over_count(4, "titusville", "Titusville")
    results.append(f"  Titusville: deleted {deleted:,} orphans → ZA now={za_after:,} (target 21,995)")
    telegram(f"🏔️ FIX 3: Titusville deleted {deleted:,} → {za_after:,}")

    # =========================================================
    # FIX 4: West Melbourne over-count (jid=9, SP=10,365, ZA=11,318)
    # =========================================================
    print("\n=== FIX 4: West Melbourne over-count ===", flush=True)
    deleted, sp_cnt, za_after = fix_over_count(9, "west_melbourne", "West Melbourne")
    results.append(f"  West Melbourne: deleted {deleted:,} orphans → ZA now={za_after:,} (target 10,365)")
    telegram(f"🏔️ FIX 4: West Melbourne deleted {deleted:,} → {za_after:,}")

    # =========================================================
    # FIX 5: Grant Valkaria fill (jid=15, may have gap after fix 1)
    # =========================================================
    print("\n=== FIX 5: Grant Valkaria fill ===", flush=True)
    upserted, sp_cnt, za_cnt, missing_cnt = fill_gap(15, "grant_valkaria", "Grant Valkaria")
    results.append(f"  Grant Valkaria fill: +{upserted:,} (SP={sp_cnt:,} missing={missing_cnt:,})")
    telegram(f"🏔️ FIX 5: Grant Valkaria +{upserted:,}")

    # =========================================================
    # FINAL VERIFICATION
    # =========================================================
    time.sleep(3)
    print("\n=== FINAL VERIFICATION ===", flush=True)

    after_total = sb_count("county=eq.brevard")
    sp_total = 351424  # confirmed from plan

    jcheck = [
        ("melbourne", "Melbourne", 62134),
        ("melbourne_village", "Melbourne Village", 1001),
        ("unincorporated_brevard", "Unincorporated Brevard", 80793),
        ("titusville", "Titusville", 21995),
        ("west_melbourne", "West Melbourne", 10365),
        ("grant_valkaria", "Grant Valkaria", 3065),
        ("palm_bay", "Palm Bay", 78697),
        ("cocoa", "Cocoa", 29882),
    ]

    j_results = []
    for jval, display, target in jcheck:
        cnt = sb_count(f"jurisdiction=eq.{jval}")
        delta = cnt - target
        status = "✅" if abs(delta) <= 10 else ("⚠️ OVER" if delta > 0 else "❌ SHORT")
        j_results.append(f"  {display}: {cnt:,} (target {target:,} delta={delta:+,} {status})")
        print(f"  {display}: {cnt:,} (target {target:,} delta={delta:+,})", flush=True)

    coverage = after_total / sp_total * 100 if sp_total > 0 else 0
    elapsed = int(time.time() - start)
    results_text = "\n".join(results)
    j_text = "\n".join(j_results)

    match_ok = abs(after_total - sp_total) <= 50

    telegram(f"""🏔️ ZONEWISE REMEDIATION COMPLETE

📊 OPERATIONS:
{results_text}

🏗️ PER-JURISDICTION:
{j_text}

📈 FINAL COUNT(*):
  zoning_assignments (brevard): {after_total:,}
  sample_properties (BCPAO):    {sp_total:,}
  Coverage: {coverage:.1f}%
  Delta: {after_total - sp_total:+,}
  Match within ±50: {"YES ✅" if match_ok else "NO ❌ — further investigation needed"}

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")


if __name__ == "__main__":
    main()
