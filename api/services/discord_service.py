"""Discord notifications via incoming webhooks.

A webhook URL is the "destination" of a Discord alert config. If the given URL is
empty, runs in DRY-RUN (logs + reports success) so the flow is testable offline.
"""
import logging

import requests

logger = logging.getLogger(__name__)


def send_discord(webhook_url: str, content: str, username: str = "TCGWatch") -> tuple[bool, str]:
    """Post a message to a Discord webhook. Returns (ok, detail)."""
    if not webhook_url:
        logger.info("[discord dry-run] %s", content)
        return True, "dry-run (webhook absent — message journalisé)"

    try:
        resp = requests.post(
            webhook_url,
            json={"username": username, "content": content[:2000]},
            timeout=15,
        )
        # Discord returns 204 No Content on success.
        if resp.status_code in (200, 204):
            return True, "sent"
        return False, f"Discord HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        logger.error("Discord webhook failed: %s", exc)
        return False, f"erreur Discord: {exc}"
