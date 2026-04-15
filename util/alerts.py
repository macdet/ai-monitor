from __future__ import annotations

import logging
import os
from typing import List

import requests

logger = logging.getLogger(__name__)


def send_ntfy_alerts(alerts: list[str]) -> bool:
    """
    Sendet Alerts an ntfy.

    Konfiguration via ENV:
      - NTFY_URL (Default: http://192.168.178.183:7777)
      - NTFY_TOPIC (Default: ai-monitor)
      - NTFY_USER (optional)
      - NTFY_PASSWORD (optional)
      - NTFY_TOKEN (optional, alternativ zu User/Pass)
    """
    if not alerts:
        return True

    ntfy_url = os.getenv("NTFY_URL", "http://192.168.178.183:7777").rstrip("/")
    ntfy_topic = os.getenv("NTFY_TOPIC", "ai-monitor").strip() or "ai-monitor"
    ntfy_user = os.getenv("NTFY_USER")
    ntfy_password = os.getenv("NTFY_PASSWORD")
    ntfy_token = os.getenv("NTFY_TOKEN")

    endpoint = f"{ntfy_url}/{ntfy_topic}"
    body = "\n".join(f"- {line}" for line in alerts)
    message = f"AI-Monitor Alerts ({len(alerts)}):\n{body}"

    headers = {
        "Title": "AI-Monitor Alert",
        "Priority": "high",
        "Tags": "warning,rotating_light",
    }
    auth = (ntfy_user, ntfy_password) if ntfy_user and ntfy_password else None
    if ntfy_token:
        headers["Authorization"] = f"Bearer {ntfy_token}"

    try:
        response = requests.post(
            endpoint,
            data=message.encode("utf-8"),
            headers=headers,
            auth=auth,
            timeout=5,
        )
        response.raise_for_status()
        logger.info("ntfy Alert gesendet: %s", endpoint)
        return True
    except requests.RequestException as exc:
        logger.exception("ntfy Versand fehlgeschlagen: %s", exc)
        return False
