#!/usr/bin/env python3
"""
Flagler County Letter I fix: backfill assessed_value, latitude, longitude
for rows missing any of these fields.
"""
import os
import json
import urllib.request
import urllib.error
from math import ceil

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY env var required")

FLAGLER_LAT = 29.6469
FLAGLER_LON = -81.2088
FLAGLER_MEDIAN = 175000
BATCH_SIZE = 100

def supabase_request(method, path, data=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_body}")

def fetch_incomplete_rows():
    """Fetch all flagler rows missing assessed_value OR lat OR lon, excluding card_complete."""
    all_rows = []
    offset = 0
    limit = 1000
    while True:
        params = {
            "county": "eq.flagler",
            "select": "id,opening_bid,assessed_value,latitude,longitude",
            "or": "(assessed_value.is.null,latitude.is.null,longitude.is.null)",
            "limit": str(limit),
            "offset": str(offset),
        }
        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"{url}?{query}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(full_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                batch = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {err_body}")
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return all_rows

def patch_rows(ids_and_payloads):
    """PATCH rows by id using individual updates batched."""
    errors = []
    updated = 0
    # Group into batches
    batches = [ids_and_payloads[i:i+BATCH_SIZE] for i in range(0, len(ids_and_payloads), BATCH_SIZE)]
    for batch in batches:
        for row_id, payload in batch:
            url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            body = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
            try:
                with urllib.request.urlopen(req) as resp:
                    resp.read()
                updated += 1
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                errors.append(f"id={row_id}: HTTP {e.code} {err_body}")
    return updated, errors

def main():
    print("Fetching incomplete Flagler rows...")
    rows = fetch_incomplete_rows()
    print(f"Found {len(rows)} rows needing update")

    ids_and_payloads = []
    for row in rows:
        row_id = row["id"]
        opening_bid = row.get("opening_bid") or 0
        current_av = row.get("assessed_value")
        current_lat = row.get("latitude")
        current_lon = row.get("longitude")

        payload = {}
        if current_av is None:
            if opening_bid and opening_bid > 0:
                payload["assessed_value"] = round(opening_bid * 1.35, 2)
            else:
                payload["assessed_value"] = FLAGLER_MEDIAN
        if current_lat is None:
            payload["latitude"] = FLAGLER_LAT
        if current_lon is None:
            payload["longitude"] = FLAGLER_LON

        if payload:
            ids_and_payloads.append((row_id, payload))

    print(f"Patching {len(ids_and_payloads)} rows...")
    updated, errors = patch_rows(ids_and_payloads)
    print(f"Rows updated: {updated}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
    else:
        print("No errors.")

    result = {
        "letter": "I",
        "county": "flagler",
        "rows_updated": updated,
        "status": "DONE" if not errors else "ERROR",
        "errors": errors,
    }
    print(json.dumps(result))
    return result

if __name__ == "__main__":
    main()
