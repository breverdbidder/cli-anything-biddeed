#!/usr/bin/env python3
"""Harvest Brevard parcel centroids (WGS84) + JV market value from the FL Statewide
Cadastral FeatureServer into pipeline.brevard_centroid via RPC. Keyed by ALT_KEY =
BCPAO tax account = multi_county_auctions.parcel_id. Geo + value source for criterion I.
Authoritative (FL DOR), allowlist, open (no Cloudflare)."""
import os, json, time, urllib.request

BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
SB = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
assert KEY, "SUPABASE_SERVICE_KEY required"
PAGE = 2000

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "everest-centroids"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def rpc(rows):
    body = json.dumps({"p": rows}).encode()
    req = urllib.request.Request(f"{SB}/rest/v1/rpc/brevard_centroid_upsert", data=body, method="POST")
    for k, v in {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()

def main():
    offset = 0
    total = 0
    while True:
        url = (f"{BASE}?where=CO_NO%3D15&outFields=ALT_KEY%2CJV&returnCentroid=true"
               f"&returnGeometry=false&outSR=4326&f=json"
               f"&resultRecordCount={PAGE}&resultOffset={offset}&orderByFields=OBJECTID")
        d = get(url)
        feats = d.get("features") or []
        if not feats:
            break
        rows = []
        for ft in feats:
            attrs = ft.get("attributes") or {}
            a = attrs.get("ALT_KEY")
            c = ft.get("centroid") or {}
            if a and c.get("x") is not None and c.get("y") is not None:
                row = {"alt_key": str(a).strip(), "lat": c["y"], "lon": c["x"]}
                jv = attrs.get("JV")
                if jv not in (None, ""):
                    row["val"] = jv
                rows.append(row)
        for i in range(0, len(rows), 500):
            rpc(rows[i:i+500])
        total += len(rows)
        print(f"offset={offset} feats={len(feats)} kept={len(rows)} total={total}", flush=True)
        if not d.get("exceededTransferLimit") and len(feats) < PAGE:
            break
        offset += PAGE
        time.sleep(0.2)
    print(f"DONE total={total}")

if __name__ == "__main__":
    main()
