from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def get_loaded_ollama_models(
    ollama_url: str = "http://127.0.0.1:11434",
    timeout: int = 10,
) -> list[str]:
    """
    Liefert die Namen aktuell geladener Ollama-Modelle.
    """
    request = urllib.request.Request(
        url=f"{ollama_url.rstrip('/')}/api/ps",
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

            if not isinstance(data, dict):
                logger.error("Unerwartete /api/ps Antwort: kein Dict")
                return []

            models = data.get("models", [])
            return [m.get("name") for m in models if isinstance(m, dict) and m.get("name")]

    except Exception:
        logger.exception("Konnte geladene Ollama-Modelle nicht abfragen")
        return []


def unload_ollama_model(
    model: str,
    ollama_url: str = "http://127.0.0.1:11434",
    timeout: int = 10,
) -> bool:
    """
    Entlädt ein Modell über die Ollama-API.
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
        logger.exception("Unerwarteter Fehler beim Entladen von %s", model)

    return False


def unload_current_ollama_model(
    ollama_url: str = "http://127.0.0.1:11434",
    timeout: int = 10,
) -> tuple[bool, str | None]:
    """
    Entlädt das aktuell geladene Modell.
    Rückgabe:
      (erfolg, modellname)
    """
    models = get_loaded_ollama_models(ollama_url=ollama_url, timeout=timeout)

    if not models:
        logger.warning("Kein geladenes Ollama-Modell gefunden")
        return False, None

    model = models[0]
    ok = unload_ollama_model(model=model, ollama_url=ollama_url, timeout=timeout)
    return ok, model
