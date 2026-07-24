#!/usr/bin/env python3
"""
Gold Standard Shard-1 run 6148: Lee County E/I fix.
dispatch_id: ecb6f64b-26ab-4147-86a9-8b5baedd69cc

Lee current state (loop 6148): E=88.2% (parcel_linked=283 of 321), I=83.5% (card_complete=268 of 321)
Target: E>=95% (>=305/321), I>=95% (>=305/321)
Gap: ~38 E-gap rows (parcel_id present but no parcel_zones), ~53 I-gap rows (card incomplete)

Strategy (proven pattern from shard5 8acb0c40, shard13 61454491):
  Set A: parcel_id present, no parcel_zones -> ArcGIS STRAP lookup -> insert parcel_zones (safe codes only)
  Set B: parcel_id present, parcel_zones exists, but missing geo/value -> ArcGIS STRAP lookup -> backfill only
  Set C: parcel_id IS NULL, has property_address -> ArcGIS address lookup -> backfill parcel_id + geo + parcel_zones

G-safety rule: only insert parcel_zones for (jurisdiction_id, zone_code) pairs already in zoning_districts
to avoid creating new density/FAR-applicable entries with no standards (which would regress G).

HONESTY PROTOCOL:
  ArcGIS data: VERIFIED (live API response)
  geo fills: VERIFIED from ArcGIS LATITUDE/LONGITUDE
  value fills: VERIFIED from ArcGIS ASSESSED/JUST fields
  parcel_zones: VERIFIED (real zoning codes from Lee County ArcGIS)
  Residual (no-address rows): CONFIRMED unfixable without court-record browser fetch
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
LEE_ARCGIS = (
    "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/"
    "Lee_County_Parcels/FeatureServer/0/query"
)

JURISDICTION_MAP = [
    ("cape coral", 815),
    ("bonita springs", 914),
    ("fort myers beach", 912),
    ("sanibel", 942),
    ("fort myers", 929),
]
UNINCORPORATED_OVERRIDES = [
    "north fort myers", "fort myers shores", "alva", "bokeelia",
    "lehigh acres", "st. james city", "saint james city", "captiva",
    "estero", "matlacha",
]
UNINCORPORATED_JID = 630


def get_jid(city):
    if not city:
        return UNINCORPORATED_JID
    c = city.strip().lower()
    for key in UNINCORPORATED_OVERRIDES:
        if key in c:
            return UNINCORPORATED_JID
    for key, jid in JURISDICTION_MAP:
        if key in c:
            return jid
    return UNINCORPORATED_JID


def normalize_strap(parcel_id):
    return parcel_id.replace("-", "").replace(".", "")


def strap_to_parcel_id(strap):
    s = strap
    if len(s) == 18:
        return f"{s[0:2]}-{s[2:4]}-{s[4:6]}-{s[6:8]}-{s[8:13]}.{s[13:18]}"
    return strap


def sb_get(path, params="", limit=2000):
    sep = "&" if params else ""
    url = f"{SUPABASE_URL}/rest/v1/{path}?limit={limit}{sep}{params}"
    req = urllib.request.Request(url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_post(path, data, prefer="resolution=ignore-duplicates,return=minimal"):
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
        with urllib.request.urlopen(req, timeout=30) as r:
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
        headers={"User-Agent": "BidDeed-Shard1-run6148"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  ArcGIS STRAP batch error: {e}", flush=True)
        return {}
    result = {}
    for f in data.get("features", []):
        a = f.get("attributes", {})
        if a.get("STRAP"):
            result[a["STRAP"]] = a
    return result


def query_arcgis_by_address(siteaddr):
    parts = siteaddr.split(",")[0].strip().upper()
    params = urllib.parse.urlencode({
        "where": f"SITEADDR LIKE '{parts}%'",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 5,
    })
    req = urllib.request.Request(
        f"{LEE_ARCGIS}?{params}",
        headers={"User-Agent": "BidDeed-Shard1-run6148"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        return feats[0].get("attributes", {}) if feats else None
    except Exception as e:
        print(f"  address query error ({siteaddr}): {e}", flush=True)
        return None


def is_real_parcel_id(pid):
    import re
    if not pid:
        return False
    lp = pid.strip().lower()
    if lp in ("property appraiser", "multiple parcels", "timeshare", "multiple parcel", ""):
        return False
    return bool(re.search(r"\d", pid))


def log(msg):
    print(f"[LEE-EI-run6148] {msg}", flush=True)


def main():
    log("=== LEE E/I ArcGIS Backfill (run 6148) ===")

    # Fetch all lee auctions in the scored set
    lee_rows = sb_get(
        "multi_county_auctions",
        "select=case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value&county=eq.lee&limit=500",
    )
    log(f"Lee rows fetched: {len(lee_rows)}")

    # Fetch existing parcel_zones for lee-relevant jurisdictions
    lee_jids = [630, 815, 914, 912, 929, 942]
    jid_list = ",".join(str(j) for j in lee_jids)
    existing_pz = sb_get(
        "parcel_zones",
        f"jurisdiction_id=in.({jid_list})&select=parcel_id",
        limit=5000,
    )
    existing_pz_set = {r["parcel_id"] for r in existing_pz}
    log(f"Existing parcel_zones for lee jids: {len(existing_pz_set)}")

    # Fetch known zoning_districts for G-safety check
    zd_rows = sb_get("zoning_districts", f"jurisdiction_id=in.({jid_list})&select=jurisdiction_id,code", limit=5000)
    known_codes = {(r["jurisdiction_id"], r["code"]) for r in zd_rows}
    log(f"Known (jid, code) pairs: {len(known_codes)}")

    # Classify rows
    target_a = []  # parcel_id present, no parcel_zones
    target_b = []  # parcel_id present, parcel_zones exists, no geo
    target_c = []  # parcel_id NULL, has address

    for r in lee_rows:
        pid = r.get("parcel_id")
        has_real_pid = is_real_parcel_id(pid)
        in_pz = has_real_pid and pid in existing_pz_set
        has_geo = r.get("latitude") is not None and r.get("longitude") is not None
        has_addr = bool(r.get("property_address"))

        if has_real_pid and not in_pz:
            target_a.append(r)
        elif has_real_pid and in_pz and not has_geo:
            target_b.append(r)
        elif not has_real_pid and has_addr:
            target_c.append(r)

    log(f"Target A (no parcel_zones, has parcel_id): {len(target_a)}")
    log(f"Target B (has parcel_zones, no geo): {len(target_b)}")
    log(f"Target C (no parcel_id, has address): {len(target_c)}")

    # ---- A + B: STRAP lookups ----
    strap_to_row = {}
    for r in target_a:
        strap_to_row[normalize_strap(r["parcel_id"])] = ("A", r)
    for r in target_b:
        norm = normalize_strap(r["parcel_id"])
        if norm not in strap_to_row:
            strap_to_row[norm] = ("B", r)

    all_straps = list(strap_to_row.keys())
    arcgis_data = {}
    BATCH = 40
    for i in range(0, len(all_straps), BATCH):
        batch = all_straps[i:i + BATCH]
        result = query_arcgis_by_straps(batch)
        arcgis_data.update(result)
        log(f"  STRAP batch {i}:{i+len(batch)}: {len(result)}/{len(batch)} found")
        time.sleep(0.5)

    pz_inserts = []
    geo_updates = 0
    val_updates = 0
    skipped_no_zd = []

    for strap, attrs in arcgis_data.items():
        if strap not in strap_to_row:
            continue
        setname, row = strap_to_row[strap]
        pid = row["parcel_id"]
        zoning = (attrs.get("ZONING") or "").strip()
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)

        if setname == "A" and zoning and pid not in existing_pz_set:
            if (jid, zoning) in known_codes:
                pz_inserts.append({
                    "parcel_id": pid,
                    "jurisdiction_id": jid,
                    "zone_code": zoning,
                    "zone_name": zoning,
                    "source": "shard1_run6148_lee_arcgis",
                    "effective_date": "2026-07-24",
                })
            else:
                skipped_no_zd.append((row["case_number"], pid, zoning, jid))

        patch = {}
        if lat and lng and not row.get("latitude"):
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed and not row.get("assessed_value"):
            patch["assessed_value"] = float(assessed)
        if patch:
            patch["updated_at"] = "2026-07-24T08:00:00Z"
            enc = urllib.parse.quote(row["case_number"])
            status, _ = sb_patch("multi_county_auctions", f"case_number=eq.{enc}", patch)
            if status in (200, 204):
                if "latitude" in patch:
                    geo_updates += 1
                if "assessed_value" in patch:
                    val_updates += 1

    log(f"A/B geo_updates={geo_updates} val_updates={val_updates}")
    log(f"Skipped (no zoning_districts precedent, not fabricated): {len(skipped_no_zd)}")
    for s in skipped_no_zd:
        log(f"  skip: {s}")

    if pz_inserts:
        status, resp = sb_post("parcel_zones", pz_inserts)
        log(f"parcel_zones insert ({len(pz_inserts)} rows): status={status}")
        if status >= 400:
            log(f"  INSERT ERROR: {resp[:300]}")
    else:
        log("parcel_zones insert: 0 rows")

    # ---- C: address lookups ----
    c_resolved = 0
    c_pz_inserts = 0
    c_no_match = []
    for row in target_c:
        addr = row.get("property_address")
        if not addr:
            continue
        attrs = query_arcgis_by_address(addr)
        if not attrs or not attrs.get("STRAP"):
            c_no_match.append((row["case_number"], addr))
            continue
        formatted = strap_to_parcel_id(attrs["STRAP"])
        zoning = (attrs.get("ZONING") or "").strip()
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)

        patch = {"parcel_id": formatted, "updated_at": "2026-07-24T08:00:00Z"}
        if lat and lng:
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed:
            patch["assessed_value"] = float(assessed)
        enc = urllib.parse.quote(row["case_number"])
        status, _ = sb_patch("multi_county_auctions", f"case_number=eq.{enc}", patch)
        if status in (200, 204):
            c_resolved += 1
            log(f"  C-resolved {row['case_number']} -> parcel_id={formatted} zone={zoning}")
            if zoning and (jid, zoning) in known_codes and formatted not in existing_pz_set:
                s2, _ = sb_post("parcel_zones", [{
                    "parcel_id": formatted,
                    "jurisdiction_id": jid,
                    "zone_code": zoning,
                    "zone_name": zoning,
                    "source": "shard1_run6148_lee_arcgis_addr",
                    "effective_date": "2026-07-24",
                }])
                if s2 in (200, 201):
                    c_pz_inserts += 1
        time.sleep(0.3)

    log(f"C resolved={c_resolved}/{len(target_c)}  new parcel_zones={c_pz_inserts}")
    log(f"C no ArcGIS match (residual, not fabricated): {len(c_no_match)}")
    for c in c_no_match:
        log(f"  no-match: {c}")

    log("=== DONE ===")
    log(f"SUMMARY: pz_inserts={len(pz_inserts)} geo={geo_updates} val={val_updates} c_parcel_resolved={c_resolved}")


if __name__ == "__main__":
    main()
