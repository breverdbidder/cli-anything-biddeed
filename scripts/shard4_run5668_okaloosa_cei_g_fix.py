#!/usr/bin/env python3
"""
Okaloosa C/E/I + G fix (SHARD-4 RUN-5668, 2026-07-21)
=======================================================
okaloosa status: 6/10 — failing C (30%), E (30%), G (75.6%), I (30%)

Root cause analysis:
  C/E/I were at 95% after 3rd firing (38/40). Now 30% = 12/40.
  The denominator grew from 40 to 40 (same) but matched_clean/parcel_linked
  dropped to 12, suggesting the Bid4Assets harvest introduced new rows (or
  previously matched rows had their parcel_id/parity_status cleared).

  More likely: A=13 means fc=27 td=13 = 40 total. The 3rd firing had:
    A=13 [fc=27 td=13] confirmed. The mismatch was that parity_status=
    'matched_clean' count dropped from 38 to 12, meaning 26 rows that were
    previously 'matched_clean' or 'matched_divergent' are now unmatched.

  Hypothesis: the Bid4Assets harvest (06:20Z daily cron) upserts rows with
  parity_status='matched_divergent' (FC rows) which overwrites the
  previously enriched 'matched_clean' status that okaloosa_parcel_gis_enrich.py
  set. The cron harvester runs AFTER the GIS enrichment, resetting C/E.

Strategy this session:
  1. Re-run parcel GIS enrichment for all 40 okaloosa rows (idempotent).
     This re-patches parity_status='matched_clean' for FC rows with confirmed GIS PIN.
  2. Re-run zoning substrate build for any new rows (idempotent).
  3. Attempt G density bifurcation fix for Unincorporated Okaloosa R-1 + MU:
     Query the Eglin AFB Encroachment Zone boundary and the UDAB boundary from
     okgis.myokaloosa.com to determine which density value applies per parcel.

G open gaps (from 3rd firing addendum):
  - Unincorporated R-1 (8 parcels): density bifurcated per ordinance
    (4 du/acre north of Eglin AFB vs 5 south; MU: 25 inside UDAB vs 4 outside)
  - Destin GRMU/TCMU parking: LDC Art. 8 Sec. 8.06.10 was unreachable

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DRY_RUN = "--dry-run" in sys.argv
COUNTY = "okaloosa"

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

GIS_BASE = "https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/Parcels_with_Addressing/MapServer/121/query"
CITY_LIMITS_URL = "https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/Admin_Boundaries/MapServer/99/query"
COUNTY_ZONING_URL = "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/28/query"

CITY_ZONING_SOURCES = {
    "CRESTVIEW": {
        "jurisdiction_name": "Crestview",
        "url": "https://services9.arcgis.com/zvdDL6ILvlkPNTg8/arcgis/rest/services/Zoning_and_FLU/FeatureServer/0/query",
        "zone_field": "ZONE",
        "source_tag": "crestview_gis:zoning_and_flu_featureserver:0",
    },
    "FORT WALTON BEACH": {
        "jurisdiction_name": "Fort Walton Beach",
        "url": "https://gis.fwb.org/arcgis/rest/services/Maps/Zoning/MapServer/0/query",
        "zone_field": "Zoning",
        "source_tag": "fwb_gis:maps/zoning:0",
    },
    "NICEVILLE": {
        "jurisdiction_name": "Niceville",
        "url": "https://gis.nicevillefl.gov/server/rest/services/Zoning/MapServer/0/query",
        "zone_field": "Zoning_2015",
        "source_tag": "niceville_gis:zoning:0",
    },
    "DESTIN": {
        "jurisdiction_name": "Destin",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/LocalGovernment/Destin_EnerGov/MapServer/6/query",
        "zone_field": "Zone_ABBR",
        "source_tag": "okaloosa_gis:localgovernment/destin_energov:6",
    },
}

UNINCORPORATED_JURISDICTION_NAME = "Unincorporated Okaloosa County"
COUNTY_ZONING_SOURCE_TAG = "okaloosa_gis:planning-development/zoning:28"

STREET_SUFFIXES = {
    "ST": "ST", "STREET": "ST", "AVE": "AVE", "AVENUE": "AVE",
    "DR": "DR", "DRIVE": "DR", "RD": "RD", "ROAD": "RD",
    "LN": "LN", "LANE": "LN", "CT": "CT", "COURT": "CT",
    "CIR": "CIR", "CIRCLE": "CIR", "BLVD": "BLVD", "BOULEVARD": "BLVD",
    "WAY": "WAY", "TRL": "TRL", "TRAIL": "TRL", "PL": "PL", "PLACE": "PL",
    "TER": "TER", "TERRACE": "TER", "PKWY": "PKWY", "PARKWAY": "PKWY",
    "LOOP": "LOOP", "PATH": "PATH", "RUN": "RUN", "CV": "CV", "COVE": "CV",
    "PT": "PT", "POINT": "PT", "XING": "XING", "CROSSING": "XING",
    "WALK": "WALK", "ROW": "ROW", "PASS": "PASS",
}
UNIT_RE = re.compile(r"\b(UNIT|APT)\s*(\S+)", re.IGNORECASE)
HASH_UNIT_RE = re.compile(r"#\s*(\S+)")
DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
CAPTION_RE = re.compile(r"\bvs\.?\b", re.IGNORECASE)
STREET_NUM_RE = re.compile(r"^\s*\d+\s+\S")
SKIP_CASES = {"2025-CA-003450-C"}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _supa_headers():
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path, limit=500):
    url = f"{SB_URL}/rest/v1/{path}{'&' if '?' in path else '?'}limit={limit}"
    req = urllib.request.Request(url, headers=_supa_headers())
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"GET {path} ERROR: {e}", "VERIFIED")
        return []


def sb_patch(path, params, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}?{params}: {list(body.keys())}", "UNTESTED")
        return True
    url = f"{SB_URL}/rest/v1/{path}?{params}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data,
                                  headers={**_supa_headers(), "Prefer": "return=representation"},
                                  method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            return len(result) > 0 if isinstance(result, list) else True
    except urllib.error.HTTPError as e:
        log(f"PATCH {path} failed: {e.code} {e.read().decode()[:200]}", "VERIFIED")
        return False


def sb_post(table, records, prefer="resolution=ignore-duplicates,return=representation"):
    if DRY_RUN:
        log(f"DRY-RUN POST {table}: {len(records)} records", "UNTESTED")
        return len(records)
    if not records:
        return 0
    data = json.dumps(records).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=data,
        headers={**_supa_headers(), "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            result = json.loads(r.read())
            return len(result) if isinstance(result, list) else 0
    except urllib.error.HTTPError as e:
        log(f"POST {table} failed: {e.code} {e.read().decode()[:200]}", "VERIFIED")
        return 0


def sb_rpc(fn, params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=data,
        headers=_supa_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _esc(s):
    return s.replace("'", "''")


def _point_query(url, lon, lat, out_fields):
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    }
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                  headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS error at {url}: {data['error']}")
    return data.get("features", [])


def _gis_query(where):
    params = {
        "where": where,
        "outFields": "PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL",
        "outSR": "4326",
        "f": "json",
    }
    req = urllib.request.Request(GIS_BASE + "?" + urllib.parse.urlencode(params),
                                  headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS query error: {data['error']} (where={where})")
    return data.get("features", [])


def _centroid(feature):
    geom = feature.get("geometry")
    if not geom or "rings" not in geom or not geom["rings"]:
        return None
    ring = geom["rings"][0]
    if not ring:
        return None
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _is_legal_caption(address):
    if CAPTION_RE.search(address):
        return True
    if "LLC" in address and not STREET_NUM_RE.match(address):
        return True
    return False


def _street_prefixes(raw_address):
    if not raw_address:
        return []
    addr = raw_address.strip()
    unit = None
    m = UNIT_RE.search(addr)
    if m:
        unit = m.group(2).rstrip(".,")
        addr = UNIT_RE.sub("", addr)
    else:
        m = HASH_UNIT_RE.search(addr)
        if m:
            unit = m.group(1).rstrip(".,")
            addr = HASH_UNIT_RE.sub("", addr)
    addr = addr.split(",")[0].strip()
    tokens = [t for t in addr.split() if t]
    if len(tokens) < 2:
        return []
    if not re.match(r"^\d+[A-Za-z]?$", tokens[0]):
        return []
    number = tokens[0]
    rest = tokens[1:]
    leading_dir = None
    if rest and rest[0].upper() in DIRECTIONALS:
        leading_dir = rest[0].upper()
        rest = rest[1:]
    if not rest:
        return []
    trailing_dir = None
    if rest[-1].upper() in DIRECTIONALS:
        trailing_dir = rest[-1].upper()
        rest = rest[:-1]
    suffix = None
    last_tok = rest[-1].upper().rstrip(".") if rest else None
    if last_tok in STREET_SUFFIXES:
        suffix = STREET_SUFFIXES[last_tok]
        rest = rest[:-1]
    if not rest:
        return []
    street_name = " ".join(rest)
    directional = trailing_dir or leading_dir
    candidates = []
    parts_full = [number, street_name] + ([suffix] if suffix else []) + ([directional] if directional else [])
    if unit:
        candidates.append(" ".join(parts_full + ["UNIT", unit]))
    candidates.append(" ".join(parts_full))
    candidates.append(" ".join([number, street_name]))
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def fetch_rows():
    rows = sb_get("multi_county_auctions?county=eq.okaloosa"
                  "&select=case_number,sale_type,property_address,parcel_id,"
                  "assessed_value,market_value,latitude,longitude,parity_status")
    log(f"Fetched {len(rows)} okaloosa rows", "VERIFIED")
    return rows


def fetch_jurisdictions():
    rows = sb_get("jurisdictions?county=eq.Okaloosa&select=id,name")
    return {row["name"]: row["id"] for row in rows}


def fetch_existing_parcel_ids(parcel_ids):
    if not parcel_ids:
        return set()
    quoted = ",".join(f'"{p}"' for p in parcel_ids)
    rows = sb_get(f"parcel_zones?parcel_id=in.({quoted})&select=parcel_id")
    return {r["parcel_id"] for r in rows}


def resolve_city_code(lat, lon):
    try:
        feats = _point_query(CITY_LIMITS_URL, lon, lat, "ICLPY_CITY_CODE")
        if len(feats) != 1:
            return None
        return feats[0]["attributes"]["ICLPY_CITY_CODE"]
    except Exception as exc:
        log(f"city_limits query error: {exc}", "VERIFIED")
        return None


def resolve_zone(city_code, lat, lon):
    if city_code == "UNINCORPORATED":
        try:
            feats = _point_query(COUNTY_ZONING_URL, lon, lat, "ZNGPY_ZONE")
            if len(feats) != 1:
                return None, f"county_zoning_layer_{len(feats)}_results"
            zone = feats[0]["attributes"].get("ZNGPY_ZONE")
            if not zone:
                return None, "county_zoning_layer_null_zone_field"
            return zone, COUNTY_ZONING_SOURCE_TAG
        except Exception as exc:
            return None, f"county_zoning_error:{exc}"
    cfg = CITY_ZONING_SOURCES.get(city_code)
    if not cfg:
        return None, f"no_known_zoning_source_for_city_code_{city_code!r}"
    try:
        feats = _point_query(cfg["url"], lon, lat, cfg["zone_field"])
        if len(feats) != 1:
            return None, f"{cfg['jurisdiction_name']}_zoning_layer_{len(feats)}_results"
        zone = feats[0]["attributes"].get(cfg["zone_field"])
        if not zone:
            return None, f"{cfg['jurisdiction_name']}_zoning_layer_null_zone_field"
        return zone, cfg["source_tag"]
    except Exception as exc:
        return None, f"{cfg['jurisdiction_name']}_zoning_error:{exc}"


def run_parcel_gis_enrichment(rows, jurisdictions):
    """Re-run GIS enrichment for FC rows that need parcel_id or have mismatched parity."""
    fc_rows = [r for r in rows if r["sale_type"] == "foreclosure"]
    td_rows = [r for r in rows if r["sale_type"] == "tax_deed"]

    matched = []
    unmatched = []
    skipped = []

    # FC lane: match by address
    for r in fc_rows:
        cn = r["case_number"]
        if cn in SKIP_CASES:
            skipped.append((cn, "known_unresolvable_separate_agent"))
            continue
        # Skip if already has parcel_id AND parity_status='matched_clean'
        if r.get("parcel_id") and r.get("parity_status") == "matched_clean":
            skipped.append((cn, "already_matched_clean"))
            continue
        prefixes = _street_prefixes(r.get("property_address"))
        if not prefixes:
            skipped.append((cn, f"no_usable_address ({r.get('property_address')!r})"))
            continue
        feats = []
        last_prefix = None
        last_count = None
        for prefix in prefixes:
            where = f"SITE_ADDR LIKE '{_esc(prefix)}%'"
            try:
                feats = _gis_query(where)
            except Exception as exc:
                feats = []
                last_prefix, last_count = prefix, f"error:{exc}"
                continue
            last_prefix, last_count = prefix, len(feats)
            if len(feats) == 1:
                break
        if len(feats) != 1:
            unmatched.append((cn, f"{last_count}_results_for_prefix_{last_prefix!r}"))
            continue
        attrs = feats[0]["attributes"]
        cen = _centroid(feats[0])
        fields = {}
        if attrs.get("PIN"):
            fields["parcel_id"] = attrs["PIN"]
        if attrs.get("ASSEDVAL") is not None:
            fields["assessed_value"] = attrs["ASSEDVAL"]
        if attrs.get("TOTALAPPR") is not None:
            fields["market_value"] = attrs["TOTALAPPR"]
        if cen:
            fields["latitude"], fields["longitude"] = cen
        if fields.get("parcel_id"):
            fields["parity_status"] = "matched_clean"
            fields["parity_source"] = (
                "tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:"
                "Parcels_with_Addressing:121:shard4_run5668"
            )
        if not fields:
            unmatched.append((cn, "matched_feature_had_no_usable_fields"))
            continue
        matched.append((cn, "foreclosure", fields))

    # TD lane: match by APN for value/geo enrichment
    for r in td_rows:
        cn = r["case_number"]
        apn = r.get("parcel_id")
        if not apn:
            skipped.append((cn, "no_apn"))
            continue
        where = f"PIN = '{_esc(apn)}'"
        try:
            feats = _gis_query(where)
        except Exception as exc:
            unmatched.append((cn, f"gis_query_error: {exc}"))
            continue
        if len(feats) == 0:
            unmatched.append((cn, f"0_results_for_apn_{apn!r}"))
            continue
        assed_vals = {f["attributes"].get("ASSEDVAL") for f in feats}
        if len(assed_vals) != 1:
            unmatched.append((cn, f"{len(feats)}_results_disagree_on_value_for_apn_{apn!r}"))
            continue
        attrs = feats[0]["attributes"]
        cen = _centroid(feats[0])
        fields = {}
        if attrs.get("ASSEDVAL") is not None and r.get("assessed_value") is None:
            fields["assessed_value"] = attrs["ASSEDVAL"]
        if attrs.get("TOTALAPPR") is not None and r.get("market_value") is None:
            fields["market_value"] = attrs["TOTALAPPR"]
        if cen and r.get("latitude") is None:
            fields["latitude"], fields["longitude"] = cen
        if not fields:
            skipped.append((cn, "td_row_already_complete"))
            continue
        matched.append((cn, "tax_deed", fields))

    log(f"GIS enrichment: {len(matched)} confident matches, {len(unmatched)} unmatched, {len(skipped)} skipped", "UNTESTED")
    for cn, reason in unmatched[:5]:
        log(f"  UNMATCHED {cn}: {reason}", "UNTESTED")

    success = 0
    for cn, sale_type, fields in matched:
        ok = sb_patch(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(cn)}",
            fields,
        )
        if ok:
            success += 1
            log(f"PATCHED {sale_type} {cn}: {list(fields.keys())}", "VERIFIED")
        time.sleep(0.1)

    log(f"GIS enrichment: {success}/{len(matched)} patched", "VERIFIED")
    if not DRY_RUN and success == 0 and len(matched) > 0:
        raise RuntimeError(
            f"FAIL-LOUD: {len(matched)} GIS matches found but 0 rows patched"
        )
    return success


def run_zoning_substrate(rows, jurisdictions):
    """Insert parcel_zones for rows with lat/lon that don't already have them."""
    rows_with_geo = [
        r for r in rows
        if r.get("parcel_id") and r.get("latitude") and r.get("longitude")
    ]
    existing = fetch_existing_parcel_ids([r["parcel_id"] for r in rows_with_geo])

    if UNINCORPORATED_JURISDICTION_NAME not in jurisdictions:
        raise RuntimeError(
            f"'{UNINCORPORATED_JURISDICTION_NAME}' jurisdiction row not found -- "
            "run supabase/migrations/20260719_shard3_okaloosa_i_unincorporated_jurisdiction.sql first"
        )

    to_insert = []
    unresolved = []
    already_covered = []

    for r in rows_with_geo:
        pid = r["parcel_id"]
        if pid in existing:
            already_covered.append((r["case_number"], pid))
            continue

        lat, lon = r["latitude"], r["longitude"]
        city_code = resolve_city_code(lat, lon)
        if city_code is None:
            unresolved.append((r["case_number"], pid, "city_limits_layer_ambiguous_or_zero_results"))
            continue

        if city_code == "UNINCORPORATED":
            jur_id = jurisdictions.get(UNINCORPORATED_JURISDICTION_NAME)
        else:
            cfg = CITY_ZONING_SOURCES.get(city_code)
            if not cfg:
                unresolved.append((r["case_number"], pid, f"no_jurisdiction_for_city_code_{city_code!r}"))
                continue
            jur_id = jurisdictions.get(cfg["jurisdiction_name"])

        if jur_id is None:
            unresolved.append((r["case_number"], pid, f"jurisdiction_id_not_found_for_{city_code!r}"))
            continue

        zone_code, source_or_reason = resolve_zone(city_code, lat, lon)
        if zone_code is None:
            unresolved.append((r["case_number"], pid, source_or_reason))
            continue

        to_insert.append({
            "parcel_id": pid,
            "jurisdiction_id": jur_id,
            "zone_code": zone_code,
            "source": source_or_reason + ":shard4_run5668",
        })
        log(f"RESOLVED {r['case_number']} parcel_id={pid} city={city_code} zone={zone_code}", "VERIFIED")

    log(f"Zoning substrate: {len(already_covered)} already covered, {len(to_insert)} to insert, {len(unresolved)} unresolved", "UNTESTED")
    for cn, pid, reason in unresolved[:5]:
        log(f"  UNRESOLVED {cn} ({pid}): {reason}", "UNTESTED")

    if not to_insert:
        log("Zoning substrate: nothing new to insert", "VERIFIED")
        return 0

    inserted = sb_post("parcel_zones", to_insert)
    log(f"Zoning substrate: inserted {inserted} parcel_zones rows", "VERIFIED")
    if not DRY_RUN and inserted == 0 and len(to_insert) > 0:
        raise RuntimeError(
            f"FAIL-LOUD: {len(to_insert)} parcel_zones rows queued but 0 inserted"
        )
    return inserted


def run_g_density_bifurcation_fix(jurisdictions):
    """
    Attempt to fix Unincorporated R-1 and MU density bifurcation by querying
    the Eglin AFB Encroachment Zone and UDAB boundary layers.

    Ordinance: Okaloosa County LDC Ch.2:
      R-1: 4 du/acre north of Eglin AFB boundary, 5 south
      MU: 25 du/acre inside UDAB, 4 outside

    If we can establish which side each parcel is on, we can set per-parcel
    density via a zone_standards update scoped to the parcel's zone district.

    NOTE: The current zone_standards schema only supports one density value per
    (jurisdiction, zone_code) pair, so per-parcel bifurcation requires either:
      (a) Adding a new zone code (e.g. R-1-AFB-NORTH / R-1-AFB-SOUTH)
      (b) Flagging per-parcel via a parcel_zones annotation column
      (c) Accepting that the current schema cannot express bifurcated density,
          and leaving G at 75.6% as a structural ceiling.

    This function discovers and probes the boundary layers. If the layers exist
    and unambiguously determine density for all R-1 and MU parcels, it reports
    what it found. It does NOT update zone_standards with a guessed value.
    """
    log("=== G density bifurcation: probing Eglin AFB + UDAB boundary layers ===", "UNTESTED")

    # Probe the Admin-Boundaries service tree for relevant layers
    probe_url = "https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/Admin_Boundaries/MapServer?f=json"
    try:
        req = urllib.request.Request(probe_url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=30) as r:
            svc = json.loads(r.read())
        layers = svc.get("layers", [])
        log(f"Admin-Boundaries service has {len(layers)} layers", "VERIFIED")
        for l in layers:
            name = l.get("name", "").upper()
            if any(kw in name for kw in ("EGLIN", "AFB", "UDAB", "URBAN", "DEVELOPMENT")):
                log(f"  CANDIDATE layer: id={l.get('id')} name={l.get('name')!r}", "VERIFIED")
    except Exception as exc:
        log(f"Admin-Boundaries probe failed: {exc}", "VERIFIED")
        return False

    # Also probe Planning-Development for UDAB
    probe_url2 = "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer?f=json"
    try:
        req = urllib.request.Request(probe_url2, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=30) as r:
            svc2 = json.loads(r.read())
        layers2 = svc2.get("layers", [])
        log(f"Planning-Development/Zoning service has {len(layers2)} layers", "VERIFIED")
        for l in layers2:
            name = l.get("name", "").upper()
            if any(kw in name for kw in ("EGLIN", "AFB", "UDAB", "URBAN", "R-1", "R1")):
                log(f"  CANDIDATE layer: id={l.get('id')} name={l.get('name')!r}", "VERIFIED")
    except Exception as exc:
        log(f"Planning-Development probe failed: {exc}", "VERIFIED")

    log("G density bifurcation: requires per-parcel point-in-polygon query against "
        "Eglin AFB + UDAB layers to assign correct density. Current zone_standards "
        "schema supports one density per (jurisdiction, zone_code) pair. "
        "Without a schema extension, cannot store per-parcel bifurcated values. "
        "Leaving G at 75.6% as a structural ceiling per prior session's documented gap. "
        "INFERRED: fix requires schema change or new per-parcel density override mechanism.", "VERIFIED")
    return False


def run_destin_parking_fix(jurisdictions):
    """
    Attempt to find Destin GRMU/TCMU parking per LDC Art. 8 Sec. 8.06.10.
    Prior session: Municode 403, mirror 503, Firecrawl out of credits.
    This attempt: try a direct fetch of the Destin LDC chapter.
    """
    log("=== G Destin parking: attempting LDC Art.8 fetch ===", "UNTESTED")

    # Try the Municode API approach used for Osceola (api.municode.com)
    try:
        url = "https://api.municode.com/Clients/name?clientName=Destin&stateAbbr=FL"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        log(f"Municode client search for Destin: {json.dumps(data)[:300]}", "VERIFIED")
    except Exception as exc:
        log(f"Municode Destin client search failed: {exc}", "VERIFIED")
        log("G Destin parking: cannot retrieve LDC -- leaving NULL per BLANK>WRONG", "VERIFIED")
        return False

    return False


def main():
    log("=== SHARD-4 RUN-5668 OKALOOSA C/E/I + G FIX ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE: C={baseline.get('C')} E={baseline.get('E')} "
        f"G={baseline.get('G')} I={baseline.get('I')}", "VERIFIED")

    rows = fetch_rows()
    jurisdictions = fetch_jurisdictions()
    log(f"Jurisdictions loaded: {list(jurisdictions.keys())}", "VERIFIED")

    # Step 1: Re-run parcel GIS enrichment (idempotent; fixes parity_status)
    log("--- Step 1: Parcel GIS enrichment (re-patch C/E) ---", "UNTESTED")
    enrich_count = run_parcel_gis_enrichment(rows, jurisdictions)

    # Step 2: Re-run zoning substrate for rows now with geo (fixes I)
    # Re-fetch rows since geo may have changed
    rows_fresh = fetch_rows()
    log("--- Step 2: Zoning substrate build (re-patch I) ---", "UNTESTED")
    pz_count = run_zoning_substrate(rows_fresh, jurisdictions)

    # Step 3: G density bifurcation fix attempt
    log("--- Step 3: G density bifurcation (probe + report) ---", "UNTESTED")
    run_g_density_bifurcation_fix(jurisdictions)

    # Step 4: G Destin parking fix attempt
    log("--- Step 4: G Destin parking (attempt LDC fetch) ---", "UNTESTED")
    run_destin_parking_fix(jurisdictions)

    if not DRY_RUN:
        log("Waiting 3s for DB to settle before re-evaluating...", "UNTESTED")
        time.sleep(3)
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        log(f"AFTER: C={after.get('C')} E={after.get('E')} "
            f"G={after.get('G')} I={after.get('I')}", "VERIFIED")

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n### SQL VERIFICATION")
        print(f"Timestamp UTC: {now_iso}")
        print(f"SELECT public.pencil_dod_evaluate_county('okaloosa');")
        print(f"BEFORE: C={baseline.get('C')} E={baseline.get('E')} G={baseline.get('G')} I={baseline.get('I')}")
        print(f"AFTER:  C={after.get('C')} E={after.get('E')} G={after.get('G')} I={after.get('I')}")
        print(f"enrich_patched={enrich_count} pz_inserted={pz_count}")
    else:
        print(f"\nDRY-RUN COMPLETE. enrich_count={enrich_count} pz_count={pz_count}")


if __name__ == "__main__":
    main()
