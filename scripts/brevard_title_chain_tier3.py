#!/usr/bin/env python3
"""SIGNAL$ section 16 Title Tier 3 (title search / chain of title) — Brevard,
issue #20045. Applies docs/plans/title-chain-pull-P1-build-brief.md's
two_owner algorithm "as far as it goes for Brevard" per the issue text (the
brief itself scopes Duval; this reuses its generic result-table contract).

What this DOES: reads the already-harvested public.title_tier1_results rows
for a case (scripts/pre_auction_lien_harvest.py --county brevard — never
re-scrapes) and looks for a DEED-type instrument naming the current owner as
grantee among THIS COURT CASE's own filed documents.

What this HONESTLY DOES NOT do (P1 brief section 2/6 gate, not attempted this
session): a case-number search only returns documents FILED IN THIS
LITIGATION (Lis Pendens, Judgment, Orders) — the original recorded deed into
the current owner is a separate, earlier Official Records instrument tied to
NO case number, and finding it requires either (a) a grantee-name index
search against Brevard's AcclaimWeb (unverified for this classic-ASP.NET
build, same disclosed gap as pre_auction_lien_harvest.py's owner-name sweep)
or (b) legal-description reconciliation against Brevard's own GIS parcel
layer (scripts/acclaim_case_lookup.py's proven pattern, but that script
resolves PARCEL from legal description, not the deed chain). Neither is
built here. Every case this runs against will therefore produce a
title_chain_gap at seq 1 (current owner's own deed-in unresolved) unless a
real DEED-type document happens to already be in the case's own filed
documents (rare, checked for, not assumed absent).

Per the P1 brief's own rule: BLANK > WRONG. A disclosed gap is correct
output; this never guesses a deed reference to fill the chain.

Usage: brevard_title_chain_tier3.py --case-numbers "05-...,05-..."
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import sys, os, re, json, argparse, datetime as dt
import urllib.request, urllib.parse

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
assert SB_URL and SB_KEY, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY env required"

DEED_TYPE_RE = re.compile(r"\bDEED\b", re.I)


def sb_get(path):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_insert(table, row):
    body = json.dumps(row).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}", data=body, method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-numbers", required=True)
    args = ap.parse_args()
    today = dt.date.today().isoformat()

    for case_number in [c.strip() for c in args.case_numbers.split(",") if c.strip()]:
        auctions = sb_get(f"multi_county_auctions?county=eq.brevard&case_number=eq.{urllib.parse.quote(case_number)}&select=id,parcel_id,case_number")
        if not auctions:
            print(f"{case_number}: not found in multi_county_auctions (county=brevard) — skipped")
            continue
        a = auctions[0]
        parcel_id = a.get("parcel_id")
        if not parcel_id:
            print(f"{case_number}: no parcel_id on file — cannot key title_chain_pull, skipped")
            continue

        existing = sb_get(f"title_chain_pull?parcel_id=eq.{urllib.parse.quote(parcel_id)}&county=eq.Brevard&select=id&limit=1")
        if existing:
            print(f"{case_number}: title_chain_pull already on file for parcel_id={parcel_id} (id={existing[0]['id']}) — skipped, idempotent")
            continue

        tier1 = sb_get(f"title_tier1_results?mca_id=eq.{a['id']}&select=instrument_type,recording_date,book_page,instrument_number,indirect_name,raw_data")
        deed_docs = [d for d in tier1 if DEED_TYPE_RE.search(d.get("instrument_type") or "")]
        legal_description = next(
            (d["raw_data"].get("DocLegalDescription") for d in tier1 if d.get("raw_data", {}).get("DocLegalDescription")),
            None,
        )

        pull = sb_insert("title_chain_pull", {
            "parcel_id": parcel_id, "county": "Brevard",
            "selector_kind": "parcel_id", "selector_value": parcel_id,
            "depth": "two_owner", "as_of_date": today,
            "source_platform": "acclaim", "status": "partial",
            "legal_description": legal_description,
            "reconciliation": {
                "method": "case-number search only (public.title_tier1_results, already harvested — no re-scrape)",
                "deed_type_docs_found_in_case_filings": len(deed_docs),
                "not_attempted": "owner-name/grantee-index search against Brevard AcclaimWeb; GIS legal-description reconciliation for deed-chain purposes (acclaim_case_lookup.py resolves PARCEL from legal description, not prior deeds)",
            },
            "honesty_summary": {"tags": "INFERRED/UNKNOWN — see title_chain_gap for the seq-1 gap reason"},
        })[0]

        if deed_docs:
            # A real DEED-type document was filed in this litigation (unusual,
            # but checked for rather than assumed absent) — still not
            # reconciled to the parcel legal description per the brief's
            # gate (section 6), so it is recorded as owner seq=1 with
            # honesty_marker=INFERRED (name_only), never VERIFIED here.
            d = deed_docs[0]
            sb_insert("title_chain_owner", {
                "pull_id": pull["id"], "seq": 1,
                "owner_name": d.get("indirect_name"),
                "deed_type": d.get("instrument_type"),
                "deed_date": d.get("recording_date"),
                "book_page": d.get("book_page"),
                "instrument_no": d.get("instrument_number"),
                "reconciliation_confidence": "name_only",
                "honesty_marker": "INFERRED",
            })
            n_gaps = 0
            gap_reason = None
        else:
            n_gaps = 1
            gap_reason = ("Deed into current owner not resolvable via this case's own court-filing search "
                          "(case documents were Lis Pendens/Judgment/Order only, no recorded deed) — a "
                          "grantee-name index search against Brevard AcclaimWeb was not attempted this "
                          "session (unverified for Brevard's classic AcclaimWeb build, same disclosed gap "
                          "as scripts/pre_auction_lien_harvest.py's owner-name sweep).")
            sb_insert("title_chain_gap", {
                "pull_id": pull["id"], "between_seq_low": 1, "between_seq_high": 1,
                "reason": gap_reason, "honesty_marker": "UNKNOWN",
            })

        print(f"{case_number}: title_chain_pull id={pull['id']} parcel_id={parcel_id} status=partial "
              f"deed_docs_in_case_filings={len(deed_docs)} gaps={n_gaps}")


if __name__ == "__main__":
    main()
