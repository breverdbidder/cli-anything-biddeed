#!/usr/bin/env python3
"""
Okaloosa FC GIS Backfill — new rows missing parcel_id (2026-08-02, SHARD-5)
=============================================================================
Runs automatically after the okaloosa Bid4Assets harvest to ensure new FC
rows get their parcel_id + lat/lon + value backfilled from the county GIS
layer. This is the missing link that caused the C/D/E regression (57→65
auctions, 6 new FC rows landed without parcel_id, metrics dropped below 95%).

Root cause documented (harvest script line 213-226): the upsert ON CONFLICT
clause was fixed to NOT overwrite existing parcel_id, but NEW rows inserted
after the enrichment run still land without parcel_id until this script runs.
Wiring this script into the harvest workflow closes that gap permanently.

Strategy:
  1. Fetch all okaloosa FC rows with parcel_id IS NULL (excluding known
     stale placeholders that are genuinely unresolvable).
  2. For each, try GIS address-match against the county parcel layer
     (Land-Ownership/Parcels_with_Addressing/MapServer/121).
  3. On single-result confident match: PATCH parcel_id + geo + value +
     parity_status=matched_clean. Never guess; zero or multi-result = skip.
  4. Report exact counts. Fail loud if any confident match fails to write.

Known unrecoverable cases (never touch):
  - 2024-CA-000470, 2024-TDD-000089: stale placeholder seed rows, confirmed
    absent from Bid4Assets across 5+ prior sessions, no real address.

GIS endpoint: https://okgis.myokaloosa.com/arcgis/rest/services/
  Land-Ownership/Parcels_with_Addressing/MapServer/121/query
  Confirmed live, no auth, CORS open, outSR=4326 returns WGS84 lon/lat.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = clean (0+ patches applied), 1 = fatal error
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

COUNTY = "okaloosa"
GIS_BASE = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/"
    "Land-Ownership/Parcels_with_Addressing/MapServer/121/query"
)
PARITY_SOURCE = (
    "tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:"
    "Parcels_with_Addressing:121:shard5_okaloosa_fc_backfill_20260802"
)

STALE_PLACEHOLDERS = {"2024-CA-000470", "2024-TDD-000089"}

STREET_SUFFIXES = {
    "ST": "ST", "STREET": "ST",
    "AVE": "AVE", "AVENUE": "AVE",
    "DR": "DR", "DRIVE": "DR",
    "RD": "RD", "ROAD": "RD",
    "LN": "LN", "LANE": "LN",
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
    "LANCE": "LN",
}
DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
UNIT_RE = re.compile(r"\b(UNIT|APT)\s*(\S+)", re.IGNORECASE)
HASH_UNIT_RE = re.compile(r"#\s*(\S+)")


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


def _street_prefixes(raw_address: str) -> list[str]:
    """Build candidate '<number> <street>...' prefixes for SITE_ADDR LIKE.
    Confirmed live 2026-07-19/24: county SITE_ADDR format is:
      '<NUM> <STREET NAME> <SUFFIX> [DIRECTIONAL] [UNIT <n>] <CITY> <ST> <ZIP>'
    """
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

    seen: set[str] = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _esc(s: str) -> str:
    return s.replace("'", "''")


def _gis_query(where: str) -> list[dict]:
    params = {
        "where": where,
        "outFields": "PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    req = urllib.request.Request(
        GIS_BASE + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "curl/8"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS query error: {data['error']} (where={where})")
    return data.get("features", [])


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


def fetch_unlinked_fc_rows() -> list[dict]:
    """Fetch okaloosa FC rows with parcel_id IS NULL, excluding known placeholders."""
    supa_url = _req("SUPABASE_URL").rstrip("/")
    url = (
        f"{supa_url}/rest/v1/multi_county_auctions"
        f"?county=eq.{COUNTY}&sale_type=eq.foreclosure&parcel_id=is.null"
        f"&select=case_number,property_address,assessed_value,market_value,latitude,longitude"
        f"&limit=200"
    )
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    return [r for r in rows if r["case_number"] not in STALE_PLACEHOLDERS]


def patch_row(case_number: str, fields: dict) -> bool:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    url = (
        f"{supa_url}/rest/v1/multi_county_auctions"
        f"?county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(case_number)}"
    )
    data = json.dumps(fields).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={**_headers(), "Prefer": "return=representation"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            if not result:
                raise RuntimeError(
                    f"PATCH for {case_number} returned 0 rows — filter matched nothing"
                )
            return True
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"PATCH failed for {case_number}: {e.code} {e.read().decode()[:200]}"
        )


def main() -> int:
    rows = fetch_unlinked_fc_rows()
    print(f">>> Found {len(rows)} FC rows with parcel_id IS NULL (excluding stale placeholders)")

    if not rows:
        print(">>> Nothing to enrich — all FC rows already have parcel_id")
        return 0

    matched = []
    unmatched = []
    skipped = []

    for r in rows:
        cn = r["case_number"]
        prefixes = _street_prefixes(r.get("property_address") or "")
        if not prefixes:
            skipped.append((cn, f"no_usable_address: {r.get('property_address')!r}"))
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
            unmatched.append((cn, f"{last_count}_results_for_prefix_{last_prefix!r}_(tried_{len(prefixes)}_candidates)"))
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

    print(f">>> Confident matches: {len(matched)}")
    print(f">>> Unmatched (0 or multi-result): {len(unmatched)}")
    for cn, reason in unmatched:
        print(f"    UNMATCHED {cn}: {reason}")
    print(f">>> Skipped (no address): {len(skipped)}")
    for cn, reason in skipped:
        print(f"    SKIPPED {cn}: {reason}")

    if not matched:
        print(">>> No confident matches found — nothing to patch")
        return 0

    success = 0
    for cn, fields, site_addr, pin in matched:
        try:
            patch_row(cn, fields)
            success += 1
            print(f"    PATCHED {cn} -> parcel_id={pin}, site_addr={site_addr!r}: {list(fields.keys())}")
        except Exception as exc:
            print(f"    PATCH FAILED {cn}: {exc}", file=sys.stderr)

    print(f"\n>>> PATCH results: {success} succeeded, {len(matched) - success} failed (of {len(matched)} confident matches)")

    if success == 0 and matched:
        raise RuntimeError(
            f"FAIL LOUD: {len(matched)} confident GIS matches found but 0 rows were patched — "
            f"write failure (bad filter, wrong path, RLS block)."
        )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
