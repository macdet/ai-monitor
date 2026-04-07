from __future__ import annotations

import logging
from typing import List, Dict, Any

from util.ollama_stats import get_ollama_status
from util.docker_stats import get_docker_stats
from util.gpu_stats import get_gpu_stats
from util.alerts import build_alerts, send_ntfy_alerts

logger = logging.getLogger(__name__)


def monitor_system() -> None:
    """
    Hauptfunktion zur Überwachung des Systems.
    Ruft alle Statistik-Module auf und sendet Warnungen.
    """
    alerts: List[str] = []

    # Ollama-Status abrufen
    try:
        ollama_status = get_ollama_status()
        if ollama_status["status"] == "error":
            logger.error("Fehler beim Abrufen des Ollama-Status: %s", ollama_status["message"])
            alerts.append(f"❌ Fehler beim Abrufen des Ollama-Status: {ollama_status['message']}")
        else:
            # Ausgabe der Statusinformationen
            try:
                running_models = ollama_status.get("running_models", [])
                available_models = ollama_status.get("available_models", [])

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

    # Docker-Status abrufen
    try:
        docker_stats = get_docker_stats()
        logger.info("Docker-Container-Status:")
        for container in docker_stats:
            logger.info(
                f"Name: {container['name']}, Status: {container['status']}, "
                f"Gesundheit: {container['health']}, Neustarts: {container['restart_count']}"
            )
    except Exception as exc:
        logger.exception("Fehler beim Abrufen des Docker-Status: %s", exc)
        alerts.append(f"⚠️ Fehler beim Abrufen des Docker-Status: {exc}")

    # GPU-Status abrufen
    try:
        gpu_stats = get_gpu_stats()
        if isinstance(gpu_stats, dict):
            logger.info("GPU-Status:")
            for gpu_id, stats in gpu_stats.items():
                logger.info(f"GPU {gpu_id}: VRAM gesamt: {stats['vram_total']} GB, "
                            f"VRAM verwendet: {stats['vram_used']} GB, "
                            f"VRAM Ratio: {stats['vram_ratio']:.2f}")
        elif isinstance(gpu_stats, float):
            # Wenn nur ein Float zurückgegeben wird (z.B. Gesamtverbrauch)
            logger.info(f"GPU-VRAM-Verbrauch: {gpu_stats:.2f} GB")
        else:
            logger.warning("GPU-Statistiken haben falsches Format: %s", gpu_stats)
            alerts.append(f"⚠️ GPU-Statistiken haben falsches Format: {gpu_stats}")
    except Exception as exc:
        logger.exception("Fehler beim Abrufen des GPU-Status: %s", exc)
        alerts.append(f"⚠️ Fehler beim Abrufen des GPU-Status: {exc}")

    # Warnungen senden
    if alerts:
        logger.warning("Es wurden Warnungen gefunden:")
        for alert in alerts:
            logger.warning(alert)
        send_ntfy_alerts(alerts)
    else:
        logger.info("✅ Alle Systeme sind in Ordnung")


if __name__ == "__main__":
    monitor_system()
