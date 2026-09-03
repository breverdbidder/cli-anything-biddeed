#!/usr/bin/env python3
"""kokoro/chatterbox draft-TTS fallback gate for bolt32 (issue #19787).

eleven_v3 (voice TX3LPaxmHKxFdv7VOQHJ) remains the canonical English brand
voice -- this module never changes that. kokoro (Apache-2.0, hexgrad/kokoro)
is ADOPTED as a draft/multilingual fallback ONLY, gated behind the
BOLT32_TTS_FALLBACK env var (default unset -> 'elevenlabs', i.e. no
behavior change unless someone deliberately opts in). resolve_tts_provider()
is the single decision point: a non-draft English reel can NEVER resolve to
kokoro/chatterbox, no matter what the env var says -- this is a hard
programming invariant, not a runtime toggle, per the issue's DoD negative
test (b): "kokoro audio on a non-draft English reel fails."

This module only decides the PROVIDER. It does not call any TTS API itself
-- scripts/biddeed_reels_lib.py's existing eleven_v3 synthesis path is
unchanged; wiring an actual kokoro/chatterbox HTTP call is out of scope
until a draft-lane pipeline exists to call it from (none does yet -- bolt32
is the postsale/presale production lane, not a draft lane).
"""
from __future__ import annotations

import os

CANONICAL_ENGLISH_PROVIDER = "elevenlabs"
CANONICAL_ENGLISH_MODEL = "eleven_v3"
DRAFT_FALLBACK_PROVIDERS = {"kokoro", "chatterbox"}
ENV_VAR = "BOLT32_TTS_FALLBACK"


class Bolt32TTSPolicyError(Exception):
    pass


def resolve_tts_provider(lang: str, draft: bool) -> tuple[str, str]:
    """Returns (provider, model_or_voice). Raises Bolt32TTSPolicyError if a
    draft-fallback provider is requested (via env var) for a non-draft
    English reel -- negative test (b)."""
    requested = os.environ.get(ENV_VAR, "").strip().lower() or CANONICAL_ENGLISH_PROVIDER

    if requested in DRAFT_FALLBACK_PROVIDERS:
        if lang == "en" and not draft:
            raise Bolt32TTSPolicyError(
                f"{ENV_VAR}={requested!r} is a draft/multilingual-only fallback -- "
                f"refusing to use it for a non-draft English reel. eleven_v3 is the "
                f"only allowed provider for approved English bolt32 renders."
            )
        return requested, requested  # kokoro/chatterbox: model == provider name today

    if requested != CANONICAL_ENGLISH_PROVIDER:
        raise Bolt32TTSPolicyError(
            f"unknown {ENV_VAR}={requested!r} -- expected one of "
            f"{sorted(DRAFT_FALLBACK_PROVIDERS)} or unset/'{CANONICAL_ENGLISH_PROVIDER}'"
        )
    return CANONICAL_ENGLISH_PROVIDER, CANONICAL_ENGLISH_MODEL


def _selftest() -> int:
    # Canonical path: no env var set -> eleven_v3, always, regardless of draft/lang.
    for lang, draft in [("en", False), ("en", True), ("es", False)]:
        os.environ.pop(ENV_VAR, None)
        provider, model = resolve_tts_provider(lang, draft)
        assert (provider, model) == (CANONICAL_ENGLISH_PROVIDER, CANONICAL_ENGLISH_MODEL), (provider, model)
    print("test_default_always_eleven_v3: PASS")

    # Negative test (b): kokoro on a non-draft English reel must fail.
    os.environ[ENV_VAR] = "kokoro"
    try:
        resolve_tts_provider("en", False)
        print("test_kokoro_blocked_on_approved_english: FAIL (no exception raised)")
        return 1
    except Bolt32TTSPolicyError as e:
        print(f"test_kokoro_blocked_on_approved_english: PASS ({e})")

    # kokoro allowed on a draft English reel.
    provider, model = resolve_tts_provider("en", True)
    assert provider == "kokoro"
    print("test_kokoro_allowed_on_draft: PASS")

    # chatterbox allowed on non-English, non-draft (multilingual fallback use case).
    os.environ[ENV_VAR] = "chatterbox"
    provider, model = resolve_tts_provider("es", False)
    assert provider == "chatterbox"
    provider, model = resolve_tts_provider("he", False)
    assert provider == "chatterbox"
    print("test_chatterbox_allowed_on_es_he: PASS")

    # Unknown value fails closed, not silently.
    os.environ[ENV_VAR] = "some-random-tts"
    try:
        resolve_tts_provider("en", True)
        print("test_unknown_provider_rejected: FAIL (no exception raised)")
        return 1
    except Bolt32TTSPolicyError as e:
        print(f"test_unknown_provider_rejected: PASS ({e})")
    finally:
        os.environ.pop(ENV_VAR, None)

    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
