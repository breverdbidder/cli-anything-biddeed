#!/usr/bin/env python3
"""
server.py — Dify Custom Tool HTTP Server: deployment-verifier
Issue: breverdbidder/cli-anything-biddeed#101

FastAPI service exposing verify_deployment + signal_detector + auto_repair
as an HTTP API that Dify can register as a custom tool.

Runs on Hetzner 87.99.129.125:8318
Dify registers it via tools/deployment-verifier/dify_tool.yaml (OpenAPI 3.0 schema)

Usage:
    uvicorn server:app --host 0.0.0.0 --port 8318
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add local module path so verify_deployment + signal_detector are importable
sys.path.insert(0, str(Path(__file__).parent))

from verify_deployment import DeploymentVerifier, VerifyResult, persist_result
from signal_detector import DeploymentSignalDetector

app = FastAPI(
    title="deployment-verifier",
    description=(
        "Dify Custom Tool — headless Chromium deployment verifier for ZoneWise.AI. "
        "Verifies URLs, detects failures, and triggers auto-repair workflows."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)


# ── Request / Response Models ─────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    url: str
    selectors: Optional[str] = None   # Comma-separated CSS selectors
    screenshot: bool = True
    persist: bool = True              # Write to Supabase deployment_checks

class SignalSummary(BaseModel):
    signal_type: str
    severity: str
    message: str
    evidence: str
    auto_repairable: bool

class VerifyResponse(BaseModel):
    url: str
    status: str                       # "pass" | "fail" | "error"
    http_code: int
    load_ms: float
    checks_passed: int
    checks_failed: int
    signals: list[SignalSummary]
    screenshot_path: Optional[str]
    errors: list[str]
    verified_at: str


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "deployment-verifier", "port": 8318}


# ── Main Verify Endpoint ──────────────────────────────────────────────────────

@app.post("/verify", response_model=VerifyResponse)
async def verify_url(req: VerifyRequest):
    """
    Verify a single deployment URL.

    Runs headless Chromium, checks HTTP status, load time, Next.js hydration,
    optional CSS selectors, captures screenshot. Returns structured result with
    failure signals detected.
    """
    selectors = [s.strip() for s in req.selectors.split(",")] if req.selectors else []

    verifier = DeploymentVerifier(
        selectors=selectors,
        screenshot=req.screenshot,
    )

    result: VerifyResult = await verifier.verify(req.url)

    if req.persist:
        await persist_result(result)

    # Detect signals
    detector = DeploymentSignalDetector()
    signals = detector.detect(result)

    passed = sum(1 for c in result.checks if c.passed)
    failed = sum(1 for c in result.checks if not c.passed)

    return VerifyResponse(
        url=result.url,
        status=result.status,
        http_code=result.http_code,
        load_ms=round(result.load_ms, 1),
        checks_passed=passed,
        checks_failed=failed,
        signals=[
            SignalSummary(
                signal_type=s.signal_type.value,
                severity=s.severity,
                message=s.message,
                evidence=s.evidence,
                auto_repairable=s.auto_repairable,
            )
            for s in signals
        ],
        screenshot_path=result.screenshot_path,
        errors=result.errors,
        verified_at=result.verified_at,
    )


@app.post("/verify/chat-v2")
async def verify_chat_v2():
    """
    Quick verify for zonewise.ai/chat-v2 with Thread selector.
    Pre-configured: checks #thread-container + .message-thread selectors.
    Returns pass/fail with screenshot.
    """
    req = VerifyRequest(
        url="https://zonewise.ai/chat-v2",
        selectors="#thread-container,.message-thread,[data-testid='thread']",
        screenshot=True,
        persist=True,
    )
    return await verify_url(req)


# ── Startup: verify Playwright + Chromium installed ───────────────────────────

@app.on_event("startup")
async def startup_check():
    try:
        from playwright.async_api import async_playwright  # noqa: F401
        print("[startup] Playwright available ✅")
    except ImportError:
        print("[startup] ⚠️  Playwright not installed — run: pip install playwright && playwright install chromium")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8318"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
