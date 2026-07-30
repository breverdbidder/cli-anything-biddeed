#!/usr/bin/env python3
"""
Brevard I: Property Card Address + Geo + Value Backfill
Dispatch: issue-16909-20260730

Sources (in order):
  S1: FL DOR Statewide Cadastral ArcGIS (CO_NO=15, ALT_KEY=parcel_id)
      Fields: PHY_ADDR1, PHY_CITY, PHY_ZIPCD, Shape (centroid), JV, AV_SD, AV_NSD

  S2: BCPAO ArcGIS FeatureServer (Brevard Property Appraiser) - backup

Writes to: multi_county_auctions (property_address, latitude, longitude,
           assessed_value, market_value)

Criterion I requires ALL of:
  - property_address IS NOT NULL
  - latitude/longitude IS NOT NULL
  - assessed_value/market_value IS NOT NULL
  - parcel_id in v_zoning_gold_standard_card (zone_code not null)

This script targets rows where one or more of address/geo/value is missing
and the parcel_id can be matched to the FL DOR Cadastral.

Env:
  SUPABASE_URL (default: https://mocerqjnksmhcjzxrewo.supabase.co)
  SUPABASE_KEY or SUPABASE_SERVICE_KEY
  TELEGRAM_BOT_TOKEN (optional)
  TELEGRAM_CHAT_ID (optional)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

DOR_BASE = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services"
    "/Florida_Statewide_Cadastral/FeatureServer/0/query"
)
DOR_FIELDS = "OBJECTID,ALT_KEY,PARCEL_ID,PARCELNO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD,AV_NSD"
COUNTY_NO = 15


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def tg(msg: str) -> None:
    if not (TELEGRAM_BOT and TELEGRAM_CHAT):
        return
    try:
        body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def sb_headers(prefer: str | None = None) -> dict:
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_rpc(fn: str, payload: dict) -> dict | list | None:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=body,
        headers=sb_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        log(f"RPC {fn} error: HTTP {e.code} — {e.read().decode()[:400]}")
        return None


def sb_get_paginated(table: str, select: str, filters: str, page_size: int = 1000) -> list:
    """Fetch all rows from a Supabase table with pagination."""
    rows: list = []
    offset = 0
    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/{table}"
            f"?select={urllib.parse.quote(select)}"
            f"&{filters}"
            f"&limit={page_size}&offset={offset}"
        )
        req = urllib.request.Request(url, headers=sb_headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                batch = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            log(f"  GET {table} error: HTTP {e.code}")
            break
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def sb_patch_batch(table: str, rows: list[dict], match_col: str) -> int:
    """PATCH (update) rows in Supabase by primary key. Uses individual PATCH per row."""
    updated = 0
    for row in rows:
        match_val = row.pop(match_col)
        if not row:
            continue
        url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{match_val}"
        body = json.dumps(row).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method="PATCH",
            headers=sb_headers(prefer="return=minimal"),
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status in (200, 204):
                    updated += 1
        except urllib.error.HTTPError as e:
            log(f"  PATCH id={match_val} error: HTTP {e.code}")
        except Exception as e:
            log(f"  PATCH id={match_val} error: {e}")
    return updated


def sb_patch_bulk(updates: list[dict]) -> int:
    """
    Bulk PATCH via RPC function: update_mca_card_fields(updates jsonb[])
    Falls back to individual PATCH if RPC unavailable.
    """
    if not updates:
        return 0
    result = sb_rpc("update_mca_card_fields", {"updates": updates})
    if result is not None and isinstance(result, (int, float)):
        return int(result)
    if isinstance(result, list) and result and "updated" in result[0]:
        return int(result[0]["updated"])
    log("  RPC update_mca_card_fields not available, falling back to individual PATCHes")
    total = 0
    for upd in updates:
        row_id = upd.get("row_id")
        if not row_id:
            continue
        payload: dict = {}
        if upd.get("property_address"):
            payload["property_address"] = upd["property_address"]
        if upd.get("latitude") is not None:
            payload["latitude"] = upd["latitude"]
        if upd.get("longitude") is not None:
            payload["longitude"] = upd["longitude"]
        if upd.get("assessed_value") is not None:
            payload["assessed_value"] = upd["assessed_value"]
        if upd.get("market_value") is not None:
            payload["market_value"] = upd["market_value"]
        if not payload:
            continue
        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=body,
            method="PATCH",
            headers=sb_headers(prefer="return=minimal"),
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status in (200, 204):
                    total += 1
        except urllib.error.HTTPError as e:
            log(f"    PATCH id={row_id} HTTP {e.code}: {e.read().decode()[:200]}")
        except Exception as e:
            log(f"    PATCH id={row_id} error: {e}")
        time.sleep(0.05)
    return total


def fetch_incomplete_brevard_rows() -> list[dict]:
    """
    Fetch MCA rows for Brevard where card is incomplete:
    - parcel_id IS NOT NULL (needed to join DOR)
    - AND (property_address IS NULL OR latitude IS NULL OR assessed_value IS NULL)
    """
    log("Fetching incomplete Brevard MCA rows...")
    rows = sb_get_paginated(
        table="multi_county_auctions",
        select="id,parcel_id,property_address,latitude,longitude,assessed_value,market_value",
        filters=(
            "county=eq.brevard"
            "&parcel_id=not.is.null"
            "&or=(property_address.is.null,latitude.is.null,assessed_value.is.null)"
            "&data_source=not.eq.propertyonion"
            "&order=id.asc"
        ),
        page_size=1000,
    )
    log(f"  Found {len(rows)} incomplete rows with parcel_id")
    return rows


def fetch_dor_batch(alt_keys: list[str]) -> list[dict]:
    """
    Query FL DOR Statewide Cadastral ArcGIS for a batch of ALT_KEY values.
    ALT_KEY = BCPAO account number = parcel_id in MCA for Brevard.
    """
    if not alt_keys:
        return []

    in_clause = ",".join(f"'{k}'" for k in alt_keys[:1000])
    where = f"CO_NO={COUNTY_NO} AND ALT_KEY IN ({in_clause})"

    params = urllib.parse.urlencode({
        "where": where,
        "outFields": DOR_FIELDS,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": 2000,
    })

    url = f"{DOR_BASE}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-GoldStandard/1.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        log(f"  DOR ArcGIS fetch error: {e}")
        return []

    features = data.get("features", [])
    results = []
    for feat in features:
        att = feat.get("attributes", {})
        geom = feat.get("geometry", {})

        alt_key = str(att.get("ALT_KEY", "") or "").strip()
        phy_addr = str(att.get("PHY_ADDR1", "") or "").strip()
        phy_city = str(att.get("PHY_CITY", "") or "").strip()
        phy_zip = str(att.get("PHY_ZIPCD", "") or "").strip()
        jv = att.get("JV")
        av_sd = att.get("AV_SD")
        av_nsd = att.get("AV_NSD")

        lat = geom.get("y")
        lon = geom.get("x")

        if not alt_key:
            continue

        full_addr = None
        if phy_addr and phy_city and "UNKNOWN" not in phy_addr.upper():
            parts = [p for p in [phy_addr, phy_city, f"FL {phy_zip}"] if p]
            full_addr = ", ".join(parts)

        results.append({
            "alt_key": alt_key,
            "address": full_addr,
            "lat": float(lat) if lat is not None else None,
            "lon": float(lon) if lon is not None else None,
            "jv": int(jv) if jv and jv > 0 else None,
            "av": int(av_sd) if av_sd and av_sd > 0 else (int(av_nsd) if av_nsd and av_nsd > 0 else None),
        })
    return results


def run() -> None:
    if not SUPABASE_KEY:
        log("ERROR: No Supabase key found in env (SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY / SUPABASE_SERVICE_KEY)")
        sys.exit(1)

    tg("🏔️ Brevard I address+geo+value backfill — starting (dispatch issue-16909-20260730)")
    log("=== Brevard I Card Completeness Backfill ===")
    log(f"Target: property_address + lat/lon + assessed_value for card-incomplete rows")

    incomplete = fetch_incomplete_brevard_rows()
    if not incomplete:
        log("No incomplete rows found — I may already be passing")
        tg("✅ Brevard I: no incomplete rows found")
        return

    parcel_map: dict[str, dict] = {}
    for row in incomplete:
        pid = str(row.get("parcel_id") or "").strip()
        if pid:
            parcel_map[pid] = row

    log(f"  Unique parcel_ids to resolve: {len(parcel_map)}")

    dor_data: dict[str, dict] = {}
    parcel_ids = list(parcel_map.keys())
    batch_size = 500

    for start in range(0, len(parcel_ids), batch_size):
        batch = parcel_ids[start:start + batch_size]
        log(f"  DOR ArcGIS batch {start//batch_size + 1}: {len(batch)} parcel_ids")
        features = fetch_dor_batch(batch)
        log(f"    → {len(features)} features returned")
        for feat in features:
            dor_data[feat["alt_key"]] = feat
        time.sleep(0.5)

    log(f"  DOR resolved {len(dor_data)} of {len(parcel_map)} parcel_ids")

    updates: list[dict] = []
    addr_count = 0
    geo_count = 0
    val_count = 0
    skipped_unknown = 0

    for pid, row in parcel_map.items():
        dor = dor_data.get(pid)
        if not dor:
            continue

        upd: dict = {"row_id": row["id"]}
        changed = False

        if not row.get("property_address") and dor.get("address"):
            upd["property_address"] = dor["address"]
            addr_count += 1
            changed = True
        elif not row.get("property_address"):
            skipped_unknown += 1

        if row.get("latitude") is None and dor.get("lat") is not None:
            upd["latitude"] = dor["lat"]
            geo_count += 1
            changed = True

        if row.get("longitude") is None and dor.get("lon") is not None:
            upd["longitude"] = dor["lon"]
            changed = True

        if not row.get("assessed_value") and not row.get("market_value"):
            if dor.get("jv"):
                upd["market_value"] = dor["jv"]
                val_count += 1
                changed = True
            if dor.get("av"):
                upd["assessed_value"] = dor["av"]
                changed = True

        if changed:
            updates.append(upd)

    log(f"  Updates prepared: {len(updates)} rows")
    log(f"    address: {addr_count}, lat/lon: {geo_count}, value: {val_count}")
    log(f"    skipped (no DOR address): {skipped_unknown}")

    if not updates:
        log("  Nothing to update")
        tg("⚠️ Brevard I: DOR fetch returned 0 updates (all already complete or no DOR match)")
        return

    log(f"  Applying {len(updates)} updates...")

    CHUNK = 50
    total_updated = 0
    for i in range(0, len(updates), CHUNK):
        chunk = updates[i:i + CHUNK]
        n = sb_patch_bulk(chunk)
        total_updated += n
        log(f"    chunk {i//CHUNK + 1}: +{n} rows updated (running total: {total_updated})")
        time.sleep(0.3)

    log(f"  Total updated: {total_updated}")
    tg(
        f"✅ Brevard I backfill complete\n"
        f"  DOR resolved: {len(dor_data)}/{len(parcel_map)} parcel_ids\n"
        f"  address: {addr_count}, lat/lon: {geo_count}, value: {val_count}\n"
        f"  rows updated: {total_updated}"
    )

    log("Evaluating Brevard I post-backfill...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "brevard"})
    if result:
        i_data = result.get("I", {})
        log(f"  I: pass={i_data.get('pass')} metric={i_data.get('metric')} detail={i_data.get('detail')}")
        tg(f"📊 Brevard I post-backfill: {i_data.get('metric')}% ({i_data.get('detail')})")
    else:
        log("  (evaluation failed or not available)")


if __name__ == "__main__":
    run()
