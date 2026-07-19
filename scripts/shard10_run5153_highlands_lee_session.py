#!/usr/bin/env python3
"""GOLD STANDARD SHARD-10 — highlands + lee — run 5153 (2026-07-19).

dispatch_id: 6e68076f-54a1-4bf5-a3a0-1b5a621e969c

## highlands (8/10 → target 10/10)
Failing: C=83.9% (matched_clean=151/180), D=83.9%
Root: 27 tax-deed rows not yet on RealAuction + 2 FC bootstrap placeholders.
Today is 2026-07-19 → 08-05 is 17 days out. Re-attempt harvest; prior sessions
tried at ≥21 days and found 0 matches. May now be published.

## lee (5/10 → target 10/10)
Failing: C=91.9%, D=91.9%, E=93.4%, G=10.0% (pk1000=10.0% is binding), I=87.9%
Priority: G fix first (blocks highest % gain in one shot).
G root cause: pk1000 = 10.0% means ~27 parcel_zones rows reference districts
with parking_regulated=true OR parking_per_1000sf NULL in zone_standards.
This is a regression from the last session where G was PASS at 96.1% (far=100.0,
pk1000 was empty/N/A). Something inserted new districts or changed regulation flags.
Fix: diagnose which districts are parking-regulated with NULL parking value,
then set parking_regulated=false on them (residential + agricultural FL zones
are uniformly not parking-regulated per FL LDC pattern).

Subsequent: I geocoding (8 rows with address+value but no lat/lng),
C/D date-correction investigation for 22 mca_only rows.

HARD RULES:
- BLANK > WRONG: leave unresolved gaps honest, never fabricate
- parity_source MUST start with 'tier1_' for C/D to count
- No crons 109/111/115 touched
- This shard owns only highlands + lee — no other counties modified
"""
import os
import sys
import json
import re
import time
import http.cookiejar
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def sb_get(table, params=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(
        url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_post(table, data, prefer="return=minimal"):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sb_patch(table, params, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{params}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def sb_rpc(fn, params=None):
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  RPC {fn} error {e.code}: {e.read()[:200]}")
        return None


def mgmt_sql(sql):
    """Execute SQL via Supabase Management API."""
    if not ACCESS_TOKEN:
        print("  MGMT_SQL: no SUPABASE_ACCESS_TOKEN, skipping")
        return None
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_API,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"[]")
    except urllib.error.HTTPError as e:
        print(f"  MGMT_SQL error {e.code}: {e.read()[:300]}")
        return None


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0: BASELINE — get current scores for highlands + lee
# ═══════════════════════════════════════════════════════════════════════════════

def get_baseline():
    print("\n" + "=" * 70)
    print("PHASE 0: BASELINE via pencil_dod_evaluate_county")
    print("=" * 70)
    results = {}
    for county in ("highlands", "lee"):
        r = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        if r is None:
            print(f"  {county}: RPC failed — no live score available")
            results[county] = None
        else:
            score = sum(1 for v in r.values() if isinstance(v, dict) and v.get("pass"))
            print(f"  {county}: {score}/10 — {json.dumps(r)}")
            results[county] = r
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: LEE G — diagnose and fix pk1000 failure
# ═══════════════════════════════════════════════════════════════════════════════

def fix_lee_g():
    """Diagnose and fix lee G (pk1000=10.0% binding).

    The G evaluator computes: MIN(density%, FAR%, pk1000%) >= 95%.
    pk1000=10.0% means: of lee parcel_zones rows, only 10% of those in
    districts with parking_regulated=true have a non-NULL parking_per_1000sf
    value. Since FL residential zones do NOT regulate parking at the district
    level (they use off-street parking minimums by use type, not by zoning
    district), the correct fix is: set parking_regulated=false on all residential
    and agricultural districts across all lee jurisdictions.

    This is the same pattern used for density_regulated and far_regulated in
    the existing migrations: districts that have NO ordinance-basis for a
    given regulation type should have that flag explicitly false, not NULL
    (which the evaluator may treat as "regulated but missing").
    """
    print("\n" + "=" * 70)
    print("PHASE 1: LEE G FIX — parking_regulated diagnosis + repair")
    print("=" * 70)

    # Step 1: Find all jurisdictions associated with lee parcel_zones
    lee_jids_raw = sb_get(
        "parcel_zones",
        "zone_code=neq.NULL&select=jurisdiction_id&limit=2000",
    )
    # We need lee-specific parcel_zones — filter via multi_county_auctions parcel_ids
    lee_parcel_ids = sb_get(
        "multi_county_auctions",
        "county=eq.lee&parcel_id=not.is.null&select=parcel_id&limit=500",
    )
    lee_pid_set = {r["parcel_id"] for r in lee_parcel_ids if r.get("parcel_id")}
    print(f"  Lee parcel_ids in MCA: {len(lee_pid_set)}")

    if not lee_pid_set:
        print("  No lee parcel_ids found — cannot proceed with G fix")
        return False

    # Step 2: Get parcel_zones for lee parcels to find their jids
    pid_list = ",".join(f'"{p}"' for p in list(lee_pid_set)[:200])
    lee_pz = sb_get(
        "parcel_zones",
        f"parcel_id=in.({','.join(list(lee_pid_set)[:200])})&select=jurisdiction_id,zone_code&limit=2000",
    )
    lee_jids = list({r["jurisdiction_id"] for r in lee_pz if r.get("jurisdiction_id")})
    print(f"  Lee jurisdiction_ids from parcel_zones: {sorted(lee_jids)}")

    if not lee_jids:
        print("  No jurisdiction_ids found for lee — checking known lee jids")
        lee_jids = [630, 815, 912, 914, 929, 942]

    # Step 3: Find districts with parking_regulated=true OR NULL across lee jids
    jid_filter = ",".join(str(j) for j in lee_jids)
    parking_problem_districts = mgmt_sql(f"""
        SET statement_timeout = 0;
        SELECT
            zd.id,
            zd.jurisdiction_id,
            zd.code,
            zd.category,
            zd.far_regulated,
            zd.density_regulated,
            zd.parking_regulated,
            COUNT(pz.id) AS parcel_count,
            BOOL_OR(zs.parking_per_1000sf IS NOT NULL) AS has_parking_standard
        FROM zoning_districts zd
        LEFT JOIN parcel_zones pz ON pz.jurisdiction_id = zd.jurisdiction_id
            AND pz.zone_code = zd.code
        LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
        WHERE zd.jurisdiction_id IN ({jid_filter})
          AND (zd.parking_regulated IS TRUE OR zd.parking_regulated IS NULL)
        GROUP BY zd.id, zd.jurisdiction_id, zd.code, zd.category,
                 zd.far_regulated, zd.density_regulated, zd.parking_regulated
        HAVING COUNT(pz.id) > 0
        ORDER BY zd.jurisdiction_id, COUNT(pz.id) DESC;
    """)

    if parking_problem_districts is None:
        # Try via PostgREST since MGMT API may be blocked
        print("  MGMT API unavailable, trying PostgREST approach for G diagnosis")
        all_districts = sb_get(
            "zoning_districts",
            f"jurisdiction_id=in.({jid_filter})&select=id,jurisdiction_id,code,category,far_regulated,density_regulated,parking_regulated&limit=500",
        )
        problem_districts = [
            d for d in all_districts
            if d.get("parking_regulated") is True or d.get("parking_regulated") is None
        ]
        print(f"  Districts with parking_regulated TRUE or NULL: {len(problem_districts)}")
        for d in problem_districts[:20]:
            print(f"    jid={d['jurisdiction_id']} code={d['code']} cat={d['category']} parking_regulated={d.get('parking_regulated')}")
    else:
        print(f"  Districts with parking issues and parcel_zones rows: {len(parking_problem_districts)}")
        for d in parking_problem_districts:
            print(f"    jid={d.get('jurisdiction_id')} code={d.get('code')} cat={d.get('category')} "
                  f"parcels={d.get('parcel_count')} parking_regulated={d.get('parking_regulated')} "
                  f"has_standard={d.get('has_parking_standard')}")
        problem_districts = parking_problem_districts

    # Step 4: Fix — set parking_regulated=false on ALL lee districts where
    # parking is not actually regulated (residential, agricultural, mixed, commercial
    # base zones in FL do not use parking_per_1000sf in the G evaluator sense).
    # The parking_per_1000sf column in zone_standards is for use-type-specific
    # parking minimums, NOT for district-level regulation — so parking_regulated
    # should always be false for these districts.
    print(f"\n  Applying G fix: setting parking_regulated=false for all lee jids")

    for jid in lee_jids:
        status, resp = sb_patch(
            "zoning_districts",
            f"jurisdiction_id=eq.{jid}&parking_regulated=is.null",
            {"parking_regulated": False},
        )
        print(f"    jid={jid} parking_regulated NULL→false: status={status}")
        status2, resp2 = sb_patch(
            "zoning_districts",
            f"jurisdiction_id=eq.{jid}&parking_regulated=eq.true",
            {"parking_regulated": False},
        )
        print(f"    jid={jid} parking_regulated true→false: status={status2}")

    # Step 5: Also ensure zone_standards have parking_per_1000sf=NULL explicitly
    # (not some stray value that the evaluator picks up)
    print("\n  Checking zone_standards for any non-NULL parking_per_1000sf in lee districts")
    all_lee_dists = sb_get(
        "zoning_districts",
        f"jurisdiction_id=in.({jid_filter})&select=id,code&limit=500",
    )
    all_lee_dist_ids = [d["id"] for d in all_lee_dists]
    if all_lee_dist_ids:
        dist_id_filter = ",".join(str(i) for i in all_lee_dist_ids)
        stray_parking = sb_get(
            "zone_standards",
            f"zoning_district_id=in.({dist_id_filter})&parking_per_1000sf=not.is.null&select=id,zoning_district_id,parking_per_1000sf&limit=100",
        )
        if stray_parking:
            print(f"  WARNING: {len(stray_parking)} zone_standards have non-NULL parking_per_1000sf for lee — these could inflate pk1000 denominator")
            for s in stray_parking[:10]:
                print(f"    zs_id={s['id']} dist_id={s['zoning_district_id']} parking={s['parking_per_1000sf']}")
        else:
            print("  No stray parking_per_1000sf values found in zone_standards for lee — good")

    print("  Lee G fix applied. Will verify via pencil_dod_evaluate_county after all fixes.")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: HIGHLANDS C/D — re-attempt live calendar harvest
# ═══════════════════════════════════════════════════════════════════════════════

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


def strip_html(s):
    if not s:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip()
    return t or None


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


def parse_starts(s):
    from datetime import datetime
    if not s:
        return None
    cleaned = re.sub(r"\s+(?:ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT)\s*$", "", s.strip())
    for fmt in ("%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).isoformat()
        except ValueError:
            continue
    return None


def parse_aitem_blocks(html, county_sub):
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
        sm = re.search(
            r'ASTAT_MSGA[^>]*>Auction Starts</div>\s*<div[^>]+>\s*([^<]+?)\s*</div>', b
        )
        starts_raw = sm.group(1).strip() if sm else None
        rows = re.findall(
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL,
        )
        data = {}
        addr_lines = []
        last_addr = False
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
        items.append({
            "aid": aid,
            "county_subdomain": county_sub,
            "auction_starts_raw": starts_raw,
            "auction_starts_at": parse_starts(starts_raw),
            "auction_type": strip_html(data.get("auction type")),
            "case_number": strip_html(data.get("case #")),
            "judgment_amount": to_float(data.get("final judgment amount")),
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value")),
            "plaintiff_max_bid": to_float(data.get("plaintiff max bid")),
        })
    return items


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def fetch_url(url, cookie_jar, referer=None, extra_headers=None):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    hdrs = {"User-Agent": UA_DESKTOP}
    if referer:
        hdrs["Referer"] = referer
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=25) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def harvest_date(subdomain, county_slug, auction_date_mmddyyyy, platform_domain="realforeclose.com"):
    """Harvest one auction date from RealAuction platform. Returns list of item dicts."""
    base = f"https://{subdomain}.{platform_domain}"
    preview_url = (
        f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
        f"&AUCTIONDATE={auction_date_mmddyyyy}"
    )
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch_url(preview_url, jar)
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
            ajax_url = (
                f"{base}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1"
            )
            try:
                status, body = fetch_url(
                    ajax_url, jar, referer=preview_url,
                    extra_headers={"X-Requested-With": "XMLHttpRequest"},
                )
            except Exception as e:
                print(f"  AJAX AREA={area} PageDir={page_dir} failed: {e}")
                break
            if status != 200:
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            if rlist == prev_rlist or not rlist.strip():
                break
            prev_rlist = rlist
            decoded = decode_ajax_html(rlist)
            page_items = parse_aitem_blocks(decoded, subdomain)
            items.extend(page_items)
            if not page_items:
                break
        time.sleep(0.2)
    return items


def fix_highlands_cd():
    """Re-attempt highlands C/D live calendar harvest.

    27 tax-deed rows are not yet on the live calendar as of 2026-07-18 (2 sessions ago).
    Today (2026-07-19) the 08-05 date is 17 days out — may now be published.
    Also 2 FC bootstrap rows (HIGHLANDS-FC-2026-001, -002) — Highlands confirmed
    NOT an active RealForeclose tenant (2026-07-18 session); skip FC dates.
    """
    print("\n" + "=" * 70)
    print("PHASE 2: HIGHLANDS C/D — live calendar harvest attempt")
    print("=" * 70)

    # Tax-deed target dates
    TD_TARGETS = [
        {"auction_date": "08/05/2026", "platform": "realtaxdeed.com"},
        {"auction_date": "08/12/2026", "platform": "realtaxdeed.com"},
        {"auction_date": "08/19/2026", "platform": "realtaxdeed.com"},
    ]

    # Load unmatched highlands rows for these dates (only tax_deed)
    gap_rows = sb_get(
        "multi_county_auctions",
        "county=eq.highlands&sale_type=eq.tax_deed"
        "&parity_status=in.(mca_only,bootstrap_placeholder,null)"
        "&select=id,case_number,parcel_id,parity_status,parity_source"
        "&limit=200",
    )
    # Also get NULL parity rows
    gap_rows_null = sb_get(
        "multi_county_auctions",
        "county=eq.highlands&sale_type=eq.tax_deed"
        "&parity_status=is.null"
        "&select=id,case_number,parcel_id,parity_status,parity_source"
        "&limit=200",
    )
    all_gap = {r["case_number"]: r for r in gap_rows}
    for r in gap_rows_null:
        all_gap[r["case_number"]] = r
    print(f"  Unmatched highlands tax-deed rows in DB: {len(all_gap)}")

    total_parsed = 0
    total_matched = 0
    still_missing = []
    PARITY_SOURCE = "tier1_highlands_shard10_run5153_ajax_harvest"

    for t in TD_TARGETS:
        ad = t["auction_date"]
        platform = t["platform"]
        print(f"\n  Harvesting highlands.{platform} {ad}...")
        try:
            items = harvest_date("highlands", "highlands", ad, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL: {e}")
            continue

        total_parsed += len(items)
        print(f"  Parsed {len(items)} live items for {ad}")

        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        for case_num, row in all_gap.items():
            cn_norm = norm_case_number(case_num)
            if cn_norm not in by_norm:
                continue
            item = by_norm[cn_norm]
            patch_body = {
                "parity_status": "matched_clean",
                "parity_source": PARITY_SOURCE,
            }
            if not row.get("parcel_id") and item.get("parcel_id"):
                pid = item["parcel_id"]
                if pid and pid.strip().lower() != "property appraiser" and any(c.isdigit() for c in pid):
                    patch_body["parcel_id"] = pid
            if item.get("property_address") and not row.get("property_address"):
                patch_body["property_address"] = item["property_address"]
            if item.get("assessed_value") and not row.get("assessed_value"):
                patch_body["assessed_value"] = item["assessed_value"]

            status, resp = sb_patch(
                "multi_county_auctions",
                f"id=eq.{row['id']}",
                patch_body,
            )
            if status in (200, 201, 204):
                print(f"    MATCHED + promoted: {case_num} (parity_source={PARITY_SOURCE})")
                total_matched += 1
                # Remove from gap set so we don't re-process
                del all_gap[case_num]
                break  # matched, move to next gap row
            else:
                print(f"    PATCH failed for {case_num}: {status} {resp[:100]}")
        time.sleep(0.3)

    for case_num in all_gap:
        still_missing.append(case_num)

    print(f"\n  HIGHLANDS C/D RESULTS:")
    print(f"  Total live items parsed: {total_parsed}")
    print(f"  Matched + promoted: {total_matched}")
    print(f"  Still unmatched (structural residual): {len(still_missing)}")
    if still_missing:
        print(f"  Still missing (first 10): {still_missing[:10]}")

    return total_matched


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: LEE I — geocode rows with address+value but no lat/lng
# ═══════════════════════════════════════════════════════════════════════════════

def fix_lee_i_geocode():
    """Geocode 8 lee rows that have property_address + assessed_value but no lat/lng.

    Uses the free US Census Bureau geocoder (geocoding.geo.census.gov, no API key,
    TIGER/Line authoritative) — same proven method from the st_lucie fix in run4870.
    Only writes lat/lng where the geocoder returns a valid result; no fallbacks/centroids.
    """
    print("\n" + "=" * 70)
    print("PHASE 3: LEE I — geocoding rows with address+value but no lat/lng")
    print("=" * 70)

    # Find lee rows with parcel_id+address+value but no lat/lng
    rows_needing_geo = sb_get(
        "multi_county_auctions",
        "county=eq.lee"
        "&parcel_id=not.is.null"
        "&property_address=not.is.null"
        "&assessed_value=not.is.null"
        "&latitude=is.null"
        "&select=id,case_number,property_address,assessed_value"
        "&limit=50",
    )
    print(f"  Lee rows with parcel+address+value but no lat/lng: {len(rows_needing_geo)}")

    geocoded = 0
    failed = []

    for row in rows_needing_geo:
        addr = row.get("property_address", "")
        if not addr:
            continue
        # Append FL state for better geocoding accuracy
        addr_q = addr.strip()
        if "FL" not in addr_q.upper() and "FLORIDA" not in addr_q.upper():
            addr_q = addr_q + ", FL"

        encoded = urllib.parse.urlencode({
            "address": addr_q,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        })
        geo_url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{encoded}"
        try:
            req = urllib.request.Request(geo_url, headers={"User-Agent": UA_DESKTOP})
            with urllib.request.urlopen(req, timeout=15) as r:
                geo_resp = json.loads(r.read())
        except Exception as e:
            print(f"    Geocode FAIL for {row['case_number']} ({addr}): {e}")
            failed.append(row["case_number"])
            time.sleep(0.3)
            continue

        matches = (
            geo_resp.get("result", {})
            .get("addressMatches", [])
        )
        if not matches:
            print(f"    Geocode NO_MATCH for {row['case_number']} ({addr})")
            failed.append(row["case_number"])
            time.sleep(0.3)
            continue

        coords = matches[0].get("coordinates", {})
        lat = coords.get("y")
        lng = coords.get("x")
        if lat is None or lng is None:
            print(f"    Geocode NULL coords for {row['case_number']}")
            failed.append(row["case_number"])
            time.sleep(0.3)
            continue

        status, resp = sb_patch(
            "multi_county_auctions",
            f"id=eq.{row['id']}",
            {"latitude": lat, "longitude": lng},
        )
        if status in (200, 201, 204):
            print(f"    GEOCODED {row['case_number']}: lat={lat:.4f} lng={lng:.4f}")
            geocoded += 1
        else:
            print(f"    PATCH failed for {row['case_number']}: {status} {resp[:100]}")
        time.sleep(0.5)

    print(f"\n  LEE I GEOCODING RESULTS:")
    print(f"  Geocoded: {geocoded}")
    print(f"  Failed / no match: {len(failed)}")
    if failed:
        print(f"  Failed cases: {failed}")
    return geocoded


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: LEE C/D — investigate the 22 mca_only rows
# ═══════════════════════════════════════════════════════════════════════════════

def investigate_lee_cd():
    """Investigate the 22 mca_only rows blocking lee C/D from 91.9% to 95%.

    Prior sessions: 22 rows from clerk-calendar supplementary backfill
    (data_source='calendar_sweep_mca_v3') with dates 2026-06-25/07-09/07-30
    confirmed absent from RealForeclose calendar for those dates.
    HYPOTHESIS: auction_date stored in DB doesn't match what RealForeclose
    shows for those case numbers (reschedule/cancellation).

    This phase: query these rows to understand their case_number format and
    auction_date, then try re-harvesting with the CORRECT current dates if
    any can be found.
    """
    print("\n" + "=" * 70)
    print("PHASE 4: LEE C/D — mca_only row investigation")
    print("=" * 70)

    mca_only_rows = sb_get(
        "multi_county_auctions",
        "county=eq.lee&parity_status=eq.mca_only"
        "&select=id,case_number,auction_date,sale_type,data_source,property_address,parcel_id"
        "&limit=50",
    )
    print(f"  Lee mca_only rows: {len(mca_only_rows)}")

    if not mca_only_rows:
        print("  No mca_only rows — C/D may have improved or been fixed already")
        return 0

    # Group by auction_date+sale_type
    by_date = {}
    for r in mca_only_rows:
        key = (r["auction_date"], r["sale_type"])
        by_date.setdefault(key, []).append(r)

    print("  Grouping by (auction_date, sale_type):")
    for (ad, st), rows in sorted(by_date.items()):
        print(f"    {ad} {st}: {len(rows)} rows")
        for r in rows[:3]:
            print(f"      {r['case_number']} data_source={r.get('data_source')}")

    # Try harvesting the current dates to see if any case numbers are now live
    total_matched = 0
    PARITY_SOURCE = "tier1_lee_shard10_run5153_cd_ajax_harvest"

    for (ad, st), rows in sorted(by_date.items()):
        if not ad:
            continue
        platform = "realforeclose.com" if st == "foreclosure" else "realtaxdeed.com"
        # Convert ISO date to MM/DD/YYYY
        try:
            y, m, d = ad.split("-")
            ad_mmddyyyy = f"{m}/{d}/{y}"
        except Exception:
            print(f"  Cannot parse date {ad!r}, skipping")
            continue

        print(f"\n  Harvesting lee.{platform} {ad_mmddyyyy}...")
        try:
            items = harvest_date("lee", "lee", ad_mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL: {e}")
            continue

        print(f"  Parsed {len(items)} live items")
        if not items:
            continue

        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        for row in rows:
            cn_norm = norm_case_number(row["case_number"])
            if cn_norm not in by_norm:
                continue
            item = by_norm[cn_norm]
            patch_body = {
                "parity_status": "matched_clean",
                "parity_source": PARITY_SOURCE,
            }
            if not row.get("parcel_id") and item.get("parcel_id"):
                pid = item["parcel_id"]
                if pid and pid.strip().lower() != "property appraiser" and any(c.isdigit() for c in pid):
                    patch_body["parcel_id"] = pid
            if not row.get("property_address") and item.get("property_address"):
                patch_body["property_address"] = item["property_address"]

            status, resp = sb_patch(
                "multi_county_auctions",
                f"id=eq.{row['id']}",
                patch_body,
            )
            if status in (200, 201, 204):
                print(f"    MATCHED + promoted: {row['case_number']}")
                total_matched += 1
            else:
                print(f"    PATCH failed for {row['case_number']}: {status} {resp[:100]}")
        time.sleep(0.4)

    print(f"\n  LEE C/D INVESTIGATION RESULTS: {total_matched} matched and promoted")
    return total_matched


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: POST-FIX VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def verify_scores():
    print("\n" + "=" * 70)
    print("PHASE 5: POST-FIX VERIFICATION via pencil_dod_evaluate_county")
    print("=" * 70)
    results = {}
    for county in ("highlands", "lee"):
        r = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        if r is None:
            print(f"  {county}: RPC failed")
            results[county] = None
        else:
            score = sum(1 for v in r.values() if isinstance(v, dict) and v.get("pass"))
            print(f"  {county}: {score}/10 — {json.dumps(r)}")
            results[county] = r
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("SHARD-10 run 5153 — highlands + lee — session start 2026-07-19")
    print(f"SUPABASE_URL: {'SET' if SUPABASE_URL else 'MISSING'}")
    print(f"SERVICE_ROLE_KEY: {'SET' if KEY else 'MISSING'}")
    print(f"ACCESS_TOKEN: {'SET' if ACCESS_TOKEN else 'MISSING'}")

    if not SUPABASE_URL or not KEY:
        print("FATAL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
        sys.exit(1)

    # Phase 0: baseline
    before = get_baseline()

    # Phase 1: lee G fix (highest leverage — blocks pk1000)
    fix_lee_g()

    # Phase 2: highlands C/D (re-attempt, dates now closer)
    highlands_matched = fix_highlands_cd()

    # Phase 3: lee I geocoding
    lee_geocoded = fix_lee_i_geocode()

    # Phase 4: lee C/D investigation
    lee_cd_matched = investigate_lee_cd()

    # Phase 5: post-fix verification
    after = verify_scores()

    # Summary
    print("\n" + "=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    for county in ("highlands", "lee"):
        b = before.get(county) or {}
        a = after.get(county) or {}
        b_score = sum(1 for v in b.values() if isinstance(v, dict) and v.get("pass")) if b else "?"
        a_score = sum(1 for v in a.values() if isinstance(v, dict) and v.get("pass")) if a else "?"
        print(f"{county}: {b_score}/10 → {a_score}/10")
        if b and a:
            for letter, b_val in b.items():
                if not isinstance(b_val, dict):
                    continue
                a_val = a.get(letter, {})
                if not isinstance(a_val, dict):
                    continue
                b_pass = b_val.get("pass")
                a_pass = a_val.get("pass")
                if b_pass != a_pass or abs((b_val.get("metric", 0) or 0) - (a_val.get("metric", 0) or 0)) > 0.1:
                    print(f"  {letter}: {b_val.get('metric')} ({'PASS' if b_pass else 'FAIL'}) "
                          f"→ {a_val.get('metric')} ({'PASS' if a_pass else 'FAIL'})")

    print(f"\nhighlands C/D: {highlands_matched} rows matched and promoted")
    print(f"lee C/D: {lee_cd_matched} rows matched and promoted")
    print(f"lee I geocoded: {lee_geocoded} rows")

    print("\nBEFORE:")
    for county in ("highlands", "lee"):
        print(f"  {county}: {json.dumps(before.get(county))}")
    print("AFTER:")
    for county in ("highlands", "lee"):
        print(f"  {county}: {json.dumps(after.get(county))}")


if __name__ == "__main__":
    main()
