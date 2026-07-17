#!/usr/bin/env python3
"""
CERTIFY ROUTER: Haiku→Sonnet→Opus tiered verification

Invariant: authority='gate' on every cert row.
LLM tiers may VETO (escalate) a gate pass, never GRANT one.
No model can flip a hard-gate FAIL to PASS.
"""
from __future__ import annotations

import json
import logging
import os
import random
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("certify_router")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def _headers() -> dict:
    key = os.environ.get("SUPABASE_KEY", SUPABASE_KEY)
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

MODEL_HAIKU  = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-4-6"
MODEL_OPUS   = "claude-opus-4-8"

# Fallback floors when DB read fails
DEFAULT_HAIKU_FLOOR  = 0.90
DEFAULT_SONNET_FLOOR = 0.85
DEFAULT_SHADOW_RATE  = 0.10

# Cost per 1M tokens (USD)
COST_PER_M = {
    MODEL_HAIKU:  (0.80, 4.00),
    MODEL_SONNET: (3.00, 15.00),
    MODEL_OPUS:   (15.00, 75.00),
}

# Sentinel alert on shadow disagreement
SENTINEL_TABLE = "sentinel_alerts"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class GateResult:
    pass_count: int
    verdict: str                  # 'pass' | 'fail'
    letters: dict[str, bool]
    detail: dict[str, dict]       # {A: {metric, detail}, ...}


@dataclass
class ScreenResult:
    verdict: str                  # 'clean' | 'escalate'
    confidence: float
    reason: str
    raw: str
    tokens_in: int
    tokens_out: int
    parse_ok: bool = True


@dataclass
class CertDecision:
    county_slug: str
    run_id: str
    final_certify: bool
    final_tier: str               # 'gate_fail'|'t1'|'t2'|'t3'|'gate_only'
    authority: str = "gate"
    gate: Optional[GateResult] = None
    t1: Optional[ScreenResult] = None
    t2: Optional[ScreenResult] = None
    t3_invoked: bool = False
    t3_diagnosis: str = ""
    t3_tokens_in: int = 0
    t3_tokens_out: int = 0


@dataclass
class RunTelemetry:
    run_id: str
    counties_total: int = 0
    counties_gate_fail: int = 0
    counties_t1_cert: int = 0
    counties_t2_cert: int = 0
    counties_t3_review: int = 0
    t1_tokens_total: int = 0
    t2_tokens_total: int = 0
    t3_tokens_total: int = 0
    cost_cents_haiku: float = 0.0
    cost_cents_sonnet: float = 0.0
    cost_cents_opus: float = 0.0
    haiku_floor_used: float = DEFAULT_HAIKU_FLOOR
    sonnet_floor_used: float = DEFAULT_SONNET_FLOOR
    shadow_rate_used: float = DEFAULT_SHADOW_RATE
    shadow_tighten_events: int = 0


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------
def _base_url() -> str:
    return os.environ.get("SUPABASE_URL", SUPABASE_URL)


def _sb_get(path: str, params: dict | None = None) -> Any:
    url = f"{_base_url()}/rest/v1/{path}"
    resp = httpx.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _sb_post(path: str, body: dict | list) -> Any:
    url = f"{_base_url()}/rest/v1/{path}"
    resp = httpx.post(url, headers=_headers(), json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _sb_patch(path: str, params: dict, body: dict) -> Any:
    url = f"{_base_url()}/rest/v1/{path}"
    resp = httpx.patch(url, headers=_headers(), params=params, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _sb_rpc(func: str, args: dict) -> Any:
    url = f"{_base_url()}/rest/v1/rpc/{func}"
    resp = httpx.post(url, headers=_headers(), json=args, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Config from DB
# ---------------------------------------------------------------------------
def _load_config() -> dict[str, Any]:
    rows = _sb_get("certify_router_config")
    cfg: dict[str, Any] = {}
    for row in rows:
        cfg[row["key"]] = row["value_num"] if row["value_num"] is not None else row["value_text"]
    return cfg


# ---------------------------------------------------------------------------
# T0 — Deterministic gate
# ---------------------------------------------------------------------------
def _run_gate(county_slug: str) -> GateResult:
    """
    Calls pencil_dod_evaluate_county via Supabase RPC.
    Returns GateResult with pass_count and per-letter booleans.
    """
    rows = _sb_rpc("pencil_dod_evaluate_county_rows", {"county_slug_arg": county_slug})

    letters: dict[str, bool] = {}
    detail: dict[str, dict] = {}
    for row in rows:
        ltr = row["letter"]
        if ltr == "ERROR":
            return GateResult(
                pass_count=0,
                verdict="fail",
                letters={},
                detail={"ERROR": {"detail": row.get("detail", "unknown error")}},
            )
        letters[ltr] = bool(row["pass"])
        detail[ltr] = {"metric": row.get("metric"), "detail": row.get("detail")}

    pass_count = sum(1 for v in letters.values() if v)
    verdict = "pass" if pass_count == 10 else "fail"
    return GateResult(pass_count=pass_count, verdict=verdict, letters=letters, detail=detail)


# ---------------------------------------------------------------------------
# Screen prompt builder
# ---------------------------------------------------------------------------
_SCREEN_SYSTEM = """\
You are an anomaly-detection screen for a gold-standard certification gate.
Your ONLY job is to check whether the gate results contain data integrity anomalies.
You have NO certification authority — the gate is the sole authority.

Respond with STRICT JSON and nothing else:
{"verdict": "clean"|"escalate", "confidence": <0.0–1.0>, "reason": "<one sentence>"}

Escalate (not clean) if ANY of the following anomalies are present:
- B metric > 100% (denominator_integrity violation)
- pass_count=10 but critical letters B, I, or J are FALSE
- J metric >95% with deal_complete_count appearing to be 0
- H metric=0 hours (likely NULL coalesced to zero)
- All letters pass but total_closed appears to be 0
- C metric > D metric (impossible: clean is a subset of any)
- pass_count=10 but no adversarial_7d ultraloop audit evidence referenced
- Any percentage metric > 100
- Any metric that is logically contradictory

Return clean only if all metrics look coherent and no anomaly is present.
Default confidence=0.50 if genuinely uncertain. Never return confidence=1.0 for clean.
"""


def _screen_prompt(county_slug: str, gate: GateResult) -> str:
    lines = [f"County: {county_slug}", f"pass_count: {gate.pass_count}/10", "Letter results:"]
    for ltr in "ABCDEFGHIJ":
        passed = gate.letters.get(ltr, False)
        d = gate.detail.get(ltr, {})
        lines.append(f"  {ltr}: {'PASS' if passed else 'FAIL'} | metric={d.get('metric')} | {d.get('detail','')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM screen call
# ---------------------------------------------------------------------------
def _call_screen(model: str, county_slug: str, gate: GateResult) -> ScreenResult:
    client = anthropic.Anthropic()
    prompt = _screen_prompt(county_slug, gate)

    try:
        msg = client.messages.create(
            model=model,
            max_tokens=256,
            system=_SCREEN_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        tokens_in  = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
    except Exception as exc:
        log.warning("LLM screen call failed (%s): %s — treating as escalate", model, exc)
        return ScreenResult(
            verdict="escalate", confidence=0.0,
            reason=f"API error: {exc}", raw="",
            tokens_in=0, tokens_out=0, parse_ok=False,
        )

    return _parse_screen(raw, tokens_in, tokens_out)


def _parse_screen(raw: str, tokens_in: int, tokens_out: int) -> ScreenResult:
    """
    Strict JSON parse. Malformed → escalate (never clean).
    """
    try:
        # Strip markdown fences if present
        text = raw
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0].strip()

        data = json.loads(text)

        verdict = str(data["verdict"]).lower()
        if verdict not in ("clean", "escalate"):
            raise ValueError(f"invalid verdict: {verdict!r}")

        confidence = float(data["confidence"])
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"confidence out of range: {confidence}")

        reason = str(data["reason"])

        return ScreenResult(
            verdict=verdict, confidence=confidence, reason=reason,
            raw=raw, tokens_in=tokens_in, tokens_out=tokens_out, parse_ok=True,
        )
    except Exception as exc:
        log.warning("Screen parse failed (%s) — escalating: %s", exc, raw[:200])
        return ScreenResult(
            verdict="escalate", confidence=0.0,
            reason=f"parse_fail: {exc}", raw=raw,
            tokens_in=tokens_in, tokens_out=tokens_out, parse_ok=False,
        )


# ---------------------------------------------------------------------------
# T3 — Opus diagnosis
# ---------------------------------------------------------------------------
_OPUS_SYSTEM = """\
You are diagnosing why a gold-standard certification gate returned unexpected results.
Provide a clear, structured diagnosis:
1. Which letters failed and why (based on the metrics)
2. Most likely root cause (data gap vs pipeline bug vs schema issue)
3. Recommended fix (specific SQL or script action)
4. Risk level: LOW / MEDIUM / HIGH

Be specific. Reference exact metric values. Do not hallucinate data not shown.
"""


def _run_opus_review(county_slug: str, gate: GateResult, trigger_reason: str) -> tuple[str, int, int]:
    client = anthropic.Anthropic()
    prompt = (
        f"Trigger: {trigger_reason}\n\n"
        + _screen_prompt(county_slug, gate)
    )

    try:
        msg = client.messages.create(
            model=MODEL_OPUS,
            max_tokens=1024,
            system=_OPUS_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        diagnosis = msg.content[0].text.strip()
        return diagnosis, msg.usage.input_tokens, msg.usage.output_tokens
    except Exception as exc:
        log.error("Opus review failed for %s: %s", county_slug, exc)
        return f"Opus call failed: {exc}", 0, 0


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------
def _cents(model: str, tokens_in: int, tokens_out: int) -> float:
    in_rate, out_rate = COST_PER_M[model]
    usd = (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000
    return usd * 100  # cents


# ---------------------------------------------------------------------------
# Main route() function
# ---------------------------------------------------------------------------
def route(county_slug: str, run_id: str, cfg: dict) -> CertDecision:
    """
    Route a single county through the tiered verification stack.

    Gate FAIL → skip T1/T2, route to Opus, no cert (final_certify=False).
    Gate PASS + T1 clean+conf>=floor → certify under gate authority (final_tier='t1').
    Gate PASS + T1 escalate → T2.
    Gate PASS + T2 clean+conf>=floor → certify (final_tier='t2').
    Gate PASS + T2 escalate → T3 diagnosis (final_certify=False, final_tier='t3').
    """
    haiku_floor  = float(cfg.get("haiku_confidence_floor",  DEFAULT_HAIKU_FLOOR))
    sonnet_floor = float(cfg.get("sonnet_confidence_floor", DEFAULT_SONNET_FLOOR))
    min_tier     = str(cfg.get("min_tier", "haiku"))

    # T0 — deterministic gate
    gate = _run_gate(county_slug)
    log.info("[%s] gate=%s pass_count=%d/10", county_slug, gate.verdict, gate.pass_count)

    if gate.verdict == "fail":
        # Hard fail — go straight to Opus diagnosis, no cert possible
        diag, t3_in, t3_out = _run_opus_review(county_slug, gate, "gate_fail")
        return CertDecision(
            county_slug=county_slug, run_id=run_id,
            final_certify=False, final_tier="gate_fail",
            gate=gate,
            t3_invoked=True, t3_diagnosis=diag,
            t3_tokens_in=t3_in, t3_tokens_out=t3_out,
        )

    # Gate passed — run anomaly screens (unless min_tier forces sonnet start)
    t1: Optional[ScreenResult] = None
    t2: Optional[ScreenResult] = None

    if min_tier == "haiku":
        t1 = _call_screen(MODEL_HAIKU, county_slug, gate)
        log.info("[%s] t1_haiku verdict=%s conf=%.2f", county_slug, t1.verdict, t1.confidence)

        if t1.verdict == "clean" and t1.confidence >= haiku_floor:
            return CertDecision(
                county_slug=county_slug, run_id=run_id,
                final_certify=True, final_tier="t1",
                gate=gate, t1=t1,
            )

    # T2 — Sonnet (either because T1 escalated, or min_tier='sonnet')
    t2 = _call_screen(MODEL_SONNET, county_slug, gate)
    log.info("[%s] t2_sonnet verdict=%s conf=%.2f", county_slug, t2.verdict, t2.confidence)

    if t2.verdict == "clean" and t2.confidence >= sonnet_floor:
        return CertDecision(
            county_slug=county_slug, run_id=run_id,
            final_certify=True, final_tier="t2",
            gate=gate, t1=t1, t2=t2,
        )

    # T3 — Sonnet escalated → Opus diagnosis (gate passed but screen flagged anomaly)
    # final_certify = False (screen veto; do not certify until human/Opus review resolves)
    escalate_reason = (t2.reason if t2 else "") or "sonnet_escalation"
    diag, t3_in, t3_out = _run_opus_review(county_slug, gate, escalate_reason)
    log.info("[%s] t3_opus diagnosis (first 120c): %s", county_slug, diag[:120])

    return CertDecision(
        county_slug=county_slug, run_id=run_id,
        final_certify=False, final_tier="t3",
        gate=gate, t1=t1, t2=t2,
        t3_invoked=True, t3_diagnosis=diag,
        t3_tokens_in=t3_in, t3_tokens_out=t3_out,
    )


# ---------------------------------------------------------------------------
# Persist tier trail + run telemetry
# ---------------------------------------------------------------------------
def _persist_trail(dec: CertDecision) -> None:
    row: dict[str, Any] = {
        "county_slug":   dec.county_slug,
        "run_id":        dec.run_id,
        "gate_pass_count": dec.gate.pass_count if dec.gate else None,
        "gate_verdict":  dec.gate.verdict if dec.gate else "fail",
        "gate_letters":  dec.gate.letters if dec.gate else {},
        "gate_detail":   dec.gate.detail if dec.gate else {},
        "final_certify": dec.final_certify,
        "final_tier":    dec.final_tier,
        "authority":     "gate",
        "t3_invoked":    dec.t3_invoked,
        "t3_diagnosis":  dec.t3_diagnosis or None,
        "t3_tokens_in":  dec.t3_tokens_in or None,
        "t3_tokens_out": dec.t3_tokens_out or None,
    }
    if dec.t1:
        row.update({
            "t1_verdict":    dec.t1.verdict,
            "t1_confidence": dec.t1.confidence,
            "t1_reason":     dec.t1.reason,
            "t1_raw":        dec.t1.raw[:2000] if dec.t1.raw else None,
            "t1_tokens_in":  dec.t1.tokens_in,
            "t1_tokens_out": dec.t1.tokens_out,
        })
    if dec.t2:
        row.update({
            "t2_verdict":    dec.t2.verdict,
            "t2_confidence": dec.t2.confidence,
            "t2_reason":     dec.t2.reason,
            "t2_raw":        dec.t2.raw[:2000] if dec.t2.raw else None,
            "t2_tokens_in":  dec.t2.tokens_in,
            "t2_tokens_out": dec.t2.tokens_out,
        })
    _sb_post("certify_tier_trail", row)


def _persist_run(tel: RunTelemetry) -> None:
    tel.cost_cents_opus   = _cents(MODEL_OPUS,   tel.t3_tokens_total, 0)  # rough
    tel.cost_cents_haiku  = _cents(MODEL_HAIKU,  tel.t1_tokens_total, 0)
    tel.cost_cents_sonnet = _cents(MODEL_SONNET, tel.t2_tokens_total, 0)
    tel.cost_cents_total  = (
        tel.cost_cents_haiku + tel.cost_cents_sonnet + tel.cost_cents_opus
    )

    _sb_post("certify_router_run", {
        "run_id":               tel.run_id,
        "counties_total":       tel.counties_total,
        "counties_gate_fail":   tel.counties_gate_fail,
        "counties_t1_cert":     tel.counties_t1_cert,
        "counties_t2_cert":     tel.counties_t2_cert,
        "counties_t3_review":   tel.counties_t3_review,
        "t1_tokens_total":      tel.t1_tokens_total,
        "t2_tokens_total":      tel.t2_tokens_total,
        "t3_tokens_total":      tel.t3_tokens_total,
        "cost_cents_haiku":     tel.cost_cents_haiku,
        "cost_cents_sonnet":    tel.cost_cents_sonnet,
        "cost_cents_opus":      tel.cost_cents_opus,
        "cost_cents_total":     tel.cost_cents_total,
        "haiku_floor_used":     tel.haiku_floor_used,
        "sonnet_floor_used":    tel.sonnet_floor_used,
        "shadow_rate_used":     tel.shadow_rate_used,
        "shadow_tighten_events": tel.shadow_tighten_events,
        "trigger_source":       os.environ.get("TRIGGER_SOURCE", "manual"),
    })


# ---------------------------------------------------------------------------
# Shadow audit
# ---------------------------------------------------------------------------
def _shadow_audit_sample(trail_id: int, county_slug: str, run_id: str, gate: GateResult) -> bool:
    """
    Re-cert with Opus. Returns True if agreed, False on disagreement.
    On disagreement: triggers auto-tighten + Sentinel alert.
    """
    log.info("[shadow] auditing trail_id=%d county=%s", trail_id, county_slug)
    diag, t3_in, t3_out = _run_opus_review(county_slug, gate, "shadow_audit_sample")

    # Opus says CERTIFY if it finds no anomalies and explicitly says so
    opus_agrees = "no anomaly" in diag.lower() or "certify" in diag.lower()
    agreed = opus_agrees

    _sb_patch(
        "certify_tier_trail",
        {"id": f"eq.{trail_id}"},
        {
            "shadow_audited":      True,
            "shadow_audit_agreed": agreed,
            "shadow_audit_reason": diag[:500],
        },
    )

    if not agreed:
        log.warning("[shadow] DISAGREEMENT on trail_id=%d — triggering auto-tighten", trail_id)
        _sb_rpc("certify_shadow_tighten", {})
        # Sentinel alert
        try:
            _sb_post(SENTINEL_TABLE, {
                "alert_type":  "certify_shadow_disagreement",
                "county_slug": county_slug,
                "run_id":      run_id,
                "trail_id":    trail_id,
                "opus_diagnosis": diag[:1000],
            })
        except Exception as exc:
            log.error("Sentinel alert failed: %s", exc)

    return agreed


# ---------------------------------------------------------------------------
# Batch run over a list of counties
# ---------------------------------------------------------------------------
def run_batch(counties: list[str], run_id: str | None = None) -> list[CertDecision]:
    if run_id is None:
        run_id = str(uuid.uuid4())

    cfg = _load_config()
    shadow_rate = float(cfg.get("shadow_audit_rate", DEFAULT_SHADOW_RATE))

    tel = RunTelemetry(
        run_id=run_id,
        haiku_floor_used=float(cfg.get("haiku_confidence_floor", DEFAULT_HAIKU_FLOOR)),
        sonnet_floor_used=float(cfg.get("sonnet_confidence_floor", DEFAULT_SONNET_FLOOR)),
        shadow_rate_used=shadow_rate,
    )

    # Persist run record (we'll update it after)
    _sb_post("certify_router_run", {
        "run_id": run_id,
        "trigger_source": os.environ.get("TRIGGER_SOURCE", "manual"),
        "haiku_floor_used":   tel.haiku_floor_used,
        "sonnet_floor_used":  tel.sonnet_floor_used,
        "shadow_rate_used":   shadow_rate,
    })

    decisions: list[CertDecision] = []

    for county in counties:
        try:
            dec = route(county, run_id, cfg)
        except Exception as exc:
            log.error("route() failed for %s: %s", county, exc)
            continue

        # Accumulate telemetry
        tel.counties_total += 1
        if dec.final_tier == "gate_fail":
            tel.counties_gate_fail += 1
        elif dec.final_tier == "t1":
            tel.counties_t1_cert += 1
        elif dec.final_tier == "t2":
            tel.counties_t2_cert += 1
        elif dec.final_tier == "t3":
            tel.counties_t3_review += 1

        if dec.t1:
            tel.t1_tokens_total += dec.t1.tokens_in + dec.t1.tokens_out
        if dec.t2:
            tel.t2_tokens_total += dec.t2.tokens_in + dec.t2.tokens_out
        if dec.t3_invoked:
            tel.t3_tokens_total += dec.t3_tokens_in + dec.t3_tokens_out

        # Persist trail
        _persist_trail(dec)
        decisions.append(dec)

        # Shadow audit — cheap-path certs only (t1 or t2)
        if dec.final_certify and dec.final_tier in ("t1", "t2"):
            if random.random() < shadow_rate:
                try:
                    rows = _sb_get("certify_tier_trail", {
                        "run_id":      f"eq.{run_id}",
                        "county_slug": f"eq.{county}",
                        "select":      "id",
                        "limit":       "1",
                    })
                    if rows:
                        agreed = _shadow_audit_sample(rows[0]["id"], county, run_id, dec.gate)
                        if not agreed:
                            tel.shadow_tighten_events += 1
                            # Reload config after tighten
                            cfg = _load_config()
                            shadow_rate = float(cfg.get("shadow_audit_rate", shadow_rate))
                except Exception as exc:
                    log.error("Shadow audit failed for %s: %s", county, exc)

    # Final telemetry update
    _persist_run(tel)

    # Summary
    log.info(
        "[run=%s] total=%d gate_fail=%d t1=%d t2=%d t3=%d shadow_tighten=%d",
        run_id, tel.counties_total, tel.counties_gate_fail,
        tel.counties_t1_cert, tel.counties_t2_cert, tel.counties_t3_review,
        tel.shadow_tighten_events,
    )
    return decisions


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Certify Router")
    parser.add_argument("counties", nargs="+", help="county slugs to certify")
    parser.add_argument("--run-id", help="run ID (generated if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="run gate only, skip LLM screens and DB writes")
    args = parser.parse_args()

    if args.dry_run:
        cfg = {
            "haiku_confidence_floor": DEFAULT_HAIKU_FLOOR,
            "sonnet_confidence_floor": DEFAULT_SONNET_FLOOR,
            "shadow_audit_rate": DEFAULT_SHADOW_RATE,
            "min_tier": "haiku",
        }
        for county in args.counties:
            gate = _run_gate(county)
            print(json.dumps({
                "county": county,
                "pass_count": gate.pass_count,
                "verdict": gate.verdict,
                "letters": gate.letters,
            }, indent=2))
        sys.exit(0)

    decisions = run_batch(args.counties, run_id=args.run_id)
    for dec in decisions:
        status = "CERTIFIED" if dec.final_certify else "NOT_CERTIFIED"
        print(f"{dec.county_slug}: {status} via {dec.final_tier} (authority={dec.authority})")
