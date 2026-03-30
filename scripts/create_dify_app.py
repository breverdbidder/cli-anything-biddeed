#!/usr/bin/env python3
"""
create_dify_app.py — Create Dify zoning agent app via console API
Issue: breverdbidder/cli-anything-biddeed#108

Creates a Dify agent-chat app wired with 3 custom tools:
  - addressNormalize (POST /address_normalize)
  - parcelLookup     (POST /parcel_lookup)
  - zoningLookup     (POST /zoning_lookup)

Configures Claude Sonnet 4.6 as the LLM (falls back to Gemini Flash).
Prints DIFY_APP_ID and DIFY_API_KEY for Vercel env var configuration.

Usage:
    python scripts/create_dify_app.py
    DIFY_HOST=http://87.99.129.125:3100 DIFY_EMAIL=admin@zonewise.ai DIFY_PASSWORD=zonewise2026 python scripts/create_dify_app.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

DIFY_HOST = os.getenv("DIFY_HOST", "http://87.99.129.125:3100")
DIFY_EMAIL = os.getenv("DIFY_EMAIL", "admin@zonewise.ai")
DIFY_PASSWORD = os.getenv("DIFY_PASSWORD", "zonewise2026")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")  # Pre-existing console API key

CONSOLE_API = f"{DIFY_HOST}/console/api"

SCHEMA_PATH = Path(__file__).parent.parent / "tools" / "zonewise-agent" / "dify_tool.yaml"

SYSTEM_PROMPT = """You are ZoneWise, an expert Florida zoning assistant for real estate investors and property owners.

You help users understand zoning regulations for specific addresses in Florida counties (primarily Brevard County).

When a user asks about a property or address, follow this sequence:
1. Call addressNormalize to standardize the address format
2. Call parcelLookup with the normalized address to find parcel ID and zone code
3. Call zoningLookup with the zone code to get detailed regulations

Provide clear, actionable answers covering:
- Current zoning classification and its category (Residential, Commercial, Agricultural)
- Permitted uses and any conditional uses
- Development standards: setbacks, maximum height, maximum density
- Whether a specific proposed use would be allowed

Always cite the zone_code and county in your response.
If no parcel is found, ask for more address details (city, zip code, or county).
Never guess or fabricate zoning data — only report what the tools return."""


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def login(client: httpx.Client) -> str:
    """Authenticate with Dify console, return access token."""
    if DIFY_API_KEY:
        print(f"[auth] Using DIFY_API_KEY from env")
        return DIFY_API_KEY

    print(f"[auth] Logging in as {DIFY_EMAIL} ...")
    resp = client.post(
        f"{CONSOLE_API}/login",
        json={"email": DIFY_EMAIL, "password": DIFY_PASSWORD, "remember_me": True},
    )
    if resp.status_code != 200:
        print(f"[auth] Login failed {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)

    data = resp.json()
    # Dify returns token at data.access_token or data.data.access_token
    token = (
        data.get("data", {}).get("access_token")
        or data.get("access_token")
        or data.get("result", {}).get("access_token")
    )
    if not token:
        print(f"[auth] No access_token in response: {json.dumps(data)[:300]}")
        sys.exit(1)

    print(f"[auth] Login successful ✅")
    return token


def load_schema() -> str:
    if not SCHEMA_PATH.exists():
        print(f"[schema] ERROR: {SCHEMA_PATH} not found")
        sys.exit(1)
    return SCHEMA_PATH.read_text()


def register_tool_provider(client: httpx.Client, token: str, schema: str) -> str:
    """Register zonewise-agent as a custom API tool provider. Returns provider name."""
    h = _headers(token)

    # List existing providers to check if already registered
    resp = client.get(f"{CONSOLE_API}/workspaces/current/tool-providers", headers=h)
    if resp.status_code == 200:
        for p in resp.json().get("data", []):
            if p.get("name") == "zonewise-agent" or "zonewise" in (p.get("name") or ""):
                print(f"[tools] Tool provider 'zonewise-agent' already registered: {p.get('id')}")
                return "zonewise-agent"

    # Register new provider
    resp = client.post(
        f"{CONSOLE_API}/workspaces/current/tool-providers/api",
        headers=h,
        json={
            "name": "zonewise-agent",
            "schema": schema,
            "schema_type": "openapi",
            "privacy_policy": "",
            "custom_disclaimer": "ZoneWise zoning data tools — internal use",
        },
    )
    if resp.status_code not in (200, 201):
        print(f"[tools] Registration failed {resp.status_code}: {resp.text[:400]}")
        print("[tools] Continuing — tool provider may need manual registration in Dify console")
        print(f"[tools] Console URL: {DIFY_HOST} → Tools → Custom → Add API Tool")
        return "zonewise-agent"

    data = resp.json()
    pid = data.get("id") or data.get("data", {}).get("id", "zonewise-agent")
    print(f"[tools] Registered 'zonewise-agent' tool provider ✅  (id={pid})")
    return "zonewise-agent"


def find_or_create_app(client: httpx.Client, token: str) -> str:
    """Find existing ZoneWise Zoning Agent app or create it. Returns app_id."""
    h = _headers(token)

    # Search existing apps
    resp = client.get(
        f"{CONSOLE_API}/apps",
        headers=h,
        params={"page": 1, "limit": 50},
    )
    if resp.status_code == 200:
        for app in resp.json().get("data", []):
            if app.get("name") == "ZoneWise Zoning Agent":
                app_id = app.get("id")
                print(f"[app] Found existing app 'ZoneWise Zoning Agent': {app_id}")
                return app_id

    # Create new app
    resp = client.post(
        f"{CONSOLE_API}/apps",
        headers=h,
        json={
            "name": "ZoneWise Zoning Agent",
            "description": "FL county zoning lookup — address_normalize + parcel_lookup + zoning_lookup",
            "mode": "agent-chat",
            "icon": "🏠",
            "icon_background": "#1E3A5F",
        },
    )
    if resp.status_code not in (200, 201):
        print(f"[app] Create failed {resp.status_code}: {resp.text[:400]}")
        sys.exit(1)

    data = resp.json()
    app_id = data.get("id") or data.get("data", {}).get("id")
    print(f"[app] Created 'ZoneWise Zoning Agent': {app_id} ✅")
    return app_id


def configure_model(client: httpx.Client, token: str, app_id: str):
    """Configure app with system prompt, tools, and LLM."""
    h = _headers(token)

    config = {
        "pre_prompt": SYSTEM_PROMPT,
        "agent_mode": {
            "enabled": True,
            "strategy": "function_call",
            "tools": [
                {"type": "api", "provider_id": "zonewise-agent", "tool_name": "addressNormalize", "enabled": True},
                {"type": "api", "provider_id": "zonewise-agent", "tool_name": "parcelLookup", "enabled": True},
                {"type": "api", "provider_id": "zonewise-agent", "tool_name": "zoningLookup", "enabled": True},
            ],
        },
        "model": {
            "provider": "anthropic",
            "name": "claude-sonnet-4-6",
            "mode": "chat",
            "completion_params": {"temperature": 0.1, "max_tokens": 4096},
        },
        "opening_statement": (
            "Hello! I'm ZoneWise. Give me any Florida address and I'll look up its "
            "zoning classification, permitted uses, and development standards."
        ),
        "user_input_form": [],
        "more_like_this": {"enabled": False},
        "sensitive_word_avoidance": {"enabled": False},
    }

    resp = client.post(f"{CONSOLE_API}/apps/{app_id}/model-config", headers=h, json=config)
    if resp.status_code not in (200, 201):
        # Fallback: try Gemini Flash
        print(f"[config] Claude Sonnet failed ({resp.status_code}) — trying Gemini Flash fallback")
        config["model"] = {
            "provider": "google",
            "name": "gemini-1.5-flash",
            "mode": "chat",
            "completion_params": {"temperature": 0.1, "max_tokens": 4096},
        }
        resp2 = client.post(f"{CONSOLE_API}/apps/{app_id}/model-config", headers=h, json=config)
        if resp2.status_code not in (200, 201):
            print(f"[config] Both LLMs failed ({resp2.status_code}): {resp2.text[:300]}")
            print(f"[config] App created — configure LLM manually at {DIFY_HOST}/app/{app_id}")
            return

    print(f"[config] App model + tools configured ✅")


def get_or_create_api_key(client: httpx.Client, token: str, app_id: str) -> str:
    """Get or create an app API key for streaming integration."""
    h = _headers(token)

    resp = client.get(f"{CONSOLE_API}/apps/{app_id}/api-keys", headers=h)
    if resp.status_code == 200:
        keys = resp.json().get("data", [])
        if keys:
            api_key = keys[0].get("token", "")
            print(f"[key] Using existing API key: {api_key[:20]}...")
            return api_key

    resp = client.post(f"{CONSOLE_API}/apps/{app_id}/api-keys", headers=h)
    if resp.status_code in (200, 201):
        api_key = resp.json().get("data", {}).get("token", "")
        print(f"[key] Created API key: {api_key[:20]}... ✅")
        return api_key

    print(f"[key] Could not retrieve API key ({resp.status_code}) — generate manually in console")
    return ""


def main():
    print(f"[init] Dify host: {DIFY_HOST}")
    print(f"[init] Console:   {CONSOLE_API}")
    print()

    with httpx.Client(timeout=30.0) as client:
        token = login(client)
        schema = load_schema()

        provider_name = register_tool_provider(client, token, schema)
        app_id = find_or_create_app(client, token)
        configure_model(client, token, app_id)
        api_key = get_or_create_api_key(client, token, app_id)

    print()
    print("=" * 60)
    print("ZoneWise Dify Agent — Setup Complete")
    print("=" * 60)
    print(f"  App ID:        {app_id}")
    print(f"  API Key:       {api_key}")
    print(f"  Base URL:      {DIFY_HOST}/v1")
    print(f"  Chat endpoint: {DIFY_HOST}/v1/chat-messages")
    print(f"  Tool server:   http://87.99.129.125:8319")
    print(f"  Console:       {DIFY_HOST}/app/{app_id}")
    print()
    print("  Add to Vercel (zonewise-web):")
    print(f"    DIFY_APP_ID={app_id}")
    print(f"    DIFY_API_KEY={api_key}")
    print(f"    DIFY_BASE_URL={DIFY_HOST}/v1")
    print()


if __name__ == "__main__":
    main()
