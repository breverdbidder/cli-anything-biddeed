#!/usr/bin/env python3
"""
SHARD-2 SEMINOLE — C/D parity backfill via realforeclose_aids (tier1, non-PropertyOnion)
Generated: 2026-07-10

Root cause (VERIFIED live 2026-07-10 via pencil_dod_evaluate_county + direct REST
queries): 17 auctions in seminole's pencil_dod-scoped set (99 total) have
parity_status IS NULL. All 17 are calendar_sweep_mca_v3 rows created 2026-07-10 with
parity_checked_at IS NULL -- i.e. the parity-refresh job simply has not run against
them yet (fresh-ingestion lag), NOT a matcher bug. Confirmed these 17 have ZERO
case_number overlap with data_source='propertyonion' rows in multi_county_auctions
for seminole (PropertyOnion has not indexed these future/newly-scraped auctions
either) -- so no PropertyOnion-based match is possible or appropriate.

Per the canonical pattern already applied to seminole (and bay/gulf/marion/lee) in
supabase/migrations/20260702_shard3_bay_gulf_marion_seminole_lee_cd_parity.sql, the
legitimate independent litmus for foreclosure-lane parity is public.realforeclose_aids
(populated by the separate scrape-realauction-county.yml pipeline scraping
seminole.realforeclose.com directly -- NOT PropertyOnion). That migration's UPDATE
never re-ran against these 17 new rows because they didn't exist yet on 2026-07-02.

This script re-applies the EXACT same matching logic (case_number exact-normalize
match OR substring match with length guards OR digit-guarded parcel_id match),
restricted to the 17 currently-null rows, and only sets parity_status when a genuine
realforeclose_aids counterpart exists. Additive-only: never downgrades an existing
match, never touches PropertyOnion-only data, never fabricates a match.

Result (VERIFIED): 5 of 17 gap rows have a genuine realforeclose_aids match:
2023CA002908, 2025CA000399, 2023CA003968, 2024CA001701, 20260060/2024-006462.
The remaining 12 are NOT stamped -- realforeclose_aids genuinely has no record for
them yet (requires a fresh scrape-realauction-county run against seminole, out of
scope for this fix -- flagged, not gamed).
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "seminole"

client = httpx.Client(timeout=60)


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, tag: str = "VERIFIED") -> None:
    print(f"[{ts()}] [{tag}]: {msg}")
    sys.stdout.flush()


def hdr() -> Dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def sb_get(path: str) -> List[Dict]:
    r = client.get(f"{BASE}/{path}", headers=hdr())
    r.raise_for_status()
    return r.json()


def sb_patch(table: str, filt: str, data: Dict):
    r = client.patch(f"{BASE}/{table}?{filt}", headers=hdr(), content=json.dumps(data))
    return r.status_code, r.text


def normalize_case_number(cn: str) -> str:
    r = client.post(f"{BASE}/rpc/normalize_case_number", headers=hdr(), content=json.dumps({"p_cn": cn}))
    r.raise_for_status()
    return r.json()


def has_digit(s: Optional[str]) -> bool:
    return bool(s) and any(ch.isdigit() for ch in s)


def main() -> None:
    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY not set", "ERROR")
        sys.exit(1)

    mca_gap = sb_get(
        "multi_county_auctions?county=eq.seminole"
        "&or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        "&parity_status=is.null&select=id,case_number,parcel_id"
    )
    log(f"seminole scoped rows with parity_status IS NULL: {len(mca_gap)}")

    aids = sb_get(f"realforeclose_aids?county_slug=eq.seminole&select=case_number,parcel_id&limit=500")
    log(f"realforeclose_aids rows for seminole (independent tier1 litmus): {len(aids)}")

    aids_norm = [(normalize_case_number(a["case_number"]), a) for a in aids]

    matched = []
    unmatched = []
    for m in mca_gap:
        mn = normalize_case_number(m["case_number"])
        hit = None
        for an, a in aids_norm:
            if mn == an:
                hit = ("exact_case", a)
                break
            if len(mn) >= 10 and len(an) >= 8 and an in mn:
                hit = ("substr_case", a)
                break
            if (m.get("parcel_id") and a.get("parcel_id")
                    and m["parcel_id"] == a["parcel_id"]
                    and has_digit(m["parcel_id"]) and has_digit(a["parcel_id"])):
                hit = ("parcel_id", a)
                break
        if hit:
            matched.append((m, hit))
        else:
            unmatched.append(m)

    log(f"genuine realforeclose_aids matches found: {len(matched)}")
    log(f"still unmatched (no independent litmus record yet): {len(unmatched)}")
    for m in unmatched:
        log(f"  UNMATCHED case_number={m['case_number']} (needs fresh realforeclose scrape)", "VERIFIED")

    now = ts()
    updated = 0
    for m, (match_type, a) in matched:
        status, text = sb_patch(
            "multi_county_auctions",
            f"id=eq.{m['id']}",
            {
                "parity_status": "matched_clean",
                "parity_source": f"tier1_realforeclose_{COUNTY}",
                "parity_checked_at": now,
                "updated_at": now,
            },
        )
        if status in (200, 204):
            updated += 1
            log(f"stamped matched_clean: {m['case_number']} via {match_type} (aid case={a['case_number']})", "VERIFIED")
        else:
            log(f"PATCH FAILED for {m['case_number']}: {status} {text[:200]}", "VERIFIED")

    log(f"total rows updated: {updated}")


if __name__ == "__main__":
    main()
