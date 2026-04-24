import json
import sys
from collections import Counter
from pathlib import Path

HISTORY_FILE = Path(
    "/mnt/ai-bulk/projects/ai-monitor/history/monitor_history.jsonl"
)


def analyze_history() -> None:
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
                print(
                    f"Warnung: Zeile {line_num} ignoriert (ungültiges JSON): {exc}",
                    file=sys.stderr,
                )
                continue

    if not entries:
        print("Keine gültigen Einträge gefunden.")
        return

    print(f"Anzahl der Einträge: {len(entries)}")

    timestamps = [entry["ts"] for entry in entries if entry.get("ts")]
    first_ts = min(timestamps)
    last_ts = max(timestamps)
    print(f"Zeitraum: {first_ts} bis {last_ts}")

    last_entry = entries[-1]
    print("\nLetzter Eintrag:")
    print(f"  Zeitstempel: {last_entry.get('ts')}")
    print(f"  Modell: {last_entry.get('model')}")
    print(
        f"  VRAM: {last_entry.get('vram_used_gib', 0):.2f}/"
        f"{last_entry.get('vram_total_gib', 0):.2f} GiB"
    )
    print(f"  Temperatur (Hotspot): {last_entry.get('temp_hotspot_c', 0):.1f} °C")
    print(f"  GPU-Nutzung: {last_entry.get('gpu_use_percent')} %")
    print(f"  Leistung: {last_entry.get('power_w')} W")
    print(f"  Thermal-Zustand: {last_entry.get('thermal_state')}")

    temps = [e["temp_hotspot_c"] for e in entries if e.get("temp_hotspot_c") is not None]
    powers = [e["power_w"] for e in entries if e.get("power_w") is not None]
    vrams = [e["vram_used_gib"] for e in entries if e.get("vram_used_gib") is not None]

    if temps:
        print(f"\nMin/Max Temperaturen (Hotspot): {min(temps):.1f} °C / {max(temps):.1f} °C")
        print(f"Durchschnitt Hotspot: {sum(temps) / len(temps):.1f} °C")

    if powers:
        print(f"Min/Max Leistung: {min(powers):.1f} W / {max(powers):.1f} W")
        print(f"Durchschnitt Leistung: {sum(powers) / len(powers):.1f} W")

    if vrams:
        print(f"Min/Max VRAM-Nutzung: {min(vrams):.2f} GiB / {max(vrams):.2f} GiB")
        print(f"Durchschnitt VRAM-Nutzung: {sum(vrams) / len(vrams):.2f} GiB")

    models = [e.get("model") for e in entries]
    model_counts = Counter(models)

    print("\nModellhäufigkeit:")
    for model, count in model_counts.most_common():
        label = model if model is not None else "<kein Modell geladen>"
        print(f"  {label}: {count}")

    thermal_states = [e.get("thermal_state") for e in entries if e.get("thermal_state") is not None]
    state_counts = Counter(thermal_states)

    print("\nThermal-Zustände:")
    for state, count in state_counts.most_common():
        print(f"  {state}: {count}")

    unloaded_count = sum(1 for e in entries if e.get("model_unloaded") is True)
    print(f"\nEinträge mit entladenem Modell: {unloaded_count}")

    # Zähle Modellwechsel
    model_changes = 0
    previous_model = None
    for entry in entries:
        current_model = entry.get("model")
        if previous_model is not None and current_model != previous_model:
            model_changes += 1
        previous_model = current_model

    print(f"Modellwechsel erkannt: {model_changes}")

    # Zähle explizit markierte Modellwechsel
    explicit_model_changes = sum(1 for e in entries if e.get("model_changed") is True)
    print(f"Explizit markierte Modellwechsel: {explicit_model_changes}")


if __name__ == "__main__":
    analyze_history()
