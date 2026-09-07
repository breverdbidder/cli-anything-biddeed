#!/usr/bin/env python3
"""Retry an OpenRouter 402 at the budget the API itself reports.

Why
---
16 reels died at T3 condition scoring on a 402 that is NOT an empty balance --
it is the key's weekly limit, and the error body states the exact ceiling:

    OpenRouter z-ai/glm-5.3-flash HTTP 402: {"error":{"message":"This request
    requires more credits, or fewer max_tokens. You requested up to 1500
    tokens, but can only afford 627. ... adjust the key's weekly limit"}}

Observed affordable ceilings across the failures: 1255, 697, 627, 237. Three of
those four are comfortably enough for this call; the request asked for 1500 and
was rejected outright rather than trimmed, so all four fell through to the
DeepSeek tier (402 again at 237) and then to claude-router, which answered for
some rows and returned "all tiers exhausted" for others.

_openrouter_vision's max_tokens cannot simply be lowered: reasoning tokens are
mandatory on this endpoint (reasoning:{enabled:false} and effort:"none" both
400) and a tight cap returns null content instead of JSON -- Ariel's 2026-09-02
live test. So the fix is not a smaller constant, it is one retry at the number
the API just told us we can afford, and only when that number is large enough to
leave room for reasoning plus the condition JSON.

Costs nothing, needs no dashboard change, and still falls through to the
existing tier cascade when the ceiling is genuinely too low.

Idempotent: exits 0 with "already applied" on a second run.
"""
import sys

MARKER = "_AFFORDABLE_RE"

ANCHOR_CONST = '''OPENROUTER_PRIMARY_MODEL = "z-ai/glm-5.3-flash"
'''

NEW_CONST = '''OPENROUTER_PRIMARY_MODEL = "z-ai/glm-5.3-flash"
# A 402 from OpenRouter names the exact token ceiling the key can currently
# afford ("you requested up to 1500 tokens, but can only afford 627"). Below
# this floor there is no point retrying: reasoning tokens are mandatory on the
# vision endpoint and a cap this tight returns null content rather than JSON.
_AFFORDABLE_RE = re.compile(r"can only afford (\\d+)")
OPENROUTER_MIN_AFFORDABLE_TOKENS = 600
'''

ANCHOR_CALL = '''    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"OpenRouter {model} HTTP {e.code}: {body[:300]}")
'''

NEW_CALL = '''    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        # A 402 here is a weekly-limit ceiling, not an empty balance, and the
        # body names the ceiling. Retry once at exactly that number when it
        # leaves room for the mandatory reasoning tokens plus the condition
        # JSON; otherwise fall through to the next tier as before.
        affordable = None
        if e.code == 402:
            m = _AFFORDABLE_RE.search(body)
            if m:
                affordable = int(m.group(1))
        if affordable is not None and affordable >= OPENROUTER_MIN_AFFORDABLE_TOKENS \\
                and affordable < payload["max_tokens"]:
            payload["max_tokens"] = affordable
            retry = urllib.request.Request(
                OPENROUTER_CHAT_URL, data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(retry, timeout=90) as resp:
                    data = json.loads(resp.read().decode())
            except urllib.error.HTTPError as e2:
                body2 = e2.read().decode() if e2.fp else ""
                raise RuntimeError(
                    f"OpenRouter {model} HTTP {e.code} then HTTP {e2.code} on the "
                    f"budget retry at max_tokens={affordable}: {body2[:200]}"
                )
        else:
            raise RuntimeError(
                f"OpenRouter {model} HTTP {e.code}"
                + (f" (affordable={affordable}, below the {OPENROUTER_MIN_AFFORDABLE_TOKENS}"
                   f"-token retry floor)" if affordable is not None else "")
                + f": {body[:300]}"
            )
'''


def main(path):
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print("already applied")
        return 0

    for old, new, what in ((ANCHOR_CONST, NEW_CONST, "constants"),
                           (ANCHOR_CALL, NEW_CALL, "402 handler")):
        n = src.count(old)
        if n != 1:
            raise SystemExit(f"{what} anchor matched {n} times, expected 1")
        src = src.replace(old, new, 1)

    open(path, "w", encoding="utf-8").write(src)

    for needle in ("_AFFORDABLE_RE", "OPENROUTER_MIN_AFFORDABLE_TOKENS", "budget retry at max_tokens="):
        if needle not in src:
            raise SystemExit(f"missing after patch: {needle!r}")
    print(f"patched {path}: OpenRouter 402 budget-aware retry")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "scripts/biddeed_reels_lib.py"))
