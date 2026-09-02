#!/usr/bin/env python3
"""BidDeed Reels v2 -- parcel-outline imagery, hook-first edit, per-property
landing page + QR/UTM click path (issue #19752, builds on v1 #19736).

GENERATES AND STAGES ONLY. Never posts, never sends. Re-renders existing
winnerdata.biddeed_reels rows in place: v1's own aerial_url/street_url/
video_url/script_text/caption_text are left untouched ("keep v1 video_url
for comparison" per the issue) -- this script only ever writes the NEW v2
columns (zw_parcel_id, parcel_geojson, parcel_outline, aerial_wide_url,
aerial_tight_url, short_code, short_url, qr_url, landing_url, video_v2_url,
edit_version) plus overwrites script_text/caption_text/hashtags/delta_pct
with the v2 beat-list versions (condition_json/condition_score are REUSED
from v1, not re-scored -- no new T3 vision spend needed to re-cut the edit).

Run:
  python scripts/biddeed_reels_pipeline_v2.py [--auction-date YYYY-MM-DD]
    [--force] [--limit N] [--only CASE_NUMBER]

Required env/vault: same as v1 (biddeed_reels_pipeline.py) minus the T3
vision keys (reused from the existing condition_json) -- GOOGLE_MAPS_API_KEY
and ELEVENLABS_API_KEY (voiceover is regenerated against the new v2 script).
"""
import argparse
import json
import os
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biddeed_reels_lib as lib

LANDING_BASE = "https://biddeed.ai/deal"
SHORT_BASE = "https://biddeed.ai/r"


def get_v1_rows(auction_date: str) -> list[dict]:
    rows = lib.run_sql(f"""
        select id, case_number, county, sale_type, auction_date, property_address,
               sold_amount, parcel_id, assessed_value, condition_json, condition_score,
               video_v2_url, short_code, aerial_wide_url, aerial_tight_url, street_url,
               zw_parcel_id, parcel_geojson, parcel_outline
        from winnerdata.biddeed_reels
        where auction_date = {lib.sql_str(auction_date)}
          and status = 'pending_approval'
        order by county, case_number;
    """)
    return rows


def _sql_val(col: str, v):
    if col in ("sold_amount", "assessed_value", "delta_pct", "condition_score",
               "duration_sec", "rank_score", "zw_parcel_id", "edit_version"):
        return lib.sql_num(v)
    if col == "hashtags":
        return lib.sql_text_array(v)
    if col in ("condition_json", "parcel_geojson"):
        return lib.sql_jsonb(v)
    if col == "parcel_outline":
        return lib.sql_bool(v)
    return lib.sql_str(v)


def update_row(row_id: str, fields: dict) -> None:
    set_clause = ", ".join(f"{c} = {_sql_val(c, v)}" for c, v in fields.items())
    lib.run_sql(f"""
        update winnerdata.biddeed_reels
        set {set_clause}, updated_at = now()
        where id = {lib.sql_str(row_id)};
    """)


def ensure_short_link(reel_id: str, existing_code: str | None, landing_url: str) -> tuple[str, str]:
    """Idempotent: reuses an existing short_code on --force re-runs instead
    of minting a new one and orphaning the old link."""
    if existing_code:
        code = existing_code
        lib.run_sql(f"""
            update winnerdata.reel_links set target = {lib.sql_str(landing_url)}, updated_at = now()
            where code = {lib.sql_str(code)};
        """)
    else:
        for _ in range(5):
            code = lib.gen_short_code()
            rows = lib.run_sql(f"select 1 from winnerdata.reel_links where code = {lib.sql_str(code)};")
            if not rows:
                break
        lib.run_sql(f"""
            insert into winnerdata.reel_links (code, reel_id, target, utm_source, utm_medium, utm_campaign)
            values ({lib.sql_str(code)}, {lib.sql_str(reel_id)}, {lib.sql_str(landing_url)},
                    'reel', 'social', 'biddeed_reels_v2');
        """)
    return code, f"{SHORT_BASE}/{code}"


def process_row_v2(row: dict, force: bool, keys: dict) -> dict:
    case_number = row["case_number"]
    county = row["county"]
    result = {"case_number": case_number, "county": county, "status": None, "error": None}

    if row.get("video_v2_url") and not force:
        result["status"] = "skipped_has_v2"
        return result

    # Directive #4A (Ariel, 2026-09-02 21:16 EDT): re-rendering an already-
    # imaged row (script/pill/PCT/voice fixes) must not re-spend Maps quota.
    # If this row already has v2 stills from an earlier run, pull them back
    # down instead of re-calling Static Maps/Street View/Geocoding.
    reuse_imagery = bool(force and row.get("aerial_wide_url") and row.get("aerial_tight_url") and row.get("street_url"))

    try:
        parcel_id = row.get("parcel_id")
        # numeric columns come back as JSON strings from the Management API
        # (pg numeric -> JSON text, to avoid float-precision surprises) --
        # coerce here so downstream arithmetic/formatting doesn't type-error.
        assessed_value = float(row["assessed_value"]) if row.get("assessed_value") is not None else None
        sold_amount = float(row["sold_amount"])
        condition = row.get("condition_json")
        if not condition:
            raise RuntimeError("no v1 condition_json to reuse -- run v1 pipeline first")

        geom_row = lib.match_zw_parcel_geom(county, parcel_id) if parcel_id else None

        date_key = row["auction_date"].isoformat() if hasattr(row["auction_date"], "isoformat") else row["auction_date"]
        import urllib.parse as up
        case_key = up.quote(case_number.replace(" ", "_").replace("/", "-"), safe="")
        prefix = f"{date_key}/{case_key}"

        with tempfile.TemporaryDirectory() as tmp:
            wide_path = os.path.join(tmp, "aerial_wide.png")
            tight_path = os.path.join(tmp, "aerial_tight.png")
            street_path = os.path.join(tmp, "street.jpg")

            if reuse_imagery:
                lib.fetch_url_to_file(row["aerial_wide_url"], wide_path)
                lib.fetch_url_to_file(row["aerial_tight_url"], tight_path)
                lib.fetch_url_to_file(row["street_url"], street_path)
                aerial_wide_url = row["aerial_wide_url"]
                aerial_tight_url = row["aerial_tight_url"]
                street_url = row["street_url"]
                zw_parcel_id = row.get("zw_parcel_id")
                parcel_geojson = row.get("parcel_geojson")
                parcel_outline = bool(row.get("parcel_outline"))
            else:
                lat = lon = None
                parcel_geojson = None
                parcel_outline = False

                if geom_row and geom_row.get("centroid_lat") is not None:
                    lat, lon = float(geom_row["centroid_lat"]), float(geom_row["centroid_lon"])
                    parcel_geojson = json.loads(geom_row["geojson"])
                    ring = lib.geojson_ring_latlng(parcel_geojson)
                    wide_url, tight_url = lib.build_parcel_aerial_urls(lat, lon, ring, keys["google_maps"])
                    parcel_outline = True
                    zw_parcel_id = geom_row["zw_parcel_id"]
                else:
                    # No geometry match -- fall back to geocoding the raw address
                    # (same fallback path v1 established) then a pin marker.
                    geocoded = lib.geocode_address(row.get("property_address", ""), keys["google_maps"])
                    if not geocoded:
                        raise RuntimeError("no zw_parcels geometry AND geocode miss -- cannot build v2 imagery")
                    lat, lon = geocoded
                    wide_url, tight_url = lib.build_pin_aerial_urls(lat, lon, keys["google_maps"])
                    zw_parcel_id = None

                lib.fetch_url_to_file(wide_url, wide_path)
                lib.fetch_url_to_file(tight_url, tight_path)

                if lib.streetview_metadata_ok(lat, lon, keys["google_maps"]):
                    lib.fetch_streetview(lat, lon, street_path, keys["google_maps"])
                    street_url = lib.storage_upload(street_path, f"{prefix}/street_v2.jpg", "image/jpeg")
                else:
                    # T1: "substitute a second tight aerial at zoom 19" so the
                    # edit never has a hole where Street View would have been.
                    sub_url = lib.build_tight_aerial_url(lat, lon, 19, keys["google_maps"])
                    lib.fetch_url_to_file(sub_url, street_path)
                    street_url = lib.storage_upload(street_path, f"{prefix}/aerial_z19_sub.jpg", "image/jpeg")

                aerial_wide_url = lib.storage_upload(wide_path, f"{prefix}/aerial_wide.png", "image/png")
                aerial_tight_url = lib.storage_upload(tight_path, f"{prefix}/aerial_tight.png", "image/png")

            # T3: short link + QR. landing_url built first (short link
            # target), short code minted/reused, QR encodes the SHORT link
            # (not the landing URL directly) per the click-path design.
            slug = lib.slugify_case_number(case_number)
            county_slug = county.replace("_", "-")
            landing_url = f"{LANDING_BASE}/{county_slug}/{slug}"
            short_code, short_url = ensure_short_link(row["id"], row.get("short_code"), landing_url)

            qr_path = os.path.join(tmp, "qr.png")
            lib.generate_qr_png(short_url, qr_path)
            qr_url = lib.storage_upload(qr_path, f"{prefix}/qr.png", "image/png")

            # T4: v2 script/caption (hook-first beat list), reusing v1's
            # already-scored condition_json -- no new T3 vision spend.
            sc = lib.build_script_and_caption_v2(county, row.get("sale_type"), sold_amount,
                                                  assessed_value, condition, short_url)
            delta_pct = sc["delta_pct"]

            # Directive #4 (Ariel, 2026-09-02 21:16 EDT): v2 voiceover must be
            # eleven_v3 with inline audio tags, not v1's Flash path.
            audio_path = os.path.join(tmp, "voice_v2.mp3")
            lib.elevenlabs_tts_v3(sc["script_text_v3"], keys["elevenlabs"], audio_path)
            audio_url = lib.storage_upload(audio_path, f"{prefix}/voice_v2.mp3", "audio/mpeg")

            tier = condition.get("general_condition_tier", "unknown")
            bullets = []
            for key_name in ("roof", "exterior", "vegetation_overgrowth"):
                obs = (condition.get(key_name) or {}).get("observation")
                if obs:
                    bullets.append(lib.condition_pill_label(key_name, obs))
            overlays = {
                "county": lib.county_display(county).replace(" County", ""),
                "sale_type_label": (row.get("sale_type") or "").replace("_", " ").upper(),
                "sold_amount": sold_amount,
                "assessed_value": assessed_value,
                "delta_pct": delta_pct,
                "condition_tier": tier,
                "condition_bullets": bullets[:2],
            }
            images = {
                "hook": tight_path, "reveal": wide_path, "street": street_path,
                "condition": tight_path, "payoff": wide_path,
            }
            video_path = os.path.join(tmp, "reel_v2.mp4")
            duration_sec = lib.assemble_video_v2(images, audio_path, overlays, qr_path, short_url, video_path)
            video_v2_url = lib.storage_upload(video_path, f"{prefix}/reel_v2.mp4", "video/mp4")

            update_row(row["id"], {
                "zw_parcel_id": zw_parcel_id,
                "parcel_geojson": parcel_geojson,
                "parcel_outline": parcel_outline,
                "aerial_wide_url": aerial_wide_url,
                "aerial_tight_url": aerial_tight_url,
                "street_url": street_url,
                "short_code": short_code,
                "short_url": short_url,
                "qr_url": qr_url,
                "landing_url": landing_url,
                "video_v2_url": video_v2_url,
                "duration_sec": round(duration_sec, 2),
                "edit_version": 2,
                "script_text": sc["script_text"],
                "caption_text": sc["caption_text"],
                "hashtags": sc["hashtags"],
                "delta_pct": delta_pct,
                "audio_url": audio_url,
                "tts_model": lib.V2_TTS_MODEL,
                "voice_id": os.environ.get("ELEVENLABS_V2_VOICE_ID", lib.V2_BRAND_VOICE_ID),
            })

            result.update({
                "status": "v2_done", "parcel_outline": parcel_outline,
                "street_or_substitute": "street" if "street_v2" in (street_url or "") else "substitute_aerial",
                "duration_sec": round(duration_sec, 2), "video_v2_url": video_v2_url,
                "landing_url": f"{landing_url}?preview={row['id']}", "short_url": short_url,
            })
            return result

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:800]
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auction-date", default="2026-09-01")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default=None, help="case_number substring filter")
    args = ap.parse_args()

    def resolve_key(env_name, vault_names):
        v = os.environ.get(env_name, "")
        if v:
            return v
        for name in vault_names:
            try:
                return lib.get_vault_secret(name)
            except Exception:
                continue
        return ""

    keys = {
        "google_maps": resolve_key("GOOGLE_MAPS_API_KEY", ["google_maps_api_key"]),
        "elevenlabs": resolve_key("ELEVENLABS_API_KEY", ["elevenlabs_api_key", "elevenlabs_production"]),
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        print(f"ERROR: missing keys: {missing}", file=sys.stderr)
        sys.exit(1)

    rows = get_v1_rows(args.auction_date)
    if args.only:
        rows = [r for r in rows if args.only in r["case_number"]]
    if args.limit:
        rows = rows[: args.limit]

    print(f"{len(rows)} row(s) to process for {args.auction_date}.")
    t0 = time.time()
    results = []
    for r in rows:
        print(f"Processing {r['case_number']} / {r['county']} ...")
        res = process_row_v2(r, args.force, keys)
        print(f"  -> {res['status']}" + (f" ({res['error']})" if res.get("error") else ""))
        results.append(res)

    n_ok = sum(1 for r in results if r["status"] == "v2_done")
    n_err = sum(1 for r in results if r["status"] == "error")
    n_skip = sum(1 for r in results if r["status"] == "skipped_has_v2")
    print("\n=== SUMMARY ===")
    print(f"rows={len(results)} v2_done={n_ok} error={n_err} skipped={n_skip} "
          f"wall_time_sec={time.time()-t0:.1f}")
    for r in results:
        if r["status"] == "v2_done":
            print(f"  {r['case_number']}/{r['county']}: outline={r['parcel_outline']} "
                  f"street={r['street_or_substitute']} dur={r['duration_sec']}s "
                  f"video={r['video_v2_url']} landing={r['landing_url']} short={r['short_url']}")
    errored = [r for r in results if r["status"] == "error"]
    if errored:
        print("\n=== ERRORS ===")
        for r in errored:
            print(f"  {r['case_number']}/{r['county']}: {r['error']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
