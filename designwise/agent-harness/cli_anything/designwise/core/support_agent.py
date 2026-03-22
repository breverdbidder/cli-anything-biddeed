"""
SupportWise Agent — SPEC Agent 08
Auto-classify and respond to customer issues.
Categories: ui_bug, feature_request, data_question, billing, general.
ui_bug → GitHub Issue. billing → Telegram (HITL). general → Claude Sonnet auto-response.
"""

import argparse
import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

CATEGORIES = ["ui_bug", "feature_request", "data_question", "billing", "general"]

CLASSIFICATION_RULES = {
    "billing": ["billing", "charge", "invoice", "payment", "refund", "subscription", "cancel", "price", "cost"],
    "ui_bug": ["broken", "bug", "crash", "error", "not working", "doesn't work", "blank", "slow", "freeze", "fail"],
    "feature_request": ["feature", "add", "would be nice", "suggestion", "request", "improve", "enhancement", "wish"],
    "data_question": ["data", "auction", "property", "case number", "county", "parcel", "bid", "forecast"],
}

AUTO_RESPONSES = {
    "ui_bug": "Thanks for reporting this bug! We've created a GitHub issue and our team is investigating. Expected ETA: 24-48 hours.",
    "feature_request": "Thanks for the suggestion! We've logged this to our backlog. Our team reviews feature requests weekly.",
    "data_question": "Thanks for your data question! Our ZoneWise chat agent is analyzing your request.",
    "billing": "Your billing inquiry has been escalated to our team. Expect a response within 4 business hours.",
    "general": "Thanks for reaching out! Our team will respond shortly.",
}


class SupportWiseAgent:
    """
    Auto-classify and respond to customer support tickets.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        github_token: Optional[str] = None,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ):
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_KEY", "")
        self.github_token = github_token or os.environ.get("GH_PAT", "")
        self.telegram_token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    def _get_db(self):
        try:
            from cli_anything.designwise.utils.supabase_client import DesignWiseDB
            return DesignWiseDB(url=self.supabase_url, key=self.supabase_key)
        except ImportError:
            return None

    def classify_ticket(self, message: str) -> Dict[str, Any]:
        """
        Classify support ticket message into a category.
        Returns {category: str, confidence: float, keywords: list}.
        """
        message_lower = message.lower()
        scores: Dict[str, int] = {cat: 0 for cat in CATEGORIES}

        for category, keywords in CLASSIFICATION_RULES.items():
            for kw in keywords:
                if kw in message_lower:
                    scores[category] += 1

        # Pick highest scoring category
        best_cat = max(scores, key=lambda c: scores[c])
        best_score = scores[best_cat]

        if best_score == 0:
            best_cat = "general"

        matched_kws = [kw for kw in CLASSIFICATION_RULES.get(best_cat, []) if kw in message_lower]
        confidence = min(1.0, best_score / 3.0) if best_score > 0 else 0.3

        return {
            "category": best_cat,
            "confidence": round(confidence, 2),
            "keywords": matched_kws,
            "message_preview": message[:100],
        }

    async def auto_respond(self, ticket_id: str) -> Dict[str, Any]:
        """
        Generate and send auto-response for a ticket.
        Returns the response message.
        """
        db = self._get_db()
        if not db:
            return {"error": "Supabase not configured"}
        tickets = await db.query("support_tickets", {"id": f"eq.{ticket_id}"})
        if not tickets or "error" in tickets:
            return {"error": f"Ticket {ticket_id} not found"}
        ticket = tickets[0] if isinstance(tickets, list) else tickets
        category = ticket.get("category", "general")
        response = AUTO_RESPONSES.get(category, AUTO_RESPONSES["general"])
        await db.update("support_tickets", {"id": ticket_id}, {
            "status": "responded",
            "auto_response": response,
        })
        return {"ticket_id": ticket_id, "category": category, "response": response}

    async def create_github_issue(self, ticket_id: str) -> Dict[str, Any]:
        """Create a GitHub issue for a ui_bug ticket."""
        if not self.github_token:
            return {"error": "GH_PAT not configured", "ticket_id": ticket_id}
        try:
            import httpx
            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
            }
            issue_body = {
                "title": f"[SupportWise] Bug Report — Ticket {ticket_id}",
                "body": f"Auto-generated from support ticket {ticket_id}\n\nNeeds triage.",
                "labels": ["bug", "support"],
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.github.com/repos/breverdbidder/biddeed-ai/issues",
                    headers=headers,
                    json=issue_body,
                )
                if resp.status_code == 201:
                    data = resp.json()
                    return {"issue_url": data["html_url"], "issue_number": data["number"], "ticket_id": ticket_id}
                return {"error": resp.text, "status": resp.status_code}
        except Exception as e:
            return {"error": str(e), "ticket_id": ticket_id}

    async def escalate_to_telegram(self, ticket_id: str) -> Dict[str, Any]:
        """Escalate billing ticket to Telegram (HITL required)."""
        if not self.telegram_token or not self.telegram_chat_id:
            return {"error": "Telegram not configured", "ticket_id": ticket_id}
        msg = f"🚨 SupportWise: BILLING escalation\nTicket: {ticket_id}\nRequires human review (HITL).\n"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                    json={"chat_id": self.telegram_chat_id, "text": msg},
                )
                return {"escalated": True, "ticket_id": ticket_id, "status": resp.status_code}
        except Exception as e:
            return {"error": str(e), "ticket_id": ticket_id}

    async def process_ticket(self, message: str) -> Dict[str, Any]:
        """Full pipeline: classify → log → respond/escalate."""
        classification = self.classify_ticket(message)
        category = classification["category"]

        db = self._get_db()
        ticket_id = f"ticket_{hash(message) % 100000}"
        if db:
            await db.insert("support_tickets", {
                "id": ticket_id,
                "message": message,
                "category": category,
                "status": "open",
                "confidence": classification["confidence"],
            })

        result = {
            "ticket_id": ticket_id,
            "category": category,
            "confidence": classification["confidence"],
            "auto_response": AUTO_RESPONSES.get(category, AUTO_RESPONSES["general"]),
        }

        if category == "ui_bug":
            gh_result = await self.create_github_issue(ticket_id)
            result["github_issue"] = gh_result
        elif category == "billing":
            escalation = await self.escalate_to_telegram(ticket_id)
            result["escalation"] = escalation

        return result

    async def run(self, ticket: Optional[str] = None, ticket_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Main async entry point."""
        if ticket:
            return await self.process_ticket(ticket)
        if ticket_id:
            return await self.auto_respond(ticket_id)
        return {"error": "Specify --ticket <message> or --ticket-id <id>", "agent": "support"}


def main():
    parser = argparse.ArgumentParser(description="SupportWise — Ticket classifier")
    parser.add_argument("--ticket", help="Support ticket message", default=None)
    parser.add_argument("--ticket-id", help="Ticket ID to respond to", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    agent = SupportWiseAgent()
    result = asyncio.run(agent.run(ticket=args.ticket, ticket_id=args.ticket_id))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
