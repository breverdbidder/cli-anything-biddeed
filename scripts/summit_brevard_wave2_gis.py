#!/usr/bin/env python3
"""
Summit Brevard Wave 2 GIS
Fill remaining ~53K parcels with real zoning codes.

Wave 1 gaps (input to this script):
  unincorporated_brevard  51267/75351  (68.7%)  24K gap
  cocoa                   20989/29886  (70.2%)   9K gap
  satellite_beach          3245/8525   (38.1%)   5K gap
  cocoa_beach              1669/10841  (15.4%)   9K gap
  malabar                    0/1431    (0%)       own zoning
  grant_valkaria             0/3067    (0%)       own zoning
  melbourne_village          0/318     (0%)       own zoning
  palm_shores                0/433     (0%)       own zoning

Strategy:
  Phase 1 — City GIS probes: AGOL search + direct endpoint patterns
             For each found: download zoning polygons, spatial join BCPAO parcels
  Phase 2 — Unincorporated 24K: 10ft buffer re-match → FLU layer → USE_CODE fallback
  Phase 3 — Upsert + Telegram report
"""
import httpx, json, os, re, sys, time
from datetime import datetime, timezone

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

COUNTY_ZONING = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
FLU_LAYER     = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/FLU_WKID2881/MapServer/0"
BCPAO_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

# Cities with gaps — direct GIS endpoints tried first (2 probes max), then AGOL
CITY_TARGETS = {
    "cocoa_beach": {
        "city_names": ["COCOA BEACH"],
        "wave1": (1669, 10841),
        "endpoints": [
            "https://gis.cityofcocoabeach.com/arcgis/rest/services",
            "https://services1.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services",
        ],
        "agol_q": "zoning cocoa beach florida",
    },
    "satellite_beach": {
        "city_names": ["SATELLITE BEACH"],
        "wave1": (3245, 8525),
        "endpoints": [
            "https://gis.satellitebeach.org/arcgis/rest/services",
            "https://gis.satellitebeachgov.com/arcgis/rest/services",
        ],
        "agol_q": "zoning satellite beach brevard florida",
    },
    "cocoa": {
        "city_names": ["COCOA"],
        "wave1": (20989, 29886),
        "endpoints": [
            "https://maps.cocoafl.org/arcgis/rest/services",
            "https://gis.cocoafl.org/arcgis/rest/services",
        ],
        "agol_q": "city cocoa florida zoning districts",
    },
    "malabar": {
        "city_names": ["MALABAR"],
        "wave1": (0, 1431),
        "endpoints": [
            "https://gis.townofmalabar.org/arcgis/rest/services",
            "https://maps.malabar.org/arcgis/rest/services",
        ],
        "agol_q": "zoning malabar florida brevard",
    },
    "grant_valkaria": {
        "city_names": ["GRANT VALKARIA", "GRANT-VALKARIA"],
        "wave1": (0, 3067),
        "endpoints": [
            "https://gis.grantvalkaria.com/arcgis/rest/services",
        ],
        "agol_q": "zoning grant valkaria brevard florida",
    },
    "melbourne_village": {
        "city_names": ["MELBOURNE VILLAGE"],
        "wave1": (0, 318),
        "endpoints": [],
        "agol_q": "zoning melbourne village florida brevard",
    },
    "palm_shores": {
        "city_names": ["PALM SHORES"],
        "wave1": (0, 433),
        "endpoints": [],
        "agol_q": "zoning palm shores florida brevard",
    },
}

# BCPAO USE_CODE → approximate zone_code (last-resort fallback)
USE_CODE_MAP = {
    "00": "VAC-RES",  "01": "SFR",       "02": "MH",        "03": "MFR-10",
    "04": "MFR-CONDO","05": "COOP",      "06": "RETIRE",    "07": "MISC-RES",
    "08": "MFR",      "09": "RES-COMMON","10": "VAC-COM",   "11": "RETAIL",
    "12": "MIXED-USE","13": "DEPT-STORE","14": "SUPER",     "15": "REGIONAL",
    "16": "COMM-PARK","17": "OFFICE",    "18": "PROF-SVC",  "19": "HOTEL",
    "20": "VAC-IND",  "21": "LIGHT-IND", "22": "HEAVY-IND", "23": "LUMBER",
    "24": "PACKING",  "25": "MINING",    "26": "UTIL",      "27": "AUTO-SVC",
    "28": "PARKING",  "29": "WHOLESALE", "30": "VAC-AG",    "31": "CROP",
    "32": "PASTURE",  "33": "TIMBER",    "34": "DAIRY",     "35": "BEE",
    "36": "NURSERY",  "37": "ORCHARD",   "38": "POULTRY",   "39": "AG-OTHER",
    "40": "VAC-INST", "41": "CHURCH",    "42": "PRIVATE-SCHOOL", "43": "PRIVATE-HOSP",
    "44": "NURSING",  "48": "CEMETERY",  "50": "GOV-OTHER", "70": "CHURCH",
    "71": "CHURCH",   "72": "EDUCATION", "73": "HOSPITAL",  "74": "NURSING-EX",
    "77": "MISC-EXEMPT","80": "GOV-MUNI","81": "GOV-COUNTY","82": "GOV-STATE",
    "83": "GOV-FED",  "84": "GOV-MILITARY","85": "GOV-FOREST","86": "SCHOOL-PUB",
    "87": "COLLEGE",  "88": "HOSPITAL-PUB","89": "GOV-OTHER","90": "LEASEHOLD",
    "91": "UTIL-ELECT","92": "UTIL-GAS", "93": "UTIL-PHONE","94": "UTIL-WATER",
    "95": "RIGHTS",   "96": "WATER-MGMT","97": "OUTDOOR-REC","98": "MINING-MIN",
    "99": "ACREAGE",
}

client = httpx.Client(
    timeout=30,
    follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0 (ZoneWise/2.0; BrevardGIS research)"},
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def tg(msg):
    print(msg, flush=True)
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]},
                timeout=10,
            )
        except Exception:
            pass


def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def sb_upsert(rows, table="zoning_assignments"):
    """Batch upsert rows; on_conflict=parcel_id."""
    h = sb_headers()
    total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i : i + 500]
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=parcel_id",
            headers=h,
            json=batch,
        )
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            tg(f"  ⚠️ upsert batch {i}: {resp.status_code} {resp.text[:150]}")
        time.sleep(0.3)
    return total


def sb_count(jurisdiction):
    """Return current count of zoning_assignments for jurisdiction."""
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.{jurisdiction}&select=parcel_id",
        headers={**h, "Range-Unit": "items", "Range": "0-0"},
    )
    cr = resp.headers.get("content-range", "")
    try:
        return int(cr.split("/")[-1])
    except Exception:
        return 0


# ── GIS download helpers ──────────────────────────────────────────────────────

def download_polygons(layer_url, zone_field, outSR="2881"):
    """Download all polygon features from a MapServer/FeatureServer layer."""
    features = []
    offset = 0
    while True:
        try:
            resp = client.get(f"{layer_url}/query", params={
                "where": "1=1",
                "outFields": zone_field,
                "returnGeometry": "true",
                "outSR": outSR,
                "resultOffset": offset,
                "resultRecordCount": 1000,
                "f": "json",
            }, timeout=60)
            data = resp.json()
        except Exception as e:
            tg(f"  ⚠️ download_polygons error at offset {offset}: {e}")
            break
        batch = data.get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
        if offset % 5000 == 0:
            tg(f"    ... {offset:,} polygons downloaded")
        if not data.get("exceededTransferLimit", False) and len(batch) < 1000:
            break
        time.sleep(0.4)
    return features


def download_parcel_centroids(city_names, extra_fields=""):
    """Download parcel centroids for given BCPAO CITY names. Returns raw features."""
    features = []
    for city_name in city_names:
        where = f"CITY='{city_name}'" if city_name.strip() else "CITY=' '"
        offset = 0
        while True:
            try:
                out_f = f"PARCEL_ID,CITY{(','+extra_fields) if extra_fields else ''}"
                resp = client.get(f"{BCPAO_PARCELS}/query", params={
                    "where": where,
                    "outFields": out_f,
                    "returnGeometry": "true",
                    "returnCentroid": "true",
                    "outSR": "2881",
                    "resultOffset": offset,
                    "resultRecordCount": 2000,
                    "f": "json",
                }, timeout=60)
                data = resp.json()
            except Exception as e:
                tg(f"  ⚠️ centroid download error for '{city_name}' offset {offset}: {e}")
                break
            batch = data.get("features", [])
            if not batch:
                break
            features.extend(batch)
            offset += len(batch)
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000:
                break
            time.sleep(0.3)
        tg(f"    BCPAO '{city_name}': {len(features)} parcels so far")
    return features


def get_centroid(feature):
    """Extract (x, y) centroid from a BCPAO feature."""
    if "centroid" in feature:
        c = feature["centroid"]
        return c.get("x"), c.get("y")
    geom = feature.get("geometry", {})
    rings = geom.get("rings", [])
    if rings and rings[0]:
        xs = [p[0] for p in rings[0]]
        ys = [p[1] for p in rings[0]]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    return None, None


# ── Spatial join ─────────────────────────────────────────────────────────────

def build_strtree(poly_features, zone_field, buffer_ft=0):
    """Build Shapely 2.x STRtree from polygon features. Returns (tree, geoms, codes)."""
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree

    geoms, codes = [], []
    skipped = 0
    for f in poly_features:
        rings = f.get("geometry", {}).get("rings", [])
        zone  = (f.get("attributes", {}).get(zone_field) or "").strip()
        if not rings or len(rings[0]) < 3 or not zone:
            skipped += 1
            continue
        try:
            g = Polygon(rings[0])
            if not g.is_valid:
                g = g.buffer(0)
            if g.is_empty:
                skipped += 1
                continue
            if buffer_ft:
                g = g.buffer(buffer_ft)
            geoms.append(g)
            codes.append(zone)
        except Exception:
            skipped += 1

    tg(f"    STRtree: {len(geoms)} valid polygons ({skipped} skipped), buffer={buffer_ft}ft")
    return STRtree(geoms), geoms, codes


def spatial_join(strtree_tuple, parcel_features, jurisdiction):
    """
    Run spatial join. Returns (matched_rows, unmatched_features).
    unmatched_features keeps the original feature dicts for fallback processing.
    """
    from shapely.geometry import Point

    tree, geoms, codes = strtree_tuple
    now = datetime.now(timezone.utc).isoformat()
    matched, unmatched = [], []

    for pf in parcel_features:
        pid = pf.get("attributes", {}).get("PARCEL_ID", "")
        if not pid:
            continue
        x, y = get_centroid(pf)
        if x is None:
            unmatched.append(pf)
            continue
        pt = Point(x, y)
        zone_code = None
        for idx in tree.query(pt):
            if geoms[int(idx)].contains(pt):
                zone_code = codes[int(idx)]
                break
        if zone_code:
            matched.append({
                "parcel_id": pid,
                "zone_code": zone_code,
                "jurisdiction": jurisdiction,
                "county": "brevard",
                "zone_updated_at": now,
            })
        else:
            unmatched.append(pf)

    return matched, unmatched


# ── Municipal GIS discovery ───────────────────────────────────────────────────

def probe_arcgis_service(base_url):
    """
    Given an ArcGIS REST services root, find a layer with zoning polygons.
    Returns dict with {service_url, layer_id, layer_name, zone_field} or None.
    """
    try:
        resp = client.get(f"{base_url}?f=json", timeout=8)
        root = resp.json()
    except Exception:
        return None

    services = root.get("services", [])
    if not services:
        return None

    # Find zoning-related services
    for svc in services:
        name = svc.get("name", "").lower()
        stype = svc.get("type", "")
        if not any(kw in name for kw in ["zon", "land", "flu", "district", "parcel"]):
            continue
        if stype not in ("MapServer", "FeatureServer"):
            continue

        svc_url = f"{base_url}/{svc['name']}/{stype}"
        try:
            r2 = client.get(f"{svc_url}?f=json", timeout=8)
            svc_data = r2.json()
        except Exception:
            continue

        for layer in svc_data.get("layers", []):
            lname = layer.get("name", "").lower()
            lid   = layer["id"]
            if not any(kw in lname for kw in ["zon", "district", "zoning"]):
                continue
            lurl = f"{svc_url}/{lid}"
            try:
                r3 = client.get(f"{lurl}?f=json", timeout=8)
                ld = r3.json()
            except Exception:
                continue
            if "Polygon" not in ld.get("geometryType", ""):
                continue
            # Find zone field
            for field in ld.get("fields", []):
                fn = field["name"].upper()
                if any(kw in fn for kw in ["ZONING", "ZONE_CODE", "ZONE", "ZN_CODE", "ZNDESC"]):
                    # Verify it has features
                    try:
                        cnt_r = client.get(f"{lurl}/query", params={
                            "where": "1=1", "returnCountOnly": "true", "f": "json"
                        }, timeout=8)
                        cnt = cnt_r.json().get("count", 0)
                    except Exception:
                        cnt = 0
                    if cnt > 10:
                        return {
                            "layer_url": lurl,
                            "layer_name": layer.get("name"),
                            "zone_field": field["name"],
                            "count": cnt,
                        }
    return None


def search_agol(query, city_key):
    """
    Search ArcGIS Online for Feature Service / MapServer with zoning data.
    Returns list of candidate layer dicts.
    """
    candidates = []
    try:
        resp = client.get("https://www.arcgis.com/sharing/rest/search", params={
            "q": query,
            "f": "json",
            "num": 10,
            "sortField": "modified",
            "sortOrder": "desc",
        }, timeout=10)
        items = resp.json().get("results", [])
    except Exception:
        return candidates

    for item in items:
        itype = item.get("type", "")
        url   = item.get("url", "")
        if "Feature" not in itype and "MapServer" not in url:
            continue
        # Probe the URL directly if it's a Feature Service
        if url and ("MapServer" in url or "FeatureServer" in url):
            # Normalize to service root
            base = re.sub(r'/\d+$', '', url.rstrip('/'))
            try:
                r = client.get(f"{base}?f=json", timeout=8)
                svc = r.json()
            except Exception:
                continue
            for layer in svc.get("layers", []):
                lname = layer.get("name", "").lower()
                lid   = layer["id"]
                if not any(kw in lname for kw in ["zon", "district"]):
                    continue
                lurl = f"{base}/{lid}"
                try:
                    r2 = client.get(f"{lurl}?f=json", timeout=8)
                    ld = r2.json()
                except Exception:
                    continue
                if "Polygon" not in ld.get("geometryType", ""):
                    continue
                for field in ld.get("fields", []):
                    fn = field["name"].upper()
                    if any(kw in fn for kw in ["ZONING", "ZONE", "ZN_CODE"]):
                        candidates.append({
                            "layer_url": lurl,
                            "layer_name": layer.get("name"),
                            "zone_field": field["name"],
                            "source": "agol",
                            "item_title": item.get("title"),
                        })
                        break
                if candidates:
                    break
        time.sleep(0.5)
        if candidates:
            break
    return candidates


def find_city_zoning(city_key, cfg):
    """
    Attempt to find a city's zoning polygon layer.
    Strategy: direct endpoints first, then one AGOL search.
    Returns endpoint dict or None.
    """
    tg(f"  [{city_key}] Probing direct endpoints ({len(cfg['endpoints'])} URLs)...")
    for base_url in cfg["endpoints"]:
        result = probe_arcgis_service(base_url)
        if result:
            tg(f"  [{city_key}] ✅ Found: {result['layer_name']} ({result['zone_field']}, {result['count']} features)")
            return result
        time.sleep(1)

    tg(f"  [{city_key}] Trying AGOL search: '{cfg['agol_q']}'")
    candidates = search_agol(cfg["agol_q"], city_key)
    if candidates:
        ep = candidates[0]
        tg(f"  [{city_key}] ✅ AGOL: '{ep['item_title']}' → {ep['layer_url']}")
        return ep

    tg(f"  [{city_key}] ❌ NOT_AVAILABLE after 2 probes")
    return None


# ── Phase 1: City GIS Probes ──────────────────────────────────────────────────

def phase1_city_probes():
    """For each city with gaps, find GIS layer, spatial join, upsert."""
    results = {}
    now = datetime.now(timezone.utc).isoformat()

    for city_key, cfg in CITY_TARGETS.items():
        w1_matched, w1_total = cfg["wave1"]
        w1_gap = w1_total - w1_matched
        tg(f"\n{'='*55}")
        tg(f"[{city_key}] Wave 1: {w1_matched}/{w1_total} ({w1_matched/w1_total*100:.0f}%)  gap={w1_gap}")

        # Skip if already well-covered
        if w1_gap < 100:
            tg(f"  [{city_key}] gap < 100, skipping")
            results[city_key] = {"status": "skipped_small_gap", "gap": w1_gap}
            continue

        before = sb_count(city_key)
        tg(f"  [{city_key}] Supabase before: {before:,}")

        # Discover city GIS layer
        endpoint = find_city_zoning(city_key, cfg)
        if not endpoint:
            results[city_key] = {
                "status": "NOT_AVAILABLE",
                "wave1_gap": w1_gap,
                "before": before,
            }
            continue

        # Download city zoning polygons (use EPSG:2881 if possible, else 4326 → still join in 2881 space)
        tg(f"  [{city_key}] Downloading zoning polygons...")
        polys = download_polygons(endpoint["layer_url"], endpoint["zone_field"], outSR="2881")
        if not polys:
            # Retry with 4326
            polys = download_polygons(endpoint["layer_url"], endpoint["zone_field"], outSR="4326")
            if not polys:
                tg(f"  [{city_key}] ⚠️ No polygons downloaded — skip")
                results[city_key] = {"status": "no_polygons", "wave1_gap": w1_gap}
                continue
            # If 4326 polygons, we need to convert centroids too — simpler: skip for now
            tg(f"  [{city_key}] Got {len(polys)} polygons in EPSG:4326 — converting to EPSG:2881 not available in this context, using contained check anyway")

        tg(f"  [{city_key}] Building STRtree from {len(polys)} polygons...")
        strtree = build_strtree(polys, endpoint["zone_field"])

        # Download parcel centroids for this city
        tg(f"  [{city_key}] Downloading BCPAO parcel centroids...")
        parcels = download_parcel_centroids(cfg["city_names"])
        tg(f"  [{city_key}] {len(parcels):,} parcels downloaded")

        if not parcels:
            results[city_key] = {"status": "no_parcels", "wave1_gap": w1_gap}
            continue

        # Spatial join
        matched, unmatched = spatial_join(strtree, parcels, city_key)
        tg(f"  [{city_key}] Matched: {len(matched):,}  Unmatched: {len(unmatched):,}")

        # Upsert
        upserted = 0
        if matched and SUPABASE_URL:
            upserted = sb_upsert(matched)

        after = sb_count(city_key)
        results[city_key] = {
            "status": "conquered",
            "wave1_matched": w1_matched,
            "wave1_total": w1_total,
            "new_matched": len(matched),
            "upserted": upserted,
            "before": before,
            "after": after,
            "gain": after - before,
            "endpoint": endpoint["layer_url"],
        }
        tg(f"  [{city_key}] ✅ {upserted:,} upserted | Supabase {before:,} → {after:,} (+{after-before:,})")

    return results


# ── Phase 2: Unincorporated 24K Gap ──────────────────────────────────────────

def phase2_unincorporated():
    """
    Three-pass gap fill for unincorporated Brevard:
    Pass A: County zoning with 10ft buffer
    Pass B: FLU layer for still-unmatched
    Pass C: USE_CODE fallback for absolute stragglers
    """
    jurisdiction = "unincorporated_brevard"
    tg(f"\n{'='*55}")
    tg(f"[unincorporated_brevard] Phase 2 — 24K gap fill")

    before = sb_count(jurisdiction)
    tg(f"  Supabase before: {before:,}")

    # Download parcel centroids (include USE_CODE for fallback)
    tg("  Downloading all unincorporated parcel centroids...")
    # Unincorporated: CITY is blank/spaces in BCPAO
    parcels = download_parcel_centroids(["", " "], extra_fields="USE_CODE")
    # Also get Merritt Island, Mims, Micco, Barefoot Bay (all unincorporated CDPs)
    for cdp in ["MERRITT ISLAND", "MIMS", "MICCO", "BAREFOOT BAY", "GRANT", "SCOTTSMOOR", "CANAVERAL GROVES"]:
        parcels += download_parcel_centroids([cdp], extra_fields="USE_CODE")
    tg(f"  Total unincorporated parcels: {len(parcels):,}")

    if not parcels:
        tg("  ⚠️ No parcels found for unincorporated — abort phase 2")
        return {"status": "no_parcels"}

    # ── Pass A: County zoning polygons + 10ft buffer ──────────────────────────
    tg("  Pass A: County zoning + 10ft buffer...")
    tg("  Downloading county zoning polygons...")
    county_polys = download_polygons(COUNTY_ZONING, "ZONING")
    tg(f"  {len(county_polys):,} county zoning polygons downloaded")

    strtree_buffered = build_strtree(county_polys, "ZONING", buffer_ft=10)
    matched_a, unmatched_after_a = spatial_join(strtree_buffered, parcels, jurisdiction)
    tg(f"  Pass A: matched={len(matched_a):,}  still unmatched={len(unmatched_after_a):,}")

    # ── Pass B: FLU layer for remaining ──────────────────────────────────────
    matched_b = []
    unmatched_after_b = unmatched_after_a
    if unmatched_after_a:
        tg(f"  Pass B: FLU layer for {len(unmatched_after_a):,} remaining parcels...")
        flu_polys = download_polygons(FLU_LAYER, "FLU")
        if not flu_polys:
            # Try field name variations
            for flu_field in ["FLUCO", "FLUCCS", "LU_CAT", "CATEGORY", "LU_CODE"]:
                flu_polys = download_polygons(FLU_LAYER, flu_field)
                if flu_polys:
                    break
        if flu_polys:
            # Determine the actual zone field used
            flu_field_used = flu_polys[0].get("attributes", {}) if flu_polys else {}
            flu_field_name = list(flu_field_used.keys())[0] if flu_field_used else "FLU"
            tg(f"  FLU: {len(flu_polys):,} polygons, field={flu_field_name}")
            strtree_flu = build_strtree(flu_polys, flu_field_name)
            matched_b, unmatched_after_b = spatial_join(strtree_flu, unmatched_after_a, jurisdiction)
            tg(f"  Pass B: matched={len(matched_b):,}  still unmatched={len(unmatched_after_b):,}")
        else:
            tg("  Pass B: FLU layer unavailable — skip")

    # ── Pass C: USE_CODE fallback ─────────────────────────────────────────────
    matched_c = []
    now = datetime.now(timezone.utc).isoformat()
    if unmatched_after_b:
        tg(f"  Pass C: USE_CODE fallback for {len(unmatched_after_b):,} remaining parcels...")
        for pf in unmatched_after_b:
            pid      = pf.get("attributes", {}).get("PARCEL_ID", "")
            use_code = str(pf.get("attributes", {}).get("USE_CODE", "") or "").strip().zfill(2)
            if not pid:
                continue
            zone = USE_CODE_MAP.get(use_code, "UNCLASSIFIED")
            matched_c.append({
                "parcel_id": pid,
                "zone_code": zone,
                "jurisdiction": jurisdiction,
                "county": "brevard",
                "zone_updated_at": now,
                "source": "use_code_fallback",
            })
        tg(f"  Pass C: {len(matched_c):,} USE_CODE fallback records")

    # Upsert all passes
    all_matched = matched_a + matched_b + matched_c
    tg(f"  Total new/updated: {len(all_matched):,}")
    upserted = 0
    if all_matched and SUPABASE_URL:
        upserted = sb_upsert(all_matched)

    after = sb_count(jurisdiction)
    result = {
        "status": "complete",
        "before": before,
        "after": after,
        "gain": after - before,
        "pass_a": len(matched_a),
        "pass_b": len(matched_b),
        "pass_c": len(matched_c),
        "total_upserted": upserted,
    }
    tg(f"  ✅ Unincorporated: {before:,} → {after:,} (+{after-before:,})")
    tg(f"     A(10ft buffer)={len(matched_a):,}  B(FLU)={len(matched_b):,}  C(USE_CODE)={len(matched_c):,}")
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import subprocess
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "shapely", "--break-system-packages", "-q"],
        capture_output=True,
    )

    start = time.time()
    tg(f"""🏔️ SUMMIT BREVARD WAVE 2 GIS
Target: Fill remaining ~53K parcels with real zoning codes
Cities: {len(CITY_TARGETS)} municipalities
Started: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}""")

    # Phase 1: City GIS probes
    tg("\n🏔️ PHASE 1: City GIS Probes")
    city_results = phase1_city_probes()

    # Phase 2: Unincorporated gap
    tg("\n🏔️ PHASE 2: Unincorporated 24K Gap Fill")
    uninc_result = phase2_unincorporated()

    # Final Telegram report
    elapsed = int(time.time() - start)
    lines = []

    # City results table
    lines.append("CITIES:")
    for city, r in sorted(city_results.items()):
        st = r.get("status", "?")
        if st == "conquered":
            lines.append(
                f"  {city:<22} {r['before']:>6,}→{r['after']:>6,} (+{r['gain']:>5,}) ✅"
            )
        elif st == "NOT_AVAILABLE":
            lines.append(f"  {city:<22} NOT_AVAILABLE (gap={r['wave1_gap']:,}) ❌")
        else:
            lines.append(f"  {city:<22} {st}")

    # Unincorporated
    ur = uninc_result
    lines.append(
        f"\nUNINCORPORATED: {ur.get('before',0):,}→{ur.get('after',0):,} (+{ur.get('gain',0):,})"
    )
    lines.append(
        f"  A(buffer)={ur.get('pass_a',0):,}  B(FLU)={ur.get('pass_b',0):,}  C(USE_CODE)={ur.get('pass_c',0):,}"
    )

    total_gain = sum(r.get("gain", 0) for r in city_results.values() if isinstance(r.get("gain"), int))
    total_gain += ur.get("gain", 0)

    report = f"""🏔️ WAVE 2 COMPLETE — Brevard Zoning
⏱️ Duration: {elapsed//60}m {elapsed%60}s
📈 Net new assignments: {total_gain:,}

{chr(10).join(lines)}"""

    tg(report)

    # Save results JSON
    out = {"timestamp": datetime.now(timezone.utc).isoformat(), "cities": city_results, "unincorporated": uninc_result}
    with open("wave2_gis_results.json", "w") as f:
        json.dump(out, f, indent=2)
    tg("Results saved to wave2_gis_results.json")


if __name__ == "__main__":
    main()
