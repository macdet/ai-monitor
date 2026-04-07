import os
import requests
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def get_ollama_data() -> Dict[str, Any]:
    """
    Abfrage der Ollama API nach den Projekt-Conventions.
    Berechnet die GPU-Ratio und gibt ein flaches Dictionary zurück.
    """
    # IP aus direnv/env laden, sonst Fallback auf Localhost
    base_url = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434')
    
    result = {
        "status": "ok",
        "models": [],
        "message": ""
    }

    try:
        # API-Endpunkt für laufende Modelle
        response = requests.get(f"{base_url}/api/ps", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Ollama liefert die Liste im Key 'models'
        for m in data.get("models", []):
            size = m.get("size", 0)
            vram = m.get("size_vram", 0)
            
            # GPU-Ratio Logik (Convention Check)
            ratio = vram / size if size > 0 else 0
            
            if ratio >= 1.0:
                proc = "100% GPU"
            elif ratio > 0:
                proc = f"{int(ratio * 100)}% GPU"
            else:
                proc = "CPU"

            # Wir extrahieren nur, was wir wirklich brauchen
            result["models"].append({
                "name": m.get("name", "Unknown"),
                "processor": proc,
                "size_gb": round(size / (1024**3), 2),
                "context": m.get("context_length", 0) 
            })

    except Exception as e:
        logger.error(f"Ollama Abfrage fehlgeschlagen: {e}")
        result["status"] = "error"
        result["message"] = str(e)

    return result
