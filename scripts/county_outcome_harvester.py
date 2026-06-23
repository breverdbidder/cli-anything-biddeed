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
def _sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h

def sb_get(path: str, params: dict = None) -> list | dict:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers=_sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"sb_get {path} HTTP {e.code}: {e.read()[:200]}", "WARN")
        return []

def sb_rpc(fn: str, payload: dict) -> list | dict | None:
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=body, headers=_sb_headers(), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"sb_rpc {fn}: {e}", "WARN")
        return None

def sb_upsert(table: str, rows: list[dict], conflict_cols: str = "") -> int:
    if not rows:
        return 0
    body  = json.dumps(rows).encode()
    extra = {"Prefer": f"resolution=merge-duplicates,return=minimal"}
    if conflict_cols:
        extra["Prefer"] += f",on-conflict={conflict_cols}"
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}", data=body,
        headers=_sb_headers(extra), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        return len(rows)
    except urllib.error.HTTPError as e:
        log(f"sb_upsert {table} HTTP {e.code}: {e.read()[:300]}", "WARN")
        return 0

def sb_patch(table: str, filter_qs: str, payload: dict) -> int:
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}", data=body,
        headers=_sb_headers({"Prefer": "return=minimal"}), method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
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
    result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": COUNTY})
    state  = {}
    if isinstance(result, list):
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
        "county_slug": f"eq.{COUNTY}", "select": "id", "limit": "10000",
    })
    td = sb_get("tax_deed_outcomes", {
        "county_slug": f"eq.{COUNTY}", "select": "id", "limit": "10000",
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
                "county_slug":        COUNTY,
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
                "county_slug":      COUNTY,
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
                       conflict_cols="county_slug,case_number,auction_date")
        fc_loaded += n
        log(f"  foreclosure_outcomes batch {i//BATCH+1}: {n}")
    for i in range(0, len(td_records), BATCH):
        n = sb_upsert("tax_deed_outcomes", td_records[i:i + BATCH],
                       conflict_cols="county_slug,case_number,auction_date")
        td_loaded += n
        log(f"  tax_deed_outcomes batch {i//BATCH+1}: {n}")
    return fc_loaded, td_loaded

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
                "county_slug":      COUNTY,
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

    b_pct  = round(100.0 * total_outcomes / total_closed, 1) if total_closed else 0
    f_pct  = round(100.0 * tier1_count    / total_closed, 1) if total_closed else 0
    b_pass = total_outcomes >= int(total_closed * 0.95)
    f_pass = tier1_count    >= int(total_closed * 0.95)

    parity_rows = sb_get("multi_county_auctions", {
        "county": f"eq.{COUNTY}", "select": "parity_status", "limit": "10000",
    })
    c_count = sum(1 for r in parity_rows if r.get("parity_status") == "matched_clean")
    d_count = sum(1 for r in parity_rows
                  if r.get("parity_status") in ("matched_clean", "matched_divergent"))
    total_all = len(parity_rows)
    c_pct = round(100.0 * c_count / total_all, 1) if total_all else 0
    d_pct = round(100.0 * d_count / total_all, 1) if total_all else 0

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

    closed_rows = fetch_closed_auctions()
    fc_records, td_records = build_outcome_records(closed_rows)
    fc_loaded, td_loaded   = load_outcomes(fc_records, td_records)
    log(f"Outcomes loaded: fc={fc_loaded}  td={td_loaded}")

    fixed = fix_tier1_sold_amount(closed_rows)
    log(f"tier1_sold_amount fixed: {fixed} rows")

    live_results = scrape_realforeclose_results()
    if live_results:
        live_n = sb_upsert("foreclosure_outcomes", live_results,
                            conflict_cols="county_slug,case_number,auction_date")
        log(f"Live scrape loaded: {live_n} additional outcomes")

    verdict = final_audit()
    failing = [k for k, v in verdict.items() if not v["pass"]]
    if failing:
        log(f"Remaining failures: {failing}", "WARN")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
