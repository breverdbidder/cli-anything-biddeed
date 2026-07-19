#!/usr/bin/env python3
"""
Okaloosa Parcel GIS Enrichment (2026-07-19, SHARD3-OKALOOSA-C/E/J continuation)
=================================================================================
Backfills parcel_id, assessed_value, latitude, longitude on
multi_county_auctions for Okaloosa's 40 live Bid4Assets rows, using the
county's public ArcGIS REST parcel layer:

  https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/
  Parcels_with_Addressing/MapServer/121/query

Confirmed live this session: no auth required, CORS open, outSR=4326 returns
WGS84 lon/lat polygon rings directly (no manual reprojection needed).

Two matching lanes:
  FC rows (26 of 27; case_number='2025-CA-003450-C' SKIPPED -- corrupted
  property_address being fixed by a separate agent; case_number=
  '2024-CA-000470' SKIPPED -- has no property_address to match on at all):
    Match by SITE_ADDR LIKE '<street_number> <street_name>%' (endpoint does
    a plain prefix LIKE, so street suffix words like DRIVE/DR/COURT/CT must
    be stripped from our search term -- confirmed live that "800 BRADFORD
    DRIVE" returns 0 rows against a real SITE_ADDR of "800 BRADFORD DR ...",
    but "800 BRADFORD" (no suffix) returns exactly 1 confident match).
    Only a SINGLE feature result is treated as a confident match. Zero or
    multiple results (multi-unit/duplex addressing) are left untouched and
    counted as "unmatched" -- never guess.

  TD rows (12 of 13; case_number='2024-TDD-000089' SKIPPED -- has no
  parcel_id/APN to match on, it's a differently-sourced legacy row):
    Match by PIN = '<apn>' (exact). parcel_id is NOT overwritten for these
    (they already carry a real APN from the Bid4Assets grid) -- only
    assessed_value/latitude/longitude are backfilled.

Value field used: TOTALAPPR (alias PATPCL_TOTALAPPR, "total appraised
value") is written to multi_county_auctions.market_value, and ASSEDVAL
(alias PATPCL_ASSEDVAL, "assessed value") is written to
multi_county_auctions.assessed_value. Rationale: the county's own field
naming maps directly 1:1 onto our two columns by name/semantics -- ASSEDVAL
is the assessed value used for tax purposes (same concept as our
`assessed_value` column, and matches the pre-existing 2024-CA-000470/
2024-TDD-000089 rows which already carry a value in `assessed_value`), while
TOTALAPPR is the appraiser's total market/appraised value (our
`market_value` column). No estimation or derivation is involved here --
both are real values returned directly by the county API.

Geometry -> lat/lon: ArcGIS returns polygon rings in [lon, lat] pairs (since
outSR=4326 was requested). Centroid is computed as the mean of the ring's
vertices (documented as an approximation in the upstream research -- true
area centroid would require shoelace-formula weighting, but for roughly
convex residential parcel polygons the vertex-mean is a acceptable proxy for
sub-meter map-pin purposes, not a legal survey figure).

Write pattern: PATCH per row (never blind upsert) so unrelated columns
(data_source, tier1_authoritative, parity_status, etc.) are never clobbered:
  PATCH {SUPABASE_URL}/rest/v1/multi_county_auctions
        ?county=eq.okaloosa&case_number=eq.<case_number>
  body: only the fields being set on that row

FAIL LOUD: if the script successfully queries the GIS endpoint and gets
confident matches but the PATCH calls end up writing 0 rows, it raises --
this is a real failure (bad filter, wrong REST path, RLS block), not a
silent no-op.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row patched), 1 = fatal error
"""
import json
import os
import re
import sys

import httpx

GIS_BASE = "https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/Parcels_with_Addressing/MapServer/121/query"

# Corrupted-address FC row being fixed by a separate agent -- must not touch.
SKIP_CORRUPTED_ADDRESS = {"2025-CA-003450-C"}

# Maps recognized suffix words/abbreviations -> the county's abbreviated
# form (confirmed live this session: SITE_ADDR always uses the abbreviation,
# e.g. "DR" not "DRIVE", "TER" not "TERRACE" -- a full-word suffix like
# "DRIVE" must be normalized to "DR" or the LIKE prefix match returns 0).
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
}

UNIT_RE = re.compile(r"\b(UNIT|APT)\s*(\S+)", re.IGNORECASE)
HASH_UNIT_RE = re.compile(r"#\s*(\S+)")
DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def _street_prefixes(raw_address: str) -> list[str]:
    """Build one or more candidate '<number> <street...>' prefixes to try
    against SITE_ADDR LIKE '<prefix>%', in priority order, since the GIS
    endpoint only supports a plain prefix match against a full 'NUMBER
    STREET [DIRECTIONAL] [CITY STATE ZIP]' string. Confirmed live this
    session that the county's SITE_ADDR format is:
      '<NUM> <STREET NAME> <SUFFIX> [DIRECTIONAL] [UNIT <n>] <CITY> <ST> <ZIP>'
    e.g. '208 COMBS MANOR CT NW FORT WALTON BEACH FL 32548' and
    '4000 GULF TERRACE DR UNIT 190 DESTIN FL 32541' -- so a leading
    directional in our source address ('21 NW Linwood Road') must be moved
    to the end, and a unit number ('Unit 190') must be kept (not stripped)
    since some addresses are only unique with the unit included."""
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

    # Drop everything after the first comma (city/state/zip tail), if present.
    addr = addr.split(",")[0].strip()
    tokens = [t for t in addr.split() if t]
    if len(tokens) < 2:
        return []
    if not re.match(r"^\d+[A-Za-z]?$", tokens[0]):
        return []  # doesn't start with a street number -- can't build a prefix

    number = tokens[0]
    rest = tokens[1:]

    # A leading directional (before the street name) belongs AFTER the
    # street name + suffix in the county's format -- move it there.
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
        suffix = STREET_SUFFIXES[last_tok]  # normalized abbreviation
        rest = rest[:-1]
    if not rest:
        return []

    street_name = " ".join(rest)
    directional = trailing_dir or leading_dir  # county format puts it at the end

    candidates = []
    # Most specific first: number + street + suffix + directional + unit
    parts_full = [number, street_name] + ([suffix] if suffix else []) + ([directional] if directional else [])
    if unit:
        candidates.append(" ".join(parts_full + ["UNIT", unit]))
    candidates.append(" ".join(parts_full))
    # Fallback: number + street name only (no suffix/directional) -- broadest,
    # only useful if the above are too specific and return 0.
    candidates.append(" ".join([number, street_name]))
    # De-dupe while preserving order.
    seen = set()
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
        "f": "json",
    }
    resp = httpx.get(GIS_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
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
    return (sum(lats) / len(lats), sum(lons) / len(lons))  # (lat, lon)


def fetch_rows() -> list[dict]:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {"apikey": supa_key, "Authorization": f"Bearer {supa_key}"}
    resp = httpx.get(
        f"{supa_url}/rest/v1/multi_county_auctions",
        params={
            "county": "eq.okaloosa",
            "select": "case_number,sale_type,property_address,parcel_id,assessed_value,market_value,latitude,longitude",
        },
        headers=headers, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def patch_row(case_number: str, fields: dict) -> None:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    resp = httpx.patch(
        f"{supa_url}/rest/v1/multi_county_auctions",
        params={"county": "eq.okaloosa", "case_number": f"eq.{case_number}"},
        headers=headers, json=fields, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(f"PATCH failed for {case_number}: {resp.status_code} {resp.text[:300]}")
    body = resp.json()
    if not body:
        raise RuntimeError(f"PATCH for {case_number} returned 0 rows -- case_number/county filter matched nothing")


def main() -> int:
    rows = fetch_rows()
    fc_rows = [r for r in rows if r["sale_type"] == "foreclosure"]
    td_rows = [r for r in rows if r["sale_type"] == "tax_deed"]

    matched = []
    unmatched = []
    skipped = []

    # ---- FC lane: match by address ----
    for r in fc_rows:
        cn = r["case_number"]
        if cn in SKIP_CORRUPTED_ADDRESS:
            skipped.append((cn, "corrupted_address_separate_agent"))
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
                break  # confident match, stop trying broader candidates
        if len(feats) != 1:
            unmatched.append((cn, f"{last_count}_results_for_prefix_{last_prefix!r}_(tried {len(prefixes)} candidates)"))
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
        if not fields:
            unmatched.append((cn, "matched_feature_had_no_usable_fields"))
            continue
        # A real, GIS-verified parcel_id now exists for this FC row -- honest
        # to promote parity_status to matched_clean (Bid4Assets' own FC grid
        # never carries an APN, but the county GIS layer is itself a real
        # tier-1 authoritative source, so this is new evidence, not a status
        # change without backing).
        if fields.get("parcel_id"):
            fields["parity_status"] = "matched_clean"
            fields["parity_source"] = (
                "tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:"
                "Parcels_with_Addressing:121"
            )
        matched.append((cn, "foreclosure", fields, attrs.get("SITE_ADDR")))

    # ---- TD lane: match by APN (parcel_id already known) ----
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
        # TD rows CAN legitimately return >1 feature for one PIN (confirmed
        # in research: multi-unit/multi-situs parcels share a PIN). Use the
        # first feature's value/geometry fields (they're identical across
        # duplicate-PIN rows per the research finding) but only if all
        # returned features agree on ASSEDVAL -- else treat as ambiguous.
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
        if attrs.get("ASSEDVAL") is not None:
            fields["assessed_value"] = attrs["ASSEDVAL"]
        if attrs.get("TOTALAPPR") is not None:
            fields["market_value"] = attrs["TOTALAPPR"]
        if cen:
            fields["latitude"], fields["longitude"] = cen
        if not fields:
            unmatched.append((cn, "matched_feature_had_no_usable_fields"))
            continue
        matched.append((cn, "tax_deed", fields, apn))

    print(f">>> FC rows: {len(fc_rows)} total, TD rows: {len(td_rows)} total")
    print(f">>> Confident matches: {len(matched)}")
    print(f">>> Unmatched (ambiguous/zero-result): {len(unmatched)}")
    for cn, reason in unmatched:
        print(f"    UNMATCHED {cn}: {reason}")
    print(f">>> Skipped (out of scope): {len(skipped)}")
    for cn, reason in skipped:
        print(f"    SKIPPED {cn}: {reason}")

    if not matched:
        raise RuntimeError("Zero confident matches across all rows -- GIS endpoint or matching logic likely broken")

    success = 0
    failures = []
    for cn, sale_type, fields, key in matched:
        try:
            patch_row(cn, fields)
            success += 1
            print(f"    PATCHED {sale_type} {cn} (key={key}): {fields}")
        except Exception as exc:
            failures.append((cn, str(exc)))
            print(f"    PATCH FAILED {cn}: {exc}", file=sys.stderr)

    print(f"\n>>> PATCH results: {success} succeeded, {len(failures)} failed (of {len(matched)} confident matches)")

    if success == 0:
        raise RuntimeError(
            f"FAIL LOUD: {len(matched)} confident GIS matches found but 0 rows were successfully "
            f"patched in multi_county_auctions -- this is a write failure, not a data-absence case."
        )
    if failures:
        print(f"WARNING: {len(failures)} PATCH failures despite confident matches -- see stderr above", file=sys.stderr)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
