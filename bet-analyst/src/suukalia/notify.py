"""Notifications Telegram (optionnel, echec silencieux par conception)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


def send_telegram(token: str, chat_id: str, message: str, timeout: float = 10.0) -> bool:
    """Envoie un message. Retourne False en cas d'echec, sans lever d'exception.

    Une notification ratee ne doit jamais faire echouer un run : les paris ont
    deja ete calcules et enregistres, et le cron ne doit pas rejouer le cycle.
    """
    if not token or not chat_id:
        return False
    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": message, "disable_web_page_preview": "true"}
    ).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=payload
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return bool(json.loads(response.read().decode("utf-8")).get("ok"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return False
