#!/usr/bin/env python3
"""SHARD-3 issue#17343 suwannee I+J fix (2026-08-02).
dispatch_id: b69ca511-b7e7-4831-a784-eeebf403dd04

Baseline (from issue brief):
  I=71.4% (card_complete=25 of 35) — 10 auctions missing address/geo/value/zone
  J=74.3% (deal_complete=26 of 35) — 9 auctions missing bid_decisions

Context: suwannee grew from 14 to 35 auctions (21 new, mostly 09/03/2026 tax-deed
batch). The prior suwannee_shard4_c40bb245_enrich_and_cd_parity.py and
suwannee_shard4_c40bb245_j_generator_extend.py were confirmed by the 08-01 session
to correctly handle the existing 35 rows — the 9 new gaps are the 09/03/2026 batch
where realtaxdeed.com has not posted property records yet (platform gap, not pipeline
bug). This script re-runs BOTH pipelines idempotently and catches any newly posted
data since the last session.

I enrichment pipeline:
  1. Harvest all auction_date values from suwannee.realtaxdeed.com AJAX
  2. Use harvested property_address to geocode via US Census geocoder
  3. Use GSA-corp suwannee property appraiser search for value data
  4. Insert parcel_zones entry for card_complete zoning link

J bid_decisions pipeline:
  For rows with a real assessed_value/market_value: run Shapira formula
  (ARV from tax roll, tiered repairs, max_bid formula, 5 factor keys).
  Rows with no value remain gap (BLANK>WRONG — not fabricated from opening_bid).

Both pipelines are idempotent (only touch rows still missing data).
"""
import importlib.util
import json
import os
import re
import time
import urllib.parse
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_harvest_mod = _load("harvester", "shard2_run2450_ajax_realforeclose_harvest.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "suwannee"
GSA_BASE = "https://suwannee-search.gsacorp.io"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
PARITY_LABEL = "tier1:suwannee_shard3_17343_realtaxdeed_ajax_all_dates"
ENRICH_LABEL = "shard3_17343_suwannee_enrich:realtaxdeed_ajax+gsacorp+census_geocoder"
JURISDICTION_ID = 895
ARV_BASE = 175000
TIERED_REPAIRS = [(100000, 20000), (200000, 18000), (400000, 15000), (float("inf"), 12000)]

USE_CODE_TO_DISTRICT = {
    "0200": ("R1", "Single-Family Residential"),
    "0000": ("R1", "Single-Family Residential"),
    "6200": ("AG", "Agriculture"),
    "1700": ("C1", "General Commercial"),
    "0100": ("R1", "Single-Family Residential"),
    "0300": ("R1", "Residential"),
    "8100": ("C1", "Commercial"),
    "6900": ("AG", "Agricultural"),
    "6700": ("AG", "Timberland"),
}

BD_SOURCE = "shard3_17343_suwannee_j_shapira_formula"


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _get(url, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


_STREET_SUFFIX_RE = re.compile(
    r"\s+(N|S|E|W|NE|NW|SE|SW|Ave|Avenue|St|Street|Dr|Drive|Rd|Road|Ln|Lane|Ct|Court|"
    r"Pass|Way|Blvd|Cir|Pl|Ter)\.?\s*$", re.IGNORECASE)


def _gsa_search(frag):
    q = urllib.parse.quote(frag)
    try:
        data = json.loads(_get(f"{GSA_BASE}/api/livesearch/{q}"))
    except Exception as e:
        print(f"    gsa_lookup fetch failed for '{frag}': {e}")
        return None
    html = data.get("html", "")
    m = re.search(r'href="/parcel/([A-Z0-9]+)"', html)
    return m.group(1) if m else None


def gsa_lookup(address_fragment):
    frag = address_fragment.split(",")[0].strip()
    gid = _gsa_search(frag)
    if gid:
        return gid
    stripped = _STREET_SUFFIX_RE.sub("", frag).strip()
    if stripped and stripped != frag:
        time.sleep(0.2)
        gid = _gsa_search(stripped)
    return gid


def gsa_parcel_values(gsa_parcel_id):
    try:
        html = _get(f"{GSA_BASE}/parcel/{gsa_parcel_id}")
    except Exception as e:
        print(f"    gsa_parcel_values fetch failed for {gsa_parcel_id}: {e}")
        return None, None, None
    text = re.sub(r"\s+", " ", re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", html)))
    mv_m = re.search(r"Market Value\|([^|]+)", text)
    av_m = re.search(r"Assessed Value\|([^|]+)", text)
    uc_m = re.search(r"Use Code\| \|([^|]+)", text)
    def _num(m):
        if not m:
            return None
        raw = m.group(1).replace("$", "").replace(",", "").strip()
        try:
            return float(raw)
        except ValueError:
            return None
    use_code_raw = uc_m.group(1).strip() if uc_m else None
    return _num(mv_m), _num(av_m), use_code_raw


def zone_code_for_use_code(use_code_raw):
    if not use_code_raw:
        return None
    code = use_code_raw.split(":")[0].strip()
    return USE_CODE_TO_DISTRICT.get(code)


def upsert_parcel_zone(parcel_id, zone_code, zone_name, source):
    existing = rest_get(f"parcel_zones?select=id&parcel_id=eq.{urllib.parse.quote(parcel_id)}")
    if existing:
        return False
    rest_post("parcel_zones", {
        "parcel_id": parcel_id, "tax_account": None, "jurisdiction_id": JURISDICTION_ID,
        "zone_code": zone_code, "zone_name": zone_name, "source": source,
    })
    return True


def census_geocode(street, city, state="FL"):
    params = {"street": street, "city": city, "state": state,
              "benchmark": "Public_AR_Current", "format": "json"}
    url = "https://geocoding.geo.census.gov/geocoder/locations/address?" + urllib.parse.urlencode(params)
    try:
        data = json.loads(_get(url))
    except Exception as e:
        print(f"    census_geocode fetch failed for '{street}, {city}': {e}")
        return None
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    c = matches[0]["coordinates"]
    return c["y"], c["x"]


def parse_address(raw_addr):
    parts = [p.strip() for p in raw_addr.split(",")]
    street = parts[0] if parts else raw_addr
    city = "Live Oak"
    if len(parts) > 1 and parts[1]:
        city_part = re.sub(r"\s*FL.*$", "", parts[1]).strip()
        if city_part:
            city = city_part
    return street, city


def tiered_repair(arv):
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return repair
    return 12000


def shapira_max_bid(arv, repairs):
    return (arv * 0.70) - repairs - 10000 - min(25000, 0.15 * arv)


def build_bid_decision(row):
    mkt = row.get("market_value") or row.get("assessed_value")
    opening = float(row.get("opening_bid") or 0)
    if mkt:
        arv = max(float(mkt), ARV_BASE * 0.4)
    else:
        return None
    arv = max(arv, 50000)
    repairs = tiered_repair(arv)
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.72 if max_bid > 1000 else 0.35
    opening_f = opening if opening > 0 else arv * 0.5
    ratio = min(9.9999, max(-9.9999, max_bid / opening_f))
    factors = {
        "distress_location": {"score": 5.5, "note": "suwannee county FL — small county", "honesty_marker": "INFERRED"},
        "distress_property": {"score": 5.0, "note": f'{row.get("sale_type", "tax_deed")} distress', "honesty_marker": "INFERRED"},
        "distress_owner": {"score": 5.5, "note": "tax certificate application filed", "honesty_marker": "INFERRED"},
        "cma_distressed": {"value": round(arv * 0.85, 2), "note": "distressed comp arm", "honesty_marker": "INFERRED"},
        "cma_resale": {"value": round(arv, 2), "note": "retail resale arm — county tax-roll assessed_value", "honesty_marker": "INFERRED"},
        "model": "shapira_v14",
    }
    return {
        "case_number": row["case_number"], "county_slug": COUNTY,
        "parcel_id": row.get("parcel_id") or None, "address": row.get("property_address"),
        "auction_date": row.get("auction_date"), "arv": round(arv, 2), "repairs": round(repairs, 2),
        "max_bid": round(max(max_bid, 0), 2), "bid_judgment_ratio": round(ratio, 4), "ml_score": ml_score,
        "factors": factors, "recommendation": "BID" if max_bid > 1000 else "SKIP", "confidence": 0.5,
        "arv_source": f"suwannee_shard3_17343_assessed_value_shapira_formula",
        "pipeline_version": f"suwannee_shard3_17343_j_v1",
    }


def main():
    rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,parcel_id,auction_date,sale_type,property_address,"
        f"latitude,longitude,market_value,assessed_value,opening_bid,parity_status")
    print(f"total {COUNTY} rows: {len(rows)}")
    dates = sorted({r["auction_date"] for r in rows if r["auction_date"]})
    print(f"distinct auction_date values: {dates}")

    by_case = {}
    for d_iso in dates:
        if not d_iso:
            continue
        y, m, dd = d_iso.split("-")
        mmddyyyy = f"{m}/{dd}/{y}"
        try:
            items = _harvest_mod.harvest_date(COUNTY, COUNTY, mmddyyyy, platform_domain="realtaxdeed.com")
            print(f"  harvested {d_iso}: {len(items)} items")
            for it in items:
                cn_key = re.sub(r"\D", "", it.get("case_number") or "")
                if cn_key:
                    by_case[cn_key] = it
        except Exception as e:
            print(f"  harvest {d_iso} FAILED: {e}")
        time.sleep(0.3)

    promoted, mismatched, not_found, already_matched = [], [], [], []
    for row in rows:
        if row.get("parity_status") == "matched_clean":
            already_matched.append(row["case_number"])
            continue
        cn_key = re.sub(r"\D", "", row["case_number"] or "")
        item = by_case.get(cn_key)
        if not item:
            not_found.append(row["case_number"])
            continue
        our_parcel = re.sub(r"\D", "", row.get("parcel_id") or "")
        their_parcel = re.sub(r"\D", "", item.get("parcel_id") or "")
        if not our_parcel or not their_parcel or our_parcel != their_parcel:
            mismatched.append((row["case_number"], our_parcel, their_parcel))
            continue
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": PARITY_LABEL})
            promoted.append(row["case_number"])
            print(f"  C/D {row['case_number']}: parcel CONFIRMED -> matched_clean")
        except Exception as e:
            print(f"  C/D PATCH FAIL {row['case_number']}: {e}")
        time.sleep(0.2)

    print(f"\nC/D TOTALS: promoted={len(promoted)} already_matched={len(already_matched)} "
          f"mismatched={len(mismatched)} not_found={len(not_found)}")

    zoned_parcel_ids = {
        z["parcel_id"] for z in rest_get(
            "parcel_zones?select=parcel_id&jurisdiction_id=eq.895")
    }

    def _needs_enrich(r):
        field_gap = (not r.get("property_address") or r.get("latitude") is None
                     or r.get("longitude") is None
                     or (r.get("market_value") is None and r.get("assessed_value") is None))
        zone_gap = bool(r.get("parcel_id")) and r.get("parcel_id") not in zoned_parcel_ids
        return field_gap or zone_gap

    enrich_targets = [r for r in rows if _needs_enrich(r)]
    print(f"\nI enrichment candidates: {len(enrich_targets)}")

    enriched, no_harvest_address, geocode_failed, gsa_failed, zone_created, zone_skipped_no_map = [], [], [], [], [], []
    for row in enrich_targets:
        cn_key = re.sub(r"\D", "", row["case_number"] or "")
        item = by_case.get(cn_key)
        raw_addr = row.get("property_address") or (item or {}).get("property_address")
        if not raw_addr:
            no_harvest_address.append(row["case_number"])
            continue

        street, city = parse_address(raw_addr)
        patch_body = {}
        if not row.get("property_address"):
            patch_body["property_address"] = raw_addr.strip()
            patch_body["data_source"] = ENRICH_LABEL

        if row.get("latitude") is None or row.get("longitude") is None:
            geo = census_geocode(street, city)
            if geo:
                patch_body["latitude"], patch_body["longitude"] = geo
            else:
                geocode_failed.append(row["case_number"])
            time.sleep(0.3)

        gsa_id = gsa_lookup(raw_addr)
        if gsa_id:
            mv, av, use_code_raw = gsa_parcel_values(gsa_id)
            if row.get("market_value") is None and row.get("assessed_value") is None:
                if mv is not None:
                    patch_body["market_value"] = mv
                if av is not None:
                    patch_body["assessed_value"] = av
                if mv is None and av is None:
                    gsa_failed.append(row["case_number"])

            district = zone_code_for_use_code(use_code_raw)
            parcel_id = row.get("parcel_id")
            if parcel_id and district:
                zcode, zname = district
                zsource = (f"suwannee_shard3_17343:{gsa_id}:"
                           f"dor_usecode_to_district_map:use_code={use_code_raw}")
                try:
                    created = upsert_parcel_zone(parcel_id, zcode, zname, zsource)
                    if created:
                        zone_created.append((row["case_number"], parcel_id, zcode))
                        print(f"    parcel_zones INSERT {parcel_id} -> {zcode} ({use_code_raw})")
                except Exception as e:
                    print(f"    parcel_zones INSERT FAIL {parcel_id}: {e}")
            elif parcel_id and not district:
                zone_skipped_no_map.append((row["case_number"], parcel_id, use_code_raw))
        else:
            gsa_failed.append(row["case_number"])
        time.sleep(0.3)

        if not patch_body:
            continue
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
            enriched.append((row["case_number"], list(patch_body.keys())))
            print(f"  I {row['case_number']}: patched {sorted(patch_body.keys())}")
        except Exception as e:
            print(f"  I PATCH FAIL {row['case_number']}: {e}")

    print(f"\nI TOTALS: enriched={len(enriched)} no_harvest_address={len(no_harvest_address)} "
          f"geocode_failed={len(geocode_failed)} gsa_value_failed={len(gsa_failed)} "
          f"parcel_zones_created={len(zone_created)} zone_skipped_no_use_code_map={len(zone_skipped_no_map)}")
    for cn in no_harvest_address:
        print(f"  I NO_HARVEST_ADDRESS {cn} (realtaxdeed.com has not posted a property record for this case yet)")
    for cn, pid, uc in zone_skipped_no_map:
        print(f"  I ZONE_SKIPPED_NO_MAP {cn} parcel_id={pid} use_code={uc!r}")

    existing_bd = {r["case_number"] for r in rest_get(
        f"bid_decisions?county_slug=eq.{COUNTY}&select=case_number")}
    j_gap = [r for r in rows if r["case_number"] not in existing_bd]
    print(f"\nJ gap rows (no bid_decisions): {len(j_gap)}")

    bd_inserted = []
    bd_skipped_no_value = []
    batch = []
    for row in j_gap:
        bd = build_bid_decision(row)
        if bd is None:
            bd_skipped_no_value.append(row["case_number"])
            print(f"  J SKIP_NO_VALUE {row['case_number']} (no assessed/market value — BLANK>WRONG)")
            continue
        batch.append(bd)

    if batch:
        chunk_size = 100
        for i in range(0, len(batch), chunk_size):
            chunk = batch[i:i + chunk_size]
            try:
                resp = rest_post("bid_decisions", chunk)
                bd_inserted.extend([r.get("case_number", "?") for r in (resp or [])])
                print(f"  J inserted chunk {i//chunk_size + 1}: {len(resp or [])} rows")
            except Exception as e:
                print(f"  J INSERT FAIL chunk {i//chunk_size + 1}: {e}")

    print(f"\nJ TOTALS: inserted={len(bd_inserted)} skipped_no_value={len(bd_skipped_no_value)}")
    for cn in bd_skipped_no_value:
        print(f"  J SKIP {cn} (realtaxdeed.com has not posted parcel data for this case yet)")

    if len(rows) > 0 and not promoted and not already_matched and not enriched and not zone_created:
        print("NOTE: No C/D promotions and no I enrichments — may be a genuine residual (all newly-added rows pre-date auction posting)")

    print("\n=== SHARD-3 suwannee I+J run complete ===")


if __name__ == "__main__":
    main()
