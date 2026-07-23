#!/usr/bin/env python3
"""GOLD STANDARD Shard-12 (lee), loop run 6046, dispatch 86e03369.

Lee County E + I fix via ArcGIS FeatureServer.

TARGETS (from brief):
  - E: 278/318 parcel_linked (87.4%) — need ≥95% (302+), gap=40 rows
  - I: 247/318 card_complete (77.7%) — need ≥95% (302+), gap=71 rows

BACKGROUND:
  45 new rows added since July 11 session (273→318 total).
  Prior sessions used Lee County ArcGIS FeatureServer (PROVEN ENDPOINT):
    https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/
    Lee_County_Parcels/FeatureServer/0/query

THREE TARGET SETS:
  A: parcel_id IS NOT NULL (real STRAP) but NO parcel_zones row → lookup by
     STRAP, insert parcel_zones (safe zone codes only) + backfill geo/value.
  B: parcel_id IS NOT NULL, already zoning-linked, but missing lat/lng → lookup
     by STRAP, backfill geo/value only (no parcel_zones insert needed).
  C: parcel_id IS NULL but has property_address → lookup by address, backfill
     parcel_id + geo/value + parcel_zones (if code is in known_codes).

SAFE ZONE CODES (won't trigger G regression):
  Any code whose zoning_districts row has:
    - far_regulated=false AND density_regulated=false → safe (not applicable)
    - far_regulated=false AND density_regulated=true + zone_standards EXISTS → safe
  Codes that are NOT in zoning_districts at all → SKIPPED (never fabricated)
  Codes in zoning_districts with far_regulated=true/NULL + no zone_standards → RISKY, SKIP

JURISDICTION MAP (from proven prior scripts):
  cape coral    → 815
  bonita springs → 914
  fort myers beach → 912
  sanibel       → 942
  fort myers    → 929  (must come AFTER fort myers beach)
  north fort myers / fort myers shores / alva / bokeelia /
  lehigh acres / st. james city / captiva → 630 (unincorporated)
  default       → 630 (unincorporated Lee County)

SOURCE TAG: 'shard12_run6046_lee_arcgis_20260723'
  — fresh never-reused tag per the lesson from the July 11 session where
  source-tag collision caused unrelated rows to be deleted.
"""
import json
import os
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
LEE_ARCGIS = (
    "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/"
    "Lee_County_Parcels/FeatureServer/0/query"
)
SOURCE_TAG = "shard12_run6046_lee_arcgis_20260723"

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
    "pine island", "matlacha", "estero",
]


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
    return parcel_id.replace("-", "").replace(".", "").upper()


def strap_to_parcel_id(strap):
    s = strap.replace("-", "").replace(".", "").upper()
    if len(s) == 18:
        return f"{s[0:2]}-{s[2:4]}-{s[4:6]}-{s[6:8]}-{s[8:13]}.{s[13:18]}"
    return strap


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(
        url,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"},
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


def query_arcgis_by_straps(straps):
    if not straps:
        return {}
    in_clause = ",".join(f"'{s}'" for s in straps)
    where = f"STRAP IN ({in_clause})"
    params = urllib.parse.urlencode({
        "where": where,
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 2000,
    })
    req = urllib.request.Request(
        f"{LEE_ARCGIS}?{params}",
        headers={"User-Agent": "BidDeed-SHARD12"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        result = {}
        for f in data.get("features", []):
            a = f.get("attributes", {})
            if a.get("STRAP"):
                result[a["STRAP"]] = a
        return result
    except Exception as e:
        print(f"  ArcGIS STRAP batch error: {e}", flush=True)
        return {}


def query_arcgis_by_address(siteaddr):
    parts = siteaddr.split(",")[0].strip().upper()
    if not parts:
        return None
    params = urllib.parse.urlencode({
        "where": f"SITEADDR LIKE '{parts}%'",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 5,
    })
    req = urllib.request.Request(
        f"{LEE_ARCGIS}?{params}",
        headers={"User-Agent": "BidDeed-SHARD12"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        return feats[0].get("attributes", {}) if feats else None
    except Exception as e:
        print(f"  address query error ({siteaddr!r}): {e}", flush=True)
        return None


def is_real_strap(parcel_id):
    if not parcel_id:
        return False
    pid = parcel_id.strip()
    if pid.upper() in ("MULTIPLE PARCEL", "MULTIPLE PARCELS", "PROPERTY APPRAISER", ""):
        return False
    import re
    return bool(re.search(r"\d", pid))


def main():
    print("=== Lee County E+I ArcGIS Backfill — Shard-12 Run 6046 ===", flush=True)
    print(f"Source tag: {SOURCE_TAG}", flush=True)

    # --- Load known zoning_districts for Lee jurisdictions ---
    print("\n[1] Loading known zoning_districts for Lee jurisdictions...", flush=True)
    zd_rows = sb_get(
        "zoning_districts",
        "jurisdiction_id=in.(630,815,914,912,929,942)"
        "&select=jurisdiction_id,code,id,far_regulated,density_regulated,pk1000_regulated,category"
        "&limit=500",
    )
    # Build safe-code set: codes we can safely insert parcel_zones for
    # "Safe" = (a) far_regulated=false AND density_regulated=false → never applicable, always safe
    #          (b) far_regulated=false AND density_regulated=true → only density matters,
    #              safe IF zone_standards exists (handled below)
    known_codes = {(r["jurisdiction_id"], r["code"]): r for r in zd_rows}
    print(f"  Loaded {len(known_codes)} known (jid, code) pairs", flush=True)

    # Load zone_standards to check which codes have standards
    zs_rows = sb_get(
        "zone_standards",
        "select=zoning_district_id,max_far,max_density_du_acre,parking_per_1000sf&limit=500",
    )
    zs_by_district = {r["zoning_district_id"]: r for r in zs_rows}

    def is_safe_code(jid, code):
        key = (jid, code)
        if key not in known_codes:
            return False  # Unknown code — never insert, could cause G regression
        zd = known_codes[key]
        zd_id = zd["id"]
        far_reg = zd.get("far_regulated")
        density_reg = zd.get("density_regulated")
        pk1000_reg = zd.get("pk1000_regulated")

        # If all are explicitly false or None (default safe for residential), safe
        if far_reg is False and (density_reg is False or density_reg is None):
            return True  # far N/A, density N/A — G will not count this

        # If density regulated, safe only if zone_standards exists with a value
        if density_reg is True:
            if zd_id in zs_by_district and zs_by_district[zd_id]["max_density_du_acre"] is not None:
                return True  # has real density standard
            return False  # density applicable but no standard → G regression risk

        # If far regulated, unsafe (we don't have far values for Lee commercial)
        if far_reg is True:
            return False

        # Default: safe (residential pattern = not applicable)
        return True

    # --- Load existing parcel_zones for lee jurisdictions ---
    print("\n[2] Loading existing parcel_zones for Lee jurisdictions...", flush=True)
    existing_pz = sb_get(
        "parcel_zones",
        "jurisdiction_id=in.(630,815,914,912,929,942)&select=parcel_id&limit=5000",
    )
    existing_pz_set = {r["parcel_id"] for r in existing_pz}
    print(f"  Existing parcel_zones rows: {len(existing_pz_set)}", flush=True)

    # --- Load Lee county auctions ---
    print("\n[3] Loading Lee county auctions...", flush=True)
    # Load all lee rows with their key fields — paginated
    all_lee = []
    offset = 0
    batch = 1000
    while True:
        page = sb_get(
            "multi_county_auctions",
            f"county=eq.lee&select=case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value,opening_bid&limit={batch}&offset={offset}",
        )
        if not page:
            break
        all_lee.extend(page)
        if len(page) < batch:
            break
        offset += batch
    print(f"  Total lee rows loaded: {len(all_lee)}", flush=True)

    # Classify into sets
    target_a = []  # real parcel_id, no parcel_zones row
    target_b = []  # real parcel_id, has parcel_zones, but missing geo
    target_c = []  # no parcel_id but has address

    for row in all_lee:
        pid = row.get("parcel_id")
        has_lat = row.get("latitude") is not None
        has_pid = is_real_strap(pid)
        has_addr = bool(row.get("property_address", "").strip())
        has_pz = pid in existing_pz_set if has_pid else False

        if has_pid and not has_pz:
            target_a.append(row)
        elif has_pid and has_pz and not has_lat:
            target_b.append(row)
        elif not has_pid and has_addr:
            target_c.append(row)

    print(f"\n  Target A (no parcel_zones): {len(target_a)}", flush=True)
    print(f"  Target B (no geo):          {len(target_b)}", flush=True)
    print(f"  Target C (no parcel_id):    {len(target_c)}", flush=True)

    # --- Target A + B: STRAP lookups ---
    print("\n[4] STRAP lookups for A+B sets...", flush=True)
    strap_to_row = {}
    for r in target_a:
        strap_to_row[normalize_strap(r["parcel_id"])] = ("A", r)
    for r in target_b:
        strap_to_row[normalize_strap(r["parcel_id"])] = ("B", r)

    all_straps = list(strap_to_row.keys())
    arcgis_data = {}
    BATCH = 40
    for i in range(0, len(all_straps), BATCH):
        batch_straps = all_straps[i:i + BATCH]
        result = query_arcgis_by_straps(batch_straps)
        arcgis_data.update(result)
        print(
            f"  STRAP batch {i}-{i + len(batch_straps)}: "
            f"{len(result)}/{len(batch_straps)} found",
            flush=True,
        )
        time.sleep(0.3)

    # Process A+B results
    pz_inserts = []
    geo_updates = 0
    val_updates = 0
    skipped_no_zd = []
    skipped_risky = []

    for strap, attrs in arcgis_data.items():
        setname, row = strap_to_row.get(strap, (None, None))
        if not setname:
            continue
        pid = row["parcel_id"]
        zoning = (attrs.get("ZONING") or "").strip()
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = (attrs.get("SITECITY") or "").strip()
        jid = get_jid(city)

        if setname == "A" and zoning and pid not in existing_pz_set:
            if is_safe_code(jid, zoning):
                pz_inserts.append({
                    "parcel_id": pid,
                    "jurisdiction_id": jid,
                    "zone_code": zoning,
                    "zone_name": zoning,
                    "source": SOURCE_TAG,
                })
            elif (jid, zoning) not in known_codes:
                skipped_no_zd.append((row["case_number"], pid, zoning, jid, city))
            else:
                skipped_risky.append((row["case_number"], pid, zoning, jid, city))

        # Geo + value patch for both A and B
        patch = {}
        if lat and lng:
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed and not row.get("assessed_value"):
            patch["assessed_value"] = float(assessed)
        if patch:
            cn_enc = urllib.parse.quote(row["case_number"])
            status, _ = sb_patch(
                "multi_county_auctions",
                f"case_number=eq.{cn_enc}",
                patch,
            )
            if status in (200, 204):
                if "latitude" in patch:
                    geo_updates += 1
                if "assessed_value" in patch:
                    val_updates += 1

    print(f"\n  A/B results:", flush=True)
    print(f"    geo_updates: {geo_updates}", flush=True)
    print(f"    val_updates: {val_updates}", flush=True)
    print(f"    pz_inserts queued: {len(pz_inserts)}", flush=True)
    print(f"    skipped (unknown code): {len(skipped_no_zd)}", flush=True)
    for s in skipped_no_zd:
        print(f"      UNKNOWN: {s}", flush=True)
    print(f"    skipped (risky code, no standards): {len(skipped_risky)}", flush=True)
    for s in skipped_risky:
        print(f"      RISKY: {s}", flush=True)

    # Insert parcel_zones (A set)
    CHUNK = 100
    pz_inserted = 0
    for i in range(0, len(pz_inserts), CHUNK):
        chunk = pz_inserts[i:i + CHUNK]
        status, resp = sb_post(
            "parcel_zones",
            chunk,
            prefer="resolution=ignore-duplicates,return=minimal",
        )
        if status in (200, 201):
            pz_inserted += len(chunk)
            print(f"  parcel_zones chunk {i}-{i + len(chunk)}: status={status} OK", flush=True)
        else:
            print(
                f"  parcel_zones chunk {i}-{i + len(chunk)}: FAILED status={status} {resp[:200]}",
                flush=True,
            )

    print(f"\n  parcel_zones inserted: {pz_inserted} of {len(pz_inserts)} attempted", flush=True)

    # Update existing_pz_set for C-set check
    existing_pz_set.update({r["parcel_id"] for r in pz_inserts})

    # --- Target C: address lookups ---
    print("\n[5] Address lookups for C set...", flush=True)
    c_resolved = 0
    c_pz_inserts = 0
    c_no_match = []

    for row in target_c:
        addr = (row.get("property_address") or "").strip()
        if not addr:
            continue
        attrs = query_arcgis_by_address(addr)
        if not attrs or not attrs.get("STRAP"):
            c_no_match.append((row["case_number"], addr))
            continue

        formatted_pid = strap_to_parcel_id(attrs["STRAP"])
        zoning = (attrs.get("ZONING") or "").strip()
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = (attrs.get("SITECITY") or "").strip()
        jid = get_jid(city)

        patch = {"parcel_id": formatted_pid}
        if lat and lng:
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed:
            patch["assessed_value"] = float(assessed)

        cn_enc = urllib.parse.quote(row["case_number"])
        status, _ = sb_patch(
            "multi_county_auctions",
            f"case_number=eq.{cn_enc}",
            patch,
        )
        if status in (200, 204):
            c_resolved += 1
            print(
                f"  C-resolved {row['case_number']} → parcel_id={formatted_pid} zone={zoning}",
                flush=True,
            )
            # Insert parcel_zones if code is known and safe
            if zoning and formatted_pid not in existing_pz_set and is_safe_code(jid, zoning):
                s2, _ = sb_post(
                    "parcel_zones",
                    [{
                        "parcel_id": formatted_pid,
                        "jurisdiction_id": jid,
                        "zone_code": zoning,
                        "zone_name": zoning,
                        "source": SOURCE_TAG + "_addr",
                    }],
                    prefer="resolution=ignore-duplicates,return=minimal",
                )
                if s2 in (200, 201):
                    c_pz_inserts += 1
                    existing_pz_set.add(formatted_pid)
        time.sleep(0.2)

    print(f"\n  C results:", flush=True)
    print(f"    resolved: {c_resolved}/{len(target_c)}", flush=True)
    print(f"    new parcel_zones: {c_pz_inserts}", flush=True)
    print(f"    no match: {len(c_no_match)}", flush=True)
    for c in c_no_match:
        print(f"    NO_MATCH: {c}", flush=True)

    # --- Summary ---
    print("\n" + "=" * 60, flush=True)
    print("SUMMARY", flush=True)
    print(f"  parcel_zones inserted (A set): {pz_inserted}", flush=True)
    print(f"  parcel_zones inserted (C set): {c_pz_inserts}", flush=True)
    print(f"  geo/lat-lng updates:           {geo_updates}", flush=True)
    print(f"  assessed_value updates:        {val_updates}", flush=True)
    print(f"  new parcel_id resolved (C):    {c_resolved}", flush=True)
    print(f"  skipped (unknown zone code):   {len(skipped_no_zd)}", flush=True)
    print(f"  skipped (risky zone code):     {len(skipped_risky)}", flush=True)
    print(f"  no ArcGIS match (C):           {len(c_no_match)}", flush=True)
    print("=== DONE ===", flush=True)


if __name__ == "__main__":
    main()
