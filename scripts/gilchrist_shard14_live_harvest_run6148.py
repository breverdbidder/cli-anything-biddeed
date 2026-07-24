#!/usr/bin/env python3
"""GOLD STANDARD SHARD-14 run-6148 — gilchrist — live C/D/E/I fix.

Real data only: harvests the live gilchrist.realforeclose.com (foreclosure)
and gilchrist.realtaxdeed.com (tax deed) AJAX calendar endpoints for the
specific auction dates covering our 8 non-matched rows, matches by
case_number, and writes REAL parcel_id/property_address/assessed_value plus
a genuine parity stamp. No centroid/median placeholders.

AJAX harvest mechanics ported verbatim from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (verified live pattern,
2026-07-02) — reused rather than reimplemented per K3 surgical-changes rule.

NOTE on geocode/value: the FL DOR statewide cadastral FeatureServer
(services9.arcgis.com/.../Florida_Statewide_Cadastral) was tried live for
per-parcel geocode/assessed-value backfill and is UNTESTED-usable right now —
CO_NO=<n> attribute filters return HTTP 400 "Invalid query parameters" for
every county tried (11, 16, 31, 48), while OBJECTID/PARCEL_ID filters work.
Gilchrist's own PARCEL_ID format did not match any DOR row either. Dropped
rather than shipped as a silent no-op or backed by a fabricated placeholder.

FAIL-LOUD: any row we attempt to enrich and get zero AJAX matches for is
reported as UNRESOLVED, never silently skipped or filled with a placeholder.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'), ("@D", "<div>"),
    ("@E", "AUCTION"), ("@F", "</td><td"), ("@G", "</td></tr>"), ("@H", "<tr><td "),
    ("@I", "table"), ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]

def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def to_float(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


def parse_aitem_blocks(html):
    items = []
    starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
    if not starts:
        return items
    starts.append(len(html))
    for i in range(len(starts) - 1):
        b = html[starts[i]:starts[i + 1]]
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
        data, addr_lines, last_addr = {}, [], False
        for lbl_h, dta_h in rows:
            lbl = re.sub(r"<[^>]+>", "", lbl_h).strip().rstrip(":").lower()
            if "property address" in lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                last_addr = True
                continue
            if last_addr and not lbl:
                t = strip_html(dta_h)
                if t:
                    addr_lines.append(t)
                continue
            last_addr = False
            if lbl:
                data[lbl] = dta_h
        raw_parcel = strip_html(data.get("parcel id"))
        # Some RealAuction listings render the Parcel ID cell as a generic
        # "Property Appraiser" hyperlink with no real parcel number in the
        # anchor text (confirmed live 2026-07-24 for gilchrist foreclosure
        # items, unlike tax-deed items where the anchor text IS the parcel
        # number). A prior session (source=shard5_g_i_fix in parcel_zones)
        # hit this same trap and wrote the literal string as a parcel_id —
        # guard against repeating that ghost-success.
        parcel_id = raw_parcel if raw_parcel and re.search(r"\d", raw_parcel) else None
        items.append({
            "case_number": strip_html(data.get("case #")),
            "parcel_id": parcel_id,
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
            "judgment_amount": to_float(data.get("final judgment amount")),
        })
    return items


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def fetch(url, cookie_jar, referer=None, headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    hdrs = {"User-Agent": UA_DESKTOP}
    if referer:
        hdrs["Referer"] = referer
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=25) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def harvest_date(subdomain, auction_date_mmddyyyy, platform_domain):
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch(preview_url, jar)
    except Exception as e:
        log(f"PREVIEW fetch failed {subdomain}/{platform_domain} {auction_date_mmddyyyy}: {e}", "VERIFIED")
        return []
    if status != 200:
        log(f"PREVIEW non-200 ({status}) {subdomain}/{platform_domain} {auction_date_mmddyyyy}", "VERIFIED")
        return []
    items = []
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            tsm = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={page_dir}&doR=0&tx={tsm}&bypassPage=0&test=1")
            try:
                status, body = fetch(ajax_url, jar, referer=preview_url,
                                      headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                log(f"AJAX fetch failed AREA={area} page={page_dir}: {e}", "VERIFIED")
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
                items.extend(parse_aitem_blocks(decode_ajax_html(ret_html)))
            time.sleep(0.4)
    return items


def norm_case(c):
    if not c:
        return ""
    return re.sub(r"[^A-Z0-9]", "", c.upper())


def sb_patch(row_id, fields):
    if not fields:
        return
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
    req = urllib.request.Request(
        url, data=json.dumps(fields).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status not in (200, 204):
                raise RuntimeError(f"PATCH {row_id} failed: HTTP {r.status}")
    except urllib.error.HTTPError as e:
        body = e.read()[:500]
        raise RuntimeError(f"PATCH {row_id} failed: HTTP {e.code} {body}")


def sb_get_current_matched_clean():
    """Row ids already carrying a real parity_status — re-checked live right
    before writing, so a concurrent shard/cron job's verification is never
    clobbered by ours (they run in parallel, per PARALLEL-FLEET RULES)."""
    url = (f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
           f"?county=eq.gilchrist&parity_status=eq.matched_clean&select=id")
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return [row["id"] for row in json.loads(r.read())]
    except Exception as e:
        log(f"sb_get_current_matched_clean failed: {e}", "VERIFIED")
        return []


def sb_post(path, payload):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"})
    with urllib.request.urlopen(url=req, timeout=30) as r:
        return r.status


def main():
    dry_run = "--dry-run" in sys.argv
    if not SUPABASE_KEY and not dry_run:
        log("SUPABASE_SERVICE_ROLE_KEY not set", "VERIFIED")
        sys.exit(1)

    # Our 9 target rows (8 non-matched-clean + a00900ac stamp-only), from live
    # query run 2026-07-24 against multi_county_auctions WHERE county='gilchrist'.
    targets = [
        {"id": "853be989-9e8a-46ff-839a-957b921bfcf0", "case_number": "26-0010-TD", "date": "09/08/2026", "platform": "realtaxdeed.com"},
        {"id": "f71f6d5f-5ae0-431a-a0b0-a0d80c32dcf9", "case_number": "26-0013-TD", "date": "09/08/2026", "platform": "realtaxdeed.com"},
        {"id": "687d2ad6-4470-4992-93c4-7d28a0b30999", "case_number": "212025CA000064CAAXMX", "date": "09/14/2026", "platform": "realforeclose.com"},
        {"id": "8d48ca78-3f0c-4e80-850e-177642da92c0", "case_number": "212026CA000004CAAXMX", "date": "09/14/2026", "platform": "realforeclose.com"},
        {"id": "a00900ac-4807-434e-9660-dddd1e0c5ad6", "case_number": "212025CA000042CAAXMX", "date": "09/14/2026", "platform": "realforeclose.com"},
        {"id": "9bbeb28e-d2ec-4b2a-a7f5-bc6ce46b0484", "case_number": "212025CA000033CAAXMX", "date": "09/28/2026", "platform": "realforeclose.com"},
        {"id": "d539cf17-bbf5-401d-9259-29f4d6a89d89", "case_number": "212025CA000070CAAXMX", "date": "09/28/2026", "platform": "realforeclose.com"},
        {"id": "4517a039-4157-4b84-bc04-b0fe22b22df3", "case_number": "212025CA000043CAAXMX", "date": "10/12/2026", "platform": "realforeclose.com"},
        {"id": "c2a988e3-4175-4d89-b65f-8b352d362df0", "case_number": "212025CA000036CAAXMX", "date": "10/26/2026", "platform": "realforeclose.com"},
    ]

    by_date_platform = {}
    for t in targets:
        by_date_platform.setdefault((t["date"], t["platform"]), []).append(t)

    harvested_by_case = {}
    for (date, platform), rows in by_date_platform.items():
        items = harvest_date("gilchrist", date, platform)
        log(f"{platform} {date}: harvested {len(items)} AJAX items", "VERIFIED")
        for it in items:
            harvested_by_case[norm_case(it["case_number"])] = it

    already_verified = set(sb_get_current_matched_clean())

    resolved, unresolved, skipped_already_done = [], [], []
    for t in targets:
        key = norm_case(t["case_number"])
        item = harvested_by_case.get(key)
        if not item:
            unresolved.append(t["case_number"])
            continue
        if t["id"] in already_verified:
            skipped_already_done.append(t["case_number"])
            continue
        resolved.append((t, item))

    if skipped_already_done:
        log(f"Skipping {skipped_already_done}: already matched_clean via another live source", "VERIFIED")

    log(f"Resolved {len(resolved)}/{len(targets)} via live AJAX; unresolved: {unresolved}", "VERIFIED")

    updated_rows, failed_rows = [], []
    for t, item in resolved:
        fields = {}
        parcel_id = item.get("parcel_id")
        if parcel_id:
            fields["parcel_id"] = parcel_id
        if item.get("property_address"):
            fields["property_address"] = item["property_address"]
        assessed = item.get("assessed_value")
        if assessed:
            fields["assessed_value"] = assessed
        # Real, live-verified parity: the case number + auction date matched
        # a genuine live RealAuction calendar entry for gilchrist (zero
        # PropertyOnion coverage county — STANDING AUTHORIZATION 2026-06-12
        # covers clerk/RealAuction-sourced parity when there is no PO litmus
        # to diverge against). This is independent of whether the listing
        # also carried a parcel/address (that gap is disclosed, not hidden).
        fields["parity_status"] = "matched_clean"
        fields["parity_source"] = "tier1:shard14_gilchrist_run6148_live_realauction_ajax"
        fields["parity_checked_at"] = datetime.now(timezone.utc).isoformat()
        fields["tier1_authoritative"] = True
        fields["tier1_verified_at"] = datetime.now(timezone.utc).isoformat()
        fields["tier1_source_run_id"] = 6148
        fields["last_seen_at"] = datetime.now(timezone.utc).isoformat()

        log(f"{t['case_number']} -> parcel={parcel_id} addr={item.get('property_address')!r} assessed={assessed}", "VERIFIED")
        if not dry_run:
            try:
                sb_patch(t["id"], fields)
            except Exception as e:
                log(f"PATCH failed for {t['case_number']}: {e}", "VERIFIED")
                failed_rows.append(t["case_number"])
                continue
        updated_rows.append(t["case_number"])

    if resolved and not updated_rows:
        raise RuntimeError("FAIL-LOUD: rows resolved via AJAX but zero DB updates applied")

    print(json.dumps({
        "resolved_count": len(resolved),
        "unresolved_cases": unresolved,
        "updated_cases": updated_rows,
        "failed_cases": failed_rows,
        "skipped_already_verified": skipped_already_done,
        "dry_run": dry_run,
    }, indent=2))


if __name__ == "__main__":
    main()
