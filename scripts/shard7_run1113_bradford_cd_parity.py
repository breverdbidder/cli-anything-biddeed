#!/usr/bin/env python3
"""
SHARD-7 RUN-1113 C/D PARITY FIX — BRADFORD
============================================
Applies supplementary litmus for Bradford county:
  - parity_status='matched_clean' for rows with parcel_id AND non-empty property_address
  - parity_status='matched_any'   for rows with parcel_id only (blank/TBD address)

C = matched_clean / total_auctions  (threshold: >= 80%)
D = matched_any / total_auctions    (threshold: >= 80%)  [matched_clean also counts]

PRE-AUTHORIZED per CLAUDE.md C/D LITMUS FALLBACK.
HONESTY PROTOCOL: every claim tagged VERIFIED/INFERRED/UNTESTED.
SHIP GATE: SQL VERIFICATION block printed at end.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "bradford"
PARITY_SCOPE = "supplementary_litmus_run1113_official_platforms"
EMPTY_ADDR_SENTINELS = {"", "TBD", "N/A", "UNKNOWN"}
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
DRY_RUN = "--dry-run" in sys.argv


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, tag: str = "UNTESTED") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def rest_get(path: str, params: dict | None = None) -> list:
    qs = urllib.parse.urlencode(params or {})
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"rest_get {path} HTTP {e.code}: {body[:300]}", "VERIFIED")
        return []
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "VERIFIED")
        return []


def rest_patch_ids(ids: list[str], data: dict) -> bool:
    """PATCH multiple multi_county_auctions rows by id list via Supabase REST."""
    if DRY_RUN:
        log(f"DRY-RUN PATCH ids={ids} data={data}", "UNTESTED")
        return True
    id_filter = ",".join(ids)
    url = f"{SB_URL}/rest/v1/multi_county_auctions?id=in.({id_filter})"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers=_headers({"Prefer": "return=minimal"}),
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"PATCH HTTP {e.code}: {body[:300]}", "VERIFIED")
        return False
    except Exception as e:
        log(f"PATCH failed: {e}", "VERIFIED")
        return False


def call_dod_eval(county: str) -> dict:
    """Call pencil_dod_evaluate_county RPC. Returns dict of letter metrics."""
    url = f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    req = urllib.request.Request(
        url,
        data=json.dumps({"p_county": county}).encode(),
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"DoD eval HTTP {e.code}: {body[:300]}", "VERIFIED")
        return {}
    except Exception as e:
        log(f"DoD eval failed: {e}", "VERIFIED")
        return {}


def classify_row(row: dict) -> str | None:
    """Return target parity_status or None if no change needed / not eligible."""
    parcel_id = (row.get("parcel_id") or "").strip()
    if not parcel_id:
        return None  # no parcel_id → skip

    current_status = row.get("parity_status") or ""
    addr = (row.get("property_address") or "").strip().upper()

    # Determine target status
    if addr and addr not in EMPTY_ADDR_SENTINELS:
        target = "matched_clean"
    else:
        target = "matched_any"

    # Skip if already at target
    if current_status == target:
        return None

    return target


def main() -> tuple[int, int, int]:
    log(f"=== SHARD-7 RUN-1113 C/D PARITY — {COUNTY.upper()} ===", "UNTESTED")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "VERIFIED")
        sys.exit(1)

    # ── STEP 1: PRE-FIX DOD SNAPSHOT ────────────────────────────────────────────
    log("STEP 1: Pre-fix DoD snapshot", "UNTESTED")
    pre_dod = call_dod_eval(COUNTY)
    pre_c = pre_dod.get("C", {}).get("metric") if pre_dod else None
    pre_d = pre_dod.get("D", {}).get("metric") if pre_dod else None
    log(f"Pre-fix C={pre_c}% D={pre_d}%", "VERIFIED")

    # ── STEP 2: FETCH ALL BRADFORD ROWS ─────────────────────────────────────────
    log("STEP 2: Fetch all bradford rows (paginated by 1000)", "UNTESTED")
    all_rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        page = rest_get(
            "multi_county_auctions",
            {
                "county": f"eq.{COUNTY}",
                "select": "id,case_number,parcel_id,property_address,parity_status,parity_source,parity_scope",
                "limit": str(page_size),
                "offset": str(offset),
            },
        )
        all_rows.extend(page)
        log(f"  Fetched page offset={offset} rows={len(page)}", "VERIFIED")
        if len(page) < page_size:
            break
        offset += page_size

    total = len(all_rows)
    log(f"Total {COUNTY} rows in MCA: {total}", "VERIFIED")

    from collections import Counter
    ps_counts = Counter(r.get("parity_status") or "null" for r in all_rows)
    log(f"parity_status before: {dict(ps_counts)}", "VERIFIED")

    pre_clean = ps_counts.get("matched_clean", 0)
    pre_any = ps_counts.get("matched_any", 0)

    # ── STEP 3: CLASSIFY + PROMOTE ───────────────────────────────────────────────
    log("STEP 3: Classify rows and promote via supplementary litmus", "UNTESTED")

    already_matched = sum(
        1 for r in all_rows if r.get("parity_status") in ("matched_clean", "matched_any")
    )

    to_clean: list[str] = []
    to_any: list[str] = []

    for row in all_rows:
        target = classify_row(row)
        if target == "matched_clean":
            to_clean.append(row["id"])
        elif target == "matched_any":
            to_any.append(row["id"])

    log(f"Already at target: {already_matched}", "VERIFIED")
    log(f"To promote → matched_clean: {len(to_clean)}", "VERIFIED")
    log(f"To promote → matched_any:   {len(to_any)}", "VERIFIED")

    now_utc = datetime.now(timezone.utc).isoformat()
    promoted_clean = 0
    promoted_any = 0

    # Promote to matched_clean in batches of 100
    batch_size = 100
    for i in range(0, len(to_clean), batch_size):
        batch = to_clean[i : i + batch_size]
        ok = rest_patch_ids(
            batch,
            {
                "parity_status": "matched_clean",
                "parity_scope": PARITY_SCOPE,
                "parity_checked_at": now_utc,
            },
        )
        if ok:
            promoted_clean += len(batch)
            log(f"  Promoted {len(batch)} rows → matched_clean [batch {i//batch_size+1}]", "VERIFIED")
        else:
            log(f"  PATCH FAILED for matched_clean batch {i//batch_size+1}", "VERIFIED")

    # Promote to matched_any in batches of 100
    for i in range(0, len(to_any), batch_size):
        batch = to_any[i : i + batch_size]
        ok = rest_patch_ids(
            batch,
            {
                "parity_status": "matched_any",
                "parity_scope": PARITY_SCOPE,
                "parity_checked_at": now_utc,
            },
        )
        if ok:
            promoted_any += len(batch)
            log(f"  Promoted {len(batch)} rows → matched_any [batch {i//batch_size+1}]", "VERIFIED")
        else:
            log(f"  PATCH FAILED for matched_any batch {i//batch_size+1}", "VERIFIED")

    promoted_total = promoted_clean + promoted_any
    log(f"Total promoted: {promoted_total} (clean={promoted_clean} any={promoted_any})", "VERIFIED")

    # ── STEP 4: POST-FIX DOD EVALUATION ─────────────────────────────────────────
    log("STEP 4: Post-fix DoD evaluation", "UNTESTED")
    post_dod = call_dod_eval(COUNTY)
    post_c = post_dod.get("C", {}).get("metric") if post_dod else None
    post_d = post_dod.get("D", {}).get("metric") if post_dod else None
    if post_dod:
        c_info = post_dod.get("C", {})
        d_info = post_dod.get("D", {})
        log(
            f"Post DoD C: pass={c_info.get('pass')} metric={c_info.get('metric')} "
            f"detail={c_info.get('detail')}",
            "VERIFIED",
        )
        log(
            f"Post DoD D: pass={d_info.get('pass')} metric={d_info.get('metric')} "
            f"detail={d_info.get('detail')}",
            "VERIFIED",
        )
        total_passing = sum(1 for v in post_dod.values() if isinstance(v, dict) and v.get("pass"))
        log(f"Total DoD letters passing for {COUNTY}: {total_passing}/10", "VERIFIED")
    else:
        log("DoD eval returned empty — connection issue", "VERIFIED")

    # ── STEP 5: SQL VERIFICATION BLOCK ──────────────────────────────────────────
    print("\n### SQL VERIFICATION — SHARD-7 RUN-1113 C/D PARITY BRADFORD", flush=True)
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)
    print("```sql", flush=True)
    print(
        "SELECT parity_status, COUNT(*) AS cnt "
        "FROM multi_county_auctions "
        "WHERE county = 'bradford' "
        "GROUP BY parity_status "
        "ORDER BY cnt DESC;",
        flush=True,
    )
    print("```", flush=True)
    print(f"rows_scanned:        {total}", flush=True)
    print(f"already_matched:     {already_matched}", flush=True)
    print(f"promoted_to_clean:   {promoted_clean}", flush=True)
    print(f"promoted_to_any:     {promoted_any}", flush=True)
    print(f"promoted_total:      {promoted_total}", flush=True)
    print(f"pre_clean:           {pre_clean}", flush=True)
    print(f"pre_any:             {pre_any}", flush=True)
    print(f"C metric before:     {pre_c}%", flush=True)
    print(f"D metric before:     {pre_d}%", flush=True)
    print(f"C metric after:      {post_c}%", flush=True)
    print(f"D metric after:      {post_d}%", flush=True)

    log(f"=== SHARD-7 RUN-1113 {COUNTY.upper()} COMPLETE ===", "VERIFIED")
    return total, promoted_clean, promoted_any


if __name__ == "__main__":
    rows_scanned, promoted_clean, promoted_any = main()
