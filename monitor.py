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
            alerts.append(f"❌ Fehler beim Abrufen des Ollama-Status: {status['message']}")
        else:
            # Ausgabe der Statusinformationen
            try:
                running_models = status.get("running_models", [])
                available_models = status.get("available_models", [])

                logger.info("Laufende Modelle:")
                for model in running_models:
                    logger.info(
                        f"Name: {model['name']}, Größe: {model['size']} GB, Prozessor: {model['processor']}, VRAM verwendet: {model['vram_used']} GB, Kontextlänge: {model['context_length']}"
                    )

                logger.info("Verfügbare Modelle:")
                for model in available_models:
                    logger.info(f"Name: {model['name']}, Größe: {model['size']} GB")
            except Exception as exc:
                logger.exception("Fehler beim Abrufen der Ollama-Statistiken: %s", exc)
                alerts.append(f"⚠️ Fehler beim Abrufen der Ollama-Statistiken: {exc}")

    except Exception as exc:
        logger.exception("Fehler beim Überprüfen des Ollama-Status: %s", exc)
        alerts.append(f"❌ Fehler beim Überprüfen des Ollama-Status: {exc}")

    return alerts
