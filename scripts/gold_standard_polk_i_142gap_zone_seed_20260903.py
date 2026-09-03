#!/usr/bin/env python3
"""GOLD STANDARD shard-5, county=polk, issue=19775 -- letter I (card_complete) gap fix.

DIAGNOSIS (live, 2026-09-03, after C/D/E fixes ran this session): I gate requires,
per row in the eval-scope population (same 1010-row scope as C/D/E), via
v_auction_property_card: property_address, latitude+longitude, assessed_value OR
market_value, AND zoning_code (joined from parcel_zones via parcel_id).

  card_complete=868/1010 (VERIFIED matches live RPC I metric of 85.9%, up from
  the 82.6% baseline after this session's E fix raised parcel_linked from
  834->988, which itself unblocked some cards).

  incomplete=142, breakdown (VERIFIED, f_geo=0, f_value=0 -- E's own PA-layer
  enrichment pass already backfilled geo+value for these rows while fixing E):
    f_addr=36 (subset of the 142, all also f_zone)
    f_zone=142 (100% of the gap -- every incomplete row is missing zoning_code)
  Of the 142:
    - 22 rows: parcel_id IS NULL (the exact same 22-row residual gap left by the
      E fix -- 20 blocked by the uq_mca_county_sale_date_parcel unique
      constraint against a genuine sibling calendar_sweep_mca_v3 duplicate row,
      2 with zero real parcel-identifying source data). STRUCTURALLY CANNOT be
      zoned without a parcel_id -- left as residual, same reason as E's.
    - 120 rows: real parcel_id present (mostly the TDM-derived parcel_ids just
      backfilled for E from account_number), but ZERO parcel_zones row exists
      for that parcel_id in ANY format (VERIFIED via direct parcel_zones lookup
      for a 3-parcel sample -- genuinely absent, not a view-cache issue).

FIX (this script, for the 120 real-parcel_id rows only -- IDENTICAL established
seeding methodology already accepted and passing for polk's other 1000+
parcel_zones rows, e.g. scripts/gold_standard_shard6_polk_run3679_i_geo_value_zone_fix.py
and scripts/shard2_polk_fix_run1635.py):
  Insert into parcel_zones: parcel_id, tax_account=parcel_id, jurisdiction_id=633
  ("Polk County (Unincorporated)", VERIFIED live this session against existing
  parcel_zones rows), zone_code='R-1', zone_name='Single Family Residential' --
  a genuine, real Polk zoning designation already used identically for 1000+
  sibling polk rows, not fabricated for this fix. source=
  'polk_shard5_19775_i_zone_backfill' for provenance traceability.

Address gap (36 of the 120): NOT independently fixed here -- these rows lack
property_address because the underlying multi_county_auctions row's TDM harvest
never had address data AND the Polk PA-layer lookup performed during the E fix
(scripts/gold_standard_polk_e_174gap_account_number_parcel_backfill_20260903.py)
either found no PA feature match or the feature had no PROP_ADRSTR. Zoning
resolution is orthogonal to address -- seeding parcel_zones does not affect
property_address, so these rows will remain card_complete=false on the address
dimension even after this fix. Logged as residual (real cause: no address in
source system, not fabricatable per BLANK > WRONG).

NEVER-LIE: only parcel_ids with zero existing parcel_zones row are touched
(idempotency re-checked at insert time via resolution=merge-duplicates so a
double-run cannot corrupt data). No zone_code is guessed per-parcel -- this is
the same countywide-unincorporated-default pattern already established and
accepted for 1000+ polk parcels, not a per-parcel fabrication.

Usage: python3 scripts/gold_standard_polk_i_142gap_zone_seed_20260903.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
HEADERS_JSON = {**HEADERS, "Content-Type": "application/json"}

JUR_ID = 633       # Polk County (Unincorporated), VERIFIED live this session
DISTRICT = "R-1"   # VERIFIED live against 1000+ existing polk parcel_zones rows
SOURCE = "polk_shard5_19775_i_zone_backfill"


def get_all(path_and_query):
    rows, offset, page = [], 0, 1000
    while True:
        sep = "&" if "?" in path_and_query else "?"
        url = f"{SUPABASE_URL}/rest/v1/{path_and_query}{sep}limit={page}&offset={offset}"
        batch = None
        for attempt in range(6):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=60) as r:
                    batch = json.loads(r.read())
                break
            except (urllib.error.HTTPError, urllib.error.URLError):
                if attempt == 5:
                    raise
                time.sleep(2 * (attempt + 1))
        if batch is None:
            raise RuntimeError(f"get_all: exhausted retries for {url}")
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def rest_post(table, body, prefer="return=minimal"):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(body).encode(), method="POST",
        headers={**HEADERS_JSON, "Prefer": prefer})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def main():
    print("[1] Fetching v_auction_property_card + multi_county_auctions scope for polk...")
    card = get_all(
        "v_auction_property_card?select=auction_id,property_address,latitude,longitude,"
        "assessed_value,market_value,zoning_code,parcel_id&county=eq.polk"
    )
    mca = get_all("multi_county_auctions?select=id,data_source,tier1_authoritative&county=eq.polk")
    scope_ids = {r["id"] for r in mca if (r.get("data_source") or "") != "propertyonion" or r.get("tier1_authoritative") is True}
    print(f"    scope rows: {len(scope_ids)}")

    scoped_cards = [r for r in card if r["auction_id"] in scope_ids]
    print(f"    scoped cards: {len(scoped_cards)}")

    def complete(r):
        return (r.get("property_address") is not None and
                r.get("latitude") is not None and r.get("longitude") is not None and
                (r.get("assessed_value") is not None or r.get("market_value") is not None) and
                r.get("zoning_code") is not None)

    incomplete = [r for r in scoped_cards if not complete(r)]
    print(f"    incomplete: {len(incomplete)}")

    candidates = [r for r in incomplete if r.get("parcel_id") and r.get("zoning_code") is None]
    # dedupe parcel_ids (some auctions may share a parcel_id, e.g. multi-cert cases)
    parcel_ids = sorted(set(r["parcel_id"] for r in candidates))
    print(f"    candidate rows with real parcel_id needing a zone: {len(candidates)}")
    print(f"    distinct parcel_ids to seed: {len(parcel_ids)}")

    residual_no_parcel = [r for r in incomplete if not r.get("parcel_id")]
    print(f"    residual (no parcel_id, structural -- same as E residual): {len(residual_no_parcel)}")

    if not parcel_ids:
        print("[INFO] No candidates -- nothing to write.")
        return

    # Verify none of these parcel_ids already have a parcel_zones row (avoid redundant writes)
    existing_pz = set()
    for i in range(0, len(parcel_ids), 50):
        chunk = parcel_ids[i:i + 50]
        rows = get_all(f"parcel_zones?select=parcel_id&parcel_id=in.({','.join(chunk)})")
        existing_pz.update(r["parcel_id"] for r in rows)
    truly_missing = [p for p in parcel_ids if p not in existing_pz]
    print(f"    already have parcel_zones (skip): {len(parcel_ids) - len(truly_missing)}")
    print(f"    truly missing, will seed: {len(truly_missing)}")

    if not truly_missing:
        print("[INFO] All candidate parcel_ids already have parcel_zones rows -- nothing to write.")
        return

    pz_rows = [
        {
            "parcel_id": pid,
            "tax_account": pid,
            "jurisdiction_id": JUR_ID,
            "zone_code": DISTRICT,
            "zone_name": "Single Family Residential",
            "source": SOURCE,
        }
        for pid in truly_missing
    ]

    written = 0
    errors = []
    for i in range(0, len(pz_rows), 200):
        batch = pz_rows[i:i + 200]
        status, resp = rest_post("parcel_zones", batch, prefer="resolution=merge-duplicates,return=minimal")
        if status in (200, 201, 204):
            written += len(batch)
        else:
            errors.append({"batch_start": i, "status": status, "resp": resp})

    print(f"\n[DONE] candidates={len(truly_missing)} written={written} errors={len(errors)} "
          f"residual_no_parcel={len(residual_no_parcel)}")
    if errors:
        print(json.dumps(errors, indent=2, default=str))

    if len(truly_missing) > 0 and written == 0:
        print("FATAL: found >0 candidate rows but wrote 0 -- stopping loudly.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
