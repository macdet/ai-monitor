#!/usr/bin/env python3
"""
Analysiert AI-Monitor-History nach getrennten Lastphasen.

Ziel:
- Default-, 300W- und 285W-Läufe nicht vermischen
- Power-Spikes sichtbar machen
- Hotspot-Dauerbereiche pro Lastphase ausgeben
- thermisch problematische Läufe klar markieren
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from statistics import mean
from typing import Any


DEFAULT_HISTORY_FILE = "history/monitor_history.jsonl"

# Wann gilt ein Messpunkt als aktive Last?
ACTIVE_GPU_USE_MIN = 20.0
ACTIVE_POWER_MIN_W = 80.0

# Maximale Lücke zwischen aktiven Messpunkten innerhalb derselben Lastphase.
MAX_GAP_SECONDS = 45.0

# Temperatur-Schwellen
HOTSPOT_WARM_C = 80.0
HOTSPOT_WARN_C = 88.0
HOTSPOT_CRIT_C = 95.0

MEMORY_WARM_C = 80.0
MEMORY_WARN_C = 88.0

# Power-Spike-Schwelle
POWER_SPIKE_W = 330.0


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def fmt_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def fmt_float(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def clean_numbers(values: list[Any]) -> list[float]:
    return [float(v) for v in values if is_number(v)]


def percentile(values: list[Any], p: float) -> float | None:
    clean = sorted(clean_numbers(values))
    if not clean:
        return None

    index = int((len(clean) - 1) * p / 100)
    return clean[index]


def average(values: list[Any]) -> float | None:
    clean = clean_numbers(values)
    if not clean:
        return None
    return mean(clean)


def maximum(values: list[Any]) -> float | None:
    clean = clean_numbers(values)
    if not clean:
        return None
    return max(clean)


def load_rows(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with open(path, "r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = obj.get("timestamp")
            if not is_number(ts):
                continue

            ts = float(ts)

            # Sicherheit, falls irgendwann Millisekunden gespeichert werden.
            if ts > 10_000_000_000:
                ts = ts / 1000

            models = obj.get("ollama_models") or []
            model_name = ""

            if models and isinstance(models[0], dict):
                model_name = models[0].get("name") or models[0].get("model") or ""

            state = obj.get("state") or {}
            state_label = state.get("label") if isinstance(state, dict) else ""

            rows.append(
                {
                    "line": line_no,
                    "timestamp": ts,
                    "gpu_temp": obj.get("gpu_temp"),
                    "hotspot": obj.get("gpu_temp_junction"),
                    "memory_temp": obj.get("gpu_temp_memory"),
                    "gpu_use": obj.get("gpu_use"),
                    "power_w": obj.get("power_w"),
                    "vram_percent": obj.get("vram_percent"),
                    "state_label": state_label or "",
                    "model": model_name,
                }
            )

    rows.sort(key=lambda row: row["timestamp"])
    return rows


def is_active(row: dict[str, Any]) -> bool:
    gpu_use = row.get("gpu_use")
    power_w = row.get("power_w")
    state_label = str(row.get("state_label") or "")

    if is_number(gpu_use) and gpu_use >= ACTIVE_GPU_USE_MIN:
        return True

    if is_number(power_w) and power_w >= ACTIVE_POWER_MIN_W:
        return True

    if state_label.startswith("active_"):
        return True

    if state_label.startswith("thermal_"):
        return True

    return False


def split_segments(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    segments: list[list[dict[str, Any]]] = []

    current: list[dict[str, Any]] = []
    last_active_ts: float | None = None

    for row in rows:
        if not is_active(row):
            continue

        ts = row["timestamp"]

        if current and last_active_ts is not None:
            gap = ts - last_active_ts
            if gap > MAX_GAP_SECONDS:
                segments.append(current)
                current = []

        current.append(row)
        last_active_ts = ts

    if current:
        segments.append(current)

    return segments


def seconds_over(segment: list[dict[str, Any]], key: str, limit: float) -> int:
    total = 0.0

    for current, nxt in zip(segment, segment[1:]):
        value = current.get(key)
        dt = nxt["timestamp"] - current["timestamp"]

        if dt <= 0 or dt > MAX_GAP_SECONDS:
            continue

        if is_number(value) and value >= limit:
            total += dt

    return int(total)


def count_over(segment: list[dict[str, Any]], key: str, limit: float) -> int:
    count = 0

    for row in segment:
        value = row.get(key)
        if is_number(value) and value >= limit:
            count += 1

    return count


def guess_profile(
    power_avg: float | None,
    power_p75: float | None,
    power_p95: float | None,
    power_max: float | None,
    spike_count: int,
    hotspot_88s: int,
    hotspot_95s: int,
) -> str:
    """
    Schätzt das Profil einer Lastphase.

    Wichtig:
    - p95/max zeigen Spikes.
    - avg/p75 zeigen eher die nachhaltige Last.
    - Thermik wird separat stark gewichtet.
    """

    if power_avg is None and power_p75 is None and power_p95 is None and power_max is None:
        return "unklar"

    sustained = power_p75 if power_p75 is not None else power_avg

    if hotspot_95s > 0:
        return "thermisch kritisch"

    if hotspot_88s >= 60:
        return "thermisch warnend"

    if sustained is None:
        return "unklar"

    has_spikes = spike_count > 0

    if sustained >= 330:
        return "Default/uncapped"

    if 292 <= sustained < 330:
        if has_spikes:
            return "300W-Kandidat mit Spikes"
        return "300W-Kandidat"

    if 260 <= sustained < 292:
        if has_spikes:
            return "285W-Kandidat mit Spikes"
        return "285W-Kandidat"

    if 220 <= sustained < 260:
        if has_spikes:
            return "unter 285W / Teillast mit Spikes"
        return "unter 285W / Teillast"

    if sustained < 220:
        return "kurze/unklare Teillast"

    return "unklar"


def summarize_segment(segment: list[dict[str, Any]], index: int) -> dict[str, Any]:
    start_ts = segment[0]["timestamp"]
    end_ts = segment[-1]["timestamp"]

    powers = [row.get("power_w") for row in segment]
    hotspots = [row.get("hotspot") for row in segment]
    edge_temps = [row.get("gpu_temp") for row in segment]
    mem_temps = [row.get("memory_temp") for row in segment]
    gpu_uses = [row.get("gpu_use") for row in segment]
    vram_values = [row.get("vram_percent") for row in segment]

    power_avg = average(powers)
    power_p50 = percentile(powers, 50)
    power_p75 = percentile(powers, 75)
    power_p95 = percentile(powers, 95)
    power_max = maximum(powers)

    hotspot_80s = seconds_over(segment, "hotspot", HOTSPOT_WARM_C)
    hotspot_88s = seconds_over(segment, "hotspot", HOTSPOT_WARN_C)
    hotspot_95s = seconds_over(segment, "hotspot", HOTSPOT_CRIT_C)

    memory_80s = seconds_over(segment, "memory_temp", MEMORY_WARM_C)
    memory_88s = seconds_over(segment, "memory_temp", MEMORY_WARN_C)

    spike_count = count_over(segment, "power_w", POWER_SPIKE_W)
    model = next((row.get("model") for row in segment if row.get("model")), "-")

    return {
        "id": index,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "start": fmt_time(start_ts),
        "end": fmt_time(end_ts),
        "duration_seconds": int(end_ts - start_ts),
        "duration": fmt_duration(end_ts - start_ts),
        "samples": len(segment),
        "model": model,
        "power_avg": power_avg,
        "power_p50": power_p50,
        "power_p75": power_p75,
        "power_p95": power_p95,
        "power_max": power_max,
        "power_spikes": spike_count,
        "edge_max": maximum(edge_temps),
        "hotspot_avg": average(hotspots),
        "hotspot_max": maximum(hotspots),
        "hotspot_80s": hotspot_80s,
        "hotspot_88s": hotspot_88s,
        "hotspot_95s": hotspot_95s,
        "memory_max": maximum(mem_temps),
        "memory_80s": memory_80s,
        "memory_88s": memory_88s,
        "gpu_use_max": maximum(gpu_uses),
        "vram_max": maximum(vram_values),
        "profile_guess": guess_profile(
            power_avg=power_avg,
            power_p75=power_p75,
            power_p95=power_p95,
            power_max=power_max,
            spike_count=spike_count,
            hotspot_88s=hotspot_88s,
            hotspot_95s=hotspot_95s,
        ),
    }


def print_table(summaries: list[dict[str, Any]]) -> None:
    print("AI Monitor Lastphasen Analyse")
    print("=============================")
    print()

    if not summaries:
        print("Keine Lastphasen gefunden.")
        return

    print(
        "ID | Start               | Dauer   | Samples | "
        "Power avg/p75/p95/max | Hotspot avg/max | >=88C | >=95C | Spikes | Profil"
    )
    print(
        "---|---------------------|---------|---------|"
        "------------------------|-----------------|-------|-------|--------|--------------------------"
    )

    for item in summaries:
        print(
            f"{item['id']:2d} | "
            f"{item['start']} | "
            f"{item['duration']:<7} | "
            f"{item['samples']:7d} | "
            f"{fmt_float(item['power_avg'])}/"
            f"{fmt_float(item['power_p75'])}/"
            f"{fmt_float(item['power_p95'])}/"
            f"{fmt_float(item['power_max'])} W | "
            f"{fmt_float(item['hotspot_avg'])}/"
            f"{fmt_float(item['hotspot_max'])} C | "
            f"{fmt_duration(item['hotspot_88s']):>5} | "
            f"{fmt_duration(item['hotspot_95s']):>5} | "
            f"{item['power_spikes']:6d} | "
            f"{item['profile_guess']}"
        )


def print_details(summaries: list[dict[str, Any]]) -> None:
    print()
    print("Details")
    print("=======")

    for item in summaries:
        print()
        print(f"== Lastphase {item['id']} ==")
        print(f"Start:           {item['start']}")
        print(f"Ende:            {item['end']}")
        print(f"Dauer:           {item['duration']}")
        print(f"Samples:         {item['samples']}")
        print(f"Modell:          {item['model']}")
        print(f"Profil:          {item['profile_guess']}")
        print()
        print(f"Power avg:       {fmt_float(item['power_avg'])}W")
        print(f"Power p50:       {fmt_float(item['power_p50'])}W")
        print(f"Power p75:       {fmt_float(item['power_p75'])}W")
        print(f"Power p95:       {fmt_float(item['power_p95'])}W")
        print(f"Power max:       {fmt_float(item['power_max'])}W")
        print(f"Power >={int(POWER_SPIKE_W)}W:   {item['power_spikes']} Messpunkte")
        print()
        print(f"Edge max:        {fmt_float(item['edge_max'])}°C")
        print(f"Hotspot avg:     {fmt_float(item['hotspot_avg'])}°C")
        print(f"Hotspot max:     {fmt_float(item['hotspot_max'])}°C")
        print(f"Hotspot >=80°C:  {fmt_duration(item['hotspot_80s'])}")
        print(f"Hotspot >=88°C:  {fmt_duration(item['hotspot_88s'])}")
        print(f"Hotspot >=95°C:  {fmt_duration(item['hotspot_95s'])}")
        print()
        print(f"Memory max:      {fmt_float(item['memory_max'])}°C")
        print(f"Memory >=80°C:   {fmt_duration(item['memory_80s'])}")
        print(f"Memory >=88°C:   {fmt_duration(item['memory_88s'])}")
        print()
        print(f"GPU Use max:     {fmt_float(item['gpu_use_max'])}%")
        print(f"VRAM max:        {fmt_float(item['vram_max'])}%")


def print_summary(summaries: list[dict[str, Any]]) -> None:
    if not summaries:
        return

    critical = [item for item in summaries if item["hotspot_95s"] > 0]
    warning = [
        item
        for item in summaries
        if item["hotspot_95s"] == 0 and item["hotspot_88s"] >= 60
    ]
    stable = [
        item
        for item in summaries
        if item["hotspot_88s"] == 0 and item["hotspot_95s"] == 0
    ]

    print()
    print("Kurzfazit")
    print("=========")
    print(f"Lastphasen gesamt:       {len(summaries)}")
    print(f"Thermisch kritisch:      {len(critical)}")
    print(f"Thermisch warnend:       {len(warning)}")
    print(f"Ohne Hotspot >=88°C:     {len(stable)}")

    if critical:
        ids = ", ".join(str(item["id"]) for item in critical)
        print(f"Kritische IDs:           {ids}")

    if warning:
        ids = ", ".join(str(item["id"]) for item in warning)
        print(f"Warnende IDs:            {ids}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analysiert AI-Monitor-History nach getrennten Lastphasen"
    )

    parser.add_argument(
        "--history-file",
        default=DEFAULT_HISTORY_FILE,
        help="Pfad zur monitor_history.jsonl",
    )

    parser.add_argument(
        "--minutes",
        type=int,
        help="Nur die letzten N Minuten analysieren",
    )

    parser.add_argument(
        "--since-epoch",
        type=float,
        help="Nur Messpunkte ab diesem Unix-Timestamp analysieren",
    )

    parser.add_argument(
        "--details",
        action="store_true",
        help="Zusätzlich Detailausgabe pro Lastphase anzeigen",
    )

    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Kurzfazit unterdrücken",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    rows = load_rows(args.history_file)

    if args.since_epoch is not None:
        rows = [row for row in rows if row["timestamp"] >= args.since_epoch]

    if args.minutes is not None:
        cutoff = time.time() - args.minutes * 60
        rows = [row for row in rows if row["timestamp"] >= cutoff]

    if not rows:
        print("Keine Messpunkte im gewählten Zeitraum gefunden.")
        return 1

    segments = split_segments(rows)
    summaries = [
        summarize_segment(segment, index)
        for index, segment in enumerate(segments, 1)
    ]

    print_table(summaries)

    if not args.no_summary:
        print_summary(summaries)

    if args.details:
        print_details(summaries)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
