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

    Rückgabe:
      - vram_used: GiB
      - vram_total: GiB
      - vram_ratio: 0..1
      - temperature_edge: °C
      - temperature_hotspot: °C
      - gpu_use: %
      - power_w: W

    Diese Funktion misst nur. Sie trifft keine Policy-Entscheidung.
    """
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
        "temperature_edge": None,
        "temperature_hotspot": None,
        "gpu_use": None,
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

    def first_value_by_alternatives(
        payload: dict[str, Any],
        alternatives: list[tuple[str, ...]],
    ) -> float | None:
        for terms in alternatives:
            value = first_value_by_terms(payload, terms)
            if value is not None:
                return value
        return None

    def first_gpu_payload(data: dict[str, Any]) -> dict[str, Any] | None:
        for value in data.values():
            if isinstance(value, dict):
                return value
        return None

    def convert_vram_to_gib(raw_value: float | None) -> float | None:
        if raw_value is None:
            return None

        gib = raw_value / (1024**3)

        # Fallback, falls die Quelle unerwartet nicht in Bytes liefert
        if gib > 100:
            gib = raw_value / 1024

        return gib

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

        first_gpu = first_gpu_payload(data)
        if not isinstance(first_gpu, dict):
            raise ValueError("Keine GPU-Daten in rocm-smi JSON gefunden")

        # VRAM
        vram_used_raw = first_value_by_alternatives(
            first_gpu,
            [
                ("used", "vram"),
                ("vram", "used"),
            ],
        )
        vram_total_raw = first_value_by_alternatives(
            first_gpu,
            [
                ("total", "vram"),
                ("vram", "total"),
            ],
        )

        vram_used_gib = convert_vram_to_gib(vram_used_raw)
        vram_total_gib = convert_vram_to_gib(vram_total_raw)

        vram_ratio = (
            vram_used_gib / vram_total_gib
            if vram_used_gib is not None and vram_total_gib not in (None, 0)
            else None
        )

        # Temperatur
        temperature_edge = first_value_by_alternatives(
            first_gpu,
            [
                ("temperature", "edge"),
                ("temp", "edge"),
                ("temperature", "current"),
                ("temp", "current"),
            ],
        )

        temperature_hotspot = first_value_by_alternatives(
            first_gpu,
            [
                ("temperature", "junction"),
                ("temp", "junction"),
                ("temperature", "hotspot"),
                ("temp", "hotspot"),
                ("temperature", "mem"),
                ("temp", "mem"),
            ],
        )

        # GPU-Auslastung
        gpu_use = first_value_by_alternatives(
            first_gpu,
            [
                ("gpu", "use"),
                ("use", "gpu"),
                ("utilization", "gpu"),
            ],
        )

        # Leistung
        power_w = first_value_by_alternatives(
            first_gpu,
            [
                ("current", "power"),
                ("power", "average"),
                ("socket", "power"),
                ("power",),
            ],
        )

        result = {
            "vram_used": vram_used_gib,
            "vram_total": vram_total_gib,
            "vram_ratio": vram_ratio,
            "temperature_edge": temperature_edge,
            "temperature_hotspot": temperature_hotspot,
            "gpu_use": gpu_use,
            "power_w": power_w,
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
