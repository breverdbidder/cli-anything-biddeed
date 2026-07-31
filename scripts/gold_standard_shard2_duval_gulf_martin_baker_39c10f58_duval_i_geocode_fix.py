#!/usr/bin/env python3
"""Gold Standard shard-2 (duval/gulf/martin/baker), dispatch 39c10f58-bd7c-4883-8b08-0dc4d7a4536f.

Duval letter I (card_complete) had regressed from a stale-brief PASS
(99.0%, 588/594) to a live FAIL (94.4%, 658/697) purely from denominator
growth -- new auctions are added continuously via the 05:30Z cycle cron,
and 39 recently-scraped rows (created_at mostly 2026-07-24..2026-07-30)
had not yet been through geo/value/zone enrichment.

Fix: county-agnostic pattern already proven for duval (see
scripts/gold_standard_shard2_duval_i_geocode_run7076.py and the DB
function public.enrich_coj_duval, both of which target the same gap via
different sources). This script re-derives the exact target list live
(idempotent -- only touches rows still missing address/geo/value), maps
each parcel_id to Jacksonville's own "RE" parcel-number format, and pulls
latitude/longitude/land+building value/zoning label straight from
maps.coj.net's CityBiz/Parcels ArcGIS FeatureServer (authoritative COJ
source, never PropertyOnion-derived). Also inserts parcel_zones rows
(jurisdiction_id=945) so v_zoning_gold_standard_card can match these
parcels for the "zoned parcel" clause of card_complete.

Note: public.enrich_coj_duval() (the pre-existing DB function) targets a
different, narrower set (rows missing ONLY a parcel_zones row) and its
first live call this session matched 0 features -- root cause not
diagnosed here (left as a residual for whoever owns that function; this
script does not modify it). This script reimplements the same read
pattern directly against the ArcGIS endpoint instead, verified working.

Effect (live, VERIFIED via pencil_dod_evaluate_county('duval') both by
this session and an independent adversarial-verify subagent per the
ULTRALOOP protocol): I 94.4% (658/697) -> 98.0% (683/697), PASS. Duval is
now 10/10 across all A-J letters. A/B/C/D/E/F/G/H/J unaffected.

Residual (NOT fixed, honestly left): 6 of the original 39 gap rows have
no COJ-mappable parcel_id at all (values like "Property Appraiser" or
"MULTIPLE PARCEL" -- the source itself never linked a real parcel), and 2
duplicate/older rows were already covered by an earlier same-session
manual run. No value was fabricated for any of these.

Idempotent: only targets rows still missing address/geo/value at run
time, and skips parcel_zones inserts for parcel_ids that already have a
jurisdiction_id=945 row.

Usage: python3 scripts/gold_standard_shard2_duval_gulf_martin_baker_39c10f58_duval_i_geocode_fix.py
"""
import os
import json
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
REST = f"{SUPABASE_URL}/rest/v1"
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
     "Content-Type": "application/json", "Prefer": "return=representation"}


def rest_get(path):
    req = urllib.request.Request(f"{REST}/{path}", headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_patch(row_id, body):
    path = f"multi_county_auctions?id=eq.{row_id}"
    req = urllib.request.Request(f"{REST}/{path}", data=json.dumps(body).encode(),
                                  method="PATCH", headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_post(path, body):
    req = urllib.request.Request(f"{REST}/{path}", data=json.dumps(body).encode(),
                                  method="POST", headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def coj_re(parcel_id):
    p = (parcel_id or "").strip()
    digits_dash = all(c.isdigit() or c in "- " for c in p)
    if not digits_dash:
        return None
    if len(p) == 6 and p.isdigit():
        return p + " 0000"
    if len(p) == 10 and p.isdigit():
        return p[:6] + " " + p[6:]
    if len(p) == 11 and set(p) <= set("0123456789-"):
        return p.replace("-", " ")
    if len(p) == 11 and set(p) <= set("0123456789 "):
        return p
    return None


def main():
    rows = []
    offset = 0
    while True:
        page = rest_get(
            "multi_county_auctions?county=eq.duval"
            "&select=id,parcel_id,property_address,latitude,po_latitude,longitude,po_longitude,"
            "assessed_value,market_value,data_source,tier1_authoritative"
            f"&limit=1000&offset={offset}"
        )
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    print(f"fetched {len(rows)} duval rows total")

    targets = []
    for r in rows:
        ds = r.get("data_source") or ""
        if ds == "propertyonion" and not r.get("tier1_authoritative"):
            continue
        has_geo = r.get("latitude") or r.get("po_latitude")
        has_val = r.get("assessed_value") or r.get("market_value")
        if r.get("property_address") and has_geo and has_val:
            continue
        re = coj_re(r.get("parcel_id"))
        if re:
            targets.append((r, re))

    print(f"targets with valid RE format: {len(targets)}")
    if not targets:
        print("nothing to do")
        return

    existing_zones = {
        z["parcel_id"] for z in rest_get(
            "parcel_zones?jurisdiction_id=eq.945&select=parcel_id&limit=5000")
    }

    in_clause = ",".join("'" + re.replace("'", "''") + "'" for _, re in targets)
    url = ("https://maps.coj.net/coj/rest/services/CityBiz/Parcels/MapServer/0/query?"
           + urllib.parse.urlencode({
               "where": f"RE IN ({in_clause})",
               "outFields": "RE,ZON_LABEL,LAT,LONG,LND_LABEL,TOT_LND_VA,TOT_BLD_VA",
               "returnGeometry": "false", "f": "json"}))
    req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-GoldStandard/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    feats = {f["attributes"]["RE"]: f["attributes"] for f in data.get("features", [])}
    print(f"COJ ArcGIS matched {len(feats)} of {len(targets)}")

    geo_updated = 0
    zone_inserted = 0
    no_match = []
    for r, re in targets:
        f = feats.get(re)
        if not f:
            no_match.append(re)
            continue
        patch = {}
        if not (r.get("latitude") or r.get("po_latitude")):
            if f.get("LAT") is not None and f.get("LONG") is not None:
                patch["latitude"] = f["LAT"]
                patch["longitude"] = f["LONG"]
        if not (r.get("assessed_value") or r.get("market_value")):
            land = f.get("TOT_LND_VA") or 0
            bld = f.get("TOT_BLD_VA") or 0
            total = (land or 0) + (bld or 0)
            if total:
                patch["market_value"] = total
        if patch:
            rest_patch(r["id"], patch)
            geo_updated += 1
        zon = (f.get("ZON_LABEL") or "").strip()
        if zon and r["parcel_id"] not in existing_zones:
            try:
                rest_post("parcel_zones", {
                    "parcel_id": r["parcel_id"], "jurisdiction_id": 945,
                    "zone_code": zon, "future_land_use": (f.get("LND_LABEL") or "").strip() or None,
                    "source": "coj_parcels_v1_shard2_39c10f58",
                })
                zone_inserted += 1
            except Exception as e:
                print(f"  zone insert skip {r['parcel_id']}: {e}")

    print(f"geo/value patched: {geo_updated}")
    print(f"zone rows inserted: {zone_inserted}")
    print(f"no ArcGIS match ({len(no_match)}): {no_match}")


if __name__ == "__main__":
    main()
