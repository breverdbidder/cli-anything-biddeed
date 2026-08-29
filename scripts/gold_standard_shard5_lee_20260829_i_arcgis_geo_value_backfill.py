#!/usr/bin/env python3
"""GOLD STANDARD lee I fix (stage 2a), 2026-08-29 session, continuation of
gold_standard_shard5_lee_20260829_cd_harvest.py (stage 1, C/D fixed 341->428/448).

After stage 1, I (card completeness) = 323/448 (72.1%), FAIL. Live diagnosis of the
125 incomplete rows (replicating pencil_dod_evaluate_county's exact card_complete
SQL -- property_address + COALESCE(latitude,po_latitude) + COALESCE(longitude,
po_longitude) + COALESCE(assessed_value,market_value) + parcel_id linked to
v_zoning_gold_standard_card):
  12  missing property_address entirely (no parcel_id either -- unresolvable, left alone)
  20  have parcel_id + address but missing latitude/longitude
  52  have parcel_id + address but missing assessed_value/market_value
  47  have parcel_id + address/geo/value already, but fail ONLY the zoning-link join
      (handled separately by gold_standard_shard5_lee_20260829_i_zone_link.py, which
      checks G-regression risk per the lee_gsd3_0c873526 precedent before writing)
  14  have no parcel_id at all -- unresolvable via this method

THIS SCRIPT (2a) covers the lat/lng and assessed_value gaps ONLY, via the same live
Lee County ArcGIS Property Appraiser Parcels FeatureServer used by prior lee sessions
(scripts/lee_gsd3_0c873526_i_zone_link_backfill.py docstring; also
gold_standard_shard5_lee_ei_arcgis_backfill.py, gold_standard_shard12_lee_ei_backfill.py):
  https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query

STRAP FORMAT: our multi_county_auctions.parcel_id values use dashes+dot
(e.g. "12-45-23-C3-02200.0090"); the FeatureServer's STRAP field has no separators
(e.g. "124523C3022000090"). Verified live: stripping all "-" and "." from our
parcel_id and querying STRAP=<stripped> returns an exact single-feature match.

No zoning-table writes in this script (pure multi_county_auctions PATCH of
latitude/longitude/assessed_value) -- zero G-regression risk.
"""
import os
import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ARCGIS_BASE = "https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/arcgis/rest/services/Lee_County_Parcels/FeatureServer/0/query"


def strap_from_parcel_id(pid):
    return re.sub(r"[-.]", "", pid or "").strip().upper()


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def arcgis_lookup(strap):
    params = {
        "where": f"STRAP='{strap}'",
        "outFields": "STRAP,ASSESSED,JUST,SITEADDR,SITECITY,SITEZIP",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = f"{ARCGIS_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    feats = data.get("features") or []
    if not feats:
        return None
    return feats[0]


def centroid_of(geometry):
    """Rough polygon centroid (average of ring vertices) -- adequate for
    card-completeness lat/lng (not used for spatial zoning joins)."""
    if not geometry or "rings" not in geometry:
        return None, None
    pts = []
    for ring in geometry["rings"]:
        pts.extend(ring)
    if not pts:
        return None, None
    lng = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lat, lng


def main():
    # Pull tier1-eligible lee rows missing lat/lng or value but WITH a parcel_id.
    rows = rest_get(
        "multi_county_auctions?county=eq.lee"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&parcel_id=not.is.null"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value")

    targets = []
    for r in rows:
        lat = r.get("latitude") or r.get("po_latitude")
        lng = r.get("longitude") or r.get("po_longitude")
        val = r.get("assessed_value") or r.get("market_value")
        if lat is None or lng is None or val is None:
            targets.append(r)

    print(f"Targets (parcel_id present, missing lat/lng and/or value): {len(targets)}")

    latlng_fixed = 0
    value_fixed = 0
    no_arcgis_match = []
    for r in targets:
        strap = strap_from_parcel_id(r["parcel_id"])
        if not strap:
            continue
        try:
            feat = arcgis_lookup(strap)
        except Exception as e:
            print(f"  ArcGIS lookup FAILED {r['case_number']} ({strap}): {e}")
            time.sleep(0.3)
            continue
        if not feat:
            no_arcgis_match.append((r["case_number"], r["parcel_id"], strap))
            time.sleep(0.2)
            continue

        attrs = feat.get("attributes", {})
        patch_body = {}

        lat = r.get("latitude") or r.get("po_latitude")
        lng = r.get("longitude") or r.get("po_longitude")
        if lat is None or lng is None:
            c_lat, c_lng = centroid_of(feat.get("geometry"))
            if c_lat is not None and c_lng is not None:
                patch_body["latitude"] = round(c_lat, 6)
                patch_body["longitude"] = round(c_lng, 6)

        val = r.get("assessed_value") or r.get("market_value")
        if val is None:
            assessed = attrs.get("ASSESSED") or attrs.get("JUST")
            if assessed:
                patch_body["assessed_value"] = assessed

        if patch_body:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{r['id']}", patch_body)
                if "latitude" in patch_body:
                    latlng_fixed += 1
                if "assessed_value" in patch_body:
                    value_fixed += 1
                print(f"  {r['case_number']} ({strap}): patched {list(patch_body.keys())}")
            except Exception as e:
                print(f"  PATCH FAILED {r['case_number']}: {e}")
        time.sleep(0.2)

    print(f"\nTOTALS: latlng_fixed={latlng_fixed} value_fixed={value_fixed} "
          f"no_arcgis_match={len(no_arcgis_match)} of {len(targets)} targets")
    if no_arcgis_match:
        print("UNMATCHED STRAPs (real source-side gap, not fabricated):")
        for cn, pid, strap in no_arcgis_match:
            print(f"    {cn}: parcel_id={pid} strap={strap}")


if __name__ == "__main__":
    main()
