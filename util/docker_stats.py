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
            # Führe docker inspect ohne check=True aus, um Fehler zu behandeln
            proc = subprocess.run(
                ["docker", "inspect", name],
                check=False,  # Wichtig: nicht check=True verwenden
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Prüfe den Exit-Code für erfolgreiche und fehlgeschlagene Abfragen
            if proc.returncode != 0:
                # Container existiert nicht
                if (
                    "No such object" in proc.stderr
                    or "No such container" in proc.stderr
                ):
                    logger.info(f"Container {name} nicht gefunden (nicht existent)")
                    results.append(
                        {
                            "name": name,
                            "status": "missing",
                            "health": "none",
                            "restart_count": None,
                            "error": "Container nicht gefunden",
                        }
                    )
                else:
                    # Andere Fehler beim Inspect
                    msg = f"docker inspect fehlgeschlagen (exit={proc.returncode}) - {proc.stderr}"
                    logger.exception("%s für '%s'", msg, name)
                    results.append(fallback(name, msg))
                continue

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
