#!/usr/bin/env python3
"""SHARD-13 escambia C/D fix (2026-07-11 gold-standard fixer session).

Baseline (VERIFIED live this session via pencil_dod_evaluate_county + direct REST
queries against multi_county_auctions): escambia eval-scope (data_source<>'propertyonion')
= 332 rows, 258 matched_clean, 74 gap rows with parity_status IS NULL. All 74 gap rows have
data_source='calendar_sweep_mca_v3':
  - 73 rows sale_type='tax_deed', spanning 5 dates: 2026-08-05 (10), 2026-09-02 (20),
    2026-10-07 (14), 2026-11-04 (10), 2026-12-02 (19).
  - 1 row sale_type='foreclosure', auction_date=2026-07-23, case_number='2025 CA 001478'.
C=D=77.7% at session start (matched_clean=258 / auctions_total=332).

Prior session context (commit 41258467, ~5 min before this one, scripts/
shard_escambia_cd_taxdeed_fix.py): probed escambia.realtaxdeed.com for the same 5 tax_deed
dates, promoted 3 rows via exact case_number match, and VERIFIED the remaining 73 (now)
have zero overlap with live case_number OR parcel_id on realtaxdeed.com -- a genuine,
non-forced gap, not a matcher bug. That script never touched the 1 foreclosure row (07/23),
which is out of its scope (tax_deed-only filter).

This script:
  1. Re-probes escambia.realtaxdeed.com (tax-deed platform, VERIFIED same RealAuction AJAX
     markup as realforeclose.com) for the 5 tax_deed gap dates -- fresh probe in case the
     calendar has updated since the prior run (auction listings can populate/change closer
     to the sale date). Idempotent: only promotes rows not already matched_clean.
  2. Probes escambia.realforeclose.com (foreclosure platform, VERIFIED via existing
     matched_clean rows' parity_source='tier1_realforeclose_escambia' /
     'tier1_realforeclose_aids_escambia') for the single 2026-07-23 foreclosure gap row.
  3. Uses the shared harvest_date_paginated() + exact_match_and_promote() from
     scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py (imported, not
     copy-pasted) -- same exact-case_number-only matching contract as every other shard fix.
  4. Reports exact counts. Any row with zero live overlap after this probe is left
     parity_status IS NULL and documented as an honest residual (auction listed on the
     county calendar for a future date, not yet cross-referenced on the platform, or
     genuinely absent) -- no forced/fuzzy match.

Usage: python3 scripts/shard13_escambia_cd_fix.py
Idempotent: harvest is read-only; promote only PATCHes rows not already matched_clean.
"""
import os
import json
import time
import importlib.util
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "escambia"
SUBDOMAIN = "escambia"

TAXDEED_DOMAIN = "realtaxdeed.com"
TAXDEED_LABEL = "tier1_realtaxdeed_escambia_shard13"

FORECLOSURE_DOMAIN = "realforeclose.com"
FORECLOSURE_LABEL = "tier1_realforeclose_escambia_shard13"


def rest_get(path):
    import urllib.request
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    import urllib.request
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                  "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def promote_matches_scoped(sale_type, items, parity_source_label):
    """Exact normalize_case_number match ONLY, scoped to escambia rows of the given
    sale_type still parity_status IS NULL. Mirrors shard_escambia_cd_taxdeed_fix.py's
    promote_matches() but generalized over sale_type so it also covers the foreclosure
    lane's single gap row."""
    by_norm = {}
    for it in items:
        cn = fixmod.norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.{sale_type}"
        "&parity_status=is.null"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,parity_status")
    matches = []
    for row in mca_rows:
        cn = fixmod.norm_case_number(row["case_number"])
        if cn in by_norm:
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_source_label})
    return matches


def run_lane(sale_type, domain, parity_source_label, dates):
    print(f"\n=== {sale_type} lane: {SUBDOMAIN}.{domain} -- {len(dates)} date(s) ===")
    all_promoted = []
    zero_harvest_dates = []
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, domain)
        print(f"  {d} ({mmddyyyy}): harvested {len(items)} live AITEM records from "
              f"{SUBDOMAIN}.{domain}")
        if items:
            promoted = promote_matches_scoped(sale_type, items, parity_source_label)
            print(f"    promoted {len(promoted)} rows to matched_clean: {promoted}")
            all_promoted.extend(promoted)
            if len(promoted) == 0:
                print(f"    WARNING: parsed {len(items)} live records but promoted 0 for {d} "
                      f"-- live auction exists but no case_number matched our rows for this date.")
        else:
            zero_harvest_dates.append(d)
        time.sleep(0.5)
    return all_promoted, zero_harvest_dates


def main():
    td_null = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.tax_deed"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")
    fc_null = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.foreclosure"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")

    td_dates = sorted({r["auction_date"][:10] for r in td_null if r.get("auction_date")})
    fc_dates = sorted({r["auction_date"][:10] for r in fc_null if r.get("auction_date")})

    print(f"[{datetime.utcnow().isoformat()}] escambia gap: "
          f"tax_deed NULL rows={len(td_null)} across {len(td_dates)} dates {td_dates}; "
          f"foreclosure NULL rows={len(fc_null)} across {len(fc_dates)} dates {fc_dates}")

    td_promoted, td_zero = run_lane("tax_deed", TAXDEED_DOMAIN, TAXDEED_LABEL, td_dates)
    fc_promoted, fc_zero = run_lane("foreclosure", FORECLOSURE_DOMAIN, FORECLOSURE_LABEL, fc_dates)

    total_promoted = td_promoted + fc_promoted
    print(f"\nTOTAL promoted this run: {len(total_promoted)} "
          f"(tax_deed={len(td_promoted)}, foreclosure={len(fc_promoted)})")
    print(f"Zero-harvest dates: tax_deed={td_zero} foreclosure={fc_zero}")
    print(json.dumps({
        "tax_deed_null_targeted": len(td_null),
        "tax_deed_dates": td_dates,
        "tax_deed_promoted": len(td_promoted),
        "tax_deed_promoted_ids": td_promoted,
        "tax_deed_zero_harvest_dates": td_zero,
        "foreclosure_null_targeted": len(fc_null),
        "foreclosure_dates": fc_dates,
        "foreclosure_promoted": len(fc_promoted),
        "foreclosure_promoted_ids": fc_promoted,
        "foreclosure_zero_harvest_dates": fc_zero,
        "total_promoted": len(total_promoted),
    }))


if __name__ == "__main__":
    main()
