#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from typing import Any, Optional

ROCM_SMI = "/opt/rocm/bin/rocm-smi"


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "N/A", "None", "null"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _to_int(value: Any) -> Optional[int]:
    number = _to_float(value)
    return None if number is None else int(number)


def _extract_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}") + 1

    if start < 0 or end <= start:
        raise ValueError(f"No JSON found in rocm-smi output: {raw[:300]!r}")

    parsed = json.loads(raw[start:end])
    if not isinstance(parsed, dict):
        raise ValueError(f"Unexpected JSON type: {type(parsed).__name__}")

    return parsed


def _run_rocm_smi(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        [ROCM_SMI, *args, "--json"],
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
    )

    raw = proc.stdout.strip() or proc.stderr.strip()

    if not raw:
        raise RuntimeError(
            f"rocm-smi returned no output; rc={proc.returncode}; stderr={proc.stderr!r}"
        )

    # Add debug output for empty JSON
    if raw.strip() == "{}":
        raise RuntimeError(
            f"rocm-smi returned empty JSON; rc={proc.returncode}; stderr={proc.stderr!r}; stdout={proc.stdout!r}"
        )

    return _extract_json(raw)


def _first_card(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return {}

    first = next(iter(data.values()))
    return first if isinstance(first, dict) else {}


def collect_gpu_stats() -> dict[str, Any]:
    result: dict[str, Any] = {
        "gpu_temp": None,
        "gpu_temp_junction": None,
        "gpu_temp_memory": None,
        "gpu_use": None,
        "power_w": None,
        "vram_percent": None,
        "vram_used": None,
        "vram_total": None,
        "gpu_error": None,
    }

    try:
        data = _run_rocm_smi([
            "--showtemp",
            "--showpower",
            "--showuse",
            "--showmemuse",
        ])
        card = _first_card(data)

        result.update({
            "gpu_temp": _to_float(card.get("Temperature (Sensor edge) (C)")),
            "gpu_temp_junction": _to_float(card.get("Temperature (Sensor junction) (C)")),
            "gpu_temp_memory": _to_float(card.get("Temperature (Sensor memory) (C)")),
            "power_w": _to_float(card.get("Average Graphics Package Power (W)")),
            "gpu_use": _to_float(card.get("GPU use (%)")),
            "vram_percent": _to_float(card.get("GPU Memory Allocated (VRAM%)")),
        })

    except Exception as exc:
        result["gpu_error"] = f"basic_metrics_failed: {exc!r}"
        return result

    try:
        mem_data = _run_rocm_smi(["--showmeminfo", "vram"])
        mem_card = _first_card(mem_data)

        used_keys = [
            "VRAM Total Used Memory (B)",
            "VRAM Used Memory (B)",
            "GPU Memory Used (B)",
        ]
        total_keys = [
            "VRAM Total Memory (B)",
            "VRAM Total Available Memory (B)",
            "GPU Memory Total (B)",
        ]

        for key in used_keys:
            if key in mem_card:
                result["vram_used"] = _to_int(mem_card.get(key))
                break

        for key in total_keys:
            if key in mem_card:
                result["vram_total"] = _to_int(mem_card.get(key))
                break

    except Exception as exc:
        result["vram_error"] = f"vram_bytes_failed: {exc!r}"

    return result


def get_gpu_stats() -> dict[str, Any]:
    return collect_gpu_stats()


def read_gpu_stats() -> dict[str, Any]:
    return collect_gpu_stats()


def collect() -> dict[str, Any]:
    return collect_gpu_stats()


if __name__ == "__main__":
    print(json.dumps(collect_gpu_stats(), indent=2, ensure_ascii=False))
    