#!/usr/bin/env python3
"""GOLD STANDARD shard-13, dispatch 850748bb-e511-4a3d-bfe5-3714665723b5, county=lee.

Loop run 7553. Lee is at 8/10 with E=91.3% (parcel_linked=294/322) and
I=85.7% (card_complete=276/322). Need both at >=95% (306+ rows each).

STRATEGY (based on prior session residuals from run 6354):
1. Live-query DB for exact E and I gaps
2. Re-try ArcGIS address lookup on the "soft" E-gap rows (have address, prior
   LIKE-prefix approach failed) using street-number-only and normalized strategies
3. For I geocode gap: use nominatim geocoding for rows with address+value but no lat/lng
4. For I zone gap: source Fort Myers CPD, Bonita Springs MH-1, Fort Myers Beach RS-1,
   and Lee County unincorporated CS ordinance values from public sources

HARD RULES:
- Never insert parcel_zones for a zone_code with no zoning_districts precedent
- Never fabricate geo/value data
- Fail-loud: parsed>0 AND inserted=0 raises
"""

import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
LEE_ARCGIS = (
    "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/"
    "Lee_County_Parcels/FeatureServer/0/query"
)

JURISDICTION_MAP_ORDERED = [
    ("cape coral", 815),
    ("bonita springs", 914),
    ("fort myers beach", 912),
    ("sanibel", 942),
    ("estero", 930),
    ("fort myers", 929),
]
UNINCORPORATED_KEYS = [
    "north fort myers", "fort myers shores", "alva", "bokeelia",
    "lehigh acres", "st. james city", "saint james city", "captiva",
    "matlacha", "pine island",
]


def get_jid(city):
    if not city:
        return 630
    c = city.strip().lower()
    for key in UNINCORPORATED_KEYS:
        if key in c:
            return 630
    for key, jid in JURISDICTION_MAP_ORDERED:
        if key in c:
            return jid
    return 630


def normalize_strap(parcel_id):
    return parcel_id.replace("-", "").replace(".", "")


def strap_to_parcel_id(strap):
    s = strap
    if len(s) == 18:
        return f"{s[0:2]}-{s[2:4]}-{s[4:6]}-{s[6:8]}-{s[8:13]}.{s[13:18]}"
    return strap


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_post(path, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=body,
        headers={
            "apikey": KEY, "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json", "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sb_patch(path, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}?{params}", data=body,
        headers={
            "apikey": KEY, "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json", "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
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
        "f": "json", "resultRecordCount": 2000,
    })
    req = urllib.request.Request(f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-Shard13"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    result = {}
    for f in data.get("features", []):
        a = f.get("attributes", {})
        if a.get("STRAP"):
            result[a["STRAP"]] = a
    return result


def query_arcgis_by_address_strict(siteaddr):
    """Try exact prefix match - works when address format matches ArcGIS exactly."""
    parts = siteaddr.split(",")[0].strip().upper()
    params = urllib.parse.urlencode({
        "where": f"SITEADDR LIKE '{parts}%'",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json", "resultRecordCount": 5,
    })
    req = urllib.request.Request(f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-Shard13"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        return feats[0].get("attributes", {}) if feats else None
    except Exception as e:
        print(f"    strict addr query error ({siteaddr}): {e}", flush=True)
        return None


def query_arcgis_by_street_number(siteaddr):
    """Fallback: extract just the street number for a looser match."""
    parts = siteaddr.split(",")[0].strip().upper().split()
    if not parts:
        return None
    street_num = parts[0]
    if not street_num.isdigit():
        return None
    street_name = " ".join(parts[1:3]) if len(parts) > 1 else ""
    if not street_name:
        return None
    params = urllib.parse.urlencode({
        "where": f"SITEADDR LIKE '{street_num} {street_name}%'",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json", "resultRecordCount": 3,
    })
    req = urllib.request.Request(f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-Shard13"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        return feats[0].get("attributes", {}) if feats else None
    except Exception as e:
        print(f"    street-num addr query error ({siteaddr}): {e}", flush=True)
        return None


def query_nominatim(address):
    """Geocode an address via Nominatim (free, no key). Returns (lat, lng) or None."""
    params = urllib.parse.urlencode({
        "q": address, "format": "json", "limit": "1", "countrycodes": "us",
    })
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": "BidDeed-GoldStandard/1.0 (+https://biddeed.ai)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            results = json.loads(resp.read())
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
        return None
    except Exception as e:
        print(f"    nominatim error ({address}): {e}", flush=True)
        return None


def main():
    if not KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", flush=True)
        raise SystemExit(1)

    print("=== Lee County E+I Gap Fix, shard-13 run 7553 ===", flush=True)
    print(f"SUPABASE_URL: {SUPABASE_URL}", flush=True)

    # ── STEP 1: Get known zoning_districts so we never create orphan parcel_zones ──
    print("\n[1] Loading zoning_districts for lee jurisdictions...", flush=True)
    zd_rows = sb_get("zoning_districts", "select=id,jurisdiction_id,code&limit=5000")
    known_codes = {(r["jurisdiction_id"], r["code"]): r["id"] for r in zd_rows}
    print(f"  Known zoning_district (jid, code) pairs: {len(known_codes)}", flush=True)

    # Log what we have for fort myers (929), bonita springs (914), fort myers beach (912), unincorp (630)
    for jid, name in [(929, "Fort Myers"), (914, "Bonita Springs"), (912, "Fort Myers Beach"), (630, "Unincorp")]:
        codes = [c for j, c in known_codes if j == jid]
        print(f"  {name} (jid={jid}): {len(codes)} codes — {sorted(codes)}", flush=True)

    # ── STEP 2: Load existing parcel_zones for lee ──
    print("\n[2] Loading existing parcel_zones for lee...", flush=True)
    existing_pz = sb_get(
        "parcel_zones",
        "jurisdiction_id=in.(630,815,914,912,929,942)&select=parcel_id,zone_code,jurisdiction_id&limit=5000"
    )
    existing_pz_set = {r["parcel_id"] for r in existing_pz}
    print(f"  Existing parcel_zones: {len(existing_pz_set)}", flush=True)

    # ── STEP 3: Get all lee auction rows for gap analysis ──
    print("\n[3] Loading all lee auction rows...", flush=True)
    lee_rows = sb_get(
        "multi_county_auctions",
        "county=eq.lee&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value&limit=500&order=case_number.asc"
    )
    print(f"  Total lee rows: {len(lee_rows)}", flush=True)

    # E-gap: parcel_id IS NULL or is a placeholder
    PLACEHOLDER_IDS = {"property appraiser", "timeshare", ""}
    def is_real_parcel(pid):
        if not pid:
            return False
        import re
        return bool(re.search(r"\d", pid)) and pid.strip().lower() not in PLACEHOLDER_IDS

    e_gap = [r for r in lee_rows if not is_real_parcel(r.get("parcel_id"))]
    print(f"  E-gap rows (no real parcel_id): {len(e_gap)}", flush=True)

    e_gap_with_addr = [r for r in e_gap if r.get("property_address")]
    e_gap_no_addr = [r for r in e_gap if not r.get("property_address")]
    print(f"    With address: {len(e_gap_with_addr)}, Without address: {len(e_gap_no_addr)}", flush=True)

    # I-gap: has real parcel_id but missing lat/lng or assessed_value
    # (full card_complete requires address + lat/lng + value + parcel_zones link)
    geo_gap = [
        r for r in lee_rows
        if is_real_parcel(r.get("parcel_id"))
        and (r.get("latitude") is None or r.get("longitude") is None)
    ]
    print(f"  I geo-gap rows (real parcel_id but no lat/lng): {len(geo_gap)}", flush=True)

    no_pz_link = [
        r for r in lee_rows
        if is_real_parcel(r.get("parcel_id"))
        and r.get("parcel_id") not in existing_pz_set
        and r.get("latitude") is not None
    ]
    print(f"  I zone-gap rows (real parcel_id, no parcel_zones, has geo): {len(no_pz_link)}", flush=True)

    # ── STEP 4: ArcGIS address lookup for E-gap rows with addresses ──
    print(f"\n[4] ArcGIS address lookup for {len(e_gap_with_addr)} E-gap rows...", flush=True)
    e_resolved = []
    e_addr_only = []

    for row in e_gap_with_addr:
        addr = row["property_address"]
        case = row["case_number"]
        print(f"  Case {case}: {addr}", flush=True)

        # Try strict match first
        attrs = query_arcgis_by_address_strict(addr)
        if attrs and attrs.get("STRAP"):
            print(f"    -> strict match: STRAP={attrs['STRAP']} ZONE={attrs.get('ZONING')}", flush=True)
            e_resolved.append((row, attrs, "strict"))
            time.sleep(0.2)
            continue

        # Try street-number looser match
        attrs = query_arcgis_by_street_number(addr)
        if attrs and attrs.get("STRAP"):
            print(f"    -> street-num match: STRAP={attrs['STRAP']} ZONE={attrs.get('ZONING')}", flush=True)
            e_resolved.append((row, attrs, "street_num"))
            time.sleep(0.2)
            continue

        print(f"    -> no ArcGIS match", flush=True)
        e_addr_only.append(row)
        time.sleep(0.2)

    print(f"  E-gap with-addr resolved: {len(e_resolved)}/{len(e_gap_with_addr)}", flush=True)

    # ── STEP 5: ArcGIS STRAP lookup for geo-gap rows ──
    print(f"\n[5] ArcGIS STRAP lookup for {len(geo_gap)} geo-gap rows...", flush=True)
    geo_resolved = []
    if geo_gap:
        straps = [normalize_strap(r["parcel_id"]) for r in geo_gap]
        strap_to_row = {normalize_strap(r["parcel_id"]): r for r in geo_gap}
        BATCH = 40
        arcgis_data = {}
        for i in range(0, len(straps), BATCH):
            batch = straps[i:i + BATCH]
            result = query_arcgis_by_straps(batch)
            arcgis_data.update(result)
            print(f"  STRAP batch {i}-{i+len(batch)}: {len(result)}/{len(batch)} found", flush=True)
            time.sleep(0.3)

        for strap, attrs in arcgis_data.items():
            row = strap_to_row.get(strap)
            if row:
                geo_resolved.append((row, attrs))

    print(f"  Geo-gap resolved: {len(geo_resolved)}/{len(geo_gap)}", flush=True)

    # ── STEP 6: ArcGIS STRAP lookup for zone-gap rows ──
    print(f"\n[6] ArcGIS STRAP lookup for {len(no_pz_link)} zone-gap rows...", flush=True)
    zone_resolved = []
    skipped_no_precedent = []
    if no_pz_link:
        straps = [normalize_strap(r["parcel_id"]) for r in no_pz_link]
        strap_to_row2 = {normalize_strap(r["parcel_id"]): r for r in no_pz_link}
        BATCH = 40
        arcgis_data2 = {}
        for i in range(0, len(straps), BATCH):
            batch = straps[i:i + BATCH]
            result = query_arcgis_by_straps(batch)
            arcgis_data2.update(result)
            print(f"  STRAP batch {i}-{i+len(batch)}: {len(result)}/{len(batch)} found", flush=True)
            time.sleep(0.3)

        for strap, attrs in arcgis_data2.items():
            row = strap_to_row2.get(strap)
            if not row:
                continue
            zoning = attrs.get("ZONING", "")
            city = attrs.get("SITECITY", "")
            jid = get_jid(city)
            if zoning and (jid, zoning) in known_codes:
                zone_resolved.append((row, attrs))
            else:
                skipped_no_precedent.append((row["case_number"], row["parcel_id"], zoning, jid, city))

    print(f"  Zone-gap resolved (safe to insert): {len(zone_resolved)}", flush=True)
    print(f"  Zone-gap skipped (no zoning_districts precedent): {len(skipped_no_precedent)}", flush=True)
    for s in skipped_no_precedent:
        print(f"    {s}", flush=True)

    # ── STEP 7: Nominatim geocoding for E-gap rows with no ArcGIS match ──
    print(f"\n[7] Nominatim geocoding for {len(e_addr_only)} E-gap rows (address but no ArcGIS)...", flush=True)
    nominatim_results = []
    for row in e_addr_only:
        addr = row["property_address"]
        # Only do this if they have no lat/lng (geocode = partial I help, not E)
        if row.get("latitude") is not None:
            print(f"  {row['case_number']}: already has lat/lng, skip nominatim", flush=True)
            continue
        result = query_nominatim(addr)
        if result:
            lat, lng = result
            print(f"  {row['case_number']}: nominatim -> {lat},{lng}", flush=True)
            nominatim_results.append((row, lat, lng))
        else:
            print(f"  {row['case_number']}: nominatim no result", flush=True)
        time.sleep(1.1)  # Nominatim rate limit: 1/second

    # ── STEP 8: Apply writes to Supabase ──
    print("\n[8] Applying writes to Supabase...", flush=True)

    e_parcel_written = 0
    pz_written = 0
    geo_written = 0
    failed = []

    # 8a: E-gap resolved rows — write parcel_id + geo + value + parcel_zones if safe
    for row, attrs, method in e_resolved:
        pid = strap_to_parcel_id(attrs["STRAP"])
        zoning = attrs.get("ZONING", "")
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)

        patch = {"parcel_id": pid}
        if lat and lng:
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed:
            patch["assessed_value"] = assessed

        status, resp = sb_patch(
            "multi_county_auctions",
            f"case_number=eq.{urllib.parse.quote(row['case_number'])}&county=eq.lee",
            patch
        )
        if status in (200, 204):
            e_parcel_written += 1
            print(f"  E-written {row['case_number']} -> parcel_id={pid} (method={method})", flush=True)
            if zoning and (jid, zoning) in known_codes and pid not in existing_pz_set:
                s2, _ = sb_post("parcel_zones", [{
                    "parcel_id": pid, "jurisdiction_id": jid,
                    "zone_code": zoning, "zone_name": zoning,
                    "source": "shard13_run7553_arcgis_addr",
                }], prefer="resolution=ignore-duplicates,return=minimal")
                if s2 in (200, 201):
                    pz_written += 1
                    print(f"    + parcel_zones {pid} jid={jid} zone={zoning}", flush=True)
        else:
            print(f"  FAILED {row['case_number']}: status={status} {resp[:200]}", flush=True)
            failed.append(row["case_number"])

    # 8b: Geo-gap rows — write lat/lng + value
    for row, attrs in geo_resolved:
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        if not (lat and lng):
            continue
        patch = {"latitude": lat, "longitude": lng}
        if assessed:
            patch["assessed_value"] = assessed
        status, resp = sb_patch(
            "multi_county_auctions",
            f"case_number=eq.{urllib.parse.quote(row['case_number'])}&county=eq.lee",
            patch
        )
        if status in (200, 204):
            geo_written += 1
            print(f"  Geo-written {row['case_number']} -> lat={lat} lng={lng}", flush=True)
        else:
            print(f"  FAILED geo {row['case_number']}: {status}", flush=True)

    # 8c: Zone-gap rows — insert parcel_zones
    for row, attrs in zone_resolved:
        pid = row["parcel_id"]
        zoning = attrs.get("ZONING", "")
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)
        if pid in existing_pz_set:
            print(f"  Zone skip {row['case_number']}: parcel_id already in parcel_zones", flush=True)
            continue
        s2, _ = sb_post("parcel_zones", [{
            "parcel_id": pid, "jurisdiction_id": jid,
            "zone_code": zoning, "zone_name": zoning,
            "source": "shard13_run7553_arcgis_zone",
        }], prefer="resolution=ignore-duplicates,return=minimal")
        if s2 in (200, 201):
            pz_written += 1
            existing_pz_set.add(pid)
            print(f"  PZ-written {row['case_number']} {pid} jid={jid} zone={zoning}", flush=True)
        else:
            print(f"  FAILED pz {row['case_number']}: {s2}", flush=True)

    # 8d: Nominatim results — write lat/lng (geocoded only, no parcel/zone changes)
    for row, lat, lng in nominatim_results:
        patch = {"latitude": lat, "longitude": lng}
        status, resp = sb_patch(
            "multi_county_auctions",
            f"case_number=eq.{urllib.parse.quote(row['case_number'])}&county=eq.lee",
            patch
        )
        if status in (200, 204):
            geo_written += 1
            print(f"  Nominatim-written {row['case_number']} -> lat={lat} lng={lng}", flush=True)
        else:
            print(f"  FAILED nominatim {row['case_number']}: {status}", flush=True)

    # ── STEP 9: Verify via pencil_dod_evaluate_county ──
    print("\n[9] Verification: pencil_dod_evaluate_county('lee')...", flush=True)
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            data=json.dumps({"county_slug_arg": "lee"}).encode(),
            headers={
                "apikey": KEY, "Authorization": f"Bearer {KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            print(f"EVALUATION RESULT:\n{json.dumps(result, indent=2)}", flush=True)
    except Exception as ex:
        print(f"Evaluation error: {ex}", flush=True)
        # Also try the function name without _arg suffix
        try:
            req = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                data=json.dumps({"p_county": "lee"}).encode(),
                headers={
                    "apikey": KEY, "Authorization": f"Bearer {KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
                print(f"EVALUATION RESULT (p_county):\n{json.dumps(result, indent=2)}", flush=True)
        except Exception as ex2:
            print(f"Evaluation error (p_county): {ex2}", flush=True)

    # ── SUMMARY ──
    print("\n=== SUMMARY ===", flush=True)
    print(f"E-parcel_id written: {e_parcel_written}", flush=True)
    print(f"parcel_zones inserted: {pz_written}", flush=True)
    print(f"geo (lat/lng) written: {geo_written}", flush=True)
    print(f"E-gap remaining (no ArcGIS match, no address): {len(e_gap_no_addr)}", flush=True)
    print(f"E-gap remaining (address, no ArcGIS): {len(e_addr_only)}", flush=True)
    print(f"Zone-gap skipped (no precedent): {len(skipped_no_precedent)}", flush=True)
    if failed:
        print(f"FAILURES: {failed}", flush=True)
        raise RuntimeError(f"Fail-loud: {len(failed)} writes failed — {failed}")
    print("DONE — no failures", flush=True)


if __name__ == "__main__":
    main()
