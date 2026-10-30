"""Send an issue's status to Telegram as one message that is edited as the status changes.

Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (comma-separated for several chats). Without them, nothing is sent.
"""

import html
import json
import logging
import os
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.host.progress import IssueProgress

logger = logging.getLogger(__name__)

MAX_LENGTH = 4096
QUOTE_LENGTH = 3000
WORKING_MESSAGE = "🛠 <b>AGENT IS FIXING...</b>"


class TelegramStatus:
    def __init__(self, issue: dict):
        self.issue = issue
        self.sent_message = notify(self._create_message(WORKING_MESSAGE))

    def progress(self, progress: "IssueProgress") -> None:
        """Show the agent's steps as a tree with their state and timing."""
        lines = [WORKING_MESSAGE]

        for i, s in enumerate(progress.steps):
            branch = "└" if i == len(progress.steps) - 1 else "├"
            label = html.escape(s.label[:1].upper() + s.label[1:], quote=False)

            if s.duration is None:
                icon, detail = "⏳", f"since {s.started_at:%H:%M}"
            else:
                icon, detail = "❌" if s.failed else "✅", f"{s.duration:.1f}s"

            lines.append(f"\u2003{branch} {icon} {label} · <i>{detail}</i>")

        self._show_status("\n".join(lines))

    def failed(self, error: Exception) -> None:
        self._show_status(f"❌ <b>RUN FAILED</b>\n{quote(str(error))}")

    def fixed(self, pr_url: str) -> None:
        self._show_status(f'✅ <b>FIXED</b>\n🔗 <a href="{html.escape(pr_url)}">View pull request</a>')

    def not_fixed(self, summary: str | None) -> None:
        self._show_status(f"➖ <b>NOT FIXED</b>\n{quote(summary or 'The agent made no changes.')}")

    def _show_status(self, status: str) -> None:
        self.sent_message = replace_message(self.sent_message, self._create_message(status))

    def _create_message(self, status: str) -> str:
        """Build the message: issue id, title, then `status`."""
        return (
            f"🐞 <code>{html.escape(self.issue['shortId'], quote=False)}</code>\n"
            f"📝 {html.escape(self.issue['title'], quote=False)}\n\n"
            f"{status}"
        )


def quote(text: str) -> str:
    """Wrap `text` in a collapsed blockquote, escaped and shortened."""
    return f"<blockquote expandable>{html.escape(_truncate(text, QUOTE_LENGTH), quote=False)}</blockquote>"


def notify(text: str) -> dict[str, int]:
    """Send `text` (Telegram HTML) to each chat and return the message id per chat. Never raises."""
    return replace_message({}, text)


def replace_message(sent: dict[str, int], text: str) -> dict[str, int]:
    """Edit the `sent` messages to `text`, or send a new one where editing fails. Returns the message id per chat."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids = [chat_id for chat_id in map(str.strip, os.environ.get("TELEGRAM_CHAT_ID", "").split(",")) if chat_id]

    if not token or not chat_ids:
        return {}

    text = _truncate(text, MAX_LENGTH)
    message_ids = {}

    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }

        if chat_id in sent and _call(token, "editMessageText", payload | {"message_id": sent[chat_id]}):
            message_ids[chat_id] = sent[chat_id]
        elif result := _call(token, "sendMessage", payload):
            message_ids[chat_id] = result["message_id"]
    return message_ids


def _truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[: length - 1] + "…"


def _call(token: str, method: str, payload: dict) -> dict | None:
    """Call a Bot API method. Returns its result, or None on failure."""

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)["result"]
    except Exception:
        logger.warning("telegram %s to chat %s failed", method, payload["chat_id"], exc_info=True)
        return None
