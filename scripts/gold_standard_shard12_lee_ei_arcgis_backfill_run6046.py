#!/usr/bin/env python3
"""SHARD-12 (lee), dispatch 86e03369, run 6046.

Lee County E/I fix via the Lee County ArcGIS FeatureServer.
Reuses the proven endpoint from prior sessions (shard-5, shard-8, shard-13, shard-14):

  https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/
  Lee_County_Parcels/FeatureServer/0/query

This session's approach (building on shard-5 continuation):

  Target A: rows with real parcel_id but NO parcel_zones row in the current
     gap set. Lookup by STRAP, insert parcel_zones ONLY if (jid, zone_code)
     pair already exists in zoning_districts (migration
     20260723_shard12_lee_g_mdp3_i_zoning_districts.sql adds the missing
     Fort Myers RS-6/RS-7/NC/CG/CPD/CS/MPD and Cape Coral RS-6/RS-7 codes
     before this script runs).

  Target B: rows with real parcel_id, already zoning-linked, but missing
     lat/lng or assessed_value. Lookup by STRAP, backfill geo+value only.

  Target C: rows where parcel_id IS NULL but property_address IS NOT NULL.
     Lookup by address, backfill parcel_id + geo + value + parcel_zones
     only where (jid, zone_code) is registered.

G-regression guard (HARD): never insert a parcel_zones row for a
(jurisdiction_id, zone_code) pair that does NOT have a matching
zoning_districts row — the migration above must run first.

Source tag: 'shard12_run6046_lee_arcgis' (never reused — avoids the
shard-13 source-tag-collision incident where a DELETE by source tag
deleted pre-existing rows with the same tag from a prior session).

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/gold_standard_shard12_lee_ei_arcgis_backfill_run6046.py
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
SOURCE_TAG = "shard12_run6046_lee_arcgis"
COUNTY = "lee"

LEE_JIDS = (630, 815, 914, 912, 929, 942)

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
    "estero",
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
    return parcel_id.replace("-", "").replace(".", "")


def sb_get(path, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
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
    params = urllib.parse.urlencode({
        "where": f"STRAP IN ({in_clause})",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 2000,
    })
    req = urllib.request.Request(
        f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-SHARD12-run6046"}
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
    params = urllib.parse.urlencode({
        "where": f"SITEADDR LIKE '{parts}%'",
        "outFields": "STRAP,ZONING,LATITUDE,LONGITUDE,ASSESSED,JUST,SITEADDR,SITECITY",
        "f": "json",
        "resultRecordCount": 5,
    })
    req = urllib.request.Request(
        f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-SHARD12-run6046"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        return feats[0].get("attributes", {}) if feats else None
    except Exception as e:
        print(f"  address query error ({siteaddr}): {e}", flush=True)
        return None


def main():
    print("=== Lee County E/I ArcGIS Backfill — shard12 run6046 ===", flush=True)

    # Step 1: Load existing state
    print("\n--- Loading existing parcel_zones for Lee jurisdictions ---", flush=True)
    existing_pz_rows = sb_get(
        "parcel_zones",
        f"jurisdiction_id=in.({','.join(str(j) for j in LEE_JIDS)})&select=parcel_id&limit=3000"
    )
    existing_pz_set = {r["parcel_id"] for r in existing_pz_rows}
    print(f"  existing parcel_zones: {len(existing_pz_set)}", flush=True)

    # Step 2: Load known (jid, code) pairs from zoning_districts
    print("\n--- Loading known zoning_districts ---", flush=True)
    zd_rows = sb_get("zoning_districts", "select=jurisdiction_id,code&limit=5000")
    known_codes = {(r["jurisdiction_id"], r["code"]) for r in zd_rows}
    print(f"  known zoning_districts: {len(known_codes)}", flush=True)

    # Step 3: Query current E gap (parcel_id present, no parcel_zones)
    print("\n--- Querying E gap (Target A): real parcel_id but no parcel_zones ---", flush=True)
    all_lee = sb_get(
        "multi_county_auctions",
        "county=eq.lee"
        "&parcel_id=not.is.null"
        "&select=case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value"
        "&limit=2000"
    )
    print(f"  lee rows with parcel_id: {len(all_lee)}", flush=True)

    target_a = [
        r for r in all_lee
        if r["parcel_id"] and r["parcel_id"] != "MULTIPLE PARCEL"
        and any(c.isdigit() for c in r["parcel_id"])
        and r["parcel_id"] not in existing_pz_set
    ]
    print(f"  Target A (need parcel_zones): {len(target_a)}", flush=True)

    # Target B: have parcel_zones but missing geo
    zoned_with_pid = {
        r["parcel_id"] for r in all_lee
        if r["parcel_id"] in existing_pz_set
    }
    target_b = [
        r for r in all_lee
        if r["parcel_id"] in existing_pz_set
        and (not r.get("latitude") or not r.get("longitude"))
        and r["parcel_id"] and r["parcel_id"] != "MULTIPLE PARCEL"
    ]
    print(f"  Target B (have parcel_zones, need geo): {len(target_b)}", flush=True)

    # Target C: no parcel_id but has address
    lee_no_pid = sb_get(
        "multi_county_auctions",
        "county=eq.lee"
        "&parcel_id=is.null"
        "&property_address=not.is.null"
        "&select=case_number,parcel_id,property_address,latitude,longitude,assessed_value"
        "&limit=500"
    )
    target_c = [r for r in lee_no_pid if r.get("property_address")]
    print(f"  Target C (no parcel_id, has address): {len(target_c)}", flush=True)

    # Step 4: ArcGIS STRAP lookups for A + B
    print("\n--- ArcGIS STRAP lookups ---", flush=True)
    strap_to_row = {}
    for r in target_a:
        strap = normalize_strap(r["parcel_id"])
        strap_to_row[strap] = ("A", r)
    for r in target_b:
        strap = normalize_strap(r["parcel_id"])
        if strap not in strap_to_row:
            strap_to_row[strap] = ("B", r)

    all_straps = list(strap_to_row.keys())
    print(f"  total STRAPs to look up: {len(all_straps)}", flush=True)

    arcgis_data = {}
    BATCH = 40
    for i in range(0, len(all_straps), BATCH):
        batch = all_straps[i:i + BATCH]
        result = query_arcgis_by_straps(batch)
        arcgis_data.update(result)
        print(f"  STRAP batch {i}-{i + len(batch)}: {len(result)}/{len(batch)} found", flush=True)
        time.sleep(0.3)

    # Step 5: Process A+B results
    pz_inserts = []
    geo_updates = 0
    val_updates = 0
    skipped_no_zd = []
    skipped_no_zoning = []

    for strap, attrs in arcgis_data.items():
        setname, row = strap_to_row[strap]
        pid = row["parcel_id"]
        zoning = attrs.get("ZONING") or ""
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY") or ""
        jid = get_jid(city)

        if setname == "A":
            if not zoning:
                skipped_no_zoning.append((row["case_number"], pid, city))
            elif pid not in existing_pz_set:
                if (jid, zoning) in known_codes:
                    pz_inserts.append({
                        "parcel_id": pid,
                        "jurisdiction_id": jid,
                        "zone_code": zoning,
                        "zone_name": zoning,
                        "source": SOURCE_TAG,
                    })
                else:
                    skipped_no_zd.append((row["case_number"], pid, zoning, jid))

        patch = {}
        if lat and lng and (not row.get("latitude") or not row.get("longitude")):
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed and not row.get("assessed_value"):
            patch["assessed_value"] = assessed
        if patch:
            status, _ = sb_patch(
                "multi_county_auctions",
                f"case_number=eq.{urllib.parse.quote(row['case_number'])}",
                patch,
            )
            if status in (200, 204):
                if "latitude" in patch:
                    geo_updates += 1
                if "assessed_value" in patch:
                    val_updates += 1

    print(f"\n  A/B: geo_updates={geo_updates} val_updates={val_updates}", flush=True)
    print(f"  skipped (no ZONING returned): {len(skipped_no_zoning)}", flush=True)
    print(f"  skipped (no zoning_districts precedent — NOT fabricated): {len(skipped_no_zd)}", flush=True)
    for s in skipped_no_zd:
        print(f"    {s}", flush=True)

    # Step 6: Insert parcel_zones
    print(f"\n--- Inserting {len(pz_inserts)} parcel_zones rows ---", flush=True)
    pz_inserted = 0
    if pz_inserts:
        CHUNK = 100
        for i in range(0, len(pz_inserts), CHUNK):
            chunk = pz_inserts[i:i + CHUNK]
            status, resp = sb_post(
                "parcel_zones", chunk, prefer="resolution=ignore-duplicates,return=minimal"
            )
            if status in (200, 201):
                pz_inserted += len(chunk)
                print(f"  chunk {i}-{i + len(chunk)}: status={status} OK", flush=True)
            else:
                print(f"  chunk {i}-{i + len(chunk)}: FAILED status={status} {resp[:200]}", flush=True)
    else:
        print("  0 rows to insert", flush=True)

    # Fail-loud invariant
    if len(pz_inserts) > 0 and pz_inserted == 0:
        raise RuntimeError(
            f"FAIL-LOUD: parsed={len(pz_inserts)} parcel_zones rows but inserted=0"
        )

    # Step 7: Address lookups for Target C
    print(f"\n--- Address lookups for Target C ({len(target_c)} rows) ---", flush=True)
    c_resolved = 0
    c_pz_inserts = 0
    c_no_match = []

    for row in target_c:
        addr = row.get("property_address", "")
        if not addr:
            continue
        attrs = query_arcgis_by_address(addr)
        if not attrs or not attrs.get("STRAP"):
            c_no_match.append((row["case_number"], addr))
            continue

        raw_strap = attrs["STRAP"]
        formatted_pid = raw_strap
        if len(raw_strap) == 18:
            formatted_pid = (
                f"{raw_strap[0:2]}-{raw_strap[2:4]}-{raw_strap[4:6]}-"
                f"{raw_strap[6:8]}-{raw_strap[8:13]}.{raw_strap[13:18]}"
            )

        zoning = attrs.get("ZONING") or ""
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY") or ""
        jid = get_jid(city)

        patch = {"parcel_id": formatted_pid}
        if lat and lng:
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed:
            patch["assessed_value"] = assessed

        status, _ = sb_patch(
            "multi_county_auctions",
            f"case_number=eq.{urllib.parse.quote(row['case_number'])}",
            patch,
        )
        if status in (200, 204):
            c_resolved += 1
            print(f"  C-resolved {row['case_number']} -> {formatted_pid} zone={zoning}", flush=True)
            if (
                zoning
                and (jid, zoning) in known_codes
                and formatted_pid not in existing_pz_set
            ):
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
        time.sleep(0.2)

    print(f"\n  C: resolved={c_resolved}/{len(target_c)}  new parcel_zones={c_pz_inserts}", flush=True)
    print(f"  C no ArcGIS match (residual, not fabricated): {len(c_no_match)}", flush=True)
    for c in c_no_match:
        print(f"    {c}", flush=True)

    print(f"""
=== SUMMARY ===
parcel_zones inserted: {pz_inserted} (+ {c_pz_inserts} from address lookups)
geo_updates: {geo_updates}
val_updates: {val_updates}
C-resolved parcel_ids: {c_resolved}
skipped_no_zoning: {len(skipped_no_zoning)}
skipped_no_zd_precedent: {len(skipped_no_zd)}
=== DONE ===
""", flush=True)


if __name__ == "__main__":
    main()
