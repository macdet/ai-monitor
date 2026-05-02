from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)


@dataclass
class LoadedModel:
    name: str
    size_gb: float
    vram_gb: float
    context: int
    processor: str
    cpu_pct: float


def get_loaded_models(ollama_url: str | None = None) -> list[LoadedModel]:
    """
    Abfrage der Ollama API nach geladenen Modellen.
    Berechnet GPU/CPU-Anteil und gibt Liste von LoadedModel zurück.
    """
    base_url = ollama_url or os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
    
    try:
        response = requests.get(f"{base_url}/api/ps", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        models: list[LoadedModel] = []
        for m in data.get("models", []):
            size = m.get("size", 0)
            vram = m.get("size_vram", 0)
            
            size_gb = round(size / (1024**3), 2)
            vram_gb = round(vram / (1024**3), 2)
            
            # GPU-Ratio Logik
            ratio = vram / size if size > 0 else 0.0
            gpu_pct = min(ratio * 100, 100.0)
            cpu_pct = 100.0 - gpu_pct
            
            if gpu_pct >= 100.0:
                proc = "Modell geladen (GPU)"
            elif gpu_pct > 0:
                proc = f"{int(gpu_pct)}% GPU / {int(cpu_pct)}% CPU"
            else:
                proc = "Modell geladen (CPU)"

            models.append(LoadedModel(
                name=m.get("name", "Unknown"),
                size_gb=size_gb,
                vram_gb=vram_gb,
                context=m.get("context_length", 0),
                processor=proc,
                cpu_pct=cpu_pct,
            ))
        return models

    except Exception as e:
        logger.error("Ollama Abfrage fehlgeschlagen: %s", e)
        return []


def get_ollama_data() -> dict[str, Any]:
    """
    Rückwärtskompatibilität für bestehende Caller.
    """
    models = get_loaded_models()
    return {
        "status": "ok",
        "models": [
            {
                "name": m.name,
                "processor": m.processor,
                "size_gb": m.size_gb,
                "vram_used_gb": m.vram_gb,
                "context": m.context,
            }
            for m in models
        ],
    }
