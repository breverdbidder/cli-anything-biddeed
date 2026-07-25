#!/usr/bin/env python3
"""
Lee County E+I fix — SHARD-11, dispatch 03ff9ae3-9a64-4179-8345-d6b129a0ed83, run 6354.

Current state (brief): E=88.5% [285/322], I=83.2% [268/322]. Target: both >=95%.

Strategy (learned from all prior Lee sessions):
  1. Live-query the exact current E+I gaps from Supabase.
  2. For E: address-lookup via Lee ArcGIS FeatureServer for any rows that have
     property_address but parcel_id IS NULL.
  3. For I (parcel_zones gap): query ArcGIS by STRAP for all rows with a real
     parcel_id but no parcel_zones row. Insert ONLY where the (jid, zone_code)
     pair already exists in zoning_districts — never fabricate or create a new
     zoning_districts entry on-the-fly (G regression risk).
  4. For I (geo/value gap): query ArcGIS by STRAP for rows missing lat/lng or
     assessed_value, backfill from ArcGIS LATITUDE/LONGITUDE/ASSESSED fields.
  5. NEVER insert a parcel_zones row for a zone code with no zoning_districts
     precedent. Log the skipped cases explicitly (not silently).
  6. Fail-loud invariant: if we get parseable ArcGIS results but zero DB writes
     succeed, raise — do not silently pass.

Key facts from prior sessions:
  - Lee ArcGIS endpoint: services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/
      Lee_County_Parcels/FeatureServer/0/query  (VERIFIED live multiple sessions)
  - ArcGIS STRAP field uses undashed format; our parcel_id uses dashed (XX-XX-XX-XX-XXXXX.XXXXX)
  - Jurisdiction mapping (VERIFIED, with fix for "north fort myers" substring collision):
      cape coral -> 815, bonita springs -> 914, fort myers beach -> 912,
      sanibel -> 942, fort myers -> 929, everything else -> 630 (unincorporated)
      BUT: north fort myers, fort myers shores, alva, bokeelia, lehigh acres,
           st. james city, captiva -> 630 (unincorporated, NOT fort myers city)
  - Source tag: use FRESH never-reused tag (lesson from shard13 session incident)
  - G regression guard: check v_zoning_district_applicability indirectly by checking
      (jid, zone_code) in known zoning_districts — never insert for unknown pairs
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
LEE_ARCGIS = (
    "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/"
    "Lee_County_Parcels/FeatureServer/0/query"
)
SOURCE_TAG = "shard11_run6354_lee_arcgis_20260725"

JURISDICTION_MAP_ORDERED = [
    ("cape coral", 815),
    ("bonita springs", 914),
    ("fort myers beach", 912),
    ("sanibel", 942),
    ("fort myers", 929),
]
UNINCORPORATED_OVERRIDES = [
    "north fort myers", "fort myers shores", "alva", "bokeelia",
    "lehigh acres", "st. james city", "saint james city", "captiva",
    "estero", "matlacha", "pine island",
]


def log(msg, tag="INFO"):
    print(f"[{tag}] {msg}", flush=True)


def get_jid(city):
    if not city:
        return 630
    c = city.strip().lower()
    for key in UNINCORPORATED_OVERRIDES:
        if key in c:
            return 630
    for key, jid in JURISDICTION_MAP_ORDERED:
        if key in c:
            return jid
    return 630


def normalize_strap(parcel_id):
    return parcel_id.replace("-", "").replace(".", "")


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(
        url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(path, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sb_patch(path, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}?{params}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def is_real_parcel_id(pid):
    if not pid:
        return False
    pid_stripped = pid.strip().lower()
    bad = ["property appraiser", "multiple parcel", "multiple", "address on file", "n/a"]
    if pid_stripped in bad:
        return False
    import re
    return bool(re.search(r"\d", pid))


def query_arcgis_by_straps(straps):
    if not straps:
        return {}
    norm_straps = [normalize_strap(s) for s in straps]
    in_clause = ",".join(f"'{s}'" for s in norm_straps)
    where = f"STRAP IN ({in_clause})"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 2000,
    })
    req = urllib.request.Request(
        f"{LEE_ARCGIS}?{params}",
        headers={"User-Agent": "BidDeed-SHARD11-run6354"},
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            data = json.loads(resp.read())
        result = {}
        for f in data.get("features", []):
            a = f.get("attributes", {})
            if a.get("STRAP"):
                result[a["STRAP"]] = a
        return result
    except Exception as e:
        log(f"ArcGIS STRAP batch error: {e}", "ERROR")
        return {}


def query_arcgis_by_address(siteaddr):
    parts = siteaddr.split(",")[0].strip().upper()
    if len(parts) < 5:
        return None
    where = f"SITEADDR LIKE '{parts}%'"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 5,
    })
    req = urllib.request.Request(
        f"{LEE_ARCGIS}?{params}",
        headers={"User-Agent": "BidDeed-SHARD11-run6354"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        return feats[0].get("attributes", {}) if feats else None
    except Exception as e:
        log(f"ArcGIS address error ({siteaddr[:40]}): {e}", "WARN")
        return None


def format_strap(strap):
    s = strap
    if len(s) == 18:
        return f"{s[0:2]}-{s[2:4]}-{s[4:6]}-{s[6:8]}-{s[8:13]}.{s[13:18]}"
    return s


def main():
    log("=== Lee County E+I fix — SHARD-11 run6354 ===", "START")

    lee_jids = "(630,815,914,912,929,942)"

    # ── Step 1: Load known zoning_districts (jid, code) ───────────────────
    log("Step 1: load known zoning_districts for Lee jurisdictions", "INFO")
    zd_rows = sb_get(
        "zoning_districts",
        f"jurisdiction_id=in.{lee_jids}&select=jurisdiction_id,code,id&limit=2000"
    )
    known_codes = {(r["jurisdiction_id"], r["code"]): r["id"] for r in zd_rows}
    log(f"  known zoning_district (jid,code) pairs: {len(known_codes)}", "VERIFIED")

    # ── Step 2: Load existing parcel_zones for Lee ─────────────────────────
    log("Step 2: load existing parcel_zones for Lee", "INFO")
    existing_pz_rows = sb_get(
        "parcel_zones",
        f"jurisdiction_id=in.{lee_jids}&select=parcel_id&limit=5000"
    )
    existing_pz_set = {r["parcel_id"] for r in existing_pz_rows}
    log(f"  existing parcel_zones count: {len(existing_pz_set)}", "VERIFIED")

    # ── Step 3: Load all in-scope Lee auctions (exclude propertyonion) ─────
    log("Step 3: load Lee in-scope auctions", "INFO")
    mca_rows = sb_get(
        "multi_county_auctions",
        "county=eq.lee"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value"
        "&limit=2000"
    )
    log(f"  total in-scope lee rows: {len(mca_rows)}", "VERIFIED")

    # ── Step 4: Classify gaps ─────────────────────────────────────────────
    e_gap_has_address = []    # parcel_id IS NULL but has property_address
    e_gap_no_address = []     # parcel_id IS NULL and no address (hard remainder)
    i_gap_needs_pz = []       # real parcel_id but no parcel_zones row
    i_gap_needs_geo = []      # has parcel_id + parcel_zones but missing lat/lng
    i_gap_needs_val = []      # has parcel_id but missing assessed/market value

    for row in mca_rows:
        pid = row.get("parcel_id")
        addr = row.get("property_address")
        lat = row.get("latitude")
        lng = row.get("longitude")
        assessed = row.get("assessed_value")
        market = row.get("market_value")

        if not is_real_parcel_id(pid):
            if addr and len(addr.strip()) > 5:
                e_gap_has_address.append(row)
            else:
                e_gap_no_address.append(row)
        else:
            if pid not in existing_pz_set:
                i_gap_needs_pz.append(row)
            if not lat or not lng:
                i_gap_needs_geo.append(row)
            if not assessed and not market:
                i_gap_needs_val.append(row)

    log(f"E gap: {len(e_gap_has_address)} rows have address, {len(e_gap_no_address)} rows have no address (hard remainder)", "VERIFIED")
    log(f"I gap: {len(i_gap_needs_pz)} rows need parcel_zones, {len(i_gap_needs_geo)} need geo, {len(i_gap_needs_val)} need value", "VERIFIED")

    # ── Step 5: E fix — address-based ArcGIS lookup ───────────────────────
    e_resolved = 0
    e_pz_inserted_via_addr = 0
    log(f"\nStep 5: E fix — address lookups for {len(e_gap_has_address)} rows", "INFO")
    for row in e_gap_has_address:
        addr = row["property_address"].strip()
        attrs = query_arcgis_by_address(addr)
        if not attrs or not attrs.get("STRAP"):
            log(f"  E-addr no match: {row['case_number']} / '{addr[:50]}'", "WARN")
            time.sleep(0.2)
            continue
        strap = attrs["STRAP"]
        formatted_pid = format_strap(strap)
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)
        zoning = (attrs.get("ZONING") or "").strip()
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")

        patch = {"parcel_id": formatted_pid}
        if lat and lng and not row.get("latitude"):
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed and not row.get("assessed_value") and not row.get("market_value"):
            patch["assessed_value"] = assessed

        status, resp = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch)
        if status in (200, 204):
            e_resolved += 1
            log(f"  E-addr resolved: {row['case_number']} -> {formatted_pid} (zone={zoning}, jid={jid})", "VERIFIED")
            if zoning and (jid, zoning) in known_codes and formatted_pid not in existing_pz_set:
                pz_status, _ = sb_post("parcel_zones", [{
                    "parcel_id": formatted_pid,
                    "jurisdiction_id": jid,
                    "zone_code": zoning,
                    "zone_name": zoning,
                    "source": SOURCE_TAG + "_addr",
                }], prefer="resolution=ignore-duplicates,return=minimal")
                if pz_status in (200, 201):
                    e_pz_inserted_via_addr += 1
                    existing_pz_set.add(formatted_pid)
                    log(f"    parcel_zones inserted for {formatted_pid}", "VERIFIED")
        else:
            log(f"  E-addr patch FAILED: {row['case_number']} ({status}): {resp[:100]}", "ERROR")
        time.sleep(0.25)

    log(f"E address fix: {e_resolved}/{len(e_gap_has_address)} resolved, {e_pz_inserted_via_addr} parcel_zones added", "RESULT")

    # ── Step 6: I fix — STRAP-based ArcGIS lookup for parcel_zones gaps ──
    log(f"\nStep 6: I fix — STRAP lookup for {len(i_gap_needs_pz)} rows needing parcel_zones", "INFO")

    # Gather all STRAPs
    strap_to_row = {}
    for row in i_gap_needs_pz:
        if row["parcel_id"] not in existing_pz_set:
            strap_norm = normalize_strap(row["parcel_id"])
            strap_to_row[strap_norm] = row

    log(f"  unique STRAPs to look up: {len(strap_to_row)}", "INFO")

    all_straps_norm = list(strap_to_row.keys())
    arcgis_data_pz = {}
    BATCH = 40
    for i in range(0, len(all_straps_norm), BATCH):
        batch = all_straps_norm[i:i + BATCH]
        result = query_arcgis_by_straps([s for s in batch])
        arcgis_data_pz.update(result)
        log(f"  PZ STRAP batch {i}-{i+len(batch)}: {len(result)}/{len(batch)} found", "INFO")
        time.sleep(0.4)

    pz_inserts = []
    pz_skipped_no_zd = []
    pz_skipped_no_zoning = []

    for strap_norm, attrs in arcgis_data_pz.items():
        row = strap_to_row.get(strap_norm)
        if not row:
            continue
        pid = row["parcel_id"]
        if pid in existing_pz_set:
            continue
        zoning = (attrs.get("ZONING") or "").strip()
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)

        if not zoning:
            pz_skipped_no_zoning.append((row["case_number"], pid, city))
            continue

        if (jid, zoning) not in known_codes:
            pz_skipped_no_zd.append((row["case_number"], pid, zoning, jid))
            continue

        pz_inserts.append({
            "parcel_id": pid,
            "jurisdiction_id": jid,
            "zone_code": zoning,
            "zone_name": zoning,
            "source": SOURCE_TAG,
        })

    log(f"  parcel_zones to insert (known codes only): {len(pz_inserts)}", "VERIFIED")
    if pz_skipped_no_zd:
        log(f"  SKIPPED (no zoning_districts precedent, NOT fabricated): {len(pz_skipped_no_zd)}", "WARN")
        for s in pz_skipped_no_zd:
            log(f"    {s}", "WARN")
    if pz_skipped_no_zoning:
        log(f"  SKIPPED (ArcGIS returned empty ZONING): {len(pz_skipped_no_zoning)}", "WARN")
        for s in pz_skipped_no_zoning:
            log(f"    {s}", "WARN")

    pz_inserted = 0
    CHUNK = 80
    for i in range(0, len(pz_inserts), CHUNK):
        chunk = pz_inserts[i:i + CHUNK]
        status, resp = sb_post("parcel_zones", chunk, prefer="resolution=ignore-duplicates,return=minimal")
        if status in (200, 201):
            pz_inserted += len(chunk)
            for row_insert in chunk:
                existing_pz_set.add(row_insert["parcel_id"])
        else:
            log(f"  parcel_zones insert FAILED ({status}): {resp[:200]}", "ERROR")
        time.sleep(0.3)

    log(f"parcel_zones inserted: {pz_inserted}/{len(pz_inserts)}", "RESULT")

    # ── Step 7: I fix — geo/value backfill for rows missing lat/lng or value ──
    log(f"\nStep 7: I fix — geo/value backfill for rows missing lat/lng or value", "INFO")

    geo_val_rows = i_gap_needs_geo + [
        r for r in i_gap_needs_val
        if r not in i_gap_needs_geo
    ]
    geo_val_rows_deduped = {r["id"]: r for r in geo_val_rows}.values()

    strap_to_geo_row = {}
    for row in geo_val_rows_deduped:
        if is_real_parcel_id(row.get("parcel_id")):
            strap_norm = normalize_strap(row["parcel_id"])
            strap_to_geo_row[strap_norm] = row

    log(f"  unique STRAPs for geo/value backfill: {len(strap_to_geo_row)}", "INFO")

    all_geo_straps = list(strap_to_geo_row.keys())
    arcgis_data_geo = {}
    for i in range(0, len(all_geo_straps), BATCH):
        batch = all_geo_straps[i:i + BATCH]
        result = query_arcgis_by_straps([s for s in batch])
        arcgis_data_geo.update(result)
        log(f"  GEO STRAP batch {i}-{i+len(batch)}: {len(result)}/{len(batch)} found", "INFO")
        time.sleep(0.4)

    geo_updates = 0
    val_updates = 0
    for strap_norm, attrs in arcgis_data_geo.items():
        row = strap_to_geo_row.get(strap_norm)
        if not row:
            continue
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        patch = {}
        if lat and lng and not row.get("latitude"):
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed and not row.get("assessed_value") and not row.get("market_value"):
            patch["assessed_value"] = assessed
        if not patch:
            continue
        status, _ = sb_patch("multi_county_auctions", f"id=eq.{row['id']}", patch)
        if status in (200, 204):
            if "latitude" in patch:
                geo_updates += 1
            if "assessed_value" in patch:
                val_updates += 1
        time.sleep(0.15)

    log(f"geo updates: {geo_updates}, value updates: {val_updates}", "RESULT")

    # ── Fail-loud check ───────────────────────────────────────────────────
    total_writes = e_resolved + pz_inserted + e_pz_inserted_via_addr + geo_updates + val_updates
    arcgis_found = len(arcgis_data_pz) + len(arcgis_data_geo)
    if arcgis_found > 0 and total_writes == 0:
        log("FAIL-LOUD: ArcGIS returned results but ZERO DB writes succeeded", "ERROR")
        sys.exit(1)

    # ── Summary ───────────────────────────────────────────────────────────
    log("\n=== Summary ===", "RESULT")
    log(f"E resolved (address lookup): {e_resolved}/{len(e_gap_has_address)}", "VERIFIED")
    log(f"E hard remainder (no address): {len(e_gap_no_address)} (not fabricated, not attempted)", "VERIFIED")
    log(f"I parcel_zones inserted: {pz_inserted} (skipped no-ZD: {len(pz_skipped_no_zd)}, no-zoning: {len(pz_skipped_no_zoning)})", "VERIFIED")
    log(f"I geo updates: {geo_updates}, value updates: {val_updates}", "VERIFIED")
    log(f"parcel_zones via E-addr fix: {e_pz_inserted_via_addr}", "VERIFIED")
    log("Next: run SELECT public.pencil_dod_evaluate_county('lee') to confirm E+I movement", "NEXT")


if __name__ == "__main__":
    main()
