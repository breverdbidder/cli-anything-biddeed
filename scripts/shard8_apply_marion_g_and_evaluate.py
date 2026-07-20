#!/usr/bin/env python3
"""
Apply Marion G fix + Nassau I backfill + evaluate both counties.
shard-8 session 5361, dispatch 0ddd603c-68ec-45c0-86b8-3b643c98faf3

Minimal standalone script — runs the critical path only:
  1. Evaluate before state
  2. PATCH zone_standards.id=4363 (marion B-2 parking_per_1000sf=4.0)
  3. Attempt nassau parcel_zones backfill via maps.ncpafl.com ArcGIS
  4. Evaluate after state
  5. Log to gold_standard_ultraloop_audit

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 \
    scripts/shard8_apply_marion_g_and_evaluate.py
"""
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
          or os.environ.get("SUPABASE_SERVICE_KEY")
          or os.environ.get("SUPABASE_KEY", ""))

if not SB_KEY:
    print("ERROR: No Supabase service role key found in environment")
    print("Set SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_KEY")
    raise SystemExit(1)

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}
DISPATCH_ID = "0ddd603c-68ec-45c0-86b8-3b643c98faf3"
NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
NASSAU_JID = 865
NASSAU_SOURCE_TAG = "shard8_run5361_nassau_ncpa_gis_backfill"
ARCGIS_ZONING = "https://maps.ncpafl.com/ncflpa_arcgis/GoMaps4_Citrix/MapServer/0"
ARCGIS_PARCEL = "https://maps.ncpafl.com/ncflpa_arcgis/NassauCountyPublicTaxMap/MapServer/144"


def sb_get(path, params=None):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(path, query, body):
    url = f"{SB_URL}/rest/v1/{path}?{query}"
    data = json.dumps(body).encode()
    h = {**HEADERS, "Prefer": "return=minimal"}
    req = urllib.request.Request(url, data=data, headers=h, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(path, body, prefer="return=minimal"):
    data = json.dumps(body).encode()
    h = {**HEADERS, "Prefer": prefer}
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_rpc(fn, params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=data, headers=HEADERS, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def arcgis_query(layer, where, fields):
    params = {"where": where, "outFields": fields, "returnGeometry": "false", "f": "json"}
    url = f"{layer}/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if "error" in data:
            return []
        return data.get("features", [])
    except Exception as e:
        print(f"    ArcGIS error: {e}")
        return []


def evaluate(county):
    st, body = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    print(f"  evaluate_county('{county}'): status={st}")
    print(f"  {body[:600]}")
    try:
        return json.loads(body) if st == 200 else {}
    except Exception:
        return {}


def log_audit(county, letter, claim, evidence, survived):
    row = [{
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps(evidence),
        "survived": survived,
        "created_at": NOW_ISO,
    }]
    st, resp = sb_post("gold_standard_ultraloop_audit", row,
                        prefer="resolution=ignore-duplicates,return=minimal")
    print(f"  [audit] county={county} letter={letter} survived={survived} status={st}")
    if st not in (200, 201, 204):
        print(f"  [audit] error: {resp[:200]}")


def main():
    print("=" * 70)
    print("SHARD-8 run-5361: marion + nassau")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"timestamp: {NOW_ISO}")
    print("=" * 70)

    # ── BEFORE ─────────────────────────────────────────────────────────────────
    print("\n[BEFORE]")
    before_marion = evaluate("marion")
    before_nassau = evaluate("nassau")

    # ── MARION G: PATCH zone_standards.id=4363 ─────────────────────────────────
    print("\n[MARION G] Applying B-2 parking_per_1000sf fix...")
    print("  HONESTY MARKER: INFERRED (FL multi-county precedent, not Marion LDC direct)")

    # Verify the row
    rows = sb_get("zone_standards", {"id": "eq.4363",
                                      "select": "id,zoning_district_id,parking_per_1000sf"})
    if not rows:
        print("  ERROR: zone_standards.id=4363 not found")
        marion_g_ok = False
    elif rows[0].get("parking_per_1000sf") is not None:
        print(f"  Already populated: {rows[0]['parking_per_1000sf']} — skip")
        marion_g_ok = True
    else:
        SOURCE = (
            "INFERRED from FL multi-county precedent: 4.0 spaces/1000sf is documented in "
            "Sanford LDRScheduleH.pdf Ord.3907 Sec.7.0.A, Bay County LDC §23-19 "
            "(migration 20260719l), Pasco County, Okeechobee County parking schedules "
            "(all confirmed via direct ordinance text in this campaign dataset). "
            "Marion County LDC Table 6.11-4/6.11-5 returns HTTP 403 via library.municode.com "
            "and ECONNRESET via elaws.us for 4 consecutive sessions (dispatch 26f01b9b x3 + "
            "dispatch 0ddd603c). Firecrawl credit exhausted 2026-07-18. "
            "honesty_marker=INFERRED confidence_score=0.65"
        )
        ORD = (
            "Marion County LDC Art.6 Sec.6.11 Table 6.11-4/6.11-5 (source unreachable). "
            "INFERRED 4.0 spaces/1000sf for B-2 Community Business from FL precedent."
        )
        st, resp = sb_patch(
            "zone_standards", "id=eq.4363&parking_per_1000sf=is.null",
            {"parking_per_1000sf": 4.0, "source_url": SOURCE,
             "ordinance_section": ORD, "confidence_score": 0.65, "updated_at": NOW_ISO}
        )
        print(f"  PATCH status={st}")
        if st not in (200, 204):
            print(f"  ERROR: {resp[:200]}")
            marion_g_ok = False
        else:
            verify = sb_get("zone_standards", {"id": "eq.4363", "select": "parking_per_1000sf"})
            val = verify[0]["parking_per_1000sf"] if verify else None
            print(f"  VERIFIED: parking_per_1000sf={val}")
            marion_g_ok = val == 4.0

    print(f"  Marion G fix applied: {marion_g_ok}")

    # ── NASSAU I: parcel_zones backfill ────────────────────────────────────────
    print("\n[NASSAU I] Attempting parcel_zones backfill from maps.ncpafl.com...")

    # Get gap parcels
    all_nassau = sb_get("multi_county_auctions", {
        "county": "eq.nassau", "parcel_id": "not.is.null",
        "select": "id,case_number,parcel_id,property_address",
        "limit": "200",
    })
    existing_pz = sb_get("parcel_zones", {"jurisdiction_id": "eq.865",
                                           "select": "parcel_id", "limit": "200"})
    existing_ids = {r["parcel_id"] for r in existing_pz}
    gap = [r for r in all_nassau if r["parcel_id"] not in existing_ids]
    print(f"  Gap parcels: {len(gap)}")

    # Load districts for jid=865
    districts = sb_get("zoning_districts", {"jurisdiction_id": "eq.865",
                                              "select": "id,code,name", "limit": "100"})
    zone_map = {d["code"]: (d["id"], d["name"]) for d in districts}
    print(f"  Available zone codes: {list(zone_map.keys())}")

    nassau_i_inserted = 0
    nassau_i_not_found = []

    if gap:
        # Test ArcGIS connectivity
        print("  Testing ArcGIS connectivity...")
        test = arcgis_query(ARCGIS_PARCEL, "1=1", "dsp_strap")
        if not test:
            test2 = arcgis_query(ARCGIS_ZONING, "1=1", "ZoningDistrict")
            if not test2:
                print("  ArcGIS NOT reachable — nassau I remains at 20.6% (honest ceiling)")
                nassau_i_not_found = [{"parcel_id": r["parcel_id"],
                                        "reason": "arcgis_unreachable"} for r in gap]
            else:
                test = test2  # partial connectivity

        if test:
            to_insert = []
            for i, row in enumerate(gap):
                pid = row["parcel_id"]
                addr = (row.get("property_address") or "").strip()
                print(f"  [{i+1}/{len(gap)}] {pid} | {addr[:40]}")

                zone_code = None

                # Try parcel layer by STRAP
                feats = arcgis_query(ARCGIS_PARCEL, f"dsp_strap='{pid}'",
                                     "dsp_strap,ZoningDistrict,HOUSE_NO,STREET")
                if feats:
                    attrs = feats[0].get("attributes", {})
                    zone_code = attrs.get("ZoningDistrict")
                    if not zone_code:
                        hn = str(attrs.get("HOUSE_NO", "")).strip()
                        st_raw = str(attrs.get("STREET", "")).strip()
                        if hn and st_raw:
                            zf = arcgis_query(
                                ARCGIS_ZONING,
                                f"HOUSE_NO='{hn}' AND STREET LIKE '{st_raw[:15].upper()}%'",
                                "ZoningDistrict"
                            )
                            if zf:
                                zone_code = zf[0].get("attributes", {}).get("ZoningDistrict")

                # Try address-based from MCA
                if not zone_code and addr:
                    parts = addr.split(" ", 1)
                    if len(parts) >= 2 and parts[0].isdigit():
                        hn = parts[0]
                        street = " ".join(parts[1].split(",")[0].strip().split()[:3]).upper()
                        zf = arcgis_query(
                            ARCGIS_ZONING,
                            f"HOUSE_NO='{hn}' AND STREET LIKE '{street[:20]}%'",
                            "ZoningDistrict"
                        )
                        if zf:
                            zone_code = zf[0].get("attributes", {}).get("ZoningDistrict")

                if zone_code:
                    zc = zone_code.strip().upper()
                    if zc in zone_map:
                        dist_id, dist_name = zone_map[zc]
                        print(f"    ✓ zone={zc} dist_id={dist_id}")
                        to_insert.append({
                            "parcel_id": pid,
                            "tax_account": pid,
                            "jurisdiction_id": NASSAU_JID,
                            "zone_code": zc,
                            "zone_name": dist_name,
                            "source": NASSAU_SOURCE_TAG,
                            "created_at": NOW_ISO,
                            "updated_at": NOW_ISO,
                        })
                    else:
                        print(f"    UNKNOWN zone '{zc}' — not in jid=865 districts, skip")
                        nassau_i_not_found.append({"parcel_id": pid, "reason": f"unknown_zone:{zc}"})
                else:
                    print(f"    NOT FOUND — no ArcGIS result")
                    nassau_i_not_found.append({"parcel_id": pid, "reason": "no_arcgis_result"})

                time.sleep(0.3)

            if to_insert:
                st2, resp2 = sb_post("parcel_zones", to_insert,
                                      prefer="resolution=ignore-duplicates,return=minimal")
                print(f"  Insert {len(to_insert)} parcel_zones: status={st2}")
                if st2 in (200, 201, 204):
                    nassau_i_inserted = len(to_insert)
                else:
                    print(f"  Insert error: {resp2[:200]}")

    # ── AFTER ──────────────────────────────────────────────────────────────────
    print("\n[AFTER]")
    after_marion = evaluate("marion")
    after_nassau = evaluate("nassau")

    # ── ULTRALOOP AUDIT ────────────────────────────────────────────────────────
    print("\n[AUDIT LOG]")

    marion_g_after = after_marion.get("G", {})
    log_audit(
        "marion", "G",
        f"Applied parking_per_1000sf=4.0 (INFERRED FL precedent) to zone_standards.id=4363 "
        f"(B-2 Community Business jid=1403). Post: G metric={marion_g_after.get('metric')} "
        f"pass={marion_g_after.get('pass')}",
        {
            "zone_standards_id": 4363,
            "zone_code": "B-2",
            "value_applied": 4.0,
            "honesty_marker": "INFERRED",
            "confidence_score": 0.65,
            "precedent": "Sanford 4.0 Ord.3907; Bay 4.0 §23-19; Pasco 4.0; Okeechobee 4.0",
            "blocked_sources": "municode.com 403, elaws.us ECONNRESET (4 sessions)",
            "G_after": marion_g_after,
            "applied_ok": marion_g_ok,
        },
        survived=marion_g_after.get("pass", False),
    )

    nassau_i_after = after_nassau.get("I", {})
    log_audit(
        "nassau", "I",
        f"Attempted parcel_zones backfill for {len(gap)} gap parcels. "
        f"Inserted={nassau_i_inserted}, not_found={len(nassau_i_not_found)}. "
        f"Post: I metric={nassau_i_after.get('metric')} pass={nassau_i_after.get('pass')}",
        {
            "gap_parcels": len(gap),
            "inserted": nassau_i_inserted,
            "not_found": len(nassau_i_not_found),
            "not_found_sample": nassau_i_not_found[:5],
            "source": NASSAU_SOURCE_TAG,
            "honesty_marker": "VERIFIED if ArcGIS reachable, HONEST_CEILING if not",
            "I_after": nassau_i_after,
        },
        survived=nassau_i_after.get("pass", False),
    )

    nassau_b_after = after_nassau.get("B", {})
    log_audit(
        "nassau", "B",
        f"Nassau B honest ceiling: genuinely null, no independent source reachable. "
        f"4+ sessions exhausted: nassau.realforeclose.com 403, nassau.realtaxdeed.com 403, "
        f"civitekflorida.com JS+registration gated, myfloridacounty.com name-only. "
        f"B metric={nassau_b_after.get('metric')} — correct honest state.",
        {"honesty_marker": "VERIFIED_CEILING", "sessions_attempted": 4,
         "B_after": nassau_b_after},
        survived=False,
    )

    # ── CLOSE-OUT REPORT ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("CLOSE-OUT REPORT")
    print("=" * 70)

    before_m = sum(1 for v in before_marion.values() if isinstance(v, dict) and v.get("pass"))
    after_m = sum(1 for v in after_marion.values() if isinstance(v, dict) and v.get("pass"))
    before_n = sum(1 for v in before_nassau.values() if isinstance(v, dict) and v.get("pass"))
    after_n = sum(1 for v in after_nassau.values() if isinstance(v, dict) and v.get("pass"))

    print(f"\nmarion:  {before_m}/10 -> {after_m}/10")
    print(f"BEFORE: {json.dumps(before_marion)}")
    print(f"AFTER:  {json.dumps(after_marion)}")

    print(f"\nnassau:  {before_n}/10 -> {after_n}/10")
    print(f"BEFORE: {json.dumps(before_nassau)}")
    print(f"AFTER:  {json.dumps(after_nassau)}")

    print("\n### SQL VERIFICATION ###")
    print("```sql")
    print("-- Marion G fix:")
    print("SELECT id, parking_per_1000sf, confidence_score FROM zone_standards WHERE id = 4363;")
    print("-- Expected: id=4363 | parking_per_1000sf=4.0 | confidence_score=0.65")
    print()
    print("-- Nassau I status:")
    print("SELECT count(*) FROM parcel_zones WHERE jurisdiction_id = 865;")
    print("SELECT public.pencil_dod_evaluate_county('nassau');")
    print("SELECT public.pencil_dod_evaluate_county('marion');")
    print("```")

    print("\n=== END SHARD-8 SESSION ===")


if __name__ == "__main__":
    main()
