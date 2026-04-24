from __future__ import annotations

import logging
import os
import time
from typing import Any

from util.alerts import send_ntfy_alerts
from util.docker_stats import get_docker_stats
from util.gpu_stats import get_gpu_stats
from util.ollama_control import unload_current_ollama_model
from util.ollama_stats import get_ollama_data
from util.thermal_policy import ThermalPolicy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = int(os.getenv("AI_MONITOR_POLL_INTERVAL", "15"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

thermal_policy = ThermalPolicy(
    warn_temp_c=85.0,
    critical_temp_c=90.0,
    recover_temp_c=80.0,
    critical_hits_needed=3,
)

_last_thermal_state: str | None = None


def monitor_system() -> dict[str, Any]:
    global _last_thermal_state

    alerts: list[str] = []
    payload: dict[str, Any] = {
        "ollama": None,
        "docker": None,
        "gpu": None,
        "thermal": None,
        "actions": {
            "model_unloaded": False,
            "unloaded_model": None,
        },
    }

    # 1. Ollama Check
    ollama = get_ollama_data()
    payload["ollama"] = ollama

    if ollama["status"] == "error":
        alerts.append(f"🔴 Ollama API Fehler: {ollama['message']}")
    else:
        for m in ollama["models"]:
            logger.info(
                "Modell aktiv: %s (%s) - Context: %s",
                m["name"],
                m["processor"],
                m["context"],
            )
            if "CPU" in m["processor"]:
                alerts.append(f"🟡 Warnung: {m['name']} läuft auf {m['processor']}!")

    # 2. Docker Check
    try:
        docker_stats = get_docker_stats()
        payload["docker"] = docker_stats

        for c in docker_stats:
            if c["status"] == "missing":
                alerts.append(
                    f"🔴 Container {c['name']} ist nicht vorhanden (nicht gefunden)"
                )
            elif c["status"] != "running" or c["health"] == "unhealthy":
                alerts.append(
                    f"🔴 Container {c['name']} ist {c['status']} ({c['health']})"
                )
    except Exception as exc:
        alerts.append(f"⚠️ Docker Check fehlgeschlagen: {exc}")

    # 3. GPU + Thermal Check
    try:
        gpu = get_gpu_stats()
        payload["gpu"] = gpu

        if gpu["vram_total"] is not None:
            logger.info(
                "GPU VRAM: %.2f / %.2f GB (%.1f%%)",
                gpu["vram_used"],
                gpu["vram_total"],
                (gpu["vram_ratio"] or 0) * 100,
            )
        else:
            logger.info("GPU VRAM: Daten nicht verfügbar")

        logger.info(
            "GPU Temp edge=%s hotspot=%s use=%s power=%s",
            gpu.get("temperature_edge"),
            gpu.get("temperature_hotspot"),
            gpu.get("gpu_use"),
            gpu.get("power_w"),
        )

        decision = thermal_policy.evaluate(gpu)
        payload["thermal"] = {
            "state": decision.state,
            "temperature_c": decision.temperature_c,
            "reason": decision.reason,
            "should_warn": decision.should_warn,
            "should_unload": decision.should_unload,
        }

        if decision.state != _last_thermal_state:
            logger.info(
                "Thermal state changed: %s -> %s",
                _last_thermal_state,
                decision.state,
            )
            _last_thermal_state = decision.state

            if decision.reason:
                alerts.append(f"🌡️ {decision.reason}")

        # VRAM-Warnung bleibt zusätzlich sinnvoll
        if gpu["vram_ratio"] is not None and gpu["vram_ratio"] > 0.95:
            alerts.append(
                f"🟡 Warnung: GPU VRAM-Verbrauch ist hoch: {gpu['vram_ratio']:.1%}"
            )

        # Nur bei anhaltend kritischer Temperatur eingreifen
        if decision.should_unload:
            ok, model = unload_current_ollama_model(ollama_url=OLLAMA_URL)
            payload["actions"]["model_unloaded"] = ok
            payload["actions"]["unloaded_model"] = model

            if ok and model:
                msg = f"🔴 Ollama-Modell wegen kritischer GPU-Temperatur entladen: {model}"
                logger.error(msg)
                alerts.append(msg)
            else:
                msg = "🔴 Kritische GPU-Temperatur erkannt, Modell konnte aber nicht entladen werden"
                logger.error(msg)
                alerts.append(msg)

    except Exception as exc:
        alerts.append(f"⚠️ GPU/Thermal Check fehlgeschlagen: {exc}")

    # 4. Alerts senden
    if alerts:
        logger.warning("Alerts gefunden, sende Benachrichtigungen")
        success = send_ntfy_alerts(alerts)
        if not success:
            logger.error("❌ Fehler beim Senden der Alerts an ntfy")
    else:
        logger.info("✅ Alles im grünen Bereich")

    return payload


def run_monitor_loop() -> None:
    logger.info("ai-monitor gestartet, Intervall=%ss", POLL_INTERVAL_SECONDS)

    while True:
        try:
            payload = monitor_system()
            logger.info("Monitor payload: %s", payload)
        except Exception:
            logger.exception("Fehler im Monitor-Loop")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_monitor_loop()
