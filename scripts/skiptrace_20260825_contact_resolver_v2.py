#!/usr/bin/env python3
"""Contact resolution cascade v2 batch runner (issue #19454) -- re-runs the
24 2026-08-24 third_party buyers (the same batch #19447 delivered 0 phones /
0 emails from, using exactly one vendor) through the newly-wired cascade in
scripts/contact_resolver.py: Apify Google Maps -> Hunter.io -> OSS
permutation+SMTP (business), Tracerfy -> Endato/EnformionGO stub (person).
ZoomInfo is called and honestly reports BLOCKED_NO_CREDENTIAL for every
buyer (see contact_resolver.resolve_zoominfo docstring for the live check).

Reuses BUYERS (case_number -> entities/type/gate/needs_sunbiz) from
scripts/skiptrace_20260825_portfolio_batch.py rather than re-typing it --
that dict is this batch's single source of truth for which case maps to
which buyer entity.

Writes: summitleads.leads.contact_phone / contact_email / consent_certificate
(merges a "contact_resolution_v2" key into the existing jsonb, never
overwrites the improved_gate/skip_trace_status keys phase2 already set).
Join key is signal_events.event_payload->>'case_number' for this batch
(entity_name is not unique-safe across counties -- same lesson phase2
documented).

DNC: every resolved phone is scrubbed via tracerfy_client.dnc_scrub()
before contact_phone is written as deliverable-by-automation; a DNC hit
still gets contact_phone populated (compliance is about *how* you dial, not
whether the number is even known) but outbound_lane is forced to
'compliant_outbound' (never 'instant_automation') and consent_certificate
carries dnc_flag=true, manual_dial_only=true.
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
from identity_cascade import resolve_identity, normalize  # noqa: E402
from skiptrace_20260825_portfolio_batch import BUYERS, VERIFIED_THIS_SESSION  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH = "20260824_third_party"


def run_sql(query: str, timeout: int = 90, retries: int = 3):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "contact-resolver-v2-batch/1.0"},
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


def get_vault_secret(name: str) -> str | None:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(
        f"{url}/rest/v1/rpc/vault_secret",
        data=json.dumps({"p_name": name}).encode(),
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        v = json.loads(resp.read())
    return v.strip('"') if isinstance(v, str) else v


def own_name_lookup(entity_name: str) -> dict | None:
    """fl_parcels row (any county) where own_name exact-matches this buyer --
    their OWN mailing address on file, not the just-purchased property's
    address (see tracerfy_client.py module docstring for why that matters)."""
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
    rows = run_sql(f"""
        select se.signal_id, se.event_payload->>'case_number' as case_number
        from summitleads.signal_events se
        where se.source='biddeed' and se.event_type='auction_close'
          and (se.event_payload->>'batch') = '{BATCH}';
    """)
    return {r["case_number"]: r["signal_id"] for r in rows}


def dnc_check(phone: str) -> dict:
    """First-ever live call to tracerfy_client.dnc_scrub() in this repo.
    Real response schema (verified live 2026-08-25, undocumented in
    tracerfy_client.py's module docstring until now): POST returns
    {dnc_queue_id, status:'pending', phones_to_check, ...}; GET
    dnc/queue/{id} returns {id, pending: bool, phones_checked, phones_clean,
    download_url, clean_download_url} -- no per-phone breakdown in the JSON
    itself (that's only in the CSV at download_url), but for a single-phone
    scrub phones_clean==phones_checked unambiguously means not flagged, and
    phones_clean==0 means flagged. VERIFIED live: a real scrub of
    7867122809 (E&M Plumbing) completed with pending=false almost
    immediately and phones_clean=1/phones_checked=1 (not on the DNC list)."""
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


def main():
    hunter_acct = contact_resolver.hunter_account()
    hunter_budget = [int(hunter_acct["requests"]["credits"]["remaining"])] if hunter_acct else [0]
    print(f"Hunter.io credits available at start: {hunter_budget[0]}")

    apify_token = get_vault_secret("apify_api_token")
    print(f"Apify token retrieved from vault: {'yes' if apify_token else 'NO -- Apify tier will be skipped'}")

    sig_ids = signal_ids_for_batch()
    report = []

    for case_no, buyer in BUYERS.items():
        anchor = buyer["entities"][0]
        gate = buyer["gate"]
        etype = buyer["type"]
        row = {"case_no": case_no, "entity": anchor, "type": etype, "gate": gate,
               "phone": None, "email": None, "phone_tier": None, "email_tier": None,
               "dnc": None, "delivered": False, "tiers_failed": []}

        if gate == "vacant_land":
            row["tiers_failed"].append("SKIPPED: gate=vacant_land, not a Fact Finder lead (established #19447 compliance decision)")
            report.append(row)
            print(f"\n{anchor} ({case_no}): SKIPPED (vacant_land gate)")
            continue

        mailing = own_name_lookup(anchor)
        print(f"\n{anchor} ({case_no}, {etype}, gate={gate}):")
        print(f"  own mailing address on file: {mailing}")

        if etype == "business":
            principal_name = None
            if buyer.get("needs_sunbiz"):
                key = normalize(anchor)
                if key in VERIFIED_THIS_SESSION:
                    cascade_hit = VERIFIED_THIS_SESSION[key]
                else:
                    cascade_hit = resolve_identity(anchor)
                if cascade_hit.get("resolved"):
                    principal_name = cascade_hit.get("principal_name")
                    print(f"  Sunbiz cascade: RESOLVED -> principal {principal_name}")
                else:
                    print(f"  Sunbiz cascade: UNRESOLVED after {cascade_hit.get('sources_tried')}")
                    row["tiers_failed"].append(f"sunbiz_cascade: unresolved after {cascade_hit.get('sources_tried')}")

            city = (mailing or {}).get("own_city")
            result = contact_resolver.resolve_business_contact(
                anchor, city=city, state="FL", apify_token=apify_token or "",
                principal_name=principal_name, hunter_credits_remaining=hunter_budget,
            )
            print(f"  sources tried: {result['sources_tried']}")
            if result.get("phone"):
                row["phone"] = result["phone"]["value"]
                row["phone_tier"] = f"{result['phone']['tier']}:{result['phone']['source']}"
            elif result.get("apify_dropped_no_name_match"):
                d = result["apify_dropped_no_name_match"]
                row["tiers_failed"].append(f"apify_google_maps: listing '{d.get('title')}' found but does NOT name-match '{anchor}' -- discarded, not used")
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

        else:  # person
            result = contact_resolver.resolve_person_contact(
                anchor, mailing_address=(mailing or {}).get("own_addr1"),
                city=(mailing or {}).get("own_city"), state="FL",
                zipcode=(mailing or {}).get("own_zipcd"),
            )
            print(f"  sources tried: {result['sources_tried']}")
            if result.get("phone"):
                row["phone"] = result["phone"]["value"]
                row["phone_tier"] = f"{result['phone']['tier']}:{result['phone']['source']}"
            else:
                if not (mailing or {}).get("own_addr1"):
                    row["tiers_failed"].append("tracerfy: no mailing address on file for this person (own_name has no fl_parcels history)")
                else:
                    parse_status = (result.get("tracerfy_raw") or {}).get("parse_status")
                    row["tiers_failed"].append(f"tracerfy: {parse_status}")
                row["tiers_failed"].append(f"endato_enformion: {result.get('endato_result', {}).get('reason')}")
            if result.get("email"):
                row["email"] = result["email"]["value"]
                row["email_tier"] = f"{result['email']['tier']}:{result['email']['source']}"

        if row["phone"]:
            dnc = dnc_check(row["phone"])
            row["dnc"] = dnc
            print(f"  DNC scrub: {dnc['status']} flagged={dnc['flagged']}")

        row["delivered"] = bool((row["phone"] or row["email"]) and gate == "pass")
        if (row["phone"] or row["email"]) and gate != "pass":
            row["tiers_failed"].append(f"NOT DELIVERED: gate={gate} (improved-status unconfirmed, compliance hold per #19447 precedent)")

        sig_id = sig_ids.get(case_no)
        if sig_id:
            manual_dial_only = bool(row["dnc"] and row["dnc"].get("flagged"))
            cert_patch = {
                "contact_resolution_v2": {
                    "phone": row["phone"], "phone_tier": row["phone_tier"],
                    "email": row["email"], "email_tier": row["email_tier"],
                    "dnc": row["dnc"], "manual_dial_only": manual_dial_only, "tiers_failed": row["tiers_failed"],
                    "delivered": row["delivered"], "resolved_at": datetime.now(timezone.utc).isoformat(),
                }
            }
            set_clauses = ["consent_certificate = consent_certificate || " + s(json.dumps(cert_patch)) + "::jsonb"]
            if row["phone"] and row["delivered"]:
                set_clauses.append(f"contact_phone = {s(row['phone'])}")
                set_clauses.append("outbound_lane = 'compliant_outbound'")
            if row["email"] and row["delivered"]:
                set_clauses.append(f"contact_email = {s(row['email'])}")
            if row["phone"]:
                set_clauses.append("dnc_scrubbed_at = now()")
            run_sql(f"update summitleads.leads set {', '.join(set_clauses)} where signal_id = {s(sig_id)};")
            print(f"  DB updated (signal_id={sig_id}, manual_dial_only={manual_dial_only})")
        else:
            row["tiers_failed"].append("NO_SIGNAL_EVENT_MATCH -- could not write to summitleads.leads")
            print("  WARNING: no matching signal_event for this case_number, DB not updated")

        report.append(row)

    with open("/tmp/contact_resolver_v2_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    phones = [r for r in report if r["phone"]]
    emails = [r for r in report if r["email"]]
    delivered = [r for r in report if r["delivered"]]
    print("\n" + "=" * 70)
    print("CONTACT RESOLUTION V2 -- FINAL REPORT")
    print("=" * 70)
    for r in report:
        print(f"{r['entity']} ({r['case_no']}): phone={r['phone']!r} [{r['phone_tier']}]  "
              f"email={r['email']!r} [{r['email_tier']}]  delivered={r['delivered']}")
        for t in r["tiers_failed"]:
            print(f"    FAILED: {t}")
    print("-" * 70)
    print(f"TOTALS: {len(report)} buyers processed")
    print(f"  phones found: {len(phones)} / {len(report)}")
    print(f"  emails found: {len(emails)} / {len(report)}")
    print(f"  delivered (gate=pass + phone/email + written to leads): {len(delivered)}")
    print(f"  Hunter.io credits remaining after run: {hunter_budget[0]}")
    print("Wrote /tmp/contact_resolver_v2_report.json")


if __name__ == "__main__":
    main()
