#!/usr/bin/env python3
"""BidDeed Reels pipeline v1 -- daily short-form reel generation for
third-party Florida auction wins (issue #19736).

GENERATES AND STAGES ONLY. Never posts, never sends. Every row lands at
status='pending_approval' or 'error' (with error_text) -- nothing in this
script sets status to 'approved'/'posted'.

Run:
  python scripts/biddeed_reels_pipeline.py [--auction-date YYYY-MM-DD]
    [--force] [--dry-run] [--limit N]

Required env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN,
  GOOGLE_MAPS_API_KEY, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY.
"""
import argparse
import os
import sys
import tempfile
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biddeed_reels_lib as lib


def get_yesterday():
    rows = lib.run_sql("select (current_date - interval '1 day')::date::text as d;")
    return rows[0]["d"]


def get_third_party_wins(auction_date: str) -> list[dict]:
    params = (
        "select=case_number,county,sale_type,auction_date,property_address,sold_amount"
        f"&buyer_type=eq.third_party&auction_date=eq.{auction_date}"
    )
    return lib.pg_rest("auction_buyer_sightings", params, timeout=60)


def get_existing_reel(case_number: str, county: str) -> dict | None:
    rows = lib.run_sql(
        f"""select video_url, voiceover_source, audio_url, status
            from winnerdata.biddeed_reels
            where case_number = {lib.sql_str(case_number)} and county = {lib.sql_str(county)};"""
    )
    return rows[0] if rows else None


def upsert_reel(row: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY-RUN] Would upsert biddeed_reels({row.get('case_number')}, {row.get('county')}) "
              f"status={row.get('status')}")
        return
    cols = list(row.keys())
    set_clause = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in ("case_number", "county"))
    col_list = ", ".join(cols)
    val_list = ", ".join(_sql_val(c, row[c]) for c in cols)
    lib.run_sql(f"""
        insert into winnerdata.biddeed_reels ({col_list}, updated_at)
        values ({val_list}, now())
        on conflict (case_number, county) do update set {set_clause}, updated_at = now();
    """)


def _sql_val(col: str, v):
    if col in ("sold_amount", "assessed_value", "delta_pct", "condition_score", "duration_sec", "rank_score"):
        return lib.sql_num(v)
    if col == "hashtags":
        return lib.sql_text_array(v)
    if col == "condition_json":
        return lib.sql_jsonb(v)
    if col == "shortlisted":
        return lib.sql_bool(v)
    return lib.sql_str(v)


def process_row(sighting: dict, force: bool, dry_run: bool, keys: dict) -> dict:
    """Returns a per-row result dict for the T9 summary. Never raises -- all
    failures are caught and written as status='error' + error_text so one
    bad property never aborts the batch (T8 per-row error isolation)."""
    case_number = sighting["case_number"]
    county = sighting["county"]
    result = {"case_number": case_number, "county": county, "status": None,
              "error": None, "image_calls": 0, "tts_chars": 0}

    base_row = {
        "case_number": case_number, "county": county,
        "sale_type": sighting.get("sale_type"),
        "auction_date": sighting["auction_date"],
        "property_address": sighting.get("property_address"),
        "sold_amount": sighting.get("sold_amount"),
    }

    try:
        existing = get_existing_reel(case_number, county)
        if existing and existing.get("video_url") and not force:
            result["status"] = "skipped_has_video"
            return result

        parcel = lib.match_parcel(sighting.get("property_address", ""), county)
        if not parcel or parcel.get("centroid_lat") is None or parcel.get("centroid_lon") is None:
            row = dict(base_row, status="error",
                       error_text="no zw_parcels match (or missing lat/lon) for property_address")
            upsert_reel(row, dry_run)
            result["status"] = "error"
            result["error"] = row["error_text"]
            return result

        lat, lon = parcel["centroid_lat"], parcel["centroid_lon"]
        assessed_value = parcel.get("val_assessed")

        with tempfile.TemporaryDirectory() as tmp:
            aerial_path = os.path.join(tmp, "aerial.png")
            lib.fetch_static_map(lat, lon, aerial_path, keys["google_maps"])
            result["image_calls"] += 1

            street_path = None
            street_url = None
            if lib.streetview_metadata_ok(lat, lon, keys["google_maps"]):
                street_path = os.path.join(tmp, "street.jpg")
                lib.fetch_streetview(lat, lon, street_path, keys["google_maps"])
                result["image_calls"] += 1

            date_key = sighting["auction_date"]
            case_key = urllib.parse.quote(case_number.replace(" ", "_").replace("/", "-"), safe="")
            prefix = f"{date_key}/{case_key}"

            aerial_url = lib.storage_upload(aerial_path, f"{prefix}/aerial.png", "image/png")
            if street_path:
                street_url = lib.storage_upload(street_path, f"{prefix}/street.jpg", "image/jpeg")

            image_paths = [aerial_path] + ([street_path] if street_path else [])
            condition = lib.score_condition(image_paths, keys["anthropic"])
            condition_score = int(round(condition["condition_score"]))

            sale_and_caption = lib.build_script_and_caption(
                county, sighting.get("sale_type"), sighting.get("sold_amount"),
                assessed_value, condition,
            )
            delta_pct = sale_and_caption["delta_pct"]

            if existing and existing.get("voiceover_source") == "ariel" and existing.get("audio_url"):
                audio_url = existing["audio_url"]
                voiceover_source = "ariel"
                audio_path = None
            else:
                audio_path = os.path.join(tmp, "voice.mp3")
                lib.elevenlabs_tts(sale_and_caption["script_text"], keys["elevenlabs"], audio_path)
                result["tts_chars"] += len(sale_and_caption["script_text"])
                audio_url = lib.storage_upload(audio_path, f"{prefix}/voice.mp3", "audio/mpeg")
                voiceover_source = "tts"

            if audio_path is None:
                # Ariel-recorded override: download it locally so ffmpeg can mux it.
                import urllib.request
                audio_path = os.path.join(tmp, "voice_override.mp3")
                urllib.request.urlretrieve(audio_url, audio_path)

            tier = condition.get("general_condition_tier", "unknown")
            sale_type_raw = sighting.get("sale_type") or ""
            overlays = {
                "county": lib.county_display(county),
                "sale_type_label": sale_type_raw.replace("_", " ").upper(),
                "sold_amount": sighting.get("sold_amount"),
                "assessed_value": assessed_value,
                "condition_badge": f"{tier.title()} condition" if tier != "unknown" else "",
            }
            video_path = os.path.join(tmp, "reel.mp4")
            duration_sec = lib.assemble_video(aerial_path, street_path, audio_path, overlays, video_path)
            video_url = lib.storage_upload(video_path, f"{prefix}/reel.mp4", "video/mp4")

            score = lib.rank_score(delta_pct, condition_score, sighting.get("sold_amount"))

            row = dict(
                base_row,
                parcel_id=parcel.get("pin_clean"),
                assessed_value=assessed_value,
                delta_pct=delta_pct,
                aerial_url=aerial_url,
                street_url=street_url,
                condition_json=condition,
                condition_score=condition_score,
                script_text=sale_and_caption["script_text"],
                caption_text=sale_and_caption["caption_text"],
                hashtags=sale_and_caption["hashtags"],
                voiceover_source=voiceover_source,
                audio_url=audio_url,
                video_url=video_url,
                duration_sec=round(duration_sec, 2),
                rank_score=score,
                status="pending_approval",
                error_text=None,
            )
            upsert_reel(row, dry_run)
            result["status"] = "pending_approval"
            result["rank_score"] = score
            result["video_url"] = video_url
            return result

    except Exception as e:
        row = dict(base_row, status="error", error_text=str(e)[:2000])
        try:
            upsert_reel(row, dry_run)
        except Exception as write_err:
            print(f"  WARN: also failed to write error row for {case_number}/{county}: {write_err}", file=sys.stderr)
        result["status"] = "error"
        result["error"] = str(e)[:500]
        return result


def apply_shortlist(auction_date: str, dry_run: bool, top_n: int = 5) -> list[dict]:
    if dry_run:
        print(f"[DRY-RUN] Would shortlist top {top_n} by rank_score for {auction_date}")
        return []
    lib.run_sql(f"""
        update winnerdata.biddeed_reels set shortlisted = false, updated_at = now()
        where auction_date = {lib.sql_str(auction_date)} and shortlisted = true;
    """)
    top = lib.run_sql(f"""
        select id, case_number, county, rank_score, video_url
        from winnerdata.biddeed_reels
        where auction_date = {lib.sql_str(auction_date)} and status = 'pending_approval'
        order by rank_score desc nulls last
        limit {top_n};
    """)
    for r in top:
        lib.run_sql(f"""
            update winnerdata.biddeed_reels set shortlisted = true, updated_at = now()
            where id = {lib.sql_str(r['id'])};
        """)
    return top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auction-date", default=None, help="YYYY-MM-DD, defaults to yesterday (UTC)")
    ap.add_argument("--force", action="store_true", help="re-render rows that already have a video_url")
    ap.add_argument("--dry-run", action="store_true", help="no DB writes, no external API calls beyond the read query")
    ap.add_argument("--limit", type=int, default=None, help="cap number of rows processed (testing only)")
    args = ap.parse_args()

    auction_date = args.auction_date or get_yesterday()
    print(f"Auction date: {auction_date}")

    keys = {
        "google_maps": os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        "elevenlabs": os.environ.get("ELEVENLABS_API_KEY", ""),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
    }
    missing = [k for k, v in keys.items() if not v and not args.dry_run]
    if missing:
        print(f"ERROR: missing required env vars for: {missing}", file=sys.stderr)
        sys.exit(1)

    sightings = get_third_party_wins(auction_date)
    print(f"{len(sightings)} third-party win(s) for {auction_date}.")
    if args.limit:
        sightings = sightings[: args.limit]

    t0 = time.time()
    results = []
    for s in sightings:
        print(f"Processing {s['case_number']} / {s['county']} ...")
        r = process_row(s, args.force, args.dry_run, keys)
        print(f"  -> {r['status']}" + (f" ({r['error']})" if r.get("error") else ""))
        results.append(r)

    shortlisted = apply_shortlist(auction_date, args.dry_run)
    wall_time = time.time() - t0

    n_ok = sum(1 for r in results if r["status"] == "pending_approval")
    n_err = sum(1 for r in results if r["status"] == "error")
    n_skip = sum(1 for r in results if r["status"] == "skipped_has_video")
    total_images = sum(r["image_calls"] for r in results)
    total_tts_chars = sum(r["tts_chars"] for r in results)

    print("\n=== SUMMARY ===")
    print(f"auction_date={auction_date} rows={len(results)} pending_approval={n_ok} error={n_err} "
          f"skipped_has_video={n_skip}")
    print(f"image_calls_total={total_images} tts_chars_total={total_tts_chars} wall_time_sec={wall_time:.1f}")
    print(f"shortlisted={len(shortlisted)}")
    for r in sorted(shortlisted, key=lambda x: x.get("rank_score") or 0, reverse=True):
        print(f"  #{r['case_number']} / {r['county']} rank_score={r['rank_score']} video_url={r['video_url']}")

    errored = [r for r in results if r["status"] == "error"]
    if errored:
        print("\n=== ERRORS ===")
        for r in errored:
            print(f"  {r['case_number']} / {r['county']}: {r['error']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
