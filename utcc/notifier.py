"""
UTCC Notifier — Telegram notification helper.
"""

import os
from typing import Optional

import httpx


TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    """Send messages to a Telegram chat via bot API."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.bot_token = bot_token or os.environ.get("BIDDEED_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("BIDDEED_BOT_CHAT_ID", "")
        self.timeout = timeout

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to the configured chat.

        Returns True on success, False on any failure (never raises).
        """
        if not self.bot_token or not self.chat_id:
            print("[notifier] Telegram credentials not set — skipping")
            return False
        try:
            r = httpx.post(
                f"{TELEGRAM_API}/bot{self.bot_token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode},
                timeout=self.timeout,
            )
            return r.status_code == 200
        except Exception as exc:
            print(f"[notifier] Telegram send failed: {exc}")
            return False

    def task_started(self, task_id: str, task_type: str, platform: str) -> bool:
        return self.send(
            f"🚀 <b>UTCC Task Started</b>\n"
            f"ID: <code>{task_id}</code>\n"
            f"Type: {task_type} | Platform: {platform}"
        )

    def task_completed(
        self,
        task_id: str,
        run_url: str = "",
        summary: str = "",
    ) -> bool:
        msg = f"✅ <b>UTCC Task Done</b>\n<code>{task_id}</code>"
        if summary:
            msg += f"\n{summary[:300]}"
        if run_url:
            msg += f"\n<a href='{run_url}'>GHA Run</a>"
        return self.send(msg)

    def task_failed(self, task_id: str, error: str = "", run_url: str = "") -> bool:
        msg = f"❌ <b>UTCC Task Failed</b>\n<code>{task_id}</code>"
        if error:
            msg += f"\n{error[:300]}"
        if run_url:
            msg += f"\n<a href='{run_url}'>GHA Run</a>"
        return self.send(msg)

    def batch_summary(
        self,
        batch_id: str,
        total: int,
        succeeded: int,
        failed: int,
    ) -> bool:
        return self.send(
            f"📦 <b>UTCC Batch Complete</b>\n"
            f"Batch: <code>{batch_id}</code>\n"
            f"✅ {succeeded}/{total} succeeded | ❌ {failed} failed"
        )


# Module-level convenience
_default_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    global _default_notifier
    if _default_notifier is None:
        _default_notifier = TelegramNotifier()
    return _default_notifier


def notify(text: str) -> bool:
    return get_notifier().send(text)
