#!/usr/bin/env python3
"""Shared helpers for the BidDeed Reels pipeline (issue #19736).

This pipeline GENERATES and STAGES reels only -- it never posts to a social
platform and never sends anything to anyone. Every row this pipeline writes
lands at status='generated' -> 'pending_approval' or 'error'; nothing in
this module ever flips status to 'approved'/'posted' (that is a human
review step, out of scope here).

Guardrails enforced in code, not just prose (see build_script_and_caption):
  - no buyer/bidder/person name anywhere in generated text
  - no vendor/tool name (Google, ElevenLabs, etc.) in generated text
  - Maps calls are capped at 2 image fetches per property (1 static map +
    1 street view); the street view metadata check is free and does not
    count against that cap
  - a reel is never re-rendered once it has a video_url unless force=True

2026-09-02 directives (issue #19736 comments, after the first backfill came
back 15/15 error): T3 condition scoring must not call any AI provider
directly with a key this pipeline resolves and holds itself for a *quota-
capped* provider. Directive #1 (direct Gemini) and directive #2
(claude-router-only) both hit real capacity ceilings (Gemini prepay/free-tier
quota; the Max-OAuth-backed router tier is fine but was the only live tier).
Directive #3 (final, 2026-09-02 12:55 EDT) routes score_condition() through
OpenRouter directly: primary z-ai/glm-5.3-flash, fallback deepseek-v4-flash-
vision-exp (only if confirmed live on OpenRouter's /api/v1/models), final
fallback the claude-router edge function (whose own T10 cascade lands on
Claude Haiku OAuth). T2 also gained a Geocoding API fallback
(geocode_address()) for addresses that don't match any public.zw_parcels row,
so imagery still runs (parcel_id/assessed_value/delta_pct land null for those
rows instead of the row erroring outright).

public schema (auction_buyer_sightings, zw_parcels) reads go through
PostgREST (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY), matching
entity_portfolio_resolver.py's pg_rest() pattern. winnerdata.* is NOT
exposed via PostgREST on this project (documented in
winnerdata_ff_digest_lib.py) -- all winnerdata reads/writes go through the
Supabase Management API (SUPABASE_ACCESS_TOKEN), matching that module's
run_sql()/sql_str() pattern.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
STORAGE_BUCKET = "biddeed-reels"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

MGMT_API_RETRIES = 3
MGMT_API_BACKOFF_SECONDS = 3

# 2026-09-02 directive #2 (issue #19736 comment): T3 vision scoring must go
# through the claude-router edge function, not a direct provider call --
# the first fix (direct Gemini calls) hit a quota wall on both available
# Gemini keys mid-backfill. claude-router's own T1 (Gemini) / T1.5 (DeepSeek
# vision, T10) / T2 (Claude Haiku via Max OAuth) cascade handles the fallback.
CLAUDE_ROUTER_URL_PATH = "/functions/v1/claude-router"

# Standard ElevenLabs premade voice ("Rachel") -- always present on any
# ElevenLabs account, no account-specific voice provisioning required.
# Override with ELEVENLABS_VOICE_ID if Ariel wants a different one.
DEFAULT_ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

BRAND_NAVY = "0x1E3A5F"
BRAND_AMBER = "0xF59E0B"
BRAND_VOID = "0x020617"


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------

def run_sql(query: str):
    """winnerdata.* access via the Management API (see module docstring)."""
    token = os.environ["SUPABASE_ACCESS_TOKEN"]
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "biddeed-reels-pipeline/1.0",
        },
        method="POST",
    )
    last_err = None
    for attempt in range(1, MGMT_API_RETRIES + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
            if isinstance(body, dict) and "message" in body:
                raise RuntimeError(body["message"])
            return body
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < MGMT_API_RETRIES:
                time.sleep(MGMT_API_BACKOFF_SECONDS * attempt)
    raise last_err


def sql_str(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def sql_num(v):
    return "null" if v is None else str(v)


def sql_bool(v):
    return "null" if v is None else ("true" if v else "false")


def sql_text_array(items):
    if not items:
        return "null"
    escaped = ", ".join(sql_str(i) for i in items)
    return f"array[{escaped}]::text[]"


def sql_jsonb(obj):
    if obj is None:
        return "null"
    return sql_str(json.dumps(obj)) + "::jsonb"


def get_vault_secret(name: str) -> str:
    """Vault fallback for keys not present in the environment (e.g. this
    pipeline running outside the GHA runner, which has no GOOGLE_MAPS_API_KEY/
    ELEVENLABS_API_KEY env vars). Matches gemini_task_runner.py's
    get_vault_secret() -- RPC only, never echoed, never written to a shell
    command (CREDENTIAL HANDLING mandate)."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/get_vault_secret_mcp",
        data=json.dumps({"p_name": name}).encode(),
        headers={
            "apikey": SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "biddeed-reels-pipeline/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode()).strip('"')


def pg_rest(table: str, params: str, timeout: int = 60) -> list[dict]:
    """public schema reads via PostgREST (see module docstring).

    Retries on transient Cloudflare/edge errors in front of
    *.supabase.co (521/520/503 -- live-verified during this pipeline's own
    build/backfill session, 2026-09-02: the same zw_parcels query that
    failed with 521 on one attempt succeeded on retry seconds later, so
    this is genuine edge-layer flakiness, not a real data or auth problem).
    Matches run_sql()'s existing retry/backoff shape for winnerdata access.
    """
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(
        url,
        headers={"apikey": SERVICE_ROLE_KEY, "Authorization": f"Bearer {SERVICE_ROLE_KEY}"},
    )
    last_err = None
    for attempt in range(1, MGMT_API_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < MGMT_API_RETRIES:
                time.sleep(MGMT_API_BACKOFF_SECONDS * attempt)
    raise last_err


# ---------------------------------------------------------------------------
# Storage (Supabase Storage bucket 'biddeed-reels' -- see docs/spec/19736.md
# for why this replaces the issue's literal "R2 bucket" instruction: no R2
# bucket or R2 credentials exist anywhere in this repo/org, live-verified;
# Supabase Storage is the repo's actual existing pattern for this kind of
# asset, e.g. generate_daily_auction_banner.py's 'social-banners' bucket)
# ---------------------------------------------------------------------------

def storage_upload(local_path: str, key: str, content_type: str) -> str:
    result = subprocess.run(
        [
            "curl", "-s", "-w", "\n%{http_code}",
            f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{key}",
            "-H", f"apikey: {SERVICE_ROLE_KEY}",
            "-H", f"Authorization: Bearer {SERVICE_ROLE_KEY}",
            "-H", f"Content-Type: {content_type}",
            "-H", "x-upsert: true",
            "--data-binary", f"@{local_path}",
        ],
        capture_output=True, text=True, check=True,
    )
    lines = result.stdout.strip().split("\n")
    http_code = lines[-1]
    if http_code not in ("200", "201"):
        raise RuntimeError(f"Storage upload failed (HTTP {http_code}): {result.stdout}")
    return f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{key}"


# ---------------------------------------------------------------------------
# T2 support -- address -> zw_parcels match
# ---------------------------------------------------------------------------

_ABBREV = {
    " STREET": " ST", " AVENUE": " AVE", " BOULEVARD": " BLVD", " DRIVE": " DR",
    " ROAD": " RD", " LANE": " LN", " COURT": " CT", " CIRCLE": " CIR",
    " TERRACE": " TER", " PLACE": " PL", " HIGHWAY": " HWY", " PARKWAY": " PKWY",
}


def normalize_addr(addr: str) -> str:
    if not addr:
        return ""
    a = addr.upper()
    a = re.sub(r"[^A-Z0-9 ]", " ", a)
    a = re.sub(r"\s+", " ", a).strip()
    for k, v in _ABBREV.items():
        a = a.replace(k, v)
    return a


def street_part(property_address: str) -> str:
    """'1955 HATBILL RD, MIMS, FL 32754' -> '1955 HATBILL RD'."""
    return (property_address or "").split(",")[0].strip()


def county_slug_to_query(county_slug: str) -> str:
    return (county_slug or "").replace("_", " ")


def match_parcel(property_address: str, county_slug: str) -> dict | None:
    """Best-effort address match against public.zw_parcels (the parcel SSOT).

    Returns None (not an exception) for an unmatchable address -- e.g. FL GIO
    "NO ADDRESS ON TAX ROLL" placeholder rows, or a genuine miss. Callers
    treat None as "no parcel data" (skip imagery/video for that row, mark
    status='error'), never as a reason to fabricate a match.
    """
    street = street_part(property_address)
    if not street or "NO ADDRESS" in street.upper():
        return None
    target = normalize_addr(street)
    county_q = county_slug_to_query(county_slug)
    params = (
        "select=pin_clean,county,site_addr,site_city,centroid_lat,centroid_lon,"
        "val_assessed,val_market,beds,baths_full,baths_half,sqft_heated,year_built"
        f"&county=ilike.{urllib.parse.quote(county_q)}"
        f"&site_addr=ilike.{urllib.parse.quote(street)}&limit=20"
    )
    rows = pg_rest("zw_parcels", params, timeout=60)
    for r in rows:
        if normalize_addr(r.get("site_addr") or "") == target:
            return r
    if len(rows) == 1:
        return rows[0]
    return None


def geocode_address(property_address: str, api_key: str) -> tuple[float, float] | None:
    """2026-09-02 directive (issue #19736 comment): when an address can't be
    matched to a zw_parcels row, fall back to the Geocoding API so imagery
    still runs. Returns None on any miss/error -- caller treats that as the
    real error case (both parcel match AND geocode failed)."""
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={urllib.parse.quote(property_address or '')}&region=us&key={api_key}"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            body = json.loads(r.read())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None
    if body.get("status") != "OK" or not body.get("results"):
        return None
    loc = body["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


# ---------------------------------------------------------------------------
# T2 support -- Google Maps Static + Street View
# ---------------------------------------------------------------------------

def streetview_metadata_ok(lat: float, lon: float, api_key: str) -> bool:
    """Free metadata check -- does NOT count against the 2-image-call cap."""
    url = (
        "https://maps.googleapis.com/maps/api/streetview/metadata"
        f"?location={lat},{lon}&key={api_key}"
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        body = json.loads(r.read())
    return body.get("status") == "OK"


def fetch_static_map(lat: float, lon: float, out_path: str, api_key: str) -> None:
    url = (
        "https://maps.googleapis.com/maps/api/staticmap"
        f"?center={lat},{lon}&zoom=19&size=640x640&maptype=satellite&key={api_key}"
    )
    urllib.request.urlretrieve(url, out_path)


def fetch_streetview(lat: float, lon: float, out_path: str, api_key: str) -> None:
    url = (
        "https://maps.googleapis.com/maps/api/streetview"
        f"?size=640x640&location={lat},{lon}&key={api_key}"
    )
    urllib.request.urlretrieve(url, out_path)


# ---------------------------------------------------------------------------
# T3 -- condition scoring (Claude vision)
# ---------------------------------------------------------------------------

CONDITION_PROMPT = """You are assessing the visible physical condition of a Florida property from \
satellite/aerial and (if present) street-level imagery, for an internal marketing content pipeline. \
You are NOT identifying any person. Do not speculate about occupants.

Return ONLY a JSON object with this exact shape:
{
  "roof": {"observation": "<short phrase>", "confidence": "VERIFIED|LIKELY|UNCONFIRMED"},
  "exterior": {"observation": "<short phrase>", "confidence": "VERIFIED|LIKELY|UNCONFIRMED"},
  "vegetation_overgrowth": {"observation": "<short phrase>", "confidence": "VERIFIED|LIKELY|UNCONFIRMED"},
  "vacancy_signals": {"observation": "<short phrase>", "confidence": "VERIFIED|LIKELY|UNCONFIRMED"},
  "general_condition_tier": "excellent|good|fair|poor|unknown",
  "condition_score": <integer 0-100, 100=pristine, 0=severely distressed>
}

Confidence rules: use VERIFIED only if a street-level image is present and the feature is clearly \
visible in it. Use LIKELY if only the aerial/satellite image supports the observation. Use \
UNCONFIRMED if you genuinely cannot tell from the available imagery -- do not guess. If only an \
aerial image is available, roof/vegetation can be VERIFIED or LIKELY but exterior/vacancy_signals \
should usually be UNCONFIRMED or LIKELY at best."""


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
# 2026-09-02 directive #3 (supersedes #2's Gemini/DeepSeek-direct routing):
# live-verified 2026-09-02 12:52 EDT by Ariel against a real Street View
# image -- HTTP 200 in 4.4s, coherent roof/exterior/vegetation rating,
# $0.000119/call. The ":free" slug is gone (404 "unavailable for free").
OPENROUTER_PRIMARY_MODEL = "z-ai/glm-5.3-flash"
OPENROUTER_FALLBACK_MODEL = "deepseek/deepseek-v4-flash-vision-exp"

_openrouter_model_cache: dict[str, bool] = {}


def _openrouter_model_available(model: str, api_key: str) -> bool:
    """Live-checks OpenRouter's /api/v1/models rather than assuming a slug
    exists -- directive #3 explicitly calls this out after the ':free' GLM
    slug vanished without notice. Cached per-process since this pipeline
    processes many rows per run and the model catalog doesn't change
    mid-run."""
    if model in _openrouter_model_cache:
        return _openrouter_model_cache[model]
    try:
        req = urllib.request.Request(OPENROUTER_MODELS_URL, headers={"Authorization": f"Bearer {api_key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        available = model in {m.get("id") for m in data.get("data", [])}
    except Exception:
        available = False
    _openrouter_model_cache[model] = available
    return available


def _openrouter_vision(image_paths: list[str], api_key: str, model: str,
                        extra_instruction: str | None = None) -> tuple[str, float | None]:
    """One OpenRouter chat-completions call with both images in a single
    message. Reasoning is mandatory on this endpoint (reasoning:{enabled:false}
    and effort:"none" both 400) -- max_tokens must be generous enough to
    survive the reasoning-token spend or content comes back null, per
    Ariel's 2026-09-02 12:52 EDT live test."""
    prompt = CONDITION_PROMPT + (f"\n\n{extra_instruction}" if extra_instruction else "")
    content = [{"type": "text", "text": prompt}]
    for p in image_paths:
        media_type = "image/png" if p.lower().endswith(".png") else "image/jpeg"
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}})

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1500,
        "temperature": 0,
    }
    req = urllib.request.Request(
        OPENROUTER_CHAT_URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"OpenRouter {model} HTTP {e.code}: {body[:300]}")
    choice = (data.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content")
    if not text:
        raise RuntimeError(f"OpenRouter {model} returned no content (finish_reason={choice.get('finish_reason')!r})")
    cost = (data.get("usage") or {}).get("cost")
    return text.strip(), cost


def _parse_condition_json(text: str) -> dict:
    # Models sometimes wrap JSON in a fenced code block despite instructions.
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def _claude_router_vision(image_paths: list[str], router_key: str) -> str:
    """Calls the claude-router edge function with the image(s) as vision
    input -- T3 fallback 2 (issue #19736 directive #3). The router's own
    cascade (T1 OpenRouter GLM -> T1.5 OpenRouter DeepSeek -> T2 Claude Haiku
    OAuth, per T10) is only reached here if this pipeline's own direct
    OpenRouter attempts above both failed -- since it hits the same
    OpenRouter API, that will typically fail identically and land straight
    on the router's T2 Claude Haiku OAuth tier."""
    images = []
    for p in image_paths:
        media_type = "image/png" if p.lower().endswith(".png") else "image/jpeg"
        b64 = base64.b64encode(open(p, "rb").read()).decode()
        images.append({"media_type": media_type, "data": b64})

    payload = {
        "messages": [{"role": "user", "content": CONDITION_PROMPT}],
        "images": images,
        "max_tokens": 2048,
        "source": "biddeed-reels-pipeline",
        "tool_name": "score_condition",
        "metadata": {"request_type": "analysis"},
    }
    url = f"{SUPABASE_URL}{CLAUDE_ROUTER_URL_PATH}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={
            "X-Router-Key": router_key,
            "apikey": SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"claude-router HTTP {e.code}: {body[:300]}")
    if "error" in data:
        raise RuntimeError(f"claude-router error: {data['error']}")
    text = data.get("text")
    if not text:
        raise RuntimeError(f"claude-router returned no text (tier={data.get('tier')})")
    return text.strip()


def score_condition(image_paths: list[str], keys: dict) -> dict:
    """T3 condition scoring (issue #19736 directive #3, supersedes directive
    #2's router-only routing):
      1. Primary: OpenRouter z-ai/glm-5.3-flash, both images in one call.
         On a JSON parse failure, retry once with an explicit "JSON only"
         nudge (per directive) before giving up on this tier.
      2. Fallback 1: OpenRouter deepseek-v4-flash-vision-exp -- only
         attempted if the slug is confirmed live on /api/v1/models (it has
         disappeared before, e.g. the ':free' GLM slug).
      3. Fallback 2: claude-router edge function (its T10 cascade lands on
         Claude Haiku OAuth once its own OpenRouter tiers fail the same way).
    `keys` = {"openrouter": ..., "router": ...}. Every attempt's provider +
    cost lands in the returned dict's "meta" key regardless of which tier
    actually answered, per directive #3 ("Log provider + cost per row")."""
    openrouter_key = keys.get("openrouter")
    attempts: list[str] = []
    parsed = None
    provider = None
    cost = None

    if openrouter_key:
        try:
            text, cost = _openrouter_vision(image_paths, openrouter_key, OPENROUTER_PRIMARY_MODEL)
            try:
                parsed = _parse_condition_json(text)
            except json.JSONDecodeError:
                text, cost = _openrouter_vision(
                    image_paths, openrouter_key, OPENROUTER_PRIMARY_MODEL,
                    extra_instruction="Your last reply was not valid JSON. Reply with JSON only "
                                      "-- no prose, no markdown code fences.",
                )
                parsed = _parse_condition_json(text)
            provider = "openrouter_glm"
        except Exception as e:
            attempts.append(f"openrouter_glm: {e}")

        if parsed is None:
            if _openrouter_model_available(OPENROUTER_FALLBACK_MODEL, openrouter_key):
                try:
                    text, cost = _openrouter_vision(image_paths, openrouter_key, OPENROUTER_FALLBACK_MODEL)
                    parsed = _parse_condition_json(text)
                    provider = "openrouter_deepseek"
                except Exception as e:
                    attempts.append(f"openrouter_deepseek: {e}")
            else:
                attempts.append("openrouter_deepseek: skipped (slug not present on /api/v1/models)")

    if parsed is None:
        router_key = keys.get("router")
        if not router_key:
            raise RuntimeError(f"all OpenRouter T3 tiers failed and no router key available: {'; '.join(attempts)}")
        try:
            text = _claude_router_vision(image_paths, router_key)
            parsed = _parse_condition_json(text)
            provider = "claude_router_fallback"
            cost = 0.0
        except Exception as e:
            attempts.append(f"claude_router_fallback: {e}")
            raise RuntimeError(f"all T3 vision tiers failed: {'; '.join(attempts)}")

    score = parsed.get("condition_score")
    if not isinstance(score, (int, float)) or not (0 <= score <= 100):
        raise ValueError(f"condition_score out of range or missing: {parsed!r}")

    parsed["meta"] = {"provider": provider, "cost_usd": cost, "failed_tiers": attempts or None}
    return parsed


# ---------------------------------------------------------------------------
# T4 -- script + caption (NO names, NO vendor names -- guardrail enforced
# below by construction: the template only ever interpolates county, sale
# type, dollar figures, and condition-tier phrases pulled from
# score_condition()'s controlled vocabulary, never a free-text buyer/entity
# field)
# ---------------------------------------------------------------------------

_SALE_TYPE_LABEL = {"foreclosure": "foreclosure sale", "tax_deed": "tax deed sale"}

_CONDITION_PHRASE = {
    "excellent": "move-in ready condition",
    "good": "solid, well-kept condition",
    "fair": "fixer-upper potential",
    "poor": "heavy rehab potential",
    "unknown": "condition pending review",
}

_HASHTAG_POOL = [
    "#FloridaRealEstate", "#FLRealEstate", "#RealEstateInvesting",
    "#PropertyDeals", "#AuctionDeals", "#InvestmentProperty", "#BidDeedAI",
]


def county_display(county_slug: str) -> str:
    return county_slug.replace("_", " ").title() + " County"


def build_script_and_caption(county_slug: str, sale_type: str, sold_amount: float,
                              assessed_value: float | None, condition: dict) -> dict:
    county_name = county_display(county_slug)
    sale_label = _SALE_TYPE_LABEL.get(sale_type, "auction sale")
    tier = (condition or {}).get("general_condition_tier", "unknown")
    condition_phrase = _CONDITION_PHRASE.get(tier, _CONDITION_PHRASE["unknown"])

    delta_pct = None
    delta_sentence = ""
    if assessed_value and assessed_value > 0:
        delta_pct = round((sold_amount - assessed_value) / assessed_value * 100, 1)
        direction = "below" if delta_pct < 0 else "above"
        delta_sentence = (
            f"That's {abs(delta_pct):.0f}% {direction} the county's ${assessed_value:,.0f} assessed value."
        )

    hook = f"A {sale_label} just closed in {county_name}, Florida for ${sold_amount:,.0f}."
    condition_sentence = f"Visual condition points to {condition_phrase}."
    cta = "See deals like this first — biddeed.ai."

    parts = [hook]
    if delta_sentence:
        parts.append(delta_sentence)
    parts.append(condition_sentence)
    parts.append(cta)
    script_text = " ".join(parts)

    caption_text = (
        f"{sale_label.capitalize()} in {county_name} — ${sold_amount:,.0f}. "
        f"{condition_sentence} {cta}"
    )

    hashtags = list(_HASHTAG_POOL[:4])
    county_tag = "#" + county_slug.replace("_", "").title() + "County"
    hashtags.append(county_tag)
    hashtags.append("#TaxDeedSale" if sale_type == "tax_deed" else "#ForeclosureAuction")
    hashtags = hashtags[:8]

    return {
        "script_text": script_text,
        "caption_text": caption_text,
        "hashtags": hashtags,
        "delta_pct": delta_pct,
    }


# ---------------------------------------------------------------------------
# T5 -- ElevenLabs Flash v2.5 TTS
# ---------------------------------------------------------------------------

def elevenlabs_tts(text: str, api_key: str, out_path: str, voice_id: str | None = None) -> None:
    voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": "eleven_flash_v2_5",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(out_path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------------------
# T7 -- ranking
# ---------------------------------------------------------------------------

def rank_score(delta_pct: float | None, condition_score: int | None, sold_amount: float | None) -> float:
    """Higher is better. Rewards a bigger discount to assessed value, worse
    (lower) condition score (more upside story), and bigger deal size, each
    normalized to a comparable 0-100ish scale so no single factor dominates
    by unit magnitude alone."""
    discount_component = max(0.0, -(delta_pct or 0.0))  # only reward below-assessed deals
    condition_component = 100 - (condition_score if condition_score is not None else 50)
    size_component = min((sold_amount or 0.0) / 5000.0, 100.0)  # saturates at $500k
    return round(discount_component * 0.5 + condition_component * 0.3 + size_component * 0.2, 2)


# ---------------------------------------------------------------------------
# T6 -- video assembly (ffmpeg)
# ---------------------------------------------------------------------------

INTER_BOLD_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf"
)
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

MAX_VIDEO_SECONDS = 45
END_CARD_SECONDS = 3


def _ensure_font() -> str:
    """Best-effort Inter (brand font). Falls back to DejaVu Sans Bold
    (already present on ubuntu-latest runners) if the download fails --
    logged, not a hard failure, since the brand font is a polish item, not
    a DoD requirement."""
    cache_path = "/tmp/biddeed_reels_inter_bold.ttf"
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path
    try:
        urllib.request.urlretrieve(INTER_BOLD_URL, cache_path)
        if os.path.getsize(cache_path) > 0:
            return cache_path
    except Exception as e:
        print(f"WARN: could not download Inter font, falling back to DejaVu Sans Bold: {e}")
    return FALLBACK_FONT


def _ffprobe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def assemble_video(aerial_path: str, street_path: str | None, audio_path: str,
                    overlays: dict, out_path: str) -> float:
    """Ken Burns pan/zoom over the stills, brand text overlays, voice track,
    1080x1920 9:16, <=45s, biddeed.ai end card. Returns duration_sec.

    Deviation from the issue's literal spec: no "royalty-free bed at low
    gain" is mixed in. No such licensed audio asset exists anywhere in this
    repo, and this pipeline has no music-licensing capability of its own --
    grabbing an unverified audio file off the internet to use as a bed track
    risks a real copyright problem for a client-facing asset, which is a
    worse outcome than a voice-only track. Flagged, not silently done.
    """
    font = _ensure_font()
    voice_duration = _ffprobe_duration(audio_path)
    main_duration = min(voice_duration, MAX_VIDEO_SECONDS - END_CARD_SECONDS)
    total_duration = main_duration + END_CARD_SECONDS

    stills = [aerial_path] + ([street_path] if street_path else [])
    n = len(stills)
    per_still = main_duration / n
    fps = 30

    filter_parts = []
    labels = []
    for i, still in enumerate(stills):
        frames = max(int(per_still * fps), 1)
        label = f"v{i}"
        filter_parts.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,zoompan=z='min(zoom+0.0006,1.15)':d={frames}:"
            f"s=1080x1920:fps={fps}[{label}]"
        )
        labels.append(label)

    end_card_idx = n
    filter_parts.append(
        f"color=c={BRAND_NAVY}:s=1080x1920:d={END_CARD_SECONDS}:r={fps}[precard]"
    )
    end_card_text = _escape_drawtext("biddeed.ai")
    filter_parts.append(
        f"[precard]drawtext=fontfile={font}:text='{end_card_text}':"
        f"fontcolor={BRAND_AMBER}:fontsize=90:x=(w-text_w)/2:y=(h-text_h)/2[card]"
    )
    labels.append("card")

    overlay_lines = [
        overlays.get("county", ""),
        overlays.get("sale_type_label", ""),
        f"SOLD ${overlays['sold_amount']:,.0f}" if overlays.get("sold_amount") else "",
        f"Assessed ${overlays['assessed_value']:,.0f}" if overlays.get("assessed_value") else "",
        overlays.get("condition_badge", ""),
    ]
    overlay_lines = [l for l in overlay_lines if l]

    concat_inputs = "".join(f"[{l}]" for l in labels)
    filter_parts.append(f"{concat_inputs}concat=n={len(labels)}:v=1:a=0[vconcat]")

    prev = "vconcat"
    for idx, line in enumerate(overlay_lines):
        y = 1500 + idx * 90
        txt = _escape_drawtext(line)
        nxt = f"vtext{idx}"
        filter_parts.append(
            f"[{prev}]drawtext=fontfile={font}:text='{txt}':fontcolor=white:fontsize=54:"
            f"box=1:boxcolor={BRAND_NAVY}@0.6:boxborderw=12:x=(w-text_w)/2:"
            f"y={y}:enable='lt(t,{main_duration})'[{nxt}]"
        )
        prev = nxt

    # Audio must span the FULL output (main content + end card), not just
    # the voice track's own length -- otherwise -shortest (or an implicit
    # stream-length mismatch) truncates the end card almost entirely, which
    # is exactly what an earlier version of this function did (caught by
    # this module's own smoke test before this was ever wired into the
    # pipeline). atrim guards the case where the voice track was capped by
    # MAX_VIDEO_SECONDS and is actually longer than main_duration.
    filter_parts.append(
        f"[{n}:a]atrim=0:{main_duration},apad=pad_dur={END_CARD_SECONDS}[aout]"
    )

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"]
    for still in stills:
        cmd += ["-loop", "1", "-t", str(per_still), "-i", still]
    cmd += [
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", f"[{prev}]",
        "-map", "[aout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-t", str(total_duration),
        out_path,
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return _ffprobe_duration(out_path)
