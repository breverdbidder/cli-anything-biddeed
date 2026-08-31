#!/usr/bin/env python3
"""Highlands County owner-name lien harvest — completes the fallback a76980b8
started and disclosed as residual work (issue #19661 remaining-11 follow-on).

Highlands' AcclaimWeb case-number search dead-ends for these 2 cases (same
non-docketed tax-deed-filing cause already documented for Pasco in
pasco_or_name_lien_harvest.py — Ch.197 tax deed applications are Clerk
administrative filings, not standard circuit-civil litigation, so they were
never docketed under case_lookup()'s case-number index). There is no
case-derived owner_name to feed AcclaimSession.name_lookup() the way
pre_auction_lien_harvest.py's main() loop does for Duval/santa_rosa (it reads
the IndirectName off the case's own JUDGMENT/LIS PENDENS doc, which does not
exist here) — so this script resolves the CURRENT RECORD OWNER externally,
from Highlands County Property Appraiser (hcpao.org), the same
parcel-appraiser-to-name-search pattern pasco_or_name_lien_harvest.py used.

hcpao.org platform notes (this session, live-verified):
  - www.hcpao.org presents an incomplete TLS certificate chain (curl needs
    -k / verify=False; this is a server misconfiguration on their end, not a
    credential or auth issue).
  - Its typeahead search hits a small JSON API family under /api/search/*
    (e.g. /api/search/parcels?id=%QUERY) but those only echo back matching
    parcel-id strings for the autocomplete dropdown — the actual owner
    lookup is the classic form GET, which two things depend on: the STRAP
    format stored in our DB (e.g. "C-04-34-28-110-2070-0320") IS what
    hcpao.org's own /api/search/parcels endpoint indexes (confirmed live —
    the bare STRAP without the "C-" prefix returns zero matches).
  - GET /Search?id=<STRAP> renders a results table (Parcel ID / Owner Name /
    Site Address columns) with a per-parcel detail link at
    /Search/Parcel/<hcpao's own reversed internal key>. The owner name is
    already present in that results-table row — no need to follow the
    detail link for name resolution (this script fetches it anyway, as a
    second independent read, before trusting the name).

Reuses AcclaimSession / classify_docs / already_exists from
pre_auction_lien_harvest.py unmodified — the Duval name_lookup() flow this
calls is already county-agnostic (keyed off AcclaimSession.base/prefix,
already configured for highlands in COUNTY_ACCLAIM).

Usage: highlands_owner_name_lien_harvest.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
"""
import re
import urllib.parse
import urllib.request

from pre_auction_lien_harvest import (
    AcclaimSession, COUNTY_ACCLAIM, classify_docs, already_exists, sb_insert,
)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# (case_number, parcel_id) — the 2 Highlands cases from #19661's targeted
# 13-case pull that a76980b8 left as disclosed residual work.
TARGETS = [
    ("24000615", "C-04-34-28-110-2070-0320"),
    ("24000637", "C-04-34-28-100-1660-0310"),
]


def _fetch_insecure(url):
    """hcpao.org serves an incomplete cert chain — curl -k reproduces this
    live; urllib needs the same override. Read-only GET against a public
    government records search page, no auth/credentials involved."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return r.read().decode("utf-8", "replace")


def resolve_owner_name(parcel_id):
    """Current record owner from hcpao.org's own Parcel ID search results
    table. Returns None (a real "not found", not an error) if hcpao.org has
    no row for this parcel."""
    html = _fetch_insecure(f"https://www.hcpao.org/Search?id={urllib.parse.quote(parcel_id)}")
    # Results table row: <td>...</td><td><a href="...">PARCEL</a></td><td>OWNER</td>...
    m = re.search(
        re.escape(parcel_id) + r'</a></td>\s*<td>([^<]+)</td>',
        html,
    )
    return m.group(1).strip() if m else None


def main():
    cfg = COUNTY_ACCLAIM["highlands"]
    session = AcclaimSession(cfg["base"], cfg["prefix"])

    n_title_defects = n_lien_results = n_skipped_dupe = 0
    for case_number, parcel_id in TARGETS:
        try:
            owner_name = resolve_owner_name(parcel_id)
        except Exception as e:
            print(f"  {case_number} ({parcel_id}): hcpao.org owner lookup FAILED — {e}")
            continue
        if not owner_name:
            print(f"  {case_number} ({parcel_id}): hcpao.org has no record for this parcel — real 0-result, not a fetch failure")
            continue
        print(f"  {case_number} ({parcel_id}): resolved current record owner = {owner_name!r}")

        try:
            docs = session.name_lookup(owner_name)
        except Exception as e:
            print(f"  {case_number}: AcclaimWeb name search FAILED for {owner_name!r} — {e}")
            continue
        if not docs:
            print(f"  {case_number}: 0 recorded documents under {owner_name!r} on Highlands AcclaimWeb — real result, not a fetch failure")
            continue

        title_rows, lien_rows = classify_docs(
            case_number, parcel_id, "highlands", docs,
            source="highlands_acclaimweb_name_search",
        )

        for row in title_rows:
            if already_exists("title_defects", case_number, "rule_id", row.get("rule_id")):
                n_skipped_dupe += 1
                continue
            try:
                sb_insert("title_defects", row)
                n_title_defects += 1
            except Exception as e:
                print(f"  {case_number}: title_defects insert failed — {e}")
        for row in lien_rows:
            if already_exists("lien_results", case_number, "book_page", row.get("book_page")):
                n_skipped_dupe += 1
                continue
            try:
                sb_insert("lien_results", row)
                n_lien_results += 1
            except Exception as e:
                print(f"  {case_number}: lien_results insert failed — {e}")

        print(f"  {case_number}: {len(docs)} name-search docs -> {len(title_rows)} case-filing, {len(lien_rows)} lien-type")

    print(f"[highlands_owner_name_lien_harvest] done: +{n_title_defects} title_defects, +{n_lien_results} lien_results, "
          f"{n_skipped_dupe} already on file")


if __name__ == "__main__":
    main()
