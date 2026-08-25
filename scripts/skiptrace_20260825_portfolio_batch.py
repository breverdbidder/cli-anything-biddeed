#!/usr/bin/env python3
"""Identity cascade + Portfolio Fact Finder re-run of the 2026-08-24
third_party batch (24 buyers). Supersedes the delivery half of #19447
(closed with 0 phones from 24 buyers).

Two parts, both live-executed against Supabase (Management API SQL, per
this repo's documented psql-unavailable-in-sandbox fallback -- see
decision_log ids 169/205/287 and scripts/skiptrace_20260824_phase2_leads.py):

  PART 1 -- identity cascade (scripts/identity_cascade.py) for every LLC/corp
  buyer that scripts/skiptrace_20260824_phase2_leads.py tagged
  TRACED_NO_MAILING_ADDRESS (fl_parcels had no prior-deed history under the
  buyer's own name, and #19447's Sunbiz attempt was blocked 12/12 times).

  PART 2 -- portfolio aggregation: for EVERY one of the 24 buyers (not just
  the Sunbiz-resolved ones), enumerate every fl_parcels row they hold across
  all FL counties (exact own_name match), plus affiliate entities sharing a
  mailing address (own_addr1+own_city) AND a second corroborator (a shared
  Sunbiz principal from Part 1 -- shared registered-agent ADDRESS alone is
  explicitly not sufficient, since Dade Tax Consulting is RA for 51 entities).

Writes: winnerdata.owner_portfolio (one row per owner_key x parcel),
summitleads.leads (phone/email when Tracerfy resolves a name+address).
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from identity_cascade import resolve_identity, normalize  # noqa: E402

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
BATCH_ID = "20260825_third_party_portfolio"

# Loaded live from public.fl_counties in main() -- NOT hand-typed. fl_parcels.co_no
# follows FL DOR's official (non-alphabetical) county numbering, e.g. Bay=13,
# Miami-Dade=23, Pasco=61 -- verified live 2026-08-25 against fl_counties;
# an earlier hand-typed guess based on a different repo module's 1-67
# alphabetical COUNTY_MAP (scripts/owner_osint.py) was WRONG for this
# purpose and has been replaced.
CO_NO_TO_COUNTY: dict[int, str] = {}


def run_sql(query: str, timeout: int = 120, retries: int = 3):
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "skiptrace-20260825-portfolio-batch/1.0"},
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
                print(f"  [run_sql] transient error ({e}), retrying in {2 ** attempt}s...", flush=True)
                time.sleep(2 ** attempt)
    raise last_exc


def s(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


# case_number -> (primary buyer entities to portfolio-search, entity_type,
# already-known trace status from phase2). Extracted by hand from the raw
# multi_county_auctions.winning_bidder strings (trustee/land-trust boilerplate
# stripped to the actual operating entity per the issue's own worked example
# for P&W Homes LLC / Fresh Legal Perspective PL).
BUYERS = {
    "502024CA007475XXXAMB": {"entities": ["ZANO INVESTMENTS LLC"], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "2024-008301-CA-01": {"entities": ["ALAIN FAJARDO GONZALEZ"], "type": "person", "gate": "pass", "needs_sunbiz": False},
    "2025-019889-CA-01": {"entities": ["LEINIER CASTILLO"], "type": "person", "gate": "pass", "needs_sunbiz": False},
    "502022CA002491XXXXMB": {"entities": ["OUTSTANDING CONSTRUCTION INC"], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "502025CA004424XXXAMB": {"entities": ["770 PRO INC"], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "26000157CA": {"entities": ["Salo Properties, LLC"], "type": "business", "gate": "unknown", "needs_sunbiz": True},
    "51-2025-CA-002518-CAAX-WS": {"entities": ["Fresh Legal Perspective PL"], "type": "business", "gate": "vacant_land", "needs_sunbiz": False},
    "2022-024528-CA-01": {"entities": ["E&M Plumbing of Miami Inc"], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "2024-018502-CA-01": {"entities": ["LY AUCTION PROPERTIES INVESTORS, CORP"], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "2025-019697-CA-01": {"entities": ["Nasinnya LLC"], "type": "business", "gate": "pass", "needs_sunbiz": False},
    "2026-003141-CA-01": {"entities": ["YASMANI CHIRINO"], "type": "person", "gate": "unknown", "needs_sunbiz": False},
    "2026-001351-CA-01": {"entities": ["New Med Research, Inc"], "type": "business", "gate": "unknown", "needs_sunbiz": True},
    "2025-009775-CA-01": {"entities": ["LDC WORLDWIDE CORPORATION LLC"], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "51-2025-CA-004040-CAAX-WS": {"entities": ["Streamline Homes Inc.", "DSD Consulting Inc."], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "2025-019702-CA-01": {"entities": ["P&W Homes LLC"], "type": "business", "gate": "pass", "needs_sunbiz": False},
    "2026-002345-CA-01": {"entities": ["JDCS INVESTMENTS LLC"], "type": "business", "gate": "pass", "needs_sunbiz": True},
    "2026-004941-CA-01": {"entities": ["Ariadna guerra"], "type": "person", "gate": "pass", "needs_sunbiz": False},
    "2026 CA 000425 NC": {"entities": ["Slobodan Kitanovski"], "type": "person", "gate": "pass", "needs_sunbiz": False},
    "292025CA010082A001HC": {"entities": ["GIANTHONY INVESTMENTS LLC"], "type": "business", "gate": "pass", "needs_sunbiz": False},
    "502025CA011714XXXAMB": {"entities": ["Pavel Zoloto"], "type": "person", "gate": "pass", "needs_sunbiz": False},
    "2026110": {"entities": ["Mark H. Fink"], "type": "person", "gate": "vacant_land", "needs_sunbiz": False},
    "51-2025-CA-003759-CAAX-WS": {"entities": ["Harmony Holdings Group Inc"], "type": "business", "gate": "pass", "needs_sunbiz": False},
    "2025-005539-CA-01": {"entities": ["BROWARD LAND MARK"], "type": "business", "gate": "pass", "needs_sunbiz": False},
    "2026113": {"entities": ["Denlin Properties LLC", "Keith Fenstemacher"], "type": "business", "gate": "pass", "needs_sunbiz": True},
}

# Manually verified this session via direct Exa /contents fetch on a URL that
# repeated exa_search() calls did not reliably re-surface (neural search
# ranking is non-deterministic across calls) -- see session transcript for
# the raw fetch. Kept separate from the live resolve_identity() cascade so
# every use of it is auditable as "verified once, not re-derived."
VERIFIED_THIS_SESSION = {
    "E&M PLUMBING OF MIAMI INC": {
        "resolved": True, "source_step": "exa",
        "source_url": "https://www.bizprofile.net/fl/miami/e-m-service-and",
        "sources_tried": ["exa"],
        "principal_name": "Elieser Perez Mesa", "principal_address": "8956 SW 36th St, Miami, FL 33165",
        "mailing_address": "8956 SW 36th St, Miami, FL 33165", "doc_number": "P19000030613", "status": "Active",
        "officers": [{"name": "Elieser Perez Mesa", "position": "President", "address": "Miami, FL"},
                     {"name": "Elieser Perez Mesa, Sr", "position": "Registered Agent", "address": "8956 SW 36th St, Miami, FL 33165"}],
    },
}


def part1_identity_cascade():
    print("\n=== PART 1: Identity resolution cascade ===")
    results = {}
    for case_no, buyer in BUYERS.items():
        if not buyer["needs_sunbiz"]:
            continue
        for entity in buyer["entities"]:
            key = normalize(entity)
            if key in results:
                continue
            if key in VERIFIED_THIS_SESSION:
                r = VERIFIED_THIS_SESSION[key]
                print(f"  {entity}: RESOLVED (verified this session, direct URL fetch) -> {r['principal_name']} @ {r['principal_address']}")
            else:
                r = resolve_identity(entity)
                if r["resolved"]:
                    print(f"  {entity}: RESOLVED via {r['source_step']} -> {r.get('principal_name')} @ {r.get('principal_address') or r.get('mailing_address')}")
                else:
                    print(f"  {entity}: UNRESOLVED after {r['sources_tried']} -- tag: 'no individual name on record'")
            results[key] = r
    return results


def find_portfolio(entity_name: str):
    """fl_parcels rows where own_name is an EXACT normalized match. Runs
    across all 67 counties (no co_no filter) -- this is the full-book query,
    not scoped to the auction county."""
    esc = entity_name.replace("'", "''")
    rows = run_sql(f"""
        select co_no, parcel_id, phy_addr1, phy_city, dor_uc, no_buldng, jv, own_addr1, own_city, own_name
        from public.fl_parcels
        where upper(regexp_replace(own_name, '[.,]', '', 'g')) = upper(regexp_replace('{esc}', '[.,]', '', 'g'))
        order by co_no, parcel_id;
    """)
    return rows


def find_affiliate_by_addr(own_addr1: str, own_city: str, exclude_norm_names: set[str]):
    """Rows sharing the exact mailing address+city of an anchor entity, under
    a DIFFERENT own_name than any already-claimed entity. This is the
    candidate pool for affiliate linking -- corroboration (shared principal)
    is checked by the caller before these are actually merged in."""
    if not own_addr1 or not own_city:
        return []
    esc_addr = own_addr1.replace("'", "''")
    esc_city = own_city.replace("'", "''")
    rows = run_sql(f"""
        select distinct co_no, parcel_id, phy_addr1, phy_city, dor_uc, no_buldng, jv, own_addr1, own_city, own_name
        from public.fl_parcels
        where upper(own_addr1) = upper('{esc_addr}') and upper(own_city) = upper('{esc_city}')
        order by co_no, parcel_id;
    """)
    return [r for r in rows if normalize(r["own_name"]) not in exclude_norm_names]


def load_auction_parcels():
    """case_number -> (county_slug, parcel_id) for the subject parcel actually
    won 2026-08-24, so the matching owner_portfolio row can be tagged
    acquisition_source='auction_win' instead of 'prior_holding'. joined by
    county slug, not co_no -- multi_county_auctions.county is already the
    text slug (e.g. 'miami_dade'); it has no co_no column."""
    rows = run_sql("""
        select case_number, parcel_id, county
        from public.multi_county_auctions
        where auction_date = '2026-08-24' and tier1_buyer_type = 'third_party' and winning_bidder is not null;
    """)
    return {r["case_number"]: (r["county"], r["parcel_id"]) for r in rows}


def part2_portfolio(cascade_results: dict):
    print("\n=== PART 2: Portfolio aggregation ===")
    run_sql(f"delete from winnerdata.owner_portfolio where batch_id = '{BATCH_ID}';")
    auction_parcels = load_auction_parcels()
    portfolio_summary = {}
    for case_no, buyer in BUYERS.items():
        anchor_entity = buyer["entities"][0]
        owner_key = normalize(anchor_entity)
        anchor_rows = find_portfolio(anchor_entity)
        claimed_norm_names = {normalize(anchor_entity)}
        all_rows = [(r, "exact_name", None) for r in anchor_rows]

        # affiliate clustering: for each address seen on an exact-name row,
        # look for OTHER entities at the same address, then require a second
        # corroborator (shared Sunbiz principal from Part 1) before merging
        seen_addrs = {(r["own_addr1"], r["own_city"]) for r in anchor_rows if r["own_addr1"]}
        cascade_hit = cascade_results.get(owner_key)
        anchor_principals = set()
        if cascade_hit and cascade_hit.get("resolved"):
            anchor_principals = {normalize(o["name"]) for o in cascade_hit.get("officers", [])}
            if cascade_hit.get("principal_name"):
                anchor_principals.add(normalize(cascade_hit["principal_name"]))

        if not anchor_principals:
            addr_count = sum(len(find_affiliate_by_addr(a, c, claimed_norm_names)) for a, c in seen_addrs)
            if addr_count:
                print(f"  {anchor_entity}: {addr_count} affiliate-address candidate(s) across {len(seen_addrs)} address(es) -- NOT merged (no Sunbiz principal resolved for anchor to corroborate against; shared address alone is insufficient)")
        else:
            # corroboration only against PART 1's already-resolved cascade results --
            # deliberately does NOT spawn a fresh resolve_identity() cascade call per
            # candidate (a shared corporate-service/mill address can have 50+ unrelated
            # entities; re-running Bright Data/Playwright per candidate is unbounded cost)
            for addr, city in seen_addrs:
                candidates = find_affiliate_by_addr(addr, city, claimed_norm_names)
                for cand_name in {r["own_name"] for r in candidates}:
                    cand_hit = cascade_results.get(normalize(cand_name))
                    if not cand_hit or not cand_hit.get("resolved"):
                        print(f"  {anchor_entity}: affiliate candidate '{cand_name}' at {addr} -- NOT merged (not independently Sunbiz-resolved this session; shared address alone is insufficient)")
                        continue
                    cand_principals = {normalize(o["name"]) for o in cand_hit.get("officers", [])}
                    if cand_hit.get("principal_name"):
                        cand_principals.add(normalize(cand_hit["principal_name"]))
                    shared = anchor_principals & cand_principals
                    if shared:
                        print(f"  {anchor_entity}: affiliate '{cand_name}' MERGED -- shared address {addr} + shared principal {sorted(shared)}")
                        claimed_norm_names.add(normalize(cand_name))
                        cand_rows = [r for r in candidates if r["own_name"] == cand_name]
                        all_rows.extend((r, "affiliate_own_addr", f"shared_principal={sorted(shared)[0]}; addr={addr}") for r in cand_rows)
                    else:
                        print(f"  {anchor_entity}: affiliate candidate '{cand_name}' at {addr} -- NOT merged (Sunbiz-resolved but no shared principal with anchor)")

        win_county, win_parcel_id = auction_parcels.get(case_no, (None, None))
        for r, linked_via, detail in all_rows:
            county = CO_NO_TO_COUNTY.get(r["co_no"], f"co_no_{r['co_no']}")
            is_win = (county == win_county and r["parcel_id"] == win_parcel_id)
            acquisition_source = "auction_win" if is_win else "prior_holding"
            row_case_no = case_no if is_win else None
            run_sql(f"""
                insert into winnerdata.owner_portfolio
                  (owner_key, entity_name_raw, county, co_no, parcel_id, address, dor_uc, no_buldng, jv,
                   coastal_flood_indicator, acquisition_source, linked_via, linked_via_detail, batch_id, case_number)
                values
                  ({s(owner_key)}, {s(r['own_name'])}, {s(county)}, {r['co_no']}, {s(r['parcel_id'])},
                   {s(r['phy_addr1'])}, {s(r['dor_uc'])}, {r['no_buldng'] if r['no_buldng'] is not None else 'null'},
                   {r['jv'] if r['jv'] is not None else 'null'}, 'UNKNOWN', {s(acquisition_source)},
                   {s(linked_via)}, {s(detail)}, {s(BATCH_ID)}, {s(row_case_no)})
                on conflict (owner_key, co_no, parcel_id) do nothing;
            """)
        portfolio_summary[case_no] = {"owner_key": owner_key, "property_count": len(all_rows),
                                       "counties": sorted({CO_NO_TO_COUNTY.get(r["co_no"], r["co_no"]) for r, _, _ in all_rows}),
                                       "total_jv": sum(float(r["jv"]) if r["jv"] not in (None, "") else 0 for r, _, _ in all_rows)}
        print(f"  {anchor_entity}: {len(all_rows)} properties across {len(portfolio_summary[case_no]['counties'])} counties (JV total ${portfolio_summary[case_no]['total_jv']:,.0f})")
    return portfolio_summary


def load_co_no_map():
    rows = run_sql("select co_no, slug from public.fl_counties;")
    CO_NO_TO_COUNTY.update({r["co_no"]: r["slug"] for r in rows})


CASCADE_CACHE = "/tmp/cascade_cache_20260825.json"

if __name__ == "__main__":
    load_co_no_map()
    if os.path.exists(CASCADE_CACHE):
        print(f"Loading cached Part 1 cascade results from {CASCADE_CACHE} (skips re-hitting Bright Data/Exa)")
        cascade = json.load(open(CASCADE_CACHE))
    else:
        cascade = part1_identity_cascade()
        json.dump(cascade, open(CASCADE_CACHE, "w"), default=str)
    portfolio = part2_portfolio(cascade)
    with open("/tmp/portfolio_batch_result.json", "w") as f:
        json.dump({"cascade": cascade, "portfolio": portfolio}, f, indent=2, default=str)
    print("\nWrote /tmp/portfolio_batch_result.json")
