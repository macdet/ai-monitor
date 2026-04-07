import logging
from util.ollama_stats import get_ollama_data
from util.docker_stats import get_docker_stats
from util.gpu_stats import get_gpu_stats
from util.alerts import send_ntfy_alerts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def monitor_system():
    alerts = []
    
    # 1. Ollama Check
    ollama = get_ollama_data()
    if ollama["status"] == "error":
        alerts.append(f"🔴 Ollama API Fehler: {ollama['message']}")
    else:
        for m in ollama["models"]:
            logger.info(f"Modell aktiv: {m['name']} ({m['processor']}) - Context: {m['context']}")
            if "CPU" in m["processor"]:
                alerts.append(f"🟡 Warnung: {m['name']} läuft auf {m['processor']}!")

    # 2. Docker Check
    try:
        for c in get_docker_stats():
            if c['status'] != 'running' or c['health'] == 'unhealthy':
                alerts.append(f"🔴 Container {c['name']} ist {c['status']} ({c['health']})")
    except Exception as e:
        alerts.append(f"⚠️ Docker Check fehlgeschlagen: {e}")

    # 3. GPU Check
    try:
        gpu = get_gpu_stats()
        # Hier loggen wir nur, Alerts kommen nur bei Überlastung (>95%)
        logger.info(f"GPU Last: {gpu}") 
    except Exception as e:
        alerts.append(f"⚠️ GPU Check fehlgeschlagen: {e}")

    # 4. Senden
    if alerts:
        send_ntfy_alerts(alerts)
    else:
        logger.info("✅ Alles im grünen Bereich")

if __name__ == "__main__":
    monitor_system()
