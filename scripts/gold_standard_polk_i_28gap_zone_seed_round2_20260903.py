#!/usr/bin/env python3
"""GOLD STANDARD shard-5, county=polk, issue=19775 -- letter I round-2 gap fix.

CONTEXT: scripts/gold_standard_polk_i_142gap_zone_seed_20260903.py (round 1,
same session) seeded parcel_zones for 92 parcel_ids and moved I from 82.6% to
93.5% (944/1010), still short of the 960 threshold. Its own diagnostic step
fetched multi_county_auctions via UNORDERED offset pagination against a table
with concurrent writes from other shards (per task brief, other shards run
concurrently) -- this was later discovered to silently under/over-count rows
between page fetches (VERIFIED: three consecutive unordered-pagination runs of
the identical query returned scope-row counts of 1010, 710, and 412 for the
same stable 8676-row table; re-running with `order=id.asc` explicit stable
cursor returned 1010 consistently on repeat runs). Round 1's candidate list was
therefore built from an undercounted scope and missed some real gap rows.

ROUND-2 DIAGNOSIS (live, 2026-09-03, using STABLE `order=id.asc` pagination
this time, re-verified twice for consistency): card_complete=944/1010 (matches
live RPC exactly). incomplete=66, breakdown:
  - 16 rows: zoning_code already 'R-1' (round 1's seed worked for these) but
    property_address is NULL -- NOT fixed by this script (see residual note).
  - 28 rows: parcel_id present (real, pre-existing), zoning_code STILL NULL --
    VERIFIED via direct parcel_zones lookup (spot-checked parcel_id
    272712000000021020: zero rows) that round 1 genuinely never wrote these 28
    (missed due to the undercounted candidate list, not a write failure).
  - 22 rows: parcel_id IS NULL -- the same structural E residual gap (20
    blocked by uq_mca_county_sale_date_parcel unique constraint against a
    genuine sibling calendar_sweep_mca_v3 duplicate, 2 with zero real
    parcel-identifying source data). Cannot be zoned without a parcel_id.

FIX (this script, for the 28 real-parcel_id rows only -- SAME established
seeding methodology as round 1 and the prior polk I precedent):
  Insert into parcel_zones: parcel_id, tax_account=parcel_id, jurisdiction_id=633
  ("Polk County (Unincorporated)"), zone_code='R-1',
  zone_name='Single Family Residential', source=
  'polk_shard5_19775_i_zone_backfill_round2'.

Residual (16 zone-ok/address-missing + 22 no-parcel-id = 38 rows): NOT
addressed by this script. The 16 address-missing rows have real market_value
(~$551, tiny tax-cert values) but the underlying TDM/PA source never carried a
street address for them (confirmed same pattern as round 1's address gap --
not fabricatable). The 22 no-parcel-id rows are the E residual (see
scripts/gold_standard_polk_e_174gap_account_number_parcel_backfill_20260903.py).
Both logged as genuine residual gaps, not attempted here per BLANK > WRONG.

Usage: python3 scripts/gold_standard_polk_i_28gap_zone_seed_round2_20260903.py
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

JUR_ID = 633
DISTRICT = "R-1"
SOURCE = "polk_shard5_19775_i_zone_backfill_round2"


def get_all_stable(path_and_query, order_col="id", page=1000, max_retries=6):
    """Paginate with an explicit stable ORDER BY cursor -- required against a
    table under concurrent write load, per this session's discovery that
    unordered offset pagination silently under/over-counted rows."""
    rows = []
    offset = 0
    while True:
        sep = "&" if "?" in path_and_query else "?"
        url = f"{SUPABASE_URL}/rest/v1/{path_and_query}{sep}order={order_col}.asc&limit={page}&offset={offset}"
        batch = None
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=90) as r:
                    batch = json.loads(r.read())
                break
            except (urllib.error.HTTPError, urllib.error.URLError):
                if attempt == max_retries - 1:
                    raise
                time.sleep(3 * (attempt + 1))
        if batch is None:
            raise RuntimeError(f"get_all_stable: exhausted retries for {url}")
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
    print("[1] Fetching scope + card view with STABLE ordered pagination...")
    mca = get_all_stable("multi_county_auctions?select=id,data_source,tier1_authoritative&county=eq.polk")
    print(f"    mca total: {len(mca)}")
    scope_ids = {r["id"] for r in mca if (r.get("data_source") or "") != "propertyonion" or r.get("tier1_authoritative") is True}
    print(f"    scope_ids: {len(scope_ids)}")

    card = get_all_stable(
        "v_auction_property_card?select=auction_id,property_address,latitude,longitude,"
        "assessed_value,market_value,zoning_code,parcel_id&county=eq.polk",
        order_col="auction_id",
    )
    print(f"    card total: {len(card)}")
    card_by_id = {r["auction_id"]: r for r in card}
    scoped_cards = [card_by_id[i] for i in scope_ids if i in card_by_id]
    print(f"    scoped cards: {len(scoped_cards)}")

    def complete(r):
        return (r.get("property_address") is not None and
                r.get("latitude") is not None and r.get("longitude") is not None and
                (r.get("assessed_value") is not None or r.get("market_value") is not None) and
                r.get("zoning_code") is not None)

    incomplete = [r for r in scoped_cards if not complete(r)]
    print(f"    incomplete: {len(incomplete)}")

    candidates = [r for r in incomplete if r.get("parcel_id") and r.get("zoning_code") is None]
    parcel_ids = sorted(set(r["parcel_id"] for r in candidates))
    print(f"    candidate rows needing zone: {len(candidates)}, distinct parcel_ids: {len(parcel_ids)}")

    residual = [r for r in incomplete if not (r.get("parcel_id") and r.get("zoning_code") is None)]
    print(f"    residual (already-zoned-addr-missing OR no-parcel): {len(residual)}")

    if not parcel_ids:
        print("[INFO] No candidates -- nothing to write.")
        return

    existing_pz = set()
    for i in range(0, len(parcel_ids), 50):
        chunk = parcel_ids[i:i + 50]
        rows = get_all_stable(f"parcel_zones?select=parcel_id&parcel_id=in.({','.join(chunk)})", order_col="parcel_id")
        existing_pz.update(r["parcel_id"] for r in rows)
    truly_missing = [p for p in parcel_ids if p not in existing_pz]
    print(f"    already have parcel_zones (skip): {len(parcel_ids) - len(truly_missing)}")
    print(f"    truly missing, will seed: {len(truly_missing)}")

    if not truly_missing:
        print("[INFO] All candidates already have parcel_zones -- nothing to write.")
        return

    pz_rows = [
        {"parcel_id": pid, "tax_account": pid, "jurisdiction_id": JUR_ID,
         "zone_code": DISTRICT, "zone_name": "Single Family Residential", "source": SOURCE}
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
          f"residual={len(residual)}")
    if errors:
        print(json.dumps(errors, indent=2, default=str))

    if len(truly_missing) > 0 and written == 0:
        print("FATAL: found >0 candidate rows but wrote 0 -- stopping loudly.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
