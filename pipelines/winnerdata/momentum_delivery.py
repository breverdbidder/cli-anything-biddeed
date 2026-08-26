#!/usr/bin/env python3
"""Winner Data FF -> Momentum AMS (NowCerts) delivery bridge.

Takes a filled Winner Data FF (WINNERDATA_QUOTE_REQUEST_TEMPLATE.json,
auction-investor edition) and transforms it into a NowCerts Zapier-API
payload (InsertProspect + SimpleCustomField/Insert + InsertTask), then
delivers it -- idempotently, search-first -- so Momentum Rate/Quotelinq
can prefill a quote from that record with zero re-keying.

Endpoint contracts below are taken verbatim from the public NowCerts API
Postman collection (ReduceMyIns/Nowcerts-API, api version 2.1.5) and cross-
checked against the MIT-licensed ReduceMyIns/n8n-nodes-momentum node --
see docs/winnerdata/NOWCERTS_MCP_AUDIT.md for the sourcing detail.

Runs against the live `winnerdata` schema via the Supabase Management API
SQL endpoint (PostgREST does not expose the winnerdata schema), matching
the pattern established by scripts/winnerdata_pipeline.py.

Two modes:
  fixtures  - pure transform, no network, no DB writes. Reads FF JSON files,
              validates, gates, writes NowCerts-shaped payload JSON to
              docs/winnerdata/payload_fixtures/. Runs with zero credentials.
  deliver   - full pipeline: validate -> gate -> search NowCerts -> insert
              or update prospect -> custom fields -> producer task -> log
              every attempt (delivered/skipped/validation_failed/gate_blocked/
              failed) to winnerdata.lead_activity. Requires
              NOWCERTS_API_USERNAME / NOWCERTS_API_PASSWORD and
              SUPABASE_ACCESS_TOKEN.
"""
import argparse
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
NOWCERTS_BASE_URL = "https://api.nowcerts.com/api"


# ---------------------------------------------------------------------------
# Supabase (winnerdata schema) access
# ---------------------------------------------------------------------------

def run_sql(query):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "winnerdata-momentum-delivery/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    if isinstance(body, dict) and "message" in body:
        raise RuntimeError(body["message"])
    return body


def sql_literal(value):
    """Render a Python value as a Postgres literal for inline SQL."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict) or isinstance(value, list):
        return "'" + json.dumps(value).replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


def log_lead_activity(lead_id, org_id, producer_id, activity_type, payload):
    run_sql(f"""
        insert into winnerdata.lead_activity (lead_id, org_id, producer_id, activity_type, channel, payload, occurred_at)
        values ({sql_literal(lead_id)}, {sql_literal(org_id)}, {sql_literal(producer_id)},
                {sql_literal(activity_type)}, 'momentum_ams', {sql_literal(payload)}, now());
    """)


def get_producer_id(org_id):
    rows = run_sql(f"""
        select rd.producer_id from winnerdata.routing_decisions rd
        join winnerdata.leads l on l.lead_id = rd.lead_id
        where l.org_id = {sql_literal(org_id)}
        order by rd.routed_at desc limit 1;
    """)
    return rows[0]["producer_id"] if rows else None


# ---------------------------------------------------------------------------
# FF validation + delivery gate
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self, ok, errors=None):
        self.ok = ok
        self.errors = errors or []


def validate_ff(ff):
    """Structural validation: reject FFs that cannot be transformed at all."""
    errors = []
    entity_name = (ff.get("applicant") or {}).get("entity_name", {}).get("value")
    if not entity_name:
        errors.append("applicant.entity_name.value is missing/null")
    return ValidationResult(ok=(len(errors) == 0), errors=errors)


class GateResult:
    def __init__(self, eligible, reason=None):
        self.eligible = eligible
        self.reason = reason


def check_delivery_gate(ff):
    """Standing deliverability rule: vacant land and non-Tracerfy-verified
    phones are pipeline-only -- never delivered to Momentum AMS.

    num_buildings == 0 is an FLP-confirmed vacant lot (not the same as
    num_buildings is null, which just means FLP has no row for this parcel
    -- an unknown, not a confirmed vacancy, and is NOT gated).

    contact_phone is sourced exclusively as "SL" in this template (see
    sources_legend: winnerdata.leads / Tracerfy skip-trace data already
    purchased). A non-null value is the only signal available in this
    schema that Tracerfy skip-trace resolved a real number for this lead --
    there is no separate verified-boolean column. See
    docs/winnerdata/FF_TO_MOMENTUM_MAPPING.md for the INFERRED tag on this
    rule.
    """
    num_buildings = (ff.get("property") or {}).get("num_buildings", {}).get("value")
    if num_buildings == 0:
        return GateResult(eligible=False, reason="vacant_land")
    phone = (ff.get("applicant") or {}).get("contact_phone", {}).get("value")
    if not phone:
        return GateResult(eligible=False, reason="non_tracerfy_verified_phone")
    return GateResult(eligible=True)


# ---------------------------------------------------------------------------
# Transform: FF -> NowCerts payload
# ---------------------------------------------------------------------------

# Same heuristic as scripts/winnerdata_render_batch.py's `card()` -- reused
# verbatim so business/person classification agrees with what the producer
# call sheet already shows for the same lead. Known limitation inherited
# from that heuristic: word-boundary matching means e.g. "INCORPORATED"
# (no bare "inc" token) and "TRUSTEE" (no bare "trust" token) don't match --
# flagged as a residual in docs/winnerdata/FF_TO_MOMENTUM_MAPPING.md rather
# than silently diverging from the existing house standard.
_BUSINESS_RE = re.compile(r"\bllc\b|\binc\b|\btrust\b|\bcorp\b|properties|construction", re.IGNORECASE)

_ADDR_RE = re.compile(
    r"^(?P<street>.*?),\s*(?P<city>[^,]+?),?\s*(?P<state>FL)?-?\s*(?P<zip>\d{5})?$",
    re.IGNORECASE,
)


def _is_business(entity_name):
    return bool(_BUSINESS_RE.search(entity_name or ""))


def _split_person_name(entity_name):
    """Best-effort split of a person name into (first, last).

    Handles 'LAST, FIRST' (court-record convention) and 'FIRST LAST'.
    Multi-party leads (e.g. 'A / B') and trustee/IRA phrasing are left as a
    single first_name with last_name blank -- flagged in the mapping doc as
    a known-lossy case, not silently guessed.
    """
    name = entity_name.strip()
    if "," in name:
        left, _, right = name.partition(",")
        left, right = left.strip(), right.strip()
        # 'LAST, FIRST' court-record convention only holds when both sides
        # are short name tokens -- longer trailing text ('..., TRUSTEE OF
        # ZIVKO PSP') is a descriptor, not a first name, so fall back to a
        # single first_name rather than misassigning it as a surname.
        if len(left.split()) <= 3 and len(right.split()) <= 3:
            return right, left
        return name.replace(",", ""), ""
    parts = name.split()
    if len(parts) >= 2:
        return " ".join(parts[:-1]), parts[-1]
    return name, ""


def _parse_property_address(address_str):
    """Split a free-text address string into (street, city, state, zip).

    The FF carries two shapes: 'STREET, CITY, STATE ZIP' (normal parcels)
    and 'CITY, STATE ZIP' with no street segment (vacant-land rows like
    'BUNNELL, FL- 32110', sometimes prefixed '(vacant land) '). Comma count
    disambiguates which shape it is -- returns None for any part that
    can't be confidently parsed rather than misassigning city<->street.
    """
    if not address_str:
        return None, None, None, None
    cleaned = re.sub(r"^\(vacant land\)\s*", "", address_str.strip(), flags=re.IGNORECASE)
    parts = [p.strip() for p in cleaned.split(",")]
    if len(parts) >= 3:
        street, city, state_zip = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        street, city, state_zip = None, parts[0], parts[1]
    else:
        return cleaned or None, None, None, None
    m = re.match(r"^(?P<state>FL)?-?\s*(?P<zip>\d{5})?$", state_zip, re.IGNORECASE)
    state = (m.group("state") if m else None) or "FL"
    zip_code = m.group("zip") if m else None
    return street or None, city or None, state, zip_code


def _val(section, key):
    return (section or {}).get(key, {}).get("value")


def normalize_name(name):
    """Normalization key used for search-first dedupe against Momentum."""
    return re.sub(r"[^A-Z0-9 ]", "", (name or "").upper()).strip()


def build_custom_fields(ff, insured_database_id):
    """Every FF field with no native NowCerts Prospect column becomes a
    SimpleCustomField/Insert entry, so it is visible to the producer
    (and to Quotelinq prefill) without re-keying. See
    docs/winnerdata/FF_TO_MOMENTUM_MAPPING.md for the full table.
    """
    applicant = ff.get("applicant") or {}
    prop = ff.get("property") or {}
    purchase = ff.get("purchase") or {}
    buyer = ff.get("buyer_profile") or {}
    bundle = ff.get("bundle_doctrine") or {}
    compliance = ff.get("compliance") or {}

    fields = {
        "Winner Data Lead ID": ff.get("lead_id"),
        "Winner Data FF ID": ff.get("id"),
        "Property County": _val(prop, "county"),
        "Parcel ID": _val(prop, "parcel_id"),
        "Property Address (Full)": _val(prop, "address"),
        "Year Built": _val(prop, "year_built"),
        "Square Footage": _val(prop, "sqft"),
        "Number of Buildings": _val(prop, "num_buildings"),
        "Construction Class": _val(prop, "construction_class"),
        "DOR Use Code": _val(prop, "dor_use_code"),
        "Zone Code": _val(prop, "zone_code"),
        "Just Value": _val(prop, "just_value"),
        "Improved": _val(prop, "improved"),
        "Occupancy Status": _val(prop, "occupancy_status"),
        "Sale Type": _val(purchase, "sale_type"),
        "Sold Amount": _val(purchase, "sold_amount"),
        "Auction Date": _val(purchase, "auction_date"),
        "Case Number": _val(purchase, "case_number"),
        "Buyer Total Wins": _val(buyer, "total_wins"),
        "Buyer Total Deployed": _val(buyer, "total_deployed"),
        "Buyer Counties Active": _val(buyer, "counties_active"),
        "Is Repeat Investor": _val(buyer, "is_repeat_investor"),
        "Umbrella Quote Requested": bundle.get("umbrella_quote_requested"),
        "Umbrella Quote Reason": bundle.get("umbrella_quote_reason"),
        "Umbrella Limit": bundle.get("umbrella_limit"),
        "Flood If Indicated": bundle.get("flood_if_indicated"),
        "Flood Basis": bundle.get("flood_basis"),
        "Commercial BOP If Applicable": bundle.get("commercial_bop_if_applicable"),
        "Builders Risk If Renovation": bundle.get("builders_risk_if_renovation"),
        "Master Policy Conversation": bundle.get("master_policy_conversation"),
        "Must Quote": ff.get("must_quote"),
        "Readiness Score": ff.get("readiness_score"),
        "Missing Required Fields": ff.get("missing_required_fields"),
        "Product Line": ff.get("product_line"),
        "Consent Status": compliance.get("consent_status"),
        "Compliance Flag": compliance.get("compliance_flag"),
        "DNC Scrubbed": compliance.get("dnc_scrubbed"),
        "Outbound Lane": compliance.get("outbound_lane"),
    }

    entries = []
    for label, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (list, dict)):
            value = json.dumps(value)
        entries.append({
            "text": label,
            "value": str(value),
            "insuredDatabaseId": insured_database_id,
        })
    return entries


def build_payload(ff):
    """Pure transform: FF dict -> {prospect, custom_fields, task, meta}.

    No network, no DB. Safe to call for fixture generation on any
    structurally-valid FF regardless of delivery-gate eligibility.
    """
    entity_name = _val(ff.get("applicant"), "entity_name")
    is_business = _is_business(entity_name)
    first_name, last_name = ("", "") if is_business else _split_person_name(entity_name)

    street, city, state, zip_code = _parse_property_address(_val(ff.get("property"), "address"))
    if not city:
        # fall back to FF's own county-derived city when address parsing
        # can't find one (e.g. vacant-land "(vacant land) CITY, FL ZIP" rows)
        city = None

    prospect = {
        "first_name": first_name,
        "last_name": last_name,
        "commercial_name": entity_name if is_business else "",
        "address_line_1": street or "",
        "city": city or "",
        "state": state or "FL",
        "zip_code": zip_code or "",
        "email": _val(ff.get("applicant"), "contact_email") or "",
        "phone_number": _val(ff.get("applicant"), "contact_phone") or "",
        "active": True,
        "referral_source": f"Winner Data: {ff.get('product_line') or 'unclassified'}",
        "type": 2 if is_business else 1,
        "insuredType": 2 if is_business else 1,
    }

    task = {
        "title": f"Quote-ready Winner Data lead: {entity_name}",
        "description": ff.get("producer_message_draft") or "",
        "status": "New",
        "priority": "high" if (ff.get("readiness_score") or 0) >= 70 else "medium",
        "completion": 0,
    }

    return {
        "dedupe_key": normalize_name(entity_name),
        "prospect": prospect,
        "custom_fields": build_custom_fields(ff, insured_database_id=None),
        "task": task,
        "meta": {
            "ff_id": ff.get("id"),
            "lead_id": ff.get("lead_id"),
            "org_id": ff.get("org_id"),
            "is_business": is_business,
        },
    }


# ---------------------------------------------------------------------------
# NowCerts client (thin, credential-gated)
# ---------------------------------------------------------------------------

class NowCertsClient:
    """Thin client for the endpoints this bridge needs. Endpoint shapes are
    taken from the public NowCerts Postman collection (see audit doc) --
    not from the empty ReduceMyIns/nowcerts-mcp-server-v3 repo, which has
    no code to source a contract from.
    """

    def __init__(self, base_url=NOWCERTS_BASE_URL, username=None, password=None):
        self.base_url = base_url
        self.username = username or os.environ.get("NOWCERTS_API_USERNAME")
        self.password = password or os.environ.get("NOWCERTS_API_PASSWORD")
        self._token = None

    def _request(self, method, path, body=None, form=False, auth=True):
        url = f"{self.base_url}{path}"
        headers = {"User-Agent": "winnerdata-momentum-delivery/1.0"}
        data = None
        if body is not None:
            if form:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                data = body.encode()
            else:
                headers["Content-Type"] = "application/json"
                data = json.dumps(body).encode()
        if auth:
            headers["Authorization"] = f"Bearer {self.token()}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"NowCerts {method} {path} failed: {e.code} {e.read()[:500]}") from e
        return json.loads(raw) if raw else {}

    def token(self):
        if self._token:
            return self._token
        if not self.username or not self.password:
            raise RuntimeError("NOWCERTS_API_USERNAME / NOWCERTS_API_PASSWORD not set")
        form = f"grant_type=password&username={self.username}&password={self.password}&client_id=ngAuthApp"
        resp = self._request("POST", "/token", body=form, form=True, auth=False)
        if "access_token" not in resp:
            raise RuntimeError("NowCerts token response missing access_token")
        self._token = resp["access_token"]
        return self._token

    def find_prospect(self, phone=None, email=None):
        """Search-first dedupe. Filters CustomersList (the general
        insured/prospect listing endpoint -- there is no prospect-only
        list in the public collection) by phone or email.
        """
        clauses = []
        if phone:
            clauses.append(f"phone eq '{phone}'")
        if email:
            clauses.append(f"email eq '{email}'")
        if not clauses:
            return []
        filt = " or ".join(clauses)
        return self._request("GET", f"/CustomersList?$filter=({filt})&$count=true&$top=5")

    def insert_prospect(self, prospect):
        return self._request("POST", "/Zapier/InsertProspect", body=prospect)

    def insert_custom_field(self, field):
        return self._request("POST", "/SimpleCustomField/Insert", body=field)

    def insert_task(self, task):
        return self._request("POST", "/Zapier/InsertTask", body=task)


# ---------------------------------------------------------------------------
# Delivery orchestration
# ---------------------------------------------------------------------------

def deliver(ff, client, log_fn=log_lead_activity):
    """Full validate -> gate -> search -> insert/update -> log pipeline.

    Returns a dict {status, reason?, nowcerts_id?} and always calls log_fn
    exactly once (except for structural validation failures with no
    lead_id/org_id to log against, which are logged with null producer_id).
    """
    lead_id = ff.get("lead_id")
    org_id = ff.get("org_id")

    validation = validate_ff(ff)
    if not validation.ok:
        payload = {"ff_id": ff.get("id"), "errors": validation.errors}
        log_fn(lead_id, org_id, None, "momentum_validation_failed", payload)
        return {"status": "validation_failed", "errors": validation.errors}

    gate = check_delivery_gate(ff)
    if not gate.eligible:
        producer_id = get_producer_id(org_id) if org_id else None
        payload = {"ff_id": ff.get("id"), "reason": gate.reason}
        log_fn(lead_id, org_id, producer_id, "momentum_gate_blocked", payload)
        return {"status": "gate_blocked", "reason": gate.reason}

    payload_bundle = build_payload(ff)
    producer_id = get_producer_id(org_id)

    try:
        existing = client.find_prospect(
            phone=payload_bundle["prospect"]["phone_number"] or None,
            email=payload_bundle["prospect"]["email"] or None,
        )
    except Exception as e:
        log_fn(lead_id, org_id, producer_id, "momentum_delivery_failed",
               {"ff_id": ff.get("id"), "stage": "search", "error": str(e)})
        return {"status": "failed", "stage": "search", "error": str(e)}

    dedupe_key = payload_bundle["dedupe_key"]
    match = next(
        (r for r in existing
         if normalize_name(r.get("commercialName") or f"{r.get('firstName','')} {r.get('lastName','')}") == dedupe_key),
        None,
    )

    if match:
        insured_id = match.get("databaseId") or match.get("id")
        log_fn(lead_id, org_id, producer_id, "momentum_skipped_duplicate",
               {"ff_id": ff.get("id"), "nowcerts_id": insured_id})
        return {"status": "skipped_duplicate", "nowcerts_id": insured_id}

    try:
        prospect_resp = client.insert_prospect(payload_bundle["prospect"])
        insured_id = prospect_resp.get("databaseId") or prospect_resp.get("id")

        for field in build_custom_fields(ff, insured_database_id=insured_id):
            client.insert_custom_field(field)

        task_body = dict(payload_bundle["task"])
        task_body["insured_database_id"] = insured_id
        client.insert_task(task_body)
    except Exception as e:
        log_fn(lead_id, org_id, producer_id, "momentum_delivery_failed",
               {"ff_id": ff.get("id"), "stage": "insert", "error": str(e)})
        return {"status": "failed", "stage": "insert", "error": str(e)}

    log_fn(lead_id, org_id, producer_id, "momentum_delivered",
           {"ff_id": ff.get("id"), "nowcerts_id": insured_id})
    return {"status": "delivered", "nowcerts_id": insured_id}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_ff_files(intake_glob):
    paths = sorted(glob.glob(intake_glob))
    out = []
    for p in paths:
        with open(p) as f:
            out.append((p, json.load(f)))
    return out


def cmd_fixtures(args):
    """Transform every FF under --intake into a NowCerts payload fixture
    under --out. No network, no DB. Malformed FFs (missing insured name)
    produce zero artifacts, per the delivery bridge's negative-test
    contract.
    """
    os.makedirs(args.out, exist_ok=True)
    written, rejected, gated = 0, 0, 0
    for path, ff in _load_ff_files(args.intake):
        validation = validate_ff(ff)
        if not validation.ok:
            rejected += 1
            print(f"REJECTED {path}: {validation.errors}")
            continue
        gate = check_delivery_gate(ff)
        bundle = build_payload(ff)
        bundle["_delivery_gate"] = {"eligible": gate.eligible, "reason": gate.reason}
        if not gate.eligible:
            gated += 1
        out_name = os.path.splitext(os.path.basename(path))[0] + ".nowcerts.json"
        with open(os.path.join(args.out, out_name), "w") as f:
            json.dump(bundle, f, indent=2, sort_keys=True)
        written += 1
    print(f"Fixtures: {written} written ({gated} gate-blocked, still transformed), {rejected} rejected (no artifact).")
    return 0


def cmd_deliver(args):
    if not os.environ.get("NOWCERTS_API_USERNAME") or not os.environ.get("NOWCERTS_API_PASSWORD"):
        print("BLOCKED: NOWCERTS_API_USERNAME / NOWCERTS_API_PASSWORD not set -- "
              "cannot run live delivery. Run `fixtures` instead for the credential-free path.")
        return 2
    client = NowCertsClient()
    results = {"delivered": 0, "skipped_duplicate": 0, "gate_blocked": 0,
               "validation_failed": 0, "failed": 0}
    for path, ff in _load_ff_files(args.intake):
        result = deliver(ff, client)
        results[result["status"]] = results.get(result["status"], 0) + 1
        print(path, "->", result["status"])
    print(json.dumps(results, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fixtures = sub.add_parser("fixtures", help="dry-run transform, no network/DB")
    p_fixtures.add_argument("--intake", default="winnerdata/intake/*.json")
    p_fixtures.add_argument("--out", default="docs/winnerdata/payload_fixtures")
    p_fixtures.set_defaults(func=cmd_fixtures)

    p_deliver = sub.add_parser("deliver", help="live delivery to Momentum AMS")
    p_deliver.add_argument("--intake", default="winnerdata/intake/*.json")
    p_deliver.set_defaults(func=cmd_deliver)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
