#!/usr/bin/env python3
"""SHARD-2 hillsborough E/I real fix (run3713 residual, 2026-07-11).

ULTRALOOP audit (commit eea355bc) found hillsborough's parcel_id column is
~95% fabricated: values like "1828133" are not invented from nothing -- they
are the truncated leading-digit run of the genuine 22-char HCPAFL STRAP
(e.g. real strap "1828133CU000000000440A" truncated at the first letter).
Verified live against gis.hcpafl.org/arcgis/rest/services/Webmaps/
HillsboroughFL_WebParcels/MapServer/0 for 3 independent samples before
writing this script -- this is a parsing/truncation bug in a prior
ingestion run, not random fabrication.

This script recovers the genuine parcel identifier per auction row by
address lookup against the live HCPAFL ArcGIS FeatureServer (folio + strap
fields), and only writes a value when the match is unambiguous. Rows whose
property_address is a confidentiality redaction ("Address On File ...") or
whose address matches >1 parcel (e.g. condo buildings without a unit
number in our stored address) are left untouched and reported as
UNRESOLVED -- no guessing, per Honesty Protocol.

Prefers strap (22-char) as the corrected parcel_id (matches the format of
the 45 auction rows that were already genuine), but writes folio (10-digit)
instead when folio -- not strap -- is the format already used for that
parcel in v_zoning_gold_standard_card, so the fix also cascades into I
(property-card zoning linkage) wherever possible.

Usage: python3 scripts/shard2_hillsborough_e_i_folio_fix.py [--apply]
Without --apply, runs read-only and prints the resolution plan + counts.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = SUPABASE_URL.split("//")[1].split(".")[0]
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
ARCGIS_QUERY_URL = (
    "https://gis.hcpafl.org/arcgis/rest/services/Webmaps/"
    "HillsboroughFL_WebParcels/MapServer/0/query"
)


def mgmt_query(sql: str, _retries: int = 6):
    # Supabase's Management API front door (Cloudflare) 403s python's urllib
    # user-agent/TLS fingerprint but accepts curl -- shell out for reliability.
    for attempt in range(_retries):
        try:
            proc = subprocess.run(
                [
                    "curl", "-s", "-X", "POST", MGMT_URL,
                    "-H", f"Authorization: Bearer {ACCESS_TOKEN}",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps({"query": sql}),
                ],
                capture_output=True, text=True, timeout=90,
            )
        except subprocess.TimeoutExpired:
            time.sleep(1.5 * (attempt + 1))
            continue
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result = {"message": f"non-JSON response: {proc.stdout[:200]}"}
        msg = result.get("message", "") if isinstance(result, dict) else ""
        if "ThrottlerException" in msg or "Too Many Requests" in msg:
            time.sleep(1.5 * (attempt + 1))
            continue
        return result
    return result


def arcgis_query(where: str, out_fields: str = "folio,strap,FullAddress"):
    params = urllib.parse.urlencode({"where": where, "outFields": out_fields, "f": "json"})
    req = urllib.request.Request(f"{ARCGIS_QUERY_URL}?{params}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode())
                return data.get("features", [])
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                print(f"  ArcGIS query failed after retries: {e}", file=sys.stderr)
                return []
            time.sleep(2)


def street_part(addr: str) -> str:
    """Strip city/state/zip suffix, keep the street portion, upper-cased."""
    if not addr:
        return ""
    base = addr.split(",")[0].strip().upper()
    return base


def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def _require_list(result, context):
    if not isinstance(result, list):
        raise RuntimeError(f"{context}: expected list result, got {result!r}")
    return result


def fetch_candidates():
    sql = (
        "SELECT case_number, parcel_id, property_address FROM multi_county_auctions "
        "WHERE county='hillsborough' AND parcel_id ~ '^[0-9]{6,12}$' "
        "ORDER BY case_number;"
    )
    return _require_list(mgmt_query(sql), "fetch_candidates")


def fetch_zoning_card_ids():
    """Which parcel_id values (any format) already resolve to a hillsborough zoning row."""
    rows = _require_list(
        mgmt_query("SELECT parcel_id FROM v_zoning_gold_standard_card WHERE county='hillsborough';"),
        "fetch_zoning_card_ids",
    )
    return {r["parcel_id"] for r in rows}


def main():
    apply = "--apply" in sys.argv

    candidates = fetch_candidates()
    print(f"candidates (truncated-numeric parcel_id): {len(candidates)}")

    redacted = [c for c in candidates if "Address On File" in (c.get("property_address") or "")]
    addressable = [c for c in candidates if c not in redacted]
    print(f"redacted (unresolvable by address, left untouched): {len(redacted)}")
    print(f"addressable candidates: {len(addressable)}")

    zoning_ids = fetch_zoning_card_ids()
    print(f"hillsborough zoning-card parcel_id values (any format): {len(zoning_ids)}")

    resolved = []
    ambiguous = []
    no_match = []

    BATCH = 15
    for i in range(0, len(addressable), BATCH):
        batch = addressable[i:i + BATCH]
        streets = {street_part(c["property_address"]) for c in batch}
        streets = {s for s in streets if s}
        clauses = " OR ".join(f"UPPER(FullAddress) LIKE '{sql_escape(s)}%'" for s in streets)
        if not clauses:
            continue
        features = arcgis_query(clauses)
        by_street = {}
        for f in features:
            attrs = f["attributes"]
            full = (attrs.get("FullAddress") or "").upper()
            key = full.split(",")[0].strip()
            by_street.setdefault(key, []).append(attrs)

        for c in batch:
            s = street_part(c["property_address"])
            matches = by_street.get(s, [])
            if len(matches) == 0:
                no_match.append(c)
            elif len(matches) == 1:
                resolved.append((c, matches[0]))
            else:
                # Try exact FullAddress equality (handles unit numbers embedded
                # in our stored address, e.g. "... DR 1511, TAMPA, FL- 33647").
                our_full = (c["property_address"] or "").upper()
                exact = [m for m in matches if our_full.startswith((m.get("FullAddress") or "").upper())
                         and len((m.get("FullAddress") or "")) > len(s) + 2]
                if len(exact) == 1:
                    resolved.append((c, exact[0]))
                else:
                    ambiguous.append((c, matches))
        time.sleep(0.3)

    print(f"resolved (unambiguous address match): {len(resolved)}")
    print(f"ambiguous (multiple parcels at address, left untouched): {len(ambiguous)}")
    print(f"no_match (address not found in HCPAFL GIS, left untouched): {len(no_match)}")

    strap_choice = 0
    folio_choice = 0
    updates = []
    for c, attrs in resolved:
        strap = attrs.get("strap")
        folio = attrs.get("folio")
        # Prefer whichever format already exists in the zoning card, so the
        # fix cascades into I; default to strap (matches genuine-format rows).
        if folio and folio in zoning_ids:
            new_id = folio
            folio_choice += 1
        elif strap and strap in zoning_ids:
            new_id = strap
            strap_choice += 1
        elif strap:
            new_id = strap
            strap_choice += 1
        elif folio:
            new_id = folio
            folio_choice += 1
        else:
            continue
        updates.append((c["case_number"], c["parcel_id"], new_id))

    print(f"resolved -> strap chosen: {strap_choice}, folio chosen (zoning-matched): {folio_choice}")
    print("sample resolutions:")
    for case_number, old, new in updates[:10]:
        print(f"  {case_number}: {old} -> {new}")

    if not apply:
        print("\nDRY RUN (no --apply passed). No writes performed.")
        return

    print(f"\nAPPLYING {len(updates)} updates ONE AT A TIME (fail-loud, no batching -- "
          f"a unique constraint uq_mca_county_sale_date_parcel(county,sale_type,auction_date,parcel_id) "
          f"can reject individual rows and batched multi-statement SQL was found to silently drop "
          f"failures for the rest of that statement string)...")
    succeeded = []
    failed = []
    for case_number, old_id, new_id in updates:
        sql = (
            "UPDATE multi_county_auctions SET parcel_id='%s' "
            "WHERE county='hillsborough' AND case_number='%s' "
            "RETURNING case_number;"
            % (sql_escape(new_id), sql_escape(case_number))
        )
        result = mgmt_query(sql)
        if isinstance(result, dict) and "message" in result:
            failed.append((case_number, old_id, new_id, result["message"]))
        elif isinstance(result, list) and len(result) > 0:
            succeeded.append((case_number, old_id, new_id))
        else:
            failed.append((case_number, old_id, new_id, "no rows matched WHERE clause"))
        time.sleep(1.1)

    print(f"\nDONE. Succeeded: {len(succeeded)}. Failed: {len(failed)}.")
    if failed:
        print("FAILURES (left at prior value, not silently dropped):")
        for case_number, old_id, new_id, msg in failed:
            short = msg.splitlines()[0][:160] if msg else msg
            print(f"  {case_number}: {old_id} -/-> {new_id}  ({short})")
    print(f"Still unresolved (never attempted): {len(redacted)} redacted + {len(ambiguous)} ambiguous + "
          f"{len(no_match)} no_match = {len(redacted) + len(ambiguous) + len(no_match)}")


if __name__ == "__main__":
    main()
