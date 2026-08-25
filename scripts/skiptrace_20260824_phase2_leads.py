#!/usr/bin/env python3
"""Phase 2: create summitleads.leads for the 24-row 2026-08-24 third_party
batch, keyed by case_number (unambiguous within this batch -- winning_bidder
names are not unique-safe as a join key across counties).

Classification baked in from live queries already run this session:
  - improved_gate: 'pass' (fl_parcels.no_buldng > 0 on the SUBJECT parcel,
    confirmed live), 'vacant_land' (no_buldng = 0, confirmed live), or
    'unknown' (no fl_parcels row for that parcel/county -- bay county has
    zero fl_parcels rows at all; two miami_dade condo-unit parcels have no
    row either -- a real coverage gap, not assumed vacant).
  - skip_trace: result of a REAL Tracerfy enhanced_trace call this session
    (mailing address sourced from fl_parcels.own_name history -- the buyer's
    OWN prior deed, never the just-purchased property) for the 7 rows where
    an address existed, or an honest ceiling tag for the other 12 gate-pass
    rows (Sunbiz piercing attempted, blocked by Cloudflare + Firecrawl 402
    this session -- see script header of skiptrace_20260824_third_party_batch.py).
"""
import json
import os
import urllib.request

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def run_sql(query, timeout=90):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "skiptrace-aug24-batch-phase2/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    if isinstance(body, dict) and "message" in body:
        raise RuntimeError(body["message"])
    return body


def s(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


# case_number -> classification. entity_type is a simple business/person
# heuristic (matches scripts/summitleads_render_batch.py's existing pattern)
# used only for the render banner, not for gating.
CLASS = {
    # --- confirmed VACANT (no_buldng=0) -- gate-blocked, pipeline-only ---
    "51-2025-CA-002518-CAAX-WS": {"gate": "vacant_land", "entity_type": "business",
        "note": "Fresh Legal Perspective PL as Trustee (689.071 land trust) -- subject parcel confirmed 0 buildings, sold $5,600. Builder's-risk follow-up only, not a Fact Finder lead this batch."},
    "2026110": {"gate": "vacant_land", "entity_type": "person",
        "note": "Mark H. Fink, Trustee of the MHF Retirement Trust -- subject parcel confirmed 0 buildings (tax roll carries no address). Confirms the issue's own flagged hypothesis. Builder's-risk follow-up only."},

    # --- improved-status UNKNOWN (no fl_parcels row for this parcel) -- gate-blocked, pipeline-only ---
    "26000157CA": {"gate": "unknown", "entity_type": "business",
        "note": "Salo Properties, LLC -- bay county has zero fl_parcels rows in this pipeline (confirmed live: co_no=3 returns 0 total rows). Cannot confirm improved vs vacant; not delivered this batch on an unconfirmed gate."},
    "2026-001351-CA-01": {"gate": "unknown", "entity_type": "business",
        "note": "New Med Research, Inc -- no fl_parcels row for parcel 32-2024-034-0060 (likely a condo-unit STRAP suffix not covered). Improved status unconfirmed; not delivered this batch."},
    "2026-003141-CA-01": {"gate": "unknown", "entity_type": "person",
        "note": "YASMANI CHIRINO -- no fl_parcels row for parcel 10-7928-017-0510. Improved status unconfirmed; not delivered this batch."},

    # --- gate PASS (no_buldng > 0), Tracerfy attempted with a real mailing address, real NO_MATCH result ---
    "292025CA010082A001HC": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_HIT",
        "note": "GIANTHONY INVESTMENTS LLC -- traced against 8212 Canyon Creek Way, Tampa FL 33647 (buyer's own fl_parcels history). Tracerfy enhanced trace: NO_MATCH."},
    "2025-005539-CA-01": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_HIT",
        "note": "BROWARD LAND MARK -- traced against 8510 SW 47 St, Miami FL (zip not on file in fl_parcels). Tracerfy enhanced trace: NO_MATCH."},
    "2025-019697-CA-01": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_HIT",
        "note": "Nasinnya LLC -- traced against 20851 Johnson St Ste 113, Pembroke Pines FL 33029. Tracerfy enhanced trace: NO_MATCH."},
    "2025-019702-CA-01": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_HIT",
        "note": "P&W Homes LLC, Trustee of the 25-19702 land trust -- entity parsed from the 689.071 boilerplate; traced against 1430 S Dixie Hwy #306, Coral Gables FL 33146 (P&W Homes LLC's own fl_parcels history). Tracerfy enhanced trace: NO_MATCH."},
    "2025-019889-CA-01": {"gate": "pass", "entity_type": "person", "trace": "TRACED_NO_HIT",
        "note": "LEINIER CASTILLO -- traced against 763 W 33 St, Hialeah FL (zip not on file). Tracerfy enhanced trace: NO_MATCH."},
    "51-2025-CA-003759-CAAX-WS": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_HIT",
        "note": "Harmony Holdings Group Inc -- traced against 710 1st Ave SW, Largo FL 33770. Tracerfy enhanced trace: NO_MATCH."},
    "51-2025-CA-004040-CAAX-WS": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_HIT",
        "note": "Streamline Homes Inc. & DSD Consulting Inc. (joint buyer) -- traced Streamline Homes Inc against 1603 Nodding Thistle Dr, New Port Richey FL 34655 (its own fl_parcels history). Tracerfy enhanced trace: NO_MATCH."},

    # --- gate PASS, no fl_parcels mailing-address history, Sunbiz piercing attempted and blocked this session ---
    "2022-024528-CA-01": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "E&M Plumbing of Miami Inc -- no fl_parcels prior-deed history. Sunbiz principal-resolution attempted (search.sunbiz.org) -- blocked by Cloudflare bot-challenge (HTTP 403); Firecrawl fallback returned HTTP 402 insufficient credits. No individual name on record this session."},
    "2024-018502-CA-01": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "LY AUCTION PROPERTIES INVESTORS, CORP -- no fl_parcels prior-deed history. Sunbiz principal-resolution blocked (Cloudflare + Firecrawl 402, same as above). No individual name on record this session."},
    "2025-009775-CA-01": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "LDC WORLDWIDE CORPORATION LLC -- no fl_parcels prior-deed history. Sunbiz principal-resolution blocked (Cloudflare + Firecrawl 402). No individual name on record this session."},
    "2026-002345-CA-01": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "JDCS INVESTMENTS LLC -- no fl_parcels prior-deed history. Sunbiz principal-resolution blocked (Cloudflare + Firecrawl 402). No individual name on record this session."},
    "502022CA002491XXXXMB": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "OUTSTANDING CONSTRUCTION INC -- no fl_parcels prior-deed history. Sunbiz principal-resolution blocked (Cloudflare + Firecrawl 402). No individual name on record this session."},
    "502024CA007475XXXAMB": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "ZANO INVESTMENTS LLC -- fl_parcels wildcard search's only match ('CRUZ MANZANO INVESTMENTS LLC') is a substring coincidence, not this buyer -- discarded rather than traced against the wrong entity's address. Sunbiz principal-resolution blocked (Cloudflare + Firecrawl 402). No individual name on record this session."},
    "502025CA004424XXXAMB": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "770 PRO INC -- no fl_parcels prior-deed history. Sunbiz principal-resolution blocked (Cloudflare + Firecrawl 402). No individual name on record this session."},
    "2026113": {"gate": "pass", "entity_type": "business", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "Denlin Properties LLC & Keith Fenstemacher (joint buyer) -- neither the LLC nor Keith Fenstemacher individually has fl_parcels prior-deed history. Sunbiz principal-resolution for Denlin Properties LLC blocked (Cloudflare + Firecrawl 402). No individual name on record this session."},

    # --- gate PASS, individuals genuinely no fl_parcels history (terminal, not a Sunbiz case) ---
    "2024-008301-CA-01": {"gate": "pass", "entity_type": "person", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "ALAIN FAJARDO GONZALEZ -- no fl_parcels prior-deed history under this name. Individual, not an entity -- no Sunbiz applicable."},
    "2026-004941-CA-01": {"gate": "pass", "entity_type": "person", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "Ariadna guerra -- no fl_parcels prior-deed history under this name. Individual, not an entity -- no Sunbiz applicable."},
    "502025CA011714XXXAMB": {"gate": "pass", "entity_type": "person", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "Pavel Zoloto -- no fl_parcels prior-deed history under this name. Individual, not an entity -- no Sunbiz applicable."},
    "2026 CA 000425 NC": {"gate": "pass", "entity_type": "person", "trace": "TRACED_NO_MAILING_ADDRESS",
        "note": "Slobodan Kitanovski as Trustee of the Serenity 401k plan -- named natural person is the trustee; no fl_parcels prior-deed history under his name. No Sunbiz applicable (not a corporate entity)."},
}


def main():
    org = run_sql("select org_id from summitleads.organizations where name='Protection Partners';")[0]["org_id"]

    rows = run_sql(f"""
        select se.signal_id, se.county, se.parcel_id, se.entity_name, se.occurred_at,
               se.event_payload->>'case_number' as case_number
        from summitleads.signal_events se
        where se.source='biddeed' and se.event_type='auction_close'
          and (se.event_payload->>'batch') = '20260824_third_party';
    """)
    print(f"{len(rows)} signal_events found for this batch.")

    inserted = skipped_dup = missing_class = 0
    for r in rows:
        cls = CLASS.get(r["case_number"])
        if not cls:
            print(f"  NO CLASSIFICATION for case {r['case_number']} ({r['entity_name']!r}) -- skipping, not silently guessing.")
            missing_class += 1
            continue

        gate = cls["gate"]
        entity_type = cls["entity_type"]
        cert = {"entity_type": entity_type, "improved_gate": gate, "gate_note": cls["note"], "batch": "20260824_third_party"}
        if gate == "pass":
            cert["skip_trace_status"] = cls["trace"]
        else:
            cert["skip_trace_status"] = "NOT_ATTEMPTED_GATE_BLOCKED"
            cert["compliance_flag"] = "GATE_BLOCKED_" + gate.upper()

        existing = run_sql(f"select lead_id from summitleads.leads where signal_id = {s(r['signal_id'])};")
        if existing:
            skipped_dup += 1
            continue

        run_sql(f"""
            insert into summitleads.leads (
              org_id, signal_id, product_line, temperature, outbound_lane,
              contact_name, contact_phone, contact_email, entity_name, parcel_id,
              closing_date, consent_status, consent_certificate, dnc_scrubbed_at,
              acquisition_cost_cents, ops_cost_cents
            ) values (
              {s(org)}, {s(r['signal_id'])}, 'dwelling_landlord', 'hot', 'compliant_outbound',
              {s(r['entity_name'])}, null, null, {s(r['entity_name'])}, {s(r['parcel_id'])},
              {s(r['occurred_at'][:10])}, 'none', {s(json.dumps(cert))}::jsonb, null,
              0, {150 if gate == 'pass' and cls.get('trace') else 0}
            );
        """)
        inserted += 1
        print(f"  inserted lead: {r['entity_name']} (case {r['case_number']}, gate={gate})")

    print(f"\nPhase 2 done: {inserted} leads inserted, {skipped_dup} already existed, {missing_class} missing classification.")


if __name__ == "__main__":
    main()
