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

# issue #19794 step 6 -- discount-pct vs dollar-delta archetype framing.
# Thresholds are the p75 (top-quartile) pct_below_assessed / dollar_delta
# across all genuinely-sold multi_county_auctions rows (sale_result=
# 'SOLD_THIRD_PARTY' or tier1_sale_status='SOLD', assessed_value>$500),
# both sale types combined, re-derived live 2026-09-03 (n=2303):
# p75 pct_below_assessed=65.6%, p75 dollar_delta=$115,460 (rounded below).
# NOTE contradicts this issue's own stated calibration ("tax deed usually
# wins on discount pct"): live per-sale-type numbers are foreclosure
# p75 pct_below=79.6%/dollar_delta=$149,900 vs tax_deed p75 pct_below=
# 46.8%/dollar_delta=$5,500 -- foreclosure leads on BOTH axes at this
# percentile. Thresholds are applied per-property against the property's
# own sold_amount/assessed_value, never asserted from sale_type, so a
# tax-deed row that genuinely clears a bar still gets that framing and a
# foreclosure row that doesn't still falls through to unbiased selection.
HIGH_DOLLAR_DELTA_THRESHOLD = 115_000
HIGH_DISCOUNT_PCT_THRESHOLD = 65.0


def recommend_framing_archetype(sold_amount: float | None, assessed_value: float | None) -> str | None:
    """Returns the archetype this property's OWN numbers support -- 'shock_number'
    for a top-quartile dollar delta, 'hidden_value_reveal' for a top-quartile
    discount pct, or None if neither bar clears (weak data: fall through to
    unbiased random selection rather than forcing a framing). Checked before
    dollar_delta so a property that clears both bars gets the bigger-number
    story, matching the issue's own priority ("shock_number for high dollar
    deltas, hidden_value_reveal for high discount pct"). bank_vs_house is
    deliberately not forced here even though the issue names it as a
    discount-pct option -- it has its own hard precondition (confirmed
    bank/lender plaintiff, see check_archetype_data_match) that this
    function has no visibility into, so forcing it here risks producing an
    archetype the row's own facts don't support."""
    if not sold_amount or not assessed_value or assessed_value <= 0:
        return None
    dollar_delta = assessed_value - sold_amount
    pct_below = dollar_delta / assessed_value * 100
    if dollar_delta >= HIGH_DOLLAR_DELTA_THRESHOLD:
        return "shock_number"
    if pct_below >= HIGH_DISCOUNT_PCT_THRESHOLD:
        return "hidden_value_reveal"
    return None

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
    if not rows:
        return None
    reel = rows[0]
    # issue #20032 -- lib.run_sql() goes through the Supabase Management API,
    # which serializes Postgres `numeric` columns as JSON strings (same bug
    # class fixed at scripts/biddeed_reels_pipeline.py:494 for rank_score).
    # recommend_framing_archetype() does `assessed_value <= 0`, which raises
    # TypeError on a str -- this was a live, never-hit crash in this CLI's
    # own "path of record for NEW reels" (this file's own docstring), latent
    # until this session actually called it against a real numeric row.
    for k in ("sold_amount", "assessed_value", "delta_pct", "condition_score"):
        if reel.get(k) is not None:
            reel[k] = float(reel[k])
    return reel


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

    # issue #19814 defect 1 -- 'hidden_value_reveal' asserts a discount story
    # ("worth more than it sold" / "listing undersold its own value") in two
    # of its five title templates. That claim is FALSE for a property that
    # sold ABOVE assessed value (real, live-observed on the tax_deed backfill:
    # Pasco land parcels sold 400-1266% over assessed). Gate on the row's own
    # numbers, same pattern as recommend_framing_archetype's own direction
    # check -- only fires when both figures are present and unambiguous.
    sold_amount = reel.get("sold_amount")
    assessed_value = reel.get("assessed_value")
    if archetype == "hidden_value_reveal" and sold_amount is not None and assessed_value:
        if sold_amount > assessed_value:
            reasons.append("archetype 'hidden_value_reveal' asserts the property sold for less than its "
                            "real/assessed value, but this row sold ABOVE assessed_value "
                            f"(sold_amount={sold_amount}, assessed_value={assessed_value})")

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
# issue #19802 -- Bolt technique defects: payoff leaks in beat 2, hardcoded
# generic loop line, mad-lib titles. Deterministic (not live-LLM) generation
# is used here for the same reason issue #19792 PART 2's _cp3c_b_regen.py
# chose it (docs/spec/19792.md): free, reproducible, and directly testable
# against every check below before a single row is written -- the LLM path
# (call_llm_for_one_variant / router_client) is unchanged and stays the path
# of record for brand-new reels; this section only fixes what a REGENERATION
# pass produces so the 21/22 already-shipped variants can be repaired without
# an unattended live LLM call in a headless session.
# ---------------------------------------------------------------------------

# Title emoji pair per archetype -- unchanged from issue #19792 PART 2's
# _cp3c_b_regen.py (K3 surgical: these already validate, don't touch them).
# remote_bidder is new here (that archetype existed in ARCHETYPES but had no
# emoji pair assigned since it was never included in a #19792 regen batch).
ARCHETYPE_EMOJI = {
    "shock_number": "\U0001F633\U0001F92F",       # 😳🤯
    "underdog_bidder": "\U0001F3C6\U0001F440",     # 🏆👀
    "red_flag_warning": "\U0001F630\U0001F440",    # 😰👀
    "hidden_value_reveal": "\U0001F92F\U0001F440",  # 🤯👀
    "bank_vs_house": "\U0001F494\U0001F3C6",       # 💔🏆
    "mystery_nobody_bid": "\U0001F631\U0001F440",  # 😱👀
    "countdown_presale": "\U0001F630\U0001F976",   # 😰🥶
    "remote_bidder": "\U0001F979\U0001F440",       # 🥹👀
}


def _condition_tier(reel_facts: dict) -> str:
    cj = reel_facts.get("condition_json")
    if isinstance(cj, str):
        try:
            cj = json.loads(cj) if cj else {}
        except Exception:
            cj = {}
    return (cj or {}).get("general_condition_tier") or "unknown"


# issue #19803 -- "unknown" is an internal sentinel _condition_tier() returns
# when the row's own condition_json has no general_condition_tier. It must
# never be spoken as an adjective ("unknown-condition property"): that
# literal string is exactly what leaked into 20/21 shipped scripts. Callers
# building spoken text check this first and drop the condition clause
# entirely when it's False, instead of substituting a placeholder token.
_CONDITION_TIERS_WITH_DATA = ("excellent", "good", "fair", "poor")


def _has_condition_data(reel_facts: dict) -> bool:
    return _condition_tier(reel_facts) in _CONDITION_TIERS_WITH_DATA


def _red_flag_signals(reel_facts: dict) -> str | None:
    """Pulls a real, VERIFIED/LIKELY-confidence red flag out of the row's own
    vision-scored condition_json -- never invents one. None means the row's
    own record has nothing to point at (a valid outcome, not skipped)."""
    cj = reel_facts.get("condition_json")
    if isinstance(cj, str):
        try:
            cj = json.loads(cj) if cj else {}
        except Exception:
            cj = {}
    cj = cj or {}
    flags = []
    veg = cj.get("vegetation_overgrowth") or {}
    if veg.get("confidence") in ("VERIFIED", "LIKELY") and veg.get("observation"):
        flags.append("overgrown vegetation")
    vac = cj.get("vacancy_signals") or {}
    if vac.get("confidence") in ("VERIFIED", "LIKELY") and vac.get("observation"):
        flags.append("possible vacancy signs")
    return " and ".join(flags) if flags else None


def _sale_mechanism_phrase(reel_facts: dict, lang: str = "en") -> str:
    st = (reel_facts.get("sale_type") or "").lower()
    if lang == "es":
        if "tax deed" in st:
            return "en una venta de escritura fiscal"
        if "foreclosure" in st:
            return "en una subasta de ejecución hipotecaria"
        return "en subasta"
    if "tax deed" in st:
        return "at a tax deed sale"
    if "foreclosure" in st:
        return "at a foreclosure auction"
    return "at auction"


# ---------------------------------------------------------------------------
# DEFECT 3 -- bespoke, facts-driven titles. Each archetype gets a POOL of
# structurally distinct templates (not one fixed sentence with only the
# county swapped) so same-archetype titles differ in sentence structure,
# not just the proper noun (checked by check_title_structural_similarity
# below). template_index picks the pool slot; callers round-robin it across
# a batch so siblings of one archetype don't collide on the same structure.
# ---------------------------------------------------------------------------

def _title_stem(archetype: str, county: str, reel_facts: dict, template_index: int, lang: str = "en") -> str:
    assessed = reel_facts.get("assessed_value")
    days = reel_facts.get("days_to_auction")

    if lang == "es":
        pools = {
            "shock_number": [
                (lambda: f"El Condado Tasó Esta Casa De {county} En ${assessed:,.0f}") if assessed is not None
                else (lambda: f"Esta Casa De {county} Sorprendió A Toda La Subasta"),
                (lambda: f"Los Tasadores De {county} La Valoraron En ${assessed:,.0f}") if assessed is not None
                else (lambda: f"Nadie Esperaba Este Número En {county}"),
                (lambda: f"El Número Real De Esta Casa En {county} Fue ${assessed:,.0f}") if assessed is not None
                else (lambda: f"Esta Casa De {county} Guardaba Un Número Sorpresa"),
            ],
            "underdog_bidder": [
                lambda: f"Un Postor Sorpresa Le Ganó A Todos En {county}",
                lambda: f"Un Postor Inesperado Ganó La Subasta En {county}",
                lambda: f"En {county} Ganó El Postor Menos Esperado",
                lambda: f"El Favorito Perdió Esta Subasta En {county}",
                lambda: f"Un Desconocido Se Llevó Esta Propiedad En {county}",
            ],
            "hidden_value_reveal": [
                lambda: f"Esta Casa De {county} Escondió Su Valor Real",
                lambda: f"Nadie En {county} Vio Venir Este Valor",
                lambda: f"El Verdadero Valor Se Escondió En {county}",
                lambda: f"Esta Propiedad En {county} Valía Más De Lo Que Se Vendió",
                lambda: f"El Anuncio De {county} No Mostró Su Verdadero Valor",
            ],
            "red_flag_warning": [
                lambda: f"Esta Casa De {county} Levantó Toda Señal De Alerta",
                lambda: f"Los Registros De {county} Marcaron Esta Propiedad",
                lambda: f"Señales De Alerta Rodearon Esta Casa De {county}",
                lambda: f"Cada Señal De Alerta Estaba En El Expediente De {county}",
                lambda: f"Esta Propiedad De {county} Se Vendió Pese A Las Alertas",
            ],
            "bank_vs_house": [
                lambda: f"El Banco Luchó Fuerte Por Esta Casa En {county}",
                lambda: f"El Prestamista De {county} Fue A La Guerra Por Esta Casa",
                lambda: f"Esta Casa Se Volvió Batalla Para El Banco De {county}",
            ],
            "mystery_nobody_bid": [
                lambda: f"Nadie Se Atrevió A Ofertar En {county}",
                lambda: f"La Subasta De {county} Se Quedó En Silencio",
                lambda: f"Esta Casa De {county} No Tuvo Ni Un Postor",
            ],
            "countdown_presale": [
                (lambda: f"Esta Casa De {county} Sale A Subasta En {days} Días") if days is not None
                else (lambda: f"Esta Casa De {county} Se Acerca A Su Subasta"),
                lambda: f"El Reloj De La Subasta De {county} Sigue Corriendo",
                lambda: f"El Tiempo Se Acaba Para Esta Casa De {county}",
            ],
            "remote_bidder": [
                lambda: f"Esta Venta En {county} No Necesitó Un Postor Local",
                lambda: f"Alguien Ganó Esta Subasta De {county} Desde Lejos",
                lambda: f"La Oferta Ganadora De {county} Llegó Desde Otro Lugar",
            ],
        }
    else:
        pools = {
            "shock_number": [
                (lambda: f"The County Valued This {county} Home At ${assessed:,.0f}") if assessed is not None
                else (lambda: f"This {county} Home Shocked The Whole Auction"),
                (lambda: f"{county} Assessors Priced This Home At ${assessed:,.0f}") if assessed is not None
                else (lambda: f"Nobody Guessed This {county} Home's Real Number"),
                (lambda: f"This {county} Home's Real Number Was ${assessed:,.0f}") if assessed is not None
                else (lambda: f"This {county} Home Kept Its Number Hidden"),
                (lambda: f"{county}'s Records Put This Home At ${assessed:,.0f}") if assessed is not None
                else (lambda: f"This {county} Home Kept Everyone Guessing"),
                (lambda: f"This {county} Home Carried A ${assessed:,.0f} Price Tag") if assessed is not None
                else (lambda: f"This {county} Home's True Number Stayed Hidden"),
            ],
            "underdog_bidder": [
                lambda: f"An Underdog Bidder Beat The Field In {county}",
                lambda: f"{county}'s Auction Had An Unlikely Winner",
                lambda: f"One Bidder Outlasted Everyone Else In {county}",
                lambda: f"The Favorite Lost This {county} Auction",
                lambda: f"A Long Shot Took This {county} Property Home",
            ],
            "hidden_value_reveal": [
                lambda: f"This {county} Home Hid Its Real Value",
                lambda: f"{county} Buyers Never Saw This Value Coming",
                lambda: f"The Real Worth Stayed Hidden In {county}",
                lambda: f"This {county} Property Was Worth More Than It Sold",
                lambda: f"{county}'s Listing Undersold Its Own Value",
            ],
            "red_flag_warning": [
                lambda: f"This {county} Home Waved Every Red Flag",
                lambda: f"{county} Records Flagged This Property For A Reason",
                lambda: f"Warning Signs Piled Up On This {county} Home",
                lambda: f"Every Red Flag Was On File In {county}",
                lambda: f"This {county} Property Sold Despite The Warnings",
            ],
            "bank_vs_house": [
                lambda: f"The Bank Fought Hard For This {county} House",
                lambda: f"{county}'s Lender Went To War Over This House",
                lambda: f"This House Became A Battle For {county}'s Bank",
            ],
            "mystery_nobody_bid": [
                lambda: f"Nobody Dared To Bid On This {county} Home",
                lambda: f"{county}'s Auction Floor Went Silent On This One",
                lambda: f"This {county} Home Found Zero Bidders At Auction",
            ],
            "countdown_presale": [
                (lambda: f"This {county} Home Hits Auction In {days} Days") if days is not None
                else (lambda: f"This {county} Home Nears Its Auction Date"),
                lambda: f"{county}'s Auction Clock Is Ticking On This Home",
                lambda: f"Days Are Running Out On This {county} Listing",
            ],
            "remote_bidder": [
                lambda: f"This {county} Sale Never Needed A Local Bidder",
                lambda: f"Someone Won This {county} Auction From Anywhere",
                lambda: f"{county}'s Winning Bid Came From Off-Site",
            ],
        }

    templates = pools.get(archetype)
    if not templates:
        raise ValueError(f"no title template pool for archetype {archetype!r} lang={lang!r}")
    fn = templates[template_index % len(templates)]
    return fn()


def generate_bespoke_title(archetype: str, reel_facts: dict, template_index: int = 0, lang: str = "en") -> str:
    """DEFECT 3 fix: draws from a per-archetype POOL of structurally distinct
    templates built from the row's own facts (assessed value / days to
    auction / condition-derived red flags), instead of one fixed sentence
    with only the county token substituted."""
    county = (reel_facts.get("county") or "").title()
    emoji = ARCHETYPE_EMOJI.get(archetype)
    if emoji is None:
        raise ValueError(f"no emoji mapping for archetype {archetype!r}")
    stem = _title_stem(archetype, county, reel_facts, template_index, lang=lang)
    return f"{stem}{ELLIPSIS}{emoji}"


# ---------------------------------------------------------------------------
# DEFECT 1 -- payoff confined to the 20-28s beat. Setup (2-9s) and tension
# (9-20s) describe the property/situation only; assessed_value is the one
# number allowed early (a Setup-beat fact per check_payoff_leak's own
# allowance), sold_amount/delta_pct (postsale) and opening_bid/judgment_amount
# (presale) are withheld until the payoff beat.
# ---------------------------------------------------------------------------

def _payoff_phrase(phase: str | None, reel_facts: dict, lang: str = "en") -> str:
    if phase == "presale":
        ob = reel_facts.get("opening_bid")
        ja = reel_facts.get("judgment_amount")
        if lang == "es":
            if ob is not None and ja is not None:
                return f"La oferta inicial es de ${ob:,.0f} contra un juicio de ${ja:,.0f}."
            if ob is not None:
                return f"La oferta inicial es de ${ob:,.0f}."
            return "La oferta inicial aún no se ha publicado."
        if ob is not None and ja is not None:
            return f"The opening bid sits at ${ob:,.0f} against a ${ja:,.0f} judgment."
        if ob is not None:
            return f"The opening bid sits at ${ob:,.0f}."
        return "The opening bid has not posted yet."

    sold = reel_facts.get("sold_amount")
    delta = reel_facts.get("delta_pct")
    # issue #19814 defect 1 -- delta_pct is negative for a below-assessed sale
    # and positive for a premium (above-assessed) one; the payoff line must
    # say which direction actually happened, not assert "below" unconditionally
    # (real, live-observed on the tax_deed backfill: Pasco land parcels sold
    # 400-1266% OVER assessed value -- the old hardcoded "below" text would
    # have spoken a false claim on those rows).
    if lang == "es":
        if sold is not None and delta is not None:
            direction = "bajo" if delta < 0 else "sobre"
            return f"Se vendió por ${sold:,.0f}... un {abs(delta):.1f} por ciento {direction} el valor tasado."
        if sold is not None:
            return f"Se vendió por ${sold:,.0f}."
        return "El precio de venta aún no está disponible."
    if sold is not None and delta is not None:
        direction = "below" if delta < 0 else "above"
        return f"It sold for ${sold:,.0f}... {abs(delta):.1f} percent {direction} assessed value."
    if sold is not None:
        return f"It sold for ${sold:,.0f}."
    return "The sale figure is not on file yet."


def _tension_phrase(archetype: str, reel_facts: dict, lang: str = "en") -> str:
    condition = _condition_tier(reel_facts)
    has_condition = _has_condition_data(reel_facts)
    red_flags = _red_flag_signals(reel_facts)
    if lang == "es":
        if archetype == "red_flag_warning" and red_flags:
            return f"Se observó {red_flags} antes de que se cerrara la venta."
        defaults = {
            "shock_number": "Los postores solo tenían un número para reaccionar antes del martillazo.",
            "underdog_bidder": "Compradores más grandes rondaban, pero el grupo se redujo rápido en la subasta.",
            "hidden_value_reveal": "Nada en el anuncio insinuaba lo que esta propiedad realmente valía.",
            "red_flag_warning": (f"Una propiedad en condición {condition} con señales de alerta reales igual se vendió."
                                  if has_condition else
                                  "Una propiedad con señales de alerta reales igual se vendió."),
            "bank_vs_house": "El banco tenía toda la razón para resistir, y casi lo logra.",
            "mystery_nobody_bid": "La subasta se mantuvo en silencio mientras corría el reloj.",
            "remote_bidder": "La oferta ganadora llegó en línea... las reglas de depósito aplicaron igual que siempre.",
            "countdown_presale": (f"El reloj sigue corriendo sobre esta propiedad en condición {condition}."
                                   if has_condition else
                                   "El reloj sigue corriendo sobre esta propiedad."),
        }
        fallback = (f"Una propiedad en condición {condition} con una historia que vale la pena seguir."
                    if has_condition else
                    "Una propiedad con una historia que vale la pena seguir.")
        return defaults.get(archetype, fallback)

    if archetype == "red_flag_warning" and red_flags:
        return f"{red_flags[0].upper()}{red_flags[1:]} showed up in the record before the sale ever closed."
    defaults = {
        "shock_number": "Bidders had exactly one number to react to before the gavel fell.",
        "underdog_bidder": "Bigger buyers circled, but the field narrowed fast on the courthouse steps.",
        "hidden_value_reveal": "Nothing about the listing hinted at what this property was actually worth.",
        "red_flag_warning": (f"A {condition}-condition property with real red flags still went to closing."
                              if has_condition else
                              "A property with real red flags still went to closing."),
        "bank_vs_house": "The lender had every reason to hold out, and almost did.",
        "mystery_nobody_bid": "The auction floor stayed quiet as the clock ran down.",
        "remote_bidder": "The winning bid came in online -- deposit rules still applied like any other sale.",
        "countdown_presale": (f"The clock is running on this {condition}-condition property."
                               if has_condition else
                               "The clock is running on this property."),
    }
    fallback = (f"A {condition}-condition property with a story worth watching."
                if has_condition else
                "A property with a story worth watching.")
    return defaults.get(archetype, fallback)


def build_bespoke_script(archetype: str, reel_facts: dict, title_stem: str, lang: str = "en") -> dict:
    """Returns {"beats": [...]} on the same 5-beat/32s shape every live
    reel_variants row already uses: hook 0-2s, setup 2-9s, tension 9-20s,
    payoff 20-28s, loop_line 28-32s -- aligned to REEL_SPEC_BOLT32.md's
    beat table. Only the payoff beat (start_s>=20) may contain sold_amount/
    delta_pct (postsale) or opening_bid/judgment_amount (presale) --
    verified by check_script_payoff_confinement below, not just asserted
    here by construction."""
    county = (reel_facts.get("county") or "").title()
    condition = _condition_tier(reel_facts)
    has_condition = _has_condition_data(reel_facts)
    sale_phrase = _sale_mechanism_phrase(reel_facts, lang=lang)
    phase = reel_facts.get("phase")
    assessed = reel_facts.get("assessed_value")

    if lang == "es":
        if assessed is not None:
            setup_line = (f"Esta propiedad de condición {condition} en el condado de {county} fue tasada en ${assessed:,.0f}."
                           if has_condition else
                           f"Esta propiedad en el condado de {county} fue tasada en ${assessed:,.0f}.")
        else:
            setup_line = (f"Esta propiedad de condición {condition} en el condado de {county} salió {sale_phrase}."
                           if has_condition else
                           f"Esta propiedad en el condado de {county} salió {sale_phrase}.")
    else:
        if assessed is not None:
            setup_line = (f"This {condition}-condition {county} County home was assessed at ${assessed:,.0f}."
                           if has_condition else
                           f"This {county} County home was assessed at ${assessed:,.0f}.")
        else:
            setup_line = (f"This {condition}-condition {county} County home came up {sale_phrase}."
                           if has_condition else
                           f"This {county} County home came up {sale_phrase}.")

    tension_line = _tension_phrase(archetype, reel_facts, lang=lang)
    payoff_line = _payoff_phrase(phase, reel_facts, lang=lang)
    loop_line = loop_line_for(archetype, reel_facts, lang=lang)

    beats = [
        {"start_s": 0, "end_s": 2, "line": title_stem},
        {"start_s": 2, "end_s": 9, "line": setup_line},
        {"start_s": 9, "end_s": 20, "line": tension_line},
        {"start_s": 20, "end_s": 28, "line": payoff_line},
        {"start_s": 28, "end_s": 32, "line": loop_line},
    ]
    return {"beats": beats}


def build_caption_groups_from_beats(beats: list[dict], max_words: int = 5) -> list[dict]:
    groups = []
    for b in beats:
        start_s = float(b["start_s"])
        end_s = float(b["end_s"])
        words = str(b.get("line", "")).split()
        chunks = [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)] or [""]
        step = (end_s - start_s) / len(chunks)
        for i, chunk in enumerate(chunks):
            groups.append({
                "start_s": round(start_s + i * step, 2),
                "end_s": round(start_s + (i + 1) * step, 2),
                "words": chunk,
            })
    return groups


# ---------------------------------------------------------------------------
# DEFECT 2 -- per-archetype loop-line bank (replaces the single hardcoded
# "Next <County> countdown starts now" line that fired on every variant
# regardless of archetype/phase). "countdown" language is reachable ONLY
# through the countdown_presale branch, which itself refuses to run on a
# non-presale row (defense in depth with check_loop_line_archetype_mismatch,
# which catches it even if a loop line came from a different code path).
# ---------------------------------------------------------------------------

def loop_line_for(archetype: str, reel_facts: dict, lang: str = "en") -> str:
    phase = reel_facts.get("phase")
    county = (reel_facts.get("county") or "").title()
    days = reel_facts.get("days_to_auction")

    if archetype == "countdown_presale" and phase != "presale":
        raise ValueError(f"loop_line_for: archetype 'countdown_presale' requires phase='presale', got {phase!r}")

    if lang == "es":
        lines = {
            "shock_number": f"Ese número en {county}... ¿lo habrías adivinado?",
            "underdog_bidder": f"Un solo postor se mantuvo firme en {county}... así se gana una subasta.",
            "hidden_value_reveal": f"El valor real estuvo ahí todo el tiempo en {county}... y nadie lo vio venir.",
            "red_flag_warning": f"Cada señal de alerta estaba en el expediente de {county}... y aun así se vendió.",
            "bank_vs_house": f"El banco consiguió su número en {county}... esta vez.",
            "mystery_nobody_bid": f"Silencio en la subasta de {county}... eso también dice algo.",
            "remote_bidder": f"El ganador de {county} nunca puso un pie en Florida... se puede ofertar en línea desde cualquier lugar, las reglas de depósito aplican igual.",
            "countdown_presale": (f"La próxima cuenta regresiva de {county} empieza en {days} días." if days is not None
                                   else f"La próxima cuenta regresiva de {county} ya está en marcha."),
        }
    else:
        lines = {
            "shock_number": f"That number in {county} County... would you have guessed it?",
            "underdog_bidder": f"One bidder stayed in it in {county} County... that's how you win one.",
            "hidden_value_reveal": f"The real value was there in {county} County the whole time... and nobody saw it coming.",
            "red_flag_warning": f"Every warning sign was on file in {county} County... and it sold anyway.",
            "bank_vs_house": f"The bank got its number in {county} County... this time.",
            "mystery_nobody_bid": f"Silence at the {county} County auction... that's its own kind of answer.",
            "remote_bidder": f"This {county} County winner never had to set foot in Florida... bid online from anywhere, deposit rules still apply.",
            "countdown_presale": (f"The next {county} County countdown starts in {days} days." if days is not None
                                   else f"The next {county} County countdown is already running."),
        }

    if archetype not in lines:
        raise ValueError(f"no loop line template for archetype {archetype!r}")
    return lines[archetype]


def check_script_payoff_confinement(beats: list[dict], reel_facts: dict) -> tuple[bool, list[str]]:
    """DEFECT 1 negative test (a): a beat starting before 20s that contains
    the payoff figure (sold_amount/delta_pct postsale, opening_bid/
    judgment_amount presale) fails. Assessed value and any other non-payoff
    number are unaffected -- this checks the PAYOFF figures specifically,
    not "any beat with any number in it"."""
    reasons = []
    reel_facts = reel_facts or {}
    phase = reel_facts.get("phase")
    if phase == "presale":
        payoff_fields = [("opening bid", reel_facts.get("opening_bid")), ("judgment amount", reel_facts.get("judgment_amount"))]
    else:
        payoff_fields = [("sold price", reel_facts.get("sold_amount")), ("discount percentage", reel_facts.get("delta_pct"))]

    for beat in beats or []:
        try:
            start_s = float(beat.get("start_s", 0))
        except (TypeError, ValueError):
            start_s = 0.0
        if start_s >= 20:
            continue
        line = str(beat.get("line", ""))
        digits_found = {d.replace(",", "") for d in re.findall(r"[\d,]+(?:\.\d+)?", line)}
        for label, value in payoff_fields:
            if value is None:
                continue
            candidates = {f"{value:,.0f}", f"{value:.0f}", f"{abs(value):,.0f}", f"{abs(value):.0f}", f"{abs(value):.1f}"}
            for c in candidates:
                if c.replace(",", "") in digits_found:
                    reasons.append(f"beat starting at {start_s}s leaks the {label} figure ({c}) before the 20-28s payoff beat")
                    break
    return (len(reasons) == 0, reasons)


def check_loop_line_archetype_mismatch(loop_line: str, reel_facts: dict) -> tuple[bool, list[str]]:
    """DEFECT 2 negative test (b): a loop line containing 'countdown' is
    rejected unless the row's own phase is 'presale' -- catches the
    hardcoded-generic-line class of bug regardless of which code path
    produced the loop line."""
    reasons = []
    phase = (reel_facts or {}).get("phase")
    if "countdown" in (loop_line or "").lower() and phase != "presale":
        reasons.append(f"loop line contains 'countdown' but phase={phase!r} (must be 'presale')")
    return (len(reasons) == 0, reasons)


# ---------------------------------------------------------------------------
# DEFECT 3 negative test (c) -- structural-similarity assertion. Same-
# archetype titles must differ in sentence structure across at least half
# their word count once county/number tokens are removed, not just swap the
# proper noun. Uses token-level Levenshtein distance, not character edit
# distance, so word reordering/substitution is what's measured, not typos.
# ---------------------------------------------------------------------------

def _levenshtein(a: list, b: list) -> int:
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[m]


def _structural_tokens(title: str, county: str = "") -> list[str]:
    stem = title.split(ELLIPSIS)[0] if ELLIPSIS in (title or "") else (title or "")
    tokens = [t.lower() for t in re.findall(r"[^\W\d_]+", stem, flags=re.UNICODE)]
    county_tokens = {w.lower() for w in re.findall(r"[^\W\d_]+", county or "")}
    return [t for t in tokens if t not in county_tokens]


def title_structural_similarity(title_a: str, county_a: str, title_b: str, county_b: str) -> float:
    ta = _structural_tokens(title_a, county_a)
    tb = _structural_tokens(title_b, county_b)
    if not ta and not tb:
        return 1.0
    dist = _levenshtein(ta, tb)
    return 1 - (dist / max(len(ta), len(tb)))


def check_title_structural_similarity(entries: list[dict], threshold: float = 0.5) -> tuple[bool, list[str]]:
    """entries: [{"title":..., "county":..., "archetype":..., "id":...}, ...].
    Groups by archetype; any same-archetype pair whose structural similarity
    exceeds `threshold` (i.e. does NOT differ across at least half their
    word count once county/number tokens are removed) fails."""
    reasons = []
    by_archetype: dict[str, list[dict]] = {}
    for e in entries:
        by_archetype.setdefault(e["archetype"], []).append(e)
    for archetype, group in by_archetype.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                sim = title_structural_similarity(
                    group[i]["title"], group[i].get("county", ""), group[j]["title"], group[j].get("county", ""))
                if sim > threshold:
                    reasons.append(
                        f"archetype {archetype!r}: titles {group[i].get('id', group[i]['title'])!r} and "
                        f"{group[j].get('id', group[j]['title'])!r} are {sim:.2f} structurally similar "
                        f"(> {threshold}) after removing county/number tokens"
                    )
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


def generate_variants_for_reel(reel: dict, k: int = K_VARIANTS, max_retries: int = 2, log_prefix: str = "",
                                auction_venue_online: bool | None = None) -> dict:
    """Returns {"ok": bool, "variants": [...], "router_meta": {...}, "errors": [...]}.

    Pre-assigns each of the K slots a distinct, random archetype and fires
    all K calls CONCURRENTLY (each is an independent network round-trip to
    OpenRouter, ~30-60s). Archetype is pinned per call rather than offered
    as a free choice -- live-observed this session: given a free choice,
    the model picked "shock_number" for most calls, forcing an expensive
    sequential repair pass to satisfy no-duplicate-archetype. Pinning
    upfront makes diversity-by-construction the common case; any individual
    slot that still fails validation (e.g. a malformed title) is retried
    sequentially with the same pinned archetype. One slot is reserved for
    the framing this property's own numbers support (recommend_framing_
    archetype) when one clears the threshold -- the rest stay random for
    diversity, same as before.

    issue #20032 -- 'remote_bidder' never appeared in any of the 25 live
    variants: not because generation avoids it, but because random.sample
    over 8 archetypes just never happened to draw it in these 5 reels, and
    check_archetype_data_match hard-rejects it at QA time whenever the sale
    record's own auction_venue isn't 'online' (never guessed/defaulted).
    Caller passes that same live fact in as auction_venue_online so this
    function can (a) drop remote_bidder from the pool entirely when it would
    fail QA by construction (same pattern as hidden_value_reveal below), and
    (b) force it into one slot -- like the framing archetype -- when the
    property's own record supports it, so eligible properties actually get
    one instead of leaving it to chance."""
    used_pairs: list = []
    preferred = recommend_framing_archetype(reel.get("sold_amount"), reel.get("assessed_value"))
    # issue #19814 defect 1 -- don't even offer 'hidden_value_reveal' into the
    # random pool for a property that sold ABOVE assessed value: it fails
    # check_archetype_data_match by construction (see that function), so
    # drawing it here only burns an LLM call the QA gate will reject anyway.
    sold_amount, assessed_value = reel.get("sold_amount"), reel.get("assessed_value")
    is_premium_sale = sold_amount is not None and assessed_value and sold_amount > assessed_value
    pool = [a for a in ARCHETYPES if not (is_premium_sale and a == "hidden_value_reveal")]
    if auction_venue_online is not True:
        pool = [a for a in pool if a != "remote_bidder"]

    forced = []
    if preferred:
        forced.append(preferred)
    if auction_venue_online is True and "remote_bidder" not in forced:
        forced.append("remote_bidder")
    remaining_pool = [a for a in pool if a not in forced]
    archetypes = forced + random.sample(remaining_pool, k - len(forced))

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


def fetch_auction_venue_online(county: str, case_number: str) -> bool | None:
    """Live lookup, same field/semantics director_qa.fetch_reel_facts() uses
    for the check_archetype_data_match QA gate -- venue comes ONLY from the
    sale record's own auction_venue column, never inferred from
    source_platform. None (column absent/unset) stays None, never defaulted
    to True/False."""
    try:
        import urllib.parse as up
        rows = lib.pg_rest(
            "multi_county_auctions",
            f"select=auction_venue&case_number=eq.{up.quote(case_number)}"
            f"&county=ilike.{up.quote(county)}&limit=1",
        )
        if not rows:
            return None
        venue = rows[0].get("auction_venue")
        return (str(venue).strip().lower() == "online") if venue is not None else None
    except Exception:
        return None


def run_for_county(county: str, auction_date: str | None, dry_run: bool = False) -> dict:
    reel = fetch_shortlisted_reel(county, auction_date)
    if not reel:
        return {"county": county, "ok": False, "error": "no biddeed_reels row found"}

    auction_venue_online = fetch_auction_venue_online(reel["county"], reel["case_number"])
    result = generate_variants_for_reel(reel, log_prefix=f"[{county}]", auction_venue_online=auction_venue_online)
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
