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
import random
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

# v2 brand voice (issue #19752 addendum, 2026-09-02 20:30 EDT): "one
# consistent brand voice ... energetic, American English, mid-register".
# Checked GET /v2/voices on the account's own library (21 premade voices) --
# "Liam - Energetic, Social Media Creator" (american, male, mid-register,
# use_case=social_media) is the only voice explicitly labeled "Energetic"
# with an American accent and a social-media use case, i.e. the closest
# real match to the brief rather than a guess. Override with
# ELEVENLABS_V2_VOICE_ID if Ariel wants a different one from the library.
V2_BRAND_VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"
V2_TTS_MODEL = "eleven_v3"

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
            # api.supabase.com sits behind Cloudflare bot protection that
            # intermittently 403s (error 1010) on the bare default/custom
            # urllib UA string -- live-reproduced and fixed this session
            # (#19752): a browser-shaped UA consistently passes.
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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


# v2 condition-beat pills (issue #19752 QA blocker 2, 2026-09-02 21:11 EDT):
# the video was overlaying condition_json's raw free-text `observation`
# strings ("Dark shingle roof appears intact with some weathering/staining
# visible...") which overflow a 38px-fontsize drawtext box. Spec wants
# short "Roof: weathered" style pills, <=22 chars, derived from the same
# observation text via keyword match -- no re-scoring, no new vision call.
_PILL_PREFIX = {
    "roof": "Roof",
    "exterior": "Siding",
    "vegetation_overgrowth": "Lot",
    "vacancy_signals": "Activity",
}
_PILL_KEYWORDS = [
    ("overgrown", "overgrown"), ("weathering", "weathered"), ("weathered", "weathered"),
    ("staining", "stained"), ("stained", "stained"), ("damage", "damaged"),
    ("missing", "missing"), ("intact", "intact"), ("well-kept", "well-kept"),
    ("well kept", "well-kept"), ("mowed", "mowed"), ("bare", "bare patches"),
    ("dry", "dry patches"), ("vacant", "vacant"), ("boarded", "boarded up"),
    ("broken", "broken"), ("worn", "worn"), ("solid", "solid"),
    ("active use", "active"), ("no vacancy", "active"), ("trash", "active"),
    ("good condition", "good"), ("poor condition", "poor"),
]


def condition_pill_label(field_key: str, observation: str) -> str:
    prefix = _PILL_PREFIX.get(field_key, field_key.replace('_', ' ').title())
    text = (observation or "").lower()
    label = next((tag for kw, tag in _PILL_KEYWORDS if kw in text), "noted")
    return f"{prefix}: {label}"[:22]


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
# v2 T4/T5 -- ElevenLabs eleven_v3 TTS with inline audio tags (issue #19752
# addendum, 2026-09-02 20:30 EDT). Separate function from v1's Flash path
# above rather than an in-place swap, per directive: v1 rows/behavior stay
# untouched, only v2 renders use this.
# ---------------------------------------------------------------------------

def elevenlabs_tts_v3(text: str, api_key: str, out_path: str, voice_id: str | None = None) -> None:
    voice_id = voice_id or os.environ.get("ELEVENLABS_V2_VOICE_ID", V2_BRAND_VOICE_ID)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    payload = {
        "text": text,
        "model_id": V2_TTS_MODEL,
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


# ---------------------------------------------------------------------------
# v2 (issue #19752) -- T1 parcel-outline imagery
# ---------------------------------------------------------------------------

STATIC_MAP_URL = "https://maps.googleapis.com/maps/api/staticmap"
OUTLINE_COLOR = "0x00E5FFff"
OUTLINE_FILL = "0x00E5FF33"
MAX_STATIC_MAP_URL_LEN = 8000


def slugify_case_number(case_number: str) -> str:
    """Mirrors public.slugify_case_number() (20260902l migration) exactly --
    the pipeline builds landing_url with this, the landing-page RPC looks
    slugs up with the SQL twin. Keep both in sync if either changes."""
    return re.sub(r"[^a-z0-9]+", "-", (case_number or "").lower()).strip("-")


def match_zw_parcel_geom(county: str, parcel_id: str) -> dict | None:
    """v2 T1 join -- case-insensitive county + pin_clean, the live-verified
    join key from the issue body (11/11 v1 rows with a parcel_id matched
    zw_parcels this way; the v1 join only failed on county-name case).

    Runs via the Management API (not PostgREST) because
    ST_SimplifyPreserveTopology/ST_AsGeoJSON aren't PostgREST-callable SQL.
    Polygons >40 points are simplified per T1's explicit tolerance (0.00001,
    ~1m at FL latitudes) before GeoJSON extraction. Returns None (not an
    exception) on no match -- caller falls back to a pin marker
    (parcel_outline=false), never fabricates a boundary."""
    if not parcel_id:
        return None
    county_q = (county or "").replace("_", " ").lower()
    rows = run_sql(f"""
        select z.id as zw_parcel_id, z.centroid_lat, z.centroid_lon, z.pa_link,
               ST_NPoints(z.geom) as npoints,
               ST_AsGeoJSON(
                 case when ST_NPoints(z.geom) > 40
                   then ST_SimplifyPreserveTopology(z.geom, 0.00001)
                   else z.geom
                 end
               ) as geojson
        from public.zw_parcels z
        where lower(z.county) = {sql_str(county_q)}
          and z.pin_clean = regexp_replace({sql_str(parcel_id)}, '[^A-Za-z0-9]', '', 'g')
        limit 1;
    """)
    return rows[0] if rows else None


def geojson_ring_latlng(geojson_obj: dict) -> list[tuple[float, float]]:
    """Exterior ring of a Polygon/MultiPolygon as (lat, lng) pairs -- GeoJSON
    stores (lng, lat); the Static Maps `path=` parameter wants lat,lng."""
    t = geojson_obj.get("type")
    coords = geojson_obj.get("coordinates")
    if t == "Polygon":
        ring = coords[0]
    elif t == "MultiPolygon":
        ring = coords[0][0]
    else:
        raise ValueError(f"unexpected geometry type for parcel outline: {t}")
    return [(lat, lng) for lng, lat in ring]


def _encode_polyline_value(v: int) -> str:
    v = v << 1
    if v < 0:
        v = ~v
    chunks = []
    while v >= 0x20:
        chunks.append(chr((0x20 | (v & 0x1F)) + 63))
        v >>= 5
    chunks.append(chr(v + 63))
    return "".join(chunks)


def encode_polyline(points: list[tuple[float, float]]) -> str:
    """Google encoded-polyline algorithm -- the `path=enc:...` fallback T1
    calls for once the literal lat,lng list pushes the Static Maps URL past
    ~8kB (large/complex parcels, e.g. the 96-point Broward polygon)."""
    out = []
    prev_lat = prev_lng = 0
    for lat, lng in points:
        lat_e5 = round(lat * 1e5)
        lng_e5 = round(lng * 1e5)
        out.append(_encode_polyline_value(lat_e5 - prev_lat))
        out.append(_encode_polyline_value(lng_e5 - prev_lng))
        prev_lat, prev_lng = lat_e5, lng_e5
    return "".join(out)


def _path_points_param(points: list[tuple[float, float]]) -> str:
    literal = "|".join(f"{lat:.7f},{lng:.7f}" for lat, lng in points)
    if len(literal) <= MAX_STATIC_MAP_URL_LEN - 400:
        return literal
    return "enc:" + encode_polyline(points)


def build_parcel_aerial_urls(lat: float, lon: float, ring_points: list[tuple[float, float]],
                              api_key: str) -> tuple[str, str]:
    """v2 T1: TWO aerials, both drawing the real parcel boundary via the
    Static Maps `path=` parameter (live-verified by Ariel 2026-09-02 against
    the Escambia parcel -- HTTP 200 at zoom 18 and 20, scale=2, outline sits
    exactly on the lot). wide = zoom 18, outline only. tight = zoom 20,
    outline + translucent fill."""
    points_param = _path_points_param(ring_points)
    wide = (
        f"{STATIC_MAP_URL}?center={lat},{lon}&zoom=18&size=640x640&scale=2"
        f"&maptype=satellite&path=color:{OUTLINE_COLOR}|weight:6|{points_param}"
        f"&key={api_key}"
    )
    tight = (
        f"{STATIC_MAP_URL}?center={lat},{lon}&zoom=20&size=640x640&scale=2"
        f"&maptype=satellite&path=color:{OUTLINE_COLOR}|weight:6|fillcolor:{OUTLINE_FILL}|{points_param}"
        f"&key={api_key}"
    )
    return wide, tight


def build_tight_aerial_url(lat: float, lon: float, zoom: int, api_key: str) -> str:
    """Plain (no-outline) aerial at an arbitrary zoom -- used as T1's
    Street-View substitute ('a second tight aerial at zoom 19') when
    streetview_metadata_ok() comes back false."""
    return (
        f"{STATIC_MAP_URL}?center={lat},{lon}&zoom={zoom}&size=640x640&scale=2"
        f"&maptype=satellite&key={api_key}"
    )


def build_pin_aerial_urls(lat: float, lon: float, api_key: str) -> tuple[str, str]:
    """No parcel geometry -- markers= pin fallback (T1), parcel_outline=false."""
    wide = (
        f"{STATIC_MAP_URL}?center={lat},{lon}&zoom=18&size=640x640&scale=2"
        f"&maptype=satellite&markers=color:0x00E5FF|{lat},{lon}&key={api_key}"
    )
    tight = (
        f"{STATIC_MAP_URL}?center={lat},{lon}&zoom=20&size=640x640&scale=2"
        f"&maptype=satellite&markers=color:0x00E5FF|{lat},{lon}&key={api_key}"
    )
    return wide, tight


def fetch_url_to_file(url: str, out_path: str) -> None:
    urllib.request.urlretrieve(url, out_path)


# ---------------------------------------------------------------------------
# v2 -- T3 short link + QR
# ---------------------------------------------------------------------------

_BASE62 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def gen_short_code(n: int = 6) -> str:
    return "".join(random.choice(_BASE62) for _ in range(n))


def generate_qr_png(data: str, out_path: str) -> None:
    """Local QR generation (Python `qrcode`, no external API -- T3 spec)."""
    import qrcode  # local import: only needed by the v2 pipeline's T3 step

    img = qrcode.make(data, box_size=12, border=3)
    img.save(out_path)


# ---------------------------------------------------------------------------
# v2 -- T4 script/caption v2 (hook-first beat list, no names/vendors)
# ---------------------------------------------------------------------------

def pick_hook_variant(delta_pct: float | None, sold_amount: float) -> str:
    """3 hook variants by |delta_pct| band, per T4. Guardrail: only
    interpolates sold_amount (a controlled numeric field) -- no free-text."""
    mag = abs(delta_pct) if delta_pct is not None else 0
    if mag >= 50:
        return f"Sold for ${sold_amount:,.0f}. That's less than half what the county says it's worth."
    if mag >= 30:
        return f"This just sold for ${sold_amount:,.0f} -- well under the county's own number."
    return f"Sold for ${sold_amount:,.0f} at auction."


def build_script_and_caption_v2(county_slug: str, sale_type: str, sold_amount: float,
                                 assessed_value: float | None, condition: dict,
                                 short_url: str) -> dict:
    """v2 T4 beat-list script (hook -> reveal -> street/delta -> condition ->
    payoff -> CTA), same no-names/no-vendor guardrail as v1's
    build_script_and_caption() -- only county/sale-type/dollar/condition-tier
    controlled fields are ever interpolated."""
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

    hook = pick_hook_variant(delta_pct, sold_amount)
    reveal = f"Here's the parcel in {county_name}, Florida -- a {sale_label}."
    condition_sentence = f"Visual condition points to {condition_phrase}."
    payoff = "This is what our AI sees before you do."
    cta = "See deals like this first -- biddeed.ai."

    parts = [hook, reveal]
    if delta_sentence:
        parts.append(delta_sentence)
    parts.append(condition_sentence)
    parts.append(payoff)
    parts.append(cta)
    script_text = " ".join(parts)

    # v3 tagged variant for TTS only (issue #19752 addendum, 2026-09-02 20:30
    # EDT): eleven_v3 inline audio tags, one per sentence max -- hook
    # [excited], the assessed-value contrast [surprised], condition beat
    # untagged/neutral, CTA [warm]. caption_text below is built from
    # condition_sentence/cta directly (never hook/delta_sentence), so these
    # tags never leak into the public caption.
    v3_parts = [f"[excited] {hook}", reveal]
    if delta_sentence:
        v3_parts.append(f"[surprised] {delta_sentence}")
    v3_parts.append(condition_sentence)
    v3_parts.append(payoff)
    v3_parts.append(f"[warm] {cta}")
    script_text_v3 = " ".join(v3_parts)[:650]

    # Directive #4 (Ariel, 2026-09-02 21:16 EDT, new T8): line 1 hook, line 2
    # the watch/property CTA with the short link, hashtags appended after
    # (hashtags stay a separate returned list -- callers append them, same
    # as before this change).
    caption_text = f"{hook}\n▶ Watch + property: {short_url}"

    hashtags = list(_HASHTAG_POOL[:4])
    county_tag = "#" + county_slug.replace("_", "").title() + "County"
    hashtags.append(county_tag)
    hashtags.append("#TaxDeedSale" if sale_type == "tax_deed" else "#ForeclosureAuction")
    hashtags = hashtags[:8]

    return {
        "script_text": script_text,
        "script_text_v3": script_text_v3,
        "caption_text": caption_text,
        "hashtags": hashtags,
        "delta_pct": delta_pct,
    }


# ---------------------------------------------------------------------------
# v2 -- T4 video assembly (hook -> reveal -> street/delta -> condition ->
# payoff -> CTA beats, fixed-length regardless of voiceover length, per T4)
# ---------------------------------------------------------------------------

V2_SEGMENT_SECONDS = {
    "hook": 1.5,
    "reveal": 4.5,
    "street": 7.0,
    "condition": 7.0,
    "payoff": 7.0,
}
V2_ORDER = ["hook", "reveal", "street", "condition", "payoff"]
V2_END_CARD_SECONDS = 3.0
V2_FPS = 30
V2_TOTAL_SECONDS = sum(V2_SEGMENT_SECONDS.values()) + V2_END_CARD_SECONDS  # 30.0


def _dt(font: str, text: str, **opts) -> str:
    """drawtext filter builder -- text is single-quoted + escaped per
    _escape_drawtext (colon/backslash/quote only; commas are safe inside the
    quoted value, live-verified in v1's own "$39,600"-style overlays)."""
    parts = [f"fontfile={font}", f"text='{_escape_drawtext(text)}'"]
    for k, v in opts.items():
        parts.append(f"{k}={v}")
    return "drawtext=" + ":".join(parts)


def assemble_video_v2(images: dict, audio_path: str, overlays: dict,
                       qr_path: str, short_url: str, out_path: str) -> float:
    """v2 T4 edit -- 5 fixed-duration beats (hook/reveal/street/condition/
    payoff, 27s) + a 3s QR/short-URL CTA card = 30s, 1080x1920, 30fps.

    `images` = {"hook": path, "reveal": path, "street": path,
    "condition": path, "payoff": path} (each a still image; street/condition
    reuse the tight aerial when no real Street View exists -- see
    process_row_v2's substitution). `overlays` = county, sale_type_label,
    sold_amount, assessed_value, delta_pct, condition_tier, condition_bullets
    (<=2 short phrases from condition_json).

    Deviations from the issue's literal beat list (logged, not silent):
    hard cuts between all beats rather than a crossfade dissolve on the
    hook->reveal transition, no pulsing-outline re-render on the reveal
    aerial, and no bass-hit/ducked music bed (same no-unlicensed-audio call
    v1 made -- no royalty-free asset exists anywhere in this repo/org).
    The delta-vs-assessed counter IS a real animated count-up (ffmpeg
    drawtext `%{eif:...}` text expansion, 0 -> |delta_pct| over 3s), not a
    static number.
    """
    font = _ensure_font()
    fps = V2_FPS

    filter_parts = []
    labels = []
    for i, key in enumerate(V2_ORDER):
        d = V2_SEGMENT_SECONDS[key]
        frames = max(int(d * fps), 1)
        zoom_expr = "min(zoom+0.0035,1.12)" if key == "hook" else "min(zoom+0.0009,1.18)"
        cur = f"v{i}raw"
        # trim right after zoompan is load-bearing, not cosmetic: zoompan's
        # `d` holds EACH incoming source frame for d output frames, and a
        # looped image input still redelivers a "new" source frame every
        # 1/25s (image2 demuxer default). With `-t` set on the input (no
        # trim here), that plus zoompan's d multiplies out to source_frames
        # * d -- live-reproduced this session: a 1.5s hook segment exploded
        # to 1710 frames (57s), starving every later concat segment of ever
        # being reached (the whole 30s output stayed frozen on segment 0).
        # trim=end_frame + an untrimmed (no -t) looped input means zoompan
        # only ever needs its first source frame before this trim cuts it.
        filter_parts.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,zoompan=z='{zoom_expr}':d={frames}:s=1080x1920:fps={fps},"
            f"trim=start_frame=0:end_frame={frames},setpts=PTS-STARTPTS[{cur}]"
        )

        if key == "hook":
            hook_text = f"SOLD ${overlays['sold_amount']:,.0f}"
            nxt = f"v{i}a"
            # NOTE: any option value containing an unquoted ',' (e.g. alpha's
            # min()/if() expressions) gets mis-split by ffmpeg's top-level
            # filtergraph parser -- live-reproduced this session -- so it
            # must carry its OWN literal single-quote characters, same as
            # text= values, not just be a plain Python string.
            hook_alpha = "'min(t/0.25,1)'"
            filter_parts.append(
                f"[{cur}]{_dt(font, hook_text, fontcolor='white', fontsize=120, box=1, boxcolor=f'{BRAND_NAVY}@0.75', boxborderw=24, x='(w-text_w)/2', y='(h-text_h)/2-60', alpha=hook_alpha)}[{nxt}]"
            )
            cur = nxt
            if overlays.get("assessed_value"):
                sub_text = f"Assessed ${overlays['assessed_value']:,.0f}"
                nxt2 = f"v{i}b"
                sub_alpha = "'if(lt(t,0.3),0,min((t-0.3)/0.25,1))'"
                filter_parts.append(
                    f"[{cur}]{_dt(font, sub_text, fontcolor='white', fontsize=52, box=1, boxcolor=f'{BRAND_AMBER}@0.85', boxborderw=16, x='(w-text_w)/2', y='(h+text_h)/2+30', alpha=sub_alpha)}[{nxt2}]"
                )
                cur = nxt2

        elif key == "reveal":
            lower_third = f"{overlays['county']} County - {overlays['sale_type_label']}"
            nxt = f"v{i}a"
            filter_parts.append(
                f"[{cur}]{_dt(font, lower_third, fontcolor='white', fontsize=44, box=1, boxcolor=f'{BRAND_NAVY}@0.7', boxborderw=16, x='(w-text_w)/2', y=1650)}[{nxt}]"
            )
            cur = nxt

        elif key == "street":
            delta = overlays.get("delta_pct")
            if delta is not None:
                sign = "-" if delta < 0 else "+"
                mag = abs(delta)
                # v1 sidestepped a literal '%' with "PCT" because a bare '%'
                # breaks drawtext's %{...} expansion parser ("Stray %").
                # QA (2026-09-02 21:11 EDT) wants the real '-64%' glyph.
                # Live-verified this session against this exact ffmpeg build
                # (6.1.1-3ubuntu5, via `tesseract`-checked render tests):
                # neither '%%' nor '\%' survive inside a text string that
                # also contains an active %{eif:...} expansion -- both still
                # throw "Stray %" and drop the whole drawtext. The escape
                # that DOES work is putting the literal '%' in a SEPARATE
                # drawtext layer with expansion=none (which ffmpeg's parser
                # never treats '%' specially in), chained right after the
                # animated-number layer instead of concatenated into one
                # string.
                counter = f"{sign}%{{eif\\:{mag}*min(t/3\\,1)\\:d}}"
                nxt = f"v{i}a"
                filter_parts.append(
                    f"[{cur}]drawtext=fontfile={font}:text='{counter}':fontcolor=white:fontsize=72:"
                    f"box=1:boxcolor={BRAND_NAVY}@0.75:boxborderw=20:x='w/2-200':y=1550[{nxt}]"
                )
                cur = nxt
                nxt2 = f"v{i}a2"
                filter_parts.append(
                    f"[{cur}]drawtext=fontfile={font}:text='% vs assessed':expansion=none:fontcolor=white:fontsize=72:"
                    f"box=1:boxcolor={BRAND_NAVY}@0.75:boxborderw=20:x='w/2-30':y=1550[{nxt2}]"
                )
                cur = nxt2

        elif key == "condition":
            tier = (overlays.get("condition_tier") or "unknown").title()
            nxt = f"v{i}a"
            filter_parts.append(
                f"[{cur}]{_dt(font, tier + ' condition', fontcolor='#020617', fontsize=54, box=1, boxcolor=BRAND_AMBER, boxborderw=20, x='(w-text_w)/2', y=180)}[{nxt}]"
            )
            cur = nxt
            for bi, bullet in enumerate((overlays.get("condition_bullets") or [])[:2]):
                nxt2 = f"v{i}b{bi}"
                y = 1480 + bi * 100
                filter_parts.append(
                    f"[{cur}]{_dt(font, '- ' + bullet, fontcolor='white', fontsize=38, box=1, boxcolor=f'{BRAND_NAVY}@0.65', boxborderw=14, x='(w-text_w)/2', y=y)}[{nxt2}]"
                )
                cur = nxt2

        elif key == "payoff":
            nxt = f"v{i}a"
            filter_parts.append(
                f"[{cur}]{_dt(font, 'This is what our AI sees before you do.', fontcolor='white', fontsize=58, box=1, boxcolor=f'{BRAND_NAVY}@0.6', boxborderw=20, x='(w-text_w)/2', y='(h-text_h)/2')}[{nxt}]"
            )
            cur = nxt

        filter_parts.append(f"[{cur}]copy[vb{i}]")
        labels.append(f"vb{i}")

    # -- CTA end card: navy background + QR (input index len(V2_ORDER)+1) +
    # short URL + biddeed.ai wordmark --
    card_idx = len(V2_ORDER)
    qr_idx = len(V2_ORDER) + 1
    filter_parts.append(
        f"color=c={BRAND_NAVY}:s=1080x1920:d={V2_END_CARD_SECONDS}:r={fps}[cardbg]"
    )
    filter_parts.append(f"[{qr_idx}:v]scale=480:480[qrscaled]")
    filter_parts.append("[cardbg][qrscaled]overlay=(W-w)/2:420[cardqr]")
    filter_parts.append(
        f"[cardqr]{_dt(font, short_url, fontcolor=BRAND_AMBER.replace('0x', '#'), fontsize=56, x='(w-text_w)/2', y=1000)}[cardurl]"
    )
    filter_parts.append(
        f"[cardurl]{_dt(font, 'biddeed.ai', fontcolor='white', fontsize=70, x='(w-text_w)/2', y=1120)}[cardbrand]"
    )
    filter_parts.append(
        f"[cardbrand]{_dt(font, 'Link in bio', fontcolor='#94A3B8', fontsize=36, x='(w-text_w)/2', y=1220)}[card]"
    )
    labels.append("card")

    concat_inputs = "".join(f"[{l}]" for l in labels)
    filter_parts.append(f"{concat_inputs}concat=n={len(labels)}:v=1:a=0[vconcat]")

    main_duration = sum(V2_SEGMENT_SECONDS.values())
    total_duration = main_duration + V2_END_CARD_SECONDS
    audio_idx = len(V2_ORDER)  # the audio input directly follows the 5 image inputs
    filter_parts.append(
        f"[{audio_idx}:a]atrim=0:{main_duration},apad=pad_dur={V2_END_CARD_SECONDS}[aout]"
    )

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"]
    for key in V2_ORDER:
        # No `-t` here on purpose -- see the trim= comment above. The input
        # loops indefinitely; the per-chain trim= is what bounds it.
        cmd += ["-loop", "1", "-i", images[key]]
    cmd += ["-i", audio_path]
    cmd += ["-loop", "1", "-t", str(V2_END_CARD_SECONDS), "-i", qr_path]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vconcat]",
        "-map", "[aout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-t", str(total_duration),
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg v2 assembly failed: {result.stderr[-3000:]}")
    return _ffprobe_duration(out_path)


# ---------------------------------------------------------------------------
# v3 (issue #19761) -- PRESALE (calendar/upcoming-auction) reels + deal pages.
# Builds on v2's parcel-outline imagery / short-link / QR path -- everything
# above this section (match_zw_parcel_geom, build_parcel_aerial_urls,
# build_pin_aerial_urls, geocode_address, streetview_metadata_ok,
# fetch_streetview, score_condition, ensure/gen_short_code, generate_qr_png,
# elevenlabs_tts_v3) is reused as-is. Only ranking, script/caption, and video
# assembly are presale-specific (different beat text: opening bid instead of
# sold price, a countdown instead of a sale-outcome delta).
# ---------------------------------------------------------------------------

# T4 price_tier -> numeric component. v_upcoming_auctions_ssot.price_tier was
# null on all 8 live 2026-09-04 rows checked this session -- no real tier
# value has been observed yet, so this mapping is INFERRED from the column
# name alone, not from a confirmed enum. Any value not in this map (including
# null) falls back to the 50 neutral midpoint, same as every other unscored
# input to rank_presale_score() below -- a guessed mapping never has more
# than +/-15 * 0.5 = 7.5pts of influence on the final 0-100 score either way.
_PRICE_TIER_SCORE = {
    "entry": 65.0, "starter": 65.0, "low": 65.0,
    "mid": 50.0, "core": 50.0,
    "premium": 35.0, "high": 35.0, "luxury": 20.0,
}


def rank_presale_score(gap_pct: float | None, zip_score: float | None,
                        price_tier: str | None, condition_score: int | None) -> float:
    """v3 T4: presale_rank = f(assessed-vs-bid gap %, zip_score, price_tier,
    condition_score). Weights (0.4 gap / 0.25 zip / 0.2 condition / 0.15
    price_tier) mirror rank_score()'s existing discount/condition/size split
    for postsale rows, extended with a zip factor. Every input can be null on
    a real row (opening_bid/judgment_amount/price_tier/zip_score were null on
    8/8 live rows checked for 2026-09-04) -- a null input contributes the 50
    neutral midpoint rather than crashing or zeroing the row out of ranking
    entirely. Distinct from rank_score()/the `rank_score` column, which stay
    postsale-only (see the `presale_rank` column's own comment)."""
    gap_component = 50.0 if gap_pct is None else max(0.0, min(gap_pct, 100.0))
    zip_component = 50.0 if zip_score is None else max(0.0, min(float(zip_score), 100.0))
    condition_component = 50.0 if condition_score is None else (100 - condition_score)
    price_component = _PRICE_TIER_SCORE.get((price_tier or "").strip().lower(), 50.0)
    return round(
        gap_component * 0.4 + zip_component * 0.25 + condition_component * 0.2 + price_component * 0.15, 2
    )


def pick_presale_hook_variant(gap_pct: float | None) -> str:
    """3 hook variants keyed to |gap_pct| band, per T4 (>=50%, 25-50%, <25%).
    A 4th case (gap_pct unknown -- no opening_bid/judgment_amount posted yet)
    is not one of the issue's 3 named bands but is a real, common live state
    (8/8 rows checked 2026-09-04) that must not crash or fabricate a number."""
    if gap_pct is None:
        return "Auction day is almost here for this Florida property."
    mag = abs(gap_pct)
    if mag >= 50:
        return "This opens at less than half what the county says it's worth."
    if mag >= 25:
        return "This opens well under the county's own assessed value."
    return "This opens close to the county's full assessed value."


def build_presale_script_and_caption(county_slug: str, sale_type: str,
                                      opening_bid: float | None, judgment_amount: float | None,
                                      assessed_value: float | None, condition: dict,
                                      days_to_auction: int | None, short_url: str) -> dict:
    """v3 T4 presale beat-list script (hook -> bid -> reveal -> gap ->
    condition -> payoff -> CTA). Same no-names/no-vendor guardrail as v1/v2's
    script builders -- only county/sale-type/dollar/condition-tier controlled
    fields are ever interpolated, never a free-text field."""
    county_name = county_display(county_slug)
    sale_label = _SALE_TYPE_LABEL.get(sale_type, "auction sale")
    tier = (condition or {}).get("general_condition_tier", "unknown")
    condition_phrase = _CONDITION_PHRASE.get(tier, _CONDITION_PHRASE["unknown"])

    basis_bid = opening_bid if opening_bid is not None else judgment_amount
    basis_label = "Opening bid" if opening_bid is not None else ("Judgment amount" if judgment_amount is not None else None)

    gap_pct = None
    gap_sentence = ""
    if basis_bid and assessed_value and assessed_value > 0:
        gap_pct = round((assessed_value - basis_bid) / assessed_value * 100, 1)
        direction = "below" if gap_pct > 0 else "above"
        gap_sentence = f"That's {abs(gap_pct):.0f}% {direction} the county's ${assessed_value:,.0f} assessed value."

    hook = pick_presale_hook_variant(gap_pct)
    bid_sentence = f"{basis_label} is ${basis_bid:,.0f}." if basis_bid else "Opening bid hasn't posted yet."
    day_word = "day" if days_to_auction == 1 else "days"
    reveal = (
        f"Here's the parcel in {county_name}, Florida -- a {sale_label} coming up in "
        f"{days_to_auction if days_to_auction is not None else 'a few'} {day_word}."
    )
    condition_sentence = f"Visual condition points to {condition_phrase}."
    payoff = "Bid with data, not guesses."
    cta = "Track it now -- biddeed.ai."

    parts = [hook, bid_sentence, reveal]
    if gap_sentence:
        parts.append(gap_sentence)
    parts.append(condition_sentence)
    parts.append(payoff)
    parts.append(cta)
    script_text = " ".join(parts)

    # v3 eleven_v3-tagged variant for TTS only -- same tag convention as
    # build_script_and_caption_v2 (hook [excited], CTA [warm], everything
    # else untagged/neutral). Never leaks into caption_text.
    v3_parts = [f"[excited] {hook}", bid_sentence, reveal]
    if gap_sentence:
        v3_parts.append(f"[surprised] {gap_sentence}")
    v3_parts.append(condition_sentence)
    v3_parts.append(payoff)
    v3_parts.append(f"[warm] {cta}")
    script_text_v3 = " ".join(v3_parts)[:650]

    caption_text = f"{hook}\n▶ Track it: {short_url}"

    hashtags = list(_HASHTAG_POOL[:4])
    county_tag = "#" + county_slug.replace("_", "").title() + "County"
    hashtags.append(county_tag)
    hashtags.append("#TaxDeedSale" if sale_type == "tax_deed" else "#ForeclosureAuction")
    hashtags.append("#UpcomingAuction")
    hashtags = hashtags[:8]

    return {
        "script_text": script_text,
        "script_text_v3": script_text_v3,
        "caption_text": caption_text,
        "hashtags": hashtags,
        "gap_pct": gap_pct,
        "basis_bid": basis_bid,
        "basis_label": basis_label,
    }


def month_abbr_day(date_str: str) -> str:
    """'2026-09-04' -> 'SEP 4' (no strftime %-d -- not portable across libc,
    live-verified failure mode on some ffmpeg/py builds)."""
    import datetime
    d = datetime.date.fromisoformat(date_str)
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    return f"{months[d.month - 1]} {d.day}"


def assemble_video_presale(images: dict, audio_path: str, overlays: dict,
                            qr_path: str, short_url: str, out_path: str) -> float:
    """v3 T4 presale edit -- same 5-beat + CTA-card structure as
    assemble_video_v2 (hook/reveal/street/condition/payoff, 27s, + 3s
    QR/short-URL CTA card = 30s, 1080x1920, 30fps), with presale beat text:
    hook = "AUCTION {DAY}" slam + opening-bid sub (v2's hook was "SOLD $X"),
    street beat = a static "Assessed $Y" figure (v2 animated a delta-%
    count-up here; presale has no sale-outcome delta to animate against, so
    this is a static drawtext, not a re-implementation of the count-up),
    payoff = "Bid with data, not guesses." (v2's was different), CTA card
    gains a "{N} days to auction" countdown chip. `overlays` requires an
    `auction_date_label` (pre-formatted "SEP 4" via _month_abbr_day),
    `opening_bid_label` ("Opening bid $X,XXX" or "Opening bid TBD"),
    `assessed_value`, `county`, `sale_type_label`, `condition_tier`,
    `condition_bullets` (<=2), `days_to_auction`.

    Deviations from the issue's literal beat list (logged, not silent): hard
    cuts between beats (no crossfade/pulsing-outline re-render), no bass-hit
    audio cue on the hook and no music bed under the voice track -- same
    no-unlicensed-audio call v1/v2 already made (no royalty-free asset exists
    anywhere in this repo/org).
    """
    font = _ensure_font()
    fps = V2_FPS

    filter_parts = []
    labels = []
    for i, key in enumerate(V2_ORDER):
        d = V2_SEGMENT_SECONDS[key]
        frames = max(int(d * fps), 1)
        zoom_expr = "min(zoom+0.0035,1.12)" if key == "hook" else "min(zoom+0.0009,1.18)"
        cur = f"p{i}raw"
        # Same load-bearing trim= as assemble_video_v2 -- see that function's
        # comment for why an untrimmed looped input + trim=end_frame is
        # required (a bare -t on the input multiplies frame count with
        # zoompan's own `d` and starves later concat segments).
        filter_parts.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,zoompan=z='{zoom_expr}':d={frames}:s=1080x1920:fps={fps},"
            f"trim=start_frame=0:end_frame={frames},setpts=PTS-STARTPTS[{cur}]"
        )

        if key == "hook":
            hook_text = f"AUCTION {overlays['auction_date_label']}"
            nxt = f"p{i}a"
            hook_alpha = "'min(t/0.25,1)'"
            filter_parts.append(
                f"[{cur}]{_dt(font, hook_text, fontcolor='white', fontsize=110, box=1, boxcolor=f'{BRAND_NAVY}@0.75', boxborderw=24, x='(w-text_w)/2', y='(h-text_h)/2-60', alpha=hook_alpha)}[{nxt}]"
            )
            cur = nxt
            sub_text = overlays.get("opening_bid_label") or "Opening bid TBD"
            nxt2 = f"p{i}b"
            sub_alpha = "'if(lt(t,0.3),0,min((t-0.3)/0.25,1))'"
            filter_parts.append(
                f"[{cur}]{_dt(font, sub_text, fontcolor='white', fontsize=48, box=1, boxcolor=f'{BRAND_AMBER}@0.85', boxborderw=16, x='(w-text_w)/2', y='(h+text_h)/2+30', alpha=sub_alpha)}[{nxt2}]"
            )
            cur = nxt2

        elif key == "reveal":
            lower_third = f"{overlays['county']} County - {overlays['sale_type_label']}"
            nxt = f"p{i}a"
            filter_parts.append(
                f"[{cur}]{_dt(font, lower_third, fontcolor='white', fontsize=44, box=1, boxcolor=f'{BRAND_NAVY}@0.7', boxborderw=16, x='(w-text_w)/2', y=1650)}[{nxt}]"
            )
            cur = nxt

        elif key == "street":
            if overlays.get("assessed_value"):
                assessed_text = f"Assessed ${overlays['assessed_value']:,.0f}"
                nxt = f"p{i}a"
                filter_parts.append(
                    f"[{cur}]{_dt(font, assessed_text, fontcolor='white', fontsize=64, box=1, boxcolor=f'{BRAND_NAVY}@0.75', boxborderw=20, x='(w-text_w)/2', y=1550)}[{nxt}]"
                )
                cur = nxt

        elif key == "condition":
            tier = (overlays.get("condition_tier") or "unknown").title()
            nxt = f"p{i}a"
            filter_parts.append(
                f"[{cur}]{_dt(font, tier + ' condition', fontcolor='#020617', fontsize=54, box=1, boxcolor=BRAND_AMBER, boxborderw=20, x='(w-text_w)/2', y=180)}[{nxt}]"
            )
            cur = nxt
            for bi, bullet in enumerate((overlays.get("condition_bullets") or [])[:2]):
                nxt2 = f"p{i}b{bi}"
                y = 1480 + bi * 100
                filter_parts.append(
                    f"[{cur}]{_dt(font, '- ' + bullet, fontcolor='white', fontsize=38, box=1, boxcolor=f'{BRAND_NAVY}@0.65', boxborderw=14, x='(w-text_w)/2', y=y)}[{nxt2}]"
                )
                cur = nxt2

        elif key == "payoff":
            nxt = f"p{i}a"
            filter_parts.append(
                f"[{cur}]{_dt(font, 'Bid with data, not guesses.', fontcolor='white', fontsize=58, box=1, boxcolor=f'{BRAND_NAVY}@0.6', boxborderw=20, x='(w-text_w)/2', y='(h-text_h)/2')}[{nxt}]"
            )
            cur = nxt

        filter_parts.append(f"[{cur}]copy[pb{i}]")
        labels.append(f"pb{i}")

    # -- CTA end card: navy background + QR + short URL + biddeed.ai wordmark
    # + a countdown chip (the presale-only addition vs v2's card) --
    card_idx = len(V2_ORDER)
    qr_idx = len(V2_ORDER) + 1
    filter_parts.append(
        f"color=c={BRAND_NAVY}:s=1080x1920:d={V2_END_CARD_SECONDS}:r={fps}[pcardbg]"
    )
    filter_parts.append(f"[{qr_idx}:v]scale=440:440[pqrscaled]")
    filter_parts.append("[pcardbg][pqrscaled]overlay=(W-w)/2:360[pcardqr]")
    days = overlays.get("days_to_auction")
    countdown_text = f"{days} day{'s' if days != 1 else ''} to auction" if days is not None else "Auction coming up"
    filter_parts.append(
        f"[pcardqr]{_dt(font, countdown_text, fontcolor='#020617', fontsize=44, box=1, boxcolor=BRAND_AMBER, boxborderw=16, x='(w-text_w)/2', y=850)}[pcardcd]"
    )
    filter_parts.append(
        f"[pcardcd]{_dt(font, short_url, fontcolor=BRAND_AMBER.replace('0x', '#'), fontsize=52, x='(w-text_w)/2', y=980)}[pcardurl]"
    )
    filter_parts.append(
        f"[pcardurl]{_dt(font, 'biddeed.ai', fontcolor='white', fontsize=66, x='(w-text_w)/2', y=1090)}[pcardbrand]"
    )
    filter_parts.append(
        f"[pcardbrand]{_dt(font, 'Link in bio', fontcolor='#94A3B8', fontsize=34, x='(w-text_w)/2', y=1190)}[pcard]"
    )
    labels.append("pcard")

    concat_inputs = "".join(f"[{l}]" for l in labels)
    filter_parts.append(f"{concat_inputs}concat=n={len(labels)}:v=1:a=0[pvconcat]")

    main_duration = sum(V2_SEGMENT_SECONDS.values())
    total_duration = main_duration + V2_END_CARD_SECONDS
    audio_idx = len(V2_ORDER)
    filter_parts.append(
        f"[{audio_idx}:a]atrim=0:{main_duration},apad=pad_dur={V2_END_CARD_SECONDS}[paout]"
    )

    filter_complex = ";".join(filter_parts)

    cmd = ["ffmpeg", "-y"]
    for key in V2_ORDER:
        cmd += ["-loop", "1", "-i", images[key]]
    cmd += ["-i", audio_path]
    cmd += ["-loop", "1", "-t", str(V2_END_CARD_SECONDS), "-i", qr_path]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[pvconcat]",
        "-map", "[paout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-t", str(total_duration),
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg presale assembly failed: {result.stderr[-3000:]}")
    return _ffprobe_duration(out_path)
