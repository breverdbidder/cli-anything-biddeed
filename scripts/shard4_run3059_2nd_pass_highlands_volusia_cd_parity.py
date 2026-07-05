#!/usr/bin/env python3
"""SHARD-4 2nd pass (washington/highlands/volusia/okaloosa/columbia), dispatch
7b631590-6fdc-4e43-acef-8082c3c778d1 (re-fired identical dispatch; original run3059
session already shipped the okaloosa ghost-success purge in commit 32914d63 and
root-caused highlands/volusia C/D without writing anything). This session picks up
the two concrete, bounded next-steps that prior session logged instead of re-doing
completed work.

Confirmed live this session (2026-07-05):
- highlands.realtaxdeed.com and volusia.realtaxdeed.com/realforeclose.com are reachable
  (HTTP 200) from THIS runner with a desktop User-Agent -- the blanket "no live-scrape
  access" note in the prior session's report does not apply here; bare curl without a
  browser UA gets 403 from the WAF (that's what the prior runner likely hit), a proper
  UA does not. columbia clerk (Cloudflare challenge) and okaloosa's two realauction
  subdomains (unprovisioned tenant, redirect to realauction.com marketing splash) are
  STILL blocked exactly as the prior session found -- no new capability there.
- highlands: 15 rows dated auction_date=2026-07-01 (already 4 days past, still
  auction_status='upcoming' -- the status-transition job has not run either) show
  parity_status IS NULL or 'mca_only'. Reusing scripts/shard2_run2450_ajax_realforeclose_harvest.py's
  harvest_date() against highlands.realtaxdeed.com for that exact date returns 19 live
  calendar items; the case numbers exact-match.
- volusia: 21 concluded rows (5 tax_deed dates, 12 foreclosure dates, 1 excluded --
  labeled 'concluded' with auction_date=2026-07-06, i.e. tomorrow, which cannot actually
  be concluded yet; flagged, not touched) with parity_status IS NULL.

Reuses the proven exact-case-number-match pattern from
scripts/shard9_run3059_citrus_manatee_cd_parity.py verbatim (same safe no-fuzzy,
no-parcel-only-arm match). Idempotent: only promotes rows currently NULL/non-tier1.
"""
import os
import sys
import json
import time
import importlib.util
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def exact_match_and_promote(mca_county_filter, items, parity_source_label, restrict_case_numbers=None,
                             auction_date=None):
    """auction_date (YYYY-MM-DD), when given, restricts matching to rows whose OWN
    auction_date column equals the date of the calendar batch being matched against --
    fixes a defect (found by an independent ULTRALOOP refuter, 2026-07-05: volusia case
    12446-19 got date-mismatched, promoted under a different date's calendar batch
    purely because case_number matched fleet-wide with no date guard) where a
    case_number appearing under more than one auction_date for the same county could be
    stamped with the wrong date's parity_source label. Same defect class documented as
    a KNOWN DEFECT in scripts/shard9_run3059_citrus_manatee_cd_parity.py."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    date_filter = f"&auction_date=eq.{auction_date}" if auction_date else ""
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{mca_county_filter}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"{date_filter}"
        f"&select=id,case_number,parity_status,parity_source")
    matches = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if restrict_case_numbers is not None and cn not in restrict_case_numbers:
            continue
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")
        if cn in by_norm and not (row["parity_status"] == "matched_clean" and already_tier1):
            matches.append((row["id"], row["case_number"]))
    if not matches:
        return []
    id_filter = ",".join(str(m[0]) for m in matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_source_label})
    return matches


PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}


def run_targets(targets, label_prefix):
    total_promoted = []
    for t in targets:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date(county, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {county} {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        restrict = {norm_case_number(cn) for cn in t.get("restrict_case_numbers", [])} or None
        matched = exact_match_and_promote(
            county, items, f"tier1:{label_prefix}_ajax_harvest:{sale_type}:{ad}", restrict,
            auction_date=ad)
        total_promoted.extend(matched)
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items -> {len(matched)} promoted: "
              f"{[m[1] for m in matched]}")
        time.sleep(0.4)
    return total_promoted


HIGHLANDS_TARGETS = [
    {"county": "highlands", "sale_type": "tax_deed", "auction_date": "2026-07-01",
     "restrict_case_numbers": [
         "25000610", "25000620", "25000622", "25000623", "25000628", "25000631",
         "25000634", "25000637", "25000641", "25000644", "25000650", "25000661",
         "25000663", "25000666", "25000667"]},
]

VOLUSIA_TARGETS = [
    {"county": "volusia", "sale_type": "tax_deed", "auction_date": "2025-07-15"},
    {"county": "volusia", "sale_type": "tax_deed", "auction_date": "2025-10-21"},
    {"county": "volusia", "sale_type": "tax_deed", "auction_date": "2026-02-03"},
    {"county": "volusia", "sale_type": "tax_deed", "auction_date": "2026-02-10"},
    {"county": "volusia", "sale_type": "tax_deed", "auction_date": "2026-06-09"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-03-10"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-03-11"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-03-13"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-03-17"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-03-24"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-03-25"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-05-15"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-05-19"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-05-21"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-05-27"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-05-28"},
    {"county": "volusia", "sale_type": "foreclosure", "auction_date": "2026-05-29"},
    # 2026-07-06 (2025 22437 COCI) intentionally excluded: labeled 'concluded' but the
    # auction_date is tomorrow relative to this session (2026-07-05) -- cannot actually
    # be concluded yet, a data-quality issue in auction_status, not a parity gap. Logged,
    # not touched.
]


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    promoted = []
    if which in ("highlands", "both"):
        print("=== highlands ===")
        promoted += run_targets(HIGHLANDS_TARGETS, "shard4_run3059_2nd_pass")
    if which in ("volusia", "both"):
        print("=== volusia ===")
        promoted += run_targets(VOLUSIA_TARGETS, "shard4_run3059_2nd_pass")
    print(f"\nTOTAL PROMOTED: {len(promoted)}")
    print(json.dumps([m[1] for m in promoted]))


if __name__ == "__main__":
    main()
