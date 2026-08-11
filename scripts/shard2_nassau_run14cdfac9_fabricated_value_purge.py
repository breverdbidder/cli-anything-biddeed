#!/usr/bin/env python3
"""Gold Standard shard-2 (dispatch 14cdfac9, nassau): fabricated-value purge.

Adversarial verification of this session's nassau E/I claim (via Workflow
ULTRALOOP, verify:nassau:E) found that 15 nassau rows carried an identical
assessed_value=320000 / market_value=336000.0 pair across 15 completely
distinct properties -- a templated/placeholder fabrication signature (real
per-parcel values from the Nassau County PA ArcGIS layer range $4,500 to
$937,155, nothing close to a repeated $320K/$336K). 7 of the 15 rows even
carried a real RealForeclose source_url/AID, meaning the fabricated value
had silently overwritten (or was inserted alongside) otherwise-real rows.
This predates this session (created_at as early as 2026-07-01); this
session's own E-backfill script never wrote these fields for the affected
9 calendar-sweep rows (only parcel_id + property_address).

Fix: for 13 of the 15 rows, queried the live Nassau County PA ArcGIS layer
(maps.ncpafl.com/ncflpa_arcgis/.../MapServer/144, fields JUSTVAL and
FASMP_ASSD_VALUE_NS) by parcel_id/PIN and overwrote assessed_value/
market_value with the real per-parcel figures. 2 rows (condo-unit PINs
00-00-31-101G-0001-2169 and 00-00-31-141K-0406-0000) returned no match in
that layer (likely a master-parcel vs unit-record PIN mismatch) -- for
those, assessed_value/market_value were set to NULL rather than left
fabricated (BLANK > WRONG). This dropped nassau I from a false 100% to an
honest 95.7% (45/47), still above the 95% gate.

This is a live-data cleanup script kept for repo history / audit trail.
The actual fix was already applied live via direct REST PATCH during this
session -- running this script again is safe (idempotent: re-queries the
same live ArcGIS values and overwrites with the same numbers).
"""
import json
import os
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
     "Content-Type": "application/json", "Prefer": "return=representation"}

ARCGIS = ("https://maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/"
          "TaxMap4_CitrixV2/MapServer/144/query")

# case_number -> parcel_id (PIN), for every nassau row found carrying the
# fabricated assessed_value=320000 / market_value=336000.0 placeholder pair
# (excluding 26TD000009AXYX, whose assessed_value was real/scraped -- only
# its market_value needed fixing, handled separately below).
CASE_TO_PIN = {
    "452025CA000321CAAXYX": "44-2N-28-5160-000A-0030",
    "452025CA000370CAAXYX": "00-00-31-101G-0001-2169",  # not found in ArcGIS -> NULL
    "452024CC000497CCAXYX": "42-2N-27-4374-0028-0000",
    "452024CC000573CCAXYX": "42-2N-27-1090-0079-0000",
    "452024CC000566CCAXYX": "42-2N-27-1090-0121-0000",
    "452025CA000420CAAXYX": "42-2N-27-4460-0027-0000",
    "452025CA000336CAAXYX": "41-2N-28-1140-0064-0000",
    "26TD000005AXYX": "10-2N-26-2010-0618-0000",
    "26TD000006AXYX": "00-00-31-141K-0406-0000",  # not found in ArcGIS -> NULL
    "26TD000011AXYX": "25-4N-24-2020-0003-0010",
    "26TD000012AXYX": "16-4N-24-0000-0004-0080",
    "26TD000013AXYX": "00-00-31-1800-0161-0080",
    "26TD000014AXYX": "35-4N-25-4220-0002-0020",
    "26TD000015AXYX": "08-3N-24-2380-0103-0110",
    "26TD000016AXYX": "31-2N-28-1601-0062-0000",
    "26TD000017AXYX": "39-2N-27-0000-0001-0020",
    "26TD000018AXYX": "42-2N-27-4613-0008-0010",
}
MARKET_VALUE_ONLY = {"26TD000009AXYX": ("00-00-30-0254-0005-0000", 481124.00)}
NOT_FOUND_IN_ARCGIS = {"452025CA000370CAAXYX", "26TD000006AXYX"}


def query_pa(pin):
    params = {"where": f"UPPER(PIN) = UPPER('{pin}')",
              "outFields": "PIN,JUSTVAL,FASMP_ASSD_VALUE_NS", "returnGeometry": "false", "f": "json"}
    req = urllib.request.Request(ARCGIS + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    feats = data.get("features", [])
    return feats[0]["attributes"] if feats else None


def patch(case_number, body):
    params = {"county": "eq.nassau", "case_number": f"eq.{case_number}"}
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?" + urllib.parse.urlencode(params),
        data=json.dumps(body).encode(), method="PATCH", headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    for case, pin in CASE_TO_PIN.items():
        if case in NOT_FOUND_IN_ARCGIS:
            n = len(patch(case, {"assessed_value": None, "market_value": None}))
            print(f"{case}: PIN={pin} not in ArcGIS -- nulled fabricated placeholder ({n} rows)")
            continue
        attrs = query_pa(pin)
        if not attrs:
            print(f"{case}: PIN={pin} UNEXPECTEDLY not found this run -- skipped, no write")
            continue
        body = {}
        if attrs.get("JUSTVAL"):
            body["market_value"] = round(float(attrs["JUSTVAL"]), 2)
        if attrs.get("FASMP_ASSD_VALUE_NS"):
            body["assessed_value"] = round(float(attrs["FASMP_ASSD_VALUE_NS"]), 2)
        n = len(patch(case, body))
        print(f"{case}: PIN={pin} real values {body} ({n} rows)")

    for case, (pin, real_market) in MARKET_VALUE_ONLY.items():
        n = len(patch(case, {"market_value": real_market}))
        print(f"{case}: PIN={pin} assessed_value already real (scraped); market_value -> {real_market} ({n} rows)")


if __name__ == "__main__":
    main()
