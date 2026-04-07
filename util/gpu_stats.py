from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def get_gpu_stats() -> dict[str, float | None]:
    """
    Liest GPU-Daten über rocm-smi aus.

    Aufruf immer mit LC_ALL=C und LANG=C, damit Dezimalpunkte
    zuverlässig als "." geliefert werden (Locale-Bug vermeiden).
    """
    # Verwende den Pfad aus der Umgebung, falls gesetzt, sonst den Standardpfad
    rocm_smi_path = os.getenv("ROCM_SMI_PATH", "/opt/rocm/bin/rocm-smi")
    command = [
        rocm_smi_path,
        "--showtemp",
        "--showuse",
        "--showmeminfo",
        "vram",
        "--showpower",
        "--json",
    ]

    result: dict[str, float | None] = {
        "gpu_load": None,
        "vram_used_gb": None,
        "vram_total_gb": None,
        "temperature_c": None,
        "power_w": None,
    }

    def to_float(value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).strip().replace(",", ".")
        number_chars = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
        if not number_chars:
            return None
        try:
            return float(number_chars)
        except ValueError:
            return None

    def first_value_by_terms(payload: dict[str, Any], terms: tuple[str, ...]) -> float | None:
        for key, value in payload.items():
            key_l = str(key).lower()
            if all(term in key_l for term in terms):
                return to_float(value)
        return None

    try:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"

        proc = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        data = json.loads(proc.stdout)
        if not isinstance(data, dict) or not data:
            raise ValueError("Leere/ungültige JSON-Antwort von rocm-smi")

        first_gpu = next((v for v in data.values() if isinstance(v, dict)), None)
        if not isinstance(first_gpu, dict):
            raise ValueError("Keine GPU-Daten in rocm-smi JSON gefunden")

        gpu_load = first_value_by_terms(first_gpu, ("gpu", "use"))
        vram_used_mb = first_value_by_terms(first_gpu, ("used", "vram"))
        vram_total_mb = first_value_by_terms(first_gpu, ("total", "vram"))
        temperature_c = first_value_by_terms(first_gpu, ("temp",))
        power_w = first_value_by_terms(first_gpu, ("power",))

        result["gpu_load"] = gpu_load
        result["vram_used_gb"] = round(vram_used_mb / 1024, 3) if vram_used_mb is not None else None
        result["vram_total_gb"] = round(vram_total_mb / 1024, 3) if vram_total_mb is not None else None
        result["temperature_c"] = temperature_c
        result["power_w"] = power_w

    except FileNotFoundError:
        logger.exception("rocm-smi nicht gefunden")
    except subprocess.CalledProcessError as exc:
        logger.exception("rocm-smi fehlgeschlagen (exit=%s): %s", exc.returncode, exc)
    except subprocess.TimeoutExpired:
        logger.exception("Timeout bei rocm-smi")
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.exception("Ungültige rocm-smi Antwort: %s", exc)

    return result
