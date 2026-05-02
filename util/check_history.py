#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path("/mnt/ai-bulk/projects/ai-monitor")
HISTORY_FILE = PROJECT_DIR / "history" / "monitor_history.jsonl"
LAST_N = 20


def load_last_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"History-Datei nicht gefunden: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, Any]] = []

    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            parsed = {
                "_parse_error": str(exc),
                "_raw": line,
            }

        rows.append(parsed)

    return rows


def format_timestamp(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "?"

    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def bytes_to_gib(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "?"

    return f"{value / 1024**3:.2f} GiB"


def get_model_names(models: object) -> list[str]:
    if not isinstance(models, list):
        return []

    names: list[str] = []

    for model in models:
        if not isinstance(model, dict):
            continue

        name = model.get("name") or model.get("model")
        if isinstance(name, str):
            names.append(name)

    return names


def get_docker_ollama(row: dict[str, Any]) -> dict[str, Any]:
    docker = row.get("docker")

    if not isinstance(docker, dict):
        return {}

    ollama = docker.get("ollama")

    if not isinstance(ollama, dict):
        return {}

    return ollama


def get_state(row: dict[str, Any]) -> dict[str, Any]:
    state = row.get("state")

    if not isinstance(state, dict):
        return {}

    return state


def print_latest_snapshot(row: dict[str, Any]) -> None:
    model_names = get_model_names(row.get("ollama_models"))
    docker_ollama = get_docker_ollama(row)
    state = get_state(row)

    print("== Letzter Eintrag ==")
    print(json.dumps(row, indent=2, ensure_ascii=False))
    print()

    print("== Kurzstatus ==")
    print(f"Zeit:             {format_timestamp(row.get('timestamp'))}")
    print(f"GPU Temp Edge:    {row.get('gpu_temp')} °C")
    print(f"GPU Temp Hotspot: {row.get('gpu_temp_junction')} °C")
    print(f"GPU Temp Memory:  {row.get('gpu_temp_memory')} °C")
    print(f"GPU Use:          {row.get('gpu_use')} %")
    print(f"Power:            {row.get('power_w')} W")
    print(f"VRAM:             {row.get('vram_percent')} %")
    print(f"VRAM Used:        {bytes_to_gib(row.get('vram_used'))}")
    print(f"VRAM Total:       {bytes_to_gib(row.get('vram_total'))}")
    print(f"GPU Error:        {row.get('gpu_error')}")
    print(f"Ollama Models:    {', '.join(model_names) if model_names else '-'}")

    if docker_ollama:
        print()
        print("== Docker: ollama ==")
        print(f"CPU:              {docker_ollama.get('cpu_percent')} %")
        print(f"RAM:              {docker_ollama.get('mem_percent')} %")
        print(f"RAM Used:         {bytes_to_gib(docker_ollama.get('mem_used_bytes'))}")
        print(f"RAM Limit:        {bytes_to_gib(docker_ollama.get('mem_limit_bytes'))}")
        print(f"PIDs:             {docker_ollama.get('pids')}")
        print(f"Block I/O:        {docker_ollama.get('block_io_raw')}")
        print(f"Net I/O:          {docker_ollama.get('net_io_raw')}")
        print(f"Docker Error:     {docker_ollama.get('docker_error')}")

    print()
    print("== Betriebszustand ==")

    if state:
        print(f"Label:            {state.get('label')}")
        print(f"Severity:         {state.get('severity')}")
        print(f"Summary:          {state.get('summary')}")
        print(f"Empfehlung:       {state.get('recommendation')}")
    else:
        print("Noch kein state-Feld im letzten History-Eintrag.")

    print()


def print_null_fields(row: dict[str, Any]) -> None:
    print("== Null-Feld-Analyse letzter Eintrag ==")

    ignored_null_fields = {
        "gpu_error",
        "vram_error",
        "ollama_error",
        "docker_error",
    }

    found = False

    for key, value in sorted(row.items()):
        if key in ignored_null_fields:
            continue

        if value is None:
            print(f"NULL: {key}")
            found = True

    if not found:
        print("Keine problematischen Null-Felder im letzten Eintrag.")

    print()


def print_timeline(rows: list[dict[str, Any]]) -> None:
    print("== Entwicklung der letzten Werte ==")

    for row in rows:
        model_names = get_model_names(row.get("ollama_models"))
        docker_ollama = get_docker_ollama(row)
        state = get_state(row)

        docker_cpu = docker_ollama.get("cpu_percent") if docker_ollama else None
        docker_mem = docker_ollama.get("mem_percent") if docker_ollama else None
        state_label = state.get("label") if state else "-"
        state_severity = state.get("severity") if state else "-"

        print(
            f"{format_timestamp(row.get('timestamp'))} | "
            f"edge={row.get('gpu_temp')}°C | "
            f"hotspot={row.get('gpu_temp_junction')}°C | "
            f"mem={row.get('gpu_temp_memory')}°C | "
            f"gpu={row.get('gpu_use')}% | "
            f"vram={row.get('vram_percent')}% | "
            f"power={row.get('power_w')}W | "
            f"models={','.join(model_names) if model_names else '-'} | "
            f"docker_cpu={docker_cpu}% | "
            f"docker_mem={docker_mem}% | "
            f"state={state_label}/{state_severity} | "
            f"error={row.get('gpu_error')}"
        )


def main() -> int:
    rows = load_last_jsonl(HISTORY_FILE, LAST_N)

    if not rows:
        print("Keine History-Einträge gefunden.")
        return 1

    latest = rows[-1]

    print(f"Datei: {HISTORY_FILE}")
    print(f"Letzte Einträge: {len(rows)}")
    print()

    print_latest_snapshot(latest)
    print_null_fields(latest)
    print_timeline(rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())