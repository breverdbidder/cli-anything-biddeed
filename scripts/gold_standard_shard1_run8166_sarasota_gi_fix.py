#!/usr/bin/env python3
"""
Gold Standard SHARD-1 (dispatch a00c589b-9346-491a-a8bd-5ba50946fb44, loop run
8166): sarasota letters G (zoning parking/FAR/density coverage) and I (auction
card completeness).

BASELINE (VERIFIED live 2026-08-02 via
SELECT public.pencil_dod_evaluate_county('sarasota');):
  G FAIL metric=66.7 [density=93.2 far=95.5 pk1000=66.7] -- pk1000 is the
    binding constraint (LEAST(density,far,pk1000)).
  I FAIL metric=94.3 [card_complete=347 of 368] -- fresh regression, the
    auctions_total denominator roughly doubled (187->368) since the campaign
    brief's last snapshot (95.2%, 178/187); this session re-diagnoses from
    scratch rather than assuming the old 20-row gap still applies unchanged.

=====================================================================
LETTER G -- root cause (live SQL against v_zoning_gold_standard_kpi_v3 +
parcel_zones/zoning_districts/zone_standards for sarasota):
=====================================================================
Only 9 of sarasota's 346 zoned parcels are pk1000_applicable (commercial/
industrial category, not a PUD). Of those 9, 6 already have parking_per_1000sf
(4.00, correctly sourced from Sarasota County LDC/UDC Sec. 124-120(g)(2) via
https://www.zoneomics.com/code/sarasota-county-unincorporated-FL/chapter_8,
same source_url already on file for the CG/CSC districts). 3 districts are
missing parking_per_1000sf entirely (parcel-count-ranked, all n=1 parcel):
  - CN  (Commercial Neighborhood, jurisdiction_id=824, unincorporated county)
  - PID (Planned Commerce, Economic or Industrial Development, jid=824)
  - DTC (Downtown Core, jurisdiction_id=1516, City of Sarasota)

RESEARCH (WebSearch + WebFetch against library.municode.com, elaws.us,
zoneomics.com -- Firecrawl unavailable this session, "Insufficient credits"):

1. CN -- FIXED. WebSearch independently corroborates "the CN (Commercial-
   Neighborhood) zoning district permits only certain types of neighborhood
   scale commercial uses" (same use category -- retail/personal-service/office
   -- as CG "Commercial" and CSC "Commercial", both of which already carry
   parking_per_1000sf=4.00 sourced from Sec. 124-120(g)(2)'s "Retail Sales and
   Service: 1 per 250 SF" / "Office: 1 per 250 SF" table (WebFetch-confirmed
   live against zoneomics.com/code/sarasota-county-unincorporated-FL/chapter_8,
   2026-08-02). Sec. 124-120 is a USE-based table applied county-wide across
   all commercial zoning districts (WebSearch-corroborated: "the parking
   requirements contained in Section 7.1 ... for all zoning districts shall
   apply"), not district-specific, so applying the same 4.00 ratio to CN is
   the same real ordinance value already trusted for CG/CSC, not a new guess.
   -> zone_standards.parking_per_1000sf = 4.00, source_url/ordinance_section
      set to the same citation already on file for CG/CSC.

2. PID -- MARKED NOT-APPLICABLE (pk1000_regulated=false, far_regulated=false),
   NOT backfilled with a number. WebSearch of Sec. 3.14 (Planned Development
   Districts) confirms: "Article 3.14 applies to the Planned Unit Development
   (PUD), Commercial Marine/Planned Development (CM/PD), Planned Industrial
   Development (PID), Planned Commerce Development (PCD) ... Districts,"
   requiring "a development concept plan ... all stipulations shall be
   recorded in the deed records of Sarasota County" -- i.e. PID parking (like
   PUD, which the existing v_zoning_district_applicability view already
   excludes via `name !~ 'pud'`) is set case-by-case per development order,
   not by a single fixed county-wide ratio. Writing a specific number here
   would be fabrication (BANNED -- guessed standards are ghost-success per
   this task's hard guardrails). Structurally identical treatment to the
   PUD carve-out already baked into v_zoning_district_applicability.

3. DTC -- LEFT NULL, reported as residual gap. Multiple WebSearch + WebFetch
   attempts (library.municode.com Article VII Div 2 "Off-Street Parking and
   Loading" Sec. VII-206 "specific zone districts", zoneomics.com/code/
   sarasota-FL/chapter_4, harshmanrealestate.com downtown zone PDF) could not
   surface a specific DTC parking ratio or confirmed parking-exempt status
   (Municode direct fetch returned HTTP 403; the harshmanrealestate PDF did
   not extract as readable text; WebSearch snippets never quoted a DTC-
   specific number). Per NEVER-LIE / hard guardrails ("never write a
   zone_standards value you did not read from a real ordinance/municode
   source"), this session does NOT guess a City of Sarasota downtown parking
   ratio. Flagged explicitly as residual, not silently dropped.

Net effect on G: fills 1 of 3 missing pk1000 districts with a real backfilled
value (CN, 1 parcel), reclassifies 1 as legitimately not-applicable via real
ordinance evidence (PID, 1 parcel) rather than leaving it as a false gap in
the KPI denominator, and leaves 1 (DTC, 1 parcel) as an honest unresolved gap.
Expected KPI shift: pk1000_applicable_parcels drops from 9 to 8 (PID no longer
counted as applicable), pk1000-with-value rises from 6 to 7 -> pct_pk1000 =
round(100*7/8,1) = 87.5. Still short of the 95% pass threshold (LEAST also
gated by density=93.2), reported honestly below -- not claimed as a pass.

=====================================================================
LETTER I -- root cause (live SQL replicating pencil_dod_evaluate_county's
exact letter-I predicate for sarasota, 2026-08-02):
=====================================================================
21 of 368 scoped rows fail card_complete. Breaking down by blocker (fresh
diagnosis, NOT reused from the prior 347/367 session's stale 20-row list --
the row set changed with the denominator):

  (a) 5 rows: no property_address at all ("Address Not Available, Sarasota
      County, FL" placeholder or NULL), same 2024 CA 006* cluster already
      flagged out-of-scope by the prior sarasota_shard4_9f070f2b session
      (needs court-docket address discovery, a different pipeline). NOT
      attempted here -- still out of scope.

  (b) 7 rows: property_address/lat/lon/assessed_value ALL present but with
      IDENTICAL placeholder values (property_address literally "Address Not
      Available, Sarasota County, FL", lat/lon = county centroid fallback
      27.3364/-82.5307, assessed_value = flat 185000.0 across all 7) and
      parcel_id NULL. This is the "join-format mismatch" flagged in the task
      brief as needing investigation before assuming fresh backfill -- LIVE
      CHECK via the sarasota.realforeclose.com AJAX PREVIEW calendar (forked
      from scripts/shard2_run2450_ajax_realforeclose_harvest.py, session-
      cookie + desktop UA, bare curl gets 403 from the WAF as documented)
      for each row's own auction_date shows:
        - 2025 CC 008713 SC (06/30/2026) -> REAL parcel_id 0851130021,
          real address "422 CYPRESS FOREST DR, ENGLEWOOD, 34223",
          real assessed_value 206000.0 -- genuinely backfillable.
        - 2025 CC 007829 NC, 2024 CC 007808 NC -> RealForeclose's OWN listing
          says parcel_id="TIMESHARE" (no single parcel).
        - 2025 CA 003095 NC -> RealForeclose's OWN listing says
          parcel_id="MULTIPLE PARCEL" (no single parcel).
        - 2025 CA 001336 NC, 2024 CA 006165 NC, 2025 CA 002873 NC ->
          RealForeclose's OWN listing says parcel_id="Property Appraiser"
          (a known placeholder RealForeclose itself uses when the court
          filing didn't supply one -- see is_real_parcel_id() filtering this
          exact string in the shard10 script). Not a format mismatch on OUR
          side -- the source system itself has no single parcel_id for these
          6 cases. Cannot fabricate one. Left untouched.
      So of the 7, only 1 (2025 CC 008713 SC) is genuinely backfillable, and
      it is applied below (COALESCE-safe, only fills currently-NULL fields).

  (c) 9 rows: already have a parcel_id, but that parcel_id does not exist
      ANYWHERE in v_zoning_gold_standard_card for sarasota (confirmed live,
      zero matches for all 9 IDs, exact string -- not a padding/format
      variant). This is a letter-G zoning-coverage gap (same finding as the
      prior sarasota_shard4_9f070f2b session for a different 6-row subset),
      out of scope for a letter-I fix (no fabricated zone links). Of these 9,
      4 are ALSO missing lat/lon. Sarasota PA ArcGIS FeatureServer
      (ags3.scgov.net/.../ParcelProperty/FeatureServer/0) lookup by exact
      `account` found:
        - 0491060010 (7440 Manasota Key Rd) -> 1 unambiguous match, real
          centroid lat/lon backfilled.
        - 0129072075, 0111044001, 2028103031 -> either zero matches or the
          PA site's own `account` field uses a different (shorter, condo-
          building-level) ID scheme than our stored unit-level parcel_id, so
          no unambiguous 1:1 match exists. NOT backfilled (would risk wrong
          geo). Left untouched, flagged as residual.
      Filling 0491060010's geo is real and non-destructive, but since its
      parcel_id itself is absent from the zoning crosswalk, it does NOT flip
      card_complete for that row on its own (same "helps completeness,
      doesn't move the KPI" finding as the prior session's 2-row case).

Net effect on I: 1 row gets a real parcel_id+address+value (2025 CC 008713 SC,
still blocked from card_complete by the same-row zoning-crosswalk gap -- its
new parcel_id 0851130021 is not in v_zoning_gold_standard_card either,
confirmed live), 1 row gets real lat/lon (0491060010, same crosswalk-blocked
situation). Both are genuine data-completeness improvements but, per the same
honest math as the prior sarasota_shard4_9f070f2b session, do NOT move
card_complete off 347/368 by themselves. Reported as residual, not oversold.

Usage:
  python3 scripts/gold_standard_shard1_run8166_sarasota_gi_fix.py           # apply
  python3 scripts/gold_standard_shard1_run8166_sarasota_gi_fix.py --dry-run
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar
import re
import time
from datetime import datetime

SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_ACCESS_TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN not set", file=sys.stderr)
    sys.exit(1)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

HEADERS_REST = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

PA_FEATURESERVER = (
    "https://ags3.scgov.net/server/rest/services/Hosted/ParcelProperty/"
    "FeatureServer/0/query"
)

CG_CSC_SOURCE_URL = "https://www.zoneomics.com/code/sarasota-county-unincorporated-FL/chapter_8"
CN_ORDINANCE_SECTION = (
    "Sarasota County LDC/UDC Sec. 124-120(g)(2) Off-Street Parking Requirements "
    "Table -- 'Retail Sales and Service: 1 per 250 SF gross leasable area' / "
    "'Office: 1 per 250 SF floor area' (= 4.00 spaces/1,000sf), a USE-based "
    "table applied county-wide to all commercial zoning districts (confirmed "
    "via WebSearch: 'the parking requirements contained in Section 7.1 ... "
    "for all zoning districts shall apply'); same source_url and ratio "
    "already on file for CG and CSC (both 'Commercial' category districts in "
    "jurisdiction_id=824). CN (Commercial Neighborhood) is independently "
    "corroborated by WebSearch as permitting only 'neighborhood scale "
    "commercial uses' (retail/personal-service/office), the same use category "
    "-- applying the identical real ratio, not a new guess."
)
PID_ORDINANCE_SECTION = (
    "Sarasota County LDC/UDC Article 3, Sec. 3.14 'Planned Development "
    "Districts' -- confirmed via WebSearch: 'Article 3.14 applies to the "
    "Planned Unit Development (PUD), Commercial Marine/Planned Development "
    "(CM/PD), Planned Industrial Development (PID), Planned Commerce "
    "Development (PCD) ... Districts,' requiring 'a development concept "
    "plan ... all stipulations shall be recorded in the deed records of "
    "Sarasota County.' Parking for PID (like PUD) is set case-by-case per "
    "development order, not a single fixed county-wide ratio -- marked "
    "not-applicable rather than fabricating a number, structurally identical "
    "to the existing PUD carve-out in v_zoning_district_applicability "
    "(name !~ 'pud')."
)


def mgmt_sql(query, dry_run_label=None):
    if dry_run_label:
        print(f"[DRY-RUN] would execute: {dry_run_label}")
        return None
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            # Cloudflare WAF (error code 1010) blocks Python's default
            # urllib User-Agent on api.supabase.com -- a curl-like UA passes.
            "User-Agent": "curl/8.5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS_REST)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def rest_patch(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=data,
        method="PATCH",
        headers={**HEADERS_REST, "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


# ---------------------------------------------------------------------------
# LETTER G
# ---------------------------------------------------------------------------

def step_g_zone_standards(dry_run):
    print("\n=== LETTER G: zone_standards backfill (real ordinance only) ===")

    districts = mgmt_sql(
        "SELECT d.id, d.jurisdiction_id, d.code, d.name, d.far_regulated, "
        "d.pk1000_regulated, s.id AS std_id, s.parking_per_1000sf, s.max_far "
        "FROM zoning_districts d "
        "JOIN jurisdictions j ON j.id = d.jurisdiction_id "
        "LEFT JOIN zone_standards s ON s.zoning_district_id = d.id "
        "WHERE norm_county_key(COALESCE(j.county_name, j.county)) = 'sarasota' "
        "AND d.code IN ('CN','PID','DTC');"
    )
    print(f"  Found {len(districts)} target district rows: "
          f"{[(r['code'], r['jurisdiction_id']) for r in districts]}")

    written_standards = 0
    written_districts = 0

    for r in districts:
        code = r["code"]
        did = r["id"]
        std_id = r["std_id"]

        if code == "CN":
            if r.get("parking_per_1000sf") is not None:
                print(f"  CN (id={did}): parking_per_1000sf already set, skipping (idempotent).")
                continue
            if std_id is None:
                q = (
                    f"INSERT INTO zone_standards (zoning_district_id, parking_per_1000sf, "
                    f"source_url, ordinance_section) VALUES ({did}, 4.00, "
                    f"'{CG_CSC_SOURCE_URL}', $ord${CN_ORDINANCE_SECTION}$ord$);"
                )
                mgmt_sql(q, dry_run_label=f"INSERT zone_standards for CN (district_id={did})" if dry_run else None)
            else:
                q = (
                    f"UPDATE zone_standards SET parking_per_1000sf = 4.00, "
                    f"source_url = COALESCE(source_url, '{CG_CSC_SOURCE_URL}'), "
                    f"ordinance_section = COALESCE(ordinance_section, $ord${CN_ORDINANCE_SECTION}$ord$) "
                    f"WHERE id = {std_id} AND parking_per_1000sf IS NULL;"
                )
                mgmt_sql(q, dry_run_label=f"UPDATE zone_standards id={std_id} for CN, fill parking_per_1000sf" if dry_run else None)
            written_standards += 1
            print(f"  CN (id={did}): WROTE parking_per_1000sf=4.00 (Sec. 124-120(g)(2), same source as CG/CSC).")

        elif code == "PID":
            if r.get("pk1000_regulated") is not None or r.get("far_regulated") is not None:
                print(f"  PID (id={did}): applicability flags already set, skipping (idempotent).")
                continue
            q = (
                f"UPDATE zoning_districts SET pk1000_regulated = false, far_regulated = false, "
                f"ordinance_section = COALESCE(ordinance_section, $ord${PID_ORDINANCE_SECTION}$ord$) "
                f"WHERE id = {did} AND pk1000_regulated IS NULL AND far_regulated IS NULL;"
            )
            mgmt_sql(q, dry_run_label=f"UPDATE zoning_districts id={did} for PID, set pk1000_regulated=false, far_regulated=false" if dry_run else None)
            written_districts += 1
            print(f"  PID (id={did}): MARKED NOT-APPLICABLE for pk1000/far (Art. 3.14 planned-development, "
                  f"case-by-case parking, not a fixed ratio -- not fabricated).")

        elif code == "DTC":
            print(f"  DTC (id={did}): NO real ordinance value found this session (Municode 403, PDF unreadable, "
                  f"no WebSearch snippet quoted a DTC-specific ratio). LEFT NULL. Residual gap, not fabricated.")

    return {"written_standards": written_standards, "written_districts": written_districts}


# ---------------------------------------------------------------------------
# LETTER I -- RealForeclose AJAX harvest (forked from shard2_run2450)
# ---------------------------------------------------------------------------

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


def parse_starts(s):
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
    """Verbatim port of scripts/shard2_run2450_ajax_realforeclose_harvest.py."""
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
            r'<td[^>]*class="AD_LBL"[^>]*>(.*?)</td>\s*<td[^>]*class="AD_DTA[^"]*"[^>]*>(.*?)</td>',
            b, re.DOTALL)
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
            "case_number": strip_html(data.get("case #")),
            "parcel_id": strip_html(data.get("parcel id")),
            "property_address": ", ".join(addr_lines) if addr_lines else None,
            "assessed_value": to_float(data.get("assessed value") or data.get("property app. market value")),
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
    with opener.open(req, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def harvest_date(subdomain, auction_date_mmddyyyy):
    base = f"https://{subdomain}.realforeclose.com"
    preview_url = f"{base}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={auction_date_mmddyyyy}"
    jar = http.cookiejar.CookieJar()
    try:
        status, _ = fetch(preview_url, jar)
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
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(auction_date_mmddyyyy)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                status, body = fetch(ajax_url, jar, referer=preview_url,
                                      headers={"X-Requested-With": "XMLHttpRequest"})
            except Exception as e:
                print(f"  AJAX AREA={area} PageDir={page_dir} fetch failed: {e}")
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
                items.extend(parse_aitem_blocks(decoded, subdomain))
            time.sleep(0.4)
    return items


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    if not pid:
        return False
    bad = {"timeshare", "multiple parcel", "property appraiser"}
    if pid.strip().lower() in bad:
        return False
    return bool(re.search(r"\d", pid))


# The 7 rows found live (2026-08-02) with placeholder address="Address Not
# Available, Sarasota County, FL", lat/lon=county-centroid fallback, and
# assessed_value=185000.0 flat, parcel_id NULL -- mapped to their own
# auction_date for the AJAX PREVIEW calendar lookup.
CASE_TO_DATE = {
    "2025 CC 008713 SC": "06/30/2026",
    "2025 CC 007829 NC": "05/28/2026",
    "2025 CA 003095 NC": "05/27/2026",
    "2024 CC 007808 NC": "05/27/2026",
    "2025 CA 001336 NC": "05/15/2026",
    "2024 CA 006165 NC": "03/11/2026",
    "2025 CA 002873 NC": "03/10/2026",
}


def step_i_realforeclose_backfill(dry_run):
    print("\n=== LETTER I (part 1): RealForeclose live calendar backfill "
          "for the 7 placeholder-value rows ===")

    rows = rest_get(
        "multi_county_auctions?select=id,case_number,parcel_id,property_address,"
        "assessed_value&county=eq.sarasota&case_number=in.("
        + ",".join(urllib.parse.quote(f'"{cn}"') for cn in CASE_TO_DATE) + ")"
    )
    by_cn = {r["case_number"]: r for r in rows}
    print(f"  Matched {len(rows)} of {len(CASE_TO_DATE)} target rows in DB.")

    cache = {}
    applied = 0
    skipped_no_real_pid = []

    for cn, date in CASE_TO_DATE.items():
        row = by_cn.get(cn)
        if not row:
            print(f"  {cn}: not found in DB, skipping.")
            continue
        if row.get("parcel_id"):
            print(f"  {cn}: parcel_id already non-NULL ({row['parcel_id']}), skipping (idempotent).")
            continue
        if date not in cache:
            cache[date] = harvest_date("sarasota", date)
        items = cache[date]
        match = [it for it in items if norm_case_number(it["case_number"]) == norm_case_number(cn)]
        if not match:
            print(f"  {cn}: NOT FOUND on live {date} calendar ({len(items)} items that date). Skipping.")
            continue
        it = match[0]
        pid = it.get("parcel_id")
        if not is_real_parcel_id(pid):
            print(f"  {cn}: RealForeclose's OWN listing has no real single parcel_id "
                  f"(parcel_id={pid!r}) -- not a format mismatch on our side, cannot "
                  f"fabricate. Skipping.")
            skipped_no_real_pid.append(cn)
            continue

        body = {}
        if pid:
            body["parcel_id"] = pid
        if it.get("property_address"):
            body["property_address"] = it["property_address"]
        if it.get("assessed_value"):
            body["assessed_value"] = it["assessed_value"]
        if not body:
            continue

        if dry_run:
            print(f"  [DRY-RUN] would PATCH {cn} (id={row['id']}): {body}")
        else:
            resp = rest_patch(
                f"multi_county_auctions?id=eq.{row['id']}&parcel_id=is.null",
                body,
            )
            print(f"  {cn} (id={row['id']}): WROTE {body} -> {len(resp)} row(s) updated.")
        applied += 1

    print(f"  Applied: {applied} rows. Skipped (no real parcel_id at source): "
          f"{len(skipped_no_real_pid)} -> {skipped_no_real_pid}")
    return {"applied": applied, "skipped_no_real_pid": skipped_no_real_pid}


# ---------------------------------------------------------------------------
# LETTER I -- Sarasota PA ArcGIS geo backfill for the 2 unambiguous accounts
# ---------------------------------------------------------------------------

GEO_TARGETS = {
    # case_number: (parcel_id, expected_fulladdress_fragment)
    "2026 CA 000214 SC": "0491060010",
    "2025 CC 008713 SC": "0851130021",  # same row as the RealForeclose backfill above
}


def pa_lookup_by_account(account):
    params = {
        "where": f"account='{account}'",
        "outFields": "account,fulladdress,assd,just,zoning",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = PA_FEATURESERVER + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("features", [])


def centroid(rings):
    xs = [p[0] for p in rings]
    ys = [p[1] for p in rings]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def step_i_geo_backfill(dry_run):
    print("\n=== LETTER I (part 2): Sarasota PA ArcGIS geo backfill "
          "(only exact unambiguous account matches) ===")

    rows = rest_get(
        "multi_county_auctions?select=id,case_number,parcel_id,latitude,longitude"
        "&county=eq.sarasota&case_number=in.("
        + ",".join(urllib.parse.quote(f'"{cn}"') for cn in GEO_TARGETS) + ")"
    )
    by_cn = {r["case_number"]: r for r in rows}

    applied = 0
    for cn, expected_pid in GEO_TARGETS.items():
        row = by_cn.get(cn)
        if not row:
            print(f"  {cn}: not found in DB, skipping.")
            continue
        if row.get("latitude") is not None and row.get("longitude") is not None:
            print(f"  {cn}: lat/lon already non-NULL, skipping (idempotent).")
            continue
        pid = row.get("parcel_id") or expected_pid
        feats = pa_lookup_by_account(pid)
        if len(feats) != 1:
            print(f"  {cn} (parcel_id={pid}): {len(feats)} PA features (need exactly 1 "
                  f"for an unambiguous match). Skipping.")
            continue
        f = feats[0]
        rings = f["geometry"]["rings"][0]
        lon, lat = centroid(rings)
        print(f"  {cn} (parcel_id={pid}): PA match {f['attributes']['fulladdress']} "
              f"-> lat={lat:.6f} lon={lon:.6f}")
        if dry_run:
            print(f"  [DRY-RUN] would PATCH {cn} (id={row['id']}): latitude={lat}, longitude={lon}")
        else:
            resp = rest_patch(
                f"multi_county_auctions?id=eq.{row['id']}&latitude=is.null&longitude=is.null",
                {"latitude": lat, "longitude": lon},
            )
            print(f"  {cn} (id={row['id']}): WROTE lat/lon -> {len(resp)} row(s) updated.")
        applied += 1

    return {"applied": applied}


def step_verify():
    print("\n=== VERIFY: live pencil_dod_evaluate_county('sarasota') ===")
    result = mgmt_sql("SELECT public.pencil_dod_evaluate_county('sarasota');")
    out = result[0]["pencil_dod_evaluate_county"]
    print(json.dumps(out, indent=2))
    return out


def main():
    dry_run = "--dry-run" in sys.argv
    print("=" * 70)
    print("Sarasota Gold Standard G/I fix -- SHARD-1 run8166")
    print("=" * 70)

    g_result = step_g_zone_standards(dry_run)
    i_rf_result = step_i_realforeclose_backfill(dry_run)
    i_geo_result = step_i_geo_backfill(dry_run)

    # Fail-loud invariant: if we parsed real data but wrote nothing where we
    # expected to, don't swallow it silently.
    if not dry_run:
        if i_rf_result["applied"] == 0 and len(i_rf_result["skipped_no_real_pid"]) < len(CASE_TO_DATE):
            print("WARNING: parsed live RealForeclose data for some rows but wrote 0 -- "
                  "check for a bug (fail-loud, not swallowed).", file=sys.stderr)

    print("\n" + "=" * 70)
    print(f"G: zone_standards written={g_result['written_standards']}, "
          f"zoning_districts flag-updates={g_result['written_districts']}")
    print(f"I: RealForeclose backfill applied={i_rf_result['applied']}, "
          f"geo backfill applied={i_geo_result['applied']}")
    print("=" * 70)

    if not dry_run:
        step_verify()


if __name__ == "__main__":
    main()
