from __future__ import annotations

import json
import logging
import os
from typing import Any, List

import requests

logger = logging.getLogger(__name__)

def build_alerts(stats: dict[str, Any]) -> list[str]:
    """Erzeugt Alert-Texte aus Docker- und Ollama-Statusdaten."""
    alerts: list[str] = []

    docker_stats = stats.get("docker", [])
    for container in docker_stats:
        if not isinstance(container, dict):
            continue

        name = container.get("name", "unknown")
        status = container.get("status", "unknown")
        health = container.get("health", "none")
        error = container.get("error")

        if error:
            alerts.append(f"⚠️ Docker {name}: Fehler bei Abfrage ({error})")
            continue

        if status != "running":
            alerts.append(f"⚠️ Docker {name}: Status ist {status}")

        if health == "unhealthy":
            alerts.append(f"⚠️ Docker {name}: Health ist unhealthy")

    ollama_stats = stats.get("ollama", {})
    running_models = (
        ollama_stats.get("running", []) if isinstance(ollama_stats, dict) else []
    )
    if not running_models:
        alerts.append("❌ Ollama: Kein Modell läuft aktuell (/api/ps ist leer)")

    return alerts


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
