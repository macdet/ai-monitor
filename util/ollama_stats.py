from __future__ import annotations

import json
import logging
import os
import requests
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def _fetch_ollama_data(endpoint: str) -> Dict[str, Any]:
    """
    Führt eine GET-Anfrage an die Ollama-API durch und gibt die Antwort als JSON zurück.

    Parameter:
      - endpoint: Der API-Endpunkt (z.B. '/api/ps')

    Rückgabe:
      - Ein Dictionary mit den entsprechenden JSON-Antworten

    Raises:
      - requests.RequestException: Bei Netzwerkfehlern oder ungültigen Antworten
    """
    base_url = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
    timeout_seconds = 5
    url = f"{base_url}{endpoint}"
    try:
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.exception("Fehler beim Abrufen von Ollama-Daten für %s: %s", endpoint, exc)
        return {}

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

def get_ollama_status() -> Dict[str, Any]:
    """
    Liest den Ollama-Status über die Ollama-API und gibt eine detaillierte Antwort zurück.

    Rückgabe:
      - status: "ok" oder "error"
      - message: Fehlermeldung falls vorhanden
      - running_models: Liste der laufenden Modelle mit name, size_gb, processor, context
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "message": "",
        "running_models": []
    }

    endpoint = '/api/ps'
    data = _fetch_ollama_data(endpoint)

    try:
        ps_data = data.get("models", []) if isinstance(data, dict) else []

        for model in ps_data:
            if not isinstance(model, dict):
                continue
            details = model.get("details", {}) or {}
            vram_bytes = model.get("size_vram", 0)
            size_bytes = model.get("size", 0)

            gpu_ratio = float(vram_bytes) / float(size_bytes) if float(size_bytes) > 0 else 0
            processor_status = "100% GPU" if gpu_ratio == 1.0 else f"{int(gpu_ratio*100)}% GPU"

            result["running_models"].append(
                {
                    "name": model.get("name"),
                    "size_gb": bytes_to_gb(size_bytes),
                    "processor": processor_status,
                    "context": details.get("context_length")
                    or details.get("num_ctx")
                    or model.get("context_length"),
                }
            )

    except Exception as exc:
        logger.exception("Fehler bei der Verarbeitung von Ollama /api/ps-Daten: %s", exc)
        result["status"] = "error"
        result["message"] += f"Fehler bei Ollama /api/ps: {exc}\n"

    return result
