#!/usr/bin/env python3
"""
PALM BAY V5 — Modal parallel per-centroid GIS queries.

Same PROVEN approach as V4 (BCPAO centroids → PB GIS per-centroid),
but parallelized across Modal containers. 78K parcels in ~5 min vs 10 hours.

Architecture:
  1. Download 78K parcels from BCPAO (sequential, ~2 min)
  2. Split into 20 chunks of ~4K each
  3. Fan out Modal containers — each queries PB GIS per-centroid
  4. Aggregate results
  5. Upsert to Supabase
"""
import modal
import json
import os
import time

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("httpx>=0.25", "shapely>=2.0")
)

app = modal.App("zonewise-palmbay", image=image)

BCPAO = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5/query"
PB_ZONING = "https://gis.palmbayflorida.org/arcgis/rest/services/GrowthManagement/Zoning/MapServer/0/query"


@app.function(timeout=600, retries=modal.Retries(max_retries=1))
def zone_chunk(chunk_id: int, parcels: list[dict]) -> dict:
    """Query Palm Bay GIS for a chunk of parcels. Runs in parallel container."""
    import httpx
    import time as _time

    start = _time.monotonic()
    c = httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0 (ZoneWise/v5)"})

    rows = []
    errors = 0

    for i, p in enumerate(parcels):
        try:
            r = c.get(PB_ZONING, params={
                "geometry": f"{p['x']},{p['y']}",
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONING",
                "returnGeometry": "false",
                "f": "json",
            }, timeout=10)
            feats = r.json().get("features", [])
            if feats:
                zone = feats[0]["attributes"].get("ZONING", "")
                if zone:
                    rows.append({
                        "parcel_id": p["pid"],
                        "zone_code": zone.strip(),
                        "jurisdiction": "palm_bay",
                        "county": "brevard",
                    })
                else:
                    errors += 1
            else:
                errors += 1
        except Exception:
            errors += 1

        # Gentle throttle to not hammer PB GIS
        if (i + 1) % 50 == 0:
            _time.sleep(0.3)

    elapsed = _time.monotonic() - start
    return {
        "chunk_id": chunk_id,
        "total": len(parcels),
        "zoned": len(rows),
        "errors": errors,
        "elapsed": round(elapsed, 1),
        "rows": rows,
    }


@app.function(timeout=1800)
def orchestrate(
    chunk_size: int = 4000,
    supabase_url: str = "",
    supabase_key: str = "",
    telegram_bot: str = "",
    telegram_chat: str = "",
) -> dict:
    """Download parcels, fan out, aggregate, upsert."""
    import httpx
    import urllib.parse

    def tg(msg):
        if telegram_bot and telegram_chat:
            try:
                httpx.post(
                    f"https://api.telegram.org/bot{telegram_bot}/sendMessage",
                    data={"chat_id": telegram_chat, "text": msg[:4000], "parse_mode": "HTML"},
                    timeout=10,
                )
            except:
                pass
        print(msg)

    start = time.time()
    tg("<b>🏔️ PALM BAY V5 — Modal Parallel</b>\n")

    c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise/v5)"})

    # Test PB GIS
    try:
        r = c.get(PB_ZONING, params={
            "geometry": "770000,1310000",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ZONING",
            "returnGeometry": "false",
            "f": "json",
        }, timeout=10)
        feats = r.json().get("features", [])
        test = feats[0]["attributes"]["ZONING"] if feats else None
    except:
        test = None

    tg(f"  PB GIS test: {test}")
    if not test:
        tg("  ❌ Palm Bay GIS not responding. Aborting.")
        return {"status": "PB_GIS_DOWN"}

    # Step 1: Download parcels from BCPAO
    tg("\n🏔️ Step 1: Downloading parcels from BCPAO...")
    parcels = []
    offset = 0
    encoded = urllib.parse.quote("PALM BAY")

    while True:
        r = c.get(BCPAO, params={
            "where": f"CITY='{urllib.parse.unquote(encoded)}'",
            "outFields": "PARCEL_ID",
            "returnGeometry": "true",
            "outSR": "2881",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json",
        })
        feats = r.json().get("features", [])
        if not feats:
            break
        for f in feats:
            pid = (f["attributes"].get("PARCEL_ID") or "").strip()
            if not pid:
                continue
            rings = f.get("geometry", {}).get("rings", [])
            if not rings:
                continue
            ring = rings[0]
            cx = sum(p[0] for p in ring) / len(ring)
            cy = sum(p[1] for p in ring) / len(ring)
            parcels.append({"pid": pid, "x": cx, "y": cy})
        offset += len(feats)
        if offset % 10000 == 0:
            tg(f"  {offset:,} parcels downloaded...")
        if not r.json().get("exceededTransferLimit") and len(feats) < 2000:
            break
        time.sleep(0.5)

    # Dedup
    seen = {}
    for p in parcels:
        if p["pid"] not in seen:
            seen[p["pid"]] = p
    parcels = list(seen.values())
    tg(f"  ✅ {len(parcels):,} unique parcels")

    # Step 2: Split and fan out
    chunks = [parcels[i:i + chunk_size] for i in range(0, len(parcels), chunk_size)]
    num_chunks = len(chunks)
    tg(f"\n🏔️ Step 2: Launching {num_chunks} parallel containers ({chunk_size}/chunk)...")

    all_rows = []
    total_zoned = 0
    total_errors = 0
    chunk_ids = list(range(num_chunks))

    for result in zone_chunk.map(chunk_ids, chunks, return_exceptions=True):
        if isinstance(result, Exception):
            tg(f"  ❌ Chunk failed: {result}")
            total_errors += 1
            continue

        total_zoned += result["zoned"]
        total_errors += result["errors"]
        all_rows.extend(result["rows"])
        tg(f"  Chunk {result['chunk_id']}: {result['zoned']}/{result['total']} "
           f"({result['zoned']/max(result['total'],1)*100:.0f}%) in {result['elapsed']}s")

    match_pct = round(total_zoned / max(len(parcels), 1) * 100, 1)
    tg(f"\n  📊 Total: {total_zoned:,} zoned ({match_pct}%), {total_errors:,} unzoned")

    # Step 3: Upsert to Supabase
    if all_rows and supabase_url and supabase_key:
        tg(f"\n🏔️ Step 3: Upserting {len(all_rows):,} records...")
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }
        ok = err = 0
        for i in range(0, len(all_rows), 500):
            batch = all_rows[i:i + 500]
            resp = c.post(
                f"{supabase_url}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                headers=headers,
                json=batch,
            )
            if resp.status_code in (200, 201, 204):
                ok += len(batch)
            else:
                err += len(batch)
                if i == 0:
                    tg(f"  ⚠️ Supabase: {resp.status_code} {resp.text[:200]}")
            time.sleep(0.2)
        tg(f"  ✅ Upserted: {ok:,} ok, {err:,} err")

    elapsed = int(time.time() - start)
    summary = f"""
🏔️ <b>PALM BAY V5 COMPLETE</b>

📊 Parcels: {len(parcels):,}
📊 Zoned: {total_zoned:,} ({match_pct}%)
📊 Unzoned: {total_errors:,}
📊 Chunks: {num_chunks} parallel

⏱️ Duration: {elapsed // 60}m {elapsed % 60}s
💰 Cost: ~$0.01 (Modal free tier)"""
    tg(summary)

    return {
        "status": "COMPLETE",
        "parcels": len(parcels),
        "zoned": total_zoned,
        "match_pct": match_pct,
        "elapsed": elapsed,
    }


@app.local_entrypoint()
def main():
    result = orchestrate.remote(
        chunk_size=4000,
        supabase_url=os.environ.get("SUPABASE_URL", ""),
        supabase_key=os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", ""),
        telegram_bot=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat=os.environ.get("TELEGRAM_CHAT_ID", ""),
    )
    print(json.dumps(result, indent=2))
