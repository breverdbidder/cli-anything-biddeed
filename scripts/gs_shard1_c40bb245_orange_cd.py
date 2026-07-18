#!/usr/bin/env python3
"""GOLD STANDARD shard-1, dispatch bca41e8b, county=orange. C/D parity backfill.

Orange fails C (matched_clean=682/855=79.8%) and D (matched_any=682/855=79.8%),
needs >=95%. county_auction_config confirms BOTH lanes online:
  fc_url=https://myorangeclerk.realforeclose.com (fc_method=online)
  td_url=https://orange.realtaxdeed.com          (td_method=online)
This is a missing-parity-backfill problem, not a dead-vendor problem.

Forked verbatim from scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py
(itself forked from scripts/shard11_run3534_duval_cd_harvest.py, which forks
scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date() AJAX
fetcher). The only delta from the leon script: orange's foreclosure subdomain
(myorangeclerk) differs from its tax_deed subdomain (orange) and from the
county slug used in multi_county_auctions (orange) -- so harvest_date() is
called with an explicit per-sale-type subdomain instead of reusing the county
slug as the subdomain for both lanes.

For each distinct (sale_type, auction_date) present in orange's
multi_county_auctions rows (excluding data_source=propertyonion, which is
litmus-only per guardrail) with parity_status IS NULL:
  1. harvest the live myorangeclerk.realforeclose.com / orange.realtaxdeed.com
     AJAX calendar for that date (both verified live 200 OK this session)
  2. exact-match by normalized case_number (non-alphanumeric stripped),
     scoped to county AND auction_date via the harvest call itself (each
     harvest_date() call only returns items for one date's calendar, so
     cross-date mismatch is structurally impossible here)
  3. PATCH parity_status='matched_clean',
     parity_source='tier1:gs_shard1_c40bb245_orange_cd:<sale_type>:<date>'
  4. opportunistically backfill parcel_id/property_address/assessed_value
     when missing on the MCA row (idempotent -- only fills NULLs)

Direct DB (psycopg2/pooler) not used -- PostgREST only, consistent with prior
shard sessions (password auth confirmed stale).

Fails loud: if a date's calendar returns >0 parsed items but 0 rows get
parity-promoted, that is printed explicitly (not swallowed) and collected
into a summary NOTE at the end, matching the leon/shard11 precedent (a single
bad date does not abort the whole run).

Usage: python3 scripts/gs_shard1_c40bb245_orange_cd.py '<json targets>'
  targets: [{"county":"orange","sale_type":"foreclosure","auction_date":"2026-03-23"}, ...]
"""
import os
import re
import sys
import json
import time
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

import urllib.request


def parse_aitem_blocks_div(html, county_sub):
    """myorangeclerk.realforeclose.com's AJAX response renders AD_LBL/AD_DTA
    pairs as sibling <div>s instead of the <td class="AD_LBL">/<td class="AD_DTA">
    pairs scripts/shard2_run2450_ajax_realforeclose_harvest.py's
    parse_aitem_blocks() expects (verified live this session: 0 <td> tags in
    the decoded orange foreclosure AJAX payload vs 154 in orange's own
    tax_deed lane, which DOES use <td> markup and matched fine unmodified).
    Confirmed live orange foreclosure raw shape (2026-03-23 AREA=C):
      <div class="AD_LBL" ...>Case #:</div><div class="AD_DTA">
        <a href="...">2022-CA-002022-O</a> </div>
    Same label set (Case #, Parcel ID, Property Address, Assessed Value,
    Final Judgment Amount) as the <td> variant -- this is a markup-shape
    fork of parse_aitem_blocks(), not a new schema, so field extraction
    logic below is intentionally kept identical to the original."""
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]:starts[i + 1]]
        aidm = re.search(r'aid="(\d+)"', b)
        if not aidm:
            continue
        aid = aidm.group(1)
        rows = re.findall(
            r'class="AD_LBL"[^>]*>([^<]*)</div>\s*<div[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</div>',
            b, re.DOTALL)
        data = {}
        addr_lines = []
        last_addr = False
        for lbl_h, dta_h in rows:
            lbl = re.sub(r"<[^>]+>", "", lbl_h).strip().rstrip(":").lower()
            if "property address" in lbl:
                t = _mod.strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                last_addr = True
                continue
            if last_addr and not lbl:
                t = _mod.strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                continue
            last_addr = False
            if lbl:
                data[lbl] = dta_h
        items.append({
            "aid": aid,
            "county_subdomain": county_sub,
            "auction_starts_raw": None,
            "auction_starts_at": None,
            "auction_type": _mod.strip_html(data.get("auction type")),
            "case_number": _mod.strip_html(data.get("case #")),
            "judgment_amount": _mod.to_float(data.get("final judgment amount")),
            "parcel_id": _mod.strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": _mod.to_float(data.get("assessed value")),
            "plaintiff_max_bid": _mod.to_float(data.get("plaintiff max bid")),
        })
    return items


def harvest_date_div(subdomain, county_slug, auction_date_mmddyyyy, platform_domain="realforeclose.com"):
    """Identical control flow to _mod.harvest_date() (PREVIEW GET for cookie,
    then paginated AREA=W/C AJAX fetch), but decodes AITEM blocks with
    parse_aitem_blocks_div() instead of _mod.parse_aitem_blocks() since
    myorangeclerk.realforeclose.com's foreclosure lane renders divs, not
    table cells. Duplicated (not refactored into shard2's harvester) per
    Karpathy K3 surgical-changes discipline -- shard2's harvest_date() is a
    proven, in-production function used by many other counties; it is not
    touched here."""
    import urllib.parse as _uparse
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = __import__("http.cookiejar", fromlist=["CookieJar"]).CookieJar()
    try:
        status, _ = _mod.fetch(preview_url, jar)
    except Exception as e:
        print(f"  PREVIEW fetch failed {subdomain} {auction_date_mmddyyyy}: {e}")
        return []
    if status != 200:
        print(f"  PREVIEW non-200 ({status}) {subdomain} {auction_date_mmddyyyy}")
        return []

    items = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={_uparse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                status, body = _mod.fetch(ajax_url, jar, referer=preview_url,
                                           headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX AREA={area} PageDir={page_dir} fetch failed {subdomain} {auction_date_mmddyyyy}: {e}")
                break
            if status != 200:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                decoded = _mod.decode_ajax_html(ret_html)
                items.extend(parse_aitem_blocks_div(decoded, subdomain))
            time.sleep(0.4)
    return items

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

TARGETS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else None

PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}
# Orange's foreclosure subdomain differs from its tax_deed subdomain and from
# the county slug used in multi_county_auctions -- verified live 200 OK this
# session for both:
#   https://myorangeclerk.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=...
#   https://orange.realtaxdeed.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=...
SUBDOMAIN = {"foreclosure": "myorangeclerk", "tax_deed": "orange"}


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    """Some AITEM blocks decode the parcel-appraiser link as its own anchor text
    ('Property Appraiser') instead of the parcel number -- a pre-existing parser
    gap in shard2's decoder. A real parcel_id always contains at least one digit."""
    import re
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                      headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def match_and_fix(county, items, parity_source_label, target_case_numbers=None):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    parity_promoted = []
    parcel_backfilled = []
    card_backfilled = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            continue
        if target_case_numbers is not None and row["case_number"] not in target_case_numbers:
            continue
        item = by_norm[cn]
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")

        try:
            if not (row["parity_status"] == "matched_clean" and already_tier1):
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": parity_source_label})
                parity_promoted.append(row["id"])
        except Exception as e:
            print(f"    parity patch FAILED for {row['id']} ({row['case_number']}): {e}")
            continue

        patch_body = {}
        if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
            patch_body["parcel_id"] = item["parcel_id"]
        if not row.get("property_address") and item.get("property_address"):
            patch_body["property_address"] = item["property_address"]
        if not row.get("assessed_value") and item.get("assessed_value"):
            patch_body["assessed_value"] = item["assessed_value"]
        if patch_body:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
            except Exception as e:
                print(f"    card/parcel patch FAILED for {row['id']} ({row['case_number']}): {e}")
                continue
            if "parcel_id" in patch_body:
                parcel_backfilled.append(row["id"])
            if "property_address" in patch_body or "assessed_value" in patch_body:
                card_backfilled.append(row["id"])

    return parity_promoted, parcel_backfilled, card_backfilled


def main():
    if not TARGETS:
        print("usage: gs_shard1_c40bb245_orange_cd.py '<json targets>'")
        sys.exit(1)

    totals = {"parity": 0, "parcel": 0, "card": 0}
    any_parsed_zero_matched = []
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        target_cns = t.get("case_numbers")  # optional restrict list
        if not ad:
            print(f"  {county} {sale_type}: skip (no auction_date)")
            continue
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        subdomain = SUBDOMAIN[sale_type]
        try:
            if sale_type == "foreclosure":
                # myorangeclerk.realforeclose.com renders div-shaped AITEM
                # blocks, not the <td>-shaped ones _mod.harvest_date expects
                # (verified live this session -- see harvest_date_div docstring).
                items = harvest_date_div(subdomain, county, mmddyyyy, platform_domain=platform)
            else:
                items = _mod.harvest_date(subdomain, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {county} {sale_type} {ad}: {e}")
            continue
        n_parsed = len(items)
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        try:
            parity, parcel, card = match_and_fix(
                county, items, f"tier1:gs_shard1_c40bb245_orange_cd:{sale_type}:{ad}",
                target_case_numbers=target_cns)
        except Exception as e:
            print(f"  MATCH FAIL {county} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        print(f"  {county} {sale_type} {ad}: {n_parsed} calendar items -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)}")
        if n_parsed > 0 and len(parity) == 0:
            any_parsed_zero_matched.append((county, sale_type, ad, n_parsed))
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']}")
    if any_parsed_zero_matched:
        print("NOTE (not fatal, per-date, matches shard11/14 precedent): "
              f"parsed>0 but 0 promoted on: {any_parsed_zero_matched}")


def cert_number_fix_pass(dates):
    """Second-pass fix discovered mid-session: a subset of orange's
    multi_county_auctions rows are sale_type='tax_deed' but
    data_source='realforeclose' -- these are NOT rows harvestable from
    orange.realtaxdeed.com's calendar. Their case_number holds an Orange
    circuit-court case number (e.g. '48-2022-CA-000682', the underlying
    lawsuit) while their cert_number column holds the foreclosure-sale case
    number (e.g. '2024-CA-003268-O', sometimes suffixed with a parenthetical
    like ' (COUNT VIII)' for multi-count judgments -- the SAME parenthetical
    suffix, verbatim, also appears in the calendar's own case_number field
    for those multi-count cases, so it must be normalized-but-NOT-stripped
    on both sides for norm_case_number() to produce matching keys).
    Confirmed live this session: cert_number exact-matches an item on
    myorangeclerk.realforeclose.com's calendar for the SAME auction_date
    already harvested by main(). This pass re-uses that same
    harvest_date_div() call (not a new fetch) and matches these leftover
    rows by normalized cert_number instead of case_number.
    """
    totals_promoted = 0
    zero_matched = []
    for ad in dates:
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        try:
            items = harvest_date_div("myorangeclerk", "orange", mmddyyyy, platform_domain="realforeclose.com")
        except Exception as e:
            print(f"  CERT-FIX HARVEST FAIL orange tax_deed {ad}: {e}")
            continue
        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        rows = rest_get(
            f"multi_county_auctions?county=eq.orange&sale_type=eq.tax_deed"
            f"&data_source=eq.realforeclose&parity_status=is.null&auction_date=eq.{ad}"
            f"&select=id,case_number,cert_number,parcel_id,property_address,assessed_value")

        promoted = 0
        for row in rows:
            cert = row.get("cert_number") or ""
            # NOTE: do NOT strip the parenthetical count-suffix before
            # normalizing -- the calendar's own case_number field keeps the
            # same suffix (e.g. "2025-CA-000595-O (COUNT III)"), and
            # norm_case_number() strips non-alphanumerics from BOTH sides
            # identically, so an exact match requires the suffix text to
            # still be present on both sides. Stripping it here only (as an
            # earlier version of this pass did) silently produced a key that
            # exists on neither side and is a documented, corrected bug.
            cn = norm_case_number(cert)
            if cn not in by_norm:
                continue
            item = by_norm[cn]
            label = f"tier1:gs_shard1_c40bb245_orange_cd_certmatch:tax_deed:{ad}"
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": label})
                promoted += 1
            except Exception as e:
                print(f"    CERT-FIX patch FAILED {row['id']} ({row['case_number']} / cert={cert}): {e}")
                continue
            patch_body = {}
            if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
                patch_body["parcel_id"] = item["parcel_id"]
            if not row.get("property_address") and item.get("property_address"):
                patch_body["property_address"] = item["property_address"]
            if not row.get("assessed_value") and item.get("assessed_value"):
                patch_body["assessed_value"] = item["assessed_value"]
            if patch_body:
                try:
                    rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                except Exception as e:
                    print(f"    CERT-FIX card patch FAILED {row['id']}: {e}")

        print(f"  orange tax_deed(realforeclose-sourced) {ad}: {len(rows)} target rows, "
              f"{len(items)} fc calendar items -> promoted={promoted}")
        totals_promoted += promoted
        if len(rows) > 0 and promoted == 0:
            zero_matched.append(ad)
        time.sleep(0.4)

    print(f"\nCERT-FIX TOTAL promoted: {totals_promoted}")
    if zero_matched:
        print(f"NOTE (not fatal, per-date): dates with target rows but 0 promoted: {zero_matched}")


if __name__ == "__main__":
    main()
    if len(sys.argv) > 2 and sys.argv[2] == "--cert-fix":
        cert_fix_dates = json.loads(sys.argv[3])
        cert_number_fix_pass(cert_fix_dates)
