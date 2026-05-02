#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def find_project_dir() -> Path:
    current = Path(__file__).resolve()

    for candidate in [current.parent, *current.parents]:
        if (candidate / "history" / "monitor_history.jsonl").exists():
            return candidate

        if (candidate / "util" / "gpu_stats.py").exists():
            return candidate

    raise RuntimeError("Projektverzeichnis nicht gefunden")


PROJECT_DIR = find_project_dir()

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    from util.state_classifier import classify_snapshot
except Exception:
    classify_snapshot = None  # type: ignore[assignment]


HISTORY_FILE = PROJECT_DIR / "history" / "monitor_history.jsonl"


def load_last_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"History-Datei nicht gefunden: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()

    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue

        parsed = json.loads(line)

        if isinstance(parsed, dict):
            return parsed

    raise RuntimeError(f"Keine gültigen JSONL-Einträge gefunden: {path}")


def format_timestamp(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "?"

    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def snapshot_age_seconds(snapshot: dict[str, Any]) -> int | None:
    timestamp = snapshot.get("timestamp")

    if not isinstance(timestamp, (int, float)):
        return None

    return int(time.time() - timestamp)


def format_age(seconds: int | None) -> str:
    if seconds is None:
        return "?"

    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60

    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"

    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


def bytes_to_gib(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "?"

    return f"{value / 1024**3:.2f} GiB"


def get_model_names(snapshot: dict[str, Any]) -> list[str]:
    models = snapshot.get("ollama_models")

    if not isinstance(models, list):
        return []

    names: list[str] = []

    for model in models:
        if not isinstance(model, dict):
            continue

        name = model.get("name") or model.get("model")

        if isinstance(name, str) and name:
            names.append(name)

    return names


def get_docker_ollama(snapshot: dict[str, Any]) -> dict[str, Any]:
    docker = snapshot.get("docker")

    if not isinstance(docker, dict):
        return {}

    ollama = docker.get("ollama")

    if not isinstance(ollama, dict):
        return {}

    return ollama


def get_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    state = snapshot.get("state")

    if isinstance(state, dict):
        return state

    if classify_snapshot is not None:
        try:
            calculated = classify_snapshot(snapshot)
            if isinstance(calculated, dict):
                return calculated
        except Exception:
            return {}

    return {}


def severity_icon(severity: object) -> str:
    value = str(severity or "").lower()

    if value == "ok":
        return "OK"
    if value == "busy":
        return "BUSY"
    if value == "warning":
        return "WARN"
    if value == "critical":
        return "CRIT"
    if value == "error":
        return "ERR"

    return "INFO"


def print_status(snapshot: dict[str, Any]) -> None:
    model_names = get_model_names(snapshot)
    docker_ollama = get_docker_ollama(snapshot)
    state = get_state(snapshot)

    severity = state.get("severity") or "unknown"
    label = state.get("label") or "unknown"
    summary = state.get("summary") or "Kein Status verfügbar."
    recommendation = state.get("recommendation") or "Keine Empfehlung verfügbar."

    age = snapshot_age_seconds(snapshot)

    print()
    print("AI Monitor Status")
    print("=================")
    print()
    print(f"Status:       {severity_icon(severity)} - {label}")
    print(f"Bewertung:    {summary}")
    print(f"Empfehlung:   {recommendation}")
    print()
    print("Zeit")
    print("----")
    print(f"Snapshot:     {format_timestamp(snapshot.get('timestamp'))}")
    print(f"Alter:        {format_age(age)}")
    print()
    print("Ollama")
    print("------")
    print(f"Modelle:      {', '.join(model_names) if model_names else '-'}")
    print()
    print("GPU")
    print("---")
    print(f"Edge:         {snapshot.get('gpu_temp')} °C")
    print(f"Hotspot:      {snapshot.get('gpu_temp_junction')} °C")
    print(f"Memory:       {snapshot.get('gpu_temp_memory')} °C")
    print(f"GPU Use:      {snapshot.get('gpu_use')} %")
    print(f"Power:        {snapshot.get('power_w')} W")
    print(f"VRAM:         {snapshot.get('vram_percent')} %")
    print(f"VRAM Used:    {bytes_to_gib(snapshot.get('vram_used'))}")
    print(f"VRAM Total:   {bytes_to_gib(snapshot.get('vram_total'))}")
    print(f"GPU Error:    {snapshot.get('gpu_error')}")
    print()
    print("Docker: ollama")
    print("--------------")

    if docker_ollama:
        print(f"CPU:          {docker_ollama.get('cpu_percent')} %")
        print(f"RAM:          {docker_ollama.get('mem_percent')} %")
        print(f"RAM Used:     {bytes_to_gib(docker_ollama.get('mem_used_bytes'))}")
        print(f"RAM Limit:    {bytes_to_gib(docker_ollama.get('mem_limit_bytes'))}")
        print(f"PIDs:         {docker_ollama.get('pids')}")
        print(f"Block I/O:    {docker_ollama.get('block_io_raw')}")
        print(f"Net I/O:      {docker_ollama.get('net_io_raw')}")
        print(f"Error:        {docker_ollama.get('docker_error')}")
    else:
        print("Keine Docker-Stats im letzten Snapshot.")

    print()


def print_json(snapshot: dict[str, Any]) -> None:
    enriched = {
        **snapshot,
        "state": get_state(snapshot),
    }

    print(json.dumps(enriched, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Monitor Statusanzeige")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Letzten Snapshot als JSON ausgeben",
    )
    parser.add_argument(
        "--history-file",
        default=str(HISTORY_FILE),
        help="Pfad zur monitor_history.jsonl",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    history_file = Path(args.history_file)

    snapshot = load_last_snapshot(history_file)

    if args.json:
        print_json(snapshot)
    else:
        print_status(snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())