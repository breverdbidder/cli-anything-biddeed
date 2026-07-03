#!/usr/bin/env python3
"""
Lake county parcel_id linkage (criterion E) via Lake County Property Appraiser
FieldMap ArcGIS MapServer — reference pattern per scripts/lee_enrich_shard14.py,
adapted for Lake's own county GIS service (FL GIO statewide cadastral times out
on CO_NO-scoped queries from this environment; Lake's dedicated service does not).

Source: https://gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0
Writes: multi_county_auctions.parcel_id via Supabase REST PATCH (service role key).
Match requires an EXACT house-number match against PropertyAddress (not first-match-wins);
ambiguous/multi-candidate results are skipped rather than guessed.
"""
import os
import re
import sys
import time
import json
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ARCGIS_QUERY = "https://gis.lakecountyfl.gov/lakegis/rest/services/PropertyAppraiser/FieldMap/MapServer/0/query"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def sb_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def enrichment_body(attrs, existing_data_source):
    """Never relabel an existing data_source (e.g. 'propertyonion') — that would
    smuggle a PropertyOnion-sourced auction row past the canon exclusion filter
    (pencil_dod_evaluate_county's `data_source <> 'propertyonion'` population gate)
    on the strength of an unrelated parcel_id match. Only stamp our source when
    the row had none."""
    body = {"parcel_id": attrs["ParcelNumber"], "owner_name": attrs.get("OwnerName")}
    if not existing_data_source:
        body["data_source"] = "lake_pa_fieldmap_v1"
    return body


def sb_patch(row_id, body):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=HEADERS, method="PATCH"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def parse_address(addr):
    """'1873 Sanderling Dr, CLERMONT, FL, 34711' -> ('1873', 'SANDERLING')
    Street name is NOT stripped of directional prefixes (E/W/N/S) here —
    the county's PropertyAddress field keeps them (e.g. '808 E MAGNOLIA ST'),
    so the caller does a substring check against the full remainder instead.
    """
    if not addr:
        return None, None
    head = addr.split(",")[0].strip().upper()
    m = re.match(r"^(\d+)\s+(.+)$", head)
    if not m:
        return None, None
    num, rest = m.group(1), m.group(2)
    # drop unit/apt suffixes ("APT 403", "UNIT B") before matching
    rest = re.split(r"\s+(APT|UNIT|#|STE|SUITE)\b", rest)[0].strip()
    tokens = [t for t in rest.split() if t not in ("N", "S", "E", "W", "NE", "NW", "SE", "SW")]
    street = tokens[0] if tokens else None
    return num, street


def arcgis_query(num, street=None):
    where = f"UPPER(PropertyAddress) LIKE '{num} %'" if street else f"UPPER(PropertyAddress) LIKE '{num} %'"
    params = {
        "where": where,
        "outFields": "ParcelNumber,PropertyAddress,OwnerName",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": "50",
    }
    url = ARCGIS_QUERY + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    feats = data.get("features", [])
    if street:
        feats = [
            f for f in feats
            if street in f["attributes"].get("PropertyAddress", "").strip().upper()
        ]
    return feats


def arcgis_query_by_parcel(parcel_number):
    where = f"ParcelNumber = '{parcel_number}'"
    params = {
        "where": where,
        "outFields": "ParcelNumber,PropertyAddress,OwnerName",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": "2",
    }
    url = ARCGIS_QUERY + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data.get("features", [])


def main():
    rows = sb_get(
        "multi_county_auctions?select=id,case_number,property_address,data_source"
        "&county=eq.lake&parcel_id=is.null&order=id"
    )
    limit = os.environ.get("LAKE_LIMIT")
    if limit:
        rows = rows[: int(limit)]
    print(f"unmatched lake rows: {len(rows)}")

    matched = 0
    ambiguous = 0
    unparsed = 0
    no_match = 0
    errors = 0

    for row in rows:
        addr = row.get("property_address") or ""
        # "Land 30-19-27-120000000200, Mount Dora, ..." — PA-format parcel ID embedded directly
        land_parcel = re.match(r"^Land\s+([\d\-]{10,})", addr.strip())
        if land_parcel:
            candidate = land_parcel.group(1).replace("-", "")
            try:
                feats = arcgis_query_by_parcel(candidate)
            except Exception as e:
                errors += 1
                print(f"ERROR querying {row['id']}: {e}", file=sys.stderr)
                time.sleep(1)
                continue
            if len(feats) == 1:
                attrs = feats[0]["attributes"]
                try:
                    sb_patch(row["id"], enrichment_body(attrs, row.get("data_source")))
                    matched += 1
                except Exception as e:
                    errors += 1
                    print(f"ERROR patching {row['id']}: {e}", file=sys.stderr)
            else:
                no_match += 1
            time.sleep(0.05)
            continue

        num, street = parse_address(addr)
        if not num or not street:
            unparsed += 1
            continue
        try:
            feats = arcgis_query(num, street)
        except Exception as e:
            errors += 1
            print(f"ERROR querying {row['id']}: {e}", file=sys.stderr)
            time.sleep(1)
            continue

        exact = feats
        if len(exact) == 1:
            attrs = exact[0]["attributes"]
            try:
                sb_patch(row["id"], enrichment_body(attrs, row.get("data_source")))
                matched += 1
            except Exception as e:
                errors += 1
                print(f"ERROR patching {row['id']}: {e}", file=sys.stderr)
        elif len(exact) == 0:
            no_match += 1
        else:
            ambiguous += 1

        time.sleep(0.05)

    print(json.dumps({
        "total_unmatched_at_start": len(rows),
        "matched": matched,
        "ambiguous_skipped": ambiguous,
        "no_match": no_match,
        "unparsed_address": unparsed,
        "errors": errors,
    }, indent=2))


if __name__ == "__main__":
    main()
