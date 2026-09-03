#!/usr/bin/env python3
"""BidDeed Reels pipeline v1 -- daily short-form reel generation for
third-party Florida auction wins (issue #19736).

GENERATES AND STAGES ONLY. Never posts, never sends. Every row lands at
status='pending_approval' or 'error' (with error_text) -- nothing in this
script sets status to 'approved'/'posted'.

Run:
  python scripts/biddeed_reels_pipeline.py [--auction-date YYYY-MM-DD]
    [--force] [--dry-run] [--limit N]

Required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN env
  vars, plus GOOGLE_MAPS_API_KEY, ELEVENLABS_API_KEY, OPENROUTER_API_KEY,
  ROUTER_PROXY_KEY -- either as env vars (GHA runner) or resolved from the
  Supabase vault at runtime (see resolve_key() in main()). T3 condition
  scoring calls OpenRouter directly (z-ai/glm-5.3-flash primary, DeepSeek
  vision fallback) with the claude-router edge function (ROUTER_PROXY_KEY /
  vault router_proxy_key) as the final fallback tier.
"""
import argparse
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request

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


def get_reel_candidates(start_date: str, end_date: str) -> list[dict]:
    """issue #19794 -- reel-candidate query, extended over a date RANGE
    (not a single auction_date) and sale-type-aware on the buyer_type gate.

    Two real, verified findings from #19794's investigation drove this:

    1. STARVATION WAS A CADENCE GAP, NOT A COVERAGE GAP. The upstream tables
       (public.auction_buyer_sightings / public.multi_county_auctions)
       already carry far more tax_deed candidates than winnerdata.biddeed_reels
       has ever rendered -- verified live 2026-09-03: 88 tax_deed/third_party
       sightings in the trailing 14 days across 9 counties (vs. biddeed_reels'
       3 tax_deed rows), because the v1 pipeline has only ever been invoked
       for one or two discrete auction_date values, never a rolling window.
       Widening the query to a date range is the actual fix.

    2. FORECLOSURE-SPECIFIC VALIDATION WAS LEAKING ONTO TAX_DEED ROWS. The
       old query required buyer_type='third_party' for every sale_type. That
       gate exists because a foreclosure sold_amount alone is AMBIGUOUS -- the
       plaintiff/bank can bid the judgment and reclaim the property, so a real
       third-party buyer must be independently confirmed. Florida tax deed
       sales are ABSOLUTE AUCTIONS: no plaintiff/bank can reclaim, so
       sold_amount > 0 is BY ITSELF sufficient proof of a genuine third-party
       sale (see docs/gtm/REEL_SPEC_BOLT32.md "Absolute Auction Data-Quality
       Assertion"). Requiring buyer_type='third_party' for tax_deed rows
       silently drops real sales whose buyer_type was simply never classified
       -- live-verified: 7 real Flagler County tax_deed sales (sold_amount
       populated, e.g. $208,900.00 on 2025-08-12) sitting in
       auction_buyer_sightings with buyer_type IS NULL, invisible to the old
       query. This function keeps the third_party gate for foreclosure and
       drops it for tax_deed (still excluding any row explicitly classified
       buyer_type='plaintiff', which would mean a reclaim, not a sale).

    public.clerk_ssot_sale_rows (the clerk-scraped tax-deed calendar table
    this issue was framed around) is wired in as a SECOND, ADDITIVE source
    for tax_deed only, de-duplicated against auction_buyer_sightings on
    (county, normalized case_number) so a sale is never double-counted
    (negative test (b)). It is deliberately NOT the primary source: verified
    live 2026-09-03, clerk_ssot_sale_rows has no sold_amount column at all
    (it is a scheduling/docket table, not a results table); of its 11,396
    tax_deed rows, only ~3,655 carry a "sold"-shaped status token in
    raw_comment (free text, format varies per county), and of those, price
    and a joinable parcel identifier co-occur in the SAME county for
    essentially none of the 17 counties (nassau/hardee: price yes, parcel no;
    highlands: parcel yes [100% zw_parcels match], price no). See
    docs/spec/19794.md for the full per-county breakdown. This UNION branch
    exists so a future county whose clerk raw_comment DOES carry both (or a
    future re-scrape that adds a price field) is picked up automatically --
    it contributes 0 rows against live data as of this writing, verified.
    """
    sql = f"""
        with mca_source as (
            select
                s.case_number, s.county, s.sale_type, s.auction_date,
                s.property_address, s.sold_amount, s.buyer_type,
                'auction_buyer_sightings' as source
            from public.auction_buyer_sightings s
            where s.auction_date >= date {lib.sql_str(start_date)}
              and s.auction_date <= date {lib.sql_str(end_date)}
              and s.sold_amount is not null and s.sold_amount > 0
              and (
                    (s.sale_type = 'foreclosure' and s.buyer_type = 'third_party')
                    or
                    -- absolute-auction rule (docs/gtm/REEL_SPEC_BOLT32.md):
                    -- tax_deed needs no winning_bidder-type ambiguity check,
                    -- only that it wasn't explicitly reclaimed by a plaintiff.
                    (s.sale_type = 'tax_deed' and (s.buyer_type is null or s.buyer_type = 'third_party'))
              )
        ),
        clerk_priced as (
            select
                c.case_number, c.county_slug as county, 'tax_deed' as sale_type,
                c.sale_date as auction_date, null::text as property_address,
                replace((regexp_match(c.raw_comment, '\\$\\s?([0-9][0-9,]*\\.?[0-9]*)'))[1], ',', '')::numeric as sold_amount,
                'third_party'::text as buyer_type,
                'clerk_ssot_sale_rows' as source
            from public.clerk_ssot_sale_rows c
            where c.sale_type = 'tax_deed' and c.cancelled = false
              and c.raw_comment ~* 'sold' and c.raw_comment !~* 'redeem' and c.raw_comment !~* 'cancel'
              and (regexp_match(c.raw_comment, '\\$\\s?([0-9][0-9,]*\\.?[0-9]*)')) is not null
              and c.sale_date >= date {lib.sql_str(start_date)}
              and c.sale_date <= date {lib.sql_str(end_date)}
              and not exists (
                  select 1 from mca_source m
                  where lower(m.county) = lower(c.county_slug)
                    and upper(regexp_replace(m.case_number, '[^A-Za-z0-9]', '', 'g'))
                        = upper(regexp_replace(c.case_number, '[^A-Za-z0-9]', '', 'g'))
              )
        )
        select case_number, county, sale_type, auction_date::text as auction_date,
               property_address, sold_amount, source
        from mca_source
        union all
        select case_number, county, sale_type, auction_date::text as auction_date,
               property_address, sold_amount, source
        from clerk_priced
        order by auction_date, county, case_number;
    """
    return lib.run_sql(sql)


def get_existing_reel(case_number: str, county: str) -> dict | None:
    rows = lib.run_sql(
        f"""select video_url, voiceover_source, audio_url, status,
                   aerial_url, street_url, parcel_id, assessed_value
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
              "error": None, "image_calls": 0, "tts_chars": 0, "geocode_fallback": None}

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

        # Directive #2 (issue #19736 comment): "T2 must never re-call Maps for
        # a row that has aerial_url" -- a --force re-render (e.g. to pick up a
        # T3 fix) must reuse already-fetched-and-stored imagery rather than
        # spending another 1-2 Maps calls on a property whose photos we
        # already have in Storage.
        has_existing_imagery = bool(existing and existing.get("aerial_url"))
        raw_addr = sighting.get("property_address", "")
        assessed_value = (existing or {}).get("assessed_value")
        parcel_id = (existing or {}).get("parcel_id")
        lat = lon = None

        if not has_existing_imagery:
            parcel = lib.match_parcel(raw_addr, county)
            if parcel and parcel.get("centroid_lat") is not None and parcel.get("centroid_lon") is not None:
                lat, lon = parcel["centroid_lat"], parcel["centroid_lon"]
                assessed_value = parcel.get("val_assessed")
                parcel_id = parcel.get("pin_clean")
            else:
                # 2026-09-02 directive: no zw_parcels match -- log raw + normalized
                # address (T9 report) and fall back to Geocoding so imagery still
                # runs. Only a genuine error (both parcel match AND geocode miss)
                # aborts the row now.
                result["geocode_fallback"] = {
                    "raw_address": raw_addr,
                    "normalized": lib.normalize_addr(lib.street_part(raw_addr)),
                }
                geocoded = lib.geocode_address(raw_addr, keys["google_maps"])
                if not geocoded:
                    row = dict(base_row, status="error",
                               error_text="no zw_parcels match AND geocode miss for property_address "
                                          f"(normalized: {result['geocode_fallback']['normalized']!r})")
                    upsert_reel(row, dry_run)
                    result["status"] = "error"
                    result["error"] = row["error_text"]
                    return result
                lat, lon = geocoded
                result["geocode_fallback"]["lat"] = lat
                result["geocode_fallback"]["lon"] = lon

        date_key = sighting["auction_date"]
        case_key = urllib.parse.quote(case_number.replace(" ", "_").replace("/", "-"), safe="")
        prefix = f"{date_key}/{case_key}"

        with tempfile.TemporaryDirectory() as tmp:
            aerial_path = os.path.join(tmp, "aerial.png")
            street_path = None
            street_url = None

            if has_existing_imagery:
                urllib.request.urlretrieve(existing["aerial_url"], aerial_path)
                aerial_url = existing["aerial_url"]
                street_url = existing.get("street_url")
                if street_url:
                    street_path = os.path.join(tmp, "street.jpg")
                    urllib.request.urlretrieve(street_url, street_path)
            else:
                lib.fetch_static_map(lat, lon, aerial_path, keys["google_maps"])
                result["image_calls"] += 1

                if lib.streetview_metadata_ok(lat, lon, keys["google_maps"]):
                    street_path = os.path.join(tmp, "street.jpg")
                    lib.fetch_streetview(lat, lon, street_path, keys["google_maps"])
                    result["image_calls"] += 1

                aerial_url = lib.storage_upload(aerial_path, f"{prefix}/aerial.png", "image/png")
                if street_path:
                    street_url = lib.storage_upload(street_path, f"{prefix}/street.jpg", "image/jpeg")

            image_paths = [aerial_path] + ([street_path] if street_path else [])
            condition = lib.score_condition(image_paths, keys)
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
                parcel_id=parcel_id,
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
    ap.add_argument("--days-back", type=int, default=None,
                     help="issue #19794 -- backfill mode: query get_reel_candidates() over "
                          "[today - N days, yesterday] instead of a single --auction-date. "
                          "Fixes the tax-deed starvation gap, which was a query date-range gap, "
                          "not a missing-source gap (see get_reel_candidates() docstring).")
    ap.add_argument("--force", action="store_true", help="re-render rows that already have a video_url")
    ap.add_argument("--dry-run", action="store_true", help="no DB writes, no external API calls beyond the read query")
    ap.add_argument("--limit", type=int, default=None, help="cap number of rows processed (testing only)")
    args = ap.parse_args()

    auction_date = args.auction_date or get_yesterday()
    if not args.days_back:
        print(f"Auction date: {auction_date}")

    def resolve_key(env_name: str, vault_names: list[str]) -> str:
        """env var wins (GHA runner sets these from repo secrets); falls back
        to a vault fetch for sessions that don't have the env var set (never
        echoed -- see lib.get_vault_secret)."""
        v = os.environ.get(env_name, "")
        if v or args.dry_run:
            return v
        for name in vault_names:
            try:
                return lib.get_vault_secret(name)
            except Exception:
                continue
        return ""

    # 2026-09-02 directive #3 (final, supersedes #2): T3 vision scoring calls
    # OpenRouter directly (primary GLM-5.3-flash, fallback DeepSeek vision),
    # with claude-router as the last-resort fallback. "router" stays required
    # since it's the final fallback tier, not because it's the only tier
    # anymore.
    keys = {
        "google_maps": resolve_key("GOOGLE_MAPS_API_KEY", ["google_maps_api_key"]),
        "elevenlabs": resolve_key("ELEVENLABS_API_KEY", ["elevenlabs_api_key", "elevenlabs_production"]),
        "openrouter": resolve_key("OPENROUTER_API_KEY", ["openrouter_api_key"]),
        "router": resolve_key("ROUTER_PROXY_KEY", ["router_proxy_key"]),
    }
    missing = [k for k, v in keys.items() if not v and not args.dry_run]
    if missing:
        print(f"ERROR: missing required keys (env + vault both empty) for: {missing}", file=sys.stderr)
        sys.exit(1)

    if args.days_back:
        start_date = lib.run_sql(
            f"select (current_date - interval '{int(args.days_back)} days')::date::text as d;"
        )[0]["d"]
        end_date = get_yesterday()
        print(f"Backfill window: {start_date} .. {end_date} (--days-back {args.days_back})")
        sightings = get_reel_candidates(start_date, end_date)
        by_source = {}
        for s in sightings:
            by_source[s.get("source")] = by_source.get(s.get("source"), 0) + 1
        print(f"{len(sightings)} candidate(s) in window, by source: {by_source}")
    else:
        sightings = get_third_party_wins(auction_date)
        print(f"{len(sightings)} third-party win(s) for {auction_date}.")
    if args.limit:
        sightings = sightings[: args.limit]

    t0 = time.time()
    results = []
    for s in sightings:
        print(f"Processing {s['case_number']} / {s['county']} / {s.get('sale_type')} ...")
        r = process_row(s, args.force, args.dry_run, keys)
        print(f"  -> {r['status']}" + (f" ({r['error']})" if r.get("error") else ""))
        results.append(r)

    dates_to_shortlist = sorted({s["auction_date"] for s in sightings}) if args.days_back else [auction_date]
    shortlisted = []
    for d in dates_to_shortlist:
        shortlisted.extend(apply_shortlist(d, args.dry_run))
    wall_time = time.time() - t0

    n_ok = sum(1 for r in results if r["status"] == "pending_approval")
    n_err = sum(1 for r in results if r["status"] == "error")
    n_skip = sum(1 for r in results if r["status"] == "skipped_has_video")
    total_images = sum(r["image_calls"] for r in results)
    total_tts_chars = sum(r["tts_chars"] for r in results)

    print("\n=== SUMMARY ===")
    print(f"rows={len(results)} pending_approval={n_ok} error={n_err} skipped_has_video={n_skip}")
    print(f"image_calls_total={total_images} tts_chars_total={total_tts_chars} wall_time_sec={wall_time:.1f}")
    print(f"shortlisted={len(shortlisted)}")
    for r in sorted(shortlisted, key=lambda x: x.get("rank_score") or 0, reverse=True):
        print(f"  #{r['case_number']} / {r['county']} rank_score={r['rank_score']} video_url={r['video_url']}")

    geocoded = [r for r in results if r.get("geocode_fallback")]
    if geocoded:
        print("\n=== NO ZW_PARCELS MATCH (geocode fallback attempted) ===")
        for r in geocoded:
            gf = r["geocode_fallback"]
            outcome = "geocoded OK" if "lat" in gf else "geocode ALSO missed -> error"
            print(f"  {r['case_number']} / {r['county']}: raw={gf['raw_address']!r} "
                  f"normalized={gf['normalized']!r} -> {outcome}")

    errored = [r for r in results if r["status"] == "error"]
    if errored:
        print("\n=== ERRORS ===")
        for r in errored:
            print(f"  {r['case_number']} / {r['county']}: {r['error']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
