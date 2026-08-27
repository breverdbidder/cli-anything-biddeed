#!/usr/bin/env python3
"""P0 manual FF catch-up (2026-08-27): 9 real 3rd-party buyers / 7 distinct
entities, Aug 26 close, tier1_buyer_type='third_party' (multi_county_auctions,
live-queried and confirmed 9/9 match against the issue's list before this
script was written). Mariam's 8:00 AM ET Daily Winner FF deadline already
breached -- this is the manual catch-up, not #19517's automated pipeline.

SSOT: public.zw_parcels is the ONLY source used for property values/attrs
(NOT the FL DOH ArcGIS layer, which is a retracted 2011 well/septic snapshot
-- see issue). Own-name mailing-address lookups below are also against
zw_parcels.owner_name, not fl_parcels, per this issue's explicit instruction
(fl_parcels is the older/superseded table other batches used).

Method is the exact proven cascade from #19422/#19446/#19452/#19454/#19485,
reused unmodified via scripts/contact_resolver.py (Apify->Hunter->OSS for
businesses), scripts/identity_cascade.py (Sunbiz cascade for LLC/corp),
scripts/tracerfy_client.py (enhanced trace for persons against a KNOWN own
mailing address only -- never find_owner, never the just-purchased address).

Own-name lookups already run interactively before this script existed (see
session record): zw_parcels prefix/FTS scans confirmed real cross-checked
mailing addresses for 3 of 7 buyers (Ziarkowski/Randall, Hart Land
Development, Florida Investors Capital LLC) and a genuine statewide-absence
(zero zw_parcels rows) for the other 4 (OK Business LLC, Mundi Marketing LLC,
Ellen Horwitz, Jean Junior Louis Jeune) -- those results are hardcoded into
BUYERS below as known_mailing / needs_sunbiz rather than re-run, since the
underlying zw_parcels snapshot does not change within this session.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import contact_resolver  # noqa: E402
import tracerfy_client  # noqa: E402
import ff_credit_ledger  # noqa: E402
from identity_cascade import resolve_identity, normalize, exa_search, exa_contents  # noqa: E402

MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
BATCH = "20260827_p0_9buyer"

BUYERS = {
    "JOHN ZIARKOWSKI AND MENDY RANDALL": {
        "entities": ["ZIARKOWSKI JOHN", "RANDALL MENDY"], "type": "person", "needs_sunbiz": False,
        "case_numbers": ["25000033CA"], "county": "bay",
        "known_mailing": {"addr1": "2671 ROBIN HOOD LANE", "city": "BONIFAY", "state": "FL", "zip": "32425"},
        "mailing_evidence": "Cross-checked across 3 counties in zw_parcels.owner_name (Holmes 2x exact 'ZIARKOWSKI JOHN &' / 2671 Robin Hood Ln/Lane, Bay 'RANDALL, MENDY &' + 'ZIARKOWSKI, JOHN' both city=Bonifay zip=32425, Charlotte 'RANDALL MENDY & J ZIARKOWSKI' city=Bonifay zip=32425) -- 5 independent parcel records agree on Bonifay FL 32425 for this couple, own-name history not the just-purchased Bay Co address.",
    },
    "HART LAND DEVELOPMENT": {
        "entities": ["HART LAND DEVELOPMENT INC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["2026CA000210"], "county": "clay",
        "known_mailing": {"addr1": "10854 JUNIA ST", "city": "JACKSONVILLE", "state": "FL", "zip": "32219"},
        "mailing_evidence": "10+ Duval Co parcels in zw_parcels.owner_name='HART LAND DEVELOPMENT INC' all agree on 10854 Junia St, Jacksonville FL 32219 -- an active repeat land-development operator, not a one-off.",
    },
    "FLORIDA INVESTORS CAPITAL LLC": {
        "entities": ["FLORIDA INVESTORS CAPITAL LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["2025 CA 000894"], "county": "escambia",
        "known_mailing": {"addr1": "PO BOX 2086", "city": "LUTZ", "state": "FL", "zip": "33548"},
        "mailing_evidence": "2 independent Escambia Co parcels in zw_parcels.owner_name exact match agree on PO Box 2086, Lutz FL 33548.",
    },
    "OK BUSINESS LLC": {
        "entities": ["OK Business LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["25000544", "25000543"], "county": "highlands",
        "known_mailing": None,
        "mailing_evidence": "zw_parcels owner_name prefix scan 'OK BUS%' (index range scan, statewide, no county filter) returned ZERO rows -- this entity has no other Florida real property on file under this exact name. Sunbiz cascade is the only path.",
    },
    "MUNDI MARKETING LLC": {
        "entities": ["Mundi Marketing LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["24000615", "24000637"], "county": "highlands",
        "known_mailing": None,
        "mailing_evidence": "zw_parcels owner_name prefix scan 'MUNDI%' (index range scan, statewide) returned 20 rows, all individuals named Mundi*/Mundie*/Mundin*/Mundine* (coincidental surname collisions) -- zero 'MUNDI MARKETING LLC' hits. Sunbiz cascade is the only path.",
    },
    "ELLEN HORWITZ": {
        "entities": ["Ellen Horwitz"], "type": "person", "needs_sunbiz": False,
        "case_numbers": ["24000618"], "county": "highlands",
        "known_mailing": None,
        "mailing_evidence": "zw_parcels FTS scan for 'HORWITZ' (GIN index, statewide, 15 rows returned) found zero exact first-name match to Ellen -- 15 unrelated Horwitz individuals (Myron David, Heidi, Barry Alan, Aaron, Brent Kevin, Jason G, Joel David, Robin, Raquel Lena, Drew M, Sheldon M, Gerald A, Erwin, Heather, Brad E). Per identity_cascade exact-name discipline, none is usable as this buyer's own-name mailing address.",
    },
    "JEAN JUNIOR LOUIS JEUNE": {
        "entities": ["Jean Junior Louis Jeune"], "type": "person", "needs_sunbiz": False,
        "case_numbers": ["25000546"], "county": "highlands",
        "known_mailing": None,
        "mailing_evidence": "zw_parcels FTS scan for 'louis-jeune | jeune' (GIN index, statewide, 15 rows returned) found zero exact first-name match to Jean Junior -- 15 unrelated Jeune/Louis-Jeune/Petit-Jeune individuals. Per identity_cascade exact-name discipline, none is usable as this buyer's own-name mailing address.",
    },
}

# Live-verified 2026-08-27 (WebSearch + WebFetch this session): correct
# official county property-appraiser domains. NOTE hcpafl.org is Hillsborough,
# NOT Highlands -- caught and corrected before use, see session record.
COUNTY_APPRAISER_URL = {
    "bay": "https://www.baypa.net",
    "clay": "https://www.ccpao.com",
    "escambia": "https://www.escpa.org",
    "highlands": "https://www.hcpao.org",
}


def run_sql(query: str, timeout: int = 60, retries: int = 3):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "skiptrace-20260827-9buyer-batch/1.0"},
        method="POST",
    )
    last_exc = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read())
            if isinstance(body, dict) and "message" in body:
                raise RuntimeError(f"{body['message']} -- query: {query[:200]}")
            return body
        except Exception as e:
            last_exc = e
            import time
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_exc


def s(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def load_subject_properties() -> dict:
    """One row per case_number, from the SSOT (zw_parcels), matched by
    county+pin against the parcel_ids already confirmed live against
    multi_county_auctions."""
    pairs = [
        ("bay", "36582-124-000", "25000033CA"),
        ("clay", "16-05-24-005955-119-00", "2026CA000210"),
        ("escambia", "252S312400070001", "2025 CA 000894"),
        ("highlands", "C-04-34-28-110-2070-0320", "24000615"),
        ("highlands", "C-04-34-28-110-1900-0240", "24000618"),
        ("highlands", "C-04-34-28-100-1660-0310", "24000637"),
        ("highlands", "C-22-37-30-191-1830-0150", "25000543"),
        ("highlands", "C-22-37-30-191-1960-0200", "25000544"),
        ("highlands", "C-22-37-30-080-0690-0160", "25000546"),
    ]
    county_title = {"bay": "Bay", "clay": "Clay", "escambia": "Escambia", "highlands": "Highlands"}
    out = {}
    for county, pin, case_no in pairs:
        pin_clean_target = re.sub(r"[^A-Za-z0-9]", "", pin).upper()
        rows = run_sql(f"""
            select site_addr, site_city, site_zip, val_market, val_assessed, val_land, val_building,
                   year_built, sqft_heated, luse_desc, sale_date, sale_price
            from public.zw_parcels
            where county = '{county_title[county]}'
              and (pin = '{s(pin)[1:-1]}' or pin_clean = '{pin_clean_target}')
            limit 1;
        """)
        out[case_no] = rows[0] if rows else None
    return out


def auction_facts() -> dict:
    cases = [c for b in BUYERS.values() for c in b["case_numbers"]]
    conds = " or ".join(f"case_number = {s(c)}" for c in cases)
    rows = run_sql(f"""
        select county, case_number, sale_type, property_address, parcel_id,
               winning_bidder, sold_amount, auction_date
        from public.multi_county_auctions
        where tier1_buyer_type = 'third_party' and ({conds});
    """)
    return {r["case_number"]: r for r in rows}


def dnc_check(phone: str) -> dict:
    ledger = ff_credit_ledger.spend("tracerfy", 1)
    if not ledger.get("granted"):
        return {"status": "DNC_SCRUB_SKIPPED_DAILY_CAP", "flagged": None, "raw": ledger}
    resp = tracerfy_client.dnc_scrub([phone])
    if resp is None:
        return {"status": "DNC_SCRUB_REQUEST_FAILED", "flagged": None, "raw": None}
    queue_id = resp.get("dnc_queue_id")
    if queue_id is None:
        return {"status": "DNC_SCRUB_UNEXPECTED_RESPONSE_SHAPE", "flagged": None, "raw": resp}
    import time
    for _ in range(6):
        q = tracerfy_client.get_queue_status(queue_id)
        if q and q.get("pending") is False:
            checked, clean = q.get("phones_checked"), q.get("phones_clean")
            flagged = (clean == 0) if checked == 1 and clean is not None else None
            return {"status": "OK", "flagged": flagged, "raw": q}
        time.sleep(20)
    return {"status": "DNC_SCRUB_TIMEOUT", "flagged": None, "raw": None}


def resolve_person(anchor: str, known_addr: dict | None):
    if not known_addr:
        return None, {"phone": None, "email": None, "sources_tried": ["tracerfy_SKIPPED_no_mailing_address_own_name_lookup_exhausted"]}
    ledger = ff_credit_ledger.spend("tracerfy", 1)
    if not ledger.get("granted"):
        return known_addr, {"phone": None, "email": None, "sources_tried": ["tracerfy_SKIPPED_DAILY_CAP"], "ledger": ledger}
    trace = tracerfy_client.trace_lead(anchor, known_addr["addr1"], known_addr["city"], known_addr["state"], known_addr["zip"])
    out = {"phone": None, "email": None, "sources_tried": ["tracerfy_enhanced_trace"], "tracerfy_raw": trace}
    if trace.get("phone"):
        out["phone"] = {"value": trace["phone"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "VERIFIED_PRIMARY"}
    if trace.get("email"):
        out["email"] = {"value": trace["email"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "VERIFIED_PRIMARY"}
    return known_addr, out


def public_record_search(entity_name: str) -> dict | None:
    """Last-resort public-record address search for individuals with no
    zw_parcels own-name history, via Exa (same vendor already used for the
    Sunbiz cascade, no new integration). Never guesses -- exact-name
    discipline applies the same as identity_cascade.normalize()."""
    results = exa_search(f'"{entity_name}" Florida property owner OR obituary OR voter record', num_results=5)
    target = normalize(entity_name)
    for r in results:
        title_norm = normalize(r.get("title", ""))
        if target not in title_norm and normalize(r.get("text", "") or "")[:0]:
            continue
    return None  # honest: no reliable public-record address-resolution source wired for individuals this session


def main():
    report = []
    subjects = load_subject_properties()
    facts = auction_facts()

    for buyer_key, buyer in BUYERS.items():
        anchor = buyer["entities"][0]
        etype = buyer["type"]
        row = {
            "buyer_key": buyer_key, "entity": anchor, "type": etype,
            "case_numbers": buyer["case_numbers"], "county": buyer["county"],
            "mailing_address": None, "mailing_tier": None, "mailing_evidence": buyer["mailing_evidence"],
            "phone": None, "email": None, "phone_tier": None, "email_tier": None,
            "registered_agent": None, "registered_agent_address": None, "principal": None,
            "sunbiz_doc_number": None, "sunbiz_status": None, "sunbiz_source": None,
            "tiers_failed": [],
        }
        print(f"\n{'=' * 70}\n{buyer_key} ({buyer['case_numbers']}, type={etype})")

        if buyer["known_mailing"]:
            row["mailing_address"] = buyer["known_mailing"]
            row["mailing_tier"] = "VERIFIED·CROSS-CHECKED"
        else:
            row["mailing_tier"] = "NOT AVAILABLE"

        principal_name = None
        if etype == "business":
            cascade_hit = resolve_identity(anchor)
            if cascade_hit.get("resolved"):
                principal_name = cascade_hit.get("principal_name")
                row["registered_agent"] = next(
                    (o["name"] for o in cascade_hit.get("officers", []) if "registered agent" in (o.get("position") or "").lower()), None)
                row["registered_agent_address"] = next(
                    (o["address"] for o in cascade_hit.get("officers", []) if "registered agent" in (o.get("position") or "").lower()), None)
                row["principal"] = principal_name
                row["sunbiz_doc_number"] = cascade_hit.get("doc_number")
                row["sunbiz_status"] = cascade_hit.get("status")
                row["sunbiz_source"] = f"{cascade_hit.get('source_step')}:{cascade_hit.get('source_url')}"
                print(f"  Sunbiz cascade: RESOLVED via {cascade_hit.get('source_step')} -> RA={row['registered_agent']!r} principal={principal_name!r}")
                if not row["mailing_address"] and row["registered_agent_address"]:
                    row["mailing_address"] = {"addr1": row["registered_agent_address"], "city": None, "state": "FL", "zip": None}
                    row["mailing_tier"] = "VERIFIED·PRIMARY"
                    row["mailing_evidence"] += f" | Sunbiz registered-agent address ({cascade_hit.get('source_step')}): {row['registered_agent_address']}"
            else:
                print(f"  Sunbiz cascade: UNRESOLVED after {cascade_hit.get('sources_tried')}")
                row["tiers_failed"].append(f"sunbiz_cascade: unresolved after {cascade_hit.get('sources_tried')}")

            city = (row["mailing_address"] or {}).get("city")
            apify_token = os.environ.get("APIFY_API_KEY", "")
            result = contact_resolver.resolve_business_contact(anchor, city=city, state="FL", apify_token=apify_token, principal_name=principal_name)
            print(f"  business contact sources tried: {result['sources_tried']}")
            if result.get("phone"):
                row["phone"] = result["phone"]["value"]
                row["phone_tier"] = "LIKELY·SINGLE SOURCE" if result["phone"]["confidence"] != "high" else "VERIFIED·PRIMARY"
            elif result.get("apify_dropped_no_name_match"):
                d = result["apify_dropped_no_name_match"]
                row["tiers_failed"].append(f"apify_google_maps: listing '{d.get('title')}' found but does NOT name-match '{anchor}' -- discarded")
            else:
                row["tiers_failed"].append("apify_google_maps: no listing found on Google Maps for this business name/city")
            if result.get("email"):
                row["email"] = result["email"]["value"]
                row["email_tier"] = "VERIFIED·PRIMARY" if result["email"]["confidence"] == "high" else "LIKELY·SINGLE SOURCE"
            else:
                reason = "no domain discovered (Apify found no website)"
                if result.get("email_dropped"):
                    reason = f"hunter candidate dropped: {result['email_dropped']['reason']}"
                elif result.get("email_dropped_oss"):
                    reason = f"oss permutation dropped: {result['email_dropped_oss'].get('reason')}"
                row["tiers_failed"].append(f"email: {reason}")

            if principal_name and not row["phone"]:
                p_mailing, p_result = resolve_person(principal_name, row["mailing_address"])
                if p_result.get("phone"):
                    row["phone"] = p_result["phone"]["value"]
                    row["phone_tier"] = p_result["phone"]["confidence"] + "_principal"
                if p_result.get("email") and not row["email"]:
                    row["email"] = p_result["email"]["value"]
                    row["email_tier"] = p_result["email"]["confidence"] + "_principal"
                if not p_result.get("phone") and not p_result.get("email"):
                    row["tiers_failed"].append(f"tracerfy_principal({principal_name}): {p_result.get('sources_tried')}")
        else:  # person
            mailing, result = resolve_person(anchor, buyer["known_mailing"])
            print(f"  person contact sources tried: {result['sources_tried']}")
            if result.get("phone"):
                row["phone"] = result["phone"]["value"]
                row["phone_tier"] = result["phone"]["confidence"]
            else:
                if not buyer["known_mailing"]:
                    row["tiers_failed"].append("tracerfy: SKIPPED, no mailing address on file (own-name lookup exhausted, see mailing_evidence)")
                else:
                    parse_status = (result.get("tracerfy_raw") or {}).get("parse_status")
                    row["tiers_failed"].append(f"tracerfy: {parse_status}")
                endato = contact_resolver.resolve_endato()
                row["tiers_failed"].append(f"endato_enformion: {endato['reason']}")
            if result.get("email"):
                row["email"] = result["email"]["value"]
                row["email_tier"] = result["email"]["confidence"]

        if row["phone"]:
            dnc = dnc_check(row["phone"])
            row["dnc"] = dnc
            print(f"  DNC scrub: {dnc['status']} flagged={dnc['flagged']}")
        else:
            row["dnc"] = None

        found_count = sum(1 for f in (row["mailing_address"], row["phone"], row["email"]) if f)
        row["paid"] = found_count >= 2
        row["properties"] = []
        for case_no in buyer["case_numbers"]:
            fact = facts.get(case_no)
            subj = subjects.get(case_no)
            row["properties"].append({"case_number": case_no, "fact": fact, "subject": subj})

        report.append(row)

    with open("/tmp/ff_9buyer_20260827_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print("FF 9-BUYER 2026-08-27 -- CONTACT RESOLUTION FINAL REPORT")
    print("=" * 70)
    paid_n = 0
    for r in report:
        print(f"{r['buyer_key']}: address={r['mailing_tier']} phone={r['phone']!r}[{r['phone_tier']}] email={r['email']!r}[{r['email_tier']}] PAID={r['paid']}")
        for t in r["tiers_failed"]:
            print(f"    FAILED: {t}")
        if r["paid"]:
            paid_n += 1
    print("-" * 70)
    print(f"TOTALS: {len(report)} buyers | PAID (2+ of address/phone/email): {paid_n}/{len(report)}")
    print("Wrote /tmp/ff_9buyer_20260827_report.json")


if __name__ == "__main__":
    main()
