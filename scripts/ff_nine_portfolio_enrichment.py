#!/usr/bin/env python3
"""Nine-case FF enrichment runner.

Reads 2026-08-26 third-party auctions from multi_county_auctions, applies the
validated parcel crosswalk, enriches property/portfolio fields from ZoneWise,
and optionally calls Tracerfy only when a prior buyer-owned mailing address is
available. No find_owner call is made and no purchased-property address is
used as a buyer contact anchor.
"""
from __future__ import annotations
import json, os, re, sys, time, urllib.error, urllib.request
from datetime import date, datetime, timezone

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_DATE = os.environ.get("BATCH_DATE", "2026-08-26")
OUT = os.environ.get("OUT", f"ff_nine_enrichment_{BATCH_DATE}.json")
SB_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
TRACERFY_KEY = os.environ.get("TRACERFY_API_KEY", "")


def sql(q: str):
    if not SB_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN is required")
    req = urllib.request.Request(MGMT_URL, data=json.dumps({"query": q}).encode(), headers={"Authorization": f"Bearer {SB_TOKEN}", "Content-Type": "application/json", "User-Agent": "winnerdata-ff-nine-enrichment/1.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        body = json.loads(r.read())
    if isinstance(body, dict) and body.get("message"):
        raise RuntimeError(body["message"])
    return body


def esc(v):
    return str(v or "").replace("'", "''")


def norm(v):
    return re.sub(r"[^A-Z0-9]", "", (v or "").upper())


def tracerfy(name, address, city, state, zipcode):
    if not TRACERFY_KEY or not address:
        return {"status": "SKIPPED_NO_TRACERFY_OR_PRIOR_ADDRESS"}
    parts = (name or "").strip().split(",", 1)
    if len(parts) == 2:
        first, last = parts[1].strip().split(" ", 1)[0], parts[0].strip()
    else:
        toks = (name or "").split()
        first, last = (toks[-1], toks[0]) if len(toks) > 1 else ("", name or "")
    payload = {"first_name": first, "last_name": last, "address": address, "city": city, "state": state, "zip": zipcode}
    req = urllib.request.Request("https://tracerfy.com/v1/api/trace/enhanced/lookup/", data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {TRACERFY_KEY}", "Content-Type": "application/json", "User-Agent": "winnerdata-pipeline/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = json.loads(r.read())
        if not body.get("hit") or not body.get("persons"):
            return {"status": "NO_MATCH"}
        p = body["persons"][0]
        phones = sorted(p.get("phones") or [], key=lambda x: x.get("rank", 999))
        emails = sorted(p.get("emails") or [], key=lambda x: x.get("rank", 999))
        return {"status": "OK", "full_name": p.get("full_name"), "phone": phones[0].get("number") if phones else None, "email": emails[0].get("email") if emails else None, "source": "Tracerfy enhanced lookup", "queried_anchor": {"address": address, "city": city, "state": state, "zip": zipcode}}
    except Exception as e:
        return {"status": "REQUEST_FAILED", "error": str(e)[:240]}


def main():
    auctions = sql(f"""select id, county, auction_date, property_address, case_number, sale_type, tier1_buyer_type, winning_bidder, tier1_sold_amount, market_value, assessed_value, parcel_id, auction_url, source_url from public.multi_county_auctions where auction_date = date '{esc(BATCH_DATE)}' and tier1_buyer_type = 'third_party' and nullif(btrim(winning_bidder), '') is not null order by county, case_number limit 20""")
    if len(auctions) != 9:
        raise RuntimeError(f"Expected 9 third-party auctions for {BATCH_DATE}; got {len(auctions)}")
    out = []
    for a in auctions:
        auction_id = a["id"]
        x = sql(f"select auction_id, auction_parcel_id, pin_clean, match_method, verified_at, verified_by from winnerdata.ff_parcel_crosswalk where auction_id = '{esc(auction_id)}' limit 1")
        if not x:
            out.append({"auction": a, "qa_status": "BLOCKED_NO_VALIDATED_CROSSWALK"})
            continue
        pin = x[0]["pin_clean"]
        p = sql(f"select county, pin_clean, owner_name, owner_name2, owner_addr1, owner_addr2, owner_city, owner_state, owner_zip, site_addr, site_city, site_zip, luse_code, luse_desc, num_buildings, sqft_heated, year_built, val_market, val_assessed, pa_link, data_source, updated_at from public.zw_parcels where pin_clean = '{esc(pin)}' limit 2")
        parcel = p[0] if p else None
        prior = sql(f"select parcel_id, own_name, own_addr1, own_city, own_state, own_zip from public.fl_parcels where upper(regexp_replace(coalesce(own_name,''),'[^A-Z0-9]','','g')) = upper(regexp_replace('{esc(a['winning_bidder'])}','[^A-Z0-9]','','g')) limit 5")
        anchor = prior[0] if prior else None
        tf = tracerfy(a["winning_bidder"], anchor.get("own_addr1") if anchor else None, anchor.get("own_city") if anchor else None, anchor.get("own_state") if anchor else None, anchor.get("own_zip") if anchor else None)
        out.append({"auction": a, "crosswalk": x[0], "parcel": parcel, "prior_buyer_owned_addresses": prior, "tracerfy": tf, "qa_status": "SSOT_MATCHED" if parcel and parcel.get("owner_name") else "BLOCKED_NO_PARCEL_SSOT"})
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "batch_date": BATCH_DATE, "candidate_count": len(auctions), "records": out, "bright_data": "NOT_RUN_NO_KEY", "policy": "BLANK_OVER_WRONG; no purchased-property address used for buyer contact"}
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(json.dumps({"output": OUT, "candidate_count": len(auctions), "ssot_matched": sum(r.get("qa_status") == "SSOT_MATCHED" for r in out), "tracerfy_ok": sum(r.get("tracerfy", {}).get("status") == "OK" for r in out)}, indent=2))

if __name__ == "__main__":
    main()
