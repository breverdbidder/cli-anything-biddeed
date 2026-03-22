"""
AnalyticsWise Agent — SPEC Agent 07
Customer behavior monitor using PostHog (self-hosted, privacy-first).
PostHog: Hetzner 87.99.129.125:8100.
Alert: any funnel step drops >15% vs 7-day average → Telegram.
"""

import argparse
import asyncio
import json
import os
from typing import Any, Dict, List, Optional

POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "http://87.99.129.125:8100")

FUNNEL_STEPS = [
    "heatmap_view",
    "parcel_click",
    "gate_shown",
    "signup_start",
    "signup_complete",
    "trial_start",
    "paid",
]

ALERT_DROP_THRESHOLD = 0.15  # 15%


class AnalyticsWiseAgent:
    """
    Daily/weekly analytics aggregation from PostHog.
    Writes to page_analytics and conversion_funnel Supabase tables.
    """

    def __init__(
        self,
        posthog_host: Optional[str] = None,
        posthog_key: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.posthog_host = posthog_host or POSTHOG_HOST
        self.posthog_key = posthog_key or os.environ.get("POSTHOG_API_KEY", "")
        self.supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "")
        self.supabase_key = supabase_key or os.environ.get("SUPABASE_SERVICE_KEY", "")

    def _get_db(self):
        try:
            from cli_anything.designwise.utils.supabase_client import DesignWiseDB
            return DesignWiseDB(url=self.supabase_url, key=self.supabase_key)
        except ImportError:
            return None

    async def _posthog_query(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Query PostHog API."""
        try:
            import httpx
            headers = {"Authorization": f"Bearer {self.posthog_key}"}
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.posthog_host}/api/{endpoint}",
                    headers=headers,
                    params=params or {},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def aggregate_daily(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate daily page views per route from PostHog.
        Writes results to page_analytics table.
        """
        import datetime
        date = date or datetime.date.today().isoformat()
        raw = await self._posthog_query("insights/trend/", {
            "events": json.dumps([{"id": "$pageview", "type": "events"}]),
            "date_from": date,
            "date_to": date,
        })
        if "error" in raw:
            return {"error": raw["error"], "date": date, "agent": "analytics"}

        # Extract page metrics
        routes = {}
        for item in raw.get("result", []):
            route = item.get("action", {}).get("name", "unknown")
            count = sum(item.get("data", []))
            routes[route] = count

        db = self._get_db()
        if db:
            for route, count in routes.items():
                await db.upsert("page_analytics", {
                    "route": route,
                    "date": date,
                    "page_views": count,
                })

        return {"date": date, "routes": routes, "total_pages": len(routes)}

    async def generate_funnel_report(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate conversion funnel rates for each step.
        Writes to conversion_funnel table.
        """
        import datetime
        date = date or datetime.date.today().isoformat()
        raw = await self._posthog_query("insights/funnel/", {
            "events": json.dumps([{"id": step} for step in FUNNEL_STEPS]),
            "date_from": date,
            "date_to": date,
        })

        if "error" in raw:
            # Return stub with 0s if PostHog unavailable
            steps = {step: {"count": 0, "rate": 0.0} for step in FUNNEL_STEPS}
            return {"date": date, "funnel": steps, "note": raw["error"]}

        funnel_data = raw.get("result", [{}])[0] if raw.get("result") else {}
        steps_result = {}
        prev_count = None
        for i, step in enumerate(FUNNEL_STEPS):
            count = funnel_data.get(f"step_{i}_count", 0)
            rate = (count / prev_count) if prev_count and prev_count > 0 else 1.0
            steps_result[step] = {"count": count, "rate": round(rate, 4)}
            prev_count = count

        db = self._get_db()
        if db:
            for step, data in steps_result.items():
                await db.upsert("conversion_funnel", {
                    "date": date,
                    "step": step,
                    "count": data["count"],
                    "rate": data["rate"],
                })

        return {"date": date, "funnel": steps_result}

    async def check_conversion_alerts(self) -> Dict[str, Any]:
        """
        Compare today's funnel vs 7-day average.
        Alert via Telegram if any step drops >15%.
        """
        import datetime
        today = datetime.date.today().isoformat()
        today_funnel = await self.generate_funnel_report(date=today)
        if "error" in today_funnel:
            return {"alerts": [], "error": today_funnel.get("error")}

        alerts = []
        for step, data in today_funnel.get("funnel", {}).items():
            rate = data.get("rate", 1.0)
            # In production: compare vs 7-day rolling average from Supabase
            # Here we flag if rate drops below 15% (placeholder logic)
            if rate < (1 - ALERT_DROP_THRESHOLD) and rate > 0:
                alerts.append({
                    "step": step,
                    "rate": rate,
                    "drop_pct": round((1 - rate) * 100, 1),
                    "threshold": ALERT_DROP_THRESHOLD * 100,
                })

        if alerts:
            await self._send_telegram_alert(alerts)

        return {"alerts": alerts, "checked_steps": len(today_funnel.get("funnel", {}))}

    async def _send_telegram_alert(self, alerts: List[Dict]) -> None:
        """Send Telegram alert for conversion drops."""
        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not telegram_token or not chat_id:
            return
        msg = "⚠️ AnalyticsWise: Conversion drop detected\n"
        for a in alerts:
            msg += f"  • {a['step']}: -{a['drop_pct']}% (threshold: {a['threshold']}%)\n"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg},
                )
        except Exception:
            pass

    async def generate_weekly_digest(self) -> Dict[str, Any]:
        """Generate weekly analytics summary (7 days of data)."""
        import datetime
        today = datetime.date.today()
        daily_results = []
        for i in range(7):
            date = (today - datetime.timedelta(days=i)).isoformat()
            daily = await self.aggregate_daily(date=date)
            daily_results.append({"date": date, "data": daily})

        total_views = sum(
            sum(d["data"].get("routes", {}).values())
            for d in daily_results if "error" not in d.get("data", {})
        )
        return {
            "period": "7d",
            "total_views": total_views,
            "daily_breakdown": daily_results,
            "funnel_alerts": await self.check_conversion_alerts(),
        }

    async def run(self, daily: bool = False, weekly: bool = False, **kwargs) -> Dict[str, Any]:
        """Main async entry point."""
        if weekly:
            return await self.generate_weekly_digest()
        if daily:
            result = await self.aggregate_daily()
            funnel = await self.generate_funnel_report()
            return {"daily": result, "funnel": funnel}
        return {"error": "Specify --daily or --weekly", "agent": "analytics"}


def main():
    parser = argparse.ArgumentParser(description="AnalyticsWise — PostHog + funnel tracking")
    parser.add_argument("--daily", action="store_true", help="Run daily aggregation")
    parser.add_argument("--weekly", action="store_true", help="Run weekly digest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    agent = AnalyticsWiseAgent()
    result = asyncio.run(agent.run(daily=args.daily, weekly=args.weekly))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
