#!/usr/bin/env python3
"""GOLD STANDARD SHARD-4, dispatch cefc3fb1 -- gadsden E/I parcel-linkage backfill.

ROOT CAUSE (verified live 2026-08-11): the clerk_ssot calendar sweep
(scripts/clerk_ssot/parsers/gadsden.py) added 40 new gadsden auction rows
(case_number/sale_date/status only, from Aug/Sep/Oct 2026 clerk sheets) but
that parser only captures 4 columns from each source table and DISCARDS
columns that are already present on the live gadsdenclerk.com sheets:

  Foreclosure sheet columns: SaleDate | CASE# | Plaintiff | Defendant |
    Property Address | (blank) | JudgmentAmount | (blank)
    -- parser (scripts/clerk_ssot/parsers/gadsden.py:parse_foreclosure) only
    takes cells[0..3], silently dropping Property Address + JudgmentAmount.

  Tax deed sheet columns: SaleDate | Case# | TaxCertificate# | Certificate
    Holder | Last Owner of Record | Parcel # | Address | LienHolders |
    OpeningBid | SalePrice | Excess Overbid
    -- parser only takes cells[0..4] + cells[9], silently dropping the real,
    authoritative Parcel # (cells[5]) and Address (cells[6]).

This is why 40/63 gadsden rows (all inserted by the clerk_ssot sweep) carry
NULL parcel_id/property_address/owner_name despite the clerk source having
every one of those fields directly retrievable, no fuzzy matching needed
for tax deeds (Parcel # is printed verbatim on the source page).

This script does NOT touch scripts/clerk_ssot/parsers/gadsden.py itself
(that is shared cross-county code -- out of shard-4 scope, and editing it
requires a Duval smoke-test per the scraper-framework rebase rule). It
re-fetches the live sheets directly and backfills multi_county_auctions +
cross-references fl_parcels(co_no=30) for real geo/assessed-value, which is
the same effect for gadsden without touching shared code paths.

TD rows: parcel_id is CONFIRMED (verbatim clerk source). fl_parcels lookup
by that parcel_id (co_no=30, verified co_no for gadsden per
20260704_shard11_gadsden_e_parcel_linkage.sql) supplies CONFIRMED
phy_addr1/phy_city/jv/centroid_lat/centroid_lng/own_name -- real appraisal
data, not a proxy.

FC rows: property_address + judgment_amount are CONFIRMED (verbatim clerk
source) but parcel_id is not printed on that sheet. Address-based fl_parcels
match attempted only where the source address is a real street address (not
a bare PLSS/legal description) and the match is UNIQUE. INFERRED assessed
value = judgment_amount proxy (same convention as the original
shard8_gadsden_bootstrap_v1 session) where no unique parcel match is found.

Usage: python3 scripts/gold_standard_shard4_gadsden_dispatch_cefc3fb1_e_backfill.py [--dry-run]
"""
from __future__ import annotations
import json, os, re, sys, time
import urllib.request, urllib.error

DISPATCH_ID = "cefc3fb1-5729-4e6e-9bcd-1eb696cdc9d3"
COUNTY = "gadsden"
CO_NO = 30  # confirmed gadsden's real fl_parcels co_no (not 20 -- see 20260704 migration)

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
BASE = f"{SB_URL}/rest/v1"
DRY_RUN = "--dry-run" in sys.argv


def ts():
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table, params=""):
    url = f"{BASE}/{table}?{params}" if params else f"{BASE}/{table}"
    req = urllib.request.Request(url, headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(table, filters, data):
    if DRY_RUN:
        log(f"  [DRY-RUN] PATCH {table}?{filters} -> {data}")
        return 200, "dry-run"
    url = f"{BASE}/{table}?{filters}"
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(),
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def money(s):
    if not s:
        return None
    s = re.sub(r"[^0-9.]", "", s)
    return float(s) if s else None


def norm_addr(addr, city=""):
    s = (addr or "") + " " + (city or "")
    s = s.upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    s = s.replace("STREET", "ST").replace("AVENUE", "AVE").replace("ROAD", "RD").replace("DRIVE", "DR")
    return s


import httpx
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
FC_URL = "http://www.gadsdenclerk.com/Foreclosures/Foreclosures_files/sheet001.htm"
TD_URL = "http://www.gadsdenclerk.com/Tax_deeds/Tax_deeds_files/sheet001.htm"
FC_CASE_RE = re.compile(r"^\d{5,8}(CA|CC)[A-Z]{0,3}$")
TD_CASE_RE = re.compile(r"^\d{6,10}TDC$")


def fetch_table(url):
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml")
    table = soup.find("table")
    return [[td.get_text(strip=True) for td in tr.find_all(["td", "th"])] for tr in table.find_all("tr")]


log("=== Fetching live gadsdenclerk.com sheets (full columns) ===")
fc_raw, td_raw = {}, {}
for r in fetch_table(FC_URL):
    if len(r) >= 5 and FC_CASE_RE.match(r[1]):
        fc_raw[r[1]] = {"address": r[4], "judgment": money(r[6] if len(r) > 6 else ""), "defendant": r[3]}
for r in fetch_table(TD_URL):
    if len(r) >= 7 and TD_CASE_RE.match(r[1]):
        td_raw[r[1]] = {"parcel_id": r[5], "address": r[6], "owner": r[4],
                         "opening_bid": money(r[8] if len(r) > 8 else ""),
                         "sale_price": r[9] if len(r) > 9 else ""}
log(f"  FC parsed: {len(fc_raw)}, TD parsed: {len(td_raw)}")

log("=== Fetching gadsden rows currently missing parcel_id ===")
mca = sb_get("multi_county_auctions",
             "county=eq.gadsden&parcel_id=is.null&select=case_number,sale_type")
log(f"  unlinked rows: {len(mca)}")

E_LINKED, E_ENRICHED_NO_LINK, E_SKIPPED = 0, 0, 0
now_iso = ts()

for row in mca:
    cn = row["case_number"]
    if row["sale_type"] == "tax_deed":
        src = td_raw.get(cn)
        if not src:
            E_SKIPPED += 1
            log(f"  SKIP {cn}: not on live TD sheet (fell off, no source data this session)")
            continue
        pid = src["parcel_id"]
        fp = sb_get("fl_parcels", f"co_no=eq.{CO_NO}&parcel_id=eq.{pid}&select=phy_addr1,phy_city,jv,centroid_lat,centroid_lng,own_name")
        patch = {
            "parcel_id": pid,
            "owner_name": src["owner"],
            "opening_bid": src["opening_bid"],
            "last_seen_at": now_iso, "updated_at": now_iso,
        }
        if fp:
            f = fp[0]
            patch["property_address"] = f"{f['phy_addr1']}, {f['phy_city']}, FL"
            patch["assessed_value"] = f["jv"]
            patch["assessed_value_source"] = "fl_parcels_jv_confirmed"
            patch["latitude"] = f["centroid_lat"]
            patch["longitude"] = f["centroid_lng"]
            log(f"  TD {cn}: parcel_id={pid} CONFIRMED via clerk sheet, fl_parcels match found (jv={f['jv']})")
        else:
            patch["property_address"] = src["address"]
            log(f"  TD {cn}: parcel_id={pid} CONFIRMED via clerk sheet, no fl_parcels(co_no={CO_NO}) row (co_no or format mismatch) -- address from clerk only")
        s, resp = sb_patch("multi_county_auctions", f"case_number=eq.{cn}", patch)
        if s < 300:
            E_LINKED += 1
        else:
            log(f"    PATCH FAILED {s}: {resp[:200]}")
    else:  # foreclosure
        src = fc_raw.get(cn)
        if not src:
            E_SKIPPED += 1
            log(f"  SKIP {cn}: not on live FC sheet (fell off, no source data this session)")
            continue
        addr = src["address"]
        is_legal_desc = bool(re.search(r"\b(Lot|Block|Section|Township|Parcels?|Subdivision)\b", addr, re.I)) or addr.strip().lower() == "parcel"
        patch = {
            "property_address": f"{addr}, Gadsden County, FL",
            "judgment_amount": src["judgment"],
            "opening_bid": src["judgment"],
            "owner_name": src["defendant"],
            "last_seen_at": now_iso, "updated_at": now_iso,
        }
        matched_pid = None
        if not is_legal_desc:
            target = norm_addr(addr)
            cands = sb_get("fl_parcels", f"co_no=eq.{CO_NO}&select=parcel_id,phy_addr1,phy_city,jv,centroid_lat,centroid_lng&limit=500")
            uniq = [c for c in cands if norm_addr(c["phy_addr1"], c["phy_city"]).startswith(target[:12]) and target[:12]]
            # tighter: exact normalized-street match
            uniq = [c for c in cands if norm_addr(c["phy_addr1"]) == norm_addr(addr.split(",")[0])]
            if len(uniq) == 1:
                f = uniq[0]
                matched_pid = f["parcel_id"]
                patch["parcel_id"] = matched_pid
                patch["assessed_value"] = f["jv"]
                patch["assessed_value_source"] = "fl_parcels_jv_confirmed"
                patch["latitude"] = f["centroid_lat"]
                patch["longitude"] = f["centroid_lng"]
                patch["property_address"] = f"{f['phy_addr1']}, {f['phy_city']}, FL"
                log(f"  FC {cn}: UNIQUE address match -> parcel_id={matched_pid}")
            elif len(uniq) > 1:
                log(f"  FC {cn}: address '{addr}' AMBIGUOUS ({len(uniq)} candidates) -- leaving parcel_id NULL")
            else:
                log(f"  FC {cn}: address '{addr}' no fl_parcels match -- leaving parcel_id NULL")
        else:
            log(f"  FC {cn}: '{addr}' is a legal/plat description, not a street address -- leaving parcel_id NULL (no fabrication)")
        if not matched_pid:
            patch["assessed_value"] = src["judgment"]
            patch["assessed_value_source"] = "judgment_amount_proxy_inferred"
        s, resp = sb_patch("multi_county_auctions", f"case_number=eq.{cn}", patch)
        if s < 300:
            if matched_pid:
                E_LINKED += 1
            else:
                E_ENRICHED_NO_LINK += 1
        else:
            log(f"    PATCH FAILED {s}: {resp[:200]}")

log("=== SUMMARY ===")
log(f"  parcel_id linked (E): {E_LINKED}")
log(f"  enriched but not parcel-linked: {E_ENRICHED_NO_LINK}")
log(f"  skipped (fell off live sheet): {E_SKIPPED}")
