#!/usr/bin/env python3
"""
SHARD-3 RUN-6080 — santa_rosa Letter-I fix for newly-ingested auction rows.

Context (VERIFIED from prior session reports):
  Prior session (dispatch 4569d5ab-b34d-4b1e-80fb-183b058262db) achieved
  santa_rosa 10/10 with I=96.5% (card_complete=83/86). Since then, 2 new
  auction rows were ingested, raising the denominator to 88 and dropping
  I to 94.3% (83/88 = below the 95% threshold). Need card_complete >= 84
  to clear 95.45%.

Strategy:
  1. Identify MCA rows for santa_rosa with a parcel_id that is NOT present
     in v_zoning_gold_standard_card (the same root cause as prior sessions).
  2. For each such parcel, query:
       a. Santa Rosa County ParcelsOpenData ArcGIS FeatureServer (for
          geometry/centroid and situs address).
       b. County Zoning FeatureServer at that centroid (for zone code).
       c. If the county zoning layer returns only the "CITY" marker polygon,
          fall back to the municipal layers on cloud.santarosa.fl.gov:
            - Gulf_Breeze_Zoning/FeatureServer/0
            - City_of_Milton_Zoning/FeatureServer/0
            - TownOfJayZoning/FeatureServer/0
  3. Insert parcel_zones row + ensure zoning_districts + zone_standards
     (same pattern as shard7_run3679 + shard7c_run3679 scripts).
  4. G-regression guard: if G flips PASS->FAIL, abort with exit code 1.
  5. Emit SQL VERIFICATION block and log ultraloop audit row.

HONESTY PROTOCOL: every claim tagged VERIFIED/INFERRED/UNTESTED.

Usage:
  python3 scripts/shard3_run6080_santa_rosa_i_new_rows_fix.py
  python3 scripts/shard3_run6080_santa_rosa_i_new_rows_fix.py --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "santa_rosa"
DISPATCH_ID = "cc621572-35e9-41fd-a901-e5719416b834"
ZONE_SOURCE_TAG = "shard3_run6080_arcgis_santarosa_i_fix"

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)

DRY_RUN = "--dry-run" in sys.argv

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# Santa Rosa County ArcGIS Online (public, no auth)
ARCGIS_ORG = "Eg4L1xEv2R3abuQd"
PARCEL_QUERY_URL = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
                    f"services/ParcelsOpenData/FeatureServer/0/query")
COUNTY_ZONING_URL = (f"https://services.arcgis.com/{ARCGIS_ORG}/arcgis/rest/"
                     f"services/Zoning/FeatureServer/0/query")

# Santa Rosa County-hosted municipal zoning layers (cloud.santarosa.fl.gov,
# no auth required — Hosted folder, confirmed in prior sessions)
GULF_BREEZE_ZONING_URL = ("https://cloud.santarosa.fl.gov/arcgis/rest/services/"
                           "Hosted/Gulf_Breeze_Zoning/FeatureServer/0/query")
MILTON_ZONING_URL = ("https://cloud.santarosa.fl.gov/arcgis/rest/services/"
                     "Hosted/City_of_Milton_Zoning/FeatureServer/0/query")
JAY_ZONING_URL = ("https://cloud.santarosa.fl.gov/arcgis/rest/services/"
                  "Hosted/TownOfJayZoning/FeatureServer/0/query")

# Known jurisdiction IDs in santa_rosa
UNINC_JURISDICTION_NAME = "Unincorporated Santa Rosa County"
GULF_BREEZE_JURISDICTION_ID = 828
MILTON_JURISDICTION_ID = 956
JAY_JURISDICTION_ID = 1124

# Gulf Breeze ArcGIS compressed code -> pre-existing DB code (reuses sourced rows)
GULF_BREEZE_CODE_NORMALIZE = {"RC": "R-C", "C1": "C-1"}

# Real, codified max density from Santa Rosa County LDC Table 2.04.02.a
# (same source as shard7_run3679 script, already in DB for pre-existing rows)
LDC_SOURCE_URL = ("https://www.santarosa.fl.gov/DocumentCenter/View/5820/"
                  "Santa-Rosa-County-Land-Development-Code-")
UNINC_DENSITY_BY_CODE: dict[str, float] = {
    "AG-RR": 1.0,
    "R1": 4.0,
    "R1M": 4.0,
    "R2M": 10.0,
    "PUD": 18.0,
    "HCD": 10.0,
}

# Milton standards from City of Milton UDC Article 6 (miltonfl.org)
MILTON_UDC_SOURCE = ("https://www.miltonfl.org/DocumentCenter/View/1852/"
                     "ARTICLE-6-ZONING-DISTRICT-REGULATIONS")
MILTON_STANDARDS: dict[str, dict] = {
    "R-U": {"name": "Rural Urban District", "category": "Residential",
            "min_lot_sqft": 7000.0, "front_setback_ft": 20.0,
            "side_setback_ft": 10.0, "rear_setback_ft": 15.0,
            "max_height_ft": 36.0},
    "R-1": {"name": "R-1 Single-Family Residential Zoning District",
            "category": "Residential", "min_lot_sqft": 7500.0,
            "min_lot_width_ft": 70.0, "front_setback_ft": 25.0,
            "side_setback_ft": 12.0, "rear_setback_ft": 20.0,
            "max_height_ft": 36.0},
    "R-1A": {"name": "R-1A Single-Family Residential Zoning District",
             "category": "Residential", "min_lot_sqft": 9000.0,
             "min_lot_width_ft": 80.0, "front_setback_ft": 30.0,
             "side_setback_ft": 15.0, "rear_setback_ft": 20.0,
             "max_height_ft": 36.0},
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, tag: str = "UNTESTED") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} on {url}: {e.read()[:300]}") from e


def rest_get(path: str) -> list:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path: str, body, prefer: str = "return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json", "Prefer": prefer,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()) if prefer.startswith("return=representation") else None


def rpc(fn: str, params: dict):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(),
        method="POST",
        headers={
            "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def centroid(rings: list) -> tuple[float, float]:
    pts = rings[0]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def lookup_parcel(strap: str) -> dict | None:
    nodash = strap.replace("-", "")
    params = urllib.parse.urlencode({
        "where": f"PAR_NUM='{nodash}'",
        "outFields": "PAR_NUM,StrNum,StrName,StSuffix",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    data = http_get_json(f"{PARCEL_QUERY_URL}?{params}")
    feats = data.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    geom = feats[0].get("geometry")
    if not geom or not geom.get("rings"):
        return {"attrs": attrs, "lon": None, "lat": None, "street": None}
    lon, lat = centroid(geom["rings"])
    street = " ".join(
        x.strip() for x in [attrs.get("StrNum"), attrs.get("StrName"), attrs.get("StSuffix")]
        if x and x.strip()
    )
    return {"attrs": attrs, "lon": lon, "lat": lat, "street": street or None}


def query_point(base_url: str, lon: float, lat: float, out_fields: str) -> list[dict]:
    params = urllib.parse.urlencode({
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    })
    data = http_get_json(f"{base_url}?{params}")
    return [f["attributes"] for f in data.get("features", [])]


def lookup_zone_county(lon: float, lat: float) -> list[dict]:
    feats = query_point(COUNTY_ZONING_URL, lon, lat, "DISTRICT,Descriptio")
    return [f for f in feats if f.get("DISTRICT") and f["DISTRICT"].strip().upper() != "CITY"]


def lookup_zone_municipal(lon: float, lat: float) -> tuple[str | None, str | None, str | None]:
    """Try Gulf Breeze, Milton, Jay municipal layers. Returns (muni, raw_code, zone_name)."""
    feats = query_point(GULF_BREEZE_ZONING_URL, lon, lat, "zoning,flum")
    for f in feats:
        if f.get("zoning") and f["zoning"].strip():
            return "gulf_breeze", f["zoning"].strip(), None

    feats = query_point(MILTON_ZONING_URL, lon, lat, "zone_code,zone_distr")
    for f in feats:
        if f.get("zone_code") and f["zone_code"].strip():
            return "milton", f["zone_code"].strip(), (f.get("zone_distr") or "").strip() or None

    feats = query_point(JAY_ZONING_URL, lon, lat, "zone,district")
    for f in feats:
        if f.get("zone") and f["zone"].strip():
            return "jay", f["zone"].strip(), (f.get("district") or "").strip() or None

    return None, None, None


_zd_cache: dict[str, int] = {}


def find_zoning_district(jurisdiction_id: int, code: str) -> int | None:
    cache_key = f"{jurisdiction_id}:{code}"
    if cache_key in _zd_cache:
        return _zd_cache[cache_key]
    rows = rest_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
        f"&code=eq.{urllib.parse.quote(code)}"
    )
    if rows:
        _zd_cache[cache_key] = rows[0]["id"]
        return rows[0]["id"]
    return None


def ensure_zoning_district(jurisdiction_id: int, code: str, name: str, category: str,
                            far_regulated=None, pk1000_regulated=None) -> int:
    did = find_zoning_district(jurisdiction_id, code)
    if did is not None:
        return did
    if DRY_RUN:
        log(f"DRY-RUN would create zoning_districts jurisdiction_id={jurisdiction_id} code={code}", "UNTESTED")
        return -1
    body: dict = {"jurisdiction_id": jurisdiction_id, "code": code, "name": name, "category": category}
    if far_regulated is not None:
        body["far_regulated"] = far_regulated
    if pk1000_regulated is not None:
        body["pk1000_regulated"] = pk1000_regulated
    created = rest_post("zoning_districts", body)
    did = created[0]["id"]
    _zd_cache[f"{jurisdiction_id}:{code}"] = did
    log(f"Created zoning_districts id={did} jurisdiction_id={jurisdiction_id} code={code}", "VERIFIED")
    return did


def ensure_zone_standards_uninc(zd_id: int, zone_code: str) -> None:
    if zd_id == -1:
        return
    existing = rest_get(f"zone_standards?zoning_district_id=eq.{zd_id}")
    if existing:
        return
    density = UNINC_DENSITY_BY_CODE.get(zone_code)
    if density is None:
        log(f"  No codified density for uninc zone_code={zone_code} -- skipping zone_standards", "VERIFIED")
        return
    if DRY_RUN:
        log(f"DRY-RUN would insert zone_standards zoning_district_id={zd_id} max_density_du_acre={density}", "UNTESTED")
        return
    rest_post("zone_standards", {
        "zoning_district_id": zd_id,
        "max_density_du_acre": density,
        "source_url": LDC_SOURCE_URL,
        "confidence_score": 1.0,
    }, prefer="return=minimal")
    log(f"Inserted zone_standards zd_id={zd_id} max_density_du_acre={density} (Santa Rosa LDC Table 2.04.02)", "VERIFIED")


def ensure_zone_standards_milton(zd_id: int, code: str) -> None:
    if zd_id == -1:
        return
    existing = rest_get(f"zone_standards?zoning_district_id=eq.{zd_id}")
    if existing:
        return
    spec = MILTON_STANDARDS.get(code)
    if not spec:
        return
    if DRY_RUN:
        log(f"DRY-RUN would insert zone_standards for Milton zd_id={zd_id} code={code}", "UNTESTED")
        return
    body = {
        "zoning_district_id": zd_id,
        "source_url": MILTON_UDC_SOURCE,
        "confidence_score": 0.8,
    }
    for k in ["min_lot_sqft", "min_lot_width_ft", "front_setback_ft",
              "side_setback_ft", "rear_setback_ft", "max_height_ft"]:
        if k in spec:
            body[k] = spec[k]
    rest_post("zone_standards", body, prefer="return=minimal")
    log(f"Inserted zone_standards for Milton zd_id={zd_id} code={code} (UDC Table 6.2.1/6.4.1)", "VERIFIED")


def get_or_create_uninc_jurisdiction() -> int:
    rows = rest_get(
        f"jurisdictions?county=eq.Santa%20Rosa"
        f"&name=eq.{urllib.parse.quote(UNINC_JURISDICTION_NAME)}"
    )
    if rows:
        return rows[0]["id"]
    if DRY_RUN:
        log(f"DRY-RUN would create jurisdiction '{UNINC_JURISDICTION_NAME}'", "UNTESTED")
        return -1
    created = rest_post("jurisdictions", {
        "name": UNINC_JURISDICTION_NAME, "county": "Santa Rosa", "state": "FL",
        "co_no": 57, "active": True, "data_source": ZONE_SOURCE_TAG,
    })
    jid = created[0]["id"]
    log(f"Created jurisdiction '{UNINC_JURISDICTION_NAME}' id={jid}", "VERIFIED")
    return jid


def log_ultraloop_audit(letter: str, claim: str, evidence: dict, survived: bool) -> None:
    if DRY_RUN:
        log(f"DRY-RUN would log ultraloop audit letter={letter} survived={survived}", "UNTESTED")
        return
    try:
        rest_post("gold_standard_ultraloop_audit", {
            "dispatch_id": DISPATCH_ID,
            "ultraloop_mode": "fallback",
            "county_slug": COUNTY,
            "letter": letter,
            "claim": claim,
            "refuter_evidence": evidence,
            "survived": survived,
        }, prefer="return=minimal")
        log(f"Logged ultraloop_audit row letter={letter} survived={survived}", "VERIFIED")
    except Exception as e:
        log(f"ultraloop_audit insert failed (non-fatal): {e}", "VERIFIED")


def main() -> None:
    log("=== SHARD-3 RUN-6080: santa_rosa Letter-I new-rows ArcGIS fix ===")
    if DRY_RUN:
        log("DRY-RUN mode — no writes", "UNTESTED")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "VERIFIED")
        sys.exit(1)

    # ── BASELINE ──────────────────────────────────────────────────────────────
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE I: {baseline['I']}", "VERIFIED")
    log(f"BASELINE G: {baseline['G']}", "VERIFIED")
    log(f"BASELINE auctions_total: {baseline.get('auctions_total')}", "VERIFIED")

    # ── IDENTIFY INCOMPLETE ROWS ──────────────────────────────────────────────
    log("Fetching all santa_rosa MCA rows ...", "UNTESTED")
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        f"po_latitude,po_longitude,assessed_value,market_value"
    )
    log(f"Total MCA rows: {len(mca_rows)}", "VERIFIED")

    log("Fetching v_zoning_gold_standard_card for santa_rosa ...", "UNTESTED")
    county_enc = urllib.parse.quote("santa rosa")
    card_rows = rest_get(f"v_zoning_gold_standard_card?county=eq.{county_enc}&select=parcel_id")
    card_parcels = {r["parcel_id"] for r in card_rows if r.get("parcel_id")}
    log(f"Parcels in v_zoning_gold_standard_card: {len(card_parcels)}", "VERIFIED")

    def has(v) -> bool:
        return v is not None and str(v).strip() != ""

    missing = [
        r for r in mca_rows
        if has(r.get("parcel_id")) and r["parcel_id"] not in card_parcels
    ]
    log(f"MCA rows with parcel_id NOT in v_zoning_gold_standard_card: {len(missing)}", "VERIFIED")

    no_parcel_rows = [r for r in mca_rows if not has(r.get("parcel_id"))]
    log(f"MCA rows with NO parcel_id (out of scope for I): {len(no_parcel_rows)}", "VERIFIED")

    if not missing:
        log("No rows need parcel_zones enrichment — checking if I already passes", "VERIFIED")
        if baseline["I"]["pass"]:
            log("I already PASS — nothing to do", "VERIFIED")
        else:
            log("I still FAIL but no parcel_zones candidates found — other root cause", "VERIFIED")
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n### SQL VERIFICATION — {COUNTY} Letter-I (no new parcel_zones needed)")
        print(f"Timestamp UTC: {now_iso}")
        print(f"BASELINE I: {baseline['I']}")
        return

    # ── ArcGIS LOOKUP PER MISSING ROW ────────────────────────────────────────
    uninc_jid = get_or_create_uninc_jurisdiction()

    zone_inserts: list[dict] = []
    geo_patches: list[tuple] = []
    blocked: list[tuple] = []

    for row in missing:
        strap = row["parcel_id"]
        log(f"Processing parcel {strap} ...", "UNTESTED")

        info = lookup_parcel(strap)
        if not info:
            blocked.append((strap, "no ArcGIS ParcelsOpenData match"))
            log(f"  BLOCKED {strap}: no ArcGIS parcel match", "VERIFIED")
            continue

        lon, lat = info.get("lon"), info.get("lat")

        if lon is None or lat is None:
            blocked.append((strap, "parcel matched but no geometry returned"))
            log(f"  BLOCKED {strap}: no geometry", "VERIFIED")
            continue

        # Geo backfill for rows missing lat/lon
        geo_missing = not (has(row.get("latitude")) or has(row.get("po_latitude")))
        if geo_missing:
            geo_patches.append((row["id"], strap, lat, lon))
            log(f"  Will patch geo for id={row['id']} ({strap}): lat={lat:.6f} lon={lon:.6f}", "VERIFIED")

        # Try county zoning layer first
        county_zones = lookup_zone_county(lon, lat)
        if county_zones:
            zone_code = county_zones[0]["DISTRICT"].strip()
            zone_name = (county_zones[0].get("Descriptio") or "").strip() or None
            log(f"  County zone: {zone_code} ({zone_name})", "VERIFIED")

            zd_id = ensure_zoning_district(
                uninc_jid, zone_code, zone_name or zone_code,
                "Agricultural" if zone_code.upper().startswith("AG") else
                ("Planned Development" if zone_code.upper() == "PUD" else
                 ("Commercial" if zone_code.upper() in ("HCD", "C-1", "C-2") else "Residential")),
            )
            ensure_zone_standards_uninc(zd_id, zone_code)
            zone_inserts.append({
                "parcel_id": strap,
                "tax_account": None,
                "jurisdiction_id": uninc_jid,
                "zone_code": zone_code,
                "zone_name": zone_name,
                "source": ZONE_SOURCE_TAG,
            })
            continue

        # Fall back to municipal layers
        log(f"  County zoning returned only CITY marker — trying municipal layers", "UNTESTED")
        muni, raw_code, zone_name = lookup_zone_municipal(lon, lat)

        if muni is None:
            blocked.append((strap, "no zoning found in county or municipal layers"))
            log(f"  BLOCKED {strap}: no zone found", "VERIFIED")
            continue

        log(f"  Municipal zone ({muni}): {raw_code} ({zone_name})", "VERIFIED")

        if muni == "gulf_breeze":
            code = GULF_BREEZE_CODE_NORMALIZE.get(raw_code, raw_code)
            jid = GULF_BREEZE_JURISDICTION_ID
            zd_id = find_zoning_district(jid, code)
            if zd_id is None:
                blocked.append((strap, f"Gulf Breeze code {code} (raw {raw_code}) not in DB"))
                log(f"  BLOCKED {strap}: Gulf Breeze {code} has no pre-existing district row", "VERIFIED")
                continue
            zs = rest_get(f"zone_standards?zoning_district_id=eq.{zd_id}")
            if not zs or zs[0].get("max_density_du_acre") is None:
                log(f"  Gulf Breeze {code}: density incomplete in zone_standards (not blocking)", "VERIFIED")
            zone_inserts.append({
                "parcel_id": strap,
                "tax_account": None,
                "jurisdiction_id": jid,
                "zone_code": code,
                "zone_name": zone_name,
                "source": ZONE_SOURCE_TAG,
            })

        elif muni == "milton":
            code = raw_code
            jid = MILTON_JURISDICTION_ID
            if code not in MILTON_STANDARDS:
                blocked.append((strap, f"Milton code {code} not in sourced standards set"))
                log(f"  BLOCKED {strap}: Milton code {code} unsourced", "VERIFIED")
                continue
            spec = MILTON_STANDARDS[code]
            zd_id = ensure_zoning_district(jid, code, spec["name"], spec["category"])
            ensure_zone_standards_milton(zd_id, code)
            zone_inserts.append({
                "parcel_id": strap,
                "tax_account": None,
                "jurisdiction_id": jid,
                "zone_code": code,
                "zone_name": spec["name"],
                "source": ZONE_SOURCE_TAG,
            })

        elif muni == "jay":
            code = raw_code
            jid = JAY_JURISDICTION_ID
            zd_id = ensure_zoning_district(jid, code, zone_name or code, "Residential")
            zone_inserts.append({
                "parcel_id": strap,
                "tax_account": None,
                "jurisdiction_id": jid,
                "zone_code": code,
                "zone_name": zone_name,
                "source": ZONE_SOURCE_TAG,
            })

    log(f"zone_inserts queued: {len(zone_inserts)}", "VERIFIED")
    log(f"geo_patches queued: {len(geo_patches)}", "VERIFIED")
    log(f"blocked: {len(blocked)}", "VERIFIED")
    for strap, reason in blocked:
        log(f"  BLOCKED {strap}: {reason}", "VERIFIED")

    if DRY_RUN:
        for z in zone_inserts:
            log(f"DRY-RUN INSERT parcel_zones: {z}", "UNTESTED")
        for (rid, strap, lat, lon) in geo_patches:
            log(f"DRY-RUN PATCH mca id={rid} lat={lat} lon={lon}", "UNTESTED")
        print("\n### DRY-RUN COMPLETE — no writes performed")
        return

    # ── WRITE parcel_zones ────────────────────────────────────────────────────
    zones_written = 0
    if zone_inserts:
        existing_pz = rest_get(
            "parcel_zones?parcel_id=in.("
            + ",".join(urllib.parse.quote(z["parcel_id"]) for z in zone_inserts)
            + ")&select=parcel_id"
        )
        existing_pz_ids = {r["parcel_id"] for r in existing_pz}
        new_inserts = [z for z in zone_inserts if z["parcel_id"] not in existing_pz_ids]
        if new_inserts:
            rest_post("parcel_zones", new_inserts, prefer="return=minimal")
            zones_written = len(new_inserts)
            log(f"Inserted {zones_written} new parcel_zones rows", "VERIFIED")
        else:
            log("All candidate parcel_zones rows already exist — idempotent no-op", "VERIFIED")

    # ── WRITE geo patches ─────────────────────────────────────────────────────
    geo_written = 0
    for (rid, strap, lat, lon) in geo_patches:
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/multi_county_auctions?id=eq.{rid}",
            data=json.dumps({"latitude": lat, "longitude": lon}).encode(),
            method="PATCH",
            headers={
                "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                "Content-Type": "application/json", "Prefer": "return=minimal",
            },
        )
        with urllib.request.urlopen(req, timeout=30):
            pass
        geo_written += 1
    if geo_written:
        log(f"Patched geo on {geo_written} MCA rows (real ArcGIS centroids)", "VERIFIED")

    # ── POST-FIX EVALUATION ───────────────────────────────────────────────────
    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER I: {after['I']}", "VERIFIED")
    log(f"AFTER G: {after['G']}", "VERIFIED")

    # G regression guard
    if baseline["G"]["pass"] and not after["G"]["pass"]:
        log("REGRESSION: G flipped PASS->FAIL — aborting with exit 1 per fail-loud guardrail", "VERIFIED")
        log_ultraloop_audit(
            "G",
            "santa_rosa G regression caused by shard3_run6080 parcel_zones inserts",
            {"before": baseline["G"], "after": after["G"],
             "zones_written": zones_written, "zone_inserts": zone_inserts},
            survived=False,
        )
        print("\n### RESULT: G REGRESSION — see log above")
        sys.exit(1)

    i_pass = after["I"]["pass"]
    log(f"Letter-I gate: {'PASS' if i_pass else 'FAIL'}", "VERIFIED")

    # ── ULTRALOOP AUDIT ROWS ──────────────────────────────────────────────────
    log_ultraloop_audit(
        "I",
        f"santa_rosa I: new-row ArcGIS enrichment — {zones_written} parcel_zones inserted, "
        f"{len(blocked)} blocked, metric {baseline['I']['metric']}% -> {after['I']['metric']}%",
        {
            "before": baseline["I"],
            "after": after["I"],
            "zones_written": zones_written,
            "geo_written": geo_written,
            "blocked": [{"parcel_id": s, "reason": r} for s, r in blocked],
        },
        survived=i_pass,
    )
    log_ultraloop_audit(
        "G",
        f"santa_rosa G: confirmed NOT regressed after {zones_written} new parcel_zones inserts",
        {"before": baseline["G"], "after": after["G"], "zones_written": zones_written},
        survived=True,
    )

    # ── SQL VERIFICATION BLOCK ────────────────────────────────────────────────
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION — {COUNTY} Letter-I (shard3_run6080)")
    print(f"Timestamp UTC: {now_iso}")
    print("")
    print("-- I metric query:")
    print("SELECT")
    print("  COUNT(*) AS total_rows,")
    print("  SUM(CASE WHEN property_address IS NOT NULL AND property_address <> ''")
    print("             AND latitude IS NOT NULL AND longitude IS NOT NULL")
    print("             AND (assessed_value IS NOT NULL OR market_value IS NOT NULL)")
    print("             AND parcel_id IS NOT NULL")
    print("        THEN 1 ELSE 0 END) AS complete_cards,")
    print("  ROUND(100.0 * SUM(CASE WHEN property_address IS NOT NULL AND property_address <> ''")
    print("             AND latitude IS NOT NULL AND longitude IS NOT NULL")
    print("             AND (assessed_value IS NOT NULL OR market_value IS NOT NULL)")
    print("             AND parcel_id IS NOT NULL")
    print("        THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_complete")
    print("FROM multi_county_auctions WHERE county = 'santa_rosa';")
    print("")
    print("-- New parcel_zones rows:")
    print(f"SELECT parcel_id, jurisdiction_id, zone_code, source FROM parcel_zones")
    print(f"WHERE source = '{ZONE_SOURCE_TAG}';")
    print("")
    print(f"BEFORE I : {baseline['I']}")
    print(f"AFTER  I : {after['I']}")
    print(f"BEFORE G : {baseline['G']}")
    print(f"AFTER  G : {after['G']}")
    print(f"zones_written   = {zones_written}")
    print(f"geo_written     = {geo_written}")
    print(f"blocked_count   = {len(blocked)}")
    print(f"I gate: {'PASS' if i_pass else 'FAIL (target 95%)'}")

    if not i_pass:
        log(
            f"I still FAIL ({after['I']['metric']}% < 95%). "
            f"Remaining blocked rows need a different data source.",
            "VERIFIED",
        )
        sys.exit(2)

    log("=== COMPLETE: santa_rosa Letter-I PASS ===", "VERIFIED")


if __name__ == "__main__":
    main()
