from __future__ import annotations

import json
import logging
import subprocess
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def get_ollama_stats() -> dict[str, list[dict[str, Any]]]:
    """
    Liest Ollama-Modelldaten von /api/ps und /api/tags.

    Rückgabe:
      - running: laufende Modelle mit name, size, processor, vram_used, context_length
      - available: alle verfügbaren Modelle mit name, size
    """
    base_url = "http://localhost:11434"
    timeout_seconds = 5

    def bytes_to_gb(value: Any) -> float:
        try:
            return round(float(value) / (1024**3), 3)
        except (TypeError, ValueError):
            return 0.0

    result: dict[str, list[dict[str, Any]]] = {"running": [], "available": []}

    try:
        ps_resp = subprocess.run(
            ["curl", "-s", f"{base_url}/api/ps"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True
        )
        ps_data = json.loads(ps_resp.stdout)
        running_models = ps_data.get("models", []) if isinstance(ps_data, dict) else []

        for model in running_models:
            if not isinstance(model, dict):
                continue
            details = model.get("details", {}) or {}
            vram_bytes = model.get("size_vram", 0)
            result["running"].append(
                {
                    "name": model.get("name"),
                    "size": bytes_to_gb(model.get("size")),
                    "processor": "gpu" if float(vram_bytes or 0) > 0 else "cpu",
                    "vram_used": bytes_to_gb(vram_bytes),
                    "context_length": details.get("context_length")
                    or details.get("num_ctx")
                    or model.get("context_length"),
                }
            )

    except subprocess.CalledProcessError as exc:
        logger.exception("Fehler bei Ollama /api/ps: %s", exc)
    except (ValueError, TypeError, KeyError) as exc:
        logger.exception("Ungültige Antwort von Ollama /api/ps: %s", exc)

    try:
        tags_resp = subprocess.run(
            ["curl", "-s", f"{base_url}/api/tags"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True
        )
        tags_data = json.loads(tags_resp.stdout)
        available_models = tags_data.get("models", []) if isinstance(tags_data, dict) else []

        for model in available_models:
            if not isinstance(model, dict):
                continue
            result["available"].append(
                {
                    "name": model.get("name"),
                    "size": bytes_to_gb(model.get("size")),
                }
            )

    except subprocess.CalledProcessError as exc:
        logger.exception("Fehler bei Ollama /api/tags: %s", exc)
    except (ValueError, TypeError, KeyError) as exc:
        logger.exception("Ungültige Antwort von Ollama /api/tags: %s", exc)

    return result


def get_ollama_health() -> dict[str, Any]:
    """
    Liest den Ollama-Status über ollama ps und ollama health.

    Rückgabe:
      - status: "ok" oder "error"
      - message: Fehlermeldung falls vorhanden
      - running_models: Liste der laufenden Modelle mit name, size, processor, vram_used, context_length
      - available_models: Liste aller verfügbaren Modelle mit name, size
    """
    base_url = "http://localhost:11434"
    timeout_seconds = 5

    def bytes_to_gb(value: Any) -> float:
        try:
            return round(float(value) / (1024**3), 3)
        except (TypeError, ValueError):
            return 0.0

    result: Dict[str, Any] = {
        "status": "ok",
        "message": "",
        "running_models": [],
        "available_models": []
    }

    try:
        ps_resp = subprocess.run(
            ["curl", "-s", f"{base_url}/api/ps"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True
        )
        ps_data = json.loads(ps_resp.stdout)
        running_models = ps_data.get("models", []) if isinstance(ps_data, dict) else []

        for model in running_models:
            if not isinstance(model, dict):
                continue
            details = model.get("details", {}) or {}
            vram_bytes = model.get("size_vram", 0)
            result["running_models"].append(
                {
                    "name": model.get("name"),
                    "size": bytes_to_gb(model.get("size")),
                    "processor": "gpu" if float(vram_bytes or 0) > 0 else "cpu",
                    "vram_used": bytes_to_gb(vram_bytes),
                    "context_length": details.get("context_length")
                    or details.get("num_ctx")
                    or model.get("context_length"),
                }
            )

    except subprocess.CalledProcessError as exc:
        logger.exception("Fehler bei Ollama /api/ps: %s", exc)
        result["status"] = "error"
        result["message"] = f"Fehler bei Ollama /api/ps: {exc}"
    except (ValueError, TypeError, KeyError) as exc:
        logger.exception("Ungültige Antwort von Ollama /api/ps: %s", exc)
        result["status"] = "error"
        result["message"] = f"Ungültige Antwort von Ollama /api/ps: {exc}"

    try:
        tags_resp = subprocess.run(
            ["curl", "-s", f"{base_url}/api/tags"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True
        )
        tags_data = json.loads(tags_resp.stdout)
        available_models = tags_data.get("models", []) if isinstance(tags_data, dict) else []

        for model in available_models:
            if not isinstance(model, dict):
                continue
            result["available_models"].append(
                {
                    "name": model.get("name"),
                    "size": bytes_to_gb(model.get("size")),
                }
            )

    except subprocess.CalledProcessError as exc:
        logger.exception("Fehler bei Ollama /api/tags: %s", exc)
        if result["status"] == "ok":
            result["status"] = "error"
            result["message"] = f"Fehler bei Ollama /api/tags: {exc}"
    except (ValueError, TypeError, KeyError) as exc:
        logger.exception("Ungültige Antwort von Ollama /api/tags: %s", exc)
        if result["status"] == "ok":
            result["status"] = "error"
            result["message"] = f"Ungültige Antwort von Ollama /api/tags: {exc}"

    return result
