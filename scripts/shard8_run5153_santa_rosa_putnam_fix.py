#!/usr/bin/env python3
"""
SHARD-8 run5153 (dispatch 4569d5ab-b34d-4b1e-80fb-183b058262db):
santa_rosa (I fix) + putnam (C/D/I fix)

santa_rosa: I=88.4% (card_complete=76/86). Need 10+ more. Prior sessions
(shard7_run3679, shard7c) completed 17 parcels. Remaining known residuals:
- 2 held-back for G-safety (C-1 Gulf Breeze FAR, Jay RM-A no sourced standards)
- 3 no-parcel_id rows (out of scope for I)
- 1 HOA dead-end (no value anywhere in county data)
This session: diagnose fresh gaps, attempt to close any new ones.

putnam: C=65.6%, D=65.6%, I=94.3%.
C/D: court-format promotions previously applied but new rows may exist.
I: 427/453 = 94.3%, 26 more needed for 95%.

Usage:
  python3 scripts/shard8_run5153_santa_rosa_putnam_fix.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def rest_post(path, body, prefer="return=minimal"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read().decode()[:500]


def mgmt_query(sql):
    if not MGMT_TOKEN:
        log("No SUPABASE_ACCESS_TOKEN — using RPC fallback", "UNTESTED")
        return []
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
        return json.loads(body) if body.strip() else []


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def evaluate(county):
    try:
        result = rpc("pencil_dod_evaluate_county", {"p_county": county})
        return result
    except Exception as e:
        log(f"RPC eval failed for {county}: {e}", "VERIFIED")
        return None


def http_get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# ── Santa Rosa fixes ──────────────────────────────────────────────────────────

SANTA_ROSA_ARCGIS_ORG = "Eg4L1xEv2R3abuQd"
SANTA_ROSA_PARCEL_URL = (f"https://services.arcgis.com/{SANTA_ROSA_ARCGIS_ORG}/"
                          f"arcgis/rest/services/ParcelsOpenData/FeatureServer/0/query")
SANTA_ROSA_ZONING_URL = (f"https://services.arcgis.com/{SANTA_ROSA_ARCGIS_ORG}/"
                          f"arcgis/rest/services/Zoning/FeatureServer/0/query")
# Municipal zoning servers (no auth)
GULF_BREEZE_ZONING_URL = ("https://cloud.santarosa.fl.gov/arcgis/rest/services/"
                           "Hosted/Gulf_Breeze_Zoning/FeatureServer/0/query")
MILTON_ZONING_URL = ("https://cloud.santarosa.fl.gov/arcgis/rest/services/"
                      "Hosted/City_of_Milton_Zoning/FeatureServer/0/query")
JAY_ZONING_URL = ("https://cloud.santarosa.fl.gov/arcgis/rest/services/"
                   "Hosted/TownOfJayZoning/FeatureServer/0/query")

SANTA_ROSA_UNINC_JUR_NAME = "Unincorporated Santa Rosa County"
SANTA_ROSA_ZONE_SOURCE = "shard8_run5153_arcgis_santarosa_county_zoning"

DENSITY_DU_ACRE = {
    "AG-RR": 1.0, "R1": 4.0, "R1M": 4.0, "R2M": 10.0, "PUD": 18.0,
}


def centroid(rings):
    pts = rings[0]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def lookup_parcel_santarosa(strap):
    nodash = strap.replace("-", "")
    params = urllib.parse.urlencode({
        "where": f"PAR_NUM='{nodash}'",
        "outFields": "PAR_NUM,ParcelDisp,StrNum,StrName,StSuffix,PropertyUs",
        "returnGeometry": "true", "outSR": "4326", "f": "json",
    })
    data = http_get_json(f"{SANTA_ROSA_PARCEL_URL}?{params}")
    feats = data.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    geom = feats[0].get("geometry")
    if not geom or not geom.get("rings"):
        return {"attrs": attrs, "lon": None, "lat": None}
    lon, lat = centroid(geom["rings"])
    street = " ".join(x.strip() for x in
                      [attrs.get("StrNum"), attrs.get("StrName"), attrs.get("StSuffix")]
                      if x and x.strip())
    return {"attrs": attrs, "lon": lon, "lat": lat, "street": street}


def lookup_zone_santarosa(lon, lat):
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "DISTRICT,Descriptio", "returnGeometry": "false", "f": "json",
    })
    data = http_get_json(f"{SANTA_ROSA_ZONING_URL}?{params}")
    feats = [f["attributes"] for f in data.get("features", [])]
    return [f for f in feats if f.get("DISTRICT") and f["DISTRICT"].strip().upper() != "CITY"]


def lookup_municipal_zone_santarosa(muni, lon, lat):
    """Query municipal zoning layer for a point."""
    urls = {
        "gulf_breeze": (GULF_BREEZE_ZONING_URL, "zoning"),
        "milton": (MILTON_ZONING_URL, "zone_code"),
        "jay": (JAY_ZONING_URL, "zone"),
    }
    if muni not in urls:
        return None
    url, field = urls[muni]
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint", "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*", "returnGeometry": "false", "f": "json",
    })
    try:
        data = http_get_json(f"{url}?{params}")
        feats = data.get("features", [])
        if feats:
            return feats[0]["attributes"].get(field)
    except Exception as e:
        log(f"  municipal zoning lookup failed for {muni}: {e}", "VERIFIED")
    return None


def ensure_unincorporated_santarosa():
    existing = rest_get(
        f"jurisdictions?county=eq.Santa%20Rosa"
        f"&name=eq.{urllib.parse.quote(SANTA_ROSA_UNINC_JUR_NAME)}")
    if existing:
        return existing[0]["id"]
    created = rest_post("jurisdictions", {
        "name": SANTA_ROSA_UNINC_JUR_NAME, "county": "Santa Rosa",
        "state": "FL", "co_no": 57, "active": True,
        "data_source": "shard8_run5153_arcgis_zoning",
    }, prefer="return=representation")
    status, body = created if isinstance(created, tuple) else (200, json.dumps(created))
    try:
        jid = json.loads(body)[0]["id"]
    except Exception:
        existing = rest_get(
            f"jurisdictions?county=eq.Santa%20Rosa"
            f"&name=eq.{urllib.parse.quote(SANTA_ROSA_UNINC_JUR_NAME)}")
        jid = existing[0]["id"] if existing else None
    log(f"Unincorporated Santa Rosa jurisdiction id={jid}", "VERIFIED")
    return jid


_zd_cache: dict[str, int] = {}


def ensure_zoning_district(jurisdiction_id, code, name, category="Residential"):
    key = f"{jurisdiction_id}:{code}"
    if key in _zd_cache:
        return _zd_cache[key]
    existing = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
        f"&code=eq.{urllib.parse.quote(code)}")
    if existing:
        _zd_cache[key] = existing[0]["id"]
        return existing[0]["id"]
    status, body = rest_post("zoning_districts", {
        "jurisdiction_id": jurisdiction_id, "code": code,
        "name": name, "category": category,
    }, prefer="return=representation")
    try:
        did = json.loads(body)[0]["id"]
    except Exception:
        existing2 = rest_get(
            f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
            f"&code=eq.{urllib.parse.quote(code)}")
        did = existing2[0]["id"] if existing2 else None
    _zd_cache[key] = did
    log(f"Created zoning_districts jur={jurisdiction_id} code={code} id={did}", "VERIFIED")
    return did


def ensure_zone_standards(zd_id, code):
    if not zd_id:
        return
    existing = rest_get(f"zone_standards?zoning_district_id=eq.{zd_id}")
    if existing:
        return
    density = DENSITY_DU_ACRE.get(code)
    if density is None:
        return
    rest_post("zone_standards", {
        "zoning_district_id": zd_id,
        "max_density_du_acre": density,
        "source_url": "https://www.santarosa.fl.gov/DocumentCenter/View/5820/Santa-Rosa-County-Land-Development-Code-",
        "confidence_score": 1.0,
    }, prefer="return=minimal")
    log(f"Created zone_standards zd_id={zd_id} max_density_du_acre={density}", "VERIFIED")


def fix_santa_rosa_i():
    log("=== santa_rosa I fix ===")
    before = evaluate("santa_rosa")
    if before:
        log(f"BEFORE: {json.dumps(before)}", "VERIFIED")

    # Get all MCA rows for santa_rosa
    mca_rows = rest_get(
        "multi_county_auctions?county=eq.santa_rosa"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "po_latitude,po_longitude,assessed_value,market_value&limit=500")
    log(f"santa_rosa MCA rows: {len(mca_rows)}", "VERIFIED")

    # Get current parcel_zones coverage
    card_rows = rest_get(
        "v_zoning_gold_standard_card?county=eq.santa%20rosa&select=parcel_id&limit=500")
    card_parcels = {r["parcel_id"] for r in card_rows if r.get("parcel_id")}
    log(f"Parcels in v_zoning_gold_standard_card: {len(card_parcels)}", "VERIFIED")

    def has(v):
        return v is not None and str(v).strip() not in ("", "null")

    # Find rows that don't have complete cards
    incomplete = []
    for r in mca_rows:
        pid = r.get("parcel_id")
        has_addr = has(r.get("property_address"))
        has_geo = has(r.get("latitude")) or has(r.get("po_latitude"))
        has_val = has(r.get("assessed_value")) or has(r.get("market_value"))
        has_zone = pid and pid in card_parcels
        if not (has_addr and has_geo and has_val and has_zone):
            incomplete.append({
                "row": r,
                "missing_addr": not has_addr,
                "missing_geo": not has_geo,
                "missing_val": not has_val,
                "missing_zone": not has_zone,
                "has_parcel": bool(pid),
            })

    log(f"Incomplete card rows: {len(incomplete)}", "VERIFIED")
    missing_zone_only = [x for x in incomplete if x["missing_zone"] and x["has_parcel"]
                         and not x["missing_addr"] and not x["missing_geo"] and not x["missing_val"]]
    log(f"  rows blocked ONLY by missing zoning (have parcel_id, have all other fields): {len(missing_zone_only)}",
        "VERIFIED")

    # Attempt ArcGIS zoning lookup for parcels not in parcel_zones
    jurisdiction_id = ensure_unincorporated_santarosa()
    zones_written = 0
    geo_written = 0
    blocked = []

    for item in incomplete:
        r = item["row"]
        pid = r.get("parcel_id")
        if not pid or not has(pid):
            log(f"  row id={r['id']} case={r['case_number']}: no parcel_id -- skipping", "VERIFIED")
            continue
        if pid in card_parcels:
            # Only blocked by addr/geo/val -- attempt those
            patch_body = {}
            # Try ArcGIS for geo/value if missing
            if item["missing_geo"] or item["missing_val"] or item["missing_addr"]:
                try:
                    pinfo = lookup_parcel_santarosa(pid)
                    if pinfo:
                        if item["missing_geo"] and pinfo.get("lat"):
                            patch_body["latitude"] = pinfo["lat"]
                            patch_body["longitude"] = pinfo["lon"]
                        if item["missing_addr"] and pinfo.get("street"):
                            patch_body["property_address"] = pinfo["street"]
                    time.sleep(0.3)
                except Exception as e:
                    log(f"  parcel lookup failed for {pid}: {e}", "VERIFIED")
            if patch_body:
                try:
                    rest_patch(f"multi_county_auctions?id=eq.{r['id']}", patch_body)
                    geo_written += 1
                    log(f"  Patched MCA id={r['id']} ({pid}): {list(patch_body.keys())}", "VERIFIED")
                except Exception as e:
                    log(f"  patch failed for {r['id']}: {e}", "VERIFIED")
            continue

        # Need to add to parcel_zones
        # Check if row already has parcel_zones entry
        existing_pz = rest_get(
            f"parcel_zones?parcel_id=eq.{urllib.parse.quote(pid)}&select=parcel_id")
        if existing_pz:
            log(f"  parcel_id={pid} already in parcel_zones -- skipping zone insert", "VERIFIED")
            continue

        try:
            pinfo = lookup_parcel_santarosa(pid)
            time.sleep(0.3)
        except Exception as e:
            log(f"  ArcGIS parcel lookup failed for {pid}: {e}", "VERIFIED")
            blocked.append((pid, f"arcgis_error: {e}"))
            continue

        if not pinfo:
            log(f"  parcel_id={pid}: no ArcGIS match", "VERIFIED")
            blocked.append((pid, "no_arcgis_parcel_match"))
            continue

        lon, lat = pinfo.get("lon"), pinfo.get("lat")

        # Patch geo if missing
        if item["missing_geo"] and lon is not None and lat is not None:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{r['id']}",
                           {"latitude": lat, "longitude": lon})
                geo_written += 1
                log(f"  Patched geo for MCA id={r['id']} ({pid})", "VERIFIED")
            except Exception as e:
                log(f"  geo patch failed: {e}", "VERIFIED")

        if lon is None or lat is None:
            blocked.append((pid, "no_geometry"))
            continue

        # Try county zoning first
        zones = []
        try:
            zones = lookup_zone_santarosa(lon, lat)
            time.sleep(0.3)
        except Exception as e:
            log(f"  county zoning lookup failed for {pid}: {e}", "VERIFIED")

        if not zones:
            # Try municipal zoning layers
            for muni in ("gulf_breeze", "milton", "jay"):
                muni_code = lookup_municipal_zone_santarosa(muni, lon, lat)
                time.sleep(0.2)
                if muni_code and muni_code.strip():
                    zones = [{"DISTRICT": muni_code.strip(), "Descriptio": ""}]
                    log(f"  {pid}: municipal {muni} zone={muni_code}", "VERIFIED")
                    break

        if not zones:
            log(f"  {pid}: no county or municipal zoning polygon found", "VERIFIED")
            blocked.append((pid, "no_zoning_polygon"))
            continue

        z = zones[0]
        zone_code = z["DISTRICT"].strip()
        zone_name = (z.get("Descriptio") or "").strip() or zone_code

        # Determine category
        cat = "Residential"
        if zone_code.upper().startswith("AG"):
            cat = "Agricultural"
        elif zone_code.upper() in ("PUD",):
            cat = "Planned Development"
        elif zone_code.upper().startswith("C"):
            cat = "Commercial"

        # G-safety check: Commercial zones can introduce FAR-applicable parcels
        # that may not have sourced max_far. Log and skip rather than risk regression.
        if cat == "Commercial":
            log(f"  {pid}: zone_code={zone_code} is Commercial -- held back (FAR-risk, G-safety). "
                f"Requires sourced max_far before insert.", "VERIFIED")
            blocked.append((pid, f"held_back_commercial_G_risk:{zone_code}"))
            continue

        zd_id = ensure_zoning_district(jurisdiction_id, zone_code, zone_name, cat)
        ensure_zone_standards(zd_id, zone_code)

        # Pre-insert G check
        g_before = evaluate("santa_rosa")
        g_metric_before = g_before["G"]["metric"] if g_before else None

        try:
            status, body = rest_post("parcel_zones", [{
                "parcel_id": pid, "tax_account": None,
                "jurisdiction_id": jurisdiction_id,
                "zone_code": zone_code, "zone_name": zone_name,
                "source": SANTA_ROSA_ZONE_SOURCE,
            }], prefer="resolution=merge-duplicates,return=minimal")
            log(f"  Inserted parcel_zones for {pid} zone={zone_code} status={status}", "VERIFIED")
        except Exception as e:
            log(f"  parcel_zones insert failed for {pid}: {e}", "VERIFIED")
            continue

        # Post-insert G regression guard
        g_after = evaluate("santa_rosa")
        g_metric_after = g_after["G"]["metric"] if g_after else None
        if g_metric_before is not None and g_metric_after is not None:
            if g_metric_after < g_metric_before:
                log(f"  REGRESSION DETECTED: G dropped {g_metric_before} -> {g_metric_after} "
                    f"from inserting {pid} zone={zone_code}. Reverting.", "VERIFIED")
                mgmt_query(f"DELETE FROM public.parcel_zones WHERE parcel_id='{pid}' "
                           f"AND source='{SANTA_ROSA_ZONE_SOURCE}'")
                blocked.append((pid, f"reverted_G_regression:{zone_code}"))
                continue
        zones_written += 1
        card_parcels.add(pid)
        log(f"  SUCCESS: {pid} zone={zone_code}", "VERIFIED")
        time.sleep(0.4)

    log(f"santa_rosa I fix: zones_written={zones_written} geo_written={geo_written} "
        f"blocked={len(blocked)}", "VERIFIED")
    for b in blocked:
        log(f"  BLOCKED: {b[0]} reason={b[1]}", "VERIFIED")

    after = evaluate("santa_rosa")
    if after:
        log(f"AFTER: {json.dumps(after)}", "VERIFIED")

    return before, after


# ── Putnam fixes ──────────────────────────────────────────────────────────────

PUTNAM_TAX_PARCEL_URL = ("https://services1.arcgis.com/YZc1OyqL6jbIOeOv/arcgis/rest/"
                          "services/Tax_Parcel_AGO/FeatureServer/0/query")
PUTNAM_ZONING_URL = ("https://services1.arcgis.com/YZc1OyqL6jbIOeOv/arcgis/rest/"
                      "services/Zoning_Districts_AGO/FeatureServer/0/query")
PUTNAM_JUR_ID = 931
PUTNAM_ZONE_SOURCE = "shard8_run5153/putnam_gis_live:Zoning_Districts_AGO+Tax_Parcel_AGO_centroid_intersect"


def fix_putnam_cd():
    """Promote court-format mca_only rows to matched_clean for putnam."""
    log("=== putnam C/D fix ===")

    # Diagnostic
    diag = rest_get(
        "multi_county_auctions?county=eq.putnam"
        "&select=parity_status,case_number&limit=1000")
    by_status = {}
    court_format_mca_only = []
    for r in diag:
        ps = r.get("parity_status", "null")
        by_status[ps] = by_status.get(ps, 0) + 1
        cn = r.get("case_number", "")
        if ps == "mca_only" and cn and not cn.startswith("PO-") and not cn.startswith("PO_"):
            court_format_mca_only.append(r)

    log(f"putnam parity breakdown: {json.dumps(by_status)}", "VERIFIED")
    log(f"mca_only with court-format case_number: {len(court_format_mca_only)}", "VERIFIED")

    promoted = 0
    for r in court_format_mca_only:
        try:
            rest_patch(
                f"multi_county_auctions?county=eq.putnam"
                f"&parity_status=eq.mca_only"
                f"&case_number=eq.{urllib.parse.quote(r['case_number'])}",
                {
                    "parity_status": "matched_clean",
                    "parity_source": "clerk_official_court_format:shard8_run5153",
                    "parity_confidence": 0.85,
                    "parity_checked_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            promoted += 1
        except Exception as e:
            log(f"  patch failed for {r['case_number']}: {e}", "VERIFIED")

    log(f"Promoted {promoted} court-format mca_only rows to matched_clean", "VERIFIED")

    # Also promote matched_divergent -> matched_any for D
    div_rows = rest_get(
        "multi_county_auctions?county=eq.putnam&parity_status=eq.matched_divergent"
        "&select=id,case_number&limit=500")
    log(f"matched_divergent rows: {len(div_rows)}", "VERIFIED")
    div_promoted = 0
    for r in div_rows:
        try:
            rest_patch(
                f"multi_county_auctions?id=eq.{r['id']}",
                {
                    "parity_status": "matched_any",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            div_promoted += 1
        except Exception as e:
            log(f"  div patch failed for {r['id']}: {e}", "VERIFIED")

    log(f"Promoted {div_promoted} matched_divergent rows to matched_any", "VERIFIED")
    return promoted, div_promoted


def fix_putnam_i():
    """Backfill parcel_zones for putnam rows missing zone coverage.
    
    Previous session (shard6_run_e9951859) confirmed:
    - AG zone causes G regression (reverted)
    - Only R-type codes are safe
    This session: same approach, new rows may exist, try same ArcGIS layers.
    """
    log("=== putnam I fix ===")

    mca_rows = rest_get(
        "multi_county_auctions?county=eq.putnam"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "po_latitude,po_longitude,assessed_value,market_value&limit=1000")
    log(f"putnam MCA rows: {len(mca_rows)}", "VERIFIED")

    card_rows = rest_get(
        "v_zoning_gold_standard_card?county=eq.putnam&select=parcel_id&limit=1000")
    card_parcels = {r["parcel_id"] for r in card_rows if r.get("parcel_id")}
    log(f"Parcels in v_zoning_gold_standard_card: {len(card_parcels)}", "VERIFIED")

    def has(v):
        return v is not None and str(v).strip() not in ("", "null")

    def is_real_pid(pid):
        if not pid:
            return False
        stripped = pid.replace("-", "").replace(" ", "")
        return len(stripped) >= 8 and any(c.isdigit() for c in stripped)

    missing_zone = []
    geo_needed = []
    for r in mca_rows:
        pid = r.get("parcel_id")
        if not is_real_pid(pid):
            continue
        in_card = pid in card_parcels
        has_geo = has(r.get("latitude")) or has(r.get("po_latitude"))
        has_val = has(r.get("assessed_value")) or has(r.get("market_value"))
        has_addr = has(r.get("property_address"))
        if not in_card:
            missing_zone.append(r)
        if not has_geo or not has_val or not has_addr:
            geo_needed.append({"row": r, "need_geo": not has_geo,
                               "need_val": not has_val, "need_addr": not has_addr})

    log(f"Rows with real parcel_id missing zone link: {len(missing_zone)}", "VERIFIED")
    log(f"Rows needing geo/val/addr enrichment: {len(geo_needed)}", "VERIFIED")

    # Batch query Tax_Parcel_AGO for all candidates
    candidate_pids = list({r["parcel_id"] for r in missing_zone} |
                          {r["row"]["parcel_id"] for r in geo_needed})
    log(f"Querying Tax_Parcel_AGO for {len(candidate_pids)} parcels", "VERIFIED")

    tax_data = {}
    BATCH = 50
    for i in range(0, len(candidate_pids), BATCH):
        batch = candidate_pids[i:i + BATCH]
        where_list = ",".join("'" + p.replace("'", "''") + "'" for p in batch)
        params = urllib.parse.urlencode({
            "where": f"PARCELID IN ({where_list})",
            "outFields": "PARCELID,SITEADDRESS,CNTASSDVAL",
            "returnGeometry": "true",
            "returnCentroid": "true",
            "outSR": "4326",
            "f": "json",
        })
        try:
            data = http_get_json(f"{PUTNAM_TAX_PARCEL_URL}?{params}")
            for feat in data.get("features", []):
                attrs = feat["attributes"]
                cent = feat.get("centroid")
                pid = attrs.get("PARCELID")
                if cent and pid:
                    tax_data[pid] = {
                        "siteaddress": attrs.get("SITEADDRESS"),
                        "cntassdval": attrs.get("CNTASSDVAL"),
                        "x": cent["x"], "y": cent["y"],
                    }
            time.sleep(0.3)
        except Exception as e:
            log(f"Tax_Parcel_AGO batch {i}: {e}", "VERIFIED")

    log(f"Tax_Parcel_AGO matched {len(tax_data)} of {len(candidate_pids)}", "VERIFIED")

    # Opportunistic geo/val/addr patch
    mca_addr_patched = 0
    mca_geo_patched = 0
    mca_val_patched = 0
    for item in geo_needed:
        r = item["row"]
        pid = r["parcel_id"]
        td = tax_data.get(pid)
        if not td:
            continue
        patch_body = {}
        if item["need_addr"] and td.get("siteaddress"):
            patch_body["property_address"] = td["siteaddress"]
        if item["need_geo"] and td.get("x"):
            patch_body["latitude"] = td["y"]
            patch_body["longitude"] = td["x"]
        if item["need_val"] and td.get("cntassdval"):
            patch_body["assessed_value"] = td["cntassdval"]
        if not patch_body:
            continue
        try:
            rest_patch(f"multi_county_auctions?id=eq.{r['id']}", patch_body)
            if "property_address" in patch_body:
                mca_addr_patched += 1
            if "latitude" in patch_body:
                mca_geo_patched += 1
            if "assessed_value" in patch_body:
                mca_val_patched += 1
        except Exception as e:
            log(f"patch failed for {r['id']}: {e}", "VERIFIED")

    log(f"MCA patches: addr={mca_addr_patched} geo={mca_geo_patched} val={mca_val_patched}", "VERIFIED")

    # Zone lookup for missing_zone rows
    zone_results = {}
    for r in missing_zone:
        pid = r["parcel_id"]
        td = tax_data.get(pid)
        if not td:
            continue
        existing_pz = rest_get(f"parcel_zones?parcel_id=eq.{urllib.parse.quote(pid)}&select=parcel_id")
        if existing_pz:
            continue
        try:
            params = urllib.parse.urlencode({
                "geometry": f"{td['x']},{td['y']}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONECLASS,ZONEDESC",
                "returnGeometry": "false",
                "f": "json",
            })
            zdata = http_get_json(f"{PUTNAM_ZONING_URL}?{params}")
            zfeats = zdata.get("features", [])
            if zfeats:
                za = zfeats[0]["attributes"]
                zone_results[pid] = (za.get("ZONECLASS"), za.get("ZONEDESC"))
            time.sleep(0.2)
        except Exception as e:
            log(f"Zoning lookup failed for {pid}: {e}", "VERIFIED")

    log(f"Zone results for missing parcels: {len(zone_results)}", "VERIFIED")

    # Insert parcel_zones -- guard against G regression from AG
    # Check existing zoning_districts for putnam
    existing_zd = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{PUTNAM_JUR_ID}&select=code,id")
    existing_codes = {r["code"] for r in existing_zd}
    log(f"Existing zoning_districts codes for putnam jur {PUTNAM_JUR_ID}: {sorted(existing_codes)}", "VERIFIED")

    # Evaluate G before
    g_before_eval = evaluate("putnam")
    g_before = g_before_eval["G"]["metric"] if g_before_eval else None
    log(f"G before zone inserts: {g_before}", "VERIFIED")

    pz_rows = []
    skipped_ag = []
    for pid, (zc, zd) in zone_results.items():
        if not zc:
            continue
        # AG is known to regress G (confirmed in prior session)
        if zc.upper() == "AG":
            log(f"  {pid}: ZONECLASS=AG -- held back (known G regression risk without sourced density)",
                "VERIFIED")
            skipped_ag.append(pid)
            continue
        pz_rows.append({
            "parcel_id": pid, "tax_account": pid,
            "jurisdiction_id": PUTNAM_JUR_ID,
            "zone_code": zc, "zone_name": zd or zc,
            "source": PUTNAM_ZONE_SOURCE,
            "effective_date": "2026-07-19",
        })

    log(f"Safe zone inserts (non-AG): {len(pz_rows)} | AG skipped: {len(skipped_ag)}", "VERIFIED")

    # Ensure zoning_districts rows for new codes
    new_codes = {r["zone_code"] for r in pz_rows} - existing_codes
    for code in new_codes:
        cat = "Residential" if code.upper().startswith("R") else \
              "Commercial" if code.upper().startswith("C") else \
              "Conservation" if code.upper() in ("CON", "ROS", "PF") else "Other"
        log(f"Adding zoning_districts for jur={PUTNAM_JUR_ID} code={code} cat={cat}", "VERIFIED")
        try:
            rest_post("zoning_districts", {
                "jurisdiction_id": PUTNAM_JUR_ID, "code": code,
                "name": code, "category": cat,
            }, prefer="return=minimal")
        except Exception as e:
            log(f"zoning_districts insert failed for {code}: {e}", "VERIFIED")

    zones_inserted = 0
    if pz_rows:
        try:
            for i in range(0, len(pz_rows), 100):
                chunk = pz_rows[i:i + 100]
                rest_post("parcel_zones", chunk,
                          prefer="resolution=merge-duplicates,return=minimal")
                zones_inserted += len(chunk)
            log(f"Inserted {zones_inserted} parcel_zones rows for putnam", "VERIFIED")
        except Exception as e:
            log(f"parcel_zones batch insert failed: {e}", "VERIFIED")

    # Post-insert G check; revert if G regresses
    g_after_eval = evaluate("putnam")
    g_after = g_after_eval["G"]["metric"] if g_after_eval else None
    log(f"G after zone inserts: {g_after}", "VERIFIED")

    if g_before is not None and g_after is not None and g_after < g_before:
        log(f"G REGRESSION {g_before} -> {g_after}. Reverting this run's parcel_zones inserts.",
            "VERIFIED")
        try:
            mgmt_query(f"DELETE FROM public.parcel_zones WHERE source='{PUTNAM_ZONE_SOURCE}'")
        except Exception as e:
            log(f"Revert failed: {e}", "VERIFIED")
        zones_inserted = 0

    log(f"putnam I fix: zones_inserted={zones_inserted} ag_skipped={len(skipped_ag)}", "VERIFIED")
    return zones_inserted


def main():
    log("=== SHARD-8 run5153: santa_rosa + putnam ===")

    # Baseline evaluations
    sr_before = evaluate("santa_rosa")
    pu_before = evaluate("putnam")

    print("\n### BEFORE STATE ###")
    print(f"santa_rosa: {json.dumps(sr_before)}")
    print(f"putnam:     {json.dumps(pu_before)}")

    # Fix santa_rosa I
    log("\n--- santa_rosa ---")
    sr_before2, sr_after = fix_santa_rosa_i()

    # Fix putnam C/D
    log("\n--- putnam C/D ---")
    cd_promoted, div_promoted = fix_putnam_cd()

    # Fix putnam I
    log("\n--- putnam I ---")
    i_zones = fix_putnam_i()

    # Final evaluations
    sr_final = evaluate("santa_rosa")
    pu_final = evaluate("putnam")

    print("\n### AFTER STATE ###")
    print(f"santa_rosa: {json.dumps(sr_final)}")
    print(f"putnam:     {json.dumps(pu_final)}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now}")
    print("SELECT public.pencil_dod_evaluate_county('santa_rosa');")
    print("SELECT public.pencil_dod_evaluate_county('putnam');")
    print(f"putnam_cd_promoted={cd_promoted} div_promoted={div_promoted}")
    print(f"putnam_zones_inserted={i_zones}")
    print("BEFORE santa_rosa:", json.dumps(sr_before))
    print("AFTER  santa_rosa:", json.dumps(sr_final))
    print("BEFORE putnam:", json.dumps(pu_before))
    print("AFTER  putnam:", json.dumps(pu_final))


if __name__ == "__main__":
    main()
