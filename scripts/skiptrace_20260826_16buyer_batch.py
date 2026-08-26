#!/usr/bin/env python3
"""Contact resolution batch for the 16-property / 15-buyer 2026-08-25 confirmed-
improved list (P0 issue, 2026-08-26). Exact method from #19422/#19446/#19452/
#19454 -- reuses scripts/contact_resolver.py (Apify->Hunter->OSS cascade for
businesses, Tracerfy for persons), scripts/identity_cascade.py (Sunbiz cascade
for LLC/corp buyers), scripts/tracerfy_client.py (enhanced trace + DNC scrub).
No new resolution logic is introduced here -- only the BUYERS map is new.

signal_events/leads rows for these 18 auctions were created by running
scripts/winnerdata_pipeline.py's SPRINT1 (signal sync) + SPRINT2 (lead
creation) SQL directly (idempotent, NOT EXISTS-guarded) ahead of this script --
same mechanism the daily GHA batch uses, not a bespoke insert.

Writes: winnerdata.leads.contact_phone / contact_email / consent_certificate
(merges a "contact_resolution_20260826" key into the existing jsonb).
DNC: every resolved phone is scrubbed via tracerfy_client.dnc_scrub() before
being treated as deliverable-by-automation (same rule as #19454).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import contact_resolver  # noqa: E402
import tracerfy_client  # noqa: E402
import ff_credit_ledger  # noqa: E402
from identity_cascade import resolve_identity, normalize  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH = "20260825_p0_16buyer"

# buyer_key -> anchor entity name (for own-name lookup / Sunbiz / Tracerfy),
# type, needs_sunbiz, case_numbers this buyer holds this batch, and any
# mailing address already given verbatim in the raw winning_bidder string
# (Avante/Port Richey only -- everyone else needs the own-name lookup).
BUYERS = {
    "DANCING HOMES": {
        "entities": ["dancing homes"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["26000009CAAXMX", "2025 CA 001586"],
    },
    "LAXMI LAND INVESTMENT LLC": {
        "entities": ["Laxmi land investment llc"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["2025CA003110A000BA"],
    },
    "J & R PROPERTIES OF BRANDON INC": {
        "entities": ["J & R Properties of Brandon Inc."], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["292016CA008986A001HC"],
    },
    "CHRISTENSON LLC": {
        "entities": ["CHRISTENSON LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["2025CA000651000000", "2023CA000440000000"],
    },
    "LTD FAMILY TRUST LLC": {
        "entities": ["LTD Family Trust LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["51-2025-CA-003165-CAAX-ES", "51-2025-CA-002603-CAAX-WS"],
    },
    "KIRCHNER LLC": {
        "entities": ["Kirchner LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["26-0215"],
    },
    "DAVID P HILL TRUSTEE": {
        "entities": ["David P Hill"], "type": "person", "needs_sunbiz": False,
        "case_numbers": ["2026 10959 CIDL"],
    },
    "GREENBACK ASSETS CORP": {
        "entities": ["Greenback Assets Corp"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["51-2023-CA-003698-CAAX-WS"],
    },
    "ALA HOMES LLC": {
        "entities": ["ALA Homes LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["26-0165"],
    },
    "ROSZKOWSKI & MINICO LLC": {
        "entities": ["ROSZKOWSKI & MINICO LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["2025 CA 000118"],
    },
    "AVANTE HOLDINGS NPR LLC / PORT RICHEY 26 TRUST": {
        "entities": ["Avante Holdings NPR LLC", "Port Richey 26 Trust"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["51-2025-CC-004945-CCAX-ES"],
        "known_mailing": {
            "Avante Holdings NPR LLC": {"addr1": "4604 49th St N #167", "city": "St Petersburg", "state": "FL", "zip": "33709"},
            "Port Richey 26 Trust": {"addr1": "25737 Crippen Drive", "city": "Land O Lakes", "state": "FL", "zip": "34639"},
        },
    },
    "JEAN ROSALVA": {
        "entities": ["Jean rosalva"], "type": "person", "needs_sunbiz": False,
        "case_numbers": ["2024CA003685000000"],
    },
    "ANTHONY C SCOTT INVESTMENTS LLC": {
        "entities": ["Anthony C Scott Investments LLC"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["522025CA005628XXCICI"],
    },
    "PLUMMER INTERNATIONAL INVESTMENTS LLC": {
        "entities": ["plummer international investments llc"], "type": "business", "needs_sunbiz": True,
        "case_numbers": ["2026-5146TD"],
    },
    "ROBERT NASH SCHUSTER": {
        "entities": ["Robert Nash Schuster"], "type": "person", "needs_sunbiz": False,
        "case_numbers": ["16-2025-CC-011360-AXXX-MA"],
    },
}


def run_sql(query: str, timeout: int = 90, retries: int = 3):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "skiptrace-20260826-16buyer-batch/1.0"},
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
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise last_exc


def s(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def own_name_lookup(entity_name: str) -> dict | None:
    esc = entity_name.replace("'", "''")
    rows = run_sql(f"""
        select own_addr1, own_city, own_state, own_zipcd
        from public.fl_parcels
        where upper(regexp_replace(own_name, '[.,]', '', 'g')) = upper(regexp_replace('{esc}', '[.,]', '', 'g'))
          and own_addr1 is not null
        limit 1;
    """)
    return rows[0] if rows else None


def signal_ids_for_batch() -> dict:
    all_cases = [c for b in BUYERS.values() for c in b["case_numbers"]]
    conds = " or ".join(f"(se.event_payload->>'case_number') = {s(c)}" for c in all_cases)
    rows = run_sql(f"""
        select se.signal_id, se.event_payload->>'case_number' as case_number
        from winnerdata.signal_events se
        where se.source='biddeed' and se.event_type='auction_close'
          and ({conds});
    """)
    return {r["case_number"]: r["signal_id"] for r in rows}


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
    for _ in range(6):
        q = tracerfy_client.get_queue_status(queue_id)
        if q and q.get("pending") is False:
            checked = q.get("phones_checked")
            clean = q.get("phones_clean")
            flagged = None
            if checked == 1 and clean is not None:
                flagged = (clean == 0)
            return {"status": "OK", "flagged": flagged, "raw": q}
        time.sleep(20)
    return {"status": "DNC_SCRUB_TIMEOUT", "flagged": None, "raw": None}


def resolve_person(anchor: str, known_addr: dict | None):
    """Tracerfy trace against own-name mailing address, ledger-gated."""
    mailing = known_addr or own_name_lookup(anchor)
    addr1 = mailing.get("own_addr1") if mailing and "own_addr1" in mailing else (mailing or {}).get("addr1")
    city = mailing.get("own_city") if mailing and "own_city" in mailing else (mailing or {}).get("city")
    state = mailing.get("own_state") if mailing and "own_state" in mailing else (mailing or {}).get("state", "FL")
    zipc = mailing.get("own_zipcd") if mailing and "own_zipcd" in mailing else (mailing or {}).get("zip")
    if not addr1:
        return mailing, {"phone": None, "email": None, "sources_tried": ["tracerfy_SKIPPED_no_mailing_address"]}
    ledger = ff_credit_ledger.spend("tracerfy", 1)
    if not ledger.get("granted"):
        return mailing, {"phone": None, "email": None, "sources_tried": ["tracerfy_SKIPPED_DAILY_CAP"], "ledger": ledger}
    trace = tracerfy_client.trace_lead(anchor, addr1, city, state, zipc)
    out = {"phone": None, "email": None, "sources_tried": ["tracerfy_enhanced_trace"], "tracerfy_raw": trace}
    if trace.get("phone"):
        out["phone"] = {"value": trace["phone"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "high"}
    if trace.get("email"):
        out["email"] = {"value": trace["email"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "high"}
    return mailing, out


def main():
    hunter_acct = contact_resolver.hunter_account()
    hunter_budget = [int(hunter_acct["requests"]["credits"]["remaining"])] if hunter_acct else [0]
    print(f"Hunter.io credits available at start: {hunter_budget[0]}")

    apify_token = None
    try:
        url = os.environ["SUPABASE_URL"].rstrip("/")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        req = urllib.request.Request(
            f"{url}/rest/v1/rpc/vault_secret",
            data=json.dumps({"p_name": "apify_api_token"}).encode(),
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            v = json.loads(resp.read())
        apify_token = v.strip('"') if isinstance(v, str) else v
    except Exception as e:
        print(f"Apify vault fetch failed: {e}")
    print(f"Apify token retrieved from vault: {'yes' if apify_token else 'NO -- Apify tier will be skipped'}")

    sig_ids = signal_ids_for_batch()
    report = []

    for buyer_key, buyer in BUYERS.items():
        anchor = buyer["entities"][0]
        etype = buyer["type"]
        row = {
            "buyer_key": buyer_key, "entity": anchor, "type": etype,
            "case_numbers": buyer["case_numbers"],
            "phone": None, "email": None, "phone_tier": None, "email_tier": None,
            "dnc": None, "registered_agent": None, "registered_agent_address": None,
            "principal": None, "related_companies": [], "website": None, "website_tier": None,
            "delivered": False, "tiers_failed": [],
        }
        print(f"\n{'=' * 70}\n{buyer_key} ({buyer['case_numbers']}, type={etype})")

        mailing = own_name_lookup(anchor)
        print(f"  own-name mailing address on file: {mailing}")

        principal_name = None
        if etype == "business":
            for entity in buyer["entities"]:
                key = normalize(entity)
                known = (buyer.get("known_mailing") or {}).get(entity)
                if "trust" in entity.lower() and "llc" not in entity.lower():
                    # FL land trusts are not Sunbiz-registered corporate entities;
                    # do not run the LLC/corp identity cascade against a trust name
                    row["tiers_failed"].append(f"sunbiz_cascade SKIPPED for '{entity}': FL land trust, not a Sunbiz-registered entity")
                    if known:
                        row["related_companies"].append({
                            "name": entity, "mailing_address": f"{known['addr1']}, {known['city']}, {known['state']} {known['zip']}",
                            "source": "auction_record_verbatim",
                        })
                    continue
                cascade_hit = resolve_identity(entity)
                if cascade_hit.get("resolved"):
                    principal_name = principal_name or cascade_hit.get("principal_name")
                    row["registered_agent"] = next(
                        (o["name"] for o in cascade_hit.get("officers", []) if "registered agent" in (o.get("position") or "").lower()),
                        None,
                    )
                    row["registered_agent_address"] = next(
                        (o["address"] for o in cascade_hit.get("officers", []) if "registered agent" in (o.get("position") or "").lower()),
                        None,
                    )
                    row["principal"] = cascade_hit.get("principal_name")
                    row["sunbiz_doc_number"] = cascade_hit.get("doc_number")
                    row["sunbiz_status"] = cascade_hit.get("status")
                    row["sunbiz_source"] = f"{cascade_hit.get('source_step')}:{cascade_hit.get('source_url')}"
                    print(f"  Sunbiz cascade ({entity}): RESOLVED via {cascade_hit.get('source_step')} -> RA={row['registered_agent']!r} principal={principal_name!r}")
                else:
                    print(f"  Sunbiz cascade ({entity}): UNRESOLVED after {cascade_hit.get('sources_tried')}")
                    row["tiers_failed"].append(f"sunbiz_cascade({entity}): unresolved after {cascade_hit.get('sources_tried')}")

            city = (mailing or {}).get("own_city") or ((buyer.get("known_mailing") or {}).get(anchor, {}) or {}).get("city")
            result = contact_resolver.resolve_business_contact(
                anchor, city=city, state="FL", apify_token=apify_token or "",
                principal_name=principal_name, hunter_credits_remaining=hunter_budget,
            )
            print(f"  business contact sources tried: {result['sources_tried']}")
            if result.get("phone"):
                row["phone"] = result["phone"]["value"]
                row["phone_tier"] = f"{result['phone']['tier']}:{result['phone']['source']}"
            elif result.get("apify_dropped_no_name_match"):
                d = result["apify_dropped_no_name_match"]
                row["tiers_failed"].append(f"apify_google_maps: listing '{d.get('title')}' found but does NOT name-match '{anchor}' -- discarded")
            else:
                row["tiers_failed"].append("apify_google_maps: no listing found on Google Maps for this business name/city")
            if result.get("email"):
                row["email"] = result["email"]["value"]
                row["email_tier"] = f"{result['email']['tier']}:{result['email']['source']}"
            else:
                reason = "no domain discovered (Apify found no website)"
                if result.get("email_dropped"):
                    reason = f"hunter candidate dropped: {result['email_dropped']['reason']}"
                elif result.get("email_dropped_oss"):
                    reason = f"oss permutation dropped: {result['email_dropped_oss'].get('reason')}"
                row["tiers_failed"].append(f"email: {reason}")

            zi = contact_resolver.resolve_zoominfo()
            row["tiers_failed"].append(f"zoominfo: {zi['reason']}")

            # website/domain: independent Apify Google Maps lookup (name_match()-gated,
            # same rule contact_resolver.resolve_business_contact applies internally) --
            # resolve_business_contact() doesn't expose the raw website field, so this is
            # a second, cheap ($0.011) Apify call rather than reaching into its internals.
            if apify_token:
                gmaps = contact_resolver.apify_google_maps(anchor, city, "FL", apify_token)
                if gmaps and gmaps.get("website"):
                    if gmaps.get("name_matched"):
                        row["website"] = gmaps["website"]
                        row["website_tier"] = "VERIFIED_PRIMARY: Apify Google Maps listing name-matched to entity"
                    else:
                        row["website"] = gmaps["website"]
                        row["website_tier"] = f"UNCONFIRMED_CLAIM: Google Maps listing '{gmaps.get('title')}' does not name-match '{anchor}'"

            # Tracerfy find_owner on the resolved principal, per DoD step 3
            if principal_name:
                p_mailing, p_result = resolve_person(principal_name, None)
                if p_result.get("phone") and not row["phone"]:
                    row["phone"] = p_result["phone"]["value"]
                    row["phone_tier"] = f"{p_result['phone']['tier']}:{p_result['phone']['source']}_principal"
                if p_result.get("email") and not row["email"]:
                    row["email"] = p_result["email"]["value"]
                    row["email_tier"] = f"{p_result['email']['tier']}:{p_result['email']['source']}_principal"
                if not p_result.get("phone") and not p_result.get("email"):
                    row["tiers_failed"].append(f"tracerfy_principal({principal_name}): {p_result.get('sources_tried')}")

        else:  # person
            known = (buyer.get("known_mailing") or {}).get(anchor)
            mailing, result = resolve_person(anchor, known)
            print(f"  person contact sources tried: {result['sources_tried']}")
            if result.get("phone"):
                row["phone"] = result["phone"]["value"]
                row["phone_tier"] = f"{result['phone']['tier']}:{result['phone']['source']}"
            else:
                if not (mailing or {}).get("own_addr1") and not (mailing or {}).get("addr1"):
                    row["tiers_failed"].append("tracerfy: no mailing address on file for this person (own_name has no fl_parcels history)")
                else:
                    parse_status = (result.get("tracerfy_raw") or {}).get("parse_status")
                    row["tiers_failed"].append(f"tracerfy: {parse_status}")
                endato = contact_resolver.resolve_endato()
                row["tiers_failed"].append(f"endato_enformion: {endato['reason']}")
            if result.get("email"):
                row["email"] = result["email"]["value"]
                row["email_tier"] = f"{result['email']['tier']}:{result['email']['source']}"

        if row["phone"]:
            dnc = dnc_check(row["phone"])
            row["dnc"] = dnc
            print(f"  DNC scrub: {dnc['status']} flagged={dnc['flagged']}")

        row["delivered"] = bool(row["phone"] and row["email"])
        row["paid"] = row["delivered"]

        for case_no in buyer["case_numbers"]:
            sig_id = sig_ids.get(case_no)
            if not sig_id:
                row["tiers_failed"].append(f"NO_SIGNAL_EVENT_MATCH for case {case_no}")
                print(f"  WARNING: no matching signal_event for case_number={case_no}")
                continue
            manual_dial_only = bool(row["dnc"] and row["dnc"].get("flagged"))
            cert_patch = {
                "contact_resolution_20260826": {
                    "phone": row["phone"], "phone_tier": row["phone_tier"],
                    "email": row["email"], "email_tier": row["email_tier"],
                    "dnc": row["dnc"], "manual_dial_only": manual_dial_only,
                    "registered_agent": row["registered_agent"], "registered_agent_address": row["registered_agent_address"],
                    "principal": row["principal"], "website": row["website"], "website_tier": row["website_tier"],
                    "tiers_failed": row["tiers_failed"], "paid": row["paid"],
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                }
            }
            set_clauses = ["consent_certificate = consent_certificate || " + s(json.dumps(cert_patch)) + "::jsonb"]
            if row["phone"]:
                set_clauses.append(f"contact_phone = {s(row['phone'])}")
                set_clauses.append("dnc_scrubbed_at = now()")
                set_clauses.append("outbound_lane = 'compliant_outbound'")
            if row["email"]:
                set_clauses.append(f"contact_email = {s(row['email'])}")
            run_sql(f"update winnerdata.leads set {', '.join(set_clauses)} where signal_id = {s(sig_id)};")
            print(f"  DB updated (case={case_no}, signal_id={sig_id})")

        report.append(row)

    with open("/tmp/contact_resolver_20260826_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    phones = [r for r in report if r["phone"]]
    emails = [r for r in report if r["email"]]
    paid = [r for r in report if r["paid"]]
    print("\n" + "=" * 70)
    print("CONTACT RESOLUTION 2026-08-26 -- FINAL REPORT")
    print("=" * 70)
    for r in report:
        print(f"{r['buyer_key']}: phone={r['phone']!r} [{r['phone_tier']}]  "
              f"email={r['email']!r} [{r['email_tier']}]  PAID={r['paid']}")
        for t in r["tiers_failed"]:
            print(f"    FAILED: {t}")
    print("-" * 70)
    print(f"TOTALS: {len(report)} buyers processed")
    print(f"  phones found: {len(phones)} / {len(report)}")
    print(f"  emails found: {len(emails)} / {len(report)}")
    print(f"  PAID (phone AND email both resolved): {len(paid)} / {len(report)}")
    print(f"  Hunter.io credits remaining after run: {hunter_budget[0]}")
    print("Wrote /tmp/contact_resolver_20260826_report.json")


if __name__ == "__main__":
    main()
