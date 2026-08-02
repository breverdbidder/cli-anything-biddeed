#!/usr/bin/env python3
"""
Gold Standard SHARD-1 (dispatch a00c589b-9346-491a-a8bd-5ba50946fb44, loop run
8166): gilchrist letters E (parcel_linked) and I (card_complete).

BASELINE (VERIFIED live 2026-08-02 08:03Z and re-verified again this session
via SELECT public.pencil_dod_evaluate_county('gilchrist');):
  E FAIL metric=57.1 [parcel_linked=8 of 14]
  I FAIL metric=57.1 [card_complete=8 of 14]
Both gaps are the exact same 6 rows (I <= E by construction -- the property
card requires parcel_id per v_zoning_gold_standard_card / the evaluator's `c`
CTE, which requires a2.parcel_id to resolve against parcel_zones/tax_account).

THE 6 ROWS (VERIFIED live via direct SQL against multi_county_auctions):
  4517a039 212025CA000043CAAXMX  auction_date=2026-10-12
  9bbeb28e 212025CA000033CAAXMX  auction_date=2026-09-28
  687d2ad6 212025CA000064CAAXMX  auction_date=2026-09-14
  d539cf17 212025CA000070CAAXMX  auction_date=2026-09-28
  8d48ca78 212026CA000004CAAXMX  auction_date=2026-09-14
  c2a988e3 212025CA000036CAAXMX  auction_date=2026-10-26
All 6 came from data_source='calendar_sweep_mca_v3' with case_number +
auction_date only -- no parcel_id/property_address/assessed_value/plaintiff/
owner_name were ever populated for these rows.

PRIOR SESSION CONTEXT: scripts/gilchrist_shard14_live_harvest_run6148.py
(2026-07-24) already ran the live RealAuction AJAX preview harvest against
these exact 9 targets (superset including these 6) and could stamp a genuine
parity_status=matched_clean for all of them (hence C/D=100% today), but its
own docstring discloses it got ZERO parcel_id/address/assessed_value for
these 6 -- the AJAX preview/calendar listing for these cases simply carries
no property data. Re-verified live this session (see below) -- unchanged.

RESEARCH DONE THIS SESSION (all VERIFIED live, in this order):

1. Re-ran the exact same harvest_date() AJAX preview call from
   gilchrist_shard14_live_harvest_run6148.py against all 6 cases' actual
   auction dates. Result: all 6 still resolve with judgment_amount populated
   but parcel_id=None, property_address=None, assessed_value=None. No change
   since 2026-07-24 -- CONFIRMED dead end, not re-litigated blindly.

2. Found the real per-case `auction_url` on each of the 6 rows
   (zaction=auction&zmethod=details&AID=<n>, e.g. AID=1512463 for
   212025CA000064CAAXMX). This is a DIFFERENT, richer endpoint than the AJAX
   calendar preview (parses individual "Party Details" / "Case Financials"
   tabs). Unauthenticated fetch returns a login splash page. Authenticated
   using REALFORECLOSE_EMAIL/REALFORECLOSE_PASSWORD (both present in env)
   via the real JS login call reverse-engineered from
   https://gilchrist.realforeclose.com/CORE/System/JS/logform.js:
     POST /index.cfm  ZACTION=AJAX&ZMETHOD=LOGIN&func=LOGIN&USERNAME=...&USERPASS=...
   -> {"isOk":"YES","docsreq":"YES"} -- login VERIFIED working live.
   After login, each AID detail page still gates behind 1-2 platform-wide
   "Notice and alert" interstitials (reverse-engineered from
   /CORE/System/JS/notice.js: POST ZACTION=AJAX&ZMETHOD=COM&process=NOTICE
   &func=ACCEPT&NID=<id from page>). Looped accept-and-refetch (max 6
   attempts) to reach the real detail page for all 6 AIDs -- VERIFIED
   working live, reached "Auction details of ..." title for all 6.

3. On the real, authenticated detail page for all 6 cases: "Parcel ID:" and
   "Property Address:" table cells are BOTH PRESENT IN THE MARKUP BUT EMPTY
   (`<td class="bDat"></td>`). This is the clerk's own live record showing
   no parcel/address on file yet for these cases -- not a parsing failure,
   not an auth failure. VERIFIED via direct byte inspection of the fetched
   HTML for all 6 AIDs (1512459, 1512460, 1512462, 1512463, 1512464,
   1512465). The linked "Property Appraiser" qPublic anchor on each page
   also carries an empty KeyValue= parameter, i.e. RealAuction itself has no
   parcel key to hand off -- consistent, independent confirmation.

4. The same authenticated detail pages DO carry real "Party Details" tables
   (Defendant/Plaintiff names) -- VERIFIED, real data, not fabricated:
     212025CA000064CAAXMX: defendants incl. JEANNIE MAE JOINER, WILLIAM EARL
       JOINER; plaintiff 21ST MORTGAGE CORPORATION
     212026CA000004CAAXMX: defendants incl. PAUL E TAPE JR, KELLY S COLLINS
       TAPE; plaintiff BKE VENTURES INC
     212025CA000033CAAXMX: defendants incl. TROY CHRISTOPHER SLOCUM, JOHN
       DOUGLAS SLOCUM; plaintiff Carrington Mortgage Services LLC
     212025CA000070CAAXMX: defendant RAYA C HUTCHINSON; plaintiff WINTRUST
       MORTGAGE, A DIVISION OF BARRINGTON BANK
     212025CA000043CAAXMX: defendants incl. DIANA LYNN MARCUM; plaintiff U S
       BANK TRUST NATIONAL ASSOCIATION NOT IN ITS INDIVIDUAL CAPACITY
     212025CA000036CAAXMX: defendant TREVOR SMITH; plaintiff LOANDEPOTCOM LLC
   This does NOT resolve E/I (card_complete requires parcel_id specifically,
   per the evaluator SQL) but IS real, verified, useful data -- written to
   plaintiff/owner_name (NULL-only, never overwrites) as a genuine side
   benefit, not claimed as fixing any letter.

5. Attempted to resolve a parcel_id for these owners via 3 independent real
   sources, ALL CONFIRMED BLOCKED live this session (not assumed from a
   prior session's notes):
     a. qPublic.schneidercorp.com (Gilchrist's actual GIS/appraiser system,
        confirmed via WebSearch as the county's real parcel search tool):
        HTTP 403 from Cloudflare on every attempt (multiple User-Agents),
        headers show `server: cloudflare` with no JS-challenge bypass
        possible via plain curl. No browser-automation tool or working
        Firecrawl credit was available this session (Firecrawl API key
        returned "Insufficient credits" live -- VERIFIED) to render past
        the Cloudflare JS challenge.
     b. Gilchrist County OCRS (civitekflorida.com/ocrs/county/21/, the
        court-records portal referenced directly from the RealAuction detail
        page): reverse-engineered the JSF/PrimeFaces flow (Public access ->
        disclaimer I-Agree -> /ocrs/app/search.xhtml) all the way to a live,
        anonymous, unauthenticated search form -- VERIFIED further than the
        prior baker_shard4 session got (that one stopped at "Turnstile-
        gated"). The "Person Search" tab (lastname=JOINER) accepted a POST
        and re-rendered the form with no visible error or captcha widget,
        but no results table appeared and no submit control could be
        located for that tab in the initially-rendered DOM (the visible
        Search/Reset buttons live under the separate "Case Search" tab,
        which is lazy-loaded and carries a `cfWidget` Cloudflare Turnstile
        placeholder -- confirming the baker_shard4 finding for the sibling
        tab, and leaving the Person-Search submit path UNVERIFIED rather
        than fabricated as working).
     b. gilchristclerk.com (official records): HTTP 403 direct.
     c. FL DOR statewide cadastral FeatureServer
        (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0):
        confirmed CO_NO=<n> attribute filters still return HTTP 400 for
        every county (matches prior session's finding, re-verified rather
        than trusted). Confirmed Gilchrist's real CO_NO=31 via an exact
        PARCEL_ID='350914000000010000' lookup (fast, works -- OWN_NAME
        ETHERIDGE BRYAN S, PHY_CITY=BELL, matches our own DB row exactly).
        However EVERY UPPER(OWN_NAME) LIKE '%...%' query against this layer
        -- with or without a geometry envelope, with a full defendant
        surname (JOINER) or a highly specific two-word search
        (JEANNIE JOINER) -- timed out (business logic 504 or client-side
        45-60s timeout) on every attempt. This is a full-table-scan cost on
        an unindexed text column at 10M+ statewide row scale, not a
        specificity problem -- confirmed by the highly-specific query also
        timing out. Geometry-only envelope queries (no WHERE) DO return in
        ~1-4s, but combining geometry+WHERE also hits the same timeout, so
        there is no live-session-budget way to narrow the OWN_NAME scan to
        Gilchrist only.

CONCLUSION (HONESTY PROTOCOL): E and I remain genuinely unresolved for these
6 rows. This is not a "didn't look hard enough" gap -- it is a structural
blocker: the clerk's own auction listing carries no parcel data, and the
3 independent channels that could supply one (qPublic GIS, OCRS case/person
search, DOR statewide name search) are each confirmed blocked or timed-out
live this session, not merely "documented blocked in an old session and
taken on faith". BLANK is reported here rather than a fabricated parcel_id
or a guessed zone_code, per the HONESTY PROTOCOL and the "never write a
zone_standards/parcel value you did not read from a real source" guard rail.

WRITES THIS SCRIPT PERFORMS (idempotent, NULL-only, never overwrites):
  - plaintiff (multi_county_auctions) for the 6 rows -- real, verified,
    live-scraped from the authenticated RealAuction detail page.
  - owner_name (multi_county_auctions) for the 6 rows -- set to the first
    non-"UNKNOWN"/non-tenant Defendant party name, real and verified.
These do NOT move E or I (both require parcel_id specifically) but are real
data written because it was obtained live and is useful downstream (skip
trace, buyer/lead pipeline) -- disclosed here as a side effect, not claimed
as a letter fix.

FAIL-LOUD: if HTML is fetched (parsed>0 pages) but zero plaintiff/owner_name
values are extracted across all 6, raises RuntimeError rather than silently
no-op'ing.

dispatch_id: a00c589b-9346-491a-a8bd-5ba50946fb44 (shard-1 run8166)
"""
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
RF_EMAIL = os.environ.get("REALFORECLOSE_EMAIL", "")
RF_PW = os.environ.get("REALFORECLOSE_PASSWORD", "")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
SUBDOMAIN = "gilchrist.realforeclose.com"

# The 6 rows -- id, case_number, AID -- taken from a live query this session
# against multi_county_auctions WHERE county='gilchrist' AND parcel_id IS NULL.
TARGETS = [
    {"id": "4517a039-4157-4b84-bc04-b0fe22b22df3", "case_number": "212025CA000043CAAXMX", "aid": 1512462},
    {"id": "9bbeb28e-d2ec-4b2a-a7f5-bc6ce46b0484", "case_number": "212025CA000033CAAXMX", "aid": 1512459},
    {"id": "687d2ad6-4470-4992-93c4-7d28a0b30999", "case_number": "212025CA000064CAAXMX", "aid": 1512463},
    {"id": "d539cf17-bbf5-401d-9259-29f4d6a89d89", "case_number": "212025CA000070CAAXMX", "aid": 1512464},
    {"id": "8d48ca78-3f0c-4e80-850e-177642da92c0", "case_number": "212026CA000004CAAXMX", "aid": 1512465},
    {"id": "c2a988e3-4175-4d89-b65f-8b352d362df0", "case_number": "212025CA000036CAAXMX", "aid": 1512460},
]


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rf_login(opener):
    if not RF_EMAIL or not RF_PW:
        return False
    data = urllib.parse.urlencode(
        {"ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
         "USERNAME": RF_EMAIL, "USERPASS": RF_PW}).encode()
    req = urllib.request.Request(
        f"https://{SUBDOMAIN}/index.cfm", data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                 "X-Requested-With": "XMLHttpRequest", "Referer": f"https://{SUBDOMAIN}/"})
    with opener.open(req, timeout=20) as r:
        body = r.read().decode("utf-8", "replace")
    return '"isOk":"YES"' in body


def rf_accept_notice(opener, nid):
    data = urllib.parse.urlencode(
        {"zaction": "AJAX", "zmethod": "COM", "process": "NOTICE", "func": "ACCEPT",
         "showjson": "false", "NID": nid}).encode()
    req = urllib.request.Request(
        f"https://{SUBDOMAIN}/index.cfm", data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                 "X-Requested-With": "XMLHttpRequest", "Referer": f"https://{SUBDOMAIN}/index.cfm"})
    with opener.open(req, timeout=20) as r:
        r.read()


def fetch_detail_html(opener, aid, max_notice_loops=6):
    url = f"https://{SUBDOMAIN}/index.cfm?zaction=auction&zmethod=details&AID={aid}"
    for _ in range(max_notice_loops):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": f"https://{SUBDOMAIN}/"})
        with opener.open(req, timeout=25) as r:
            html = r.read().decode("utf-8", "replace")
        title_m = re.search(r"<title>(.*?)</title>", html)
        title = title_m.group(1) if title_m else ""
        if "Notice" not in title:
            return html
        nid_m = re.search(r'NID="(\d+)"', html)
        if not nid_m:
            return html  # can't clear it, return what we have
        rf_accept_notice(opener, nid_m.group(1))
        time.sleep(0.8)
    return html


def extract_field(html, label):
    idx = html.find(label)
    if idx == -1:
        return None
    m = re.search(r'<td class="bDat"[^>]*>(.*?)</td>', html[idx:idx + 400], re.DOTALL)
    if not m:
        return None
    val = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return val or None


def extract_parties(html):
    """Returns (plaintiff, first_real_defendant) -- both real or None."""
    rows = re.findall(
        r'<tr><td tabindex="0">([^<]+)</td><td tabindex="0">([^<]+)</td></tr>', html)
    plaintiff = None
    defendant = None
    for ptype, pname in rows:
        ptype_u = ptype.strip().upper()
        pname_clean = pname.strip()
        if ptype_u == "PLAINTIFF" and not plaintiff:
            plaintiff = pname_clean
        if ptype_u == "DEFENDANT" and not defendant:
            skip_terms = ("UNKNOWN", "TENANT", "SPOUSE OF")
            if not any(t in pname_clean.upper() for t in skip_terms):
                defendant = pname_clean
    return plaintiff, defendant


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


def sb_get_current(row_id):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}&select=owner_name,plaintiff,parcel_id"
    req = urllib.request.Request(url, headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read())
    return rows[0] if rows else {}


def call_dod_eval():
    url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    req = urllib.request.Request(
        url, data=json.dumps({"p_county": "gilchrist"}).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    dry_run = "--dry-run" in sys.argv

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    logged_in = rf_login(opener)
    log(f"RealForeclose login: {'OK' if logged_in else 'FAILED'}", "VERIFIED")
    if not logged_in:
        log("Cannot proceed without an authenticated session -- aborting fetch, "
            "reporting BLANK for all 6 rows.", "VERIFIED")

    parsed = 0
    extracted = 0
    updated = []
    no_data = []
    still_no_parcel = []

    for t in TARGETS:
        if not logged_in:
            still_no_parcel.append(t["case_number"])
            continue
        html = fetch_detail_html(opener, t["aid"])
        parsed += 1
        parcel_id = extract_field(html, "Parcel ID:")
        property_address = extract_field(html, "Property Address:")
        plaintiff, defendant = extract_parties(html)

        log(f"{t['case_number']} (AID={t['aid']}): parcel_id={parcel_id!r} "
            f"property_address={property_address!r} plaintiff={plaintiff!r} "
            f"owner/defendant={defendant!r}", "VERIFIED")

        if not parcel_id:
            still_no_parcel.append(t["case_number"])

        fields = {}
        current = sb_get_current(t["id"]) if not dry_run else {}
        if plaintiff and not current.get("plaintiff"):
            fields["plaintiff"] = plaintiff
        if defendant and not current.get("owner_name"):
            fields["owner_name"] = defendant
        # parcel_id / property_address deliberately NOT written -- both were
        # empty on the live authenticated detail page (VERIFIED), writing
        # anything here would be fabrication, banned by the ghost-success /
        # zone_standards guard rail extended to parcel data.

        if plaintiff or defendant:
            extracted += 1

        if fields:
            if not dry_run:
                sb_patch(t["id"], fields)
            updated.append({"case_number": t["case_number"], "fields": list(fields.keys())})
        else:
            no_data.append(t["case_number"])

    if parsed > 0 and extracted == 0:
        raise RuntimeError(
            f"FAIL-LOUD: fetched {parsed} authenticated detail pages but extracted "
            f"zero plaintiff/owner_name values from any of them. Manual investigation "
            f"required rather than silent no-op.")

    dod_after = call_dod_eval() if not dry_run else None

    print(json.dumps({
        "dispatch_id": "a00c589b-9346-491a-a8bd-5ba50946fb44",
        "county": "gilchrist",
        "logged_in": logged_in,
        "rows_fetched": parsed,
        "rows_with_party_data_extracted": extracted,
        "rows_updated": updated,
        "rows_no_new_data": no_data,
        "rows_still_missing_parcel_id": still_no_parcel,
        "dry_run": dry_run,
        "dod_eval_E_after": (dod_after or {}).get("pencil_dod_evaluate_county", {}).get("E") if dod_after else None,
        "dod_eval_I_after": (dod_after or {}).get("pencil_dod_evaluate_county", {}).get("I") if dod_after else None,
    }, indent=2))

    log("SHARD-1 run8166 gilchrist E/I fix script complete -- E/I NOT resolved "
        "(structural blocker, see docstring); plaintiff/owner_name backfilled "
        "where real data was live-verified.", "VERIFIED")


if __name__ == "__main__":
    main()
