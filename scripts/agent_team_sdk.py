#!/usr/bin/env python3
"""
Agent Team SDK — Event bus client for lead + teammate Claude sessions.

Every session on Hetzner running inside the Agent Teams architecture imports
this module to coordinate via Supabase. Supabase is the durable event bus;
CLAUDE.md is the read-only orientation doc.

Usage (inside a Claude session on Hetzner):

    from agent_team_sdk import AgentBus

    bus = AgentBus(run_id=<uuid>, agent="researcher")

    # Append an event
    bus.event("phase_started", phase=1)
    bus.event("checkpoint_green", phase=1, checkpoint_id="1.1",
              payload={"legal_name": "Algoma Inc.", "source": "ToS page"})

    # Send inbox message to another teammate
    bus.send("qa", "assignment", "Verify HQ claim",
             body="Researcher claims HQ=Mountain View CA. Please verify against Phase 2 captures.",
             related_checkpoint="1.2")

    # Read unread messages for me
    for msg in bus.inbox():
        print(msg)
        bus.mark_read(msg["id"])

    # Escalate a blocker to AI Architect
    bus.alert("block", "architect",
              title="HQ contradiction",
              body="Phase 1 says MV CA, Phase 2 capture says Brooklyn NY",
              recommended_action="Architect to pick canonical value")

Environment:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone


SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SRK = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

VALID_AGENTS = {"lead", "researcher", "playwright", "writer", "qa", "architect", "system"}
VALID_MSG_TYPES = {"assignment", "question", "finding", "conflict", "ack", "handoff"}
VALID_SEVERITIES = {"info", "warn", "block", "critical"}
VALID_AUDIENCES = {"architect", "ariel", "both"}


class AgentBusError(Exception):
    pass


def _headers():
    if not SRK:
        raise AgentBusError("SUPABASE_SERVICE_ROLE_KEY env var not set")
    return {
        "apikey": SRK,
        "Authorization": f"Bearer {SRK}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _request(method, path, body=None, extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = _headers()
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = r.read()
            return json.loads(resp) if resp else None
    except urllib.error.HTTPError as e:
        detail = e.read()[:500].decode("utf-8", errors="replace")
        raise AgentBusError(f"HTTP {e.code} on {method} {path}: {detail}")


# ============================================================
# Run-level helpers (called once per session, usually by lead)
# ============================================================

def create_run(summit_issue, competitor_slug, teammate_models=None, spawn_prompt_path=None):
    """Create a new agent_team_runs row. Returns run_id."""
    body = {
        "summit_issue": summit_issue,
        "competitor_slug": competitor_slug,
        "status": "queued",
        "teammate_models": teammate_models or {},
        "spawn_prompt_path": spawn_prompt_path,
    }
    rows = _request("POST", "agent_team_runs", body)
    if not rows:
        raise AgentBusError("create_run returned empty")
    return rows[0]["id"]


def get_run(run_id):
    rows = _request("GET", f"agent_team_runs?id=eq.{run_id}&select=*")
    return rows[0] if rows else None


def update_run(run_id, **fields):
    return _request("PATCH", f"agent_team_runs?id=eq.{run_id}",
                    body=fields,
                    extra_headers={"Prefer": "return=minimal"})


def find_active_run(summit_issue=None, competitor_slug=None):
    """Find the most recent running/queued run for a given issue or slug."""
    filters = ["status=in.(queued,running,blocked)"]
    if summit_issue is not None:
        filters.append(f"summit_issue=eq.{summit_issue}")
    if competitor_slug:
        filters.append(f"competitor_slug=eq.{competitor_slug}")
    q = "&".join(filters) + "&order=created_at.desc&limit=1"
    rows = _request("GET", f"agent_team_runs?{q}&select=*")
    return rows[0] if rows else None


# ============================================================
# AgentBus: per-agent instance for reading/writing the bus
# ============================================================

class AgentBus:
    def __init__(self, run_id, agent):
        if agent not in VALID_AGENTS:
            raise AgentBusError(f"agent must be one of {VALID_AGENTS}, got {agent}")
        self.run_id = run_id
        self.agent = agent

    # ---- Event log (append-only) ----

    def event(self, event_type, phase=None, checkpoint_id=None, payload=None):
        """Append an event to the run's event log."""
        body = {
            "run_id": self.run_id,
            "teammate": self.agent,
            "event_type": event_type,
            "phase": phase,
            "checkpoint_id": checkpoint_id,
            "payload": payload or {},
        }
        return _request("POST", "agent_team_events", body,
                        extra_headers={"Prefer": "return=minimal"})

    def events(self, since=None, limit=50, teammate=None, event_type=None):
        """Read events from this run. `since` is ISO timestamp or None for all."""
        filters = [f"run_id=eq.{self.run_id}"]
        if since:
            filters.append(f"created_at=gt.{since}")
        if teammate:
            filters.append(f"teammate=eq.{teammate}")
        if event_type:
            filters.append(f"event_type=eq.{event_type}")
        q = "&".join(filters) + f"&order=created_at.desc&limit={limit}"
        return _request("GET", f"agent_team_events?{q}&select=*") or []

    # ---- Inbox (peer-to-peer messages) ----

    def send(self, to_agent, message_type, subject, body, related_checkpoint=None, priority="normal"):
        """Send a message to another teammate (or 'all')."""
        if message_type not in VALID_MSG_TYPES:
            raise AgentBusError(f"message_type must be in {VALID_MSG_TYPES}")
        return _request("POST", "agent_team_inbox", {
            "run_id": self.run_id,
            "from_agent": self.agent,
            "to_agent": to_agent,
            "message_type": message_type,
            "subject": subject,
            "body": body,
            "related_checkpoint": related_checkpoint,
            "priority": priority,
        }, extra_headers={"Prefer": "return=minimal"})

    def inbox(self, unread_only=True, limit=20):
        """Read messages addressed to me (or 'all')."""
        filters = [
            f"run_id=eq.{self.run_id}",
            f"or=(to_agent.eq.{self.agent},to_agent.eq.all)",
        ]
        if unread_only:
            filters.append("read_at=is.null")
        q = "&".join(filters) + f"&order=created_at.asc&limit={limit}"
        return _request("GET", f"agent_team_inbox?{q}&select=*") or []

    def mark_read(self, message_id):
        return _request("PATCH", f"agent_team_inbox?id=eq.{message_id}",
                        body={"read_at": datetime.now(timezone.utc).isoformat()},
                        extra_headers={"Prefer": "return=minimal"})

    def ack(self, message_id, ack_body=None):
        """Mark read AND send an ack back to the original sender."""
        # Fetch original
        rows = _request("GET", f"agent_team_inbox?id=eq.{message_id}&select=from_agent,subject")
        if not rows:
            raise AgentBusError(f"message {message_id} not found")
        original = rows[0]
        self.mark_read(message_id)
        self.send(
            to_agent=original["from_agent"],
            message_type="ack",
            subject=f"ACK: {original['subject']}",
            body=ack_body or "Acknowledged",
        )

    # ---- Alerts (escalation to architect/Ariel) ----

    def alert(self, severity, audience, title, body, recommended_action=None):
        if severity not in VALID_SEVERITIES:
            raise AgentBusError(f"severity must be in {VALID_SEVERITIES}")
        if audience not in VALID_AUDIENCES:
            raise AgentBusError(f"audience must be in {VALID_AUDIENCES}")

        # Fetch run to get competitor_slug
        run = get_run(self.run_id)
        slug = run.get("competitor_slug") if run else None

        row = _request("POST", "agent_team_alerts", {
            "run_id": self.run_id,
            "competitor_slug": slug,
            "severity": severity,
            "audience": audience,
            "title": title,
            "body": body,
            "recommended_action": recommended_action,
        })

        # If urgent audience includes Ariel, also fire Telegram
        if severity in ("block", "critical") and audience in ("ariel", "both"):
            self._send_telegram(title, body, severity)

        return row

    def _send_telegram(self, title, body, severity):
        """Best-effort Telegram fire. Non-fatal if token missing."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not (token and chat_id):
            return
        icon = "🚨" if severity == "critical" else "⛔"
        msg = f"{icon} *{title}*\n\n{body[:500]}\n\nAgent: `{self.agent}`\nRun: `{self.run_id[:8]}`"
        try:
            import urllib.parse
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "Markdown",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
            )
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            # Non-fatal; the alert row is already written
            pass


# ============================================================
# Architect helpers (for me in claude.ai to check state)
# ============================================================

def unacknowledged_alerts(audience="architect", limit=20):
    """Fetch alerts waiting for architect action."""
    audiences = audience
    if audience == "architect":
        audiences = "architect,both"  # architect sees 'both' too
    q = f"audience=in.({audiences})&acknowledged_at=is.null&order=created_at.asc&limit={limit}"
    return _request("GET", f"agent_team_alerts?{q}&select=*") or []


def recent_events(run_id=None, limit=20):
    """Fetch recent events across all runs or for one run."""
    filters = ["order=created_at.desc", f"limit={limit}"]
    if run_id:
        filters.insert(0, f"run_id=eq.{run_id}")
    return _request("GET", f"agent_team_events?{'&'.join(filters)}&select=*") or []


def acknowledge_alert(alert_id, resolution, acknowledged_by="architect"):
    return _request("PATCH", f"agent_team_alerts?id=eq.{alert_id}", body={
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_by": acknowledged_by,
        "resolution": resolution,
    }, extra_headers={"Prefer": "return=minimal"})


# ============================================================
# CLI entry (for shell scripts + smoke tests)
# ============================================================

def _cli():
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    c1 = sub.add_parser("create-run")
    c1.add_argument("--issue", type=int, required=True)
    c1.add_argument("--slug", required=True)

    c2 = sub.add_parser("event")
    c2.add_argument("--run-id", required=True)
    c2.add_argument("--agent", required=True)
    c2.add_argument("--type", required=True)
    c2.add_argument("--phase", type=int)
    c2.add_argument("--checkpoint")
    c2.add_argument("--payload", default="{}")

    c3 = sub.add_parser("send")
    c3.add_argument("--run-id", required=True)
    c3.add_argument("--from", dest="from_agent", required=True)
    c3.add_argument("--to", required=True)
    c3.add_argument("--type", required=True)
    c3.add_argument("--subject", required=True)
    c3.add_argument("--body", required=True)

    c4 = sub.add_parser("inbox")
    c4.add_argument("--run-id", required=True)
    c4.add_argument("--agent", required=True)

    c5 = sub.add_parser("alert")
    c5.add_argument("--run-id", required=True)
    c5.add_argument("--agent", required=True)
    c5.add_argument("--severity", required=True)
    c5.add_argument("--audience", required=True)
    c5.add_argument("--title", required=True)
    c5.add_argument("--body", required=True)

    c6 = sub.add_parser("alerts")
    c6.add_argument("--audience", default="architect")

    c7 = sub.add_parser("events")
    c7.add_argument("--run-id", required=True)
    c7.add_argument("--limit", type=int, default=20)

    args = p.parse_args()

    if args.cmd == "create-run":
        run_id = create_run(args.issue, args.slug)
        print(run_id)
    elif args.cmd == "event":
        bus = AgentBus(args.run_id, args.agent)
        bus.event(args.type, phase=args.phase, checkpoint_id=args.checkpoint,
                  payload=json.loads(args.payload))
        print("ok")
    elif args.cmd == "send":
        bus = AgentBus(args.run_id, args.from_agent)
        bus.send(args.to, args.type, args.subject, args.body)
        print("ok")
    elif args.cmd == "inbox":
        bus = AgentBus(args.run_id, args.agent)
        for m in bus.inbox():
            print(json.dumps(m))
    elif args.cmd == "alert":
        bus = AgentBus(args.run_id, args.agent)
        bus.alert(args.severity, args.audience, args.title, args.body)
        print("ok")
    elif args.cmd == "alerts":
        for a in unacknowledged_alerts(args.audience):
            print(json.dumps(a))
    elif args.cmd == "events":
        for e in recent_events(args.run_id, args.limit):
            print(json.dumps(e))


if __name__ == "__main__":
    _cli()
