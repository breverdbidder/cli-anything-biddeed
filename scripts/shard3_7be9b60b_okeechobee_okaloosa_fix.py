#!/usr/bin/env python3
"""
Gold Standard SHARD-3, dispatch 7be9b60b-f0fa-46e5-8890-af8cb0499ce4.
Counties: okeechobee (letter I), okaloosa (letters C/D/E/I)
Date: 2026-08-12

HONESTY MARKERS:
- fl_parcels backfill: VERIFIED pattern (reused from okaloosa/miami_dade I fixes)
- DOR_UC zone crosswalk: INFERRED (not GIS point-in-polygon verified)
- PA card fetch: VERIFIED when parcel found on okeechobeepa.com

ROOT CAUSES (VERIFIED from code analysis):
- okeechobee I (78/84): New rows since session 3 (54→84 denominator) lack
  parcel_zone entries. Using fl_parcels DOR_UC crosswalk + PA card endpoint.
- okaloosa C/D/E/I (67/71): 2 new FC rows added by daily harvest lack parcel_id
  (GIS enrichment script not scheduled after harvest). FC rows can't be backfilled
  via fl_parcels without a parcel_id; need GIS API call. TD rows can be backfilled
  from fl_parcels via APN.

APPROACH:
1. Apply SQL migration for okeechobee (fl_parcels address/value backfill + parcel_zones)
2. Apply SQL migration for okaloosa (fl_parcels TD backfill + parity promotion)
3. Run okaloosa GIS enrichment for FC rows with address but no parcel_id
4. Log results to Supabase gold_standard_campaign

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import os
import sys
import json
import httpx
import re

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
                or os.environ.get("SUPABASE_KEY", ""))

BASE = f"{SUPABASE_URL}/rest/v1"
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

OKALOOSA_GIS_URL = (
    "https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/"
    "Parcels_with_Addressing/MapServer/121/query"
)

STREET_SUFFIXES = {
    "ST": "ST", "STREET": "ST",
    "AVE": "AVE", "AVENUE": "AVE",
    "DR": "DR", "DRIVE": "DR",
    "RD": "RD", "ROAD": "RD",
    "LN": "LN", "LANE": "LN",
    "CT": "CT", "COURT": "CT",
    "CIR": "CIR", "CIRCLE": "CIR",
    "BLVD": "BLVD", "BOULEVARD": "BLVD",
    "WAY": "WAY", "TRL": "TRL", "TRAIL": "TRL",
    "PL": "PL", "PLACE": "PL",
    "TER": "TER", "TERRACE": "TER",
    "PKWY": "PKWY", "PARKWAY": "PKWY",
    "LOOP": "LOOP", "PATH": "PATH",
}
DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
UNIT_RE = re.compile(r"\b(UNIT|APT)\s*(\S+)", re.IGNORECASE)
HASH_UNIT_RE = re.compile(r"#\s*(\S+)")
CAPTION_RE = re.compile(r"\bvs\.?\b", re.IGNORECASE)
STREET_NUM_RE = re.compile(r"^\s*\d+\s+\S")


def headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def mgmt_sql(query: str, token: str = None) -> dict:
    """Run SQL via Supabase Management API (requires SUPABASE_ACCESS_TOKEN)."""
    tok = token or os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not tok:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN required for mgmt_sql")
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    r = httpx.post(MGMT_URL, headers=h, json={"query": query}, timeout=120)
    return {"status": r.status_code, "body": r.json() if r.text else {}}


def rest_get(table: str, params: dict) -> list:
    r = httpx.get(f"{BASE}/{table}", params=params, headers=headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def rest_patch(table: str, params: dict, body: dict) -> int:
    h = {**headers(), "Prefer": "return=representation"}
    r = httpx.patch(f"{BASE}/{table}", params=params, headers=h, json=body, timeout=30)
    if not (200 <= r.status_code < 300):
        raise RuntimeError(f"PATCH {table} failed {r.status_code}: {r.text[:300]}")
    return len(r.json()) if r.text else 0


def rest_post(table: str, body: dict, on_conflict: str = None) -> dict:
    h = {**headers()}
    if on_conflict:
        h["Prefer"] = f"resolution=merge-duplicates,return=representation"
    r = httpx.post(
        f"{BASE}/{table}" + (f"?on_conflict={on_conflict}" if on_conflict else ""),
        headers=h, json=body, timeout=30
    )
    if not (200 <= r.status_code < 300):
        raise RuntimeError(f"POST {table} failed {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else {}


def rpc_call(func: str, params: dict) -> dict:
    r = httpx.post(
        f"{BASE}/rpc/{func}", headers=headers(), json=params, timeout=60
    )
    r.raise_for_status()
    return r.json()


def _is_legal_caption(address: str) -> bool:
    if CAPTION_RE.search(address):
        return True
    if "LLC" in address and not STREET_NUM_RE.match(address):
        return True
    return False


def _street_prefixes(raw_address: str) -> list:
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
            out.append(c.upper())
    return out


def _esc(s: str) -> str:
    return s.replace("'", "''")


def gis_query_okaloosa(where: str) -> list:
    params = {
        "where": where,
        "outFields": "PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    r = httpx.get(OKALOOSA_GIS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"GIS error: {data['error']}")
    return data.get("features", [])


def centroid(feature: dict):
    geom = feature.get("geometry")
    if not geom or "rings" not in geom or not geom["rings"]:
        return None
    ring = geom["rings"][0]
    if not ring:
        return None
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def fix_okaloosa_fc_parcel_linkage() -> dict:
    """
    Enrich okaloosa FC rows that have property_address but lack parcel_id.
    Uses the Okaloosa GIS ArcGIS endpoint (same as okaloosa_parcel_gis_enrich.py).
    """
    rows = rest_get("multi_county_auctions", {
        "county": "eq.okaloosa",
        "sale_type": "eq.foreclosure",
        "parcel_id": "is.null",
        "property_address": "not.is.null",
        "select": "case_number,property_address,parcel_id,assessed_value",
    })

    print(f"okaloosa FC rows lacking parcel_id: {len(rows)}")
    matched = []
    unmatched = []

    for r in rows:
        cn = r["case_number"]
        addr = r.get("property_address", "")
        if not addr or _is_legal_caption(addr):
            unmatched.append((cn, f"no_usable_address: {addr!r}"))
            continue

        prefixes = _street_prefixes(addr)
        if not prefixes:
            unmatched.append((cn, f"no_prefix: {addr!r}"))
            continue

        feats = []
        last_info = None
        for prefix in prefixes:
            where = f"SITE_ADDR LIKE '{_esc(prefix)}%'"
            try:
                feats = gis_query_okaloosa(where)
            except Exception as exc:
                last_info = f"error:{exc}"
                feats = []
                continue
            last_info = f"{len(feats)}_results_for_{prefix!r}"
            if len(feats) == 1:
                break

        if len(feats) != 1:
            unmatched.append((cn, last_info))
            continue

        attrs = feats[0]["attributes"]
        cen = centroid(feats[0])
        fields = {}
        if attrs.get("PIN"):
            fields["parcel_id"] = attrs["PIN"]
            fields["parity_status"] = "matched_clean"
            fields["parity_source"] = (
                "tier1:okaloosa_gis_arcgis_pin_match:okgis.myokaloosa.com:"
                "Parcels_with_Addressing:121:shard3_7be9b60b"
            )
        if attrs.get("ASSEDVAL") is not None:
            fields["assessed_value"] = attrs["ASSEDVAL"]
        if attrs.get("TOTALAPPR") is not None:
            fields["market_value"] = attrs["TOTALAPPR"]
        if cen:
            fields["latitude"], fields["longitude"] = cen

        if not fields.get("parcel_id"):
            unmatched.append((cn, "GIS_match_had_no_PIN"))
            continue

        try:
            n = rest_patch("multi_county_auctions",
                           {"county": "eq.okaloosa", "case_number": f"eq.{cn}"},
                           fields)
            matched.append((cn, fields.get("parcel_id")))
            print(f"  PATCHED {cn}: parcel_id={fields.get('parcel_id')}")
        except Exception as exc:
            unmatched.append((cn, f"patch_failed:{exc}"))

    return {"matched": len(matched), "unmatched": len(unmatched), "unmatched_detail": unmatched}


def fix_okaloosa_property_address_backfill() -> dict:
    """
    Backfill property_address for okaloosa rows that now have parcel_id
    (from GIS enrichment above) but still lack property_address.
    Also covers TD rows that have APN but no address.
    Uses fl_parcels (co_no=56).
    """
    rows = rest_get("multi_county_auctions", {
        "county": "eq.okaloosa",
        "property_address": "is.null",
        "parcel_id": "not.is.null",
        "select": "case_number,parcel_id,sale_type",
    })
    print(f"okaloosa rows with parcel_id but no address: {len(rows)}")
    patched = 0
    for r in rows:
        cn = r["case_number"]
        pid = r["parcel_id"]
        if not pid:
            continue
        normalized = re.sub(r'[^0-9A-Za-z]', '', pid)
        fp_rows = rest_get("fl_parcels", {
            "co_no": "eq.56",
            "parcel_id": f"eq.{normalized}",
            "phy_addr1": "not.is.null",
            "select": "phy_addr1,phy_city,phy_zipcd,tv_sd,jv",
        })
        if not fp_rows:
            continue
        fp = fp_rows[0]
        fields = {}
        if fp.get("phy_addr1"):
            fields["property_address"] = (
                f"{fp['phy_addr1']}, {fp.get('phy_city','')}, FL {fp.get('phy_zipcd','')}"
            )
        if fp.get("tv_sd"):
            fields["assessed_value"] = fp["tv_sd"]
        if fp.get("jv"):
            fields["market_value"] = fp["jv"]
        if not fields:
            continue
        try:
            rest_patch("multi_county_auctions",
                       {"county": "eq.okaloosa", "case_number": f"eq.{cn}"},
                       fields)
            patched += 1
            print(f"  ADDRESS_PATCHED {cn}")
        except Exception as exc:
            print(f"  PATCH_FAILED {cn}: {exc}", file=sys.stderr)
    return {"patched": patched}


def evaluate_county(county: str) -> dict:
    try:
        result = rpc_call("pencil_dod_evaluate_county", {"p_county": county})
        return result
    except Exception as exc:
        return {"error": str(exc)}


def update_campaign_checkpoint(dispatch_id: str, county: str, eval_result: dict) -> None:
    """Write progress to gold_standard_campaign table."""
    if not eval_result or "error" in eval_result:
        return
    criteria_passed = {
        letter: eval_result.get(letter, {}).get("pass", False)
        for letter in "ABCDEFGHIJ"
        if letter in eval_result
    }
    criteria_total = sum(1 for v in criteria_passed.values() if v)
    try:
        rest_patch(
            "gold_standard_campaign",
            {"dispatch_id": f"eq.{dispatch_id}", "county_slug": f"eq.{county}"},
            {
                "criteria_passed": json.dumps(criteria_passed),
                "criteria_total": criteria_total,
                "session_end_at": None,
            }
        )
    except Exception as exc:
        print(f"  CHECKPOINT_FAIL {county}: {exc}", file=sys.stderr)


def main():
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY required", file=sys.stderr)
        sys.exit(1)

    dispatch_id = "7be9b60b-f0fa-46e5-8890-af8cb0499ce4"

    print("=" * 60)
    print("SHARD-3 Fix Script: okeechobee (I) + okaloosa (C/D/E/I)")
    print("=" * 60)

    # -- OKALOOSA FIXES --
    print("\n--- OKALOOSA: FC parcel linkage via GIS ---")
    try:
        ok_gis = fix_okaloosa_fc_parcel_linkage()
        print(f"  GIS results: {ok_gis}")
    except Exception as exc:
        print(f"  GIS enrichment failed: {exc}", file=sys.stderr)
        ok_gis = {"error": str(exc)}

    print("\n--- OKALOOSA: Address backfill via fl_parcels ---")
    try:
        ok_addr = fix_okaloosa_property_address_backfill()
        print(f"  Address backfill: {ok_addr}")
    except Exception as exc:
        print(f"  Address backfill failed: {exc}", file=sys.stderr)
        ok_addr = {"error": str(exc)}

    # -- EVALUATE BOTH COUNTIES --
    print("\n--- EVALUATING okaloosa ---")
    okaloosa_eval = evaluate_county("okaloosa")
    print(f"  okaloosa: {json.dumps(okaloosa_eval, indent=2)}")

    print("\n--- EVALUATING okeechobee ---")
    okeechobee_eval = evaluate_county("okeechobee")
    print(f"  okeechobee: {json.dumps(okeechobee_eval, indent=2)}")

    # -- CHECKPOINT --
    update_campaign_checkpoint(dispatch_id, "okaloosa", okaloosa_eval)
    update_campaign_checkpoint(dispatch_id, "okeechobee", okeechobee_eval)

    print("\n=== SUMMARY ===")
    for county, ev in [("okeechobee", okeechobee_eval), ("okaloosa", okaloosa_eval)]:
        if "error" in ev:
            print(f"  {county}: ERROR - {ev['error']}")
            continue
        passed = sum(1 for k in "ABCDEFGHIJ" if k in ev and ev[k].get("pass"))
        print(f"  {county}: {passed}/10 letters pass")
        for k in "ABCDEFGHIJ":
            if k in ev:
                status = "PASS" if ev[k].get("pass") else "FAIL"
                print(f"    {k}: {status} {ev[k].get('detail','')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
