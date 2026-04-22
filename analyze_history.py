# analyze_history.py

import json
import sys
from datetime import datetime
from collections import Counter
from pathlib import Path

HISTORY_FILE = Path(
    "/mnt/ai-bulk/projects/ai-monitor/history/monitor_history.jsonl"
)

def analyze_history():
    entries = []
    with HISTORY_FILE.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError as exc:
                print(f"Warnung: Zeile {line_num} ignoriert (ungültiges JSON): {exc}", file=sys.stderr)
                continue

    if not entries:
        print("Keine gültigen Einträge gefunden.")
        return

    print(f"Anzahl der Einträge: {len(entries)}")
    
    timestamps = [entry["ts"] for entry in entries]
    first_ts = min(timestamps)
    last_ts = max(timestamps)
    print(f"Zeitraum: {first_ts} bis {last_ts}")

    last_entry = entries[-1]
    print("\nLetzter Eintrag:")
    print(f"  Zeitstempel: {last_entry['ts']}")
    print(f"  Modell: {last_entry['model']}")
    print(f"  VRAM: {last_entry['vram_used_gib']:.2f}/{last_entry['vram_total_gib']:.2f} GiB")
    print(f"  Temperatur (Hotspot): {last_entry['temp_hotspot_c']:.1f} °C")
    print(f"  GPU-Nutzung: {last_entry['gpu_use_percent']} %")
    print(f"  Leistung: {last_entry['power_w']} W")
    print(f"  Thermal-Zustand: {last_entry['thermal_state']}")

    temps = [e["temp_hotspot_c"] for e in entries if e["temp_hotspot_c"] is not None]
    powers = [e["power_w"] for e in entries if e["power_w"] is not None]
    vrams = [e["vram_used_gib"] for e in entries if e["vram_used_gib"] is not None]

    if temps:
        print(f"\nMin/Max Temperaturen (Hotspot): {min(temps):.1f} °C / {max(temps):.1f} °C")
    if powers:
        print(f"Min/Max Leistung: {min(powers):.1f} W / {max(powers):.1f} W")
    if vrams:
        print(f"Min/Max VRAM-Nutzung: {min(vrams):.2f} GiB / {max(vrams):.2f} GiB")

    models = [e["model"] for e in entries if e["model"] is not None]
    model_counts = Counter(models)
    print("\nModellhäufigkeit:")
    for model, count in model_counts.most_common():
        print(f"  {model}: {count}")

    thermal_states = [e["thermal_state"] for e in entries]
    state_counts = Counter(thermal_states)
    print("\nThermal-Zustände:")
    for state, count in state_counts.most_common():
        print(f"  {state}: {count}")

    unloaded_count = sum(1 for e in entries if e.get("model_unloaded") is True)
    print(f"\nEinträge mit entladener Model: {unloaded_count}")

if __name__ == "__main__":
    analyze_history()
