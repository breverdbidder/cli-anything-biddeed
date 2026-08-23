#!/usr/bin/env python3
"""SummitLeads Sprint 7 — SLQ intake JSON generator.

SSOT ONLY, NO RE-PURCHASE: reads summitleads.leads / v_producer_intake /
auction_buyer_profiles (data already paid for), never calls Tracerfy or any
paid vendor. One SLQ-<year>-<entity>-<seq>.json per delivered lead, written
to summitleads/intake/, per SUMMITLEADS_QUOTE_REQUEST_TEMPLATE.json. Links
each file via a summitleads.lead_activity row (activity_type=slq_generated)
so re-runs are idempotent (skip leads that already have one).

Missing SSOT fields are left null + listed in missing_required_fields —
never guessed, per Honesty Protocol.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, timezone, datetime

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
INTAKE_DIR = "summitleads/intake"

# INFERRED, not a verified FEMA flood-zone lookup -- zone_code is unpopulated
# in fl_parcels for these parcels. Florida counties touching the Atlantic or
# Gulf coastline. Flag flood_basis accordingly whenever this list is used.
COASTAL_COUNTIES = {
    "broward", "palm_beach", "miami_dade", "lee", "collier", "manatee",
    "sarasota", "pinellas", "hillsborough", "pasco", "citrus", "levy",
    "dixie", "wakulla", "franklin", "gulf", "bay", "walton", "okaloosa",
    "escambia", "santa_rosa", "flagler", "volusia", "st_johns", "nassau",
    "duval", "indian_river", "st_lucie", "martin", "charlotte", "monroe",
    "taylor", "jefferson",
}

REQUIRED_FIELDS = [
    "entity_name", "contact_name", "contact_phone", "address", "county",
    "year_built", "sqft", "num_buildings", "construction_class",
    "dor_use_code", "sold_amount", "auction_date",
]


def run_sql(query):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "summitleads-slq-generator/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())
    if isinstance(body, dict) and "message" in body:
        raise RuntimeError(body["message"])
    return body


FETCH_QUERY = """
select
  l.lead_id, l.org_id, l.entity_name, l.contact_name, l.contact_phone, l.contact_email,
  l.parcel_id, l.product_line, l.consent_status, l.consent_certificate->>'compliance_flag' as compliance_flag,
  vpi.property_address, vpi.county, vpi.sale_type, vpi.sold_amount, vpi.auction_date, vpi.case_number,
  vpi.act_yr_blt, vpi.tot_lvg_ar, vpi.no_buldng, vpi.const_clas, vpi.dor_uc, vpi.zone_code,
  vpi.just_value, vpi.buyer_mailing_addr,
  bp.total_wins, bp.total_deployed, bp.counties_active
from summitleads.leads l
join summitleads.lead_activity la on la.lead_id = l.lead_id and la.activity_type = 'delivered'
left join summitleads.v_producer_intake vpi on vpi.lead_id = l.lead_id
left join auction_buyer_profiles bp
  on regexp_replace(lower(bp.buyer_name_normalized), '[^a-z0-9 ]', '', 'g')
   = regexp_replace(lower(l.entity_name), '[^a-z0-9 ]', '', 'g')
where not exists (
  select 1 from summitleads.lead_activity done
  where done.lead_id = l.lead_id and done.activity_type = 'slq_generated'
)
order by l.entity_name;
"""


def slug(entity_name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", entity_name).strip("_").upper()
    return s[:40] if s else "UNKNOWN"


def num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def build_slq(row, seq_for_entity, batch_year):
    entity = row["entity_name"]
    num_buildings = row.get("no_buldng")
    total_wins = row.get("total_wins")
    total_deployed = num(row.get("total_deployed"))
    dor_uc = row.get("dor_uc")

    improved = None
    if num_buildings is not None:
        improved = num_buildings > 0

    is_repeat = total_wins is not None and total_wins >= 2
    umbrella = bool(is_repeat)
    umbrella_reason = (
        f"total_wins={total_wins} (repeat investor)" if is_repeat else None
    )
    umbrella_limit = None
    if umbrella:
        umbrella_limit = 2_000_000 if (total_deployed or 0) > 250_000 else 1_000_000

    county = (row.get("county") or "").lower().replace(" ", "_")
    flood = county in COASTAL_COUNTIES if county else None
    flood_basis = "INFERRED_coastal_county_heuristic" if county else None

    commercial_bop = None
    if dor_uc is not None or num_buildings is not None:
        commercial_bop = bool(
            (dor_uc and str(dor_uc) not in ("001", "002", "004", "008"))
            or (num_buildings is not None and num_buildings > 2)
        )

    master_policy = bool(total_wins is not None and total_wins >= 5)

    field_values = {
        "entity_name": entity,
        "contact_name": row.get("contact_name"),
        "contact_phone": row.get("contact_phone"),
        "address": row.get("property_address"),
        "county": row.get("county"),
        "year_built": row.get("act_yr_blt"),
        "sqft": row.get("tot_lvg_ar"),
        "num_buildings": num_buildings,
        "construction_class": row.get("const_clas"),
        "dor_use_code": dor_uc,
        "sold_amount": row.get("sold_amount"),
        "auction_date": row.get("auction_date"),
    }
    missing = [k for k, v in field_values.items() if v is None]
    readiness = round(100.0 * (len(REQUIRED_FIELDS) - len(missing)) / len(REQUIRED_FIELDS), 1)

    must_quote = [row.get("product_line") or "dwelling_landlord"]
    if umbrella:
        must_quote.append("umbrella_if_multi_property")
    if flood:
        must_quote.append("flood_if_indicated")

    opener_bits = []
    if row.get("county") and row.get("sale_type") and row.get("auction_date"):
        opener_bits.append(
            f"saw you picked up {row.get('property_address') or 'a property'} at the "
            f"{row['county'].title()} County {row['sale_type']} auction on {row['auction_date']}"
        )
        if row.get("sold_amount"):
            opener_bits[-1] += f" for ${row['sold_amount']}"
    if field_values["year_built"] or field_values["sqft"]:
        opener_bits.append(
            f"we already pulled the property card (built {field_values['year_built'] or '?'}, "
            f"{field_values['sqft'] or '?'} sqft) so we can have a landlord/dwelling quote ready today"
        )
    if umbrella:
        opener_bits.append(
            f"with {total_wins} recent auction wins on file you'd likely qualify for an umbrella "
            f"policy across the portfolio too"
        )
    opener = f"Hi {row.get('contact_name') or entity}, " + "; ".join(opener_bits) + "." if opener_bits else None

    return {
        "schema_version": "1.0",
        "id": f"SLQ-{batch_year}-{slug(entity)}-{seq_for_entity:03d}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lead_id": row["lead_id"],
        "org_id": row["org_id"],
        "applicant": {
            "entity_name": {"value": entity, "source": "SL"},
            "contact_name": {"value": row.get("contact_name"), "source": "SL"},
            "contact_phone": {"value": row.get("contact_phone"), "source": "SL"},
            "contact_email": {"value": row.get("contact_email"), "source": "SL"},
            "mailing_address": {"value": row.get("buyer_mailing_addr"), "source": "FLP"},
        },
        "property": {
            "address": {"value": row.get("property_address"), "source": "MCA"},
            "county": {"value": row.get("county"), "source": "MCA"},
            "parcel_id": {"value": row.get("parcel_id"), "source": "SL"},
            "year_built": {"value": field_values["year_built"], "source": "FLP"},
            "sqft": {"value": field_values["sqft"], "source": "FLP"},
            "num_buildings": {"value": num_buildings, "source": "FLP"},
            "construction_class": {"value": row.get("const_clas"), "source": "FLP"},
            "dor_use_code": {"value": dor_uc, "source": "FLP"},
            "zone_code": {"value": row.get("zone_code"), "source": "FLP"},
            "just_value": {"value": num(row.get("just_value")), "source": "FLP"},
            "improved": {"value": improved, "source": "FLP"},
            "occupancy_status": {"value": "unknown", "source": "PC"},
        },
        "purchase": {
            "sale_type": {"value": row.get("sale_type"), "source": "MCA"},
            "sold_amount": {"value": num(row.get("sold_amount")), "source": "MCA"},
            "auction_date": {"value": row.get("auction_date"), "source": "MCA"},
            "case_number": {"value": row.get("case_number"), "source": "MCA"},
        },
        "buyer_profile": {
            "total_wins": {"value": total_wins, "source": "ABP"},
            "total_deployed": {"value": total_deployed, "source": "ABP"},
            "counties_active": {"value": row.get("counties_active"), "source": "ABP"},
            "is_repeat_investor": {"value": is_repeat, "source": "ABP"},
        },
        "bundle_doctrine": {
            "umbrella_quote_requested": umbrella,
            "umbrella_quote_reason": umbrella_reason,
            "umbrella_limit": umbrella_limit,
            "flood_if_indicated": flood,
            "flood_basis": flood_basis,
            "commercial_bop_if_applicable": commercial_bop,
            "builders_risk_if_renovation": None,
            "auto_bundle": "ask_on_call_only",
            "master_policy_conversation": master_policy,
        },
        "must_quote": must_quote,
        "readiness_score": readiness,
        "missing_required_fields": missing,
        "compliance": {
            "outbound_lane": "compliant_outbound",
            "consent_status": row.get("consent_status"),
            "compliance_flag": row.get("compliance_flag"),
            "dnc_scrubbed": False,
        },
        "producer_message_draft": opener,
        "product_line": row.get("product_line"),
    }


def main():
    rows = run_sql(FETCH_QUERY)
    if not rows:
        print("SLQ generator: no undelivered-without-SLQ leads found — nothing to generate.")
        return
    os.makedirs(INTAKE_DIR, exist_ok=True)
    batch_year = date.today().year
    seq_by_entity = {}
    written = []
    for row in rows:
        seq_by_entity[row["entity_name"]] = seq_by_entity.get(row["entity_name"], 0) + 1
        slq = build_slq(row, seq_by_entity[row["entity_name"]], batch_year)
        path = os.path.join(INTAKE_DIR, f"{slq['id']}.json")
        with open(path, "w") as f:
            json.dump(slq, f, indent=2, default=str)
        written.append((row["lead_id"], slq["id"]))
        print(f"  wrote {path} (readiness={slq['readiness_score']}% umbrella={slq['bundle_doctrine']['umbrella_quote_requested']})")

    lead_ids = ",".join(f"'{lid}'" for lid, _ in written)
    run_sql(f"""
        insert into summitleads.lead_activity (lead_id, org_id, producer_id, activity_type, channel, payload, occurred_at)
        select l.lead_id, l.org_id, rd.producer_id, 'slq_generated', 'intake_json',
          jsonb_build_object('slq_id', v.slq_id), now()
        from summitleads.leads l
        join summitleads.routing_decisions rd on rd.lead_id = l.lead_id
        join (values {",".join(f"('{lid}','{sid}')" for lid, sid in written)}) as v(lead_id, slq_id)
          on v.lead_id::uuid = l.lead_id
        where not exists (
          select 1 from summitleads.lead_activity done
          where done.lead_id = l.lead_id and done.activity_type = 'slq_generated'
        );
    """)
    print(f"SLQ generator: {len(written)} intake file(s) written, lead_activity linked.")


if __name__ == "__main__":
    sys.exit(main())
