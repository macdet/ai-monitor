from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from util.gpu_stats import get_gpu_stats
from util.thermal_policy import ThermalPolicy
from util.ollama_control import (
    get_loaded_ollama_models,
    unload_current_ollama_model,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = int(os.getenv("AI_MONITOR_POLL_INTERVAL", "5"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

# Persistente Daten bewusst unter /mnt/ai-bulk
HISTORY_FILE = Path(
    os.getenv(
        "AI_MONITOR_HISTORY_FILE",
        "/mnt/ai-bulk/projects/ai-monitor/history/monitor_history.jsonl",
    )
)

thermal_policy = ThermalPolicy(
    warn_temp_c=85.0,
    critical_temp_c=90.0,
    recover_temp_c=80.0,
    critical_hits_needed=3,
)

_last_state: str | None = None
_last_loaded_model: str | None = None


def build_monitor_payload() -> dict[str, Any]:
    global _last_state
    global _last_loaded_model

    loaded_models = get_loaded_ollama_models(ollama_url=OLLAMA_URL)
    current_model = loaded_models[0] if loaded_models else None

    gpu_stats = get_gpu_stats()
    decision = thermal_policy.evaluate(gpu_stats)

    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ollama": {
            "loaded_models": loaded_models,
            "current_model": current_model,
        },
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

    if decision.state != _last_state:
        logger.info("Thermal state changed: %s -> %s", _last_state, decision.state)
        _last_state = decision.state

    if current_model != _last_loaded_model:
        logger.info("Loaded model changed: %s -> %s", _last_loaded_model, current_model)
        _last_loaded_model = current_model

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


def append_history_entry(payload: dict[str, Any]) -> None:
    """
    Schreibt eine kompakte JSONL-Zeile für den Verlauf.
    Eine Zeile = ein Messpunkt.
    """
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    gpu = payload.get("gpu", {})
    thermal = payload.get("thermal", {})
    ollama = payload.get("ollama", {})
    actions = payload.get("actions", {})

    record = {
        "ts": payload.get("timestamp"),
        "model": ollama.get("current_model"),
        "loaded_models": ollama.get("loaded_models", []),
        "vram_used_gib": gpu.get("vram_used"),
        "vram_total_gib": gpu.get("vram_total"),
        "vram_ratio": gpu.get("vram_ratio"),
        "temp_edge_c": gpu.get("temperature_edge"),
        "temp_hotspot_c": gpu.get("temperature_hotspot"),
        "gpu_use_percent": gpu.get("gpu_use"),
        "power_w": gpu.get("power_w"),
        "thermal_state": thermal.get("state"),
        "thermal_temp_c": thermal.get("temperature_c"),
        "warning": thermal.get("warning"),
        "model_unloaded": actions.get("model_unloaded"),
        "unloaded_model": actions.get("unloaded_model"),
    }

    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_compact_status(payload: dict[str, Any]) -> None:
    """
    Kompaktere Statuszeile statt volles Dict im Log.
    """
    gpu = payload.get("gpu", {})
    thermal = payload.get("thermal", {})
    ollama = payload.get("ollama", {})

    logger.info(
        "model=%s | vram=%.2f/%.2f GiB | hotspot=%s°C | edge=%s°C | gpu=%s%% | power=%sW | thermal=%s",
        ollama.get("current_model"),
        gpu.get("vram_used") or 0.0,
        gpu.get("vram_total") or 0.0,
        gpu.get("temperature_hotspot"),
        gpu.get("temperature_edge"),
        gpu.get("gpu_use"),
        gpu.get("power_w"),
        thermal.get("state"),
    )


def run_monitor_loop() -> None:
    logger.info("ai-monitor gestartet, Intervall=%ss", POLL_INTERVAL_SECONDS)
    logger.info("History file: %s", HISTORY_FILE)

    while True:
        try:
            payload = build_monitor_payload()
            append_history_entry(payload)
            log_compact_status(payload)
        except Exception:
            logger.exception("Fehler im ai-monitor-Loop")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_monitor_loop()
