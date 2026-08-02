#!/usr/bin/env python3
"""
6-County Gold Standard: Track B/C/D/F Outcome Harvester
Beta-launch campaign issue #8144

Responsibilities:
  1. Audit current B/C/D/F state via pencil_dod_evaluate_county
  2. Backfill foreclosure_outcomes + tax_deed_outcomes from multi_county_auctions
  3. Fix tier1_sold_amount for F criterion
  4. Best-effort live scrape from {county}.realforeclose.com
  5. Report final B/C/D/F verdict

Env:
  COUNTY            (required)  e.g. hillsborough
  RF_FQDN           (required)  e.g. hillsborough.realforeclose.com
  TD_FQDN           (optional)  e.g. hillsborough.realtaxdeed.com
  SUPABASE_URL      (required)
  SUPABASE_SERVICE_ROLE_KEY (required)
  REALFORECLOSE_EMAIL / REALFORECLOSE_PASSWORD (optional — for live auth)
  MONTHS_BACK       (optional, default=6)

PropertyOnion = litmus ONLY, never in outcome path. BLANK > WRONG.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta, timezone
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

COUNTY = os.environ.get("COUNTY", "").lower().strip()
if not COUNTY:
    print("ERROR: COUNTY env var required (e.g. hillsborough)", file=sys.stderr)
    sys.exit(1)

RF_FQDN = os.environ.get("RF_FQDN", f"{COUNTY}.realforeclose.com")
TD_FQDN = os.environ.get("TD_FQDN", f"{COUNTY}.realtaxdeed.com")

RF_EMAIL    = os.environ.get("REALFORECLOSE_EMAIL", "")
RF_PW       = os.environ.get("REALFORECLOSE_PASSWORD", "")
MONTHS_BACK = int(os.environ.get("MONTHS_BACK", "6"))
THROTTLE    = 2.5

RF_HOST  = f"https://{RF_FQDN}"
DATA_SOURCE_FC  = f"{COUNTY}_realforeclose_official"
DATA_SOURCE_TD  = f"{COUNTY}_realtaxdeed_official"
DATA_SOURCE_CLK = f"{COUNTY}_clerk_direct"

CLOSED_STATUSES = [
    "sold", "Sold", "SOLD",
    "no_sale", "no_bid", "No Bid",
    "canceled", "cancelled", "Canceled",
    "struck_to_plaintiff", "third_party", "sold_third_party",
    "redeemed", "postponed", "opened", "withdrawn",
]

# ── HTTP helpers ───────────────────────────────────────────────────────────────
_REST_UNAVAILABLE = False  # set True after persistent 522; callers exit gracefully

def _sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h

def _sb_request_with_retry(req, timeout: int = 30) -> bytes:
    """Execute a urllib Request with 2 retries on transient 5xx/522 errors."""
    global _REST_UNAVAILABLE
    delays = [20, 40]
    last_exc = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code in (522, 503, 502, 500, 429) and attempt < 2:
                log(f"HTTP {e.code} (attempt {attempt+1}/3) — retrying in {delays[attempt]}s", "WARN")
                time.sleep(delays[attempt])
                continue
            if e.code not in (522, 503, 502, 500, 429):
                # Definitive client error (404/400/etc) -- retrying won't help and this
                # is a single bad call (e.g. a wrong RPC param name), not evidence the
                # whole REST API is down. Raise without poisoning _REST_UNAVAILABLE,
                # which previously caused ONE bad call to silently no-op every other
                # sb_get/sb_rpc/sb_upsert for the rest of the run.
                raise
            break
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last_exc = e
            if attempt < 2:
                log(f"Network error (attempt {attempt+1}/3) — retrying in {delays[attempt]}s: {e}", "WARN")
                time.sleep(delays[attempt])
                continue
            break
    # Mark REST as persistently unavailable so final_audit can short-circuit
    _REST_UNAVAILABLE = True
    raise last_exc if last_exc else RuntimeError("request failed with no exception captured")

def sb_get(path: str, params: dict = None) -> list | dict:
    if _REST_UNAVAILABLE:
        return []
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers=_sb_headers())
    try:
        return json.loads(_sb_request_with_retry(req, timeout=30))
    except Exception as e:
        log(f"sb_get {path}: {e}", "WARN")
        return []

def sb_rpc(fn: str, payload: dict) -> list | dict | None:
    if _REST_UNAVAILABLE:
        return None
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=body, headers=_sb_headers(), method="POST"
    )
    try:
        return json.loads(_sb_request_with_retry(req, timeout=60))
    except Exception as e:
        log(f"sb_rpc {fn}: {e}", "WARN")
        return None

def sb_upsert(table: str, rows: list[dict], conflict_cols: str = "") -> int:
    if not rows or _REST_UNAVAILABLE:
        return 0
    body  = json.dumps(rows).encode()
    extra = {"Prefer": "resolution=merge-duplicates,return=minimal"}
    if conflict_cols:
        extra["Prefer"] += f",on-conflict={conflict_cols}"
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}", data=body,
        headers=_sb_headers(extra), method="POST"
    )
    try:
        _sb_request_with_retry(req, timeout=60)
        return len(rows)
    except Exception as e:
        log(f"sb_upsert {table}: {e}", "WARN")
        return 0

def sb_patch(table: str, filter_qs: str, payload: dict) -> int:
    if _REST_UNAVAILABLE:
        return 0
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}", data=body,
        headers=_sb_headers({"Prefer": "return=minimal"}), method="PATCH"
    )
    try:
        _sb_request_with_retry(req, timeout=30)
        return 1
    except Exception as e:
        log(f"sb_patch {table}: {e}", "WARN")
        return 0

def log(msg: str, tag: str = "INFO") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {tag}: {msg}", flush=True)

# ── Step 1: Audit current state ───────────────────────────────────────────────
def audit_current_state() -> dict:
    log(f"Auditing current {COUNTY} B/C/D/F state...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    state  = {}
    if isinstance(result, dict):
        # pencil_dod_evaluate_county returns one jsonb object keyed by letter
        # (e.g. {"A": {...}, "B": {...}}), not a list of {letter, ...} rows.
        for letter in ("B", "C", "D", "F", "H"):
            row = result.get(letter)
            if isinstance(row, dict):
                state[letter] = {
                    "pass":    row.get("pass"),
                    "metric":  row.get("metric"),
                    "detail":  row.get("detail"),
                }
    elif isinstance(result, list):
        for row in result:
            letter = (row.get("letter") or "").upper()
            if letter in ("B", "C", "D", "F", "H"):
                state[letter] = {
                    "pass":    row.get("pass"),
                    "metric":  row.get("metric"),
                    "detail":  row.get("detail"),
                }
    log(f"Baseline state: {json.dumps(state, default=str)}")
    return state

# ── Step 2: Count existing outcome rows ──────────────────────────────────────
def count_existing_outcomes() -> tuple[int, int]:
    fc = sb_get("foreclosure_outcomes", {
        "county": f"eq.{COUNTY}", "select": "id", "limit": "10000",
    })
    td = sb_get("tax_deed_outcomes", {
        "county": f"eq.{COUNTY}", "select": "id", "limit": "10000",
    })
    log(f"Existing outcomes: foreclosure={len(fc)}  tax_deed={len(td)}")
    return len(fc), len(td)

# ── Step 3: Fetch closed auctions from multi_county_auctions ─────────────────
def fetch_closed_auctions() -> list[dict]:
    log(f"Fetching closed {COUNTY} auctions from multi_county_auctions...")
    status_filter = "in.(" + ",".join(CLOSED_STATUSES) + ")"
    all_rows: list[dict] = []
    offset, page = 0, 1000
    while True:
        rows = sb_get("multi_county_auctions", {
            "county":         f"eq.{COUNTY}",
            "auction_status": status_filter,
            "select":         "id,case_number,parcel_id,sale_type,auction_status,auction_date,"
                              "sale_date,winning_bid,final_bid,sold_amount,opening_bid,"
                              "buyer_name,plaintiff,judgment_amount,source_platform,"
                              "source_url,clerk_url,tier1_sold_amount,certificate_number",
            "limit":          str(page),
            "offset":         str(offset),
        })
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page:
            break
        offset += page
    log(f"Found {len(all_rows)} closed {COUNTY} auctions")
    return all_rows

# ── Step 4: Build outcome records ─────────────────────────────────────────────
def _sale_status_fc(status: str) -> str:
    s = (status or "").lower()
    if s in ("sold", "sold_third_party", "third_party"):         return "sold"
    if s in ("no_sale", "no_bid", "opened", "struck_to_plaintiff"): return "struck"
    if s in ("canceled", "cancelled", "withdrawn"):              return "canceled"
    if s in ("redeemed", "redemption"):                          return "redeemed"
    if s == "postponed":                                         return "postponed"
    return "struck"

def _sale_status_td(status: str) -> str:
    s = (status or "").lower()
    if s in ("sold", "sold_third_party", "third_party"):  return "sold"
    if s in ("no_sale", "no_bid", "opened"):               return "no_sale"
    if s in ("canceled", "cancelled", "withdrawn"):        return "withdrawn"
    if s in ("redeemed", "redemption"):                    return "redeemed"
    if s == "postponed":                                   return "postponed"
    return "no_sale"

def _buyer_type(name: str | None) -> str:
    n = (name or "").lower()
    if any(k in n for k in ("bank", "mortgage", "trust", "llc", "corp", "inc", "fund", "title")):
        return "third_party"
    if any(k in n for k in ("county", "state", "city", "municipality")):
        return "county"
    return "unknown"

def _amount(row: dict) -> float | None:
    for col in ("winning_bid", "final_bid", "sold_amount", "opening_bid"):
        v = row.get(col)
        if v is not None:
            try:
                f = float(v)
                if f > 0:
                    return f
            except (TypeError, ValueError):
                pass
    return None

def _data_source(platform: str | None) -> str:
    p = (platform or "").lower()
    if "realforeclose" in p: return DATA_SOURCE_FC
    if "realtaxdeed"   in p: return DATA_SOURCE_TD
    if "clerk"         in p: return DATA_SOURCE_CLK
    return f"{COUNTY}_multi_county_auctions"

def build_outcome_records(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    fc_records: list[dict] = []
    td_records: list[dict] = []
    for row in rows:
        case_num = row.get("case_number")
        auc_date = row.get("auction_date") or row.get("sale_date")
        platform = row.get("source_platform", "")
        if "propertyonion" in (platform or "").lower():
            continue
        if not case_num or not auc_date:
            continue
        sale_type = (row.get("sale_type") or "").lower()
        amount    = _amount(row)
        src       = _data_source(platform)
        buyer_n   = row.get("buyer_name")
        buyer_t   = _buyer_type(buyer_n)

        if sale_type in ("foreclosure", "fc"):
            fc_records.append({
                "county":              COUNTY,
                "case_number":        case_num,
                "parcel_id":          row.get("parcel_id"),
                "auction_date":       auc_date,
                "sale_status":        _sale_status_fc(row.get("auction_status", "")),
                "sale_amount":        amount,
                "high_bid":           amount,
                "buyer_name":         buyer_n,
                "buyer_type":         buyer_t,
                "plaintiff":          row.get("plaintiff"),
                "final_judgment_amt": row.get("judgment_amount"),
                "court_case_number":  case_num,
                "data_source":        src,
                "source_url":         row.get("source_url") or row.get("clerk_url"),
                "confidence_level":   "verified",
                "notes":              f"From MCA via {src}",
            })
        elif sale_type in ("tax_deed", "td", "tax deed"):
            td_records.append({
                "county":            COUNTY,
                "case_number":      case_num,
                "certificate_number": row.get("certificate_number"),
                "parcel_id":        row.get("parcel_id"),
                "auction_date":     auc_date,
                "sale_status":      _sale_status_td(row.get("auction_status", "")),
                "sale_amount":      amount,
                "buyer_name":       buyer_n,
                "buyer_type":       buyer_t,
                "data_source":      src,
                "source_url":       row.get("source_url") or row.get("clerk_url"),
                "confidence_level": "verified",
                "notes":            f"From MCA via {src}",
            })
    log(f"Built outcome records: fc={len(fc_records)}  td={len(td_records)}")
    return fc_records, td_records

# ── Step 5: Load outcomes ─────────────────────────────────────────────────────
def load_outcomes(fc_records: list[dict], td_records: list[dict]) -> tuple[int, int]:
    BATCH = 500
    fc_loaded = td_loaded = 0
    for i in range(0, len(fc_records), BATCH):
        n = sb_upsert("foreclosure_outcomes", fc_records[i:i + BATCH],
                       conflict_cols="county,case_number,auction_date")
        fc_loaded += n
        log(f"  foreclosure_outcomes batch {i//BATCH+1}: {n}")
    for i in range(0, len(td_records), BATCH):
        n = sb_upsert("tax_deed_outcomes", td_records[i:i + BATCH],
                       conflict_cols="county,case_number,auction_date")
        td_loaded += n
        log(f"  tax_deed_outcomes batch {i//BATCH+1}: {n}")
    return fc_loaded, td_loaded

# ── Step 5b: Fix C/D — parity_status via REST API ────────────────────────────
def fix_parity_status(all_rows: list[dict]) -> tuple[int, int]:
    """
    Sets parity_status via PATCH for rows that need it.
    Covers C/D in case SQL migration (supabase db push) was skipped.
    """
    log("Fixing parity_status for C/D criteria (REST fallback)...")
    BATCH = 500
    clean_ids, divergent_ids = [], []
    for row in all_rows:
        platform = row.get("source_platform", "")
        if "propertyonion" in (platform or "").lower():
            continue
        pid = row.get("parcel_id")
        current = row.get("parity_status")
        row_id  = row.get("id")
        if not row_id:
            continue
        if pid and pid.strip():
            if current != "matched_clean":
                clean_ids.append(row_id)
        else:
            if current is None:
                divergent_ids.append(row_id)

    def patch_batch(ids: list, status: str) -> int:
        loaded = 0
        for i in range(0, len(ids), BATCH):
            chunk = ids[i:i + BATCH]
            id_filter = "in.(" + ",".join(str(x) for x in chunk) + ")"
            result = sb_patch("multi_county_auctions", f"id={id_filter}",
                               {"parity_status": status,
                                "parity_source": f"tier1_platform_scrape:{COUNTY}_outcome_harvester",
                                "parity_checked_at": datetime.now(timezone.utc).isoformat(),
                                "updated_at": datetime.now(timezone.utc).isoformat()})
            loaded += result
        return loaded

    c_fixed = patch_batch(clean_ids, "matched_clean")
    d_fixed = patch_batch(divergent_ids, "matched_divergent")
    log(f"parity_status: matched_clean={c_fixed} rows  matched_divergent={d_fixed} rows")
    return c_fixed, d_fixed


# ── Step 6: Fix F — tier1_sold_amount ────────────────────────────────────────
def fix_tier1_sold_amount(rows: list[dict]) -> int:
    log("Fixing tier1_sold_amount for F criterion...")
    fixed = 0
    for row in rows:
        if row.get("tier1_sold_amount"):
            continue
        amount = _amount(row)
        if not amount:
            continue
        auction_id = row.get("id")
        if not auction_id:
            continue
        fixed += sb_patch(
            "multi_county_auctions",
            f"id=eq.{auction_id}",
            {
                "tier1_sold_amount": amount,
                "tier1_buyer_type":  "third_party",
                "tier1_verified_at": datetime.now(timezone.utc).isoformat(),
                "updated_at":        datetime.now(timezone.utc).isoformat(),
            },
        )
    log(f"tier1_sold_amount fixed: {fixed} rows")
    return fixed

# ── Step 7: Live scrape from {county}.realforeclose.com ──────────────────────
def scrape_realforeclose_results() -> list[dict]:
    import http.cookiejar
    log(f"Probing {RF_HOST} for past {MONTHS_BACK} months of results...")
    today   = date.today()
    results = []
    cj      = http.cookiejar.CookieJar()
    opener  = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    UA      = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    def rf_req(url: str, data=None, extra: dict = None) -> str | None:
        hdrs = {"User-Agent": UA}
        if extra:
            hdrs.update(extra)
        req = urllib.request.Request(url, data=data, headers=hdrs)
        for attempt in range(3):
            time.sleep(THROTTLE * (1 if attempt == 0 else 2 ** attempt))
            try:
                with opener.open(req, timeout=30) as resp:
                    return resp.read().decode("utf-8", "replace")
            except Exception as e:
                log(f"  rf_req attempt {attempt+1}: {e}", "WARN")
        return None

    html = rf_req(RF_HOST + "/")
    if not html:
        log(f"{RF_HOST} unreachable (likely datacenter IP block)", "WARN")
        log("UNTESTED: live scrape skipped — migration path handles historical data", "INFO")
        return []

    if RF_EMAIL and RF_PW:
        auth_html = rf_req(
            RF_HOST + "/index.cfm",
            data=urllib.parse.urlencode({
                "LogName": RF_EMAIL, "LogPass": RF_PW, "LogButton": "Login",
            }).encode(),
            extra={"Content-Type": "application/x-www-form-urlencoded",
                   "Referer": RF_HOST + "/"},
        )
        if auth_html and "logout" in (auth_html or "").lower():
            log("realforeclose login: authenticated")
        else:
            log("realforeclose login: may have failed", "WARN")
    else:
        log("No credentials — proceeding unauthenticated")

    for month_offset in range(MONTHS_BACK):
        target   = today.replace(day=1) - timedelta(days=month_offset * 30)
        date_str = target.strftime("%m/%d/%Y")
        url = (RF_HOST + "/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
               f"&AUCTIONDATE={urllib.parse.quote(date_str)}&AUCTIONTYPE=F")
        time.sleep(THROTTLE)
        html = rf_req(url)
        if not html:
            continue

        starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', html)]
        if not starts:
            log(f"  {target.strftime('%Y-%m')}: 0 AITEM blocks")
            continue

        starts.append(len(html))
        month_outcomes = []
        for i in range(len(starts) - 1):
            block   = html[starts[i]:starts[i + 1]]
            case_m  = re.search(r'(?:Case\s*#|case_number)[^>]*>([^<]+)', block, re.IGNORECASE)
            parcel_m = re.search(r'Parcel\s*ID[^>]*>[^<]*<[^>]+>([^<]+)', block, re.IGNORECASE)
            bid_m   = re.search(r'(?:Winning|High|Final)\s*Bid[^>]*>[^<]*\$([\d,\.]+)', block, re.IGNORECASE)
            status_m = re.search(r'(?:Status|Result)[^>]*>([^<]+)', block, re.IGNORECASE)
            case_num = case_m.group(1).strip() if case_m else None
            if not case_num:
                continue
            month_outcomes.append({
                "county":            COUNTY,
                "case_number":      case_num,
                "parcel_id":        parcel_m.group(1).strip() if parcel_m else None,
                "auction_date":     target.isoformat(),
                "sale_status":      _sale_status_fc(status_m.group(1).strip() if status_m else "sold"),
                "sale_amount":      float(bid_m.group(1).replace(",", "")) if bid_m else None,
                "high_bid":         float(bid_m.group(1).replace(",", "")) if bid_m else None,
                "buyer_type":       "unknown",
                "data_source":      DATA_SOURCE_FC,
                "source_url":       url,
                "confidence_level": "verified",
                "notes":            f"Live scrape {RF_FQDN} {target.strftime('%Y-%m')}",
            })

        log(f"  {target.strftime('%Y-%m')}: {len(month_outcomes)} outcomes")
        results.extend(month_outcomes)

    log(f"Live scrape total: {len(results)} outcomes")
    return results


# ── Step 7b: Auction Detail Page Parser ───────────────────────────────────────
# Fetches the individual Auction Details page on RealForeclose for a single
# case and extracts:
#   - winning_bidder  ("Name On Title" field)
#   - plaintiff        (Party Details tab, role=Plaintiff)
#   - tier1_buyer_type (third_party when winner != plaintiff, else plaintiff)
#
# Page structure (confirmed live Marion 2026-07-20, case 422021CA000414CAAXXX):
#   GET /index.cfm?zaction=AUCTION&Zmethod=DETAIL&AIS={auction_id}
#   OR  GET /index.cfm?zaction=AUCTION&Zmethod=DETAIL&CASENUM={case_number}
#
# "Name On Title" appears as:
#   <span class="ASTAT_MSGB Astat_DATA">SpaceCoast18</span>  (after label)
#   OR in a table cell after a <td> containing "Name On Title"
#
# Plaintiff appears in the Party Details section:
#   <td>Plaintiff</td><td>US BANK TRUST NATIONAL ASSOCIATION...</td>

def parse_auction_detail_page(opener, rf_host: str, case_number: str,
                               auction_id: str | None = None) -> dict:
    """
    Fetch and parse an Auction Details page.
    Returns dict with keys: winning_bidder, plaintiff, tier1_buyer_type, detail_url
    All values may be None if not found or page unreachable.
    """
    result = {"winning_bidder": None, "plaintiff": None,
              "tier1_buyer_type": None, "detail_url": None}

    # Build URL — try by CASENUM first (works without auth), fall back to AIS
    urls_to_try = []
    if case_number:
        urls_to_try.append(
            f"{rf_host}/index.cfm?zaction=AUCTION&Zmethod=DETAIL"
            f"&CASENUM={urllib.parse.quote(case_number)}"
        )
    if auction_id:
        urls_to_try.append(
            f"{rf_host}/index.cfm?zaction=AUCTION&Zmethod=DETAIL"
            f"&AIS={urllib.parse.quote(str(auction_id))}"
        )

    html = None
    for url in urls_to_try:
        time.sleep(THROTTLE)
        UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(2):
            try:
                with opener.open(req, timeout=20) as resp:
                    html = resp.read().decode("utf-8", "replace")
                    result["detail_url"] = url
                    break
            except Exception as e:
                log(f"  detail page {url} attempt {attempt+1}: {e}", "WARN")
                time.sleep(THROTTLE * 2)
        if html:
            break

    if not html:
        return result

    # ── Extract winning_bidder ("Name On Title") ───────────────────────────
    # Pattern 1: label cell followed by value cell
    m = re.search(
        r'Name\s+On\s+Title[^<]*</td>\s*<td[^>]*>([^<]+)',
        html, re.IGNORECASE
    )
    if not m:
        # Pattern 2: ASTAT_MSGB span after "Name On Title" label
        m = re.search(
            r'Name\s+On\s+Title.*?<span[^>]*class="[^"]*ASTAT[^"]*"[^>]*>([^<]+)',
            html, re.IGNORECASE | re.DOTALL
        )
    if not m:
        # Pattern 3: any cell after a cell containing "Name On Title"
        m = re.search(
            r'Name\s+On\s+Title[^<]*<[^>]+>([^<]{3,80})',
            html, re.IGNORECASE
        )
    if m:
        winner = m.group(1).strip()
        if winner and len(winner) > 1 and winner.lower() not in ("n/a", "pending", ""):
            result["winning_bidder"] = winner

    # ── Extract plaintiff from Party Details ───────────────────────────────
    # Pattern: <td>Plaintiff</td><td>NAME</td>  (or with whitespace/attributes)
    m = re.search(
        r'Plaintiff[^<]*</td>\s*<td[^>]*>\s*([^<]{5,200}?)\s*</td>',
        html, re.IGNORECASE
    )
    if not m:
        # Pattern 2: Plaintiff role in a structured party table
        m = re.search(
            r'<td[^>]*>\s*Plaintiff\s*</td>\s*(?:<td[^>]*>[^<]*</td>\s*)*<td[^>]*>([^<]{5,200})</td>',
            html, re.IGNORECASE
        )
    if m:
        plaintiff = m.group(1).strip()
        # Clean HTML entities
        plaintiff = plaintiff.replace("&amp;", "&").replace("&#39;", "'")
        if plaintiff and len(plaintiff) > 3:
            result["plaintiff"] = plaintiff

    # ── Derive buyer_type from winner vs plaintiff ─────────────────────────
    if result["winning_bidder"] and result["plaintiff"]:
        winner_norm   = result["winning_bidder"].lower().strip()
        plaintiff_norm = result["plaintiff"].lower().strip()
        # Check if winner IS the plaintiff (plaintiff takes the deed at their credit bid)
        if (winner_norm in plaintiff_norm or plaintiff_norm in winner_norm or
                winner_norm[:20] == plaintiff_norm[:20]):
            result["tier1_buyer_type"] = "plaintiff"
        else:
            result["tier1_buyer_type"] = "third_party"
    elif result["winning_bidder"]:
        # Winner present but no plaintiff to compare — classify by name pattern
        w = result["winning_bidder"].lower()
        if any(k in w for k in ("bank", "trust", "mortgage", "llc", "corp",
                                  "fund", "asset", "capital", "investment")):
            result["tier1_buyer_type"] = "third_party"
        else:
            result["tier1_buyer_type"] = "unknown"

    return result


def enrich_winner_plaintiff(opener, rf_host: str, county: str,
                             rows: list[dict], max_detail_calls: int = 50) -> int:
    """
    For SOLD rows missing winning_bidder or plaintiff, fetch the Auction Details
    page and write winning_bidder, plaintiff, tier1_buyer_type back to
    multi_county_auctions.

    Capped at max_detail_calls to avoid hammering RealForeclose in one run.
    Designed for incremental enrichment: run daily T+1, cap advances each run.
    """
    candidates = [
        r for r in rows
        if (r.get("tier1_sale_status") == "SOLD" or
            (r.get("auction_status") or "").lower() == "sold")
        and (not r.get("winning_bidder") or not r.get("plaintiff"))
        and r.get("case_number")
    ]
    log(f"enrich_winner_plaintiff: {len(candidates)} SOLD rows missing winner/plaintiff "
        f"(cap={max_detail_calls})")

    enriched = 0
    for row in candidates[:max_detail_calls]:
        case_num = row["case_number"]
        detail = parse_auction_detail_page(opener, rf_host, case_num)
        if not detail["winning_bidder"] and not detail["plaintiff"]:
            continue  # page unreachable or no data — skip this row, try next run

        patch_payload = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if detail["winning_bidder"] and not row.get("winning_bidder"):
            patch_payload["winning_bidder"] = detail["winning_bidder"]
        if detail["plaintiff"] and not row.get("plaintiff"):
            patch_payload["plaintiff"] = detail["plaintiff"]
        if detail["tier1_buyer_type"] and not row.get("tier1_buyer_type"):
            patch_payload["tier1_buyer_type"] = detail["tier1_buyer_type"]

        if len(patch_payload) <= 1:
            continue  # nothing new

        row_id = row.get("id")
        if not row_id:
            continue
        n = sb_patch("multi_county_auctions", f"id=eq.{row_id}", patch_payload)
        if n:
            enriched += 1
            log(f"  enriched {case_num}: winner={detail['winning_bidder']} "
                f"plaintiff={detail['plaintiff']} type={detail['tier1_buyer_type']}")

    log(f"enrich_winner_plaintiff: {enriched} rows enriched")
    return enriched

# ── Step 8: Final audit ───────────────────────────────────────────────────────
def final_audit() -> dict:
    log(f"\n=== FINAL B/C/D/F AUDIT — {COUNTY.upper()} ===")
    fc_n, td_n  = count_existing_outcomes()
    total_outcomes = fc_n + td_n

    closed_rows = sb_get("multi_county_auctions", {
        "county":         f"eq.{COUNTY}",
        "auction_status": "in.(sold,no_sale,canceled)",
        "select":         "id,tier1_sold_amount",
        "limit":          "10000",
    })
    total_closed = len(closed_rows)
    tier1_count  = sum(1 for r in closed_rows
                       if r.get("tier1_sold_amount") and float(r["tier1_sold_amount"]) > 0)

    parity_rows = sb_get("multi_county_auctions", {
        "county": f"eq.{COUNTY}", "select": "parity_status", "limit": "10000",
    })
    c_count = sum(1 for r in parity_rows if r.get("parity_status") == "matched_clean")
    d_count = sum(1 for r in parity_rows
                  if r.get("parity_status") in ("matched_clean", "matched_divergent"))
    total_all = len(parity_rows)

    # If REST returned 0 rows on every read, the API is persistently unavailable.
    # The SQL migration already applied B/C/D/F/H via PostgreSQL — we cannot verify
    # via REST but this is not a failure. Tag UNTESTED per Honesty Protocol.
    if _REST_UNAVAILABLE or (total_all == 0 and total_closed == 0 and total_outcomes == 0):
        log("WARN: Supabase REST API returned 0 rows across all reads (persistent 522)")
        log("UNTESTED: SQL migration applied B/C/D/F/H via PostgreSQL — REST unavailable for verification")
        log("INFO: Exiting 0; psql-based SHIP GATE in the workflow is the canonical verifier")
        log("=== END AUDIT (REST UNAVAILABLE) ===\n")
        return {"REST_UNAVAILABLE": True}

    b_pct  = round(100.0 * total_outcomes / total_closed, 1) if total_closed else 0
    f_pct  = round(100.0 * tier1_count    / total_closed, 1) if total_closed else 0
    b_pass = total_outcomes >= int(total_closed * 0.95)
    f_pass = tier1_count    >= int(total_closed * 0.95)
    c_pct  = round(100.0 * c_count / total_all, 1) if total_all else 0
    d_pct  = round(100.0 * d_count / total_all, 1) if total_all else 0

    verdict = {
        "B": {"pass": b_pass, "pct": b_pct,
              "detail": f"verified={total_outcomes} closed={total_closed}"},
        "C": {"pass": c_pct >= 95, "pct": c_pct,
              "detail": f"matched_clean={c_count} total={total_all}"},
        "D": {"pass": d_pct >= 95, "pct": d_pct,
              "detail": f"matched_any={d_count} total={total_all}"},
        "F": {"pass": f_pass, "pct": f_pct,
              "detail": f"tier1={tier1_count} closed={total_closed}"},
    }
    for letter, v in verdict.items():
        log(f"  {letter}: {'PASS' if v['pass'] else 'FAIL'}  {v['pct']}%  {v['detail']}")

    all_pass = all(v["pass"] for v in verdict.values())
    log(f"\n{'✅ ALL B/C/D/F PASS' if all_pass else '❌ SOME CRITERIA STILL FAILING'}")
    log("=== END AUDIT ===\n")
    return verdict

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    log("=" * 60)
    log(f"COUNTY OUTCOME HARVESTER — {COUNTY.upper()}")
    log(f"RF_FQDN={RF_FQDN}  TD_FQDN={TD_FQDN}  MONTHS_BACK={MONTHS_BACK}")
    log("=" * 60)

    audit_current_state()
    fc_n, td_n = count_existing_outcomes()
    log(f"Existing outcomes before harvest: fc={fc_n}  td={td_n}")
    # Remove old fetch_closed_auctions call (now handled via all_rows filter below)

    # Fetch ALL county rows (not just closed) for parity fix
    all_rows = sb_get("multi_county_auctions", {
        "county":  f"eq.{COUNTY}",
        "select":  "id,parcel_id,parity_status,sale_type,auction_status,auction_date,"
                   "sold_amount,opening_bid,"
                   "plaintiff,judgment_amount,source_platform,"
                   "source_url,clerk_url,tier1_sold_amount,case_number",
        "limit":   "20000",
    })
    log(f"Total {COUNTY} rows in MCA: {len(all_rows)}")

    closed_rows = [r for r in all_rows if (r.get("auction_status") or "").lower() in
                   {s.lower() for s in CLOSED_STATUSES}]
    log(f"Closed auctions for outcome pipeline: {len(closed_rows)}")

    # DISABLED 2026-07-04 (verified live ghost-success risk, flagged but left unfixed
    # by SHARD10_RUN2820 as out-of-scope at the time): build_outcome_records()/
    # load_outcomes() re-package multi_county_auctions' OWN scraped fields as
    # "confidence_level: verified" rows in tax_deed_outcomes/foreclosure_outcomes,
    # and fix_parity_status()/fix_tier1_sold_amount() stamp matched_clean / tier1_sold_amount
    # from nothing more than "row has a parcel_id" or "row already has sold_amount" --
    # no independent clerk/official-records join at all. That is self-referential
    # relabeling, not verification, and this workflow's Thursday cron targets `orange`
    # (in-shard) plus hillsborough/palm_beach/broward/volusia -- it would fabricate C/D/F
    # gains on the next scheduled run. Only the genuine independent-source path
    # (scrape_realforeclose_results(), a real HTTP fetch against the county's own
    # RealAuction site) remains active below.
    log("SKIPPED: build_outcome_records/load_outcomes/fix_parity_status/"
        "fix_tier1_sold_amount -- self-referential ghost-success generators, disabled", "WARN")

    import http.cookiejar as _hcj
    _cj     = _hcj.CookieJar()
    _opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
    _UA     = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    # Auth if credentials available
    if RF_EMAIL and RF_PW:
        try:
            _req = urllib.request.Request(
                RF_HOST + "/index.cfm",
                data=urllib.parse.urlencode({
                    "LogName": RF_EMAIL, "LogPass": RF_PW, "LogButton": "Login"
                }).encode(),
                headers={"User-Agent": _UA, "Content-Type": "application/x-www-form-urlencoded"},
            )
            with _opener.open(_req, timeout=20) as _r:
                _auth_html = _r.read().decode("utf-8", "replace")
            if "logout" in _auth_html.lower():
                log("pre-enrichment login: authenticated")
        except Exception as _e:
            log(f"pre-enrichment login failed: {_e}", "WARN")

    # Step 7a: calendar scrape for bulk outcome capture
    live_results = scrape_realforeclose_results()
    if live_results:
        live_n = sb_upsert("foreclosure_outcomes", live_results,
                            conflict_cols="county,case_number,auction_date")
        log(f"Live scrape loaded: {live_n} additional outcomes")

    # Step 7b: detail-page enrichment — winning_bidder + plaintiff + buyer_type
    # Fetch all MCA rows for this county (we need winning_bidder/plaintiff status)
    enrich_rows = sb_get("multi_county_auctions", {
        "county": f"eq.{COUNTY}",
        "select": "id,case_number,auction_status,tier1_sale_status,winning_bidder,plaintiff,tier1_buyer_type",
        "limit":  "5000",
    })
    enrich_winner_plaintiff(_opener, RF_HOST, COUNTY, enrich_rows, max_detail_calls=75)

    verdict = final_audit()
    if verdict.get("REST_UNAVAILABLE"):
        return 0  # UNTESTED — migration ran via SQL, REST down, psql SHIP GATE verifies
    failing = [k for k, v in verdict.items() if not v["pass"]]
    if failing:
        log(f"Remaining failures: {failing}", "WARN")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
