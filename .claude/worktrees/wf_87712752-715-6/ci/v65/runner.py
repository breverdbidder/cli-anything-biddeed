#!/usr/bin/env python3
"""
CI V6.5 Artillery Runner
========================

Subcommands:
  checkpoint        Write phase state to ci_v65_phases
  execute           Run the artillery for a given phase
                    Full impls: P1_RECON, P2_TECH_FOOTPRINT
                    Stubs:      P5_API_CAPTURE
  annotate-dispatch Mark the originating summit_chat_dispatch row as observed

Environment (all required):
  SUPABASE_URL                 e.g. https://mocerqjnksmhcjzxrewo.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    JWT (from GH Actions secrets — never inline)
  DOSSIER_ID                   uuid of ci_v65_dossiers row
  PHASE                        ci_v65_phase enum literal (P1_RECON, etc.)

Honesty Protocol V3 markers (V/U/I/A/UNK) emitted on every artillery finding.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


# ---------- env -------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DOSSIER_ID = os.environ.get("DOSSIER_ID", "")
PHASE = os.environ.get("PHASE", "P1_RECON")

if not SUPABASE_URL or not SERVICE_KEY:
    print("FATAL: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing from env", file=sys.stderr)
    sys.exit(2)

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

USER_AGENT = (
    "Mozilla/5.0 (compatible; BidDeedCI/6.5; +https://biddeed.ai/about)"
)

PER_REQUEST_TIMEOUT_S = 25.0
MAX_LINKS_PER_SIDE = 50

# P2 tuning
P2_PAGE_NAV_TIMEOUT_MS = 35000     # per-page navigation hard timeout
P2_SETTLE_AFTER_DCL_MS = 4500      # post-DOMContentLoaded JS settle window
P2_MAX_PAGES = 8                   # safety cap per dossier
P2_MAX_DISTINCT_HOSTS_LOG = 80     # cap on third-party hosts persisted in event payload