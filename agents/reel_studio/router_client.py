"""Shared claude-router client for agents/reel_studio/*.

Issue #19782 hard constraint: "No Anthropic API calls in any agent (router
t1/t1.5, OpenRouter GLM/DeepSeek, or Ollama on the runner only)." The
claude-router edge function (supabase/functions/claude-router/index.ts) is
this repo's existing "router t1/t1.5" -- T1 = Gemini free tier, T1.5 =
DeepSeek cheap tier, both non-Anthropic. It also carries a T2 Claude Max
OAuth tier as its OWN last-resort fallback, and that T2 branch is NOT gated
by force_tier in the router's own code (verified by reading
supabase/functions/claude-router/index.ts:636-666 -- forceTier only gates
whether T1 gets added; T1.5 and T2 are appended unconditionally). So
force_tier alone cannot guarantee this issue's "no Anthropic" constraint --
this client enforces it itself, after the call, by rejecting any response
whose tier/provider is anthropic. That is the actual guardrail, not the
force_tier param (which is best-effort only).

Auth: X-Router-Key header, value = vault secret "router_proxy_key", fetched
via scripts/biddeed_reels_lib.get_vault_secret() (CREDENTIAL HANDLING
mandate -- RPC only, never echoed, never placed in a shell command). Falls
back to env var ROUTER_PROXY_KEY if set (matches the existing pipeline's
resolve_key() convention in scripts/biddeed_reels_pipeline.py).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import biddeed_reels_lib as lib  # noqa: E402

ROUTER_URL = lib.SUPABASE_URL + "/functions/v1/claude-router"
NON_ANTHROPIC_TIERS = {"T1_gemini_free", "T1.5_deepseek_cheap"}


class RouterBlockedAnthropicTier(RuntimeError):
    """Raised when the router's cascade fell through to its T2 Claude tier.
    Issue #19782 forbids any Anthropic call in this agent family -- the
    caller must treat this exactly like a hard failure of the LLM step
    (retry, or report BLOCKED), never silently accept the text."""


def _resolve_router_key() -> str | None:
    env_key = os.environ.get("ROUTER_PROXY_KEY")
    if env_key:
        return env_key
    try:
        return lib.get_vault_secret("router_proxy_key")
    except Exception:
        return None


def call_router(
    messages: list[dict],
    system: str | None = None,
    max_tokens: int = 2000,
    tool_name: str = "reel_studio",
    force_tier: str = "gemini",
    timeout_s: int = 90,
) -> dict:
    """Returns {"text", "tier", "provider", "model"} or raises.

    Raises RouterBlockedAnthropicTier if the only tier that answered was
    T2 (Claude) -- this agent family may not use that output.
    Raises RuntimeError for any other failure (no key, network, no text).
    """
    router_key = _resolve_router_key()
    if not router_key:
        raise RuntimeError("router_proxy_key not available (env ROUTER_PROXY_KEY unset, vault fetch failed)")

    payload = {
        "messages": messages,
        "system": system,
        "max_tokens": max_tokens,
        "source": "reel-studio",
        "tool_name": tool_name,
        "force_tier": force_tier,
        "metadata": {"request_type": "creative_generation"},
    }
    req = urllib.request.Request(
        ROUTER_URL,
        data=json.dumps(payload).encode(),
        headers={
            "X-Router-Key": router_key,
            "apikey": lib.SERVICE_ROLE_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"claude-router HTTP {e.code}: {body[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"claude-router unreachable: {e}")

    if "error" in data:
        raise RuntimeError(f"claude-router error: {data['error']}")

    tier = data.get("tier", "")
    provider = data.get("provider", "")
    text = data.get("text")
    model = (data.get("model_used") or data.get("model") or "")

    # A cache hit reports tier=provider="cache" and model="cache(<original model>)"
    # -- if the ORIGINAL call that populated the cache landed on Claude, the
    # cache-hit response would otherwise slip past the provider/tier check
    # above (both read "cache", not "anthropic"/"T2..."). Found by this
    # module's own eval (case router_rejects_or_avoids_anthropic_tier_live)
    # returning tier=cache on a second identical call -- inspect the model
    # string too, not just tier/provider.
    is_cached_anthropic = tier == "cache" and "claude" in model.lower()

    if provider == "anthropic" or tier.startswith("T2") or is_cached_anthropic:
        raise RouterBlockedAnthropicTier(
            f"router cascade landed on {tier}/{provider} (model={model}) -- refusing per "
            f"issue #19782 'No Anthropic API calls in any agent'"
        )

    if not text:
        raise RuntimeError(f"claude-router returned no text (tier={tier})")

    return {
        "text": text.strip(),
        "tier": tier,
        "provider": provider,
        "model": data.get("model_used") or data.get("model"),
    }


OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_TEXT_MODEL = "z-ai/glm-5.3-flash"  # same GLM slug the T10 vision cascade uses, text mode


def call_openrouter_text(messages: list[dict], system: str | None = None, max_tokens: int = 4000, timeout_s: int = 90) -> dict:
    """Direct OpenRouter GLM call -- the issue's other explicitly-allowed
    non-Anthropic path ("OpenRouter GLM/DeepSeek"), used when claude-router's
    own T1/T1.5 cascade can't answer (live-observed this session: T1 Gemini
    429s, T1.5 DeepSeek has no vault key -- see docs/spec/19782.md for the
    evidence). Key: vault secret "openrouter_api_key" (same one T10's vision
    cascade already uses in scripts/biddeed_reels_lib.py -- not a new key).
    `reasoning: {"exclude": true}` is required: without it this model spends
    its whole max_tokens budget on a reasoning trace and returns empty
    content (live-observed, finish_reason="length", content=null)."""
    key = os.environ.get("OPENROUTER_API_KEY") or lib.get_vault_secret("openrouter_api_key")
    full_messages = ([{"role": "system", "content": system}] if system else []) + messages
    payload = {
        "model": OPENROUTER_TEXT_MODEL,
        "messages": full_messages,
        "max_tokens": max_tokens,
        "reasoning": {"exclude": True},
    }
    req = urllib.request.Request(
        OPENROUTER_CHAT_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"OpenRouter HTTP {e.code}: {body[:300]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenRouter unreachable: {e}")

    choice = (data.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content")
    if not text:
        raise RuntimeError(f"OpenRouter returned no content (finish_reason={choice.get('finish_reason')})")
    return {"text": text.strip(), "tier": "openrouter_glm", "provider": "openrouter", "model": data.get("model")}


def call_router_with_fallback(messages: list[dict], **kwargs) -> dict:
    """Try claude-router T1 (gemini) -> T1.5 (no force_tier, lets DeepSeek
    answer if the vault key exists) -> direct OpenRouter GLM. All three are
    non-Anthropic per issue #19782; every branch that reaches an Anthropic
    tier is rejected by call_router() itself, never silently accepted here."""
    try:
        return call_router(messages, force_tier="gemini", **kwargs)
    except Exception as e1:
        try:
            return call_router(messages, force_tier=None, **kwargs)
        except Exception as e2:
            try:
                system = kwargs.get("system")
                max_tokens = kwargs.get("max_tokens", 4000)
                return call_openrouter_text(messages, system=system, max_tokens=max_tokens)
            except Exception as e3:
                raise RuntimeError(f"all three non-anthropic attempts failed: gemini={e1!r} deepseek_or_t2blocked={e2!r} openrouter_glm={e3!r}")
