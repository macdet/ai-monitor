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
        "vram_used": None,
        "vram_total": None,
        "vram_ratio": None,
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

        vram_used_mb = first_value_by_terms(first_gpu, ("used", "vram"))
        vram_total_mb = first_value_by_terms(first_gpu, ("total", "vram"))

        # Debug-Ausgabe
        # if vram_total_mb is not None:
        #     print(f"DEBUG ROHWERT: {vram_total_mb}")

        # Umrechnung in GB mit korrekter Division
        # Versuche zunächst 1024^3 (GB), dann 1024^2 (MB) wenn nötig
        vram_used_gb = None
        vram_total_gb = None
        
        if vram_used_mb is not None and vram_total_mb is not None:
            # Erste Versuch mit 1024^3
            vram_used_gb = vram_used_mb / (1024**3)
            vram_total_gb = vram_total_mb / (1024**3)
            
            # Wenn das Ergebnis zu hoch ist, versuche 1024^2
            if vram_total_gb is not None and vram_total_gb > 100:
                vram_used_gb = vram_used_mb / (1024**2)
                vram_total_gb = vram_total_mb / (1024**2)
            
            # Für RX 7900 XTX sollte vram_total 24.0 ergeben
            # if vram_total_gb is not None and abs(vram_total_gb - 24.0) > 1:
            #     print(f"DEBUG: Ungewöhnlicher Wert: {vram_total_gb} GB")
        
        # Berechne das Verhältnis
        vram_ratio = vram_used_gb / vram_total_gb if vram_used_gb is not None and vram_total_gb is not None and vram_total_gb > 0 else None

        # Rückgabe im erwarteten Format
        result = {
            "vram_used": vram_used_gb,
            "vram_total": vram_total_gb,
            "vram_ratio": vram_ratio
        }

    except FileNotFoundError:
        logger.exception("rocm-smi nicht gefunden")
    except subprocess.CalledProcessError as exc:
        logger.exception("rocm-smi fehlgeschlagen (exit=%s): %s", exc.returncode, exc)
    except subprocess.TimeoutExpired:
        logger.exception("Timeout bei rocm-smi")
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.exception("Ungültige rocm-smi Antwort: %s", exc)

    return result
