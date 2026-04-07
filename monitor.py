from __future__ import annotations

import logging
from typing import List, Dict

from util.ollama_stats import get_ollama_status

logger = logging.getLogger(__name__)


def check_ollama_status() -> List[str]:
    """
    Überprüft den Ollama-Status und gibt eine Liste von Warnungen zurück.

    Rückgabe:
      - alerts: Liste von Warnmeldungen
    """
    alerts: List[str] = []

    try:
        status = get_ollama_status()
        if status["status"] == "error":
            logger.error("Fehler beim Abrufen des Ollama-Status: %s", status["message"])
            alerts.append(f"Fehler beim Abrufen des Ollama-Status: {status['message']}")
        elif status["warning"]:
            logger.warning("Ein oder mehrere Modelle laufen nicht auf '100% GPU':")
            for model in status["models"]:
                if model["processor"] != "100% GPU":
                    alerts.append(f"Modell '{model['name']}' läuft auf {model['processor']}")
    except Exception as exc:
        logger.exception("Fehler beim Überprüfen des Ollama-Status: %s", exc)
        alerts.append(f"Fehler beim Überprüfen des Ollama-Status: {exc}")

    return alerts
