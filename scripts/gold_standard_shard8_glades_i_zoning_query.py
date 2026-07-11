#!/usr/bin/env python3
"""
gold_standard_shard8_glades_i_zoning_query.py

Read-only research/query script (NOT the migration itself). For each of
glades' 65 unique lat/lon-enriched parcels, point-in-polygon queries the
LIVE Glades County Zoning ArcGIS MapServer (Hendry County Property
Appraiser-hosted, discovered live 2026-07-11 via web search + curl probe):

  https://gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer
    layer 1 = MH_Zoning       (Moore Haven city zoning, field Z010_ZONG)
    layer 2 = county_zoning   (unincorporated Glades zoning, field Zoning / ZonDistNam)

For each parcel, queries layer 2 first (covers the whole county per its
fullExtent), falls back to layer 1 if layer 2 returns no feature. Prints a
Python list of (parcel_id, jurisdiction_id, zone_code, zone_name, lon, lat)
tuples for parcels that got a real match, and lists any that returned zero
features from BOTH layers (left unlinked, not fabricated).

This script only prints results -- it does not write to the DB. The
migration SQL is hand-assembled from this output.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

MAPSERVER = "https://gis1.hcpao.org/arcgiscv/rest/services/Glades/GladesCounty_Zoning/MapServer"

JURISDICTION_MOORE_HAVEN = 899
JURISDICTION_UNINCORPORATED = 1153


def get(url):
    req = urllib.request.Request(url, headers=H, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def query_layer(layer_id, lon, lat):
    url = MAPSERVER + f"/{layer_id}/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "curl/8"})
    # gis1.hcpao.org cert chain issue observed with system CA store during
    # discovery (curl -k required); use an unverified SSL context here to
    # match -- this is a read-only GET against a public county GIS endpoint.
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        return json.loads(resp.read().decode())


def main():
    rows = get(
        f"{SB}/rest/v1/multi_county_auctions"
        "?county=eq.glades&select=case_number,parcel_id,latitude,longitude"
        "&order=case_number&limit=200"
    )
    with_ll = [r for r in rows if r["latitude"] is not None and r["longitude"] is not None]
    seen = {}
    for r in with_ll:
        seen.setdefault(r["parcel_id"], r)
    unique_parcels = list(seen.values())
    print(f"Querying {len(unique_parcels)} unique glades parcels against live Glades County Zoning MapServer...")

    matched = []
    unmatched = []
    for r in unique_parcels:
        pid = r["parcel_id"]
        lat, lon = r["latitude"], r["longitude"]
        feats = query_layer(2, lon, lat).get("features", [])
        source_layer = "county_zoning"
        jurisdiction_id = JURISDICTION_UNINCORPORATED
        if not feats:
            feats = query_layer(1, lon, lat).get("features", [])
            source_layer = "MH_Zoning"
            jurisdiction_id = JURISDICTION_MOORE_HAVEN
        if not feats:
            unmatched.append((pid, lat, lon))
            print(f"  NO MATCH  {pid}  ({lat},{lon})")
            continue
        attrs = feats[0]["attributes"]
        if source_layer == "county_zoning":
            zone_code = (attrs.get("Zoning") or "").strip()
            zone_name = (attrs.get("ZonDistNam") or "").strip()
        else:
            zone_code = (attrs.get("Z010_ZONG") or "").strip()
            zone_name = (attrs.get("Z020_FLUM") or "").strip()
        if not zone_code:
            unmatched.append((pid, lat, lon))
            print(f"  EMPTY ZONE  {pid}  ({lat},{lon}) layer={source_layer} attrs={attrs}")
            continue
        matched.append((pid, jurisdiction_id, zone_code, zone_name, lon, lat, source_layer))
        print(f"  OK  {pid}  jurisdiction={jurisdiction_id}  zone={zone_code!r} ({zone_name!r})  layer={source_layer}")

    print(f"\nMatched: {len(matched)} / {len(unique_parcels)}")
    print(f"Unmatched: {len(unmatched)}")
    print("\nDistinct zone codes by jurisdiction:")
    from collections import defaultdict
    by_j = defaultdict(set)
    for pid, jid, code, name, lon, lat, layer in matched:
        by_j[jid].add((code, name))
    for jid, codes in by_j.items():
        print(f"  jurisdiction {jid}: {sorted(codes)}")

    print("\n--- RAW MATCHED (for migration assembly) ---")
    for row in matched:
        print(row)


if __name__ == "__main__":
    main()
