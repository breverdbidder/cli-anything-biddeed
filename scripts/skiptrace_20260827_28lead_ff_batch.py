#!/usr/bin/env python3
"""P0 final phase (2026-08-27 FF batch, issue #19557): contact enrichment +
DNC on all 28 winnerdata.ff_batch_leads rows for batch_date=2026-08-27.

Method is the exact proven cascade from #19422/#19446/#19452/#19454/#19485/
#19531, reused unmodified via scripts/contact_resolver.py (Apify->Hunter->OSS
for businesses), scripts/identity_cascade.py (Sunbiz cascade for LLC/corp),
scripts/tracerfy_client.py (enhanced trace for persons/principals against a
KNOWN own mailing address only -- never find_owner, never the just-purchased
property address). Own-name mailing-address anchors are discovered live via
public.zw_parcels FTS (same pattern as scripts/ff_nine_portfolio_enrichment.py),
excluding every pin_clean this batch's own 28 rows just purchased.

FL land trusts (named trustee, no Sunbiz registration) are NOT run through
the LLC/corp identity cascade -- marked UNRESOLVED per this issue's explicit
instruction, matching the precedent in
scripts/skiptrace_20260826_16buyer_batch.py.

Writes: winnerdata.ff_batch_leads (phone, email, contact_provider,
contact_verified_at, dnc_state, qa_status, contact_match_status,
identity_type, resolved_principal_name, identity_match_method,
identity_match_confidence, identity_match_rationale, registered_agent_name,
registered_agent_address, evidence_ledger merge). Does NOT touch owner_name/
portfolio/property-value columns -- those are already complete per the issue.

Management API User-Agent note: api.supabase.com Cloudflare-blocks the
default urllib UA (error code 1010) from this sandbox -- same root-cause
class already documented in tracerfy_client.py for tracerfy.com. Fixed here
by setting a non-default UA on every request (curl/8.5.0), verified live
2026-08-28.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import contact_resolver  # noqa: E402
import tracerfy_client  # noqa: E402
import ff_credit_ledger  # noqa: E402
from identity_cascade import resolve_identity, normalize  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_DATE = "2026-08-27"
OUT = f"/tmp/ff20260827/enrichment_report.json"

# entity_key (normalized winning_bidder) -> explicit classification.
# business: LLC/LP/INC/GROUP style entities eligible for the Sunbiz cascade.
# person: individual buyer, eligible for a direct Tracerfy trace against an
#   own-name mailing anchor.
# land_trust: named-trustee FL land trust -- NOT Sunbiz-registered, cannot be
#   pierced without guessing; marked UNRESOLVED per this issue's instruction,
#   no cascade run (mirrors the "trust"-skip rule in the 16-buyer precedent).
TYPE_OVERRIDE = {
    "11513 EQUITY INVESTMENTS LLC": "business",
    "WLA ASSET MGMT LLC": "business",
    "SWP INVESTMENTS LLC": "business",
    "dancing homes": "business",
    "Porte llc": "business",
    "Invictum Investments LLC": "business",
    "Westonport llc": "business",
    "SMART TRUCKING GROUP": "business",
    "SC Pacific Ventures LP": "business",
    "Rapperties LLC": "business",
    "Zachary davis": "person",
    "Pablo A. Ramos": "person",
    "David Radominski": "person",
    "Roberto hernandez": "person",
    "pedro ortiz aguila": "person",
    "j bretnall": "person",
    "Michael Brown": "person",
    "Monah Zahreddine": "person",
    "DILAVER CALA": "person",
    "David A Talmage": "person",
    "ALI ABDELRAOUF SAMARA": "person",
    "JOHN DUDLEY JR., as separate non-homestead property": "person",
}
# Anything not in TYPE_OVERRIDE and containing "trust" (case-insensitive) is
# treated as a land_trust. Everything else falls back to a name-shape guess
# (should not happen for this batch -- all 28 rows are covered above).


def sql(query: str, timeout: int = 90, retries: int = 3):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "curl/8.5.0"},
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


def esc(v):
    return str(v or "").replace("'", "''")


def s(v):
    return "null" if v is None else "'" + esc(v) + "'"


def norm_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", (name or "").upper()).strip()


def classify(winning_bidder: str) -> str:
    if winning_bidder in TYPE_OVERRIDE:
        return TYPE_OVERRIDE[winning_bidder]
    if "trust" in winning_bidder.lower() and "llc" not in winning_bidder.lower():
        return "land_trust"
    return "business" if re.search(r"\b(LLC|INC|CORP|LP|LLP|GROUP)\b", winning_bidder.upper()) else "person"


def load_batch_rows() -> list[dict]:
    return sql(f"""
        select auction_id, county, case_number, winning_bidder, pin_clean, auction_parcel_id, qa_status
        from winnerdata.ff_batch_leads
        where batch_date = date '{BATCH_DATE}'
        order by county, case_number
    """)


def already_enriched_buyers() -> set[str]:
    """Resumability: buyers whose rows already carry a terminal qa_status from
    a prior (possibly killed-mid-run) invocation of this script -- skip them
    so a re-run doesn't re-spend Tracerfy/Hunter/Apify credits.

    UNRESOLVED_NO_AUTHORITATIVE_MATCH is deliberately NOT terminal here: issue
    #19564's entire purpose is re-attempting those buyers now that the
    leads-finder/waterfall-enricher Apify tiers are live, so treating a prior
    UNRESOLVED as "already handled" would skip exactly the rows this run
    exists to retry."""
    rows = sql(f"""
        select distinct winning_bidder from winnerdata.ff_batch_leads
        where batch_date = date '{BATCH_DATE}'
          and qa_status in ('CONTACT_ENRICHED', 'CONTACT_ENRICHED_DNC_FLAGGED',
                             'PARTIAL_ENRICHMENT_IDENTITY_ONLY')
    """)
    return {r["winning_bidder"] for r in rows}


def persist_entry(entry: dict) -> dict:
    """Write one buyer's resolved contact/identity fields to every row for
    that buyer. Called immediately after each buyer resolves (not batched at
    the end) so a killed/timed-out run keeps whatever it already finished."""
    qa = "UNRESOLVED_NO_AUTHORITATIVE_MATCH"
    if entry["type"] == "land_trust":
        qa = "UNRESOLVED_NO_AUTHORITATIVE_MATCH"
    elif entry.get("phone") and entry.get("dnc") and entry["dnc"].get("flagged") is True:
        qa = "CONTACT_ENRICHED_DNC_FLAGGED"
    elif entry.get("phone") or entry.get("email"):
        qa = "CONTACT_ENRICHED"
    elif entry.get("principal") or entry.get("registered_agent") or entry.get("sunbiz_doc_number"):
        qa = "PARTIAL_ENRICHMENT_IDENTITY_ONLY"

    dnc_state = None
    if entry.get("phone"):
        if entry.get("dnc") and entry["dnc"].get("status") == "OK":
            dnc_state = "DNC_FLAGGED" if entry["dnc"].get("flagged") else f"clear_at_lookup_{BATCH_DATE.replace('-', '')}"
        elif entry.get("dnc"):
            dnc_state = entry["dnc"].get("status")

    identity_type_val = {"business": "business", "person": "person", "land_trust": "land_trust_unpierceable"}[entry["type"]]
    phone_tier_tail = (entry.get("phone_tier") or "").split(":")[-1]
    provider = "tracerfy" if phone_tier_tail.startswith("tracerfy") else (
        "apify_google_maps" if phone_tier_tail.startswith("apify") else None)

    ev = json.dumps({
        "contact_enrichment_20260827": {
            "phone": entry.get("phone"), "phone_tier": entry.get("phone_tier"),
            "email": entry.get("email"), "email_tier": entry.get("email_tier"),
            "principal": entry.get("principal"), "registered_agent": entry.get("registered_agent"),
            "registered_agent_address": entry.get("registered_agent_address"),
            "sunbiz_doc_number": entry.get("sunbiz_doc_number"), "sunbiz_status": entry.get("sunbiz_status"),
            "sunbiz_source": entry.get("sunbiz_source"), "mailing_anchor": entry.get("mailing_anchor"),
            "dnc": entry.get("dnc"), "tiers_failed": entry.get("tiers_failed"),
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }
    }, default=str)

    set_clauses = [
        f"qa_status = {s(qa)}",
        f"contact_match_status = {s(entry.get('contact_match_status'))}",
        f"identity_type = {s(identity_type_val)}",
        f"resolved_principal_name = {s(entry.get('principal'))}",
        f"registered_agent_name = {s(entry.get('registered_agent'))}",
        f"registered_agent_address = {s(entry.get('registered_agent_address'))}",
        f"identity_match_method = {s(entry.get('identity_match_method'))}",
        f"identity_match_confidence = {entry['identity_match_confidence'] if entry.get('identity_match_confidence') is not None else 'null'}",
        f"identity_match_rationale = {s(entry.get('identity_match_rationale'))}",
        f"phone = {s(entry.get('phone'))}",
        f"email = {s(entry.get('email'))}",
        f"contact_provider = {s(provider)}",
        f"contact_verified_at = {'now()' if provider else 'null'}",
        f"dnc_state = {s(dnc_state)}",
        "evidence_ledger = evidence_ledger || " + s(ev) + "::jsonb",
    ]
    for auction_id in entry["auction_ids"]:
        sql(f"update winnerdata.ff_batch_leads set {', '.join(set_clauses)} where batch_date = date '{BATCH_DATE}' and auction_id = '{esc(auction_id)}'")
    entry["qa_status"] = qa
    entry["dnc_state"] = dnc_state
    print(f"  PERSISTED {entry['buyer']!r}: qa_status={qa} contact_match_status={entry.get('contact_match_status')} dnc_state={dnc_state} (cases={entry['case_numbers']})")
    return entry


def own_name_anchor(entity_name: str, exclude_pins: set[str]) -> dict | None:
    """FTS scan of public.zw_parcels for a prior own-name mailing address,
    excluding this batch's own just-purchased parcels. Same token-overlap +
    most-common-address method as ff_nine_portfolio_enrichment.py."""
    target_toks = {t for t in re.sub(r"[^A-Za-z ]", " ", entity_name).upper().split() if len(t) >= 2}
    if not target_toks:
        return None
    rows = sql(f"""
        select owner_addr1, owner_city, owner_state, owner_zip, pin_clean, owner_name
        from public.zw_parcels
        where to_tsvector('english', coalesce(owner_name, ''))
              @@ plainto_tsquery('english', '{esc(entity_name)}')
        limit 30
    """)
    candidates = [
        r for r in rows
        if r.get("pin_clean") not in exclude_pins and r.get("owner_addr1")
        and target_toks <= {t for t in re.sub(r"[^A-Za-z ]", " ", r.get("owner_name") or "").upper().split() if len(t) >= 2}
    ]
    if not candidates:
        return None
    key = lambda r: (norm_key(r.get("owner_addr1")), norm_key(r.get("owner_city")), (r.get("owner_state") or "").upper(), norm_key(r.get("owner_zip")))
    best_key, _ = Counter(key(r) for r in candidates).most_common(1)[0]
    best = next(r for r in candidates if key(r) == best_key)
    return {"addr1": best["owner_addr1"], "city": best["owner_city"], "state": best["owner_state"] or "FL", "zip": best["owner_zip"],
            "evidence": f"{len(candidates)} zw_parcels own-name FTS hit(s), most-common address wins"}


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
            checked, clean = q.get("phones_checked"), q.get("phones_clean")
            flagged = (clean == 0) if checked == 1 and clean is not None else None
            return {"status": "OK", "flagged": flagged, "raw": q}
        time.sleep(20)
    return {"status": "DNC_SCRUB_TIMEOUT", "flagged": None, "raw": None}


def resolve_person(anchor_name: str, mailing: dict | None):
    if not mailing:
        return {"phone": None, "email": None, "sources_tried": ["tracerfy_SKIPPED_no_own_name_mailing_address_found"]}
    ledger = ff_credit_ledger.spend("tracerfy", 1)
    if not ledger.get("granted"):
        return {"phone": None, "email": None, "sources_tried": ["tracerfy_SKIPPED_DAILY_CAP"], "ledger": ledger}
    trace = tracerfy_client.trace_lead(anchor_name, mailing["addr1"], mailing["city"], mailing["state"], mailing["zip"])
    out = {"phone": None, "email": None, "sources_tried": ["tracerfy_enhanced_trace"], "tracerfy_raw": trace}
    if trace.get("phone"):
        out["phone"] = {"value": trace["phone"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "high"}
    if trace.get("email"):
        out["email"] = {"value": trace["email"], "tier": 2, "source": "tracerfy_enhanced_trace", "confidence": "high"}
    return out


def main():
    os.makedirs("/tmp/ff20260827", exist_ok=True)
    rows = load_batch_rows()
    if len(rows) != 28:
        print(f"WARNING: expected 28 rows, got {len(rows)}", file=sys.stderr)

    all_pins = {r["pin_clean"] for r in rows if r.get("pin_clean")}

    ALREADY_ENRICHED = {"CONTACT_ENRICHED", "CONTACT_ENRICHED_DNC_FLAGGED"}
    groups: dict[str, list[dict]] = {}
    skipped = 0
    for r in rows:
        if r.get("qa_status") in ALREADY_ENRICHED:
            skipped += 1
            continue
        groups.setdefault(r["winning_bidder"], []).append(r)
    print(f"Skipping {skipped} row(s) already CONTACT_ENRICHED -- re-running {sum(len(v) for v in groups.values())} row(s) across {len(groups)} buyer(s)")

    done = already_enriched_buyers()
    if done:
        print(f"Resuming: {len(done)} buyer(s) already persisted from a prior run, skipping: {sorted(done)}")
        groups = {k: v for k, v in groups.items() if k not in done}

    hunter_acct = contact_resolver.hunter_account()
    hunter_budget = [int(hunter_acct["requests"]["credits"]["remaining"])] if hunter_acct else [0]
    print(f"Hunter.io credits available at start: {hunter_budget[0]}")
    apify_token = os.environ.get("APIFY_API_KEY", "")
    if not apify_token:
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
            apify_token = v.strip('"') if isinstance(v, str) else (v or "")
        except Exception as e:
            print(f"Apify vault fetch failed: {e}")
    print(f"Apify token available: {'yes' if apify_token else 'NO -- Apify tier will be skipped'}")

    report = []
    for buyer_key, buyer_rows in groups.items():
        etype = classify(buyer_key)
        entry = {
            "buyer": buyer_key, "type": etype,
            "case_numbers": [r["case_number"] for r in buyer_rows],
            "auction_ids": [r["auction_id"] for r in buyer_rows],
            "phone": None, "email": None, "phone_tier": None, "email_tier": None,
            "principal": None, "registered_agent": None, "registered_agent_address": None,
            "sunbiz_doc_number": None, "sunbiz_status": None, "sunbiz_source": None,
            "identity_match_method": None, "identity_match_confidence": None, "identity_match_rationale": None,
            "mailing_anchor": None, "dnc": None, "tiers_failed": [],
        }
        print(f"\n{'=' * 70}\n{buyer_key!r} type={etype} cases={entry['case_numbers']}")

        if etype == "land_trust":
            entry["tiers_failed"].append(
                "identity: FL land trust with named trustee -- not Sunbiz-registered, cannot be pierced "
                "without guessing at the trustee's personal identity/authority scope. Marked UNRESOLVED per "
                "explicit instruction, no cascade attempted."
            )
            entry["identity_match_method"] = "NOT_APPLICABLE_LAND_TRUST"
            entry["identity_match_rationale"] = entry["tiers_failed"][0]
            report.append(persist_entry(entry))
            continue

        exclude_pins = all_pins  # never anchor on any parcel this batch's 28 rows just bought

        if etype == "business":
            cascade_hit = resolve_identity(buyer_key)
            if cascade_hit.get("resolved"):
                entry["principal"] = cascade_hit.get("principal_name")
                entry["registered_agent"] = next(
                    (o["name"] for o in cascade_hit.get("officers", []) if "registered agent" in (o.get("position") or "").lower()), None)
                entry["registered_agent_address"] = next(
                    (o["address"] for o in cascade_hit.get("officers", []) if "registered agent" in (o.get("position") or "").lower()), None)
                entry["sunbiz_doc_number"] = cascade_hit.get("doc_number")
                entry["sunbiz_status"] = cascade_hit.get("status")
                entry["sunbiz_source"] = f"{cascade_hit.get('source_step')}:{cascade_hit.get('source_url')}"
                entry["identity_match_method"] = f"sunbiz:{cascade_hit.get('source_step')}"
                entry["identity_match_confidence"] = 0.95
                entry["identity_match_rationale"] = f"Sunbiz record resolved via {cascade_hit.get('source_step')}, doc#{cascade_hit.get('doc_number')}, status={cascade_hit.get('status')}"
                print(f"  Sunbiz cascade: RESOLVED via {cascade_hit.get('source_step')} -> RA={entry['registered_agent']!r} principal={entry['principal']!r}")
            else:
                entry["tiers_failed"].append(f"sunbiz_cascade: unresolved after {cascade_hit.get('sources_tried')}")
                entry["identity_match_confidence"] = 0.0
                entry["identity_match_rationale"] = f"Sunbiz cascade unresolved after {cascade_hit.get('sources_tried')}"
                print(f"  Sunbiz cascade: UNRESOLVED after {cascade_hit.get('sources_tried')}")

            anchor = own_name_anchor(buyer_key, exclude_pins)
            entry["mailing_anchor"] = anchor
            city = (anchor or {}).get("city")
            result = contact_resolver.resolve_business_contact(
                buyer_key, city=city, state="FL", apify_token=apify_token,
                principal_name=entry["principal"], hunter_credits_remaining=hunter_budget,
            )
            print(f"  business contact sources tried: {result['sources_tried']}")
            if result.get("phone"):
                entry["phone"] = result["phone"]["value"]
                entry["phone_tier"] = f"{result['phone']['tier']}:{result['phone']['source']}"
                entry["contact_match_status"] = "business_contact_direct_apify_google_maps"
            elif result.get("apify_dropped_no_name_match"):
                d = result["apify_dropped_no_name_match"]
                entry["tiers_failed"].append(f"apify_google_maps: listing '{d.get('title')}' found but does NOT name-match '{buyer_key}' -- discarded")
            else:
                entry["tiers_failed"].append("apify_google_maps: no listing found on Google Maps for this business name/city")
            if result.get("email"):
                entry["email"] = result["email"]["value"]
                entry["email_tier"] = f"{result['email']['tier']}:{result['email']['source']}"
            else:
                reason = "no domain discovered (Apify found no website)"
                if result.get("email_dropped"):
                    reason = f"hunter candidate dropped: {result['email_dropped']['reason']}"
                elif result.get("email_dropped_oss"):
                    reason = f"oss permutation dropped: {result['email_dropped_oss'].get('reason')}"
                entry["tiers_failed"].append(f"email: {reason}")

            if entry["principal"] and not entry["phone"]:
                p_anchor = anchor or own_name_anchor(entry["principal"], exclude_pins)
                p_result = resolve_person(entry["principal"], p_anchor)
                if p_result.get("phone"):
                    entry["phone"] = p_result["phone"]["value"]
                    entry["phone_tier"] = f"{p_result['phone']['tier']}:{p_result['phone']['source']}_principal"
                    entry["contact_match_status"] = "business_contact_via_principal_tracerfy_trace"
                if p_result.get("email") and not entry["email"]:
                    entry["email"] = p_result["email"]["value"]
                    entry["email_tier"] = f"{p_result['email']['tier']}:{p_result['email']['source']}_principal"
                if not p_result.get("phone") and not p_result.get("email"):
                    entry["tiers_failed"].append(f"tracerfy_principal({entry['principal']}): {p_result.get('sources_tried')}")

        else:  # person
            anchor = own_name_anchor(buyer_key, exclude_pins)
            entry["mailing_anchor"] = anchor
            entry["identity_match_method"] = "own_name_only_no_sunbiz_applicable"
            entry["identity_match_confidence"] = 1.0 if anchor else 0.0
            entry["identity_match_rationale"] = anchor["evidence"] if anchor else "No zw_parcels own-name FTS hit outside this batch's just-purchased parcels"
            p_result = resolve_person(buyer_key, anchor)
            print(f"  person contact sources tried: {p_result['sources_tried']}")
            if p_result.get("phone"):
                entry["phone"] = p_result["phone"]["value"]
                entry["phone_tier"] = f"{p_result['phone']['tier']}:{p_result['phone']['source']}"
                entry["contact_match_status"] = "person_own_name_tracerfy_trace"
            else:
                entry["tiers_failed"].append(f"tracerfy: {p_result.get('sources_tried')}")
            if p_result.get("email"):
                entry["email"] = p_result["email"]["value"]
                entry["email_tier"] = f"{p_result['email']['tier']}:{p_result['email']['source']}"

        if entry["phone"]:
            dnc = dnc_check(entry["phone"])
            entry["dnc"] = dnc
            print(f"  DNC scrub: {dnc['status']} flagged={dnc['flagged']}")

        report.append(persist_entry(entry))

    with open(OUT, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Query live totals (not just this invocation's `report`) so a resumed
    # run's summary reflects the true full-batch state, not only what this
    # process personally touched.
    totals = sql(f"""
        select qa_status, count(*) as n from winnerdata.ff_batch_leads
        where batch_date = date '{BATCH_DATE}' group by qa_status
    """)
    by_status = {t["qa_status"]: int(t["n"]) for t in totals}
    contact_enriched = by_status.get("CONTACT_ENRICHED", 0) + by_status.get("CONTACT_ENRICHED_DNC_FLAGGED", 0)
    unresolved = by_status.get("UNRESOLVED_NO_AUTHORITATIVE_MATCH", 0)
    identity_only = by_status.get("PARTIAL_ENRICHMENT_IDENTITY_ONLY", 0)
    dnc_flagged = by_status.get("CONTACT_ENRICHED_DNC_FLAGGED", 0)
    still_pending = by_status.get("PARTIAL_ENRICHMENT", 0)
    print("\n" + "=" * 70)
    print("FF 28-LEAD 2026-08-27 -- FINAL REPORT (live DB totals)")
    print("=" * 70)
    print(f"this run resolved {len(report)} buyer(s) ({sum(len(e['auction_ids']) for e in report)} rows)")
    print(f"contact-matched (phone or email): {contact_enriched}")
    print(f"identity-only partial: {identity_only}")
    print(f"unresolved: {unresolved}")
    print(f"DNC-flagged (subset of contact-matched): {dnc_flagged}")
    print(f"still not run (qa_status=PARTIAL_ENRICHMENT): {still_pending}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
