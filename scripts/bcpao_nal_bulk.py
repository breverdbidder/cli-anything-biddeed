#!/usr/bin/env python3
"""BCPAO NAL bulk download → brevard_folio_pin_bridge.

Strategy A (primary): Download the BCPAO NAL bulk ZIP from bcpao.us/PDF/NAL.zip,
parse the CSV inside, extract folio→PIN for every queued account in
bcpao_fetch_jobs, upsert into brevard_folio_pin_bridge, then drain into MCA.

Strategy B (fallback): Query the FL DOR Statewide Cadastral FeatureServer
(CO_NO=15, fields=ALT_KEY,PARCEL_ID) — ALT_KEY is the BCPAO account number.
Already proven infrastructure used by load_brevard_parcels.py.

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  (required)
  BCPAO_NAL_URL                            (optional override, default below)
  STRATEGY                                 (A | B | auto, default auto)

Usage:
  python scripts/bcpao_nal_bulk.py [limit]
  STRATEGY=B python scripts/bcpao_nal_bulk.py
"""
from __future__ import annotations
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

# ── Config ────────────────────────────────────────────────────────────────────

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
STRATEGY = os.environ.get("STRATEGY", "auto").upper()

# INFERRED: standard BCPAO (Brevard County Property Appraiser) NAL export URL.
# Set BCPAO_NAL_URL env var to override if this shifts.
BCPAO_NAL_URL = os.environ.get(
    "BCPAO_NAL_URL",
    "https://www.bcpao.us/PDF/NAL.zip",
)

# DOR Cadastral fallback — same endpoint as load_brevard_parcels.py
DOR_URL = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
DOR_FIELDS = "ALT_KEY,PARCEL_ID,PARCELNO,PHY_ADDR1"
DOR_WHERE = "CO_NO=15 AND ALT_KEY IS NOT NULL"
DOR_BATCH = 2000

BRIDGE_TABLE = "brevard_folio_pin_bridge"
JOBS_TABLE = "bcpao_fetch_jobs"

assert SB_URL and SB_KEY, "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY required"

# ── Supabase helpers ──────────────────────────────────────────────────────────


def sb_headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path: str, params: str = "") -> list | dict:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, headers=sb_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def sb_post(path: str, payload, extra_headers: dict | None = None) -> tuple[int, str]:
    hdrs = {**sb_headers(), **(extra_headers or {})}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=body, method="POST", headers=hdrs
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_patch(path: str, payload, params: str = "") -> tuple[int, str]:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={**sb_headers(), "Prefer": "return=minimal"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def call_drain() -> int:
    """Call bcpao_folio_drain() → returns updated MCA count."""
    body = b"{}"
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/bcpao_folio_drain",
        data=body,
        method="POST",
        headers=sb_headers(),
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return int(json.loads(r.read().decode()) or 0)
    except Exception as e:
        print(f"  drain error: {e}", file=sys.stderr)
        return 0


# ── Queued accounts ───────────────────────────────────────────────────────────


def load_queued_accounts() -> tuple[set[str], dict[str, str]]:
    """Return (account_set, {folio: street_normalized}) for all queued jobs."""
    rows = sb_get(JOBS_TABLE, "status=eq.queued&select=account&limit=10000")
    accounts = {str(r["account"]).strip() for r in rows}
    print(f"queued accounts: {len(accounts)}")

    # Fetch MCA addresses for PHY_ADDR1 cross-match
    mca_rows: list = []
    offset = 0
    while True:
        batch = sb_get(
            "multi_county_auctions",
            f"county=eq.brevard&parcel_id=in.({','.join(list(accounts)[:500])})&select=parcel_id,street_normalized&limit=500&offset={offset}"
        ) if accounts else []
        # Note: REST IN clause limited to 500; use multiple passes for larger sets
        mca_rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500

    # For large sets, use a broader MCA pull filtered in Python
    if len(accounts) > 500:
        mca_rows = []
        for i in range(0, len(accounts), 500):
            chunk = list(accounts)[i:i+500]
            in_clause = ",".join(chunk)
            batch = sb_get(
                "multi_county_auctions",
                f"county=eq.brevard&select=parcel_id,street_normalized&limit=500"
                f"&parcel_id=in.({in_clause})"
            )
            mca_rows.extend(batch)

    mca_addrs = {
        str(r["parcel_id"]): str(r.get("street_normalized") or "").strip().upper()
        for r in mca_rows
        if r.get("street_normalized")
    }
    print(f"MCA addresses loaded: {len(mca_addrs)}")
    return accounts, mca_addrs


# ── Strategy A: BCPAO NAL bulk download ──────────────────────────────────────

# Candidate column names in NAL files (varies by export generation)
_ACCT_COLS = ("ACCT_NUM", "ACCOUNT", "ACCT", "ACCOUNT_NUMBER", "AccountNo", "FOLIO")
_PIN_COLS = (
    "PARCEL_ID", "PARCELID", "PARCEL", "PIN", "ParcelID", "parcelNumber",
    "PARCEL_NO", "PARCELNO",
)


def _find_col(header: list[str], candidates: tuple[str, ...]) -> str | None:
    h_upper = {c.upper(): c for c in header}
    for cand in candidates:
        if cand.upper() in h_upper:
            return h_upper[cand.upper()]
    return None


def strategy_a_nal(queued: set[str]) -> dict[str, str]:
    """Download NAL ZIP, parse CSV, return folio→PIN map for queued accounts."""
    print(f"Strategy A: downloading NAL from {BCPAO_NAL_URL}")
    req = urllib.request.Request(
        BCPAO_NAL_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; BidDeed-Data/1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
    except Exception as e:
        raise RuntimeError(f"NAL download failed: {e}") from e

    print(f"  downloaded {len(raw):,} bytes")

    # Determine if it's a ZIP or raw text/CSV
    if raw[:2] == b"PK":
        zf = zipfile.ZipFile(io.BytesIO(raw))
        # Pick the first CSV/TXT inside the ZIP
        csv_name = next(
            (n for n in zf.namelist() if n.lower().endswith((".csv", ".txt", ".nal"))),
            zf.namelist()[0],
        )
        print(f"  reading '{csv_name}' from ZIP")
        content = zf.read(csv_name).decode("latin-1", errors="replace")
    else:
        content = raw.decode("latin-1", errors="replace")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(content))
    header = reader.fieldnames or []
    print(f"  NAL columns: {header[:20]}")

    acct_col = _find_col(list(header), _ACCT_COLS)
    pin_col = _find_col(list(header), _PIN_COLS)

    if not acct_col or not pin_col:
        raise RuntimeError(
            f"Cannot locate account/pin columns in NAL. "
            f"Found: {header[:30]}. "
            f"Expected account in {_ACCT_COLS}, pin in {_PIN_COLS}."
        )

    print(f"  using cols: acct='{acct_col}' pin='{pin_col}'")

    mapping: dict[str, str] = {}
    for row in reader:
        acct = str(row.get(acct_col) or "").strip()
        pin = str(row.get(pin_col) or "").strip()
        if acct and pin and acct in queued:
            mapping[acct] = pin

    return mapping


# ── Strategy B: DOR Cadastral ALT_KEY fallback ────────────────────────────────


def _norm_phy_addr(raw: str) -> str:
    """Normalize PHY_ADDR1 the same way MCA normalizes street_normalized: strip spaces + upcase."""
    return re.sub(r"\s+", "", (raw or "").upper().strip())


def strategy_b_dor(queued: set[str], mca_addrs: dict[str, str]) -> dict[str, str]:
    """Paginate FL DOR Cadastral; return folio→PIN via ALT_KEY or PHY_ADDR1 match.

    mca_addrs: {folio: street_normalized} for all queued accounts — used to
    cross-match DOR PHY_ADDR1 when ALT_KEY lookup fails (e.g. condos).
    """
    print(f"Strategy B: querying FL DOR Cadastral (CO_NO=15, ALT_KEY + PHY_ADDR1)")
    mapping: dict[str, str] = {}
    # Build reverse: normalized_addr → set[folio] for addr-based fallback
    addr_to_folios: dict[str, list[str]] = {}
    for folio, addr in mca_addrs.items():
        if addr:
            addr_to_folios.setdefault(addr, []).append(folio)

    # CO_NO=15 (Brevard) records start at OBJECTID ~279727. Skip the non-Brevard prefix.
    last_oid = 279700
    pages = 0
    phy_matched = 0

    while True:
        where = f"{DOR_WHERE} AND OBJECTID>{last_oid}"
        params = {
            "where": where,
            "outFields": DOR_FIELDS,
            "returnGeometry": "false",
            "resultRecordCount": DOR_BATCH,
            "orderByFields": "OBJECTID ASC",
            "f": "json",
        }
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        req = urllib.request.Request(f"{DOR_URL}?{qs}",
                                     headers={"User-Agent": "Mozilla/5.0 (compatible; BidDeed/1.0)"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            print(f"  DOR page {pages}: {e}", file=sys.stderr)
            time.sleep(5)
            continue

        if "error" in data:
            print(f"  DOR error: {data['error']}", file=sys.stderr)
            break

        features = data.get("features", [])
        if not features:
            break

        pages += 1
        for feat in features:
            attrs = feat.get("attributes", {})
            alt_key = str(attrs.get("ALT_KEY") or "").strip()
            pin = str(attrs.get("PARCEL_ID") or attrs.get("PARCELNO") or "").strip()
            if not pin:
                continue

            # Primary: ALT_KEY = BCPAO folio
            if alt_key and alt_key in queued:
                mapping[alt_key] = pin

            # Secondary: PHY_ADDR1 normalized match (catches condos where ALT_KEY differs)
            phy_raw = attrs.get("PHY_ADDR1") or ""
            if phy_raw and phy_raw.upper() not in ("UNKNOWN", "0 UNKNOWN", ""):
                norm_addr = _norm_phy_addr(phy_raw)
                if norm_addr in addr_to_folios:
                    folios = addr_to_folios[norm_addr]
                    if len(folios) == 1:  # only insert when address is unambiguous
                        folio = folios[0]
                        if folio not in mapping and folio in queued:
                            mapping[folio] = pin
                            phy_matched += 1

        last_oid = features[-1]["attributes"].get("OBJECTID", last_oid)

        if pages % 10 == 0:
            print(f"  page {pages} (OID={last_oid}): alt_key={len(mapping)-phy_matched} phy={phy_matched} total={len(mapping)}/{len(queued)}")

        time.sleep(0.3)

    print(f"  DOR pages: {pages}, alt_key_matched={len(mapping)-phy_matched}, phy_matched={phy_matched}, total={len(mapping)}")
    return mapping


# ── Upsert bridge + mark jobs ─────────────────────────────────────────────────

CHUNK = 200


def upsert_bridge(mapping: dict[str, str], match_method: str) -> int:
    """Upsert folio→PIN rows into brevard_folio_pin_bridge. Returns upserted count."""
    rows = [
        {"folio": folio, "resolved_pin": pin, "match_method": match_method}
        for folio, pin in mapping.items()
    ]
    ok = 0
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        status, body = sb_post(
            BRIDGE_TABLE,
            chunk,
            {"Prefer": "resolution=ignore-duplicates,return=minimal"},
        )
        if status in (200, 201):
            ok += len(chunk)
        else:
            print(f"  bridge upsert chunk {i}: HTTP {status} {body[:200]}", file=sys.stderr)
    return ok


def mark_jobs_done(mapping: dict[str, str]) -> int:
    """Update bcpao_fetch_jobs to done for resolved accounts. Returns updated count."""
    done = 0
    for acct, pin in mapping.items():
        status, _ = sb_patch(
            JOBS_TABLE,
            {"status": "done", "parcel_id": pin},
            f"account=eq.{urllib.parse.quote(acct)}&status=eq.queued",
        )
        if status in (200, 204):
            done += 1
    return done


# ── Main ──────────────────────────────────────────────────────────────────────

import urllib.parse  # noqa: E402  (late import to keep top clean)


def main() -> None:
    queued, mca_addrs = load_queued_accounts()
    if not queued:
        print("No queued accounts — nothing to do.")
        return

    mapping: dict[str, str] = {}
    method_used = ""

    if STRATEGY in ("A", "AUTO"):
        try:
            mapping = strategy_a_nal(queued)
            method_used = "bcpao_nal"
            print(f"Strategy A matched: {len(mapping)}/{len(queued)}")
        except Exception as e:
            print(f"Strategy A failed: {e}", file=sys.stderr)
            if STRATEGY == "A":
                sys.exit(1)
            print("Falling back to Strategy B (DOR Cadastral)...")

    if not mapping and STRATEGY in ("B", "AUTO"):
        mapping = strategy_b_dor(queued, mca_addrs)
        method_used = "dor_altkey"
        print(f"Strategy B matched: {len(mapping)}/{len(queued)}")

    if not mapping:
        print("ERROR: no folios resolved by either strategy", file=sys.stderr)
        sys.exit(1)

    # Upsert bridge
    bridged = upsert_bridge(mapping, method_used)
    print(f"bridge upserted: {bridged}")

    # Mark jobs done
    marked = mark_jobs_done(mapping)
    print(f"jobs marked done: {marked}")

    # Drain into multi_county_auctions
    drained = call_drain()
    print(f"bcpao_folio_drain: {drained} MCA rows updated")

    # Summary
    unresolved = queued - set(mapping.keys())
    print(
        f"\n=== SUMMARY ===\n"
        f"  queued:     {len(queued)}\n"
        f"  resolved:   {len(mapping)}  ({method_used})\n"
        f"  bridged:    {bridged}\n"
        f"  drained:    {drained} MCA rows\n"
        f"  unresolved: {len(unresolved)}"
    )

    if unresolved:
        print(f"  unresolved sample: {sorted(unresolved)[:5]}")

    # Non-zero exit if < 90% resolved (allows some gap for vacant/deleted parcels)
    pct = len(mapping) / len(queued) * 100
    if pct < 90:
        print(
            f"WARNING: only {pct:.1f}% resolved (threshold 90%). "
            "Check NAL column names or DOR data freshness.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
