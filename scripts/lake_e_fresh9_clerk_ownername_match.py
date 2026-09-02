#!/usr/bin/env python3
"""Lake E re-run (2026-09-02), denominator-drift follow-up to
scripts/shard14_lake_e_ownername_match.py (SHARD-14, dispatch
2a2b2667-58f3-4e55-a353-d33a04236bf9).

9 NEW lake rows landed since the shard14 run (all data_source=
lake_clerk_foreclosure_calendar_v1, parcel_id=NULL, parity_source=
lake_clerk_foreclosure -- not tier1, so the E-candidate filter below still
picks them up because tier1_authoritative is False and data_source !=
propertyonion): 2025CA001179, 2025CA002825, 2025CA001512, 2026CA001004,
2026CA000632, 2026CA000030, 2026CA000927, 2026CA000750, 2025CA001658.
Same exact method as shard14, unmodified: owner-name match against the real
Lake County Property Appraiser ArcGIS FieldMap service (gis.lakecountyfl.gov).
NOT a re-run of the QUARANTINED scripts/shard7_lake_e_i_fix.py (synthetic
parcel_id/centroid fabrication, see public.honesty_violations) -- every value
here comes from a live ArcGIS feature or is left NULL.

WHY OWNER-NAME, NOT CASE-NUMBER: Lake's foreclosure source of truth is the
Lake Clerk's own calendar (foreclosurecalendar.lakecountyclerkfl.gov) because
lake.realforeclose.com is offline (confirmed dead, see
scripts/shard8_lake_clerk_foreclosure_scraper.py). That clerk calendar
publishes no property address or parcel number -- only case_number,
plaintiff, and defendant/owner_name. The AJAX RealForeclose harvester used
for martin/bay/alachua (scripts/shard2_run2450_ajax_realforeclose_harvest.py)
therefore cannot apply to lake. The Lake PA ArcGIS FieldMap service exposes
an OwnerName field (confirmed live via ?f=json schema probe), so this script
matches the foreclosure defendant's name against it instead.

MATCHING RULE (conservative -- BLANK > WRONG):
  1. Strip stopwords (ET, AL, UNKNOWN, ALL, HEIRS, HEIR, OF, THE, ESTATE,
     TRUSTEE, TRUST, DECEASED, IN, AGAINST) from owner_name to get name
     tokens (handles "RICARDO TAFOLLA GARCIA, ET AL" and "UNKNOWN TRUSTEE OF
     THE ROBERT EDWARD WINTERMEYER TRUST" alike).
  2. Query ArcGIS OwnerName LIKE '%<longest token>%' (proxy for the rarest
     surname fragment).
  3. Keep only candidates where EVERY remaining name token appears as a
     substring of the candidate's OwnerName (case-insensitive) -- full
     containment, not just the seed token.
  4. Accept ONLY if exactly one candidate survives containment. Zero or
     ambiguous (>1) hits -> skip, leave parcel_id NULL, record the reason.
     Never guess between multiple heirs/relatives sharing a surname.

Writes (only on unique match): parcel_id, property_address, assessed_value,
assessed_value_source='lake_county_arcgis_fieldmap_live', latitude,
longitude, parity_source='e_match:lake_pa_ownername_v1:<method>'.
Idempotent: only patches rows where parcel_id IS NULL.

Usage: python3 scripts/shard14_lake_e_ownername_match.py [--dry-run]
"""
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ARCGIS_QUERY_URL = (
    "https://gis.lakecountyfl.gov/lakegis/rest/services/"
    "PropertyAppraiser/FieldMap/MapServer/0/query"
)
ARCGIS_HEADERS = {"User-Agent": "curl/8.5.0"}  # Cloudflare blocks urllib's default UA (403)

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

STOPWORDS = {
    "ET", "AL", "ETAL", "UNKNOWN", "ALL", "HEIRS", "HEIR", "OF", "THE",
    "ESTATE", "TRUSTEE", "TRUST", "DECEASED", "IN", "AGAINST", "AND", "&",
    "CO", "TRUSTE", "SUCCESSOR", "REPRESENTATIVE", "PERSONAL",
}


def http_get_json(url):
    req = urllib.request.Request(url, headers=ARCGIS_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def name_tokens(owner_name):
    cleaned = re.sub(r"[.,]", " ", (owner_name or "").upper())
    cleaned = re.sub(r"DBA\s.*$", "", cleaned)  # drop trade-name suffixes ("DBA SMALLDOT")
    words = [w for w in cleaned.split() if w and w not in STOPWORDS and not w.isdigit()]
    return words


def query_ownername_like(fragment):
    params = {
        "where": f"UPPER(OwnerName) LIKE '%{fragment}%'",
        "outFields": "ParcelNumber,OwnerName,PropertyAddress,TotalJustValue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = f"{ARCGIS_QUERY_URL}?{urllib.parse.urlencode(params)}"
    return http_get_json(url)


def ring_centroid(geometry):
    rings = (geometry or {}).get("rings")
    if not rings:
        return None, None
    ring = rings[0]
    return statistics.fmean(pt[1] for pt in ring), statistics.fmean(pt[0] for pt in ring)


def resolve_by_owner_name(owner_name):
    # Only tokens of length >= 3 carry matching signal -- single/double-char
    # tokens (middle initials, "JR") trivially substring-match almost any
    # candidate and were confirmed live to produce a false positive
    # ("KIMBERLY S LAWRENCE" matched "SOULLIERE LAWRENCE J & KIMBERLY A" --
    # wrong person, coincidental first-name collision) before this filter.
    tokens = [t for t in name_tokens(owner_name) if len(t) >= 3]
    if len(tokens) < 2:
        return None, "fewer_than_2_signal_tokens"
    seed = max(tokens, key=len)
    try:
        data = query_ownername_like(seed)
    except Exception as e:
        return None, f"arcgis_error:{e}"
    feats = data.get("features", [])
    if not feats:
        return None, "no_hits"
    survivors = []
    for f in feats:
        candidate_name = (f["attributes"].get("OwnerName") or "").upper()
        candidate_tokens = [t for t in re.split(r"[^A-Z0-9]+", candidate_name) if t]
        # Lake PA OwnerName convention is "LASTNAME FIRSTNAME MIDDLE ..." --
        # require the surname-position token (candidate_tokens[0]) to be one
        # of ours, AND every one of our tokens present as a whole word (not
        # substring) in the candidate. This is what correctly rejects the
        # Soulliere collision above (neither KIMBERLY nor LAWRENCE is the
        # candidate's surname token) while accepting compound surnames
        # ("TAFOLLA GARCIA") and estate suffixes ("LESTER LEONARD E ESTATE").
        if not candidate_tokens or candidate_tokens[0] not in tokens:
            continue
        if all(tok in candidate_tokens for tok in tokens):
            survivors.append(f)
    if len(survivors) == 1:
        return survivors[0], "ownername_surname_position_unique"
    if len(survivors) == 0:
        return None, f"no_surname_position_match_of_{len(feats)}_seed_hits"
    return None, f"ambiguous_{len(survivors)}_surname_position_hits"


def main():
    dry_run = "--dry-run" in sys.argv
    rows = rest_get(
        "multi_county_auctions?county=eq.lake&parcel_id=is.null"
        "&or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        "&select=id,case_number,owner_name,property_address,latitude,longitude,assessed_value,parity_source")

    receipt = []
    matched = 0
    for row in rows:
        feature, method = resolve_by_owner_name(row.get("owner_name"))
        entry = {"case_number": row["case_number"], "owner_name": row.get("owner_name"), "method": method}
        if not feature:
            entry["matched"] = False
            receipt.append(entry)
            print(f"  SKIP {row['case_number']}: {method} ({row.get('owner_name')})")
            continue

        attrs = feature["attributes"]
        parcel_id = attrs.get("ParcelNumber")
        prop_addr = attrs.get("PropertyAddress")
        tjv = attrs.get("TotalJustValue")
        lat, lon = ring_centroid(feature.get("geometry"))

        patch_body = {
            "parcel_id": parcel_id,
        }
        # DO NOT clobber an existing tier1%-prefixed parity_source -- the DoD
        # evaluator's C/D matched_clean/matched_any counts filter on
        # `parity_source LIKE 'tier1%'`, and rows can carry a NULL parcel_id
        # while already being tier1-crosschecked matched_clean/matched_any
        # via a different lane (e.g. clerk case-number crosscheck). Confirmed
        # regression live 2026-08-07 on case 2025CA002152: overwriting
        # parity_source here dropped C 103->102 and D 109->108 even though
        # the parcel_id/address/value write itself was correct and additive.
        existing_source = row.get("parity_source") or ""
        if not existing_source.startswith("tier1"):
            patch_body["parity_source"] = f"e_match:lake_pa_ownername_v1:{method}"
        if not row.get("property_address") and prop_addr:
            patch_body["property_address"] = prop_addr
        if not row.get("assessed_value") and isinstance(tjv, (int, float)):
            patch_body["assessed_value"] = tjv
            patch_body["assessed_value_source"] = "lake_county_arcgis_fieldmap_live"
        if not row.get("latitude") and lat is not None:
            patch_body["latitude"] = round(lat, 6)
            patch_body["longitude"] = round(lon, 6)

        entry["matched"] = True
        entry["parcel_id"] = parcel_id
        entry["arcgis_owner_name"] = attrs.get("OwnerName")
        entry["patch_body"] = {k: v for k, v in patch_body.items() if k != "parity_source"}

        if dry_run:
            matched += 1
            print(f"  WOULD MATCH {row['case_number']} -> {parcel_id} ({attrs.get('OwnerName')})")
        else:
            status, resp = rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
            entry["patch_status"] = status
            if status not in (200, 204):
                print(f"  PATCH FAILED {row['case_number']}: HTTP {status} {resp}", file=sys.stderr)
                entry["matched"] = False
            else:
                matched += 1
                print(f"  MATCHED {row['case_number']} -> parcel_id={parcel_id} "
                      f"({attrs.get('OwnerName')}) addr={prop_addr}")
        receipt.append(entry)

    print(f"\nTOTALS: candidates={len(rows)} matched={matched} "
          f"skipped={len(rows) - matched}{' (DRY RUN)' if dry_run else ''}")
    print(json.dumps({"receipt": receipt}, indent=2))


if __name__ == "__main__":
    main()
