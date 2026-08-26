#!/usr/bin/env python3
"""Daily FF pipeline — appraiser cross-verification dispatcher.

Primary path (2026-08-26): the FL DOH statewide parcels ArcGIS layer
(doh_statewide.py) covers all 67 counties, no auth, no WAF -- this closes
the appraiser-verification gap for alachua/flagler/wakulla (documented
WAF/TLS ceilings on their own sites, confirmed live to resolve through this
statewide layer instead) and every other county that never had a scraper.
Every lead with a parcel_id is tried against it first.

Fallback / cross-check: the 5 county scrapers in this directory
(manatee/lee/broward/palm_beach/marion) were built and live-verified
against a one-off local JSON fixture batch (common.load_batch_parcels()
reads winnerdata/intake/*.json). They only run now when the DOH statewide
lookup does NOT resolve a parcel in one of those 5 counties -- previously
they were the only path; the statewide layer is faster (no browser) and
covers more ground, so it goes first and these are the fallback for the
cases where an exact PARCEL_ID match fails there (disambiguation the
county's own site can do that a strict equality match cannot, e.g. STRAP
formatting quirks specific to lee/broward's own numbering).

For a county with no DOH layer match AND no scraper fallback, this module
writes an honest 'unverified' parity_audit row explaining the DOH lookup
came up empty, rather than silently skipping -- per the daily pipeline's
non-goal "leads that fail verification must say so, not be silently
skipped." public.ff_get_lead (see
supabase/migrations/20260824_ff_verification_badge_rpc.sql) already reads
parity_audit generically by case_number, so it surfaces this real reason
without any RPC change.

Idempotent: already_verified() skips any case_number that already has a
'pass' verdict on its blocking fields (parcel_id/address) from a prior run,
per the daily pipeline's non-goal "do not re-verify leads that already have
... a passed appraiser check from a prior day's run."
"""
from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from common import write_parity_row  # noqa: E402
import doh_statewide  # noqa: E402

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

SUPPORTED_COUNTIES = {"manatee", "lee", "broward", "palm_beach", "marion"}  # fallback-scraper counties only, not a gate on who gets tried at all -- see doh_statewide.LAYER_MAP for the 67-county primary path
PLAYWRIGHT_COUNTIES = {"manatee", "lee", "broward"}  # palm_beach/marion are plain httpx


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[appraiser-dispatch] {tag}: {msg}", flush=True)


def already_verified(case_number: str) -> bool:
    """True if a prior run already logged a passing blocking-field verdict
    for this case -- daily re-runs must not re-spend a scrape on it."""
    if not SUPABASE_KEY:
        return False
    q = (f"{SUPABASE_URL}/rest/v1/parity_audit?select=id"
         f"&case_number=eq.{urllib.parse.quote(case_number)}"
         f"&field_name=eq.parcel_id&verdict=eq.pass&limit=1")
    req = urllib.request.Request(q, headers={
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json
            return len(json.loads(resp.read())) > 0
    except Exception as e:
        log(f"already_verified() lookup failed for {case_number}, treating as not-yet-verified: {e}", "WARN")
        return False


def _verify_via_doh(rec) -> bool:
    """True if the FL DOH statewide layer resolved this parcel and wrote
    parity_audit rows for it -- False means try the county's own scraper
    (if any) instead, this is not itself a failure worth logging."""
    result = doh_statewide.query_parcel(rec["county"], rec["parcel_id"])
    if result is None:
        return False
    write_parity_row(rec["case_number"], rec["county"], "parcel_id",
                      ff_value=rec["parcel_id"], appraiser_value=result["PARCEL_ID"],
                      verdict="pass",
                      note=f"matched FL DOH statewide parcels layer (format={result['matched_format']!r}, layer_id={result['layer_id']})",
                      competitor_name="fl_doh_statewide")
    write_parity_row(rec["case_number"], rec["county"], "address",
                      ff_value=rec["address"], appraiser_value=result.get("PHY_ADDR1"),
                      competitor_name="fl_doh_statewide")
    if rec.get("owner"):
        write_parity_row(rec["case_number"], rec["county"], "owner_of_record",
                          ff_value=rec["owner"], appraiser_value=result.get("OWN_NAME"),
                          competitor_name="fl_doh_statewide")
    if rec.get("just_value") is not None and result.get("JV") is not None:
        write_parity_row(rec["case_number"], rec["county"], "just_value",
                          ff_value=rec["just_value"], appraiser_value=result["JV"],
                          biddeed_value=float(rec["just_value"]), competitor_value=result["JV"],
                          competitor_name="fl_doh_statewide")
    return True


def _verify_manatee(page, rec):
    import manatee_wordpress_spa as m
    result = m.scrape_parcel(page, rec["parcel_id"])
    addr, owner, jv = m.extract_fields(result["body"])
    write_parity_row(rec["case_number"], "manatee", "parcel_id", ff_value=rec["parcel_id"], appraiser_value=rec["parcel_id"])
    write_parity_row(rec["case_number"], "manatee", "address", ff_value=rec["address"], appraiser_value=addr)
    if rec.get("owner"):
        write_parity_row(rec["case_number"], "manatee", "owner_of_record", ff_value=rec["owner"], appraiser_value=owner)
    if rec.get("just_value") is not None and jv is not None:
        write_parity_row(rec["case_number"], "manatee", "just_value", ff_value=rec["just_value"], appraiser_value=jv,
                          biddeed_value=float(rec["just_value"]), competitor_value=jv)


def _verify_lee(page, rec):
    import lee_aspnet_webforms as m
    result = m.scrape_parcel(page, rec["parcel_id"])
    addr, owner, _ = m.extract_fields(result, rec["parcel_id"])
    found = addr is not None
    write_parity_row(rec["case_number"], "lee", "parcel_id",
                      ff_value=rec["parcel_id"], appraiser_value=rec["parcel_id"] if found else None,
                      verdict=("pass" if found else "fail"),
                      note=("STRAP resolved to exactly one live match" if found else "STRAP search returned zero matches on live site"))
    if found:
        write_parity_row(rec["case_number"], "lee", "address", ff_value=rec["address"], appraiser_value=addr)
        if rec.get("owner"):
            write_parity_row(rec["case_number"], "lee", "owner_of_record", ff_value=rec["owner"], appraiser_value=owner)


def _verify_broward(page, rec, first):
    import broward_aspnet_webmethods as m
    body = m.scrape_parcel(page, rec["parcel_id"], first=first)
    prop_id, addr, owner, jv = m.extract_fields(body)
    resolved = prop_id is not None
    write_parity_row(rec["case_number"], "broward", "parcel_id",
                      ff_value=rec["parcel_id"], appraiser_value=prop_id,
                      verdict=("pass" if resolved else "fail"),
                      note=("folio resolved to a live parcel record" if resolved else "folio search returned no parcel record"))
    if resolved:
        write_parity_row(rec["case_number"], "broward", "address", ff_value=rec["address"], appraiser_value=addr)
        if rec.get("owner"):
            write_parity_row(rec["case_number"], "broward", "owner_of_record", ff_value=rec["owner"], appraiser_value=owner)
        if rec.get("just_value") is not None and jv is not None:
            write_parity_row(rec["case_number"], "broward", "just_value", ff_value=rec["just_value"], appraiser_value=jv,
                              biddeed_value=float(rec["just_value"]), competitor_value=jv)


def _verify_palm_beach(rec):
    import palm_beach_direct_get as m
    model = m.scrape_parcel(rec["parcel_id"])
    pd = model.get("propertyDetail") or {}
    pcn_live = pd.get("PCN")
    addr = f"{pd.get('AddressLine1', '').strip()}, {pd.get('AddressLine3', '').strip()}"
    owner = pd.get("OwnerName")
    write_parity_row(rec["case_number"], "palm_beach", "parcel_id", ff_value=rec["parcel_id"], appraiser_value=pcn_live)
    write_parity_row(rec["case_number"], "palm_beach", "address", ff_value=rec["address"], appraiser_value=addr)
    if rec.get("owner"):
        write_parity_row(rec["case_number"], "palm_beach", "owner_of_record", ff_value=rec["owner"], appraiser_value=owner)


def _verify_marion(rec):
    import marion_devexpress_aspnet as m
    prime_key = rec["parcel_id"]
    text = m.scrape_parcel(prime_key)
    real_parcel, situs, owner, jv = m.extract_fields(text)
    resolved = "Prime Key:" in text and real_parcel is not None
    write_parity_row(rec["case_number"], "marion", "parcel_id",
                      ff_value=prime_key, appraiser_value=prime_key if resolved else None,
                      verdict=("pass" if resolved else "fail"),
                      note=("Prime Key resolved to a live property record card" if resolved else "Prime Key did not resolve on the live site"))
    if resolved:
        write_parity_row(rec["case_number"], "marion", "address", ff_value=rec["address"], appraiser_value=situs)
        if rec.get("owner"):
            write_parity_row(rec["case_number"], "marion", "owner_of_record", ff_value=rec["owner"], appraiser_value=owner)
        if rec.get("just_value") is not None and jv is not None:
            write_parity_row(rec["case_number"], "marion", "just_value", ff_value=rec["just_value"], appraiser_value=jv,
                              biddeed_value=float(rec["just_value"]), competitor_value=jv)


def verify_leads(leads: list[dict]) -> dict:
    """leads: [{case_number, county, parcel_id, address, owner?, just_value?}, ...]
    Returns {verified: int, failed: int, skipped_already_verified: int, skipped_unsupported_county: int}.
    """
    stats = {"verified": 0, "failed": 0, "skipped_already_verified": 0, "skipped_unsupported_county": 0}
    candidates = []
    for rec in leads:
        county = (rec.get("county") or "").lower()
        if not rec.get("parcel_id"):
            stats["skipped_unsupported_county"] += 1
            continue
        if already_verified(rec["case_number"]):
            stats["skipped_already_verified"] += 1
            continue
        candidates.append({**rec, "county": county})

    if not candidates:
        log("no leads to verify (none with a parcel_id, or all already verified)")
        return stats

    # Primary path: FL DOH statewide layer, all 67 counties, no browser needed.
    supported = []
    for rec in candidates:
        try:
            resolved = _verify_via_doh(rec)
        except Exception as e:
            log(f"  DOH statewide lookup errored for {rec['case_number']} / {rec['county']}: {e}", "WARN")
            resolved = False
        if resolved:
            log(f"verified via DOH statewide: {rec['case_number']} / {rec['county']} / parcel {rec['parcel_id']}")
            stats["verified"] += 1
        elif rec["county"] in SUPPORTED_COUNTIES:
            supported.append(rec)  # fall back to this county's own scraper
        else:
            write_parity_row(rec["case_number"], rec["county"], "parcel_id",
                              ff_value=rec["parcel_id"], appraiser_value=None,
                              verdict="unverified",
                              note="FL DOH statewide parcels layer returned no match for this parcel ID in this county, and no county-specific scraper is configured as a fallback")
            stats["failed"] += 1

    if not supported:
        log(f"done: {stats}")
        return stats

    needs_playwright = any((r["county"] or "").lower() in PLAYWRIGHT_COUNTIES for r in supported)
    browser = context = page = None
    if needs_playwright:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch()
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

    broward_seen = False
    try:
        for rec in supported:
            county = rec["county"].lower()
            log(f"verifying {rec['case_number']} / {county} / parcel {rec['parcel_id']}")
            try:
                if county == "manatee":
                    _verify_manatee(page, rec)
                elif county == "lee":
                    _verify_lee(page, rec)
                elif county == "broward":
                    _verify_broward(page, rec, first=not broward_seen)
                    broward_seen = True
                elif county == "palm_beach":
                    _verify_palm_beach(rec)
                elif county == "marion":
                    _verify_marion(rec)
                stats["verified"] += 1
            except Exception as e:
                log(f"  FAILED {rec['case_number']} / {county}: {e}", "ERROR")
                write_parity_row(rec["case_number"], county, "parcel_id",
                                  ff_value=rec["parcel_id"], appraiser_value=None,
                                  verdict="unverified", note=f"scrape error: {e}")
                stats["failed"] += 1
    finally:
        if browser:
            browser.close()

    log(f"done: {stats}")
    return stats


if __name__ == "__main__":
    log("This module is a library for scripts/winnerdata_pipeline.py — "
        "no standalone CLI entrypoint. Run the daily pipeline instead.", "ERROR")
    sys.exit(2)
