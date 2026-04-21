from __future__ import annotations

import logging
import os

from util.gpu_stats2 import get_gpu_stats
from util.ollama_control import unload_ollama_model
from util.thermal_policy import ThermalPolicy

logger = logging.getLogger(__name__)

OLLAMA_MODEL_TO_PROTECT = os.getenv("OLLAMA_MODEL_TO_PROTECT", "qwen2.5-coder:14b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

thermal_policy = ThermalPolicy(
    warn_temp_c=85.0,
    critical_temp_c=90.0,
    recover_temp_c=80.0,
    critical_hits_needed=3,
)


def monitor_gpu_and_protect_model() -> dict[str, object]:
    stats = get_gpu_stats()
    decision = thermal_policy.evaluate(stats)

    payload: dict[str, object] = {
        "stats": stats,
        "thermal_state": decision.state,
        "thermal_temp_c": decision.temperature_c,
        "warning": decision.reason,
        "model_unloaded": False,
    }

    if decision.should_warn and decision.reason:
        logger.warning(decision.reason)

    if decision.should_unload:
        ok = unload_ollama_model(
            model=OLLAMA_MODEL_TO_PROTECT,
            ollama_url=OLLAMA_URL,
        )
        payload["model_unloaded"] = ok
        if ok:
            logger.error(
                "Ollama-Modell wegen anhaltend kritischer GPU-Temperatur entladen: %s",
                OLLAMA_MODEL_TO_PROTECT,
            )
        else:
            logger.error(
                "Kritische GPU-Temperatur erkannt, aber Ollama-Modell konnte nicht entladen werden: %s",
                OLLAMA_MODEL_TO_PROTECT,
            )

    return payload
