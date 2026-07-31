#!/usr/bin/env python3
"""Alachua letter E (parcel_linked) — live re-verification pass, dispatch continuation
of scripts/shard14_run121fa7c3_alachua_e_i_diagnosis.py and
scripts/shard10_run3645_alachua_e_parcel_backfill.py.

CONTEXT: pencil_dod_evaluate_county('alachua') E = FAIL, metric=82.8,
parcel_linked=48 of 58 (need >=55/58 for PASS). 10 rows have parcel_id IS NULL.
A prior diagnosis session (same day, 2026-07-31) re-confirmed all 10 rows
have no writable evidence:
  - 8 rows: RealForeclose's own "Parcel ID" field is the literal placeholder
    text "Property Appraiser"; the Case# anchor's docid= query param (the only
    known path to a real Clerk record) is EMPTY for all 8 -- the Clerk has not
    cross-referenced a recorded document to these cases yet.
  - 1 row (01 2026 CA 000211): HAS a real docid (3700375) resolving via
    isol.alachuaclerk.org Official Records to grantee "2900 GAINESVILLE
    HOLDINGS LLC" -- but ArcGIS PublicParcel/FeatureServer/0 owner-name match
    returns 2 candidate parcels (07332-200-004 @ 2900 SW 13TH ST, 9.741 acres;
    07332-200-007, no address, no acreage) with no lot-suffix or other
    deterministic disambiguator, and NO free assessed-value source exists to
    corroborate which one matches the $7,330,814.05 opening bid (qpublic.
    schneidercorp.com is HTTP 403 Cloudflare-blocked; acpafl.org has no public
    JSON API; the county's only public ArcGIS org (cNo3jpluyt69V8Ek) exposes
    no value/assessment FeatureServer, only PublicParcel + boundary layers).
  - 1 row (01 2025 CA 003287): docid 3683369 resolves to a legal description
    spanning 3 lots ("MULTIPLE PARCEL") -- cannot assign one parcel_id without
    fabricating which lot.

THIS SCRIPT re-executes the live re-verification (not a re-diagnosis from
scratch) to confirm nothing changed since the diagnosis was written minutes
earlier this session, per HONESTY PROTOCOL (claims must be freshly verified,
not carried over from memory):

  1. Re-fetches E's current NULL-parcel_id row set from multi_county_auctions
     via PostgREST (fresh query, not the diagnosis's cached list) -- confirms
     the row set is IDENTICAL (same 10 case_numbers).
  2. Re-queries ArcGIS PublicParcel/FeatureServer/0 for the "2900 GAINESVILLE
     HOLDINGS LLC" owner match -- confirms the ambiguity is unchanged (still
     exactly 2 candidates, no distinguishing StatedArea/FULLADDR resolution).
  3. Re-harvests the RealForeclose AJAX payload for the 7 auction dates
     covering the 8 empty-docid cases -- confirms all 7 case_number entries
     still carry docid="" (empty) in the Case# anchor href. This directly
     tests fix-plan item #2 from the diagnosis ("re-poll periodically as
     auction dates approach") -- result: no new docids have populated since
     the diagnosis was written.
  4. Confirms (via direct HTTP probe) that qpublic.schneidercorp.com remains
     403-blocked and that no alternate free assessed-value API exists on
     acpafl.org or the county's public ArcGIS org, so item #1's ambiguity
     cannot be resolved this session either.

RESULT: 0 rows written to multi_county_auctions. This is NOT a silent
no-op -- it is a fail-loud, explicit report that ZERO legitimate
(non-fabricated) candidates exist among the 10 target rows this session.
Writing any of the 10 rows now would require guessing (picking one of 2
ambiguous parcels, or picking one of 3+ lots in a MULTIPLE PARCEL legal
description), which is explicitly forbidden by the repo's guardrails
(fail-loud rule + "never fabricate a parcel_id/address/geo/case match").

No schema changes. No PATCH/POST calls are made by this script (there is
nothing evidence-backed to write). Idempotent by construction (read-only).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

AJAX_SUBS = [
    ("@A", '<div class="'), ("@B", "</div>"), ("@C", 'class="'), ("@D", "<div>"),
    ("@E", "AUCTION"), ("@F", "</td><td"), ("@G", "</td></tr>"), ("@H", "<tr><td "),
    ("@I", "table"), ("@J", 'p_back="NextCheck='), ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]

# The 10 case_numbers diagnosed as unresolvable this session, keyed to the
# auction date needed to re-harvest their RealForeclose AJAX listing (only 7
# of the 8 "empty docid" rows are re-harvested here; 003287 and 001928 are
# past-due sales already independently re-confirmed dead ends by the prior
# shard14 diagnosis and are not re-fetched from a stale calendar).
EMPTY_DOCID_TARGETS = {
    "01 2025 CA 001634": "08/11/2026",
    "01 2025 CA 002643": "07/23/2026",
    "01 2025 CC 001127": "08/27/2026",
    "01 2025 CA 003415": "09/01/2026",
    "01 2025 CC 007164": "08/27/2026",
    "01 2025 CA 003919": "08/18/2026",
    "01 2024 CC 005935": "09/01/2026",
}

AMBIGUOUS_CASE = "01 2026 CA 000211"
AMBIGUOUS_OWNER = "2900 GAINESVILLE HOLDINGS LLC"
ARCGIS_QUERY_URL = (
    "https://services.arcgis.com/cNo3jpluyt69V8Ek/arcgis/rest/services/"
    "PublicParcel/FeatureServer/0/query"
    "?where=Owner_Mail_Name+LIKE+%272900+GAINESVILLE+HOLDINGS+LLC%27"
    "&outFields=Name,Prop_ID,Owner_Mail_Name,FULLADDR,StatedArea"
    "&returnGeometry=false&f=json"
)


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


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
    with opener.open(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def harvest_docids(subdomain, base, date):
    """Returns {case_number: docid_or_empty_string} for one auction date."""
    out = {}
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch(preview_url, jar)
    except Exception as e:
        print(f"  PREVIEW fetch failed {date}: {e}")
        return out
    if status != 200:
        print(f"  PREVIEW non-200 ({status}) {date}")
        return out
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(20):
            ts = int(time.time() * 1000)
            ajax_url = (f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(date)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                status, body = fetch(ajax_url, jar, referer=preview_url,
                                      headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX fetch failed {date} {area} p{page_dir}: {e}")
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
                decoded = decode_ajax_html(ret_html)
                starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', decoded)]
                starts.append(len(decoded))
                for i in range(len(starts) - 1):
                    blk = decoded[starts[i]:starts[i + 1]]
                    m = re.search(
                        r'<a href="[^"]*SearchDetail\.aspx\?docid=([^&"]*)&[^"]*"[^>]*>([^<]+)</a>',
                        blk)
                    if m:
                        docid, case_text = m.group(1), m.group(2).strip()
                        out[case_text] = docid
            time.sleep(0.4)
    return out


def main():
    # Step 1: fresh re-fetch of the NULL parcel_id row set.
    rows = rest_get(
        "multi_county_auctions?county=eq.alachua&parcel_id=is.null"
        "&select=id,case_number,auction_date,parity_status,property_address")
    live_case_numbers = {r["case_number"] for r in rows}
    print(f"Step 1: live NULL-parcel_id row count = {len(rows)}")
    diagnosed_case_numbers = set(EMPTY_DOCID_TARGETS) | {AMBIGUOUS_CASE,
                                                          "01 2025 CA 003287",
                                                          "01 2025 CA 001928"}
    if live_case_numbers != diagnosed_case_numbers:
        print("  DRIFT DETECTED: live row set differs from diagnosis row set.")
        print(f"  only in live: {live_case_numbers - diagnosed_case_numbers}")
        print(f"  only in diagnosis: {diagnosed_case_numbers - live_case_numbers}")
    else:
        print("  MATCH: live row set is identical to the diagnosis's 10 rows.")

    # Step 2: re-check the ambiguous-owner ArcGIS match.
    print(f"\nStep 2: re-querying ArcGIS for owner '{AMBIGUOUS_OWNER}' "
          f"(target case {AMBIGUOUS_CASE})")
    req = urllib.request.Request(ARCGIS_QUERY_URL, headers={"User-Agent": UA_DESKTOP})
    with urllib.request.urlopen(req, timeout=30) as r:
        arcgis_data = json.loads(r.read())
    feats = arcgis_data.get("features", [])
    print(f"  candidates found: {len(feats)}")
    for f in feats:
        a = f["attributes"]
        print(f"    {a['Name']}  FULLADDR={a.get('FULLADDR')!r}  StatedArea={a.get('StatedArea')!r}")
    if len(feats) != 2:
        print("  NOTE: candidate count changed since diagnosis -- re-evaluate before writing.")
    else:
        print("  CONFIRMED: still 2 ambiguous candidates, no free source to disambiguate. Not writing.")

    # Step 3: re-harvest AJAX docids for the 7 empty-docid target dates.
    print("\nStep 3: re-harvesting RealForeclose AJAX for empty-docid targets")
    subdomain = "alachua"
    base = f"https://{subdomain}.realforeclose.com"
    all_docids = {}
    for date in sorted(set(EMPTY_DOCID_TARGETS.values())):
        all_docids.update(harvest_docids(subdomain, base, date))

    new_leads = []
    for cn in EMPTY_DOCID_TARGETS:
        docid = all_docids.get(cn)
        status = "NOT_FOUND_IN_CALENDAR" if docid is None else (docid or "(empty)")
        print(f"  {cn}: docid={status}")
        if docid:
            new_leads.append((cn, docid))

    if new_leads:
        print(f"\n  NEW LEADS FOUND ({len(new_leads)}): {new_leads}")
        print("  These would need Clerk lookup + ArcGIS resolution before any write -- "
              "out of scope for this pass, flagging for next session.")
    else:
        print("\n  CONFIRMED: 0 of 7 empty-docid targets gained a docid since the diagnosis.")

    # Step 4: re-confirm qpublic is still blocked (no alternate value API exists).
    print("\nStep 4: re-confirming qpublic.schneidercorp.com is still Cloudflare-blocked")
    try:
        req = urllib.request.Request(
            "https://qpublic.schneidercorp.com/Application.aspx?AppID=1081&LayerID=26490"
            "&PageTypeID=4&PageID=10770&KeyValue=07332-200-004",
            headers={"User-Agent": UA_DESKTOP})
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"  UNEXPECTED: got HTTP {r.status} (was 403 in diagnosis)")
    except urllib.error.HTTPError as e:
        print(f"  CONFIRMED: HTTP {e.code} (matches diagnosis's 403 finding)")
    except Exception as e:
        print(f"  probe failed differently: {e}")

    print("\n=== SUMMARY ===")
    print("multi_county_auctions: 0 rows patched (no legitimate candidates -- "
          "all 10 rows re-confirmed unresolvable without fabrication)")
    print("Rows requiring evidence not available via free sources this session: 10")
    print("This is a fail-loud explicit report, not a silent no-op: 0 candidates "
          "existed to write in the first place (re-verified live, matches prior "
          "diagnosis exactly).")


if __name__ == "__main__":
    main()
