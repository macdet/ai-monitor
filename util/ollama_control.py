from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def unload_ollama_model(
    model: str,
    ollama_url: str = "http://127.0.0.1:11434",
    timeout: int = 10,
) -> bool:
    """
    Entlädt ein Modell über die offizielle Ollama-API.
    """
    payload = {
        "model": model,
        "prompt": "",
        "stream": False,
        "keep_alive": 0,
    }

    request = urllib.request.Request(
        url=f"{ollama_url.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if 200 <= response.status < 300:
                return True
            logger.error("Ollama unload fehlgeschlagen: HTTP %s", response.status)
            return False
    except urllib.error.HTTPError as exc:
        logger.exception("Ollama unload HTTP-Fehler: %s", exc)
    except urllib.error.URLError as exc:
        logger.exception("Ollama unload URL-Fehler: %s", exc)
    except Exception:
        logger.exception("Unerwarteter Fehler beim Ollama-Unload für %s", model)

    return False
