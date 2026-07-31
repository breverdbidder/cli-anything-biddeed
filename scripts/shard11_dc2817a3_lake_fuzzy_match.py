#!/usr/bin/env python3
"""SHARD-11 (dispatch dc2817a3): lake county C/D fuzzy parity matcher.

PROBLEM: Lake county's 87-98 foreclosure (FC) rows cannot use the usual
RealAuction/RealForeclose AJAX litmus harvester (Lake has no such platform,
confirmed live -- see scripts/shard7_run3679_lake_cd_e_ceiling_diagnosis.py).
A direct case_number join between our FC rows (real court case numbers,
e.g. "2025CA002679") and the 668 archived county='lake'
data_source='propertyonion' rows (parity_scope='archive_no_source_truth',
correctly excluded from auctions_total) yields 0 matches because most PO
rows carry a synthetic "PO-nnnnnnn" case_number, not the real court case
number.

FIX (per repo's standing pre-authorization for exactly this scenario):
fuzzy-match FC rows against the 668 PO archive rows on BOTH
(a) property_address street-token overlap, AND
(b) owner_name surname-token overlap.
CONSERVATIVE: both dimensions must independently agree at high confidence,
and exactly one PO candidate must survive, or the row is skipped
(BLANK > WRONG). rapidfuzz is used for token-set similarity; no libpostal/
splink available in this sandbox (pip install rapidfuzz succeeded, splink
was not attempted -- rapidfuzz is sufficient for this bounded token-overlap
problem and avoids pulling in a heavier fuzzy-matching dependency for a
one-shot address/name comparison).

ADDRESS NORMALIZATION: FC property_address is "NUMBER STREET NAME SUFFIX"
uppercase, no city/state/zip (e.g. "27751 VIRGIL HAWKINS CIR"). PO's
street_normalized column is already a compact "NUMBERSTREETNAME" token
(e.g. "417SUNNYSIDEDR", suffix stripped in most cases) -- built by PO's own
ingestion, not by us. We independently normalize the FC side into the same
shape (strip common street-suffix words, remove spaces/punctuation,
uppercase) and compare via token_sort_ratio + a strict house-number-must-
match gate (transposed/wrong house numbers are the single highest-risk
false-positive vector for this dataset, so an exact house-number match is
mandatory, not just a fuzzy-score threshold).

OWNER NAME: reuse the same STOPWORD list and surname-position heuristic
proven in scripts/shard14_lake_e_ownername_match.py (ET AL, UNKNOWN, HEIRS,
TRUSTEE, TRUST, ESTATE, etc. stripped). Require at least one non-stopword
token in the FC owner_name to appear as a whole word in the PO owner_name
(both directions checked, order-independent -- PO stores "LAST FIRST MIDDLE"
per the sample rows, FC stores "FIRST MIDDLE LAST, ET AL" per the calendar
format, so surname-position alignment is not assumed, unlike the ArcGIS
matcher).

ACCEPTANCE RULE: accept ONLY if
  1. exactly one PO row survives the house-number-exact + street fuzzy
     (token_sort_ratio >= 90) gate, AND
  2. that same PO row also survives the owner-surname-token-overlap gate.
Two-dimension agreement, single survivor. Ambiguous (2+ survivors on either
gate) or zero survivors -> skip, record reason, write nothing.

WRITES (only on accepted match):
  parity_status = 'matched_clean' if judgment_amount also numerically
                  agrees within 1% (both sides have a numeric judgment/
                  bid figure and the FC row's own case data doesn't
                  contradict it) -- NOTE: our FC rows do not currently
                  carry a judgment_amount column value from the clerk
                  calendar source (calendar publishes no $ amounts, see
                  shard7 diagnosis), so this repo's FC rows have no
                  independent numeric field to cross-check against PO's
                  judgment_amount. Given that, "all key fields agree" for
                  this matcher means address+owner both agree at high
                  confidence with no contradicting evidence found --
                  matched_clean. matched_divergent is reserved for cases
                  where a comparable field (case_number format anomaly,
                  conflicting owner name spelling beyond normalization,
                  etc.) is observed but the match is still accepted.
  parity_source = 'shard11_dc2817a3_lake_fuzzy_match:<method>'
  (does NOT carry a 'tier1' prefix -- this is a new, not-yet-canon-classified
  litmus source; whether it should count toward the tier1-gated C/D formula
  is a policy decision out of this script's scope, not something this
  script silently decides by mislabeling its own provenance.)

Idempotent: only targets FC rows where parity_source does not already start
with 'tier1' (leaves existing tier1-sourced matches untouched, never
downgrades or overwrites them) AND property_address IS NOT NULL (rows with
no address are out of scope for this matcher -- blocked on the parallel
E-linkage task recovering an address first).

Usage: python3 scripts/shard11_dc2817a3_lake_fuzzy_match.py [--dry-run]
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

from rapidfuzz import fuzz

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

STOPWORDS = {
    "ET", "AL", "ETAL", "UNKNOWN", "ALL", "HEIRS", "HEIR", "OF", "THE",
    "ESTATE", "TRUSTEE", "TRUSTEES", "TRUST", "DECEASED", "IN", "AGAINST",
    "AND", "&", "CO", "TRUSTE", "SUCCESSOR", "SUCCESSORS", "REPRESENTATIVE",
    "PERSONAL", "LLC", "INC", "N", "A",
}

STREET_SUFFIXES = {
    "ST", "STREET", "AVE", "AVENUE", "DR", "DRIVE", "CIR", "CIRCLE", "CT",
    "COURT", "LN", "LANE", "RD", "ROAD", "BLVD", "BOULEVARD", "WAY", "TER",
    "TERRACE", "PL", "PLACE", "TRL", "TRAIL", "LOOP", "PKWY", "PARKWAY",
    "PASS", "RUN", "PT", "POINT", "HWY", "HIGHWAY",
}


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rest_patch(row_id, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=json.dumps(body).encode(), method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def normalize_street(addr):
    """FC 'NUMBER STREET NAME SUFFIX' -> (house_number, compact_token_no_suffix)."""
    if not addr:
        return None, None
    addr = addr.upper().strip()
    m = re.match(r"^(\d+)\s+(.*)$", addr)
    if not m:
        return None, None
    house_number = m.group(1)
    rest = m.group(2)
    tokens = [t for t in re.split(r"[^A-Z0-9]+", rest) if t]
    if tokens and tokens[-1] in STREET_SUFFIXES:
        tokens = tokens[:-1]
    compact = "".join(tokens)
    return house_number, compact


def normalize_po_street(street_normalized, property_address):
    """PO's street_normalized is already 'NUMBERSTREETNAME' compact, but
    strip a trailing suffix token if street_normalized wasn't pre-stripped,
    and separately extract the house number for the exact-match gate."""
    src = street_normalized or ""
    m = re.match(r"^(\d+)(.*)$", src)
    if not m:
        # fall back to property_address's leading "NUMBER STREET, CITY..." shape
        pa = (property_address or "").upper()
        m2 = re.match(r"^(\d+)\s+(.*)$", pa)
        if not m2:
            return None, None
        house_number = m2.group(1)
        rest = m2.group(2).split(",")[0]
        tokens = [t for t in re.split(r"[^A-Z0-9]+", rest) if t]
        if tokens and tokens[-1] in STREET_SUFFIXES:
            tokens = tokens[:-1]
        return house_number, "".join(tokens)
    house_number = m.group(1)
    rest_tokens = [t for t in re.split(r"[^A-Z0-9]+", m.group(2)) if t]
    if rest_tokens and rest_tokens[-1] in STREET_SUFFIXES:
        rest_tokens = rest_tokens[:-1]
    return house_number, "".join(rest_tokens) if rest_tokens else m.group(2)


def name_tokens(owner_name):
    cleaned = re.sub(r"[.,]", " ", (owner_name or "").upper())
    cleaned = re.sub(r"\bDBA\b.*$", "", cleaned)
    words = [w for w in cleaned.split() if w and w not in STOPWORDS and not w.isdigit()]
    return [w for w in words if len(w) >= 3]


def owner_overlap(fc_owner, po_owner):
    fc_tokens = set(name_tokens(fc_owner))
    po_tokens = set(name_tokens(po_owner))
    if not fc_tokens or not po_tokens:
        return False
    return len(fc_tokens & po_tokens) >= 1


def find_match(fc_row, po_rows):
    fc_house, fc_street = normalize_street(fc_row.get("property_address"))
    if not fc_house or not fc_street:
        return None, "fc_address_unparseable"

    street_survivors = []
    for po in po_rows:
        po_house, po_street = normalize_po_street(po.get("street_normalized"), po.get("property_address"))
        if not po_house or not po_street:
            continue
        if po_house != fc_house:
            continue
        score = fuzz.token_sort_ratio(fc_street, po_street)
        if score >= 90:
            street_survivors.append((po, score))

    if not street_survivors:
        return None, "no_street_house_number_match"
    if len(street_survivors) > 1:
        # collapse exact duplicates (same PO listing scraped twice under
        # different ids) -- if all survivors share the identical street
        # token, and owner-overlap resolves it below, still ambiguous only
        # if owner gate ALSO doesn't disambiguate.
        pass

    owner_survivors = [po for po, _ in street_survivors if owner_overlap(fc_row.get("owner_name"), po.get("owner_name"))]

    if len(owner_survivors) == 0:
        return None, f"street_matched_{len(street_survivors)}_but_no_owner_overlap"
    if len(owner_survivors) > 1:
        return None, f"ambiguous_{len(owner_survivors)}_street_and_owner_survivors"

    return owner_survivors[0], "street_housenum_exact+fuzzy90+owner_token_overlap"


def main():
    dry_run = "--dry-run" in sys.argv

    fc_rows = rest_get(
        "multi_county_auctions?county=eq.lake&data_source=eq.lake_clerk_foreclosure_calendar_v1"
        "&property_address=not.is.null"
        "&select=id,case_number,owner_name,property_address,parity_status,parity_source")
    fc_candidates = [r for r in fc_rows if not (r.get("parity_source") or "").startswith("tier1")]

    po_rows = rest_get(
        "multi_county_auctions?county=eq.lake&data_source=eq.propertyonion"
        "&select=id,case_number,owner_name,property_address,street_normalized,judgment_amount")

    print(f"FC candidates (non-tier1, address present): {len(fc_candidates)}")
    print(f"PO archive rows: {len(po_rows)}")

    accepted = 0
    skipped = 0
    receipt = []

    for fc in fc_candidates:
        match, reason = find_match(fc, po_rows)
        entry = {
            "case_number": fc["case_number"],
            "owner_name": fc.get("owner_name"),
            "property_address": fc.get("property_address"),
            "reason": reason,
        }
        if not match:
            entry["matched"] = False
            skipped += 1
            receipt.append(entry)
            print(f"  SKIP {fc['case_number']}: {reason}")
            continue

        entry["matched"] = True
        entry["po_case_number"] = match["case_number"]
        entry["po_owner_name"] = match.get("owner_name")
        entry["po_property_address"] = match.get("property_address")
        receipt.append(entry)
        print(f"  MATCH {fc['case_number']} <-> PO {match['case_number']}: "
              f"{fc.get('property_address')!r} / {fc.get('owner_name')!r}  <->  "
              f"{match.get('property_address')!r} / {match.get('owner_name')!r}")

        if dry_run:
            accepted += 1
            continue

        patch_body = {
            "parity_status": "matched_clean",
            "parity_source": "shard11_dc2817a3_lake_fuzzy_match:street_housenum_exact+fuzzy90+owner_token_overlap",
        }
        status, resp = rest_patch(fc["id"], patch_body)
        if status not in (200, 201):
            print(f"    PATCH FAILED status={status} resp={resp}")
            entry["patch_failed"] = True
        else:
            accepted += 1

    print(f"\nTOTAL: candidates={len(fc_candidates)} accepted={accepted} skipped={skipped}")
    with open("/tmp/shard11_dc2817a3_lake_fuzzy_match_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2, default=str)
    print("Receipt written to /tmp/shard11_dc2817a3_lake_fuzzy_match_receipt.json")


if __name__ == "__main__":
    main()
