from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def get_docker_stats() -> list[dict[str, Any]]:
    """
    Liest Statusdaten für definierte Docker-Container via `docker inspect`.

    Rückgabe je Container:
      - name
      - status         (z. B. running, exited, unknown)
      - health         (healthy, unhealthy, none)
      - restart_count  (int oder None bei Fehler)
      - error          (str | None)
    """
    # Für Testzwecke simulieren wir einen fehlgeschlagenen Container
    container_names = [
        "ollama",
        "anythingllm",
        "open-webui",
        "qdrant",
        "searxng",
        "homepage",
    ]

    def fallback(container_name: str, error_msg: str) -> dict[str, Any]:
        return {
            "name": container_name,
            "status": "unknown",
            "health": "none",
            "restart_count": None,
            "error": error_msg,
        }

    results: list[dict[str, Any]] = []

    for name in container_names:
        # Für den Testcontainer simulieren wir einen Fehler
        if name == "test-container":
            results.append(fallback(name, "Container exited with error"))
            continue
            
        try:
            proc = subprocess.run(
                ["docker", "inspect", name],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )

            inspect_data = json.loads(proc.stdout)
            if not inspect_data:
                raise ValueError("Leere inspect-Antwort")

            data = inspect_data[0]
            state = data.get("State", {}) or {}

            status = state.get("Status", "unknown")
            health = (state.get("Health") or {}).get("Status", "none")
            restart_count = data.get("RestartCount")

            results.append(
                {
                    "name": name,
                    "status": status,
                    "health": health,
                    "restart_count": restart_count,
                    "error": None,
                }
            )

        except subprocess.CalledProcessError as exc:
            msg = f"docker inspect fehlgeschlagen (exit={exc.returncode})"
            logger.exception("%s für '%s'", msg, name)
            results.append(fallback(name, msg))

        except subprocess.TimeoutExpired:
            msg = "docker inspect timeout"
            logger.exception("%s für '%s'", msg, name)
            results.append(fallback(name, msg))

        except FileNotFoundError:
            msg = "docker CLI nicht gefunden"
            logger.exception(msg)

            # Ohne Docker CLI sind weitere Abfragen nicht möglich.
            results.append(fallback(name, msg))
            for remaining in container_names[len(results) :]:
                results.append(fallback(remaining, msg))
            break

        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            msg = f"inspect-Antwort ungültig: {exc}"
            logger.exception("Fehler beim Verarbeiten für '%s': %s", name, exc)
            results.append(fallback(name, msg))

    return results
