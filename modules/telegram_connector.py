"""
modules/telegram_connector.py
Lightweight Telegram notifier for Claight agent.
No polling loop — just fire-and-forget notifications.

Setup:
  1. Message @BotFather on Telegram → /newbot → get token
  2. Start your bot → send it /start
  3. Get your chat_id:
     curl https://api.telegram.org/bot<TOKEN>/getUpdates
     → look for "chat":{"id": YOUR_CHAT_ID}
  4. Add to config.py:
     TELEGRAM_TOKEN   = "123456:ABC-your-token"
     TELEGRAM_CHAT_ID = "123456789"
"""

import requests
import threading
from datetime import datetime


class TelegramConnector:

    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = str(chat_id)
        self.base    = f"https://api.telegram.org/bot{token}"

    def send(self, text: str):
        """Fire-and-forget send — runs in background thread, never blocks agent."""
        def _send():
            try:
                requests.post(
                    f"{self.base}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
            except Exception as e:
                print(f"[telegram] send failed: {e}")
        threading.Thread(target=_send, daemon=True).start()

    # ── Notification helpers ──────────────────────────────────────────────────

    def notify_worker_start(self, task: str):
        self.send(f"🔧 <b>Working on:</b>\n{task}")

    def notify_todo_done(self, task: str, result: str, remaining: int):
        preview = result[:200] + "..." if len(result) > 200 else result
        self.send(
            f"✅ <b>Done:</b> {task}\n\n"
            f"<i>{preview}</i>\n\n"
            f"📋 {remaining} todo(s) remaining"
        )

    def notify_all_done(self, goal: str):
        self.send(
            f"🎉 <b>All done!</b>\n\n"
            f"Goal: {goal}\n"
            f"Finished: {datetime.now().strftime('%H:%M')}\n"
            f"Summary saved to data/summary.json"
        )

    def notify_error(self, error: str):
        self.send(f"❌ <b>Agent error:</b>\n<code>{error[:300]}</code>")


def create_telegram_connector(token: str, chat_id: str) -> TelegramConnector:
    return TelegramConnector(token, chat_id)