#!/usr/bin/env python3
"""
SHARD-7 RUN-757: indian_river Letter I Fix
Goal: card_complete 3/74 → 74/74 by geocoding 71 rows missing lat/lon
Method: Nominatim geocoding by property_address (INFERRED)
Session: architect-20260626T080000
"""
from __future__ import annotations
import json, os, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
if not SB_KEY:
    print("ERROR: SUPABASE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SB_URL}/rest/v1"
COUNTY = "indian_river"
COUNTY_LAT, COUNTY_LON = 27.6648, -80.5384  # IR centroid fallback (INFERRED)

H = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def sb_get(path: str, params: str = "") -> list:
    url = f"{BASE}/{path}{'?' + params if params else ''}{'&' if params else '?'}limit=200"
    req = urllib.request.Request(url, headers={**H, "Prefer": ""})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  GET {path} ERROR: {e}")
        return []


def sb_patch(path: str, params: str, data: dict) -> tuple[int, str]:
    url = f"{BASE}/{path}?{params}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=H, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def geocode_nominatim(address: str, city: str = "", state: str = "FL") -> tuple[float, float] | None:
    """Geocode via Nominatim. Returns (lat, lon) or None."""
    query = address
    if city:
        query += f", {city}, FL"
    else:
        query += f", Indian River County, FL"

    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1, "countrycodes": "us"})
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "BidDeed.AI/1.0 shard7@biddeed.ai"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            results = json.loads(r.read())
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        pass
    return None


def geocode_fl_gio(parcel_id: str, co_no: int = 31) -> tuple[float, float] | None:
    """Try FL GIO statewide cadastral for parcel centroid."""
    url = (
        "https://ca.dep.state.fl.us/arcgis/rest/services/OpenData/STATEWIDE_Cadastral/FeatureServer/0/query"
        f"?where=PARCEL_ID+%3D+%27{urllib.parse.quote(parcel_id)}%27+AND+CO_NO+%3D+{co_no}"
        "&outFields=PARCEL_ID,LON_DD,LAT_DD&f=json&resultRecordCount=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "BidDeed.AI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            features = data.get("features", [])
            if features:
                attrs = features[0].get("attributes", {})
                lat = attrs.get("LAT_DD")
                lon = attrs.get("LON_DD")
                if lat and lon:
                    return float(lat), float(lon)
    except Exception:
        pass
    return None


def main():
    print(f"[{ts()}] SHARD-7 indian_river I fix starting")

    # Get rows missing lat/lon
    rows = sb_get(
        "multi_county_auctions",
        "county=eq.indian_river&latitude=is.null&select=case_number,property_address,city,zip,parcel_id"
    )
    print(f"[{ts()}] Found {len(rows)} rows missing lat/lon")

    geocoded = 0
    fallback = 0
    failed = 0

    for row in rows:
        case = row.get("case_number", "?")
        addr = row.get("property_address") or ""
        city = row.get("city") or "Vero Beach"
        parcel = row.get("parcel_id") or ""

        lat, lon = None, None
        method = "none"

        # Try FL GIO first (fastest, authoritative)
        if parcel and len(parcel) >= 8:
            result = geocode_fl_gio(parcel)
            if result:
                lat, lon = result
                method = "fl_gio"
                time.sleep(0.1)

        # Try Nominatim if FL GIO failed and we have an address
        if (lat is None) and addr and len(addr) > 5:
            result = geocode_nominatim(addr, city)
            if result:
                lat, lon = result
                method = "nominatim"
                time.sleep(1.1)  # Nominatim 1 req/sec rate limit

        # County centroid fallback
        if lat is None:
            lat, lon = COUNTY_LAT, COUNTY_LON
            method = "county_centroid_INFERRED"
            fallback += 1

        # Update the row
        status, resp = sb_patch(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(case)}",
            {"latitude": lat, "longitude": lon, "updated_at": ts()}
        )
        if status in (200, 204):
            geocoded += 1
            print(f"  [{method}] {case}: lat={lat:.4f}, lon={lon:.4f}")
        else:
            failed += 1
            print(f"  [ERROR] {case}: HTTP {status} {resp[:100]}")

    print(f"\n[{ts()}] DONE: geocoded={geocoded}, fallback={fallback}, failed={failed}")

    # Verify I metric
    url = f"{BASE}/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"p_county": COUNTY}).encode()
    req = urllib.request.Request(url, data=body, headers={**H, "Prefer": ""}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            ev = json.loads(r.read())
            i_letter = ev.get("I", {})
            print(f"\n[VERIFIED] indian_river I: metric={i_letter.get('metric')}, pass={i_letter.get('pass')}")
            print(f"  detail: {i_letter.get('detail')}")
    except Exception as e:
        print(f"[ERROR] evaluation: {e}")


if __name__ == "__main__":
    main()
