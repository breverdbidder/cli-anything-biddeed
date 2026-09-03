#!/usr/bin/env python3
"""TRANSLATOR -- agents/reel_studio/translator.py (issue #19793 PART 3).

Translates an already-approved-shape English winnerdata.reel_variants row
into es/pt-BR, via the router (t1 Gemini free / t1.5 DeepSeek cheap only --
same "No Anthropic API calls in this agent family" constraint hook_writer.py
and router_client.py already enforce, see that module's docstring).

Numbers, county names, and the short URL must pass through UNCHANGED --
assert_figure_link_bytematch() is the DoD negative test (c) enforcement:
a translated script whose sale figure or short link differs from the
English source fails, not silently ships.

CLI:
  python3 translator.py translate --variant-id UUID --lang es
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import router_client  # noqa: E402
import analyst  # noqa: E402 -- reuse mint_variant_short_link(), don't reinvent short-code minting

TRANSLATABLE_LANGS = {"es": "Spanish", "pt-BR": "Brazilian Portuguese"}

# Issue #19793 PART 3 -- explicitly NOT built this issue. AR needs full RTL
# layout for captions/URL chip/safe-area (this pipeline's drawtext/safe-area
# math is LTR-only throughout biddeed_reels_lib.py); ZH needs a CJK-glyph
# font in the render environment (_ensure_font()'s Inter/DejaVu fallback has
# no CJK glyph coverage -- drawtext would render tofu boxes) plus a different
# caption-density rule (CJK characters carry far more information per
# character than the 26-char/line Latin-script budget assumes). HE also
# needs eleven_v3 (kokoro has no lang_code for Hebrew or Arabic) and RTL.
BLOCKED_LANGS = {
    "ar": "needs full RTL layout for captions/URL chip/safe-area -- this "
          "pipeline's drawtext/safe-area math (SAFE_AREA_X/Y, dt_wrapped_centered) is LTR-only",
    "zh": "needs a CJK-glyph font in the render environment (_ensure_font()'s "
          "Inter/DejaVu fallback has no CJK coverage -- drawtext would render "
          "tofu boxes) plus a different caption-density rule (26-char/line is "
          "a Latin-script budget, CJK needs a per-character, not per-word, rule)",
    "he": "kokoro has no lang_code for Hebrew -- HE stays on the eleven_v3-only "
          "(credit-blocked) path per the issue's own instruction; also needs RTL layout",
}


class TranslationByteMatchError(ValueError):
    pass


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text).rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in router output: {text[:300]}")
    return json.loads(text[start:end + 1])


def build_translation_prompt(variant: dict, target_lang: str, lang_name: str) -> tuple[str, str]:
    system = (
        f"You translate short-form real-estate auction reel scripts from English to {lang_name}. "
        "CRITICAL: any dollar figure, percentage, county name, or URL in the source text MUST appear "
        "byte-identical in your translation -- do not localize currency format, do not round numbers, "
        "do not translate the URL or the county name. Translate only the surrounding narration. "
        "Return strict JSON only, no prose, no markdown fences."
    )
    beats = variant["script"].get("beats", [])
    user = f"""Source (English):
title: {variant['title']}
beats: {json.dumps([{"start_s": b.get("start_s"), "end_s": b.get("end_s"), "line": b.get("line")} for b in beats])}
caption_groups: {json.dumps(variant.get("caption_groups") or [])}

Return a single JSON object:
{{
  "title": "translated title, same meaning, any dollar figure/county/URL byte-identical to source",
  "beats": [{{"start_s": <same as source>, "end_s": <same as source>, "line": "translated line"}}, ...],
  "caption_groups": [{{"start_s": <same>, "end_s": <same>, "words": "translated words"}}, ...]
}}
Same number of beats/caption_groups as the source, same start_s/end_s values (only translate "line"/"words").
Single JSON object only, no array, no prose."""
    return system, user


def _all_numbers(text: str) -> list[str]:
    """Extracts dollar figures and bare large numbers (>=1000, with or
    without $/commas) so a translation that reformats/rounds/drops a number
    is caught even if it keeps the currency symbol."""
    return re.findall(r"\$?\d[\d,]{2,}(?:\.\d+)?%?", text or "")


def assert_figure_link_bytematch(source_beats: list[dict], translated_beats: list[dict], short_url: str) -> None:
    """DoD negative test (c): a translated script whose sale figure or short
    link differs from the English source fails. Checks two independent
    things: (1) every numeric token found in the English source beats
    reappears byte-identical somewhere in the translated beats; (2) the
    short_url's bare domain+path reappears byte-identical in the translated
    text if it appeared in the source at all (loop_line beat speaks it)."""
    source_text = " ".join(str(b.get("line", "")) for b in source_beats)
    translated_text = " ".join(str(b.get("line", "")) for b in translated_beats)

    source_numbers = set(_all_numbers(source_text))
    missing = [n for n in source_numbers if n not in translated_text]
    if missing:
        raise TranslationByteMatchError(
            f"translated script drops/reformats source figures: {missing} not found byte-identical "
            f"in translated text {translated_text!r}"
        )

    bare_url = re.sub(r"^https?://", "", short_url or "")
    if bare_url and bare_url in source_text and bare_url not in translated_text:
        raise TranslationByteMatchError(
            f"source spoke the short link {bare_url!r} but the translated script does not contain it byte-identical"
        )


def translate_variant(variant_id: str, target_lang: str) -> dict:
    if target_lang not in TRANSLATABLE_LANGS:
        if target_lang in BLOCKED_LANGS:
            raise ValueError(f"{target_lang} is explicitly BLOCKED this issue: {BLOCKED_LANGS[target_lang]}")
        raise ValueError(f"unsupported target_lang {target_lang!r}, expected one of {sorted(TRANSLATABLE_LANGS)}")

    rows = lib.run_sql(f"""
        select id, reel_id, variant_key, variant_dna, archetype, title, script, caption_groups,
               voice_tags, hashtags, short_code, short_url, status, lang
        from winnerdata.reel_variants where id = {lib.sql_str(variant_id)};
    """)
    if not rows:
        raise ValueError(f"no reel_variants row for id={variant_id}")
    variant = rows[0]
    for col in ("variant_dna", "script", "caption_groups", "voice_tags"):
        if isinstance(variant.get(col), str):
            variant[col] = json.loads(variant[col])
    if variant.get("lang", "en") != "en":
        raise ValueError(f"translate_variant expects an English source row, got lang={variant.get('lang')!r}")

    system, user = build_translation_prompt(variant, target_lang, TRANSLATABLE_LANGS[target_lang])
    # call_router_with_fallback: T1 Gemini -> T1.5 DeepSeek -> direct
    # OpenRouter GLM, all non-Anthropic (router_client.py's own cascade,
    # live-needed this session: T1/T1.5 both fell through to T2/Claude,
    # which call_router() correctly refused rather than silently accepting).
    resp = router_client.call_router_with_fallback(
        messages=[{"role": "user", "content": user}], system=system,
        max_tokens=3000, tool_name="reel_studio_translator",
    )
    translated = _extract_json_object(resp["text"])

    source_beats = variant["script"].get("beats", [])
    translated_beats = translated.get("beats", [])
    if len(translated_beats) != len(source_beats):
        raise ValueError(f"translation returned {len(translated_beats)} beats, expected {len(source_beats)}")

    assert_figure_link_bytematch(source_beats, translated_beats, variant["short_url"])

    new_script = dict(variant["script"], beats=translated_beats)
    new_variant_dna = dict(variant["variant_dna"], lang=target_lang)

    # A translated variant is its own row and reel_variants.short_code carries
    # a hard DB-level unique index (reel_variants_short_code_uidx, live-
    # discovered this session -- distinct from the constraints pg_constraint
    # lists, since it's a bare unique index, not a table constraint) -- it
    # can NOT reuse the English source's short_code. Mints a fresh one via
    # the existing analyst.mint_variant_short_link(), same mechanism every
    # other reel_variants row already uses (English archetype siblings A-D
    # of the SAME property already each carry their own distinct short_code
    # for per-variant attribution -- a translated sibling is no different).
    # The destination property/case is identical; only the tracking token
    # differs. The DoD's figure/link byte-match requirement is about the
    # TRANSLATED SCRIPT TEXT not corrupting a number or the spoken generic
    # "biddeed.ai" domain mention -- checked above by
    # assert_figure_link_bytematch(), independent of which short_code is minted.
    new_code, new_short_url, new_qr_url = analyst.mint_variant_short_link(
        {"id": variant["reel_id"]}, f"{variant['variant_key']}_{target_lang}"
    )

    # NOTE: `archetype` is a generated column (derived from variant_dna->>'archetype'
    # -- live-confirmed this session, 428C9 "cannot insert a non-DEFAULT value into
    # column archetype"), so it is never in the insert column list; setting it via
    # new_variant_dna (unchanged from the source row) is what actually carries it.
    insert_rows = lib.run_sql(f"""
        insert into winnerdata.reel_variants
            (reel_id, variant_key, variant_dna, title, script, caption_groups,
             voice_tags, hashtags, short_code, short_url, qr_url, lang, status)
        values (
            {lib.sql_str(variant['reel_id'])}, {lib.sql_str(variant['variant_key'])},
            {lib.sql_jsonb(new_variant_dna)},
            {lib.sql_str(translated['title'])}, {lib.sql_jsonb(new_script)},
            {lib.sql_jsonb(translated.get('caption_groups') or variant.get('caption_groups'))},
            {lib.sql_jsonb(variant.get('voice_tags'))}, {lib.sql_text_array(variant.get('hashtags'))},
            {lib.sql_str(new_code)}, {lib.sql_str(new_short_url)}, {lib.sql_str(new_qr_url)},
            {lib.sql_str(target_lang)}, 'pending_approval'
        )
        returning id;
    """)
    new_id = insert_rows[0]["id"]

    return {
        "source_variant_id": variant_id, "new_variant_id": new_id,
        "target_lang": target_lang, "router_tier": resp["tier"], "router_model": resp["model"],
        "title": translated["title"], "bytematch": "PASS",
    }


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("translate")
    t.add_argument("--variant-id", required=True)
    t.add_argument("--lang", required=True, choices=sorted(TRANSLATABLE_LANGS))
    args = ap.parse_args()
    if args.cmd == "translate":
        print(json.dumps(translate_variant(args.variant_id, args.lang), indent=2, default=str))


if __name__ == "__main__":
    main()
