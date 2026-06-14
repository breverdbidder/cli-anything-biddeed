"""
Configuration for the zoning ordinance extractor.
All secrets come from environment (GitHub Actions secrets in production).
"""
import os
import re

# ---- Secrets / env -------------------------------------------------------
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
# Route through the Smart Router / cliproxy (OAuth) per cost canon — never a raw sk-ant key.
# When set, the Anthropic SDK points at this base_url instead of the public API.
ANTHROPIC_BASE_URL  = os.environ.get("ANTHROPIC_BASE_URL", "")
SUPABASE_URL        = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

# Extraction model. Sonnet is the right cost/quality point for structured table extraction.
MODEL = os.environ.get("ZONING_EXTRACT_MODEL", "claude-sonnet-4-6")

# ---- Behavior knobs ------------------------------------------------------
NAV_TIMEOUT_MS   = int(os.environ.get("NAV_TIMEOUT_MS", "45000"))
RENDER_SETTLE_MS = int(os.environ.get("RENDER_SETTLE_MS", "2500"))  # extra wait after networkidle
SELECTOR_WAIT_MS = int(os.environ.get("SELECTOR_WAIT_MS", "15000")) # wait for content selector to populate
POLITE_DELAY_S   = float(os.environ.get("POLITE_DELAY_S", "2.0"))   # between page loads
MAX_RETRIES      = int(os.environ.get("MAX_RETRIES", "4"))

# Realistic UA helps clear the bot walls that blocked plain HTTP fetches.
USER_AGENT = os.environ.get(
    "ZONING_UA",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)

# Content containers to pull rendered text from, by platform, with a body fallback.
# These are the ONLY selector assumptions; everything downstream is LLM-driven.
# If a platform changes its DOM, only this list needs tuning.
CONTENT_SELECTORS = {
    "municode":       ["#docContent", ".chunks", "[id^='genericChunkContainer']", "main", "body"],
    "american_legal": [".codenav__content", "#codeContent", "main", "article", "body"],
}

# ---- BLANK > WRONG guards ------------------------------------------------
# Codes that are NOT real zoning districts (unresolved assignments / land-use placeholders).
# These are never extraction targets — they go to an assignment-fix queue instead.
PLACEHOLDER_CODE_RE = re.compile(r"^(VAC[-_ ]?(RES|COM|INST)?|UNKNOWN|NONE|N/?A)$", re.I)

# Planned/site-specific districts: no fixed district-table density exists.
SITE_SPECIFIC_RE = re.compile(r"(^|[-_/ ])P(U|R)?D($|[-_/ 0-9])|PLANNED", re.I)

# Plausibility ranges. Out-of-range values are NOT dropped — they are flagged
# confidence='low' so the human gate sees them. Garbage-in stays visible, never silent.
RANGES = {
    "max_density_num":  (0.0, 200.0),   # dwelling units / acre
    "far":              (0.0, 30.0),
    "parking_per_1000": (0.0, 25.0),
    "max_height_ft":    (0, 2000),
}
