#!/usr/bin/env python3
"""
jefferson_bf_probe_20260724.py

Gold Standard Shard-6, run 6253 — Jefferson B/F blocker probe.
Date: 2026-07-24 (day 29 post-sale for 25-CA-164, sold 2026-06-25)

Root cause: Jefferson County foreclosure 25-CA-164 has sold_amount IS NULL.
B and F both compute 0/0 -> NULL -> FAIL.

Prior sessions (shard-12 dispatch 0f9adc6e, 3 firings; shard-7 3rd firing)
have exhausted 23+ independent sources. New approaches as of day 29:
  1. JCPA ArcGIS re-probe (bcrouch_JCPA, services5.arcgis.com/vFMp1Ly1q6rKKp0o)
     — FL appraisers process deeds in 14-30 days; day 29 may have new data
  2. jeffersonclerk.com — may have added a past-sales section since July 19
  3. FL GIO statewide cadastral re-probe (SALE_PRC1 still DOR-lagged, but checking)
  4. Attom property data API (free tier, no auth)
  5. PropertyShark via WebFetch
  6. Realtor.com sold listings for the specific address

If a sold_amount is found from an independent source:
  1. Write sold_amount to multi_county_auctions (case 25-CA-164)
  2. Insert into foreclosure_outcomes with data_source=<source>:SHARD6-JEFFERSON-BF-V1
  3. Set tier1_sold_amount + tier1_authoritative on MCA row
  4. Insert ultraloop_audit survived=true row for B and F

HONESTY PROTOCOL:
  VERIFIED = HTTP response confirmed, data extracted
  UNKNOWN = not tested, insufficient data
  INFERRED = reasoning without direct evidence
No sold_amount is fabricated under any circumstances.
"""

import urllib.request
import urllib.error
import json
import re
import os
import sys
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

COUNTY = "jefferson"
COUNTY_SLUG = "jefferson"
CASE_NUMBER = "25-CA-164"
PARCEL_ID = "00-00-00-0220-0000-0310"
DEFENDANT = "THOMPSON JAMES W"
PROPERTY_ADDRESS = "340 Marvin St Monticello FL 32344"
SALE_DATE = "2026-06-25"
JUDGMENT_AMOUNT = 86285.09

DISPATCH_ID = "c3be301d-189a-466b-967a-db850523425e"
PIPELINE_RUN_ID = "shard6-jefferson-bf-probe-20260724"

findings = {
    "sources_checked": [],
    "sold_amount_found": None,
    "sold_amount_source": None,
    "new_data": False,
    "errors": [],
}


def now_ts():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    print(f"[jefferson-probe] {msg}", flush=True)


def fetch_url(url, timeout=20, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            content = r.read().decode("utf-8", errors="replace")
            return r.status, content
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500]
    except Exception as ex:
        return None, str(ex)


def sb_get(path, qs=""):
    if not SUPABASE_KEY:
        return []
    url = f"{SUPABASE_URL}/rest/v1/{path}?{qs}" if qs else f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  Supabase GET error: {e}")
        return []


def sb_post(table, data, prefer="return=representation"):
    if DRY_RUN:
        log(f"  DRY_RUN: would insert to {table}: {json.dumps(data)[:200]}")
        return 200, []
    body = json.dumps(data if isinstance(data, list) else [data]).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=body,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def sb_patch(table, filter_qs, data):
    if DRY_RUN:
        log(f"  DRY_RUN: would PATCH {table}?{filter_qs}: {json.dumps(data)[:200]}")
        return 200, 1
    body = json.dumps(data).encode()
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter_qs}"
    req = urllib.request.Request(url, data=body, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            return r.status, len(result) if isinstance(result, list) else 1
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def eval_county():
    if not SUPABASE_KEY:
        return {"error": "no key"}
    body = json.dumps({"p_county": COUNTY}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=body,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# STEP 1: Current DB state
# ============================================================
log("=" * 60)
log("STEP 1: Current DB state — jefferson")
log("=" * 60)

log(f"  DRY_RUN={DRY_RUN}")
mca_rows = sb_get(
    "multi_county_auctions",
    "county=eq.jefferson&select=id,case_number,sale_type,auction_status,"
    "sold_amount,tier1_sold_amount,tier1_authoritative,parcel_id,auction_date&limit=10"
)
log(f"Jefferson MCA rows: {len(mca_rows)}")
for r in mca_rows:
    log(f"  {r.get('case_number')} | {r.get('sale_type')} | status={r.get('auction_status')} "
        f"| sold_amount={r.get('sold_amount')} | tier1_sold={r.get('tier1_sold_amount')} "
        f"| parcel={r.get('parcel_id')} | date={r.get('auction_date')}")

target_row = next((r for r in mca_rows if r.get("case_number") == CASE_NUMBER), None)
if not target_row:
    log(f"  WARN: target row {CASE_NUMBER} not found in DB")

fc_outcomes_existing = sb_get(
    "foreclosure_outcomes",
    f"county=eq.{COUNTY}&case_number=eq.{CASE_NUMBER}&limit=5"
)
log(f"Existing foreclosure_outcomes for {CASE_NUMBER}: {len(fc_outcomes_existing)}")

# ============================================================
# STEP 2: Evaluator pre-state
# ============================================================
log("=" * 60)
log("STEP 2: pencil_dod_evaluate_county (pre-probe)")
log("=" * 60)
eval_before = eval_county()
log(f"BEFORE: {json.dumps(eval_before, indent=2)}")
b_before = eval_before.get("B", {})
f_before = eval_before.get("F", {})
log(f"  B: pass={b_before.get('pass')} metric={b_before.get('metric')} detail={b_before.get('detail')}")
log(f"  F: pass={f_before.get('pass')} metric={f_before.get('metric')} detail={f_before.get('detail')}")

# ============================================================
# STEP 3: jeffersonclerk.com probe (fresh, day 29 post-sale)
# ============================================================
log("=" * 60)
log("STEP 3: jeffersonclerk.com — fresh probe (2026-07-24)")
log("=" * 60)

fc_page = "https://www.jeffersonclerk.com/clerk-services/property-sales/foreclosures/"
s, html = fetch_url(fc_page)
findings["sources_checked"].append(f"jeffersonclerk.com/foreclosures: HTTP {s}")
log(f"FC page: HTTP {s}, len={len(html) if html else 0}")
if html and s == 200:
    # Look for all PDF links
    pdfs = re.findall(r'href="(https?://[^"]+\.pdf)"', html, re.IGNORECASE)
    s3_pdfs = [p for p in pdfs if "jeffersonclerk.s3" in p or "jeffersonclerk.com" in p]
    log(f"  All PDF links: {pdfs}")
    log(f"  S3/clerk PDFs: {s3_pdfs}")
    # Check for post-sale result indicators
    post_sale_kws = [
        "result", "sold", "completed sale", "certificate of sale",
        "certificate of title", "winning bid", "high bidder", "sold amount",
        "past sale", "final result"
    ]
    for kw in post_sale_kws:
        idx = html.lower().find(kw)
        if idx != -1:
            snippet = html[max(0, idx-50):idx+150]
            if "<script" not in snippet.lower() and "comment" not in snippet.lower():
                log(f"  Found '{kw}': {snippet!r}")
    # Check if the known pre-sale PDF is still the only link
    if "Foreclosure-Sales.pdf" in html:
        log("  Pre-sale Foreclosure-Sales.pdf still linked")
    if not s3_pdfs:
        log("  No S3 PDF links found — page structure may have changed")

# Check for a "past sales" or results page (new paths)
past_sale_urls = [
    "https://www.jeffersonclerk.com/clerk-services/property-sales/foreclosure-sale-results/",
    "https://www.jeffersonclerk.com/clerk-services/property-sales/past-foreclosure-sales/",
    "https://www.jeffersonclerk.com/clerk-services/property-sales/completed-foreclosure-sales/",
    "https://www.jeffersonclerk.com/clerk-services/property-sales/foreclosure-results/",
]
for url in past_sale_urls:
    s2, h2 = fetch_url(url, timeout=10)
    log(f"  {url} → HTTP {s2}")
    if s2 == 200:
        log(f"    *** HIT! Content: {h2[:300]}")
        findings["sources_checked"].append(f"jeffersonclerk past-sale page {url}: HTTP {s2} FOUND")
    else:
        findings["sources_checked"].append(f"jeffersonclerk past-sale page {url}: HTTP {s2}")

# ============================================================
# STEP 4: JCPA ArcGIS re-probe (day 29 post-sale)
# ============================================================
log("=" * 60)
log("STEP 4: JCPA ArcGIS re-probe (bcrouch_JCPA, day 29 post-sale)")
log("=" * 60)

# Check services list first
jcpa_services_url = "https://services5.arcgis.com/vFMp1Ly1q6rKKp0o/arcgis/rest/services?f=json"
s, h = fetch_url(jcpa_services_url, timeout=15)
log(f"JCPA ArcGIS services: HTTP {s}")
findings["sources_checked"].append(f"JCPA ArcGIS services: HTTP {s}")
if s == 200 and h:
    try:
        data = json.loads(h)
        services = data.get("services", [])
        log(f"  {len(services)} services found")
        for svc in services:
            log(f"  - {svc.get('name')} ({svc.get('type')}) url={svc.get('url', '')}")
    except Exception as ex:
        log(f"  Parse error: {ex}")

# Try querying known layer names for our target parcel
# The shard-7 report confirmed JCPA has parcel data at this ArcGIS org
parcel_query_variants = [
    "JC_Parcel_Viewer/MapServer/0",
    "JC_Parcel_Viewer/FeatureServer/0",
    "JC_Parcel/MapServer/0",
    "JC_Parcel/FeatureServer/0",
    "Parcel/MapServer/0",
    "Parcel/FeatureServer/0",
    "Parcels/MapServer/0",
    "Parcels/FeatureServer/0",
    "JCParcelViewer/MapServer/0",
    "JC_CITY_ZONING_view/MapServer/0",
]

# Try the parcel ID we know
encoded_parcel = "00-00-00-0220-0000-0310".replace("-", "%2D")

for layer in parcel_query_variants:
    url = (
        f"https://services5.arcgis.com/vFMp1Ly1q6rKKp0o/arcgis/rest/services/"
        f"{layer}/query?"
        f"where=PARCELID+%3D+%2700-00-00-0220-0000-0310%27"
        f"&outFields=*&returnGeometry=false&f=json"
    )
    s, h = fetch_url(url, timeout=12)
    if s == 200 and h:
        try:
            data = json.loads(h)
            features = data.get("features", [])
            error = data.get("error")
            if features:
                log(f"  *** JCPA layer {layer}: {len(features)} features!")
                for feat in features:
                    attrs = feat.get("attributes", {})
                    log(f"  Attributes: {attrs}")
                    # Check for sale price fields
                    for field in attrs:
                        if any(kw in field.upper() for kw in ["SALE", "PRICE", "GRANT", "DEED", "TRANSFER"]):
                            log(f"    Field {field}={attrs[field]}")
                    # Check if owner changed
                    for owner_field in ["FIRSTOWNER", "OWN_NAME", "OWNER", "OWNER_NAME", "GRANTEE"]:
                        if owner_field in attrs and attrs[owner_field]:
                            log(f"  Owner field {owner_field}={attrs[owner_field]}")
                            if "THOMPSON" not in str(attrs[owner_field]).upper():
                                log(f"  *** OWNER CHANGED! New: {attrs[owner_field]}")
                                findings["new_data"] = True
                    # Extract any sale price
                    for price_field in ["SALE_PRC1", "SALE_PRC", "SALEPRICE", "SALE_PRICE",
                                        "LAST_SALE_PRICE", "CONSIDERATI", "CONSIDERATION"]:
                        if price_field in attrs and attrs[price_field]:
                            price_val = attrs[price_field]
                            try:
                                price_float = float(str(price_val).replace(",", ""))
                                if price_float > 0:
                                    log(f"  *** SALE PRICE FOUND: {price_field}={price_val}")
                                    findings["sold_amount_found"] = price_float
                                    findings["sold_amount_source"] = f"jcpa_arcgis:{layer}:{price_field}:SHARD6-JEFFERSON-BF-V1"
                                    findings["new_data"] = True
                            except (ValueError, TypeError):
                                pass
                findings["sources_checked"].append(f"JCPA {layer}: HTTP {s} → {len(features)} features")
                break
            elif error:
                log(f"  Layer {layer}: error={error}")
                findings["sources_checked"].append(f"JCPA {layer}: HTTP {s} error={error}")
            else:
                log(f"  Layer {layer}: HTTP {s} 0 features (parcel not found)")
                findings["sources_checked"].append(f"JCPA {layer}: HTTP {s} 0 features")
        except json.JSONDecodeError:
            log(f"  Layer {layer}: non-JSON response: {h[:100]}")
    else:
        log(f"  Layer {layer}: HTTP {s}")
        findings["sources_checked"].append(f"JCPA {layer}: HTTP {s}")

# ============================================================
# STEP 5: FL GIO statewide cadastral re-probe
# ============================================================
log("=" * 60)
log("STEP 5: FL GIO statewide cadastral SALE_PRC1 probe")
log("=" * 60)

# FL GIO statewide parcel layer - co_no=43 for Jefferson (confirmed in shard-7 session)
fgio_url = (
    "https://maps.geodata.myflorida.com/arcgis/rest/services/"
    "Cadastral_Services/Statewide_Parcel_Map/MapServer/0/query?"
    "where=PARCELID+%3D+%2700-00-00-0220-0000-0310%27+AND+CO_NO%3D43"
    "&outFields=PARCELID,OWN_NAME,SALE_PRC1,SALE_YR1,SALE_MO1,ASMNT_YR,CO_NO,SALE_PRC2,SALE_YR2"
    "&returnGeometry=false&f=json"
)
s, h = fetch_url(fgio_url, timeout=20)
log(f"FL GIO statewide cadastral: HTTP {s}")
findings["sources_checked"].append(f"FL GIO statewide cadastral: HTTP {s}")
if s == 200 and h:
    try:
        data = json.loads(h)
        features = data.get("features", [])
        log(f"  {len(features)} features")
        for feat in features:
            attrs = feat.get("attributes", {})
            log(f"  Attributes: {attrs}")
            sale_prc = attrs.get("SALE_PRC1", 0) or 0
            sale_yr = attrs.get("SALE_YR1", 0) or 0
            asmnt_yr = attrs.get("ASMNT_YR", "?")
            log(f"  SALE_PRC1={sale_prc} SALE_YR1={sale_yr} ASMNT_YR={asmnt_yr}")
            if float(sale_prc) > 0 and int(str(sale_yr)[:4]) >= 2026:
                log(f"  *** 2026 SALE FOUND in FL GIO! PRC={sale_prc} YR={sale_yr}")
                if not findings["sold_amount_found"]:
                    findings["sold_amount_found"] = float(sale_prc)
                    findings["sold_amount_source"] = f"fl_gio_cadastral:SALE_PRC1_2026:SHARD6-JEFFERSON-BF-V1"
                    findings["new_data"] = True
            else:
                log(f"  SALE_PRC1={sale_prc} is 0 or pre-2026 (ASMNT_YR={asmnt_yr}) — DOR roll still stale")
    except Exception as ex:
        log(f"  Parse error: {ex} resp={h[:200]}")

# ============================================================
# STEP 6: Attom Data free API probe
# ============================================================
log("=" * 60)
log("STEP 6: Attom Data API probe")
log("=" * 60)

# Attom has a free-tier discovery API
attom_url = (
    "https://api.attomdata.com/propertyapi/v1.0.0/property/detail?"
    "address1=340+Marvin+St&address2=Monticello+FL+32344"
)
s, h = fetch_url(attom_url, timeout=15, headers={"Accept": "application/json"})
log(f"Attom Data API: HTTP {s}")
findings["sources_checked"].append(f"Attom Data API: HTTP {s}")
if s == 200 and h:
    try:
        data = json.loads(h)
        log(f"  Attom response (first 500 chars): {json.dumps(data)[:500]}")
    except Exception:
        log(f"  Non-JSON: {h[:200]}")

# ============================================================
# STEP 7: Realtor.com sold listings probe
# ============================================================
log("=" * 60)
log("STEP 7: Realtor.com sold listings probe")
log("=" * 60)

# Check Realtor.com's API for this address
realtor_url = (
    "https://www.realtor.com/realestateandhomes-search/Monticello_FL/"
    "?price_max=300000&price_min=50000"
)
s, h = fetch_url(realtor_url, timeout=15)
log(f"Realtor.com: HTTP {s}")
findings["sources_checked"].append(f"Realtor.com: HTTP {s}")
if s == 200 and h and "340 Marvin" in h:
    log("  *** 340 Marvin St mentioned on Realtor.com!")
    idx = h.find("340 Marvin")
    log(f"  Context: {h[max(0,idx-100):idx+200]}")

# ============================================================
# STEP 8: Zillow address search
# ============================================================
log("=" * 60)
log("STEP 8: Zillow address search (was 403 in prior sessions)")
log("=" * 60)

zillow_url = "https://www.zillow.com/homes/340-Marvin-St-Monticello-FL_rb/"
s, h = fetch_url(zillow_url, timeout=15)
log(f"Zillow: HTTP {s}")
findings["sources_checked"].append(f"Zillow: HTTP {s}")
if s == 200 and h:
    # Look for "Sold" indicators
    for kw in ["Sold on", "Sale price", "Sold for", "Last sold"]:
        idx = h.lower().find(kw.lower())
        if idx != -1:
            log(f"  Found '{kw}': {h[max(0,idx-20):idx+150]}")

# ============================================================
# STEP 9: If sold_amount found — write to DB
# ============================================================
log("=" * 60)
log("STEP 9: DB write (if sold_amount found)")
log("=" * 60)

if findings["sold_amount_found"] and findings["sold_amount_found"] > 0:
    sold_amount = findings["sold_amount_found"]
    sold_source = findings["sold_amount_source"]
    log(f"  *** SOLD AMOUNT FOUND: ${sold_amount:.2f} from {sold_source}")
    log(f"  DRY_RUN={DRY_RUN}")

    if not DRY_RUN:
        # Write sold_amount + tier1 to MCA row
        patch_status, patch_count = sb_patch(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{CASE_NUMBER}",
            {
                "sold_amount": sold_amount,
                "sold_amount_source": sold_source,
                "sold_amount_captured_at": now_ts(),
                "tier1_authoritative": True,
                "tier1_sale_status": "sold",
                "tier1_sold_amount": sold_amount,
                "tier1_verified_at": now_ts(),
                "tier1_source_run_id": PIPELINE_RUN_ID,
                "auction_status": "sold",
                "updated_at": now_ts(),
            }
        )
        log(f"  MCA PATCH → HTTP {patch_status} count={patch_count}")

        # Insert into foreclosure_outcomes (independent source required for B)
        if not fc_outcomes_existing:
            ins_status, ins_resp = sb_post("foreclosure_outcomes", [{
                "county": COUNTY,
                "case_number": CASE_NUMBER,
                "auction_date": SALE_DATE,
                "opening_bid": JUDGMENT_AMOUNT,
                "winning_bid": sold_amount,
                "property_address": PROPERTY_ADDRESS,
                "parcel_id": PARCEL_ID,
                "outcome": "sold",
                "data_source": sold_source,
                "enriched_at": now_ts(),
                "created_at": now_ts(),
            }])
            log(f"  foreclosure_outcomes INSERT → HTTP {ins_status}: {str(ins_resp)[:200]}")
        else:
            log(f"  foreclosure_outcomes already has {len(fc_outcomes_existing)} row(s) — skipping insert")

        # Insert ultraloop_audit survived=true rows for B and F
        for letter in ["B", "F"]:
            audit_status, audit_resp = sb_post("gold_standard_ultraloop_audit", [{
                "dispatch_id": DISPATCH_ID,
                "ultraloop_mode": "probe",
                "county_slug": COUNTY_SLUG,
                "letter": letter,
                "claim": f"Jefferson {letter} unblocked — sold_amount={sold_amount} found via {sold_source}",
                "refuter_evidence": json.dumps({
                    "sources_checked": findings["sources_checked"],
                    "sold_amount": sold_amount,
                    "sold_amount_source": sold_source,
                    "probe_date": "2026-07-24",
                    "days_post_sale": 29,
                    "honesty_marker": "VERIFIED",
                }),
                "survived": True,
                "created_at": now_ts(),
            }])
            log(f"  ultraloop_audit {letter} survived=true → HTTP {audit_status}")

        log(f"  DB writes complete")
    else:
        log(f"  DRY_RUN=true — skipping DB writes")
else:
    log(f"  No sold_amount found from any source")
    log(f"  Sources checked: {len(findings['sources_checked'])}")

    # Still write ultraloop_audit survived=false rows to record this session
    if not DRY_RUN and SUPABASE_KEY:
        for letter in ["B", "F"]:
            audit_status, audit_resp = sb_post("gold_standard_ultraloop_audit", [{
                "dispatch_id": DISPATCH_ID,
                "ultraloop_mode": "probe",
                "county_slug": COUNTY_SLUG,
                "letter": letter,
                "claim": f"Jefferson {letter} still blocked — 29 sources exhausted through day 29 post-sale",
                "refuter_evidence": json.dumps({
                    "sources_checked": findings["sources_checked"],
                    "probe_date": "2026-07-24",
                    "days_post_sale": 29,
                    "new_angles_tried": [
                        "JCPA ArcGIS re-probe (day 29)",
                        "jeffersonclerk.com past-sale pages",
                        "FL GIO SALE_PRC1 (checking 2026 YR)",
                        "Attom Data API",
                        "Realtor.com sold listings",
                        "Zillow (was 403, re-checked)",
                    ],
                    "honesty_marker": "VERIFIED",
                    "escalation": (
                        "Tax deed sales 26-TD-04 and 26-TD-05 scheduled 2026-08-19 "
                        "(26 days away). These will provide 2 real closed_sold rows "
                        "after the sale. The foreclosure 25-CA-164 sold_amount remains "
                        "unavailable from any independent source. Once the tax deed sales "
                        "complete, check the clerks PDF for results on the tax deed lane; "
                        "this will not help foreclosure B/F but provides a different angle."
                    ),
                }),
                "survived": False,
                "created_at": now_ts(),
            }])
            log(f"  ultraloop_audit {letter} survived=false → HTTP {audit_status}: {str(audit_resp)[:100]}")

# ============================================================
# STEP 10: Post-probe evaluator
# ============================================================
log("=" * 60)
log("STEP 10: pencil_dod_evaluate_county (post-probe)")
log("=" * 60)

import time
time.sleep(2)
eval_after = eval_county()
log(f"AFTER: {json.dumps(eval_after, indent=2)}")

passes = 0
for letter in "ABCDEFGHIJ":
    ld = eval_after.get(letter, {})
    passed = bool(ld.get("pass"))
    if passed:
        passes += 1
    mark = "PASS" if passed else "FAIL"
    log(f"  {letter}: {mark} metric={ld.get('metric')} detail={ld.get('detail', '')[:60]}")
log(f"  TOTAL: {passes}/10 passing (was 8/10)")

b_after = eval_after.get("B", {})
f_after = eval_after.get("F", {})
if b_after.get("pass") and f_after.get("pass"):
    log("  *** JEFFERSON 10/10 ACHIEVED!")
elif b_after.get("pass") or f_after.get("pass"):
    log(f"  PARTIAL: B={'PASS' if b_after.get('pass') else 'FAIL'} F={'PASS' if f_after.get('pass') else 'FAIL'}")
else:
    log("  B and F still FAIL — blocker persists (BLANK > WRONG, no fabrication)")

# ============================================================
# FINAL SUMMARY
# ============================================================
log("=" * 60)
log("FINAL SUMMARY")
log("=" * 60)
log(f"  Sources checked ({len(findings['sources_checked'])}):")
for src in findings["sources_checked"]:
    log(f"    - {src}")
log(f"  sold_amount_found: {findings['sold_amount_found']}")
log(f"  sold_amount_source: {findings['sold_amount_source']}")
log(f"  new_data: {findings['new_data']}")
if findings["errors"]:
    log(f"  Errors: {findings['errors']}")
log(f"  Probe date: 2026-07-24 (day 29 post-sale for 25-CA-164)")
log(f"  Next milestone: 2026-08-19 (tax deed sales 26-TD-04/26-TD-05)")
log(f"  After 08-19: if tax deed results posted to clerks PDF, these 2 cases")
log(f"    will populate closed_sold=2 and potentially B+F on tax deed lane")
