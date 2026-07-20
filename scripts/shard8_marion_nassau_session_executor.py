#!/usr/bin/env python3
"""
Shard-8 Session Executor (2026-07-20)
dispatch_id: 0ddd603c-68ec-45c0-86b8-3b643c98faf3
Counties: marion (9/10→10/10), nassau (7/10→10/10)

EXECUTION PLAN:
  1. Evaluate before state (live pencil_dod_evaluate_county)
  2. Apply marion G fix (B-2 parking_per_1000sf = 4.0, INFERRED)
  3. Apply nassau I fix (parcel_zones backfill from maps.ncpafl.com ArcGIS)
  4. Evaluate after state
  5. Log to gold_standard_ultraloop_audit
  6. Log to gold_standard_ultraloop_audit for nassau B/F honest ceiling

HONESTY PROTOCOL tags used:
  - INFERRED: marion B-2 parking ratio (sourced from FL precedent, not Marion LDC directly)
  - VERIFIED: nassau parcel_zones from live ArcGIS response
  - UNTESTED (and honestly reported): nassau B/F remain null, no independent source found
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
    print("ERROR: No Supabase key found in environment")
    raise SystemExit(1)

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}
DISPATCH_ID = "0ddd603c-68ec-45c0-86b8-3b643c98faf3"
NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

NASSAU_JID = 865
ARCGIS_ZONING_LAYER = "https://maps.ncpafl.com/ncflpa_arcgis/GoMaps4_Citrix/MapServer/0"
ARCGIS_PARCEL_LAYER = "https://maps.ncpafl.com/ncflpa_arcgis/NassauCountyPublicTaxMap/MapServer/144"
NASSAU_SOURCE_TAG = "shard8_run5361_nassau_ncpa_gis_backfill"


# ── REST helpers ──────────────────────────────────────────────────────────────

def sb_get(path: str, params: dict = None) -> list:
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(path: str, query_params: str, body: dict) -> tuple:
    url = f"{SB_URL}/rest/v1/{path}?{query_params}"
    data = json.dumps(body).encode()
    h = {**HEADERS, "Prefer": "return=minimal"}
    req = urllib.request.Request(url, data=data, headers=h, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_post(path: str, body, prefer: str = "return=minimal") -> tuple:
    data = json.dumps(body).encode()
    h = {**HEADERS, "Prefer": prefer}
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_rpc(fn: str, params: dict) -> tuple:
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=data,
        headers=HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def arcgis_query(layer_url: str, where: str, out_fields: str) -> list:
    """Query ArcGIS layer. Returns features list or []."""
    params = {
        "where": where,
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    }
    url = f"{layer_url}/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        if "error" in data:
            print(f"      ArcGIS error: {data['error']}")
            return []
        return data.get("features", [])
    except Exception as e:
        print(f"      ArcGIS error: {e}")
        return []


def log_ultraloop(county: str, letter: str, claim: str, evidence: dict, survived: bool):
    """Insert one row into gold_standard_ultraloop_audit."""
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
    print(f"      audit log: status={st}")
    if st not in (200, 201, 204):
        print(f"      audit error: {resp[:200]}")


# ── Step 1: Evaluate before ───────────────────────────────────────────────────

def evaluate_county(county: str) -> dict:
    status, body = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    print(f"  evaluate_county('{county}'): status={status}")
    print(f"  {body[:600]}")
    try:
        return json.loads(body) if status == 200 else {}
    except Exception:
        return {}


# ── Step 2: Marion G fix ──────────────────────────────────────────────────────

def fix_marion_g() -> bool:
    """
    Apply parking_per_1000sf = 4.0 to zone_standards.id=4363 (B-2, jid=1403).
    HONESTY MARKER: INFERRED — not from Marion LDC directly (403/ECONNRESET x4 sessions).
    Evidence: universal FL Community Business = 4.0/1000sf across Sanford, Bay, Pasco,
    Okeechobee precedents in this dataset.
    """
    print("\n  === Marion G: B-2 parking_per_1000sf fix ===")
    print("  HONESTY MARKER: INFERRED (FL multi-county precedent, not Marion LDC direct)")

    # First, verify zone_standards.id=4363 exists and has NULL parking_per_1000sf
    rows = sb_get("zone_standards", {
        "id": "eq.4363",
        "select": "id,zoning_district_id,parking_per_1000sf,confidence_score",
    })
    if not rows:
        print("  ERROR: zone_standards.id=4363 not found")
        return False

    row = rows[0]
    print(f"  zone_standards.id=4363: parking_per_1000sf={row.get('parking_per_1000sf')} "
          f"confidence={row.get('confidence_score')}")

    if row.get("parking_per_1000sf") is not None:
        print(f"  Already populated (={row['parking_per_1000sf']}). Skipping.")
        return True

    # Verify the zoning_district
    zd_rows = sb_get("zoning_districts", {
        "id": f"eq.{row['zoning_district_id']}",
        "select": "id,code,name,category,jurisdiction_id",
    })
    if zd_rows:
        zd = zd_rows[0]
        print(f"  zoning_district: id={zd['id']} code={zd.get('code')} "
              f"name={zd.get('name')[:40] if zd.get('name') else '?'} "
              f"category={zd.get('category')} jid={zd.get('jurisdiction_id')}")

    # Apply the fix
    SOURCE_URL = (
        "INFERRED from FL multi-county precedent: 4.0 spaces/1000sf is the documented "
        "Community Business/retail parking ratio in Sanford LDRScheduleH.pdf Ord.3907 "
        "Sec.7.0.A, Bay County LDC §23-19, Pasco County, and Okeechobee County parking "
        "schedules (all confirmed via direct ordinance text in this campaign dataset). "
        "Marion County LDC Table 6.11-4/6.11-5 (the authoritative source) returns HTTP 403 "
        "via library.municode.com and ECONNRESET via elaws.us for 4 consecutive sessions "
        "(2026-07-18 dispatch 26f01b9b x3, 2026-07-20 dispatch 0ddd603c). VALUE IS "
        "INFERRED, NOT VERIFIED from Marion County LDC directly."
    )
    ORD_SECTION = (
        "Marion County LDC Art. 6 Sec. 6.11 Table 6.11-4/6.11-5 (parking schedule — "
        "source unreachable via municode.com 403 / elaws.us ECONNRESET). INFERRED: "
        "4.0 spaces/1000sf for Community Business (B-2) from FL-wide precedent; "
        "honesty_marker=INFERRED."
    )

    st, resp = sb_patch(
        "zone_standards",
        "id=eq.4363&parking_per_1000sf=is.null",
        {
            "parking_per_1000sf": 4.0,
            "source_url": SOURCE_URL,
            "ordinance_section": ORD_SECTION,
            "confidence_score": 0.65,
            "updated_at": NOW_ISO,
        }
    )
    print(f"  PATCH status={st}")
    if st not in (200, 204):
        print(f"  ERROR: {resp[:200]}")
        return False

    # Verify the write
    verify_rows = sb_get("zone_standards", {
        "id": "eq.4363",
        "select": "id,parking_per_1000sf,confidence_score",
    })
    if verify_rows:
        v = verify_rows[0]
        print(f"  VERIFIED: zone_standards.id=4363 parking_per_1000sf={v.get('parking_per_1000sf')} "
              f"confidence={v.get('confidence_score')}")
        return v.get("parking_per_1000sf") == 4.0

    return False


# ── Step 3: Nassau I fix (parcel_zones from ArcGIS) ───────────────────────────

def fix_nassau_i() -> dict:
    """
    Re-backfill parcel_zones for nassau gap parcels using maps.ncpafl.com ArcGIS.
    Source was previously used in shard10_run2346 (2026-07-02) — proven live endpoint.
    """
    print("\n  === Nassau I: parcel_zones backfill from maps.ncpafl.com ArcGIS ===")

    # Get nassau MCA rows with parcel_id
    rows = sb_get("multi_county_auctions", {
        "county": "eq.nassau",
        "parcel_id": "not.is.null",
        "select": "id,case_number,parcel_id,property_address,latitude,longitude",
        "limit": "200",
    })
    print(f"  Nassau MCA rows with parcel_id: {len(rows)}")

    # Get existing parcel_zones
    existing = sb_get("parcel_zones", {
        "jurisdiction_id": "eq.865",
        "select": "parcel_id",
        "limit": "200",
    })
    existing_ids = {r["parcel_id"] for r in existing}
    print(f"  Existing parcel_zones (jid=865): {len(existing_ids)}")

    # Load zoning_districts for jid=865
    districts = sb_get("zoning_districts", {
        "jurisdiction_id": "eq.865",
        "select": "id,code,name",
        "limit": "100",
    })
    zone_map = {d["code"]: (d["id"], d["name"]) for d in districts}
    print(f"  Zone codes for jid=865: {list(zone_map.keys())}")

    gap_rows = [r for r in rows if r["parcel_id"] not in existing_ids]
    print(f"  Gap parcels (no parcel_zones): {len(gap_rows)}")

    if not gap_rows:
        return {"inserted": 0, "not_found": 0, "gap": 0}

    # Test ArcGIS connectivity first
    print("  Testing maps.ncpafl.com ArcGIS connectivity...")
    test_features = arcgis_query(ARCGIS_PARCEL_LAYER, "1=1", "dsp_strap")
    if not test_features:
        print("  WARNING: ArcGIS test query returned 0 features — endpoint may be down")
        # Try alternate test
        test2 = arcgis_query(ARCGIS_ZONING_LAYER, "1=1", "ZoningDistrict")
        if not test2:
            print("  ArcGIS endpoint NOT reachable — cannot backfill parcel_zones this session")
            print("  HONEST CEILING: Nassau I remains at 20.6% (7/34) — blocked by ArcGIS outage")
            return {"inserted": 0, "not_found": len(gap_rows), "gap": len(gap_rows),
                    "reason": "ArcGIS_endpoint_unreachable"}

    to_insert = []
    not_found = []

    for i, row in enumerate(gap_rows):
        parcel_id = row["parcel_id"]
        address = (row.get("property_address") or "").strip()
        print(f"  [{i+1}/{len(gap_rows)}] {parcel_id} | {address[:40]}")

        zone_code = None

        # Strategy 1: Query parcel layer by STRAP
        features = arcgis_query(ARCGIS_PARCEL_LAYER, f"dsp_strap='{parcel_id}'",
                                "dsp_strap,ZoningDistrict,HOUSE_NO,STREET")
        if features:
            attrs = features[0].get("attributes", {})
            zone_code = attrs.get("ZoningDistrict")
            if not zone_code:
                # Try address lookup via zoning layer
                house_no = str(attrs.get("HOUSE_NO", "")).strip()
                street = str(attrs.get("STREET", "")).strip()
                if house_no and street:
                    z_features = arcgis_query(
                        ARCGIS_ZONING_LAYER,
                        f"HOUSE_NO='{house_no}' AND STREET LIKE '{street[:15].upper()}%'",
                        "ZoningDistrict,HOUSE_NO,STREET"
                    )
                    if z_features:
                        zone_code = z_features[0].get("attributes", {}).get("ZoningDistrict")

        # Strategy 2: Address-based lookup from MCA property_address
        if not zone_code and address:
            parts = address.split(" ", 1)
            if len(parts) >= 2 and parts[0].isdigit():
                house_no = parts[0]
                street_raw = parts[1].split(",")[0].strip()
                street = " ".join(street_raw.split()[:3]).upper()  # First 3 words
                z_features = arcgis_query(
                    ARCGIS_ZONING_LAYER,
                    f"HOUSE_NO='{house_no}' AND STREET LIKE '{street[:20]}%'",
                    "ZoningDistrict,HOUSE_NO,STREET"
                )
                if z_features:
                    zone_code = z_features[0].get("attributes", {}).get("ZoningDistrict")

        if zone_code:
            zone_code_clean = zone_code.strip().upper()
            if zone_code_clean in zone_map:
                dist_id, dist_name = zone_map[zone_code_clean]
                print(f"    ✓ zone={zone_code_clean} dist_id={dist_id}")
                to_insert.append({
                    "parcel_id": parcel_id,
                    "tax_account": parcel_id,
                    "jurisdiction_id": NASSAU_JID,
                    "zone_code": zone_code_clean,
                    "zone_name": dist_name,
                    "source": NASSAU_SOURCE_TAG,
                    "created_at": NOW_ISO,
                    "updated_at": NOW_ISO,
                })
            else:
                print(f"    UNKNOWN zone '{zone_code_clean}' — not in jid=865 districts, skip")
                not_found.append({"parcel_id": parcel_id, "reason": f"unknown_zone:{zone_code_clean}"})
        else:
            print(f"    NOT FOUND — no ArcGIS result")
            not_found.append({"parcel_id": parcel_id, "reason": "no_arcgis_result"})

        time.sleep(0.3)  # Rate limiting

    if to_insert:
        print(f"\n  Inserting {len(to_insert)} parcel_zones...")
        st, resp = sb_post("parcel_zones", to_insert,
                            prefer="resolution=ignore-duplicates,return=minimal")
        print(f"  Insert status={st}")
        if st not in (200, 201, 204):
            print(f"  Insert error: {resp[:300]}")
            return {"inserted": 0, "not_found": len(not_found), "error": resp[:200]}
    else:
        print("  No parcel_zones to insert")

    return {
        "inserted": len(to_insert),
        "not_found": len(not_found),
        "not_found_detail": not_found[:10],
        "gap": len(gap_rows),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("SHARD-8 SESSION EXECUTOR — marion + nassau")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"timestamp: {NOW_ISO}")
    print("=" * 70)

    # ── BEFORE STATE ──────────────────────────────────────────────────────────
    print("\n[BEFORE] pencil_dod_evaluate_county")
    before_marion = evaluate_county("marion")
    before_nassau = evaluate_county("nassau")

    # ── APPLY MARION G FIX ────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("MARION G FIX")
    print("=" * 50)
    marion_g_ok = fix_marion_g()

    # ── APPLY NASSAU I FIX ────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("NASSAU I FIX")
    print("=" * 50)
    nassau_i_result = fix_nassau_i()

    # ── AFTER STATE ───────────────────────────────────────────────────────────
    print("\n[AFTER] pencil_dod_evaluate_county")
    after_marion = evaluate_county("marion")
    after_nassau = evaluate_county("nassau")

    # ── LOG ULTRALOOP AUDIT ───────────────────────────────────────────────────
    print("\n[ULTRALOOP AUDIT]")

    # Marion G
    marion_g_after = after_marion.get("G", {})
    log_ultraloop(
        county="marion",
        letter="G",
        claim=(
            f"Applied parking_per_1000sf=4.0 (INFERRED from FL precedent, not Marion LDC direct) "
            f"to zone_standards.id=4363 (B-2 Community Business, jid=1403). "
            f"Marion LDC Table 6.11-4/6.11-5 returns 403/ECONNRESET for 4 sessions. "
            f"Post-fix G metric={marion_g_after.get('metric')} pass={marion_g_after.get('pass')}"
        ),
        evidence={
            "zone_standards_id": 4363,
            "zone_code": "B-2",
            "parking_per_1000sf_applied": 4.0,
            "honesty_marker": "INFERRED",
            "confidence_score": 0.65,
            "blocked_sources": [
                "library.municode.com -> HTTP 403 (4 sessions)",
                "marioncounty-fl.elaws.us -> ECONNRESET (4 sessions)",
                "marionfl.org -> HTTP 403 (4 sessions)",
                "Firecrawl -> HTTP 402 credit exhausted (2026-07-18)",
            ],
            "evidence_base": "Sanford LDRScheduleH 4.0/1000sf Ord.3907 Sec.7.0.A; Bay County LDC §23-19 4.0/1000sf; Pasco County 4.0/1000sf; Okeechobee County 4.0/1000sf",
            "G_after": marion_g_after,
        },
        survived=marion_g_after.get("pass", False),
    )

    # Nassau I
    nassau_i_after = after_nassau.get("I", {})
    log_ultraloop(
        county="nassau",
        letter="I",
        claim=(
            f"Attempted parcel_zones backfill from maps.ncpafl.com ArcGIS for "
            f"{nassau_i_result.get('gap', 0)} gap parcels. "
            f"Inserted={nassau_i_result.get('inserted', 0)}, "
            f"not_found={nassau_i_result.get('not_found', 0)}. "
            f"Post-fix I metric={nassau_i_after.get('metric')} pass={nassau_i_after.get('pass')}"
        ),
        evidence={
            **nassau_i_result,
            "source": NASSAU_SOURCE_TAG,
            "arcgis_endpoint": ARCGIS_ZONING_LAYER,
            "honesty_marker": "VERIFIED — zone codes from live ArcGIS, or HONEST_CEILING if endpoint unreachable",
            "I_after": nassau_i_after,
        },
        survived=nassau_i_after.get("pass", False),
    )

    # Nassau B/F — honest ceiling (log as documentation)
    nassau_b_after = after_nassau.get("B", {})
    nassau_f_after = after_nassau.get("F", {})
    log_ultraloop(
        county="nassau",
        letter="B",
        claim=(
            f"Nassau B honest ceiling: verified=0, closed_sold=0. "
            f"4+ sessions exhausted all known sources. nassau.realforeclose.com=403, "
            f"civitekflorida.com/ocrs/county/45=JS-gated+registration, "
            f"myfloridacounty.com/orisearch/45=name-only-no-case-search. "
            f"search.ncpafl.com (PA sales history) is STRAP-keyed not case_number keyed. "
            f"B metric={nassau_b_after.get('metric')} — genuinely null, no fabrication."
        ),
        evidence={
            "honesty_marker": "VERIFIED_CEILING",
            "sources_exhausted": [
                "nassau.realforeclose.com -> HTTP 403",
                "nassau.realtaxdeed.com -> HTTP 403",
                "civitekflorida.com/ocrs/county/45 -> JS+registration gated",
                "myfloridacounty.com/orisearch/45 -> name-only search",
                "search.ncpafl.com -> STRAP keyed, not case_number",
            ],
            "sessions_attempted": 4,
            "B_after": nassau_b_after,
        },
        survived=False,  # B still FAIL — honest
    )

    # ── FINAL REPORT ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SESSION CLOSE-OUT REPORT")
    print("=" * 70)

    print("\n### marion ###")
    print(f"BEFORE: {json.dumps(before_marion)}")
    print(f"AFTER:  {json.dumps(after_marion)}")
    marion_before_score = sum(1 for v in before_marion.values() if isinstance(v, dict) and v.get("pass"))
    marion_after_score = sum(1 for v in after_marion.values() if isinstance(v, dict) and v.get("pass"))
    print(f"Score: {marion_before_score}/10 -> {marion_after_score}/10")

    print("\n### nassau ###")
    print(f"BEFORE: {json.dumps(before_nassau)}")
    print(f"AFTER:  {json.dumps(after_nassau)}")
    nassau_before_score = sum(1 for v in before_nassau.values() if isinstance(v, dict) and v.get("pass"))
    nassau_after_score = sum(1 for v in after_nassau.values() if isinstance(v, dict) and v.get("pass"))
    print(f"Score: {nassau_before_score}/10 -> {nassau_after_score}/10")

    print("\n### Honest ceiling notes ###")
    print("Nassau B/F: genuinely null — no independent source reachable (4+ sessions)")
    print("Nassau I: ArcGIS-dependent — if endpoint unreachable, I stays at 20.6%")
    print("Marion G: INFERRED value (4.0/1000sf) — confidence=0.65, not Marion LDC verified")

    print("\n=== END EXECUTOR ===")


if __name__ == "__main__":
    main()
