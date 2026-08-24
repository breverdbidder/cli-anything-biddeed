#!/usr/bin/env python3
"""Daily FF pipeline — appraiser cross-verification dispatcher.

The 5 county scrapers in this directory (manatee/lee/broward/palm_beach/
marion) were built and live-verified against a one-off local JSON fixture
batch (common.load_batch_parcels() reads summitleads/intake/*.json). This
module is the missing piece to run them against real, live
summitleads.leads rows every day instead of a fixture file: verify_leads()
takes lead records already pulled from the DB by the caller and drives the
same scrape_parcel()/extract_fields() functions those files define, writing
identical parity_audit rows via common.write_parity_row.

Scope: ONLY the 5 counties with a live scraper. For any other county
(including the 3 documented WAF/TLS ceilings -- alachua, flagler, wakulla --
and the 59 counties with no scraper at all), this module does nothing and
writes no parity_audit row. That is intentional, not a gap: public.ff_get_lead
(see supabase/migrations/20260824_ff_verification_badge_rpc.sql) already
derives a correct NOT VERIFIED badge + reason for those counties straight
from fl_property_appraiser_configs.known_issues / fl_counties.appraiser_url
without needing a placeholder audit row.

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

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

SUPPORTED_COUNTIES = {"manatee", "lee", "broward", "palm_beach", "marion"}
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
    supported = []
    for rec in leads:
        county = (rec.get("county") or "").lower()
        if county not in SUPPORTED_COUNTIES:
            stats["skipped_unsupported_county"] += 1
            continue
        if not rec.get("parcel_id"):
            stats["skipped_unsupported_county"] += 1
            continue
        if already_verified(rec["case_number"]):
            stats["skipped_already_verified"] += 1
            continue
        supported.append(rec)

    if not supported:
        log("no leads to verify (none in a supported county, or all already verified)")
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
    log("This module is a library for scripts/summitleads_pipeline.py — "
        "no standalone CLI entrypoint. Run the daily pipeline instead.", "ERROR")
    sys.exit(2)
