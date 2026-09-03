#!/usr/bin/env python3
"""BidDeed Reels v3 -- PRESALE (calendar/upcoming-auction) deal pages + reels
(issue #19761, builds on v2 #19752).

GENERATES AND STAGES ONLY. Never posts, never sends. Runs T-2 days before the
auction date so Ariel has time to approve: every property on
public.v_upcoming_auctions_ssot for the target auction_date gets a
winnerdata.biddeed_reels row with phase='presale' + a deal page (T3, no
video). The top 20 rows by presale_rank additionally get a rendered reel
(T4); the top 5 of those are shortlisted. Every row lands at
status='pending_approval' (or 'error' + error_text on a per-row failure) --
nothing downstream reads this table for outbound sends, matching v1/v2's
same guardrail.

Run:
  python scripts/biddeed_reels_pipeline_presale.py [--auction-date YYYY-MM-DD]
    [--force] [--limit N] [--only CASE_NUMBER] [--skip-reels]

--auction-date defaults to today+2 (UTC), matching the issue's T5 cron
target. --force re-fetches imagery/re-scores condition/re-renders reels for
rows that already have them (T3/T4 are otherwise idempotent: a row with a
landing_url is skipped for deal-page work, a row with a video_v2_url is
skipped for reel rendering, unless --force). --skip-reels does T3 only (no
TTS/video spend) -- useful for a dry run of deal-page coverage alone.

Required env/vault: same as v1/v2 -- GOOGLE_MAPS_API_KEY, ELEVENLABS_API_KEY,
OPENROUTER_API_KEY, ROUTER_PROXY_KEY (T3 vision fallback only). Vision scoring
goes through OpenRouter GLM (score_condition()'s existing primary tier) --
never a direct Anthropic/Gemini call, per this repo's standing CLAUDE.md
directive.
"""
import argparse
import datetime
import json
import os
import sys
import tempfile
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biddeed_reels_lib as lib

LANDING_BASE = "https://biddeed.ai/deal"
SHORT_BASE = "https://biddeed.ai/r"
TOP_N_REELS = 20
SHORTLIST_N = 5
PRESALE_EDIT_VERSION = 3


def get_ssot_rows(auction_date: str) -> list[dict]:
    """v_upcoming_auctions_ssot has a live-verified PostgREST permission gap
    (2026-09-03: `permission denied for table tier1_today` even with the
    service-role key -- the underlying table an ancestor view joins lacks a
    grant PostgREST's role picks up, distinct from RLS bypass) -- read via
    the Management API instead, same as every other winnerdata.* access in
    this pipeline."""
    rows = lib.run_sql(f"""
        select county, source_platform, sale_type, auction_date, case_number, parcel_id,
               property_address, assessed_value, opening_bid, judgment_amount,
               realforeclose_url, price_tier, flip_rate_pct, avg_roi, zip_score, anchors_in_zip
        from public.v_upcoming_auctions_ssot
        where auction_date = {lib.sql_str(auction_date)}
        order by county, case_number;
    """)
    return rows


def get_existing_presale_row(case_number: str, county: str) -> dict | None:
    rows = lib.run_sql(f"""
        select id, landing_url, video_v2_url, short_code, aerial_wide_url, aerial_tight_url,
               street_url, zw_parcel_id, parcel_geojson, parcel_outline, condition_json,
               condition_score, assessed_value
        from winnerdata.biddeed_reels
        where case_number = {lib.sql_str(case_number)} and county = {lib.sql_str(county)}
          and phase = 'presale';
    """)
    return rows[0] if rows else None


def _sql_val(col: str, v):
    if col in ("sold_amount", "assessed_value", "delta_pct", "condition_score", "duration_sec",
               "rank_score", "zw_parcel_id", "edit_version", "opening_bid", "judgment_amount",
               "days_to_auction", "presale_rank"):
        return lib.sql_num(v)
    if col == "hashtags":
        return lib.sql_text_array(v)
    if col in ("condition_json", "parcel_geojson"):
        return lib.sql_jsonb(v)
    if col in ("parcel_outline", "shortlisted"):
        return lib.sql_bool(v)
    return lib.sql_str(v)


def upsert_presale_row(row: dict) -> str:
    """insert-or-update by (case_number, county, phase='presale') -- returns
    the row id. `row` never includes case_number/county/phase itself in the
    update SET clause (those are the conflict key)."""
    cols = list(row.keys())
    col_list = ", ".join(cols)
    val_list = ", ".join(_sql_val(c, row[c]) for c in cols)
    set_clause = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in ("case_number", "county", "phase"))
    result = lib.run_sql(f"""
        insert into winnerdata.biddeed_reels ({col_list}, updated_at)
        values ({val_list}, now())
        on conflict (case_number, county, phase) do update set {set_clause}, updated_at = now()
        returning id;
    """)
    return result[0]["id"]


def update_row(row_id: str, fields: dict) -> None:
    set_clause = ", ".join(f"{c} = {_sql_val(c, v)}" for c, v in fields.items())
    lib.run_sql(f"""
        update winnerdata.biddeed_reels
        set {set_clause}, updated_at = now()
        where id = {lib.sql_str(row_id)};
    """)


def ensure_short_link(reel_id: str, existing_code: str | None, landing_url: str) -> tuple[str, str]:
    """Idempotent, mirroring v2's own ensure_short_link(): reuses an existing
    short_code on a --force re-run instead of minting a new one and orphaning
    the old link/QR."""
    if existing_code:
        code = existing_code
        lib.run_sql(f"""
            update winnerdata.reel_links set target = {lib.sql_str(landing_url)}, updated_at = now()
            where code = {lib.sql_str(code)};
        """)
    else:
        code = None
        for _ in range(5):
            candidate = lib.gen_short_code()
            rows = lib.run_sql(f"select 1 from winnerdata.reel_links where code = {lib.sql_str(candidate)};")
            if not rows:
                code = candidate
                break
        if code is None:
            raise RuntimeError("could not mint a unique short_code after 5 attempts")
        lib.run_sql(f"""
            insert into winnerdata.reel_links (code, reel_id, target, utm_source, utm_medium, utm_campaign)
            values ({lib.sql_str(code)}, {lib.sql_str(reel_id)}, {lib.sql_str(landing_url)},
                    'reel', 'social', 'biddeed_reels_presale');
        """)
    return code, f"{SHORT_BASE}/{code}"


def _ml_recommendation(gap_pct: float | None) -> str:
    """Deliberately NOT a re-implementation of the paid S5 report's
    calibrated Shapira model (that lives behind the MCP server / Modal.com
    inference and needs a real purchase record to even query) -- this is a
    simple, honestly-labeled gap-band signal computed from the same
    assessed_value/opening_bid/judgment_amount fields the deal page already
    shows. See docs/spec/19761.md for why this deviates from the issue's
    literal "ML score/recommendation" wording."""
    if gap_pct is None:
        return "Pending -- opening bid not posted yet"
    mag = abs(gap_pct)
    if mag >= 50:
        return "Strong equity spread vs. assessed value"
    if mag >= 25:
        return "Solid spread vs. assessed value"
    return "Tight spread -- verify comps before bidding"


def process_presale_deal(row: dict, auction_date: str, days_to_auction: int, force: bool, keys: dict) -> dict:
    """T3: upsert the presale row + build its deal-page assets (outlined
    aerial(s), street shot, vision condition score, presale intel, landing/
    short/QR links). No TTS, no video -- that's T4, run separately below on
    the ranked top 20."""
    case_number = row["case_number"]
    county = row["county"]
    result = {"case_number": case_number, "county": county, "status": None, "error": None}

    existing = get_existing_presale_row(case_number, county)
    if existing and existing.get("landing_url") and not force:
        result["status"] = "skipped_has_deal_page"
        result["row_id"] = existing["id"]
        return result

    try:
        assessed_value = float(row["assessed_value"]) if row.get("assessed_value") is not None else None
        opening_bid = float(row["opening_bid"]) if row.get("opening_bid") is not None else None
        judgment_amount = float(row["judgment_amount"]) if row.get("judgment_amount") is not None else None
        parcel_id = row.get("parcel_id")

        reuse_imagery = bool(
            force and existing and existing.get("aerial_wide_url")
            and existing.get("aerial_tight_url") and existing.get("street_url")
        )

        date_key = auction_date
        case_key = urllib.parse.quote(case_number.replace(" ", "_").replace("/", "-"), safe="")
        prefix = f"{date_key}/presale/{county}/{case_key}"

        with tempfile.TemporaryDirectory() as tmp:
            wide_path = os.path.join(tmp, "aerial_wide.png")
            tight_path = os.path.join(tmp, "aerial_tight.png")
            street_path = os.path.join(tmp, "street.jpg")

            pa_link = None
            if reuse_imagery:
                lib.fetch_url_to_file(existing["aerial_wide_url"], wide_path)
                lib.fetch_url_to_file(existing["aerial_tight_url"], tight_path)
                lib.fetch_url_to_file(existing["street_url"], street_path)
                aerial_wide_url = existing["aerial_wide_url"]
                aerial_tight_url = existing["aerial_tight_url"]
                street_url = existing["street_url"]
                zw_parcel_id = existing.get("zw_parcel_id")
                parcel_geojson = existing.get("parcel_geojson")
                parcel_outline = bool(existing.get("parcel_outline"))
            else:
                geom_row = lib.match_zw_parcel_geom(county, parcel_id) if parcel_id else None
                lat = lon = None
                parcel_geojson = None
                parcel_outline = False
                zw_parcel_id = None

                if geom_row and geom_row.get("centroid_lat") is not None:
                    lat, lon = float(geom_row["centroid_lat"]), float(geom_row["centroid_lon"])
                    parcel_geojson = json.loads(geom_row["geojson"])
                    ring = lib.geojson_ring_latlng(parcel_geojson)
                    wide_url, tight_url = lib.build_parcel_aerial_urls(lat, lon, ring, keys["google_maps"])
                    parcel_outline = True
                    zw_parcel_id = geom_row["zw_parcel_id"]
                    pa_link = geom_row.get("pa_link")
                else:
                    geocoded = lib.geocode_address(row.get("property_address", ""), keys["google_maps"])
                    if not geocoded:
                        raise RuntimeError("no zw_parcels geometry AND geocode miss -- cannot build presale imagery")
                    lat, lon = geocoded
                    wide_url, tight_url = lib.build_pin_aerial_urls(lat, lon, keys["google_maps"])

                lib.fetch_url_to_file(wide_url, wide_path)
                lib.fetch_url_to_file(tight_url, tight_path)

                if lib.streetview_metadata_ok(lat, lon, keys["google_maps"]):
                    lib.fetch_streetview(lat, lon, street_path, keys["google_maps"])
                    street_url = lib.storage_upload(street_path, f"{prefix}/street.jpg", "image/jpeg")
                else:
                    sub_url = lib.build_tight_aerial_url(lat, lon, 19, keys["google_maps"])
                    lib.fetch_url_to_file(sub_url, street_path)
                    street_url = lib.storage_upload(street_path, f"{prefix}/aerial_z19_sub.jpg", "image/jpeg")

                aerial_wide_url = lib.storage_upload(wide_path, f"{prefix}/aerial_wide.png", "image/png")
                aerial_tight_url = lib.storage_upload(tight_path, f"{prefix}/aerial_tight.png", "image/png")

            # T3 vision score -- OpenRouter GLM primary (score_condition()'s
            # existing cascade), reused verbatim from v1/v2.
            if not reuse_imagery or not existing.get("condition_json"):
                condition = lib.score_condition([tight_path, street_path], keys)
                condition_score = int(round(condition["condition_score"]))
            else:
                condition = existing["condition_json"]
                condition_score = existing.get("condition_score")

            basis_bid = opening_bid if opening_bid is not None else judgment_amount
            gap_pct = None
            if basis_bid and assessed_value and assessed_value > 0:
                gap_pct = round((assessed_value - basis_bid) / assessed_value * 100, 1)

            ml_max_bid = round(assessed_value * 0.70) if assessed_value else None
            condition["presale_intel"] = {
                "flip_rate_pct": row.get("flip_rate_pct"),
                "avg_roi": row.get("avg_roi"),
                "zip_score": row.get("zip_score"),
                "anchors_in_zip": row.get("anchors_in_zip"),
                "pa_link": pa_link,
                "source_platform": row.get("source_platform"),
                "realforeclose_url": row.get("realforeclose_url"),
                "senior_liens": None,  # not sourced by this pipeline -- honest placeholder, never fabricated
                "gap_pct": gap_pct,
                "ml_max_bid": ml_max_bid,
                "ml_recommendation": _ml_recommendation(gap_pct),
            }

            slug = lib.slugify_case_number(case_number)
            county_slug = county.replace("_", "-")
            landing_url = f"{LANDING_BASE}/{county_slug}/{slug}"

            fields = {
                "sale_type": row.get("sale_type"),
                "auction_date": auction_date,
                "property_address": row.get("property_address"),
                "parcel_id": parcel_id,
                "assessed_value": assessed_value,
                "opening_bid": opening_bid,
                "judgment_amount": judgment_amount,
                "days_to_auction": days_to_auction,
                "zw_parcel_id": zw_parcel_id,
                "parcel_geojson": parcel_geojson,
                "parcel_outline": parcel_outline,
                "aerial_wide_url": aerial_wide_url,
                "aerial_tight_url": aerial_tight_url,
                "street_url": street_url,
                "condition_json": condition,
                "condition_score": condition_score,
                "landing_url": landing_url,
                "status": "pending_approval",
                "error_text": None,
            }

            # winnerdata.reel_links.reel_id is a hard FK to biddeed_reels.id --
            # the row must exist BEFORE the short link does. Upsert first
            # (short_code/short_url/qr_url filled in by a second small update
            # right after), unlike v2's pipeline which only ever re-renders
            # rows v1 already inserted days earlier.
            if existing:
                row_id = existing["id"]
                update_row(row_id, fields)
            else:
                row_id = upsert_presale_row(dict(
                    fields, case_number=case_number, county=county, phase="presale",
                ))

            short_code, short_url = ensure_short_link(row_id, existing.get("short_code") if existing else None, landing_url)

            qr_path = os.path.join(tmp, "qr.png")
            lib.generate_qr_png(short_url, qr_path)
            qr_url = lib.storage_upload(qr_path, f"{prefix}/qr.png", "image/png")

            update_row(row_id, {"short_code": short_code, "short_url": short_url, "qr_url": qr_url})

            result.update({
                "status": "deal_page_done", "row_id": row_id, "parcel_outline": parcel_outline,
                "gap_pct": gap_pct, "landing_url": f"{landing_url}?preview={row_id}", "short_url": short_url,
            })
            return result

    except Exception as e:
        error_text = str(e)[:2000]
        try:
            if existing:
                update_row(existing["id"], {"status": "error", "error_text": error_text})
            else:
                upsert_presale_row({
                    "case_number": case_number, "county": county, "phase": "presale",
                    "sale_type": row.get("sale_type"), "auction_date": auction_date,
                    "property_address": row.get("property_address"), "days_to_auction": days_to_auction,
                    "status": "error", "error_text": error_text,
                })
        except Exception as write_err:
            print(f"  WARN: also failed to write error row for {case_number}/{county}: {write_err}", file=sys.stderr)
        result["status"] = "error"
        result["error"] = error_text[:500]
        return result


def rank_and_shortlist(auction_date: str) -> list[dict]:
    """T4 ranking: compute presale_rank for every presale row on this
    auction_date that made it past T3 (status != 'error'), then shortlist
    the top 5. Returns the ranked rows, highest presale_rank first."""
    rows = lib.run_sql(f"""
        select id, case_number, county, assessed_value, opening_bid, judgment_amount,
               condition_score, condition_json
        from winnerdata.biddeed_reels
        where phase = 'presale' and auction_date = {lib.sql_str(auction_date)}
          and status != 'error';
    """)
    ranked = []
    for r in rows:
        assessed_value = float(r["assessed_value"]) if r.get("assessed_value") is not None else None
        opening_bid = float(r["opening_bid"]) if r.get("opening_bid") is not None else None
        judgment_amount = float(r["judgment_amount"]) if r.get("judgment_amount") is not None else None
        basis_bid = opening_bid if opening_bid is not None else judgment_amount
        gap_pct = None
        if basis_bid and assessed_value and assessed_value > 0:
            gap_pct = (assessed_value - basis_bid) / assessed_value * 100
        cond = r.get("condition_json") or {}
        intel = cond.get("presale_intel") or {}
        zip_score = intel.get("zip_score")
        price_tier = None  # not stored on the row -- carried only in v_upcoming_auctions_ssot at T3 time
        score = lib.rank_presale_score(gap_pct, zip_score, price_tier, r.get("condition_score"))
        update_row(r["id"], {"presale_rank": score})
        ranked.append({**r, "presale_rank": score})

    ranked.sort(key=lambda x: x["presale_rank"], reverse=True)

    lib.run_sql(f"""
        update winnerdata.biddeed_reels set shortlisted = false, updated_at = now()
        where phase = 'presale' and auction_date = {lib.sql_str(auction_date)} and shortlisted = true;
    """)
    for r in ranked[:SHORTLIST_N]:
        lib.run_sql(f"update winnerdata.biddeed_reels set shortlisted = true, updated_at = now() where id = {lib.sql_str(r['id'])};")

    return ranked


def render_presale_reel(row_id: str, force: bool, keys: dict) -> dict:
    """T4: render the 30s presale reel for one already-deal-paged row, reusing
    its existing imagery (no re-fetch of Maps/Street View -- same rule as
    v2's directive #4A)."""
    rows = lib.run_sql(f"""
        select id, case_number, county, sale_type, auction_date, assessed_value, opening_bid,
               judgment_amount, days_to_auction, condition_json, condition_score,
               aerial_wide_url, aerial_tight_url, street_url, short_url, video_v2_url
        from winnerdata.biddeed_reels where id = {lib.sql_str(row_id)};
    """)
    if not rows:
        return {"row_id": row_id, "status": "error", "error": "row disappeared before reel render"}
    row = rows[0]
    result = {"case_number": row["case_number"], "county": row["county"], "status": None, "error": None}

    if row.get("video_v2_url") and not force:
        result["status"] = "skipped_has_reel"
        return result

    try:
        assessed_value = float(row["assessed_value"]) if row.get("assessed_value") is not None else None
        opening_bid = float(row["opening_bid"]) if row.get("opening_bid") is not None else None
        judgment_amount = float(row["judgment_amount"]) if row.get("judgment_amount") is not None else None
        condition = row.get("condition_json") or {}
        if not condition or "general_condition_tier" not in condition:
            raise RuntimeError("no condition_json to build reel from -- run T3 deal-page step first")

        auction_date_str = row["auction_date"].isoformat() if hasattr(row["auction_date"], "isoformat") else row["auction_date"]
        case_key = urllib.parse.quote(row["case_number"].replace(" ", "_").replace("/", "-"), safe="")
        prefix = f"{auction_date_str}/presale/{row['county']}/{case_key}"

        with tempfile.TemporaryDirectory() as tmp:
            wide_path = os.path.join(tmp, "aerial_wide.png")
            tight_path = os.path.join(tmp, "aerial_tight.png")
            street_path = os.path.join(tmp, "street.jpg")
            lib.fetch_url_to_file(row["aerial_wide_url"], wide_path)
            lib.fetch_url_to_file(row["aerial_tight_url"], tight_path)
            lib.fetch_url_to_file(row["street_url"], street_path)

            short_url = row["short_url"]
            sc = lib.build_presale_script_and_caption(
                row["county"], row.get("sale_type"), opening_bid, judgment_amount,
                assessed_value, condition, row.get("days_to_auction"), short_url,
            )

            audio_path = os.path.join(tmp, "voice_presale.mp3")
            lib.elevenlabs_tts_v3(sc["script_text_v3"], keys["elevenlabs"], audio_path)
            audio_url = lib.storage_upload(audio_path, f"{prefix}/voice_presale.mp3", "audio/mpeg")

            basis_bid = sc["basis_bid"]
            opening_bid_label = f"{sc['basis_label']} ${basis_bid:,.0f}" if basis_bid else None
            tier = condition.get("general_condition_tier", "unknown")
            bullets = []
            for key_name in ("roof", "exterior", "vegetation_overgrowth"):
                obs = (condition.get(key_name) or {}).get("observation")
                if obs:
                    bullets.append(lib.condition_pill_label(key_name, obs))

            overlays = {
                "county": lib.county_display(row["county"]).replace(" County", ""),
                "sale_type_label": (row.get("sale_type") or "").replace("_", " ").upper(),
                "auction_date_label": lib.month_abbr_day(auction_date_str),
                "opening_bid_label": opening_bid_label,
                "assessed_value": assessed_value,
                "condition_tier": tier,
                "condition_bullets": bullets[:2],
                "days_to_auction": row.get("days_to_auction"),
            }
            images = {
                "hook": tight_path, "reveal": wide_path, "street": street_path,
                "condition": tight_path, "payoff": wide_path,
            }
            qr_path = os.path.join(tmp, "qr.png")
            lib.generate_qr_png(short_url, qr_path)

            video_path = os.path.join(tmp, "reel_presale.mp4")
            duration_sec = lib.assemble_video_presale(images, audio_path, overlays, qr_path, short_url, video_path)
            video_v2_url = lib.storage_upload(video_path, f"{prefix}/reel_presale.mp4", "video/mp4")

            update_row(row["id"], {
                "video_v2_url": video_v2_url,
                "duration_sec": round(duration_sec, 2),
                "edit_version": PRESALE_EDIT_VERSION,
                "script_text": sc["script_text"],
                "caption_text": sc["caption_text"],
                "hashtags": sc["hashtags"],
                "audio_url": audio_url,
                "tts_model": lib.V2_TTS_MODEL,
                "voice_id": os.environ.get("ELEVENLABS_V2_VOICE_ID", lib.V2_BRAND_VOICE_ID),
            })
            result.update({"status": "reel_done", "duration_sec": round(duration_sec, 2), "video_v2_url": video_v2_url})
            return result

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:800]
        update_row(row_id, {"status": "error", "error_text": result["error"]})
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auction-date", default=None, help="YYYY-MM-DD, defaults to today+2 (UTC)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only", default=None, help="case_number substring filter")
    ap.add_argument("--skip-reels", action="store_true", help="T3 deal pages only, no TTS/video spend")
    args = ap.parse_args()

    today = datetime.date.today()
    auction_date = args.auction_date or (today + datetime.timedelta(days=2)).isoformat()
    days_to_auction = (datetime.date.fromisoformat(auction_date) - today).days
    print(f"Auction date: {auction_date} (days_to_auction={days_to_auction})")

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
        "openrouter": resolve_key("OPENROUTER_API_KEY", ["openrouter_api_key"]),
        "router": resolve_key("ROUTER_PROXY_KEY", ["router_proxy_key"]),
    }
    missing = [k for k in ("google_maps", "openrouter") if not keys[k]]
    if not args.skip_reels and not keys["elevenlabs"]:
        missing.append("elevenlabs")
    if missing:
        print(f"ERROR: missing keys: {missing}", file=sys.stderr)
        sys.exit(1)

    ssot_rows = get_ssot_rows(auction_date)
    if args.only:
        ssot_rows = [r for r in ssot_rows if args.only in r["case_number"]]
    if args.limit:
        ssot_rows = ssot_rows[: args.limit]

    print(f"{len(ssot_rows)} calendar row(s) for {auction_date} (T3 deal pages).")
    t0 = time.time()
    deal_results = []
    for r in ssot_rows:
        print(f"T3 {r['case_number']} / {r['county']} ...")
        res = process_presale_deal(r, auction_date, days_to_auction, args.force, keys)
        print(f"  -> {res['status']}" + (f" ({res['error']})" if res.get("error") else ""))
        deal_results.append(res)

    n_deal_ok = sum(1 for r in deal_results if r["status"] == "deal_page_done")
    n_deal_skip = sum(1 for r in deal_results if r["status"] == "skipped_has_deal_page")
    n_deal_err = sum(1 for r in deal_results if r["status"] == "error")

    print("\n=== T3 SUMMARY ===")
    print(f"rows={len(deal_results)} deal_page_done={n_deal_ok} skipped={n_deal_skip} error={n_deal_err}")

    ranked = rank_and_shortlist(auction_date)
    print(f"\nranked={len(ranked)} shortlisted(top {SHORTLIST_N})={min(SHORTLIST_N, len(ranked))}")

    reel_results = []
    if not args.skip_reels:
        top20 = ranked[:TOP_N_REELS]
        print(f"\n{len(top20)} row(s) eligible for T4 reel render (top {TOP_N_REELS} by presale_rank).")
        for r in top20:
            print(f"T4 {r['case_number']} / {r['county']} (presale_rank={r['presale_rank']}) ...")
            res = render_presale_reel(r["id"], args.force, keys)
            print(f"  -> {res['status']}" + (f" ({res['error']})" if res.get("error") else ""))
            reel_results.append(res)

    n_reel_ok = sum(1 for r in reel_results if r["status"] == "reel_done")
    n_reel_skip = sum(1 for r in reel_results if r["status"] == "skipped_has_reel")
    n_reel_err = sum(1 for r in reel_results if r["status"] == "error")

    print("\n=== T4 SUMMARY ===")
    print(f"rows={len(reel_results)} reel_done={n_reel_ok} skipped={n_reel_skip} error={n_reel_err}")
    print(f"\nwall_time_sec={time.time()-t0:.1f}")

    errored = [r for r in deal_results + reel_results if r["status"] == "error"]
    if errored:
        print("\n=== ERRORS ===")
        for r in errored:
            print(f"  {r['case_number']}/{r['county']}: {r['error']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
