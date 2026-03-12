"""
ZoneWise Modal Spatial App
==========================
Modal.com serverless infrastructure for parallel spatial zoning.

Agents:
  1. SpatialZoner    - STRtree parcel→zone matching (per chunk)
  2. CountyOrchestrator - Splits parcels, fans out, aggregates
  3. SupabaseWriter  - Bulk upserts results to Supabase

Architecture:
  Orchestrator → .map(SpatialZoner, chunks) → SupabaseWriter → Done

Cost: ~$0.02/run for 78K parcels (well within $30/mo free tier)
"""

import modal
import json
import os
import pickle
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Modal Image: Python 3.11 + spatial libs + supabase
# ---------------------------------------------------------------------------
spatial_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "shapely>=2.0",
        "requests>=2.31",
        "supabase>=2.0",
        "httpx>=0.25",
    )
)

app = modal.App("zonewise-spatial", image=spatial_image)

# ---------------------------------------------------------------------------
# Shared Volume for polygon cache (avoids re-downloading per container)
# ---------------------------------------------------------------------------
polygon_cache = modal.Volume.from_name("zonewise-polygon-cache", create_if_missing=True)

# ---------------------------------------------------------------------------
# Secrets (set via `modal secret create zonewise-secrets ...`)
# ---------------------------------------------------------------------------
# Required secrets:
#   SUPABASE_URL, SUPABASE_SERVICE_KEY
#   (Optional) BCPAO_API_BASE for parcel fetching


@dataclass
class ZoneResult:
    """Single parcel zoning result."""
    parcel_id: str
    account_number: str
    latitude: float
    longitude: float
    zone_code: str
    zone_district: str
    zone_description: str
    match_confidence: float  # 0.0-1.0
    county: str
    matched_at: str  # ISO timestamp


@dataclass
class ChunkResult:
    """Result from processing one chunk of parcels."""
    chunk_id: int
    total_parcels: int
    matched: int
    unmatched: int
    elapsed_seconds: float
    results: list = field(default_factory=list)
    errors: list = field(default_factory=list)


# ===========================================================================
# AGENT 1: SpatialZoner — Runs inside each Modal container
# ===========================================================================
@app.function(
    timeout=600,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
    volumes={"/cache": polygon_cache},
)
def spatial_zoner(
    chunk_id: int,
    parcel_chunk: list[dict],
    county: str,
) -> dict:
    """
    Match a chunk of parcels against zoning polygons using Shapely STRtree.

    Each Modal container:
    1. Loads cached polygons from Volume (or downloads once)
    2. Builds STRtree index
    3. Matches all parcels in chunk
    4. Returns ChunkResult as dict
    """
    from shapely.geometry import Point, shape
    from shapely import STRtree
    import time as _time
    from datetime import datetime, timezone

    start = _time.monotonic()

    # --- Load polygons from cache or fetch ---
    cache_path = f"/cache/{county}_polygons.pkl"
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            polygon_data = pickle.load(f)
    else:
        # Fetch from GIS endpoint (Brevard example)
        polygon_data = _fetch_zoning_polygons(county)
        os.makedirs("/cache", exist_ok=True)
        with open(cache_path, "wb") as f:
            pickle.dump(polygon_data, f)

    # --- Build STRtree ---
    geometries = []
    zone_attrs = []
    for feat in polygon_data["features"]:
        try:
            geom = shape(feat["geometry"])
            geometries.append(geom)
            props = feat.get("properties", {})
            zone_attrs.append({
                "zone_code": props.get("ZONING", props.get("ZONE_CODE", "UNKNOWN")),
                "zone_district": props.get("ZONE_DIST", props.get("DISTRICT", "")),
                "zone_description": props.get("ZONE_DESC", props.get("DESCRIPTION", "")),
            })
        except Exception:
            continue

    tree = STRtree(geometries)

    # --- Match parcels ---
    results = []
    errors = []
    matched = 0

    for parcel in parcel_chunk:
        try:
            lat = float(parcel.get("latitude", 0))
            lon = float(parcel.get("longitude", 0))
            if lat == 0 or lon == 0:
                errors.append({"parcel_id": parcel.get("parcel_id", "?"), "error": "no_coordinates"})
                continue

            point = Point(lon, lat)
            idx = tree.nearest(point)

            if idx is not None and geometries[idx].contains(point):
                confidence = 1.0
            elif idx is not None:
                dist = geometries[idx].distance(point)
                confidence = max(0.0, 1.0 - (dist / 0.001))  # decay over ~100m
            else:
                confidence = 0.0

            if idx is not None and confidence > 0.5:
                attr = zone_attrs[idx]
                results.append(asdict(ZoneResult(
                    parcel_id=parcel.get("parcel_id", ""),
                    account_number=parcel.get("account_number", ""),
                    latitude=lat,
                    longitude=lon,
                    zone_code=attr["zone_code"],
                    zone_district=attr["zone_district"],
                    zone_description=attr["zone_description"],
                    match_confidence=round(confidence, 4),
                    county=county,
                    matched_at=datetime.now(timezone.utc).isoformat(),
                )))
                matched += 1
            else:
                errors.append({"parcel_id": parcel.get("parcel_id", "?"), "error": "low_confidence"})

        except Exception as e:
            errors.append({"parcel_id": parcel.get("parcel_id", "?"), "error": str(e)})

    elapsed = _time.monotonic() - start

    return asdict(ChunkResult(
        chunk_id=chunk_id,
        total_parcels=len(parcel_chunk),
        matched=matched,
        unmatched=len(parcel_chunk) - matched,
        elapsed_seconds=round(elapsed, 2),
        results=results,
        errors=errors[:50],  # cap error list
    ))


def _fetch_zoning_polygons(county: str) -> dict:
    """
    Fetch zoning polygons from county GIS endpoint.
    Returns GeoJSON FeatureCollection.
    """
    import requests

    # County GIS endpoints registry
    endpoints = {
        "brevard": {
            "url": "https://gis.brevardfl.gov/gissrv/rest/services/PublicWorks/Zoning/MapServer/0/query",
            "params": {
                "where": "1=1",
                "outFields": "ZONING,ZONE_DESC,ZONE_DIST",
                "f": "geojson",
                "returnGeometry": "true",
                "resultRecordCount": 15000,
            }
        },
        # Add more counties here as discovered
    }

    county_key = county.lower().replace(" ", "_").replace("-", "_")

    if county_key not in endpoints:
        raise ValueError(f"No GIS endpoint configured for county: {county}. "
                         f"Available: {list(endpoints.keys())}")

    cfg = endpoints[county_key]
    resp = requests.get(cfg["url"], params=cfg["params"], timeout=120)
    resp.raise_for_status()
    return resp.json()


# ===========================================================================
# AGENT 2: CountyOrchestrator — Splits, fans out, aggregates
# ===========================================================================
@app.function(timeout=1800)
def county_orchestrator(
    county: str,
    chunk_size: int = 5000,
    max_parallel: int = 20,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
) -> dict:
    """
    Orchestrate parallel zoning for an entire county.

    1. Fetch all parcels for county from Supabase
    2. Split into chunks
    3. Fan out via spatial_zoner.map()
    4. Aggregate results
    5. Write back to Supabase
    """
    import time as _time
    from datetime import datetime, timezone

    start = _time.monotonic()

    sb_url = supabase_url or os.environ.get("SUPABASE_URL", "")
    sb_key = supabase_key or os.environ.get("SUPABASE_SERVICE_KEY", "")

    # --- Step 1: Fetch parcels ---
    print(f"[Orchestrator] Fetching parcels for {county}...")
    parcels = _fetch_parcels_from_supabase(county, sb_url, sb_key)
    total = len(parcels)
    print(f"[Orchestrator] {total} parcels loaded")

    if total == 0:
        return {
            "county": county,
            "status": "NO_PARCELS",
            "total": 0,
            "matched": 0,
            "elapsed_seconds": 0,
        }

    # --- Step 2: Chunk ---
    chunks = [parcels[i:i + chunk_size] for i in range(0, total, chunk_size)]
    num_chunks = len(chunks)
    print(f"[Orchestrator] Split into {num_chunks} chunks of ~{chunk_size}")

    # --- Step 3: Fan out with Modal .map() ---
    print(f"[Orchestrator] Launching {num_chunks} parallel containers...")

    chunk_ids = list(range(num_chunks))
    counties = [county] * num_chunks

    all_results = []
    total_matched = 0
    total_errors = 0

    for chunk_result in spatial_zoner.map(
        chunk_ids,
        chunks,
        counties,
        return_exceptions=True,
    ):
        if isinstance(chunk_result, Exception):
            print(f"[Orchestrator] Chunk failed: {chunk_result}")
            total_errors += 1
            continue

        cr = chunk_result
        total_matched += cr["matched"]
        all_results.extend(cr["results"])
        print(f"[Orchestrator] Chunk {cr['chunk_id']}: "
              f"{cr['matched']}/{cr['total_parcels']} matched "
              f"in {cr['elapsed_seconds']}s")

    # --- Step 4: Write to Supabase ---
    if all_results and sb_url and sb_key:
        print(f"[Orchestrator] Writing {len(all_results)} results to Supabase...")
        write_count = supabase_bulk_writer.remote(all_results, sb_url, sb_key)
        print(f"[Orchestrator] Wrote {write_count} rows")

    elapsed = _time.monotonic() - start
    match_rate = round(total_matched / total * 100, 2) if total > 0 else 0

    summary = {
        "county": county,
        "status": "COMPLETE",
        "total_parcels": total,
        "total_matched": total_matched,
        "match_rate_pct": match_rate,
        "num_chunks": num_chunks,
        "chunk_errors": total_errors,
        "elapsed_seconds": round(elapsed, 2),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    print(f"\n{'='*60}")
    print(f"[Orchestrator] COMPLETE: {county}")
    print(f"  Parcels:    {total}")
    print(f"  Matched:    {total_matched} ({match_rate}%)")
    print(f"  Elapsed:    {elapsed:.1f}s")
    print(f"{'='*60}")

    return summary


def _fetch_parcels_from_supabase(county: str, url: str, key: str) -> list[dict]:
    """Fetch all parcels for a county from Supabase."""
    import httpx

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    all_parcels = []
    offset = 0
    limit = 10000

    while True:
        resp = httpx.get(
            f"{url}/rest/v1/parcels",
            headers=headers,
            params={
                "county": f"eq.{county}",
                "select": "parcel_id,account_number,latitude,longitude",
                "offset": offset,
                "limit": limit,
                "order": "parcel_id.asc",
            },
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()

        if not batch:
            break

        all_parcels.extend(batch)
        offset += limit

        if len(batch) < limit:
            break

    return all_parcels


# ===========================================================================
# AGENT 3: SupabaseWriter — Bulk upsert results
# ===========================================================================
@app.function(timeout=300)
def supabase_bulk_writer(
    results: list[dict],
    supabase_url: str,
    supabase_key: str,
    batch_size: int = 1000,
) -> int:
    """
    Bulk upsert zoning results to Supabase.
    Returns total rows written.
    """
    import httpx

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    written = 0

    for i in range(0, len(results), batch_size):
        batch = results[i:i + batch_size]

        resp = httpx.post(
            f"{supabase_url}/rest/v1/parcel_zoning",
            headers=headers,
            json=batch,
            timeout=60,
        )

        if resp.status_code in (200, 201):
            written += len(batch)
        else:
            print(f"[Writer] Batch {i//batch_size} error: {resp.status_code} {resp.text[:200]}")

    return written


# ===========================================================================
# AGENT 4: MultiCountyOrchestrator — 67 counties in parallel
# ===========================================================================
@app.function(timeout=3600)
def multi_county_orchestrator(
    counties: list[str],
    chunk_size: int = 5000,
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
) -> list[dict]:
    """
    Run zoning across multiple counties in parallel.
    Each county gets its own county_orchestrator, which internally
    parallelizes its own parcels.

    This is the top-level "67-county button."
    """
    print(f"[MultiCounty] Launching {len(counties)} county orchestrators...")

    sb_url = supabase_url or os.environ.get("SUPABASE_URL", "")
    sb_key = supabase_key or os.environ.get("SUPABASE_SERVICE_KEY", "")

    summaries = []

    for result in county_orchestrator.map(
        counties,
        [chunk_size] * len(counties),
        [20] * len(counties),
        [sb_url] * len(counties),
        [sb_key] * len(counties),
        return_exceptions=True,
    ):
        if isinstance(result, Exception):
            print(f"[MultiCounty] County failed: {result}")
            summaries.append({"status": "FAILED", "error": str(result)})
        else:
            summaries.append(result)
            print(f"[MultiCounty] {result['county']}: {result.get('match_rate_pct', 0)}% match rate")

    return summaries


# ===========================================================================
# Local entrypoint for CLI usage
# ===========================================================================
@app.local_entrypoint()
def main(
    county: str = "brevard",
    chunk_size: int = 5000,
    multi: bool = False,
):
    """
    Run from CLI:
      modal run modal_app.py --county brevard
      modal run modal_app.py --county brevard --chunk-size 10000
      modal run modal_app.py --multi  # all configured counties
    """
    if multi:
        # All counties with configured GIS endpoints
        counties = ["brevard"]  # Add more as endpoints are discovered
        results = multi_county_orchestrator.remote(counties, chunk_size)
        for r in results:
            print(json.dumps(r, indent=2))
    else:
        result = county_orchestrator.remote(county, chunk_size)
        print(json.dumps(result, indent=2))
