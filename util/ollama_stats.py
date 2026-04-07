from __future__ import annotations

import json
import logging
import os
import requests
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def _fetch_ollama_data(endpoints: List[str]) -> Dict[str, Any]:
    """
    Führt mehrere GET-Anfragen an die Ollama-API durch und gibt die Antworten als JSON zurück.

    Parameter:
      - endpoints: Liste der API-Endpunkte (z.B. ['/api/ps', '/api/tags'])

    Rückgabe:
      - Ein Dictionary mit den Endpunkten als Schlüssel und den entsprechenden JSON-Antworten als Werte

    Raises:
      - requests.RequestException: Bei Netzwerkfehlern oder ungültigen Antworten
    """
    base_url = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
    timeout_seconds = 5
    results: Dict[str, Any] = {}

    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            results[endpoint] = response.json()
        except requests.RequestException as exc:
            logger.exception("Fehler beim Abrufen von Ollama-Daten für %s: %s", endpoint, exc)
            results[endpoint] = {}

    return results


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

    endpoints = ['/api/ps', '/api/tags']
    data = _fetch_ollama_data(endpoints)

    try:
        ps_data = data.get('/api/ps', {})
        running_models = ps_data.get("models", []) if isinstance(ps_data, dict) else []

        for model in running_models:
            if not isinstance(model, dict):
                continue
            details = model.get("details", {}) or {}
            vram_bytes = model.get("size_vram", 0)
            size_bytes = model.get("size", 0)

            gpu_ratio = (float(vram_bytes) / float(size_bytes)) * 100 if float(size_bytes) > 0 else 0
            processor_status = "GPU" if gpu_ratio >= 50 else "CPU"
            if gpu_ratio < 50 and gpu_ratio > 0:
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

    except Exception as exc:
        logger.exception("Fehler bei der Verarbeitung von Ollama /api/ps-Daten: %s", exc)
        result["status"] = "error"
        result["message"] += f"Fehler bei Ollama /api/ps: {exc}\n"

    try:
        tags_data = data.get('/api/tags', {})
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

    except Exception as exc:
        logger.exception("Fehler bei der Verarbeitung von Ollama /api/tags-Daten: %s", exc)
        if result["status"] == "ok":
            result["status"] = "error"
            result["message"] += f"Fehler bei Ollama /api/tags: {exc}\n"

    return result
