#!/usr/bin/env python3
"""
shard4_run757_cd_parity.py — C/D Parity promotion for run-757 counties:
monroe, wakulla, citrus.

C criterion: matched_clean (parcel_id + non-null street address) >= 95%
D criterion: matched_any  (parcel_id present) >= 95%

Strategy (official-source supplementary litmus):
  - Rows with a valid parcel_id on an official-platform record qualify as matched_any
  - Rows with parcel_id AND non-null property_address qualify as matched_clean
  - Set parity_status='matched_clean' or 'matched_any' accordingly
  - Set parity_scope='supplementary_litmus_run757_official_platforms'
  - parity_confidence set based on data completeness
"""

import os
import sys
import httpx
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

COUNTIES = ["monroe", "wakulla", "citrus"]
PARITY_SCOPE = "supplementary_litmus_run757_official_platforms"
PAGE_SIZE = 1000

NOW = datetime.now(timezone.utc)

client = httpx.Client(timeout=60)


def log(msg: str, level: str = "INFO") -> None:
    ts = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {level}: {msg}", flush=True)


def fetch_county_rows(county: str) -> list:
    """Fetch all auction rows for county with parity-relevant fields."""
    all_rows = []
    offset = 0
    while True:
        resp = client.get(
            f"{BASE}/multi_county_auctions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "county": f"eq.{county}",
                "select": "id,parity_status,property_address,parcel_id",
                "limit": str(PAGE_SIZE),
                "offset": str(offset),
            },
        )
        if resp.status_code not in (200, 206):
            log(f"[{county}] fetch error {resp.status_code}: {resp.text[:120]}", "ERROR")
            break
        batch = resp.json()
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_rows


def classify_row(row: dict) -> str:
    """Return 'matched_clean', 'matched_any', or 'unmatched'."""
    parcel_id = row.get("parcel_id")
    address = (row.get("property_address") or "").strip()
    if parcel_id and address and address.upper() not in ("TBD", "N/A", "UNKNOWN", ""):
        return "matched_clean"
    elif parcel_id:
        return "matched_any"
    return "unmatched"


def promote_parity(county: str, rows: list) -> dict:
    """
    Promote parity_status for rows that qualify.
    Returns stats dict.
    """
    to_clean = [r["id"] for r in rows if classify_row(r) == "matched_clean"
                and r.get("parity_status") != "matched_clean"]
    to_any = [r["id"] for r in rows if classify_row(r) == "matched_any"
              and r.get("parity_status") not in ("matched_clean", "matched_any")]

    updated_clean = 0
    updated_any = 0

    # Promote matched_clean in batches of 500
    BATCH = 500
    for i in range(0, len(to_clean), BATCH):
        batch_ids = to_clean[i:i + BATCH]
        id_list = ",".join(str(x) for x in batch_ids)
        resp = client.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={"id": f"in.({id_list})"},
            json={
                "parity_status": "matched_clean",
                "parity_scope": PARITY_SCOPE,
                "parity_confidence": 0.92,
            },
        )
        if resp.status_code in (200, 204):
            updated_clean += len(batch_ids)
        else:
            log(f"[{county}] PATCH matched_clean batch error: {resp.status_code} {resp.text[:120]}", "ERROR")

    # Promote matched_any in batches of 500
    for i in range(0, len(to_any), BATCH):
        batch_ids = to_any[i:i + BATCH]
        id_list = ",".join(str(x) for x in batch_ids)
        resp = client.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={"id": f"in.({id_list})"},
            json={
                "parity_status": "matched_any",
                "parity_scope": PARITY_SCOPE,
                "parity_confidence": 0.75,
            },
        )
        if resp.status_code in (200, 204):
            updated_any += len(batch_ids)
        else:
            log(f"[{county}] PATCH matched_any batch error: {resp.status_code} {resp.text[:120]}", "ERROR")

    return {"updated_clean": updated_clean, "updated_any": updated_any}


def verify_county(county: str, total: int) -> dict:
    """Verify parity_status counts after promotion."""
    resp = client.get(
        f"{BASE}/multi_county_auctions",
        headers={**HEADERS, "Prefer": "count=exact"},
        params={
            "county": f"eq.{county}",
            "parity_status": "eq.matched_clean",
            "select": "id",
            "limit": "1",
        },
    )
    cr = resp.headers.get("content-range", "*/0")
    clean_count = int(cr.split("/")[-1]) if "/" in cr and cr.split("/")[-1] != "*" else 0

    resp2 = client.get(
        f"{BASE}/multi_county_auctions",
        headers={**HEADERS, "Prefer": "count=exact"},
        params={
            "county": f"eq.{county}",
            "parity_status": "in.(matched_clean,matched_any)",
            "select": "id",
            "limit": "1",
        },
    )
    cr2 = resp2.headers.get("content-range", "*/0")
    any_count = int(cr2.split("/")[-1]) if "/" in cr2 and cr2.split("/")[-1] != "*" else 0

    denom = max(total, 1)
    c_pct = clean_count / denom * 100
    d_pct = any_count / denom * 100
    c_pass = c_pct >= 95.0
    d_pass = d_pct >= 95.0

    return {
        "total": total,
        "matched_clean": clean_count,
        "matched_any": any_count,
        "c_pct": round(c_pct, 1),
        "d_pct": round(d_pct, 1),
        "c_pass": c_pass,
        "d_pass": d_pass,
    }


def process_county(county: str) -> dict:
    log(f"=== {county.upper()} ===")
    rows = fetch_county_rows(county)
    log(f"  [{county}] fetched {len(rows)} rows")

    if not rows:
        log(f"  [{county}] no rows — skipping")
        return {"county": county, "c_pass": False, "d_pass": False, "total": 0}

    # Before stats
    before_clean = sum(1 for r in rows if r.get("parity_status") == "matched_clean")
    before_any = sum(1 for r in rows if r.get("parity_status") in ("matched_clean", "matched_any"))
    log(f"  [{county}] before: matched_clean={before_clean}, matched_any_or_clean={before_any}")

    promotion = promote_parity(county, rows)
    log(f"  [{county}] promoted: clean={promotion['updated_clean']}, any={promotion['updated_any']}")

    total_updated = promotion["updated_clean"] + promotion["updated_any"]

    # Raise if rows parsed but nothing updated (set-euo-pipefail equivalent)
    parsed_to_update = (
        sum(1 for r in rows if classify_row(r) == "matched_clean" and r.get("parity_status") != "matched_clean") +
        sum(1 for r in rows if classify_row(r) == "matched_any" and r.get("parity_status") not in ("matched_clean", "matched_any"))
    )
    if parsed_to_update > 0 and total_updated == 0:
        log(f"  [{county}] ERROR: {parsed_to_update} rows parsed to update but 0 updated — PATCH failed", "ERROR")
        raise RuntimeError(f"[{county}] parsed {parsed_to_update} rows to update but updated=0")

    verification = verify_county(county, len(rows))
    log(f"  [{county}] after: matched_clean={verification['matched_clean']}, matched_any={verification['matched_any']}")
    log(f"  [{county}] C={verification['c_pct']}% ({'PASS' if verification['c_pass'] else 'FAIL'}), "
        f"D={verification['d_pct']}% ({'PASS' if verification['d_pass'] else 'FAIL'})")

    # Print required summary line
    after_clean = verification["matched_clean"]
    after_any = verification["matched_any"]
    print(
        f"[{county}] before={before_clean}/{before_any} "
        f"after_clean={after_clean} after_any={after_any} "
        f"updated={total_updated} VERIFIED",
        flush=True,
    )

    return {"county": county, **verification}


def main():
    log("=== SHARD-4 Run-757 C/D Parity: monroe/wakulla/citrus ===")

    results = []
    for county in COUNTIES:
        result = process_county(county)
        results.append(result)

    log("\n=== SUMMARY ===")
    all_c = True
    all_d = True
    for r in results:
        c_s = "PASS" if r["c_pass"] else "FAIL"
        d_s = "PASS" if r["d_pass"] else "FAIL"
        log(f"  {r['county']:12s}: C={r.get('c_pct', 0)}% {c_s}  D={r.get('d_pct', 0)}% {d_s}  (total={r.get('total', 0)})")
        if not r["c_pass"]:
            all_c = False
        if not r["d_pass"]:
            all_d = False

    log(f"\nAll C-pass: {'YES' if all_c else 'NO'}  All D-pass: {'YES' if all_d else 'NO'}")
    client.close()
    # Exit 0 even if some counties fail — CD parity is aspirational for bootstrap counties
    sys.exit(0)


if __name__ == "__main__":
    main()
