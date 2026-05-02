#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from util.gpu_stats import collect_gpu_stats
from util.docker_stats import collect_docker_stats
from util.state_classifier import classify_snapshot


PROJECT_DIR = Path(__file__).resolve().parent
HISTORY_FILE = PROJECT_DIR / "history" / "monitor_history.jsonl"
OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"

RUNNING = True


def handle_stop_signal(signum: int, frame: object) -> None:
    global RUNNING
    RUNNING = False


def collect_ollama_models() -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(OLLAMA_PS_URL, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))

        models = payload.get("models", [])
        if isinstance(models, list):
            return models

        return []

    except Exception:
        return []


def collect_system_stats() -> dict[str, Any]:
    """Collect CPU load, RAM usage, and CPU temperature."""
    system_stats: dict[str, Any] = {
        "cpu_percent": None,
        "ram_total": None,
        "ram_available": None,
        "ram_used": None,
        "ram_percent": None,
        "cpu_temp": None,
        "error": None,
    }

    if not PSUTIL_AVAILABLE:
        system_stats["error"] = "psutil_not_available"
        return system_stats

    try:
        # CPU load percentage
        system_stats["cpu_percent"] = psutil.cpu_percent(interval=1)
        
        # RAM usage
        ram = psutil.virtual_memory()
        system_stats["ram_total"] = ram.total
        system_stats["ram_available"] = ram.available
        system_stats["ram_used"] = ram.used
        system_stats["ram_percent"] = ram.percent
        
        # CPU temperature (if available)
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                # Get the first available temperature sensor
                for sensor_name, sensor_data in temps.items():
                    if sensor_data:
                        # Try to get coretemp or similar
                        if 'coretemp' in sensor_name.lower() or 'cpu' in sensor_name.lower():
                            # Get the first temperature reading
                            if sensor_data:
                                system_stats["cpu_temp"] = sensor_data[0].current
                                break
                # If no coretemp found, try first sensor
                if system_stats["cpu_temp"] is None and temps:
                    first_sensor = next(iter(temps.values()))
                    if first_sensor:
                        system_stats["cpu_temp"] = first_sensor[0].current
        except Exception:
            # CPU temperature not available
            system_stats["cpu_temp"] = None
            
    except Exception as exc:
        system_stats["error"] = f"system_stats_failed: {exc!r}"
        return system_stats

    return system_stats


def build_snapshot() -> dict[str, Any]:
    gpu = collect_gpu_stats()
    system_stats = collect_system_stats()

    snapshot: dict[str, Any] = {
        "timestamp": int(time.time()),
        **gpu,
        **system_stats,
        "ollama_models": collect_ollama_models(),
        "docker": collect_docker_stats(["ollama"]),
    }

    snapshot["state"] = classify_snapshot(snapshot)

    return snapshot

def append_snapshot(snapshot: dict[str, Any]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with HISTORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def print_snapshot(snapshot: dict[str, Any]) -> None:
    models = snapshot.get("ollama_models") or []
    model_names = [
        model.get("name") or model.get("model") or "?"
        for model in models
        if isinstance(model, dict)
    ]

    print(
        " | ".join(
            [
                time.strftime("%Y-%m-%d %H:%M:%S"),
                f"edge={snapshot.get('gpu_temp')}°C",
                f"hotspot={snapshot.get('gpu_temp_junction')}°C",
                f"mem={snapshot.get('gpu_temp_memory')}°C",
                f"gpu={snapshot.get('gpu_use')}%",
                f"vram={snapshot.get('vram_percent')}%",
                f"power={snapshot.get('power_w')}W",
                f"cpu={snapshot.get('cpu_percent')}%",
                f"ram={snapshot.get('ram_percent')}%",
                f"cpu_temp={snapshot.get('cpu_temp')}°C",
                f"models={','.join(model_names) if model_names else '-'}",
                f"error={snapshot.get('gpu_error')}",
                f"docker_error={snapshot.get('docker_error')}",
            ]
        ),
        flush=True,
    )


def run_monitor(interval: float, once: bool, quiet: bool = False) -> None:
    while RUNNING:
        snapshot = build_snapshot()
        append_snapshot(snapshot)

        if not quiet:
            print_snapshot(snapshot)

        if once:
            break

        time.sleep(interval)

        
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Monitor JSONL writer")
    parser.add_argument(
    "--quiet",
    action="store_true",
    help="Snapshots schreiben, aber keine Live-Ausgabe im Terminal anzeigen",
)
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Messintervall in Sekunden",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Nur einen Snapshot schreiben und beenden",
    )
    return parser.parse_args()


def main() -> int:
    signal.signal(signal.SIGINT, handle_stop_signal)
    signal.signal(signal.SIGTERM, handle_stop_signal)

    args = parse_args()
    run_monitor(interval=args.interval, once=args.once, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())