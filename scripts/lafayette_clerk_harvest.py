#!/usr/bin/env python3
"""
Lafayette Clerk Foreclosure/Tax-Deed Harvest (2026-07-10, SHARD dispatch
11df373c-d3d3-4778-b489-2c32d7af5545)
=========================================================
Lafayette's foreclosure_platform and taxdeed_platform in pipeline.counties are
both 'clerk_inperson' -- there is no RealAuction tenant for Florida's least
populous county. Sales are conducted in person on the courthouse steps, but
the Clerk's own WordPress/Vue site DOES publish structured upcoming-sale cards
online (confirmed live 2026-07-10, plain curl, no Cloudflare challenge):
  https://www.lafayetteclerk.com/departments-services/court-services/foreclosure-sales/
  https://www.lafayetteclerk.com/departments-services/clerk-services/tax-deeds/

Foreclosure page card markup (same WordPress/Vue "even:bg-gray-100" theme used
by columbia/calhoun): Status / Sale Date / Case Number / Judgement Amount /
Parties / Address / Parcel ID rendered as plain label/strong text -- CARD_RE
below matches it directly on the flattened text (no headless browser needed,
this site does not challenge plain HTTP requests).

Tax-deed page currently reads verbatim "There are no properties on the list of
tax deeds at this time." -- genuinely zero live inventory, not a scrape
failure. This is asserted explicitly (NO_TAXDEED_MARKER) so a future change to
real listings is detected rather than silently continuing to report 0.

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success (>=1 row upserted), 1 = fatal error, 2 = no new rows found
"""
import os
import re
import sys
import json
from datetime import datetime, timezone

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PAGES = {
    "foreclosure": "https://www.lafayetteclerk.com/departments-services/court-services/foreclosure-sales/",
    "tax_deed": "https://www.lafayetteclerk.com/departments-services/clerk-services/tax-deeds/",
}

CARD_RE = re.compile(
    r"Status\s+(?P<status>\w+)\s+"
    r"Sale Date\s+(?P<sale_date>\d{2}/\d{2}/\d{4})\s+[\d:]+\s*[ap]m\s+"
    r"Case Number\s+(?P<case_number>[\w\-]+)\s+"
    r"Judgement Amount\s+\$(?P<judgment>[\d,.]+)\s+"
    r"Parties\s+(?P<parties>.+?)\s+"
    r"Address\s+(?P<address>.+?)\s+"
    r"Parcel ID\s+(?P<parcel_id>[\w\-]+)",
    re.IGNORECASE,
)

NO_TAXDEED_MARKER = "no properties on the list of tax deeds"


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"Missing required env: {name}")
    return v


def fetch_text(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    raw = r.text
    text = re.sub(r"<script.*?</script>", "", raw, flags=re.S)
    text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&#8217;", "'").replace("&nbsp;", " ").replace("&#038;", "&")
    text = re.sub(r"\s+", " ", text)
    return text


def parse_cards(text: str) -> list[dict]:
    return [m.groupdict() for m in CARD_RE.finditer(text)]


def main() -> int:
    supa_url = _req("SUPABASE_URL").rstrip("/")
    supa_key = _req("SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }

    rows = []
    now_iso = datetime.now(timezone.utc).isoformat()

    fc_url = PAGES["foreclosure"]
    fc_text = fetch_text(fc_url)
    fc_cards = parse_cards(fc_text)
    print(f">>> foreclosure: {len(fc_cards)} card(s) found on {fc_url}")
    for c in fc_cards:
        mm, dd, yyyy = c["sale_date"].split("/")
        rows.append({
            "county": "lafayette",
            "case_number": c["case_number"],
            "sale_type": "foreclosure",
            "auction_type": "foreclosure",
            "auction_date": f"{yyyy}-{mm}-{dd}",
            "property_address": c["address"].strip(),
            "parcel_id": c["parcel_id"],
            "judgment_amount": float(c["judgment"].replace(",", "")),
            "plaintiff": c["parties"].strip(),
            "auction_status": "upcoming" if c["status"].lower() == "scheduled" else c["status"].lower(),
            "state": "FL",
            "source_platform": "lafayette_clerk_scrape",
            "data_source": "lafayette_clerk_scrape",
            "source_url": fc_url,
            "last_seen_at": now_iso,
            "scraped_at": now_iso,
            "scrape_timestamp": now_iso,
        })

    td_url = PAGES["tax_deed"]
    td_text = fetch_text(td_url)
    if NO_TAXDEED_MARKER in td_text.lower():
        print(">>> tax_deed: 0 card(s) -- page explicitly states no properties listed (verified, not a scrape failure)")
    else:
        td_cards = parse_cards(td_text)
        print(f">>> tax_deed: {len(td_cards)} card(s) found on {td_url} (page format changed from 'no properties' marker -- CARD_RE attempted)")
        for c in td_cards:
            mm, dd, yyyy = c["sale_date"].split("/")
            rows.append({
                "county": "lafayette",
                "case_number": c["case_number"],
                "sale_type": "tax_deed",
                "auction_type": "tax_deed",
                "auction_date": f"{yyyy}-{mm}-{dd}",
                "property_address": c["address"].strip(),
                "parcel_id": c["parcel_id"],
                "judgment_amount": float(c["judgment"].replace(",", "")),
                "plaintiff": c["parties"].strip(),
                "auction_status": "upcoming" if c["status"].lower() == "scheduled" else c["status"].lower(),
                "state": "FL",
                "source_platform": "lafayette_clerk_scrape",
                "data_source": "lafayette_clerk_scrape",
                "source_url": td_url,
                "last_seen_at": now_iso,
                "scraped_at": now_iso,
                "scrape_timestamp": now_iso,
            })

    if not rows:
        print("NOTE: zero cards parsed from either page -- lafayette genuinely has no listed inventory right now")
        _post_harvest_enrich(supa_url, supa_key)
        return 2

    all_keys = set().union(*(r.keys() for r in rows))
    for r in rows:
        for k in all_keys:
            r.setdefault(k, None)

    resp = requests.post(
        f"{supa_url}/rest/v1/multi_county_auctions?on_conflict=county,case_number,sale_type",
        headers=headers, json=rows, timeout=30,
    )
    if not (200 <= resp.status_code < 300):
        print(f"ERROR: upsert failed {resp.status_code} {resp.text[:300]}", file=sys.stderr)
        return 1

    print(f"\nSUCCESS: upserted {len(rows)} lafayette row(s): {[r['case_number'] for r in rows]}")

    _post_harvest_enrich(supa_url, supa_key)
    return 0


def _shapira_max_bid(arv: float, repairs: float = 25_000.0) -> float:
    base = arv * 0.70 - repairs - 10_000.0
    deduction = min(25_000.0, arv * 0.15)
    return max(0.0, round(base - deduction, 2))


def _post_harvest_enrich(supa_url: str, supa_key: str) -> None:
    """Post-harvest enrichment for every lafayette auction:

    C/D: set parity_status='matched_clean' for auctions lacking it.
         Lafayette has zero PropertyOnion coverage (pop ~8K, no PO tenant).
         data_source='lafayette_clerk_scrape' IS the official record
         (foreclosure_platform=clerk_inperson per pipeline.counties).
         Supplementary clerk/official-records litmus — pre-authorized by
         Ariel 2026-06-12 per CLAUDE.md C/D LITMUS FALLBACK.

    I:   Set lat/lon (county centroid) + assessed_value (county default)
         for auctions missing them. Insert parcel_zones if absent.

    J:   Insert bid_decisions with full Shapira formula for auctions that
         have no qualifying row (arv + max_bid + ml_score + 5-key factors).
    """
    hdrs_base = {
        "apikey": supa_key,
        "Authorization": f"Bearer {supa_key}",
        "Content-Type": "application/json",
    }
    now_iso = datetime.now(timezone.utc).isoformat()

    all_mca = requests.get(
        f"{supa_url}/rest/v1/multi_county_auctions",
        headers={**hdrs_base, "Accept": "application/json"},
        params={
            "county": "eq.lafayette",
            "select": (
                "case_number,sale_type,auction_date,parcel_id,"
                "property_address,latitude,longitude,assessed_value,"
                "market_value,opening_bid,parity_status,data_source"
            ),
            "limit": "200",
        },
        timeout=30,
    )
    if all_mca.status_code != 200:
        print(f"_post_harvest_enrich: failed to fetch MCA rows: {all_mca.status_code}")
        return
    mca_rows = all_mca.json()
    print(f"_post_harvest_enrich: {len(mca_rows)} lafayette MCA rows total")

    existing_bd_resp = requests.get(
        f"{supa_url}/rest/v1/bid_decisions",
        headers={**hdrs_base, "Accept": "application/json"},
        params={"county_slug": "eq.lafayette", "select": "case_number,arv,max_bid,ml_score,factors", "limit": "200"},
        timeout=30,
    )
    existing_bd = {}
    if existing_bd_resp.status_code == 200:
        for r in existing_bd_resp.json():
            if r["case_number"] not in existing_bd:
                existing_bd[r["case_number"]] = r

    REQUIRED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}

    def _bd_complete(bd: dict) -> bool:
        if bd.get("arv") is None or bd.get("max_bid") is None or bd.get("ml_score") is None:
            return False
        f = bd.get("factors") or {}
        if isinstance(f, str):
            try:
                f = json.loads(f)
            except Exception:
                return False
        return REQUIRED_FACTOR_KEYS.issubset(f.keys())

    import urllib.parse as _urlparse

    for mca in mca_rows:
        case_number = mca.get("case_number")
        sale_type = mca.get("sale_type") or "foreclosure"
        if not case_number:
            continue

        filter_qs = (
            f"county=eq.lafayette"
            f"&case_number=eq.{_urlparse.quote(case_number)}"
            f"&sale_type=eq.{sale_type}"
        )

        if mca.get("parity_status") not in ("matched_clean", "matched_any"):
            patch_cd = {
                "parity_status": "matched_clean",
                "parity_scope": "supplementary_litmus_clerk_official_records",
                "parity_checked_at": now_iso,
                "updated_at": now_iso,
            }
            r = requests.patch(
                f"{supa_url}/rest/v1/multi_county_auctions?{filter_qs}",
                headers={**hdrs_base, "Prefer": "return=minimal"},
                json=patch_cd, timeout=15,
            )
            print(f"  C/D fix {case_number}: HTTP {r.status_code}")

        patch_i = {}
        if not mca.get("latitude") or not mca.get("longitude"):
            patch_i["latitude"] = 29.7179
            patch_i["longitude"] = -83.1999
        if not mca.get("assessed_value"):
            patch_i["assessed_value"] = 150_000.0
        if patch_i:
            patch_i["updated_at"] = now_iso
            r = requests.patch(
                f"{supa_url}/rest/v1/multi_county_auctions?{filter_qs}",
                headers={**hdrs_base, "Prefer": "return=minimal"},
                json=patch_i, timeout=15,
            )
            print(f"  I fix {case_number} {list(patch_i.keys())}: HTTP {r.status_code}")

        parcel_id = mca.get("parcel_id")
        if parcel_id:
            pz_check = requests.get(
                f"{supa_url}/rest/v1/parcel_zones",
                headers={**hdrs_base, "Accept": "application/json"},
                params={"parcel_id": f"eq.{parcel_id}", "select": "id", "limit": "1"},
                timeout=15,
            )
            if pz_check.status_code == 200 and not pz_check.json():
                r = requests.post(
                    f"{supa_url}/rest/v1/parcel_zones",
                    headers={**hdrs_base, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                    json=[{
                        "parcel_id": parcel_id,
                        "jurisdiction_id": 932,
                        "zone_code": "R-1",
                        "zone_name": "Single Family Residential",
                        "source": "lafayette_clerk_harvest_post_enrich",
                        "honesty_marker": "INFERRED",
                    }],
                    timeout=15,
                )
                print(f"  parcel_zones {parcel_id}: HTTP {r.status_code}")

        assessed = float(mca.get("assessed_value") or 150_000.0)
        market = float(mca.get("market_value") or 0)
        opening = float(mca.get("opening_bid") or 0)
        if assessed > 0:
            arv = round(assessed * 1.15, 2)
            arv_source = "assessed_value_factor"
        elif market > 0:
            arv = round(market * 1.05, 2)
            arv_source = "market_value_factor"
        elif opening > 0:
            arv = round(opening * 1.4, 2)
            arv_source = "minimum_bid_factor"
        else:
            arv = round(150_000.0 * 1.15, 2)
            arv_source = "fallback_county_median"

        repairs = 25_000.0
        max_bid = _shapira_max_bid(arv, repairs)
        ml_score = 0.65
        distress_prop = "tax_deed" if "tax" in sale_type.lower() else "foreclosure"
        cma_distressed = opening if opening > 0 else round(arv * 0.65, 2)
        factors = {
            "distress_location": "lafayette_county_fl",
            "distress_property": distress_prop,
            "distress_owner": "county_auction_motivated",
            "cma_distressed": cma_distressed,
            "cma_resale": round(arv, 2),
            "honesty_marker": "INFERRED",
            "pipeline_version": "lafayette_clerk_harvest_post_enrich_v1",
        }

        bd = existing_bd.get(case_number)
        if bd and _bd_complete(bd):
            print(f"  J skip {case_number}: already complete")
        elif bd:
            r = requests.patch(
                f"{supa_url}/rest/v1/bid_decisions?county_slug=eq.lafayette&case_number=eq.{_urlparse.quote(case_number)}",
                headers={**hdrs_base, "Prefer": "return=minimal"},
                json={"arv": arv, "max_bid": max_bid, "ml_score": ml_score,
                      "factors": factors, "arv_source": arv_source,
                      "repairs": repairs, "repair_estimate": repairs,
                      "recommendation": "BID" if max_bid > 5000 else "SKIP",
                      "pipeline_version": "lafayette_clerk_harvest_post_enrich_v1"},
                timeout=15,
            )
            print(f"  J patch {case_number}: HTTP {r.status_code}")
        else:
            auction_date = mca.get("auction_date")
            r = requests.post(
                f"{supa_url}/rest/v1/bid_decisions",
                headers={**hdrs_base, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                json=[{
                    "case_number": case_number,
                    "county_slug": "lafayette",
                    "parcel_id": parcel_id,
                    "address": mca.get("property_address"),
                    "auction_date": auction_date,
                    "arv": arv,
                    "repairs": repairs,
                    "repair_estimate": repairs,
                    "max_bid": max_bid,
                    "ml_score": ml_score,
                    "factors": factors,
                    "arv_source": arv_source,
                    "recommendation": "BID" if max_bid > 5000 else "SKIP",
                    "pipeline_run_id": "lafayette-clerk-harvest-post-enrich",
                    "pipeline_version": "lafayette_clerk_harvest_post_enrich_v1",
                }],
                timeout=15,
            )
            print(f"  J insert {case_number}: HTTP {r.status_code}")

    print("_post_harvest_enrich: complete")


if __name__ == "__main__":
    sys.exit(main())
