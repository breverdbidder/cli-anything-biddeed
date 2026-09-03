#!/usr/bin/env python3
"""HOOK WRITER -- agents/reel_studio/hook_writer.py (issue #19782).

Copywriter agent. Input: one winnerdata.biddeed_reels row + its SIGNAL$ data
(sold_amount/assessed_value/delta_pct/condition_json -- the same controlled,
non-free-text fields build_script_and_caption() already uses; no person/
bidder name is ever read into a prompt). Output: K=4 variant packages, each
{title, script, caption_groups, voice_tags (eleven_v3 tag plan), hashtags,
variant_dna}, diverse on >=3 of 6 dna axes (Jaccard >= 0.5 pairwise, no two
variants sharing archetype -- also enforced at the DB level, see the CP3c
migration).

LLM calls go through agents/reel_studio/router_client.py (claude-router T1
Gemini / T1.5 DeepSeek only -- issue #19782 forbids Anthropic in this agent
family; router_client enforces that post-hoc since the router's own
force_tier param can't guarantee it, see that module's docstring).

CLI:
  python3 hook_writer.py generate --county Escambia --auction-date 2026-09-01 [--dry-run]
  python3 hook_writer.py eval
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import router_client  # noqa: E402
import analyst  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "factory", "gtm"))
import gate  # noqa: E402 -- reuse the CP0 compliance checks, don't reinvent

K_VARIANTS = 4

ARCHETYPES = [
    "shock_number", "underdog_bidder", "bank_vs_house", "mystery_nobody_bid",
    "red_flag_warning", "hidden_value_reveal", "countdown_presale",
    "remote_bidder",
]
VOICE_REGISTERS = ["calm_narrator", "hype", "whisper_reveal", "documentary"]
CAPTION_STYLES = ["karaoke_bold", "minimal_lower_third", "kinetic_type"]
MUSIC_MOODS = ["tension_build", "uplifting", "dark_drone", "none"]
EDIT_STYLES = ["static_bolt32", "kinetic_bolt32", "animated_bolt32"]
EMOTION_PAIRS = [
    ["\U0001F440", "\U0001F6A8"],  # eyes, siren
    ["\U0001F4B0", "\U0001F4C9"],  # money bag, chart down
    ["\U0001F3DA", "\U0001F511"],  # house, key
    ["\U0001F914", "\U00002753"],  # thinking, question mark
    ["\U000023F3", "\U0001F525"],  # hourglass, fire
    ["\U0001F440", "\U0001F4B0"],  # eyes, money bag
]

DNA_AXES = ["archetype", "emotion_pair", "voice_register", "caption_style", "music_mood", "edit_style"]

_FIRST_SECOND_PERSON = re.compile(r"\b(i|me|my|we|our|us|you|your|you're|youre)\b", re.IGNORECASE)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "]",
    flags=re.UNICODE,
)

BANNED_PERSON_NAMES = ["Mariam", "Adina", "Colleen", "Ariel Shapira", "Ariel"]
BANNED_TOOL_TERMS = gate.VENDOR_NAMES + [
    "issue #", "GitHub", "SUMMIT", "summitleads", "S5", "biddeed_reels",
    "Supabase", "OpenRouter", "DeepSeek", "Gemini", "claude-router",
]


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

def fetch_shortlisted_reel(county: str, auction_date: str | None = None) -> dict | None:
    where_date = f"and auction_date = {lib.sql_str(auction_date)}" if auction_date else ""
    rows = lib.run_sql(f"""
        select id, case_number, county, sale_type, auction_date, property_address,
               sold_amount, assessed_value, delta_pct, condition_json, condition_score,
               landing_url, short_code, short_url
        from winnerdata.biddeed_reels
        where lower(county) = lower({lib.sql_str(county)})
          {where_date}
        order by shortlisted desc, rank_score desc nulls last, auction_date desc
        limit 1;
    """)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def count_emoji(text: str) -> int:
    return len(_EMOJI_RE.findall(text))


ELLIPSIS = "…"

# issue #19792 PART 1 -- title-case check exempts short connective words
# (matches the style Bolt's own titles use: "The Bank Let It Go For Less
# Than Half...", where "for"/"a"/"the" stay lowercase but every content
# word is capitalized) -- but the FIRST word is always required capitalized
# regardless of this list.
_TITLE_CASE_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "to", "is", "at", "by",
    "and", "or", "its", "it's", "this", "that", "than", "off",
}


def check_ellipsis_form(title: str) -> tuple[bool, list[str]]:
    """Named check (issue #19792 PART 1): the T1 spec requires the single
    ellipsis CHARACTER '…', not the three-period '...' sequence several
    shipped titles used ('Tax deed stuns Lee County... 💰🔑')."""
    reasons = []
    title = title or ""
    if ELLIPSIS not in title:
        reasons.append("missing the single-character ellipsis '…' (literal three dots '...' does not count)")
    elif "..." in title:
        reasons.append("contains a literal '...' in addition to/instead of the single '…' character")
    return (len(reasons) == 0, reasons)


def check_emoji_placement(title: str) -> tuple[bool, list[str]]:
    """Named check (issue #19792 PART 1): zero emoji before the ellipsis,
    exactly two immediately after it, nothing following them. Catches both
    observed violations: a leading emoji ('⚠️ Foreclosure Red Flag...') and
    a title that merely CONTAINS two emoji somewhere rather than having them
    positioned as the terminal marker."""
    reasons = []
    title = title or ""
    if ELLIPSIS not in title:
        return (False, ["no ellipsis present to anchor emoji placement"])
    idx = title.index(ELLIPSIS)
    before, after = title[:idx], title[idx + 1:]
    n_before = count_emoji(before)
    if n_before > 0:
        reasons.append(f"{n_before} emoji found before the ellipsis (must be zero)")
    n_after = count_emoji(after)
    trailing_non_emoji = _EMOJI_RE.sub("", after).strip()
    if trailing_non_emoji:
        reasons.append(f"non-emoji text follows the emoji at the end of the title: {trailing_non_emoji!r}")
    if n_after != 2:
        reasons.append(f"{n_after} emoji found after the ellipsis (must be exactly 2)")
    return (len(reasons) == 0, reasons)


def check_title_case(title: str) -> tuple[bool, list[str]]:
    """Named check (issue #19792 PART 1): catches sentence-case drift
    ('Tax deed stuns Lee County...', 'The bank lost this bet...') against
    Bolt's consistently Title Case titles."""
    reasons = []
    title = title or ""
    stem = title.split(ELLIPSIS)[0] if ELLIPSIS in title else title
    words = [w for w in re.split(r"\s+", stem.strip()) if w]
    bad = []
    for i, w in enumerate(words):
        core = re.sub(r"^[^A-Za-z0-9]+", "", w)
        if not core or not core[0].isalpha():
            continue
        is_stopword = re.sub(r"[^a-z']", "", w.lower()) in _TITLE_CASE_STOPWORDS
        if core[0].isupper():
            continue
        if i == 0 or not is_stopword:
            bad.append(w)
    if bad:
        reasons.append(f"not Title Case -- lowercase word(s) that should be capitalized: {bad}")
    return (len(reasons) == 0, reasons)


def check_payoff_leak(title: str, reel: dict) -> tuple[bool, list[str]]:
    """Named check (issue #19792 PART 1) -- the anti-hook, flagged as the
    single biggest miss: a title that hands the viewer the exact number the
    20-28s Payoff beat delivers (sold price / discount pct / opening bid)
    leaves nothing to watch for. A title MAY still cite the assessed value
    (a Setup-beat fact, disclosed 2-8s) or a vague/rounded stakes phrase
    ('less than half') -- only the specific payoff-beat figures fail this
    check. `reel` = {phase, sold_amount, delta_pct, assessed_value,
    opening_bid, judgment_amount}."""
    reasons = []
    reel = reel or {}
    title = title or ""
    digits_found = {d.replace(",", "") for d in re.findall(r"[\d,]+(?:\.\d+)?", title)}

    def _leaks(value, label):
        if value is None:
            return
        for fmt in (f"{value:,.0f}", f"{value:.0f}", f"{abs(value):,.0f}", f"{abs(value):.0f}"):
            if fmt.replace(",", "") in digits_found:
                reasons.append(f"title leaks the {label} figure ({fmt}) that the 20-28s payoff beat delivers")
                return

    if reel.get("phase") == "presale":
        _leaks(reel.get("opening_bid"), "opening bid")
        _leaks(reel.get("judgment_amount"), "judgment amount")
    else:
        _leaks(reel.get("sold_amount"), "sold price")
        _leaks(reel.get("delta_pct"), "discount percentage")
    return (len(reasons) == 0, reasons)


# issue #19792 PART 1 -- archetype validity rules, checked against the
# row's ACTUAL facts (never asserted from the archetype's own story).
# Every archetype not named here has no data-dependent precondition today.
_PHASE_ONLY_ARCHETYPES = {"countdown_presale": "presale"}


def check_archetype_data_match(archetype: str, reel: dict, third_party_bidder: bool | None,
                                plaintiff_confirmed_bank: bool | None,
                                auction_venue_online: bool | None = None) -> tuple[bool, list[str]]:
    """Named check (issue #19792 PART 1, extended issue #19793 PART 2) -- a
    semantic bug, not cosmetic. countdown_presale requires phase='presale'
    (a property that already sold cannot have a countdown); mystery_nobody_bid
    requires the sale record show NO confirmed third-party bidder;
    bank_vs_house requires a confirmed bank/lender plaintiff in the case
    record; remote_bidder requires the sale's own auction-platform record
    show venue='online' (public.multi_county_auctions.auction_venue).
    `third_party_bidder` / `plaintiff_confirmed_bank` / `auction_venue_online`
    are True/False/None (None = data absent, treated as "not confirmed" --
    diversity must be achieved within the archetypes the data supports,
    never by asserting an unverified story).

    remote_bidder is the same defect class as countdown_presale on a sold
    property (issue #19793 PART 2): asserting "you didn't have to be in
    Florida" about a sale whose venue is unknown or in-person is not a minor
    embellishment, it is a false claim about how the sale actually happened.
    `source_platform` values like 'realforeclose'/'realtaxdeed' are NOT used
    to infer venue here even though those are commonly online platforms --
    the issue's own rule is "derive from the auction-platform field... where
    the venue is unknown, do not guess, do not default to online", and
    auction_venue is that field, not source_platform."""
    reasons = []
    reel = reel or {}
    phase = reel.get("phase")

    required_phase = _PHASE_ONLY_ARCHETYPES.get(archetype)
    if required_phase and phase != required_phase:
        reasons.append(f"archetype {archetype!r} requires phase={required_phase!r}, row has phase={phase!r}")

    if archetype == "mystery_nobody_bid" and third_party_bidder:
        reasons.append("archetype 'mystery_nobody_bid' requires no confirmed third-party bidder, "
                        "but the sale record shows one (sale_result=SOLD_THIRD_PARTY / winning_bidder present)")

    if archetype == "bank_vs_house" and not plaintiff_confirmed_bank:
        reasons.append("archetype 'bank_vs_house' requires a confirmed bank/lender plaintiff in the case "
                        "record; plaintiff is absent/unconfirmed for this row")

    if archetype == "remote_bidder" and auction_venue_online is not True:
        reasons.append("archetype 'remote_bidder' requires the sale record's auction_venue='online' "
                        "(multi_county_auctions.auction_venue); got "
                        f"{auction_venue_online!r} (None = unknown -- never defaulted to online)")

    return (len(reasons) == 0, reasons)


# issue #19793 PART 2 -- remote_bidder's own honesty guardrail. Approved
# phrasing pattern: "bid online from anywhere - deposit rules still apply".
# The archetype must not imply frictionlessness, must never state or imply
# BidDeed bids on anyone's behalf, and must never give investment advice.
_REMOTE_BIDDER_BANNED_PHRASES = [
    "no paperwork", "no deposit", "skip the deposit", "we bid for you",
    "we'll bid for you", "we bid on your behalf", "bid on your behalf",
    "let us bid", "guaranteed", "risk free", "risk-free", "sure thing",
    "you should buy", "you should invest", "great investment",
    "no registration", "instantly own", "own it instantly",
]


def check_remote_bidder_honesty_guardrail(archetype: str, title: str, script_text: str) -> tuple[bool, list[str]]:
    """Named check (issue #19793 PART 2) -- only applies to remote_bidder.
    Scans the title + full spoken script for language implying frictionless
    remote bidding, BidDeed bidding on the viewer's behalf, or investment
    advice. Non-blocking (pass=True) for every other archetype -- this is
    remote_bidder's own compliance rule, not a general profanity filter."""
    if archetype != "remote_bidder":
        return (True, [])
    reasons = []
    blob = f"{title or ''} {script_text or ''}".lower()
    for phrase in _REMOTE_BIDDER_BANNED_PHRASES:
        if phrase in blob:
            reasons.append(f"remote_bidder honesty guardrail: banned phrase {phrase!r} found "
                            f"(implies frictionlessness, BidDeed bidding on the viewer's behalf, "
                            f"or investment advice)")
    return (len(reasons) == 0, reasons)


def validate_title(title: str) -> tuple[bool, list[str]]:
    reasons = []
    words = [w for w in re.split(r"\s+", title.strip()) if w]
    word_count = len([w for w in words if not _EMOJI_RE.fullmatch(w)])
    if not (5 <= word_count <= 9):
        reasons.append(f"word_count={word_count} not in [5,9]")
    ok, why = check_ellipsis_form(title)
    if not ok:
        reasons.extend(why)
    ok, why = check_emoji_placement(title)
    if not ok:
        reasons.extend(why)
    ok, why = check_title_case(title)
    if not ok:
        reasons.extend(why)
    if _FIRST_SECOND_PERSON.search(title):
        reasons.append("first/second-person pronoun present (must be third person)")
    return (len(reasons) == 0, reasons)


def scan_banned_terms(text: str) -> list[str]:
    hits = []
    low = text.lower()
    for name in BANNED_PERSON_NAMES + BANNED_TOOL_TERMS:
        if name.lower() in low:
            hits.append(name)
    ok, detail = gate.check_person_name_detector(text)
    if not ok:
        hits.extend(detail.get("prose_hits", []))
    return hits


def jaccard_distance(dna_a: dict, dna_b: dict) -> float:
    set_a = {f"{k}={dna_a.get(k)}" for k in DNA_AXES}
    set_b = {f"{k}={dna_b.get(k)}" for k in DNA_AXES}
    union = set_a | set_b
    if not union:
        return 0.0
    inter = set_a & set_b
    return 1 - (len(inter) / len(union))


def assert_diversity(dna_list: list[dict]) -> tuple[bool, list[str]]:
    reasons = []
    archetypes = [d.get("archetype") for d in dna_list]
    if len(set(archetypes)) != len(archetypes):
        reasons.append(f"duplicate archetype in set: {archetypes}")
    for i in range(len(dna_list)):
        for j in range(i + 1, len(dna_list)):
            dist = jaccard_distance(dna_list[i], dna_list[j])
            if dist < 0.5:
                reasons.append(f"variant {i} vs {j} Jaccard distance {dist:.2f} < 0.5")
    return (len(reasons) == 0, reasons)


# ---------------------------------------------------------------------------
# Prompt + LLM call
# ---------------------------------------------------------------------------

def _condition_summary(condition_json) -> str:
    if not condition_json:
        return "condition unknown"
    if isinstance(condition_json, str):
        try:
            condition_json = json.loads(condition_json)
        except Exception:
            return "condition unknown"
    tier = condition_json.get("general_condition_tier", "unknown")
    return f"condition tier: {tier}"


def build_prompt(reel: dict, k: int = K_VARIANTS, avoid_archetypes: list[str] | None = None, forced_archetype: str | None = None) -> tuple[str, str]:
    """Builds a prompt for ONE variant package (not the full K-set in one
    call) -- live-observed this session: a single call asking GLM for all 4
    full packages at once (32s script + captions + voice tags x4) reliably
    returned finish_reason=error after ~100s, while a single-variant request
    completes in a few seconds. K separate smaller calls are slower in call
    count but far more reliable in practice than one large one; see
    docs/spec/19782.md for the timing evidence.

    forced_archetype pins the archetype instead of offering the model a
    choice -- also live-observed this session: given a free choice, this
    model picked "shock_number" for the large majority of calls, which
    meant most of a property's 4 concurrent variants needed an expensive
    sequential regeneration pass to satisfy the no-duplicate-archetype rule.
    Pre-assigning 4 distinct archetypes up front (one per call) avoids that
    entirely -- diversity by construction, not by retry."""
    county = reel["county"]
    sold = reel.get("sold_amount")
    assessed = reel.get("assessed_value")
    delta = reel.get("delta_pct")
    sale_type = reel.get("sale_type") or "auction sale"
    condition = _condition_summary(reel.get("condition_json"))
    avoid_archetypes = avoid_archetypes or []
    allowed_archetypes = [a for a in ARCHETYPES if a not in avoid_archetypes] or ARCHETYPES
    archetype_instruction = f'"{forced_archetype}" (use exactly this value)' if forced_archetype else f"one of {allowed_archetypes}"

    system = (
        "You write short-form (32s) real-estate auction reel scripts for BidDeed.AI. "
        "Output ONLY controlled facts (dollar amounts, county, sale type, condition tier) -- "
        "NEVER a person's name, NEVER a company/vendor name, NEVER an internal tool/issue "
        "reference. Every title: 5-9 words, third person (no I/you/we), must contain an "
        "ellipsis (...), and exactly two emoji. Return strict JSON only, no prose, no markdown fences."
    )
    if (forced_archetype or "") == "remote_bidder":
        system += (
            " This variant's archetype is remote_bidder: the hook states the stakes without "
            "the payoff, the tension beat carries one line on the online bidding mechanism, "
            "and the loop line closes on place-independence (the buyer never had to set foot "
            "in Florida). HONESTY GUARDRAIL: never imply frictionlessness -- use the approved "
            "phrasing pattern 'bid online from anywhere - deposit rules still apply', and never "
            "state or imply BidDeed bids on anyone's behalf, and never give investment advice."
        )
    user = f"""Property facts (do not invent any number not given here):
- county: {county}
- sale type: {sale_type}
- sold amount: {sold}
- assessed value: {assessed}
- delta pct (sold vs assessed): {delta}
- {condition}

Generate exactly ONE variant package as a single JSON object (not an array):
{{
  "variant_dna": {{
    "archetype": {archetype_instruction},
    "voice_register": one of {VOICE_REGISTERS},
    "caption_style": one of {CAPTION_STYLES},
    "music_mood": one of {MUSIC_MOODS},
    "edit_style": one of {EDIT_STYLES}
  }},
  "title": "5-9 words, third person, contains '...', exactly two emoji",
  "script": {{"beats": [{{"start_s": 0, "end_s": 2, "line": "..."}}, ...]}} covering 0-32s in 4-6 beats,
  "caption_groups": [{{"start_s": 0, "end_s": 2, "words": "<=5 words"}}, ...],
  "voice_tags": {{"eleven_v3_tags": ["...", "..."], "pace": "normal|fast|slow"}},
  "hashtags": ["#...", ...]
}}
The first beat (start_s=0) MUST end at or before 2.0s and its line must clearly
deliver the title's hook (hook clarity: title spoken by 2.0s).
Single JSON object only, no array, no prose."""
    return system, user


def _extract_json_array(text: str):
    """Tolerant of a truncated response (hit max_tokens mid-array): tries
    the full slice first, then falls back to decoding as many complete
    top-level array elements as are present, discarding a trailing partial
    one, so a truncated LLM response fails the '4 variants expected'
    validation cleanly instead of crashing on a JSONDecodeError."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text).rstrip("`").strip()
    start = text.find("[")
    if start == -1:
        raise ValueError(f"no JSON array found in LLM output: {text[:200]}")

    end = text.rfind("]")
    if end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    pos = start + 1
    items = []
    n = len(text)
    while pos < n:
        while pos < n and text[pos] in " \t\r\n,":
            pos += 1
        if pos >= n or text[pos] == "]":
            break
        try:
            obj, end_pos = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            break
        items.append(obj)
        pos = end_pos
    if not items:
        raise ValueError(f"could not parse any JSON objects from LLM output: {text[:200]}")
    return items


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text).rstrip("`").strip()
    start = text.find("{")
    if start == -1:
        raise ValueError(f"no JSON object found in LLM output: {text[:200]}")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text, start)
    return obj


def call_llm_for_one_variant(reel: dict, avoid_archetypes: list[str], attempt: int = 0, forced_archetype: str | None = None) -> tuple[dict, dict]:
    """Returns (variant_package, router_meta) for ONE variant. Raises on
    failure -- caller must not fabricate a variant when this fails (Honesty
    Protocol). attempt is embedded in the prompt to bust the router's
    response cache on retry (cache key is messages+system only, not
    max_tokens -- live-observed this session: an identical retry replayed a
    stale/truncated cached completion until the prompt text varied)."""
    system, user = build_prompt(reel, avoid_archetypes=avoid_archetypes, forced_archetype=forced_archetype)
    if attempt:
        user += f"\n\n(regeneration attempt {attempt} -- previous attempt was invalid, produce a fresh, complete response)"
    # Live-verified this session (docs/spec/19782.md): claude-router's T1
    # Gemini tier is failing/slow and T1.5 DeepSeek has no vault key, so
    # every claude-router attempt eventually cascades to its T2 Claude tier
    # (which router_client correctly refuses) after a long timeout. Direct
    # OpenRouter GLM (also explicitly allowed: "OpenRouter GLM/DeepSeek") is
    # used here for that reason -- router_client.call_router is still
    # exercised directly by the eval harness so that path stays covered.
    result = router_client.call_openrouter_text(
        [{"role": "user", "content": user}],
        system=system,
        max_tokens=3500,  # live-observed this session: this model burns ~800-1000
        # tokens on hidden reasoning even with reasoning.exclude=true (that budget
        # is NOT reflected in visible output) before the actual JSON content --
        # 1200 truncated (finish_reason=length); 3000 completed a full package
    )
    variant = _extract_json_object(result["text"])
    variant.setdefault("variant_dna", {})
    return variant, {"tier": result["tier"], "provider": result["provider"], "model": result["model"]}


def _fill_emotion_pair(dna: dict, used_pairs: list) -> dict:
    for pair in EMOTION_PAIRS:
        if pair not in used_pairs:
            dna["emotion_pair"] = pair
            used_pairs.append(pair)
            return dna
    dna["emotion_pair"] = random.choice(EMOTION_PAIRS)
    return dna


def validate_variant_set(variants: list[dict]) -> tuple[bool, list[str]]:
    reasons = []
    if len(variants) != K_VARIANTS:
        reasons.append(f"expected {K_VARIANTS} variants, got {len(variants)}")
    for i, v in enumerate(variants):
        ok, why = validate_title(v.get("title", ""))
        if not ok:
            reasons.append(f"variant {i} title invalid: {why}")
        hits = scan_banned_terms(json.dumps(v))
        if hits:
            reasons.append(f"variant {i} banned terms found: {hits}")
        n_groups_bad = [g for g in v.get("caption_groups", []) if len(str(g.get("words", "")).split()) > 5]
        if n_groups_bad:
            reasons.append(f"variant {i} has {len(n_groups_bad)} caption group(s) over 5 words")
    dna_list = [v["variant_dna"] for v in variants]
    div_ok, div_reasons = assert_diversity(dna_list)
    if not div_ok:
        reasons.extend(div_reasons)
    return (len(reasons) == 0, reasons)


def generate_one_variant_with_retry(reel: dict, avoid_archetypes: list[str], used_pairs: list, max_retries: int = 2, forced_archetype: str | None = None) -> tuple[dict | None, dict | None, list[str]]:
    """Generates and validates ONE variant, retrying with a fresh prompt
    (cache-busted) on any failure. Returns (variant_or_None, meta_or_None,
    errors)."""
    last_reasons = []
    for attempt in range(1, max_retries + 2):
        try:
            v, meta = call_llm_for_one_variant(reel, avoid_archetypes, attempt=attempt - 1, forced_archetype=forced_archetype)
        except router_client.RouterBlockedAnthropicTier as e:
            return None, None, [f"BLOCKED_ANTHROPIC_TIER: {e}"]
        except Exception as e:
            last_reasons = [f"attempt {attempt}: LLM call failed: {e}"]
            continue

        if forced_archetype:
            v["variant_dna"]["archetype"] = forced_archetype  # pin -- don't trust the model to echo it back verbatim
        _fill_emotion_pair(v["variant_dna"], used_pairs)
        v["variant_dna"] = {axis: v["variant_dna"].get(axis) for axis in DNA_AXES}

        ok, reasons = validate_variant_set([v])  # per-variant structural checks only (diversity checked by caller across the set)
        reasons = [r for r in reasons if "expected 4 variants" not in r]
        if not forced_archetype and v["variant_dna"].get("archetype") in avoid_archetypes:
            reasons.append(f"archetype {v['variant_dna'].get('archetype')} already used in this set")
        if not reasons:
            return v, meta, []
        last_reasons = reasons
    return None, None, last_reasons


def generate_variants_for_reel(reel: dict, k: int = K_VARIANTS, max_retries: int = 2, log_prefix: str = "") -> dict:
    """Returns {"ok": bool, "variants": [...], "router_meta": {...}, "errors": [...]}.

    Pre-assigns each of the K slots a distinct, random archetype and fires
    all K calls CONCURRENTLY (each is an independent network round-trip to
    OpenRouter, ~30-60s). Archetype is pinned per call rather than offered
    as a free choice -- live-observed this session: given a free choice,
    the model picked "shock_number" for most calls, forcing an expensive
    sequential repair pass to satisfy no-duplicate-archetype. Pinning
    upfront makes diversity-by-construction the common case; any individual
    slot that still fails validation (e.g. a malformed title) is retried
    sequentially with the same pinned archetype."""
    used_pairs: list = []
    archetypes = random.sample(ARCHETYPES, k)

    def _gen(archetype):
        return generate_one_variant_with_retry(reel, [], used_pairs, max_retries, forced_archetype=archetype)

    variants: list[dict] = []
    metas: list[dict] = []
    errors: list[str] = []
    failed_archetypes: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=k) as pool:
        futures = {pool.submit(_gen, a): a for a in archetypes}
        for fut in concurrent.futures.as_completed(futures):
            a = futures[fut]
            v, meta, reasons = fut.result()
            if log_prefix:
                print(f"{log_prefix} [{a}]: {'ok' if v else 'FAILED: ' + str(reasons)}", flush=True)
            if v is None:
                errors.extend(reasons)
                failed_archetypes.append(a)
                continue
            variants.append(v)
            metas.append(meta)

    # Any slot whose pinned archetype failed outright (LLM error, bad title,
    # etc. across all retries) gets one more sequential attempt with a fresh
    # unused archetype, so a single bad call doesn't sink the whole property.
    used_archetypes = [v["variant_dna"]["archetype"] for v in variants]
    for _ in failed_archetypes:
        remaining = [a for a in ARCHETYPES if a not in used_archetypes]
        if not remaining:
            break
        a = random.choice(remaining)
        v, meta, reasons = generate_one_variant_with_retry(reel, [], used_pairs, max_retries, forced_archetype=a)
        if v is None:
            errors.extend(reasons)
            continue
        variants.append(v)
        metas.append(meta)
        used_archetypes.append(a)

    if len(variants) < k:
        return {"ok": False, "variants": [], "router_meta": None, "errors": errors or [f"only {len(variants)}/{k} variants generated"]}

    ok, reasons = validate_variant_set(variants[:k])
    if not ok:
        return {"ok": False, "variants": [], "router_meta": None, "errors": reasons}
    return {"ok": True, "variants": variants[:k], "router_meta": metas, "errors": []}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def insert_variant(reel_id: str, variant_key: str, package: dict, short_code: str, short_url: str, qr_url: str | None) -> str:
    rows = lib.run_sql(f"""
        insert into winnerdata.reel_variants
            (reel_id, variant_key, variant_dna, title, script, caption_groups,
             voice_tags, tts_model, hashtags, short_code, short_url, qr_url, status)
        values (
            {lib.sql_str(reel_id)}, {lib.sql_str(variant_key)},
            {lib.sql_jsonb(package["variant_dna"])}, {lib.sql_str(package["title"])},
            {lib.sql_jsonb(package["script"])}, {lib.sql_jsonb(package["caption_groups"])},
            {lib.sql_jsonb(package.get("voice_tags"))}, {lib.sql_str("eleven_v3")},
            {lib.sql_text_array(package.get("hashtags") or [])},
            {lib.sql_str(short_code)}, {lib.sql_str(short_url)}, {lib.sql_str(qr_url)},
            'pending_approval'
        )
        returning id;
    """)
    return rows[0]["id"]


def run_for_county(county: str, auction_date: str | None, dry_run: bool = False) -> dict:
    reel = fetch_shortlisted_reel(county, auction_date)
    if not reel:
        return {"county": county, "ok": False, "error": "no biddeed_reels row found"}

    result = generate_variants_for_reel(reel, log_prefix=f"[{county}]")
    if not result["ok"]:
        return {"county": county, "reel_id": reel["id"], "ok": False, "errors": result["errors"]}

    if dry_run:
        return {"county": county, "reel_id": reel["id"], "ok": True, "variants": result["variants"], "router_meta": result["router_meta"], "dry_run": True}

    inserted = []
    for i, v in enumerate(result["variants"]):
        variant_key = chr(ord("A") + i)
        short_code, short_url, qr_url = analyst.mint_variant_short_link(reel, variant_key)
        variant_id = insert_variant(reel["id"], variant_key, v, short_code, short_url, qr_url)
        inserted.append({"variant_id": variant_id, "variant_key": variant_key, "short_code": short_code, "archetype": v["variant_dna"]["archetype"]})

    return {"county": county, "reel_id": reel["id"], "ok": True, "inserted": inserted, "router_meta": result["router_meta"]}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--county", required=True)
    gen.add_argument("--auction-date", default=None)
    gen.add_argument("--dry-run", action="store_true")

    sub.add_parser("eval")

    args = ap.parse_args()
    if args.cmd == "generate":
        out = run_for_county(args.county, args.auction_date, dry_run=args.dry_run)
        print(json.dumps(out, indent=2, default=str))
    elif args.cmd == "eval":
        from eval_hook_writer import run_eval  # noqa
        run_eval()


if __name__ == "__main__":
    main()
