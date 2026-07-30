#!/usr/bin/env python3
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
ARCGIS_BASE = "https://arcgis5.roktech.net/arcgis/rest/services/GoMaps4/MapServer"

print(f"SB_KEY={'SET' if SB_KEY else 'NOT_SET'}", flush=True)
print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}", flush=True)

def fetch(url, method="GET", data=None, headers=None):
    h = headers or {}
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)

def sb_get(path, params=None):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
    status, body = fetch(url, headers=h)
    if status == 200:
        return json.loads(body)
    print(f"sb_get {path}: HTTP {status}: {body[:200]}")
    return None

def arcgis_query(layer, where, out_fields="*"):
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json"
    }
    url = f"{ARCGIS_BASE}/{layer}/query?" + urllib.parse.urlencode(params)
    status, body = fetch(url)
    if status == 200:
        return json.loads(body)
    print(f"arcgis layer={layer} where={where}: HTTP {status}: {body[:100]}")
    return None

print("\n=== Step 1: Gulf ArcGIS MapServer info ===")
status, body = fetch(f"{ARCGIS_BASE}?f=json")
print(f"HTTP {status}")
if status == 200:
    data = json.loads(body)
    layers = data.get("layers", [])
    print(f"Layers ({len(layers)}):")
    for l in layers:
        print(f"  {l['id']}: {l['name']}")

print("\n=== Step 2: Probe parcel 05762000R (Port St Joe, zoning unknown) ===")
r = arcgis_query(12, "PIN='05762000R'")
if r:
    feats = r.get("features", [])
    print(f"  Features: {len(feats)}")
    for f in feats:
        print(f"  Attrs: {json.dumps(f.get('attributes', {}), indent=2)}")

print("\n=== Step 3: Probe parcel 05004050R (Port St Joe, zone=VLR per refuted claim) ===")
r = arcgis_query(12, "PIN='05004050R'")
if r:
    feats = r.get("features", [])
    print(f"  Features: {len(feats)}")
    for f in feats:
        print(f"  Attrs: {json.dumps(f.get('attributes', {}), indent=2)}")

print("\n=== Step 4: Probe parcel 03426604R (genuinely addressless) ===")
r = arcgis_query(12, "PIN='03426604R'")
if r:
    feats = r.get("features", [])
    print(f"  Features: {len(feats)}")
    for f in feats:
        print(f"  Attrs: {json.dumps(f.get('attributes', {}), indent=2)}")

print("\n=== Step 5: Probe parcel 00469000R (genuinely addressless) ===")
r = arcgis_query(12, "PIN='00469000R'")
if r:
    feats = r.get("features", [])
    print(f"  Features: {len(feats)}")
    for f in feats:
        print(f"  Attrs: {json.dumps(f.get('attributes', {}), indent=2)}")

if not SB_KEY:
    print("\nNo SB_KEY — skipping Supabase queries")
    sys.exit(0)

print("\n=== Step 6: pencil_dod_evaluate_county('gulf') via RPC ===")
body = json.dumps({"p_county": "gulf"}).encode()
req = urllib.request.Request(
    f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
    data=body,
    headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
        print("pencil_dod result:")
        if isinstance(result, list):
            for row in result:
                letter = (row.get("letter") or "").upper()
                passed = row.get("pass")
                metric = row.get("metric")
                detail = row.get("detail") or ""
                print(f"  {letter}: {'PASS' if passed else 'FAIL'}  metric={metric}  {detail[:120]}")
        else:
            print(json.dumps(result, indent=2))
except Exception as e:
    print(f"RPC error: {e}")

print("\n=== Step 7: All gulf MCA rows ===")
rows = sb_get("multi_county_auctions", {
    "county": "eq.gulf",
    "select": "case_number,parcel_id,property_address,parity_status,latitude,assessed_value",
    "order": "case_number.asc",
    "limit": "50"
})
if rows:
    print(f"Total gulf rows: {len(rows)}")
    for r in rows:
        case = r.get("case_number") or ""
        parcel = r.get("parcel_id") or "NULL"
        parity = r.get("parity_status") or "NULL"
        addr = bool(r.get("property_address"))
        geo = bool(r.get("latitude"))
        val = bool(r.get("assessed_value"))
        print(f"  {case:<32} parcel={parcel:<15} parity={parity:<20} addr={addr} geo={geo} val={val}")
    
    null_parcel = [r["case_number"] for r in rows if not r.get("parcel_id")]
    unmatched = [r["case_number"] for r in rows if r.get("parity_status") not in ("matched_clean", "matched_divergent")]
    no_e = [r["case_number"] for r in rows if not r.get("parcel_id")]
    print(f"\nNull parcel_id (E gap): {null_parcel}")
    print(f"Unmatched C/D: {unmatched}")

print(f"\nDone at {datetime.now(timezone.utc).isoformat()}")
