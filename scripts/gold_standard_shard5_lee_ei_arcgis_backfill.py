#!/usr/bin/env python3
"""SHARD-5 (seminole/highlands/lee), dispatch 8acb0c40-fd3b-48a6-b357-fc15c79f973f.

Lee County E/I fix via the Lee County ArcGIS FeatureServer (proven live
endpoint, reused from scripts/lee_enrich_shard14.py /
scripts/lee_shard8_parcel_zones_backfill.py):

  https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/
  Lee_County_Parcels/FeatureServer/0/query

Three target sets, computed live this session against multi_county_auctions:

  A (31 rows): real parcel_id present but no parcel_zones row -> lookup by
      STRAP, insert parcel_zones + backfill geo/value if missing.
  B (7 rows):  real parcel_id present, already zoning-linked, but missing
      lat/lng -> lookup by STRAP, backfill geo/value only.
  C (5 rows):  parcel_id IS NULL but has a property_address -> lookup by
      address, backfill parcel_id (+ geo/value + parcel_zones if a
      zoning_districts row already exists for the returned code in the
      matched jurisdiction; per lee_enrich_shard14.py's own documented
      caution, do NOT insert a bare parcel_zones row for a code with no
      zoning_districts/zone_standards precedent -- that would create a new
      G-denominator entry with no chance of ever passing, i.e. a self-
      inflicted regression).

Residual (NOT touched, documented not fabricated): the 35 lee rows with
parcel_id IS NULL and property_address IS NULL. No address, no case-detail
text, no ArcGIS lookup path exists for these from this session's tools.
Confirmed same root cause as the prior firing's report: genuine source-side
gap on RealForeclose / calendar_sweep, needs a session-aware court-record
lookup (Playwright/Firecrawl-browser), not attempted here.
"""
import json
import os
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
LEE_ARCGIS = "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query"

JURISDICTION_MAP_ORDERED = [
    ("cape coral", 815),
    ("bonita springs", 914),
    ("fort myers beach", 912),
    ("sanibel", 942),
    ("fort myers", 929),  # must come after fort myers beach
]
UNINCORPORATED_OVERRIDES = [
    "north fort myers", "fort myers shores", "alva", "bokeelia",
    "lehigh acres", "st. james city", "saint james city", "captiva",
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
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(path, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=body,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json", "Prefer": prefer},
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
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
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
        "f": "json", "resultRecordCount": 2000,
    })
    req = urllib.request.Request(f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-SHARD5"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
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
        "f": "json", "resultRecordCount": 5,
    })
    req = urllib.request.Request(f"{LEE_ARCGIS}?{params}", headers={"User-Agent": "BidDeed-SHARD5"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        feats = data.get("features", [])
        return feats[0].get("attributes", {}) if feats else None
    except Exception as e:
        print(f"  address query error ({siteaddr}): {e}", flush=True)
        return None


def main():
    target_a = json.load(open("/tmp/shard5/lee_target_a.json"))
    target_b = json.load(open("/tmp/shard5/lee_target_b.json"))
    target_c = json.load(open("/tmp/shard5/lee_target_c.json"))
    print(f"Targets: A(no parcel_zones)={len(target_a)} B(no geo)={len(target_b)} C(no parcel_id)={len(target_c)}", flush=True)

    # known zoning_districts (jurisdiction_id, code) so we never insert a
    # parcel_zones row pointing at a code with zero G-standards precedent
    zd_rows = sb_get("zoning_districts", "select=jurisdiction_id,code&limit=2000")
    known_codes = {(r["jurisdiction_id"], r["code"]) for r in zd_rows}

    existing_pz = sb_get("parcel_zones", "jurisdiction_id=in.(630,815,914,912,929,942)&select=parcel_id&limit=2000")
    existing_pz_set = {r["parcel_id"] for r in existing_pz}

    # ---- A + B: STRAP lookups ----
    strap_to_row = {}
    for r in target_a:
        strap_to_row[normalize_strap(r["parcel_id"])] = ("A", r)
    for r in target_b:
        strap_to_row[normalize_strap(r["parcel_id"])] = ("B", r)

    all_straps = list(strap_to_row.keys())
    arcgis_data = {}
    BATCH = 40
    for i in range(0, len(all_straps), BATCH):
        batch = all_straps[i:i + BATCH]
        result = query_arcgis_by_straps(batch)
        arcgis_data.update(result)
        print(f"  STRAP batch {i}-{i+len(batch)}: {len(result)}/{len(batch)} found", flush=True)
        time.sleep(0.3)

    pz_inserts = []
    geo_updates = 0
    val_updates = 0
    skipped_no_zd_precedent = []

    for strap, attrs in arcgis_data.items():
        setname, row = strap_to_row[strap]
        pid = row["parcel_id"]
        zoning = attrs.get("ZONING", "")
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)

        if setname == "A" and zoning and pid not in existing_pz_set:
            if (jid, zoning) in known_codes:
                pz_inserts.append({
                    "parcel_id": pid, "jurisdiction_id": jid,
                    "zone_code": zoning, "zone_name": zoning,
                    "source": "shard5_8acb0c40_lee_arcgis",
                })
            else:
                skipped_no_zd_precedent.append((row["case_number"], pid, zoning, jid))

        patch = {}
        if lat and lng:
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed:
            patch["assessed_value"] = assessed
        if patch:
            status, _ = sb_patch("multi_county_auctions", f"case_number=eq.{urllib.parse.quote(row['case_number'])}", patch)
            if status in (200, 204):
                if "latitude" in patch:
                    geo_updates += 1
                if "assessed_value" in patch:
                    val_updates += 1

    print(f"\nA/B results: geo_updates={geo_updates} val_updates={val_updates}", flush=True)
    print(f"skipped (no zoning_districts precedent, NOT fabricated): {len(skipped_no_zd_precedent)}", flush=True)
    for s in skipped_no_zd_precedent:
        print(f"  {s}", flush=True)

    if pz_inserts:
        status, resp = sb_post("parcel_zones", pz_inserts, prefer="resolution=ignore-duplicates,return=minimal")
        print(f"parcel_zones insert ({len(pz_inserts)} rows): status={status}", flush=True)
    else:
        print("parcel_zones insert: 0 rows", flush=True)

    # ---- C: address lookups (parcel_id IS NULL) ----
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
        zoning = attrs.get("ZONING", "")
        lat = attrs.get("LATITUDE")
        lng = attrs.get("LONGITUDE")
        assessed = attrs.get("ASSESSED") or attrs.get("JUST")
        city = attrs.get("SITECITY", "")
        jid = get_jid(city)

        patch = {"parcel_id": formatted}
        if lat and lng:
            patch["latitude"] = lat
            patch["longitude"] = lng
        if assessed:
            patch["assessed_value"] = assessed
        status, _ = sb_patch("multi_county_auctions", f"case_number=eq.{urllib.parse.quote(row['case_number'])}", patch)
        if status in (200, 204):
            c_resolved += 1
            print(f"  C-resolved {row['case_number']} -> parcel_id={formatted} zone={zoning}", flush=True)
            if zoning and (jid, zoning) in known_codes and formatted not in existing_pz_set:
                s2, _ = sb_post("parcel_zones", [{
                    "parcel_id": formatted, "jurisdiction_id": jid,
                    "zone_code": zoning, "zone_name": zoning,
                    "source": "shard5_8acb0c40_lee_arcgis_addr",
                }], prefer="resolution=ignore-duplicates,return=minimal")
                if s2 in (200, 201):
                    c_pz_inserts += 1
        time.sleep(0.2)

    print(f"\nC results: resolved={c_resolved}/{len(target_c)}  new parcel_zones={c_pz_inserts}", flush=True)
    print(f"C no ArcGIS match (residual, not fabricated): {len(c_no_match)}", flush=True)
    for c in c_no_match:
        print(f"  {c}", flush=True)

    print("\n=== DONE ===", flush=True)


if __name__ == "__main__":
    main()
