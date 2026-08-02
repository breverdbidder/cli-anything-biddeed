#!/usr/bin/env python3
"""
Okaloosa Post-Harvest Enrichment (2026-08-02, SHARD-5)
=======================================================
Runs after the daily Bid4Assets harvest to close C/D/E/I/J gaps for any
new rows added by the harvest. Combines three passes in sequence:

  PASS 1 — FC GIS Enrich: for FC rows with parcel_id IS NULL, run
    SITE_ADDR LIKE address-match against the county GIS parcel layer to
    backfill parcel_id + geo + value. Sets parity_status=matched_clean.
    This is the root cause of the C/D/E regression (was 96.5% PASS in July,
    dropped to 90.8% when 8 new FC rows arrived without parcel_id).

  PASS 2 — Zoning Substrate: for rows that now have parcel_id + lat/lon
    but no parcel_zones entry, resolve the city via Admin_Boundaries layer
    and look up the zone_code via the appropriate city GIS layer. Insert
    into parcel_zones. This advances letter I (card_complete requires a
    zone_code match via v_zoning_gold_standard_card).

  PASS 3 — bid_decisions Backfill: for rows without an existing
    bid_decisions entry (matched by case_number + county_slug), compute
    ARV/max_bid/ml_score/factors and insert. Advances letter J.

Each pass is idempotent: existing data is never overwritten. Fail-loud
invariant: if GIS matches are found but writes fail, the script raises.

GIS endpoints (confirmed live, no auth needed):
  Parcels: https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/
    Parcels_with_Addressing/MapServer/121/query
  City limits: https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/
    Admin_Boundaries/MapServer/99/query
  County zoning: https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/
    Zoning/MapServer/25/query (layer 25, confirmed moved from 28 this session)
  City zoning: per-city URLs in CITY_ZONING_SOURCES dict below.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success, 1 = fatal error
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "okaloosa"
PARITY_SOURCE = (
    "tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:"
    "Parcels_with_Addressing:121:shard5_okaloosa_post_harvest_enrich_20260802"
)
PIPELINE_VERSION = "shard5_okaloosa_post_harvest_enrich_20260802"

GIS_PARCEL_URL = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Land-Ownership/Parcels_with_Addressing/MapServer/121/query"
)
CITY_LIMITS_URL = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Admin-Boundaries/Admin_Boundaries/MapServer/99/query"
)
COUNTY_ZONING_URL = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Planning-Development/Zoning/MapServer/25/query"
)

CITY_ZONING_SOURCES: dict[str, dict] = {
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
UNINCORPORATED_JURIS_NAME = "Unincorporated Okaloosa County"

STALE_PLACEHOLDERS = {"2024-CA-000470", "2024-TDD-000089"}

STREET_SUFFIXES: dict[str, str] = {
    "ST": "ST", "STREET": "ST",
    "AVE": "AVE", "AVENUE": "AVE",
    "DR": "DR", "DRIVE": "DR",
    "RD": "RD", "ROAD": "RD",
    "LN": "LN", "LANE": "LN", "LANCE": "LN",
    "CT": "CT", "COURT": "CT",
    "CIR": "CIR", "CIRCLE": "CIR",
    "BLVD": "BLVD", "BOULEVARD": "BLVD",
    "WAY": "WAY",
    "TRL": "TRL", "TRAIL": "TRL",
    "PL": "PL", "PLACE": "PL",
    "TER": "TER", "TERRACE": "TER",
    "PKWY": "PKWY", "PARKWAY": "PKWY",
    "LOOP": "LOOP", "PATH": "PATH", "RUN": "RUN",
    "CV": "CV", "COVE": "CV",
    "PT": "PT", "POINT": "PT",
    "XING": "XING", "CROSSING": "XING",
    "WALK": "WALK", "ROW": "ROW", "PASS": "PASS",
}
DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
UNIT_RE = re.compile(r"\b(UNIT|APT)\s*(\S+)", re.IGNORECASE)
HASH_UNIT_RE = re.compile(r"#\s*(\S+)")

GIS_ARV_SOURCE = "okaloosa_pa_gis_value"
FORMULA_ARV_SOURCE = "formula_estimate_no_gis_match"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def _headers() -> dict:
    key = _req("SUPABASE_SERVICE_ROLE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def sb_get(path: str, limit: int = 500) -> list[dict]:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    sep = "&" if "?" in path else "?"
    url = f"{supa_url}/rest/v1/{path}{sep}limit={limit}"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_patch(table: str, params: str, body: dict) -> bool:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{supa_url}/rest/v1/{table}?{params}",
        data=data,
        headers={**_headers(), "Prefer": "return=representation"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            return len(result) > 0 if isinstance(result, list) else True
    except urllib.error.HTTPError as e:
        log(f"PATCH {table} failed: {e.code} {e.read().decode()[:200]}")
        return False


def sb_post(table: str, records: list[dict], prefer: str = "resolution=ignore-duplicates,return=representation") -> int:
    if not records:
        return 0
    supa_url = _req("SUPABASE_URL").rstrip("/")
    data = json.dumps(records).encode()
    req = urllib.request.Request(
        f"{supa_url}/rest/v1/{table}",
        data=data,
        headers={**_headers(), "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            return len(result) if isinstance(result, list) else 0
    except urllib.error.HTTPError as e:
        log(f"POST {table} failed: {e.code} {e.read().decode()[:200]}")
        return 0


def _gis_request(url: str, params: dict) -> list[dict]:
    req = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "curl/8"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS error: {data['error']} (url={url})")
    return data.get("features", [])


def _parcel_query(where: str) -> list[dict]:
    return _gis_request(GIS_PARCEL_URL, {
        "where": where,
        "outFields": "PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    })


def _point_query(url: str, lon: float, lat: float, out_fields: str) -> list[dict]:
    return _gis_request(url, {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    })


def _centroid(feature: dict) -> tuple[float, float] | None:
    geom = feature.get("geometry")
    if not geom or "rings" not in geom or not geom["rings"]:
        return None
    ring = geom["rings"][0]
    if not ring:
        return None
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _street_prefixes(raw_address: str) -> list[str]:
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
    if len(tokens) < 2 or not re.match(r"^\d+[A-Za-z]?$", tokens[0]):
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
    if last_tok and last_tok in STREET_SUFFIXES:
        suffix = STREET_SUFFIXES[last_tok]
        rest = rest[:-1]
    if not rest:
        return []

    street_name = " ".join(rest)
    directional = trailing_dir or leading_dir

    parts_full = [number, street_name] + ([suffix] if suffix else []) + ([directional] if directional else [])
    candidates = []
    if unit:
        candidates.append(" ".join(parts_full + ["UNIT", unit]))
    candidates.append(" ".join(parts_full))
    candidates.append(" ".join([number, street_name]))

    seen: set[str] = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _esc(s: str) -> str:
    return s.replace("'", "''")


def resolve_city_code(lat: float, lon: float) -> str | None:
    try:
        feats = _point_query(CITY_LIMITS_URL, lon, lat, "ICLPY_CITY_CODE")
    except Exception as exc:
        log(f"  city_limits query error: {exc}")
        return None
    if len(feats) == 1:
        return feats[0]["attributes"].get("ICLPY_CITY_CODE")
    return None


def resolve_zone(city_code: str, lat: float, lon: float) -> tuple[str | None, str]:
    if city_code == "UNINCORPORATED":
        try:
            feats = _point_query(COUNTY_ZONING_URL, lon, lat, "ZNGPY_ZONE")
        except Exception as exc:
            return None, f"county_zoning_error:{exc}"
        if not feats:
            return None, "county_zoning_0_results"
        zones = {f["attributes"].get("ZNGPY_ZONE") for f in feats}
        if len(zones) != 1:
            return None, f"county_zoning_{len(feats)}_results_disagreeing"
        zone = next(iter(zones))
        return (zone, f"okaloosa_gis:planning-development/zoning:25") if zone else (None, "county_zoning_null_zone_field")
    cfg = CITY_ZONING_SOURCES.get(city_code)
    if not cfg:
        return None, f"no_known_zoning_source_for_city_{city_code!r}"
    try:
        feats = _point_query(cfg["url"], lon, lat, cfg["zone_field"])
    except Exception as exc:
        return None, f"{cfg['jurisdiction_name']}_zoning_error:{exc}"
    if len(feats) != 1:
        return None, f"{cfg['jurisdiction_name']}_zoning_{len(feats)}_results"
    zone = feats[0]["attributes"].get(cfg["zone_field"])
    return (zone, cfg["source_tag"]) if zone else (None, f"{cfg['jurisdiction_name']}_zoning_null_field")


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pass1_fc_gis_enrich(rows: list[dict]) -> int:
    """Backfill parcel_id + geo + value for FC rows missing parcel_id."""
    targets = [
        r for r in rows
        if r["sale_type"] == "foreclosure"
        and not r.get("parcel_id")
        and r["case_number"] not in STALE_PLACEHOLDERS
    ]
    log(f"PASS1: {len(targets)} FC rows with parcel_id IS NULL (excl stale placeholders)")
    if not targets:
        return 0

    matched, unmatched, skipped = [], [], []
    for r in targets:
        cn = r["case_number"]
        prefixes = _street_prefixes(r.get("property_address") or "")
        if not prefixes:
            skipped.append((cn, f"no_usable_address:{r.get('property_address')!r}"))
            continue

        feats: list[dict] = []
        last_prefix = last_count = None
        for prefix in prefixes:
            try:
                feats = _parcel_query(f"SITE_ADDR LIKE '{_esc(prefix)}%'")
            except Exception as exc:
                feats = []
                last_prefix, last_count = prefix, f"error:{exc}"
                continue
            last_prefix, last_count = prefix, len(feats)
            if len(feats) == 1:
                break

        if len(feats) != 1:
            unmatched.append((cn, f"{last_count}_results_for_{last_prefix!r}_(tried_{len(prefixes)}_candidates)"))
            continue

        attrs = feats[0]["attributes"]
        cen = _centroid(feats[0])
        fields: dict = {}

        if attrs.get("PIN"):
            fields["parcel_id"] = attrs["PIN"]
            fields["parity_status"] = "matched_clean"
            fields["parity_source"] = PARITY_SOURCE
        if r.get("assessed_value") is None and attrs.get("ASSEDVAL") is not None:
            fields["assessed_value"] = attrs["ASSEDVAL"]
        if r.get("market_value") is None and attrs.get("TOTALAPPR") is not None:
            fields["market_value"] = attrs["TOTALAPPR"]
        if r.get("latitude") is None and cen:
            fields["latitude"], fields["longitude"] = cen

        if not fields:
            unmatched.append((cn, "matched_feature_had_no_usable_fields"))
            continue
        matched.append((cn, fields, attrs.get("SITE_ADDR"), attrs.get("PIN")))

    log(f"PASS1: {len(matched)} matches, {len(unmatched)} unmatched, {len(skipped)} no-address")
    for cn, reason in unmatched:
        log(f"  UNMATCHED {cn}: {reason}")
    for cn, reason in skipped:
        log(f"  SKIPPED {cn}: {reason}")

    success = 0
    for cn, fields, site_addr, pin in matched:
        ok = sb_patch(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(cn)}",
            fields,
        )
        if ok:
            success += 1
            log(f"  PATCHED {cn} -> pin={pin} site_addr={site_addr!r}: {list(fields.keys())}")
        else:
            log(f"  PATCH FAILED {cn}")
        time.sleep(0.05)

    if success == 0 and matched:
        raise RuntimeError(
            f"FAIL LOUD: {len(matched)} GIS matches found but 0 rows patched — write failure"
        )
    log(f"PASS1 done: {success}/{len(matched)} patched")
    return success


def pass2_zoning_substrate(rows: list[dict]) -> int:
    """Insert parcel_zones for rows with parcel_id + lat/lon but no existing zone entry."""
    rows_with_geo = [
        r for r in rows
        if r.get("parcel_id") and r.get("latitude") and r.get("longitude")
        and r["case_number"] not in STALE_PLACEHOLDERS
    ]
    if not rows_with_geo:
        log("PASS2: no rows with parcel_id + geo — nothing to zone")
        return 0

    parcel_ids = [r["parcel_id"] for r in rows_with_geo]
    quoted = ",".join(f'"{p}"' for p in parcel_ids)
    existing = {
        row["parcel_id"]
        for row in sb_get(f"parcel_zones?parcel_id=in.({quoted})&select=parcel_id")
    }
    log(f"PASS2: {len(rows_with_geo)} rows with geo, {len(existing)} already have parcel_zones")

    jurisdictions_list = sb_get("jurisdictions?county=eq.Okaloosa&select=id,name")
    jurisdictions: dict[str, str] = {r["name"]: r["id"] for r in jurisdictions_list}

    if UNINCORPORATED_JURIS_NAME not in jurisdictions:
        log(f"PASS2: WARNING '{UNINCORPORATED_JURIS_NAME}' not in jurisdictions table — unincorporated parcels will be skipped")

    city_to_juris: dict[str, str] = {
        "CRESTVIEW": "Crestview",
        "FORT WALTON BEACH": "Fort Walton Beach",
        "NICEVILLE": "Niceville",
        "DESTIN": "Destin",
        "UNINCORPORATED": UNINCORPORATED_JURIS_NAME,
    }

    to_insert: list[dict] = []
    unresolved: list[tuple] = []

    for r in rows_with_geo:
        pid = r["parcel_id"]
        if pid in existing:
            continue
        lat, lon = r["latitude"], r["longitude"]
        city_code = resolve_city_code(lat, lon)
        if city_code is None:
            unresolved.append((r["case_number"], pid, "city_limits_ambiguous"))
            continue
        jur_name = city_to_juris.get(city_code)
        if not jur_name or jur_name not in jurisdictions:
            unresolved.append((r["case_number"], pid, f"no_jurisdiction_for_city_{city_code!r}"))
            continue
        zone_code, source_or_reason = resolve_zone(city_code, lat, lon)
        if zone_code is None:
            unresolved.append((r["case_number"], pid, source_or_reason))
            continue
        to_insert.append({
            "parcel_id": pid,
            "jurisdiction_id": jurisdictions[jur_name],
            "zone_code": zone_code,
            "source": source_or_reason + ":shard5_post_harvest_enrich_20260802",
        })
        log(f"  ZONE RESOLVED {r['case_number']} pid={pid} city={city_code} zone={zone_code}")
        time.sleep(0.1)

    log(f"PASS2: {len(to_insert)} to insert, {len(unresolved)} unresolved")
    for cn, pid, reason in unresolved:
        log(f"  UNRESOLVED {cn} ({pid}): {reason}")

    if not to_insert:
        return 0
    inserted = sb_post("parcel_zones", to_insert)
    log(f"PASS2 done: inserted {inserted} parcel_zones rows")
    return inserted


def pass3_bid_decisions(rows: list[dict]) -> int:
    """Insert bid_decisions for any row not already covered by case_number."""
    existing_bds = {
        r["case_number"]
        for r in sb_get(f"bid_decisions?county_slug=eq.{COUNTY}&select=case_number&limit=1000")
        if r.get("case_number")
    }
    new_rows = [r for r in rows if r["case_number"] not in existing_bds]
    log(f"PASS3: {len(rows)} total auctions, {len(existing_bds)} already have bid_decisions, {len(new_rows)} new")
    if not new_rows:
        return 0

    market_values = [_to_float(r.get("market_value")) for r in rows]
    market_values = [v for v in market_values if v is not None]
    county_median = sorted(market_values)[len(market_values) // 2] if market_values else 200000.0
    log(f"PASS3: county median market_value = {county_median}")

    run_id = f"shard5-okaloosa-phe-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    payload = []
    for r in new_rows:
        cn = r["case_number"]
        sale_type = r.get("sale_type", "foreclosure")
        mv = _to_float(r.get("market_value"))
        av = _to_float(r.get("assessed_value"))
        if mv is None and av is None:
            arv, arv_source = round(county_median, 2), FORMULA_ARV_SOURCE
        else:
            arv = mv if mv is not None else av
            arv, arv_source = round(arv, 2), GIS_ARV_SOURCE
        repairs = round(arv * 0.13, 2)
        max_bid_raw = (arv * 0.70) - repairs - 10000 - min(25000, 0.15 * arv)
        max_bid = round(max(max_bid_raw, 0.0), 2)
        score = 0.5
        if sale_type == "tax_deed":
            score += 0.15
        if arv_source == GIS_ARV_SOURCE:
            score += 0.20
        if arv > 0:
            margin = max(0.0, min(0.70 - (max_bid / arv), 0.20))
            score += 0.15 * (margin / 0.20)
        ml_score = round(max(0.05, min(score, 0.95)), 4)
        has_addr = bool(r.get("property_address"))
        factors = {
            "distress_location": round(0.6 + (0.1 if has_addr else 0.0), 2),
            "distress_location_rationale": "0.6 base FL panhandle; +0.1 when property_address present",
            "distress_property": 0.65 if sale_type == "tax_deed" else 0.55,
            "distress_property_rationale": "Tax deed 0.65 (>=2yr unpaid taxes); foreclosure 0.55",
            "distress_owner": 0.5,
            "distress_owner_rationale": "0.5 flat — no owner-specific signal in dataset",
            "cma_distressed": round(arv * 0.80, 2),
            "cma_resale": round(arv * 1.00, 2),
        }
        payload.append({
            "pipeline_run_id": run_id,
            "case_number": cn,
            "parcel_id": r.get("parcel_id"),
            "address": r.get("property_address"),
            "auction_date": r.get("auction_date"),
            "arv": arv,
            "repairs": repairs,
            "repair_estimate": repairs,
            "final_judgment": None,
            "max_bid": max_bid,
            "bid_judgment_ratio": None,
            "recommendation": "BID" if max_bid > 0 else "SKIP",
            "confidence": ml_score,
            "ml_score": ml_score,
            "factors": factors,
            "county_slug": COUNTY,
            "triangle_score": ml_score,
            "pipeline_version": PIPELINE_VERSION,
            "arv_source": arv_source,
        })

    inserted = sb_post("bid_decisions", payload)
    log(f"PASS3 done: inserted {inserted}/{len(payload)} bid_decisions rows")
    return inserted


def main() -> int:
    log(f"=== Okaloosa post-harvest enrichment === county={COUNTY}")

    rows = sb_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=case_number,sale_type,property_address,parcel_id,"
        f"assessed_value,market_value,latitude,longitude,auction_date",
        limit=500,
    )
    log(f"Fetched {len(rows)} okaloosa auctions from DB")

    p1 = pass1_fc_gis_enrich(rows)
    log("")

    if p1 > 0:
        rows = sb_get(
            f"multi_county_auctions?county=eq.{COUNTY}"
            f"&select=case_number,sale_type,property_address,parcel_id,"
            f"assessed_value,market_value,latitude,longitude,auction_date",
            limit=500,
        )
        log(f"Re-fetched {len(rows)} rows after PASS1 GIS enrich")

    p2 = pass2_zoning_substrate(rows)
    log("")

    p3 = pass3_bid_decisions(rows)
    log("")

    log(
        f"=== DONE: PASS1={p1} FC rows linked, "
        f"PASS2={p2} parcel_zones inserted, "
        f"PASS3={p3} bid_decisions inserted ==="
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
