from __future__ import annotations

import json
import logging
import os
import requests
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def _fetch_ollama_data(endpoint: str) -> dict[str, Any]:
    """
    Führt eine GET-Anfrage an die Ollama-API durch und gibt die Antwort als JSON zurück.

    Parameter:
      - endpoint: Der API-Endpunkt (z.B. '/api/ps', '/api/tags')

    Rückgabe:
      - Die JSON-Antwort des API-Calls

    Raises:
      - requests.RequestException: Bei Netzwerkfehlern oder ungültigen Antworten
    """
    base_url = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
    url = f"{base_url}{endpoint}"
    timeout_seconds = 5

    try:
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.exception("Fehler beim Abrufen von Ollama-Daten: %s", exc)
        raise


def bytes_to_gb(value: Any) -> float:
    """
    Konvertiert einen Byte-Wert in GB und rundet auf drei Dezimalstellen.

    Parameter:
      - value: Der Wert in Bytes

    Rückgabe:
      - Der Wert in GB als Gleitkommazahl
    """
    try:
        return round(float(value) / (1024**3), 3)
    except (TypeError, ValueError):
        return 0.0


def get_ollama_status() -> dict[str, Any]:
    """
    Liest den Ollama-Status über die Ollama-API und gibt eine detaillierte Antwort zurück.

    Rückgabe:
      - status: "ok" oder "error"
      - message: Fehlermeldung falls vorhanden
      - running_models: Liste der laufenden Modelle mit name, size, processor, vram_used, context_length
      - available_models: Liste aller verfügbaren Modelle mit name, size
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "message": "",
        "running_models": [],
        "available_models": []
    }

    try:
        ps_data = _fetch_ollama_data('/api/ps')
        running_models = ps_data.get("models", []) if isinstance(ps_data, dict) else []

        for model in running_models:
            if not isinstance(model, dict):
                continue
            details = model.get("details", {}) or {}
            vram_bytes = model.get("size_vram", 0)
            size_bytes = model.get("size", 0)

            processor_status = "GPU" if float(vram_bytes) > 0 else "CPU"
            if float(vram_bytes) < float(size_bytes):
                processor_status = "Partial GPU/CPU"

            result["running_models"].append(
                {
                    "name": model.get("name"),
                    "size": bytes_to_gb(size_bytes),
                    "processor": processor_status,
                    "vram_used": bytes_to_gb(vram_bytes),
                    "context_length": details.get("context_length")
                    or details.get("num_ctx")
                    or model.get("context_length"),
                }
            )

    except requests.RequestException as exc:
        logger.exception("Fehler bei Ollama /api/ps: %s", exc)
        result["status"] = "error"
        result["message"] = f"Fehler bei Ollama /api/ps: {exc}"

    try:
        tags_data = _fetch_ollama_data('/api/tags')
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

    except requests.RequestException as exc:
        logger.exception("Fehler bei Ollama /api/tags: %s", exc)
        if result["status"] == "ok":
            result["status"] = "error"
            result["message"] = f"Fehler bei Ollama /api/tags: {exc}"

    return result
