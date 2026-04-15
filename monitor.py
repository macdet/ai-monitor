import logging
from util.ollama_stats import get_ollama_data
from util.docker_stats import get_docker_stats
from util.gpu_stats import get_gpu_stats
from util.alerts import send_ntfy_alerts

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def monitor_system():
    alerts = []

    # 1. Ollama Check
    ollama = get_ollama_data()

    if ollama["status"] == "error":
        alerts.append(f"🔴 Ollama API Fehler: {ollama['message']}")
    else:
        for m in ollama["models"]:
            logger.info(
                f"Modell aktiv: {m['name']} ({m['processor']}) - Context: {m['context']}"
            )
            if "CPU" in m["processor"]:
                alerts.append(f"🟡 Warnung: {m['name']} läuft auf {m['processor']}!")

    # 2. Docker Check
    try:
        docker_stats = get_docker_stats()
        for c in docker_stats:
            if c["status"] != "running" or c["health"] == "unhealthy":
                alerts.append(
                    f"🔴 Container {c['name']} ist {c['status']} ({c['health']})"
                )
            # Behandle fehlende Container
            elif c["status"] == "missing":
                alerts.append(
                    f"🔴 Container {c['name']} ist nicht vorhanden (nicht gefunden)"
                )
    except Exception as e:
        alerts.append(f"⚠️ Docker Check fehlgeschlagen: {e}")

    # 3. GPU Check
    try:
        gpu = get_gpu_stats()
        # Logge die GPU-Statistiken
        if gpu["vram_total"] is not None:
            logger.info(
                f"GPU VRAM: {gpu['vram_used']:.2f} / {gpu['vram_total']:.2f} GB ({gpu['vram_ratio']:.1%})"
            )

            # Nur bei Überlastung (>95%) sende einen Alert
            if gpu["vram_ratio"] is not None and gpu["vram_ratio"] > 0.95:
                alerts.append(
                    f"🟡 Warnung: GPU VRAM-Verbrauch ist hoch: {gpu['vram_ratio']:.1%}"
                )
        else:
            logger.info("GPU VRAM: Daten nicht verfügbar")

    except Exception as e:
        alerts.append(f"⚠️ GPU Check fehlgeschlagen: {e}")

    # 4. Senden
    if alerts:
        logger.warning("Alerts gefunden, sende Benachrichtigungen")
        success = send_ntfy_alerts(alerts)
        if not success:
            logger.error("❌ Fehler beim Senden der Alerts an ntfy")
    else:
        logger.info("✅ Alles im grünen Bereich")


if __name__ == "__main__":
    monitor_system()
