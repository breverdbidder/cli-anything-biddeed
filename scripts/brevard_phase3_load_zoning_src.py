#!/usr/bin/env python3
"""Paginate an ArcGIS FeatureServer/MapServer query endpoint (GeoJSON) into
zw_zoning_src for co_no=15. Usage:
  python3 scripts/brevard_phase3_load_zoning_src.py <endpoint_url> <jurisdiction> <zone_field> <source_layer> [dencap_field]
"""
import sys, os, json, time, httpx

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT = f"https://api.supabase.com/v1/projects/{REF}/database/query"


def run_sql(query: str, retries=4):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(retries):
        try:
            r = httpx.post(MGMT, headers=h, json={"query": query}, timeout=120)
        except httpx.TransportError as e:
            last_err = RuntimeError(f"transport error: {e}")
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code in (502, 503, 504, 524):
            last_err = RuntimeError(f"SQL failed {r.status_code} (transient gateway)")
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code >= 300:
            raise RuntimeError(f"SQL failed {r.status_code}: {r.text[:2000]}")
        return r.json()
    raise last_err


def insert_rows(rows, batch_size=100):
    """Insert with adaptive batch size: halve on 413 until it fits."""
    i = 0
    bs = batch_size
    inserted = 0
    while i < len(rows):
        chunk = rows[i : i + bs]
        values = ",\n".join(chunk)
        q = f"""
insert into zw_zoning_src (co_no, jurisdiction, zone_code, source_layer, source_url, geom)
values
{values};
"""
        try:
            run_sql(q)
            inserted += len(chunk)
            i += bs
        except RuntimeError as e:
            if "413" in str(e) and bs > 1:
                bs = max(1, bs // 2)
                continue
            raise
    return inserted


def esc(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def fetch_page(base_url, zone_field, offset, page_size=1000):
    params = {
        "where": "1=1",
        "outFields": zone_field,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": page_size,
    }
    r = httpx.get(base_url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    base_url, jurisdiction, zone_field, source_layer = sys.argv[1:5]
    page_size = 1000
    sub_batch = 100
    offset = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    total_loaded = 0
    total_skipped = 0
    while True:
        data = fetch_page(base_url, zone_field, offset, page_size)
        feats = data.get("features", [])
        if not feats:
            break
        rows = []
        for f in feats:
            props = f.get("properties", {})
            zone = props.get(zone_field)
            geom = f.get("geometry")
            if not geom or not zone:
                total_skipped += 1
                continue
            gj = json.dumps(geom).replace("'", "''")
            rows.append(
                f"(15, {esc(jurisdiction)}, {esc(zone)}, {esc(source_layer)}, "
                f"{esc(base_url)}, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON('{gj}'), 4326)))"
            )
        if rows:
            total_loaded += insert_rows(rows, sub_batch)
        print(f"offset={offset} fetched={len(feats)} loaded_cum={total_loaded} skipped_cum={total_skipped}", flush=True)
        if len(feats) < page_size:
            break
        offset += page_size
        time.sleep(0.2)
    print(f"DONE jurisdiction={jurisdiction} total_loaded={total_loaded} total_skipped={total_skipped}")


if __name__ == "__main__":
    main()
