#!/usr/bin/env python3
"""Harvest Brevard parcel centroids (WGS84) + JV from FL Statewide Cadastral into
pipeline.brevard_centroid via RPC. ALT_KEY = BCPAO account = mca.parcel_id.
OBJECTID keyset pagination + get() retry + rpc() retry + large batches (pool-gentle)."""
import os, json, time, urllib.request

BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
SB = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
assert KEY, "SUPABASE_SERVICE_KEY required"
PAGE = 2000
RPC_BATCH = 2000

def get(url, tries=5):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "everest-centroids"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise last

def rpc(rows, tries=5):
    body = json.dumps({"p": rows}).encode()
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(f"{SB}/rest/v1/rpc/brevard_centroid_upsert", data=body, method="POST")
            for k, v in {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}.items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode()
        except Exception as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise last

def main():
    last_oid = 0
    total = 0
    while True:
        url = (f"{BASE}?where=CO_NO%3D15+AND+OBJECTID%3E{last_oid}"
               f"&outFields=ALT_KEY%2CJV%2COBJECTID&returnCentroid=true"
               f"&returnGeometry=false&outSR=4326&f=json"
               f"&resultRecordCount={PAGE}&orderByFields=OBJECTID")
        d = get(url)
        feats = d.get("features") or []
        if not feats:
            break
        rows = []
        max_oid = last_oid
        for ft in feats:
            attrs = ft.get("attributes") or {}
            a = attrs.get("ALT_KEY"); oid = attrs.get("OBJECTID"); c = ft.get("centroid") or {}
            if oid is not None and oid > max_oid:
                max_oid = oid
            if a and c.get("x") is not None and c.get("y") is not None:
                row = {"alt_key": str(a).strip(), "lat": c["y"], "lon": c["x"]}
                jv = attrs.get("JV")
                if jv not in (None, ""):
                    row["val"] = jv
                rows.append(row)
        for i in range(0, len(rows), RPC_BATCH):
            rpc(rows[i:i+RPC_BATCH])
            time.sleep(0.5)
        total += len(rows)
        print(f"last_oid={last_oid} feats={len(feats)} kept={len(rows)} total={total}", flush=True)
        if max_oid <= last_oid:
            break
        last_oid = max_oid
        time.sleep(0.3)
    print(f"DONE total={total}")

if __name__ == "__main__":
    main()
