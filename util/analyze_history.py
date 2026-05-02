#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path("/mnt/ai-bulk/projects/ai-monitor")
HISTORY_FILE = PROJECT_DIR / "history" / "monitor_history.jsonl"


def as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    if value is None:
        return None

    try:
        return float(str(value).strip())
    except ValueError:
        return None


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if not path.exists():
        raise FileNotFoundError(path)

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(row, dict):
            rows.append(row)

    return rows


def filter_recent(rows: list[dict[str, Any]], minutes: int) -> list[dict[str, Any]]:
    cutoff = time.time() - minutes * 60
    result: list[dict[str, Any]] = []

    for row in rows:
        timestamp = row.get("timestamp")
        if isinstance(timestamp, (int, float)) and timestamp >= cutoff:
            result.append(row)

    return result


def filter_since_epoch(rows: list[dict[str, Any]], since_epoch: int | None) -> list[dict[str, Any]]:
    if since_epoch is None:
        return rows

    result: list[dict[str, Any]] = []

    for row in rows:
        timestamp = row.get("timestamp")

        if isinstance(timestamp, (int, float)) and timestamp >= since_epoch:
            result.append(row)

    return result


def format_time(timestamp: object) -> str:
    if not isinstance(timestamp, (int, float)):
        return "?"

    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def get_model_names(row: dict[str, Any]) -> list[str]:
    models = row.get("ollama_models")

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


def max_field(rows: list[dict[str, Any]], field: str) -> tuple[float | None, dict[str, Any] | None]:
    best_value: float | None = None
    best_row: dict[str, Any] | None = None

    for row in rows:
        value = as_float(row.get(field))
        if value is None:
            continue

        if best_value is None or value > best_value:
            best_value = value
            best_row = row

    return best_value, best_row


def count_rows_where(rows: list[dict[str, Any]], field: str, threshold: float) -> int:
    count = 0

    for row in rows:
        value = as_float(row.get(field))
        if value is not None and value >= threshold:
            count += 1

    return count


def estimate_duration_seconds(rows: list[dict[str, Any]], field: str, threshold: float) -> int:
    if len(rows) < 2:
        return 0

    duration = 0

    for current_row, next_row in zip(rows, rows[1:]):
        current_ts = current_row.get("timestamp")
        next_ts = next_row.get("timestamp")

        if not isinstance(current_ts, (int, float)):
            continue
        if not isinstance(next_ts, (int, float)):
            continue

        value = as_float(current_row.get(field))

        if value is not None and value >= threshold:
            duration += max(0, int(next_ts - current_ts))

    return duration


def estimate_active_duration_seconds(rows: list[dict[str, Any]]) -> int:
    if len(rows) < 2:
        return 0

    duration = 0

    for current_row, next_row in zip(rows, rows[1:]):
        current_ts = current_row.get("timestamp")
        next_ts = next_row.get("timestamp")

        if not isinstance(current_ts, (int, float)):
            continue
        if not isinstance(next_ts, (int, float)):
            continue

        gpu_use = as_float(current_row.get("gpu_use"))
        power_w = as_float(current_row.get("power_w"))

        active = (
            (gpu_use is not None and gpu_use >= 10)
            or (power_w is not None and power_w >= 40)
        )

        if active:
            duration += max(0, int(next_ts - current_ts))

    return duration


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"

    minutes = seconds // 60
    rest = seconds % 60

    if minutes < 60:
        return f"{minutes}m {rest}s"

    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


def print_max(label: str, rows: list[dict[str, Any]], field: str, unit: str) -> None:
    value, row = max_field(rows, field)

    if value is None or row is None:
        print(f"{label}: ?")
        return

    print(f"{label}: {value}{unit} um {format_time(row.get('timestamp'))}")


def classify_summary(rows: list[dict[str, Any]]) -> tuple[str, str]:
    max_hotspot, _ = max_field(rows, "gpu_temp_junction")
    max_mem, _ = max_field(rows, "gpu_temp_memory")

    hotspot_95_duration = estimate_duration_seconds(rows, "gpu_temp_junction", 95)
    hotspot_88_duration = estimate_duration_seconds(rows, "gpu_temp_junction", 88)
    mem_88_duration = estimate_duration_seconds(rows, "gpu_temp_memory", 88)

    if hotspot_95_duration >= 30:
        return (
            "CRITICAL",
            "Hotspot war mindestens 30s über 95°C. Last reduzieren oder Schutzaktion prüfen.",
        )

    if hotspot_88_duration >= 60 or mem_88_duration >= 60:
        return (
            "WARN",
            "Temperatur war länger in der Warnzone. Power-Limit/Fan/Kühlung prüfen.",
        )

    if (max_hotspot is not None and max_hotspot >= 95) or (max_mem is not None and max_mem >= 88):
        return (
            "SPIKE",
            "Es gab einen kurzen Temperatur-Spike. Beobachten, aber nicht automatisch als Dauerproblem werten.",
        )

    if (max_hotspot is not None and max_hotspot >= 80) or (max_mem is not None and max_mem >= 80):
        return (
            "WARM",
            "System wurde warm, blieb aber unter nachhaltiger Warnschwelle.",
        )

    return (
        "OK",
        "Keine thermischen Auffälligkeiten im betrachteten Zeitraum.",
    )


def print_recent_tail(rows: list[dict[str, Any]], limit: int = 12) -> None:
    print()
    print("== Letzte Messpunkte ==")

    for row in rows[-limit:]:
        models = ",".join(get_model_names(row)) or "-"

        print(
            f"{format_time(row.get('timestamp'))} | "
            f"edge={row.get('gpu_temp')}°C | "
            f"hotspot={row.get('gpu_temp_junction')}°C | "
            f"mem={row.get('gpu_temp_memory')}°C | "
            f"gpu={row.get('gpu_use')}% | "
            f"vram={row.get('vram_percent')}% | "
            f"power={row.get('power_w')}W | "
            f"models={models}"
        )


def analyze(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("Keine Daten im gewählten Zeitraum.")
        return

    status, recommendation = classify_summary(rows)

    active_duration = estimate_active_duration_seconds(rows)
    hotspot_80_duration = estimate_duration_seconds(rows, "gpu_temp_junction", 80)
    hotspot_88_duration = estimate_duration_seconds(rows, "gpu_temp_junction", 88)
    hotspot_95_duration = estimate_duration_seconds(rows, "gpu_temp_junction", 95)
    mem_80_duration = estimate_duration_seconds(rows, "gpu_temp_memory", 80)
    mem_88_duration = estimate_duration_seconds(rows, "gpu_temp_memory", 88)

    hotspot_spikes_95 = count_rows_where(rows, "gpu_temp_junction", 95)
    power_spikes_330 = count_rows_where(rows, "power_w", 330)

    print("AI Monitor History Analyse")
    print("==========================")
    print()
    print(
        f"Zeitraum:        {format_time(rows[0].get('timestamp'))} "
        f"bis {format_time(rows[-1].get('timestamp'))}"
    )
    print(f"Messpunkte:      {len(rows)}")
    print(f"Bewertung:       {status}")
    print(f"Empfehlung:      {recommendation}")
    print()
    print("== Maximalwerte ==")
    print_max("Max Edge", rows, "gpu_temp", "°C")
    print_max("Max Hotspot", rows, "gpu_temp_junction", "°C")
    print_max("Max Memory", rows, "gpu_temp_memory", "°C")
    print_max("Max GPU Use", rows, "gpu_use", "%")
    print_max("Max Power", rows, "power_w", "W")
    print_max("Max VRAM", rows, "vram_percent", "%")
    print()
    print("== Dauerbereiche ==")
    print(f"Aktive Last:     {format_duration(active_duration)}")
    print(f"Hotspot >= 80°C: {format_duration(hotspot_80_duration)}")
    print(f"Hotspot >= 88°C: {format_duration(hotspot_88_duration)}")
    print(f"Hotspot >= 95°C: {format_duration(hotspot_95_duration)}")
    print(f"Memory >= 80°C:  {format_duration(mem_80_duration)}")
    print(f"Memory >= 88°C:  {format_duration(mem_88_duration)}")
    print()
    print("== Spikes ==")
    print(f"Hotspot >= 95°C Messpunkte: {hotspot_spikes_95}")
    print(f"Power >= 330W Messpunkte:   {power_spikes_330}")

    print_recent_tail(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analysiert AI-Monitor-History")

    parser.add_argument(
        "--minutes",
        type=int,
        default=30,
        help="Nur die letzten N Minuten analysieren",
    )

    parser.add_argument(
        "--since-epoch",
        type=int,
        default=None,
        help="Nur Messpunkte ab diesem Unix-Timestamp analysieren",
    )

    parser.add_argument(
        "--history-file",
        default=str(HISTORY_FILE),
        help="Pfad zur monitor_history.jsonl",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    rows = load_rows(Path(args.history_file))

    if args.since_epoch is not None:
        rows = filter_since_epoch(rows, args.since_epoch)
    else:
        rows = filter_recent(rows, args.minutes)

    analyze(rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())