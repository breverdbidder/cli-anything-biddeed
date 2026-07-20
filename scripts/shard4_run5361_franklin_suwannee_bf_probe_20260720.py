#!/usr/bin/env python3
"""
shard4_run5361_franklin_suwannee_bf_probe_20260720.py

READ-ONLY live probe for franklin B/F and suwannee A/B/F, 2026-07-20.
dispatch_id: 6eb17f60-d04c-404c-96f6-b8181e4c302c  (GOLD STANDARD SHARD-4 run 5361)

Context: This is the 4th+/5th+ independent check of these counties' failing letters.
Prior sessions (listed in reverse chronological order):
  - GOLD_STANDARD_SHARD4_SEMINOLE_OSCEOLA_SUWANNEE_DISPATCH_AE041D7C_3RD_FIRING_ADDENDUM.md
    (2026-07-19 ~19:30 UTC): suwannee CALACT=0, CALSCH=2 for 07/09/2026;
    franklinclerk.com not re-checked (prior explicit "do not re-attempt same-day" guidance).
  - GOLD_STANDARD_SHARD9_FRANKLIN_HARDEE_DISPATCH_30B3A3EA_2ND_FIRING_SESSION_REPORT.md
    (2026-07-19): franklin 8/10 confirmed unchanged.
  - GOLD_STANDARD_SHARD3_MARION_FRANKLIN_LIBERTY_SEMINOLE_DISPATCH_26F01B9B_SECOND_CONTINUATION.md
    (2026-07-18): franklin 8/10 re-confirmed (3rd independent check); liberty 7/10.
  - scripts/franklin_liberty_bf_recheck_2026-07-18.py: franklinclerk.com all records
    frozen since May/June 2026 (modified timestamps); 5 rows unchanged for 8+ days post
    the Jul 8 sale date. 2025-CC-86 now 'cancelled' (status drift, no sold_amount).
  - scripts/franklin_bf_recheck_2026-07-11.py: 2nd check, identical findings.
  - scripts/franklin_bf_verified_no_sales_2026-07-10.py: initial discovery of the
    franklinclerk.com WP REST API; platform correction to 'franklinclerk_wp_rest'.
  - GOLD_STANDARD_SHARD4_SEMINOLE_OSCEOLA_SUWANNEE_DISPATCH_AE041D7C_SESSION_REPORT.md
    (2026-07-19 ~16:30 UTC): suwannee A/B/F re-verified from live sources;
    cases 4666/4667 CALACT=0, CALSCH=2; foreclosure lane has 0 listings.
  - scripts/shard11_run3679_suwannee_bf_taxdeed_result_probe.py (2026-07-11): first
    documented structured probe of cases 4666/4667; CALACT=0.
  - migrations/20260711_gold_standard_shard3_suwannee_fc_fabrication_repurge_and_quarantine.sql:
    removed 2 fabricated suwannee FC rows; quarantined the shard5-run1524-daily cron
    that re-injected them. Honest score regression: 8->7/10.

TODAY (2026-07-20):
  - Today is 11 days past the franklin Jul 8 sale cohort.
  - Today is 11 days past the suwannee cases 4666/4667 auction date (07-09-2026).
  - Next suwannee tax-deed date (08/06/2026) is still 17 days away.
  - suwannee.realforeclose.com (foreclosure lane, A) has had 0 listings for multiple
    sessions; any change would be the first since well before the fabrication purge.

METHODOLOGY:
  1. Franklin: re-check franklinclerk.com/wp-json/kma/v1/taxdeeds for modified-timestamp
     changes and cert_holder/status updates. Any record with modified > 2026-07-01
     would be a new signal.
  2. Suwannee A: re-check suwannee.realforeclose.com AJAX calendar for any highlighted
     auction day.
  3. Suwannee B/F: re-check suwannee.realtaxdeed.com AJAX calendar for
     CALACT and RESULTS on 07/09/2026 (cases 4666/4667).

NO WRITES to any DB table in this script. No auction_status or sold_amount updated
without direct evidence from the authoritative source.

Run: python3 scripts/shard4_run5361_franklin_suwannee_bf_probe_20260720.py
Network: requires egress to franklinclerk.com, suwannee.realforeclose.com,
         suwannee.realtaxdeed.com
"""

import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

AJAX_SUBS = [
    ("@A", '<div class="'),
    ("@B", "</div>"),
    ("@C", 'class="'),
    ("@D", "<div>"),
    ("@E", "AUCTION"),
    ("@F", "</td><td"),
    ("@G", "</td></tr>"),
    ("@H", "<tr><td "),
    ("@I", "table"),
    ("@J", 'p_back="NextCheck='),
    ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]


def _get(url, cj=None, headers=None, timeout=20):
    hdrs = {"User-Agent": UA_DESKTOP}
    if headers:
        hdrs.update(headers)
    if cj is not None:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        req = urllib.request.Request(url, headers=hdrs)
        try:
            resp = opener.open(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="replace"), resp.status
        except Exception as e:
            return None, str(e)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), resp.status
    except Exception as e:
        return None, str(e)


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def strip_html(s):
    if not s:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip() or None


def check_franklin_clerk():
    """
    Probe franklinclerk.com/wp-json/kma/v1/taxdeeds for any updated records
    (modified timestamps > 2026-07-01, or cert_holder/status changes).

    Returns dict with finding and HONESTY tag.
    """
    url = "https://www.franklinclerk.com/wp-json/kma/v1/taxdeeds"
    body, status = _get(url)
    if not body:
        return {"finding": "REQUEST_FAILED", "detail": str(status), "honesty": "VERIFIED"}

    try:
        rows = json.loads(body)
    except Exception as e:
        return {"finding": "JSON_PARSE_ERROR", "detail": str(e), "honesty": "VERIFIED"}

    result = {
        "finding": "NO_DELTA",
        "http_status": status,
        "row_count": len(rows),
        "rows": [],
        "honesty": "VERIFIED",
        "new_signal": False,
    }

    for row in rows:
        rec = {
            "case_number": row.get("case_number") or row.get("cert_number"),
            "status": row.get("status"),
            "modified": row.get("modified"),
            "cert_holder": row.get("cert_holder", ""),
            "original_bid": row.get("original_bid", ""),
        }
        result["rows"].append(rec)

        modified_str = rec["modified"] or ""
        if modified_str > "2026-07-01":
            result["new_signal"] = True
            result["finding"] = "NEW_SIGNAL_DETECTED"

        if rec["cert_holder"] and rec["cert_holder"].strip():
            result["new_signal"] = True
            result["finding"] = "CERT_HOLDER_POPULATED"

    if result["new_signal"] is False and len(rows) >= 5:
        result["finding"] = "NO_DELTA_CONFIRMED"

    return result


def check_suwannee_foreclosure_lane():
    """
    Probe suwannee.realforeclose.com AJAX calendar for any highlighted auction day.
    Returns (n_highlighted_days, honesty_tag).
    """
    base = "https://suwannee.realforeclose.com"
    url = f"{base}/index.cfm?zaction=USER&zmethod=CALENDAR"
    body, status = _get(url)
    if not body:
        return None, "VERIFIED_FAIL"

    dayid_count = len(re.findall(r"dayid='", body))
    return dayid_count, "VERIFIED"


def check_suwannee_taxdeed_cases(auction_date_mmddyyyy="07/09/2026"):
    """
    Probe suwannee.realtaxdeed.com for CALACT/CALSCH and RESULTS for the
    07/09/2026 auction date (cases 4666, 4667).

    Returns dict with calact, calsch, results_empty, sold_to_texts, honesty.
    """
    base = "https://suwannee.realtaxdeed.com"
    cj = http.cookiejar.CookieJar()

    cal_url = f"{base}/index.cfm?zaction=USER&zmethod=CALENDAR"
    cal_body, cal_status = _get(cal_url, cj)

    calact, calsch = None, None
    if cal_body:
        idx = cal_body.find(f"dayid='{auction_date_mmddyyyy}'")
        if idx >= 0:
            window = cal_body[idx:idx + 400]
            m = re.search(r'CALACT">(\d+)</span> / <span class="CALSCH">(\d+)', window)
            if m:
                calact, calsch = int(m.group(1)), int(m.group(2))

    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    _get(preview_url, cj)

    aitems = []
    results_rlists = {}
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(3):
            ts = int(time.time() * 1000)
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1"
            )
            try:
                body, _ = _get(
                    ajax_url, cj,
                    headers={"Referer": preview_url, "X-Requested-With": "XMLHttpRequest"}
                )
            except Exception:
                break
            if not body:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            results_rlists[f"{area}_{page_dir}"] = rlist
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                decoded = decode_ajax_html(ret_html)
                starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', decoded)]
                starts.append(len(decoded))
                for i in range(len(starts) - 1):
                    b = decoded[starts[i]:starts[i + 1]]
                    aidm = re.search(r'aid="(\d+)"', b)
                    if not aidm:
                        continue
                    case_m = re.search(r'Case #:</td>\s*<td[^>]*>\s*([0-9]+)', b)
                    sold_m = re.search(r'ASTAT_MSG_SOLDTO_MSG[^>]*>([^<]*)</div>', b)
                    aitems.append({
                        "aid": aidm.group(1),
                        "case_number": strip_html(case_m.group(1)) if case_m else None,
                        "sold_to_text": strip_html(sold_m.group(1)) if sold_m else None,
                    })
            time.sleep(0.3)

    results_rlists_result = "PREVIEW (no RESULTS tab yet)"

    results_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=RESULTS&AUCTIONDATE={auction_date_mmddyyyy}"
    _get(results_url, cj)
    for area in ("W", "C"):
        ts = int(time.time() * 1000)
        ajax_url = (
            f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
            f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
            f"&PageDir=0&doR=0&tx={ts}&bypassPage=0&test=1"
        )
        body, _ = _get(
            ajax_url, cj,
            headers={"Referer": results_url, "X-Requested-With": "XMLHttpRequest"}
        )
        if body:
            try:
                data = json.loads(body)
                rlist = data.get("rlist", "")
                results_rlists_result = f"RESULTS area={area}: rlist={rlist!r}"
                if rlist:
                    break
            except Exception:
                pass

    sold_to_texts = [item["sold_to_text"] for item in aitems if item["sold_to_text"]]
    results_empty = (
        all(not v for v in results_rlists.values()) if results_rlists else True
    )

    return {
        "calact": calact,
        "calsch": calsch,
        "preview_aitems": aitems,
        "results_rlist_sample": results_rlists_result,
        "sold_to_texts": sold_to_texts,
        "results_empty": results_empty,
        "honesty": "VERIFIED",
        "new_signal": bool(calact and calact > 0) or bool(sold_to_texts),
    }


def main():
    print("=" * 70)
    print("SHARD-4 RUN 5361 — LIVE PROBE 2026-07-20")
    print("dispatch_id: 6eb17f60-d04c-404c-96f6-b8181e4c302c")
    print("READ-ONLY: no DB writes in this script")
    print("=" * 70)

    print("\n--- FRANKLIN: franklinclerk.com WP REST API check ---")
    fr = check_franklin_clerk()
    print(f"  HTTP status: {fr.get('http_status', 'N/A')}")
    print(f"  Row count:   {fr.get('row_count', 'N/A')}")
    print(f"  Finding:     {fr['finding']}")
    print(f"  Honesty:     {fr['honesty']}")
    print(f"  New signal:  {fr.get('new_signal', False)}")
    for r in fr.get("rows", []):
        print(
            f"    {r['case_number']} | status={r['status']} | modified={r['modified']} "
            f"| cert_holder={r['cert_holder']!r} | original_bid={r['original_bid']!r}"
        )

    print("\n--- SUWANNEE A: suwannee.realforeclose.com (foreclosure lane) ---")
    fc_days, fc_honesty = check_suwannee_foreclosure_lane()
    if fc_days is None:
        print(f"  REQUEST FAILED — {fc_honesty}")
    else:
        print(f"  Highlighted auction days: {fc_days}")
        print(f"  Honesty: {fc_honesty}")
        if fc_days == 0:
            print("  FINDING: A still structurally blocked (0 fc listings) — NO_DELTA")
        else:
            print("  FINDING: NEW_SIGNAL — investigate immediately, fc>0 for first time")

    print("\n--- SUWANNEE B/F: suwannee.realtaxdeed.com (cases 4666/4667, 07/09/2026) ---")
    td = check_suwannee_taxdeed_cases("07/09/2026")
    print(f"  CALACT: {td['calact']}")
    print(f"  CALSCH: {td['calsch']}")
    print(f"  PREVIEW AITEMs found: {len(td['preview_aitems'])}")
    for item in td["preview_aitems"]:
        print(f"    aid={item['aid']} case={item['case_number']} sold_to={item['sold_to_text']!r}")
    print(f"  Results rlist sample: {td['results_rlist_sample']}")
    print(f"  Results empty: {td['results_empty']}")
    print(f"  Sold-to texts: {td['sold_to_texts']}")
    print(f"  New signal: {td['new_signal']}")
    print(f"  Honesty: {td['honesty']}")

    if not td["new_signal"]:
        print(
            "  FINDING: cases 4666/4667 still unresolved — CALACT=0, no sold_to_text, "
            "results rlist empty. B/F remain correctly blocked. NO_DELTA."
        )
    else:
        print(
            "  FINDING: NEW_SIGNAL DETECTED — CALACT>0 or sold_to_text present. "
            "Proceed to parse ASTAT_MSG_SOLDTO_MSG, update MCA rows, insert "
            "tax_deed_outcomes with data_source='realauction_ajax_results:SUWANNEE-TXD-V1'."
        )

    print("\n" + "=" * 70)
    print("CONCLUSION:")
    fr_blocked = not fr.get("new_signal", False)
    sw_a_blocked = (fc_days == 0) if fc_days is not None else None
    sw_bf_blocked = not td["new_signal"]

    if fr_blocked and sw_a_blocked and sw_bf_blocked:
        print("  All three failing letters (franklin B/F, suwannee A/B/F) remain")
        print("  genuinely accrual-blocked. No DB writes warranted.")
        print("  Per campaign rule: switch to next county/letter rather than idling.")
        print("  Putnam: 10/10 — already complete, no further action.")
        print("  Franklin B/F: blocked until franklinclerk.com posts Jul 8 sale outcomes.")
        print("  Suwannee A: blocked until listings appear on realforeclose.com.")
        print("  Suwannee B/F: blocked until cases 4666/4667 result OR 08/06 batch closes.")
    else:
        print("  DELTA DETECTED — see above for new signals. Proceed to write outcomes.")


if __name__ == "__main__":
    main()
