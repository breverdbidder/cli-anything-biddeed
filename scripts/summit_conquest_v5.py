#!/usr/bin/env python3
"""
SUMMIT: Brevard Municipal Conquest V5 — Melbourne + Titusville
Pattern: BCPAO centroids → reproject if needed → server-side point query against city's own zoning GIS
Same proven approach as Palm Bay conquest (78K parcels, 100% match).

Melbourne: maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109
  - CRS: 3857 (Web Mercator) — must reproject from BCPAO 2881
  - Fields: ZONE_ALL (primary), ZONING, DENSCAP, DENSITY
  - Target: 62,135 parcels

Titusville: gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15
  - CRS: 2881 (native, same as BCPAO — NO reprojection needed)
  - Fields: Zone_Code, Ordinance_Number
  - Target: 28,118 parcels

After these two, remaining cities (Cocoa, Rockledge, West Melbourne, etc.) have no public
zoning GIS endpoints. They keep county overlay data only.
"""

import httpx
import json
import os
import sys
import time
import math
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

BCPAO_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

CITIES = {
    "melbourne": {
        "bcpao_city": "MELBOURNE",
        "target": 62135,
        "zoning_url": "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109",
        "zone_field": "ZONE_ALL",
        "extra_fields": "ZONING,DENSCAP,DENSITY",
        "needs_reproject": True,  # 2881 → 3857
        "target_crs": 3857,
    },
    "titusville": {
        "bcpao_city": "TITUSVILLE",
        "target": 28118,
        "zoning_url": "https://gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15",
        "zone_field": "Zone_Code",
        "extra_fields": "Ordinance_Number",
        "needs_reproject": False,  # Both in 2881
        "target_crs": 2881,
    },
}

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Municipal Conquest)"})

# ─── CRS Transform (2881 → 3857) ───────────────────────────────────────────
# EPSG:2881 = Florida State Plane East (US feet)
# Using pyproj for accurate reprojection
transformer_cache = {}

def get_transformer(from_crs, to_crs):
    key = f"{from_crs}_{to_crs}"
    if key not in transformer_cache:
        from pyproj import Transformer
        transformer_cache[key] = Transformer.from_crs(
            f"EPSG:{from_crs}", f"EPSG:{to_crs}", always_xy=True
        )
    return transformer_cache[key]


def reproject(x, y, from_crs=2881, to_crs=3857):
    t = get_transformer(from_crs, to_crs)
    return t.transform(x, y)


# ─── Utilities ──────────────────────────────────────────────────────────────

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]},
                timeout=10,
            )
        except Exception:
            pass
    print(msg)


def sb_upsert(rows):
    """Upsert to zoning_assignments table with merge-duplicates."""
    if not rows:
        return 0, 0
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i : i + 500]
        try:
            resp = c.post(
                f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                headers=h,
                json=batch,
            )
            if resp.status_code in (200, 201, 204):
                ok += len(batch)
            else:
                err += len(batch)
                if i == 0:
                    telegram(f"  ⚠️ Supabase error: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            err += len(batch)
            if i == 0:
                telegram(f"  ⚠️ Supabase exception: {str(e)[:100]}")
        time.sleep(0.3)
    return ok, err


def centroid_from_rings(rings):
    """Calculate centroid from polygon rings."""
    if not rings:
        return None, None
    ring = rings[0]
    if len(ring) < 3:
        return None, None
    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    return cx, cy


# ─── Step 1: Download parcels from BCPAO ────────────────────────────────────

def download_parcels(city_name, bcpao_city):
    """Download all parcels for a city from BCPAO with centroids in 2881."""
    telegram(f"  📦 Downloading {bcpao_city} parcels from BCPAO...")
    parcels = []
    offset = 0
    while True:
        try:
            r = c.get(
                f"{BCPAO_PARCELS}/query",
                params={
                    "where": f"CITY='{bcpao_city}'",
                    "outFields": "PARCEL_ID",
                    "returnGeometry": "true",
                    "outSR": "2881",
                    "resultOffset": offset,
                    "resultRecordCount": 2000,
                    "f": "json",
                },
            )
            data = r.json()
            feats = data.get("features", [])
            if not feats:
                break

            for f in feats:
                pid = (f["attributes"].get("PARCEL_ID") or "").strip()
                if not pid:
                    continue
                rings = f.get("geometry", {}).get("rings", [])
                cx, cy = centroid_from_rings(rings)
                if cx is None:
                    continue
                parcels.append({"pid": pid, "x": cx, "y": cy})

            offset += len(feats)
            if offset % 10000 == 0:
                telegram(f"    {offset:,} downloaded...")
            if not data.get("exceededTransferLimit") and len(feats) < 2000:
                break
            time.sleep(0.5)
        except Exception as e:
            telegram(f"    ⚠️ BCPAO error at offset {offset}: {str(e)[:80]}")
            time.sleep(2)
            continue

    # Dedup by parcel_id
    seen = {}
    for p in parcels:
        if p["pid"] not in seen:
            seen[p["pid"]] = p
    parcels = list(seen.values())
    telegram(f"  📦 {len(parcels):,} unique parcels downloaded")
    return parcels


# ─── Step 2: Query city's zoning server ─────────────────────────────────────

def query_zoning(city_key, config, parcels):
    """Query each parcel centroid against the city's zoning GIS endpoint."""
    zoning_url = config["zoning_url"]
    zone_field = config["zone_field"]
    extra_fields = config.get("extra_fields", "")
    needs_reproject = config["needs_reproject"]
    out_fields = f"{zone_field},{extra_fields}" if extra_fields else zone_field

    telegram(f"  🔍 Querying {city_key} zoning for {len(parcels):,} parcels...")

    rows = []
    misses = 0
    errors = 0
    batch_size = 100  # Progress reporting interval

    for i, p in enumerate(parcels):
        try:
            qx, qy = p["x"], p["y"]
            if needs_reproject:
                qx, qy = reproject(p["x"], p["y"], 2881, config["target_crs"])

            r = c.get(
                f"{zoning_url}/query",
                params={
                    "geometry": f"{qx},{qy}",
                    "geometryType": "esriGeometryPoint",
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": out_fields,
                    "returnGeometry": "false",
                    "f": "json",
                },
                timeout=15,
            )
            data = r.json()
            feats = data.get("features", [])

            if feats:
                attrs = feats[0]["attributes"]
                zone = (attrs.get(zone_field) or "").strip()
                if zone:
                    row = {
                        "parcel_id": p["pid"],
                        "zone_code": zone,
                        "jurisdiction": city_key,
                        "county": "brevard",
                    }
                    rows.append(row)
                else:
                    misses += 1
            else:
                misses += 1

        except Exception as e:
            errors += 1
            if errors <= 3:
                telegram(f"    ⚠️ Query error #{errors}: {str(e)[:80]}")
            time.sleep(1)  # Back off on errors
            continue

        # Rate limiting - be respectful to city servers
        if i % 10 == 0:
            time.sleep(0.1)

        # Progress reporting
        if (i + 1) % 5000 == 0:
            pct = (i + 1) / len(parcels) * 100
            telegram(f"    {i+1:,}/{len(parcels):,} ({pct:.0f}%) — {len(rows):,} hits, {misses:,} misses")

        # Flush to Supabase every 2000 hits to avoid memory buildup
        if len(rows) >= 2000:
            ok, er = sb_upsert(rows)
            telegram(f"    💾 Flushed {ok:,} to Supabase ({er} errors)")
            rows = []

    # Final flush
    if rows:
        ok, er = sb_upsert(rows)
        telegram(f"    💾 Final flush: {ok:,} to Supabase ({er} errors)")
        total_hits = ok
    else:
        total_hits = 0

    return len(parcels), total_hits + (len(rows) if rows else 0), misses, errors


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    start = time.time()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    telegram(f"🏔️ SUMMIT: Brevard Municipal Conquest V5\n📅 {now}\n")

    # Pre-flight: test each endpoint
    telegram("🔍 Pre-flight endpoint checks...")
    active_cities = {}

    for city_key, config in CITIES.items():
        try:
            r = c.get(f"{config['zoning_url']}?f=json", timeout=10)
            info = r.json()
            name = info.get("name", "unknown")
            telegram(f"  ✅ {city_key}: {name} — ALIVE")
            active_cities[city_key] = config
        except Exception as e:
            telegram(f"  ❌ {city_key}: DEAD — {str(e)[:60]}")

    if not active_cities:
        telegram("❌ No endpoints alive. Aborting.")
        return

    results = {}

    for city_key, config in active_cities.items():
        telegram(f"\n{'='*50}")
        telegram(f"🏔️ CONQUERING: {city_key.upper()}")
        telegram(f"  Target: {config['target']:,} parcels")
        telegram(f"  Endpoint: {config['zoning_url']}")
        telegram(f"  CRS: {'2881→' + str(config['target_crs']) if config['needs_reproject'] else '2881 (native)'}")
        telegram(f"{'='*50}")

        city_start = time.time()

        # Download parcels
        parcels = download_parcels(city_key, config["bcpao_city"])
        if not parcels:
            telegram(f"  ❌ No parcels found for {city_key}")
            continue

        # Query zoning
        total, hits, misses, errors = query_zoning(city_key, config, parcels)

        elapsed = time.time() - city_start
        hit_pct = (hits / total * 100) if total else 0

        results[city_key] = {
            "total": total,
            "hits": hits,
            "misses": misses,
            "errors": errors,
            "hit_pct": hit_pct,
            "elapsed_min": elapsed / 60,
        }

        telegram(f"\n📊 {city_key.upper()} RESULTS:")
        telegram(f"  Parcels: {total:,}")
        telegram(f"  Zoning hits: {hits:,} ({hit_pct:.1f}%)")
        telegram(f"  Misses: {misses:,}")
        telegram(f"  Errors: {errors:,}")
        telegram(f"  Duration: {elapsed/60:.1f}m")

    # ─── Final Summary ───────────────────────────────────────────────────
    elapsed_total = time.time() - start

    telegram(f"\n{'='*50}")
    telegram(f"🏔️ SUMMIT COMPLETE — MUNICIPAL CONQUEST V5")
    telegram(f"{'='*50}")

    for city_key, r in results.items():
        emoji = "✅" if r["hit_pct"] >= 80 else "⚠️" if r["hit_pct"] >= 50 else "❌"
        telegram(f"  {emoji} {city_key}: {r['hits']:,}/{r['total']:,} ({r['hit_pct']:.1f}%)")

    telegram(f"\n⏱️ Total duration: {elapsed_total/60:.1f}m")
    telegram(f"💰 Cost: $0")
    telegram(f"\n📋 Remaining cities without GIS portals:")
    telegram(f"  Cocoa, Rockledge, West Melbourne, Cocoa Beach,")
    telegram(f"  Satellite Beach, Cape Canaveral, Melbourne Beach,")
    telegram(f"  Indialantic, Indian Harbour Beach, Grant-Valkaria,")
    telegram(f"  Palm Shores, Melbourne Village")
    telegram(f"  → These retain county overlay data only")

    # Save results JSON
    with open("conquest_v5_results.json", "w") as f:
        json.dump(
            {
                "summit": "brevard_municipal_conquest_v5",
                "timestamp": now,
                "duration_minutes": elapsed_total / 60,
                "cities": results,
            },
            f,
            indent=2,
        )
    telegram(f"\n📁 Results saved to conquest_v5_results.json")


if __name__ == "__main__":
    main()
