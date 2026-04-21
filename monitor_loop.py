from __future__ import annotations

import logging
import os
import time
from typing import Any

from util.gpu_stats2 import get_gpu_stats
from util.thermal_policy import ThermalPolicy
from util.ollama_control2 import unload_current_ollama_model

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = int(os.getenv("AI_MONITOR_POLL_INTERVAL", "15"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

thermal_policy = ThermalPolicy(
    warn_temp_c=85.0,
    critical_temp_c=90.0,
    recover_temp_c=80.0,
    critical_hits_needed=3,
)

_last_state: str | None = None


def build_monitor_payload() -> dict[str, Any]:
    global _last_state

    gpu_stats = get_gpu_stats()
    decision = thermal_policy.evaluate(gpu_stats)

    payload: dict[str, Any] = {
        "gpu": gpu_stats,
        "thermal": {
            "state": decision.state,
            "temperature_c": decision.temperature_c,
            "warning": decision.reason,
            "should_warn": decision.should_warn,
            "should_unload": decision.should_unload,
        },
        "actions": {
            "model_unloaded": False,
            "unloaded_model": None,
        },
    }

    # Nur bei Zustandswechsel loggen statt jeden Zyklus zu spammen
    if decision.state != _last_state:
        logger.info("Thermal state changed: %s -> %s", _last_state, decision.state)
        _last_state = decision.state

    if decision.should_warn and decision.reason:
        logger.warning(decision.reason)

    if decision.should_unload:
        ok, model = unload_current_ollama_model(ollama_url=OLLAMA_URL)
        payload["actions"]["model_unloaded"] = ok
        payload["actions"]["unloaded_model"] = model

        if ok:
            logger.error(
                "Ollama-Modell wegen kritischer GPU-Temperatur entladen: %s",
                model,
            )
        else:
            logger.error(
                "Kritische GPU-Temperatur erkannt, Modell konnte aber nicht entladen werden"
            )

    return payload


def run_monitor_loop() -> None:
    logger.info("ai-monitor gestartet, Intervall=%ss", POLL_INTERVAL_SECONDS)

    while True:
        try:
            payload = build_monitor_payload()

            # Hier kannst du später:
            # - in Datei schreiben
            # - an dein Web-Frontend geben
            # - per ntfy senden
            # - über eine API ausliefern
            logger.info("Monitor payload: %s", payload)

        except Exception:
            logger.exception("Fehler im ai-monitor-Loop")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_monitor_loop()
