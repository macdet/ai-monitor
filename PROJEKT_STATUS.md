---
title: AI Monitor Projekt Status
version: 1.0
---

# AI Monitor Projekt Status

## 1. Übersicht aller Module und ihre Funktion

### Hauptmodule

- **monitor.py**: Hauptüberwachungslogik
  - Sammelt GPU-Statistiken, Docker-Stats und Ollama-Modelle
  - Klassifiziert den Systemzustand
  - Schreibt Daten in History-Datei
  - Gibt Live-Ausgabe im Terminal aus

- **util.gpu_stats**: GPU-Statistik-Sammlung
  - Ruft GPU-Informationen mit rocm-smi ab
  - Erkennt Fehler und thermische Probleme

- **util.docker_stats**: Docker-Container-Überwachung
  - Sammelt Status- und Health-Informationen von Containern
  - Überwacht spezifische Container (ollama, anythingllm, etc.)

- **util.state_classifier**: Zustandsklassifizierung
  - Bewertet Sammlung zur Ermittlung des aktuellen Systemzustands
  - Definiert verschiedene Zustände (aktiv, idle, kritisch, etc.)
  - Gibt Empfehlungen basierend auf dem Zustand

### Konfiguration

- **.env**: Umgebungsvariablen für ntfy-Einstellungen
- **history/monitor_history.jsonl**: Speichert historische Daten
- **monitor.py**: Hauptscript zur Ausführung

## 2. Wie man den Monitor startet und stoppt

### Starten

```bash
# Standardstart ( kontinuierliche Überwachung)
python monitor.py

# Einmaliger Snapshot
python monitor.py --once

# Mit spezifischem Intervall (z.B. 10 Sekunden)
python monitor.py --interval 10

# Ohne Live-Ausgabe
python monitor.py --quiet

# Einzelne Ausführung mit Stille
python monitor.py --once --quiet
```

### Stoppen

Der Monitor wird mit `Ctrl+C` beendet.

## 3. Wie man die gesammelten Werte ansieht

### History-Datei

Die historischen Daten werden in `history/monitor_history.jsonl` gespeichert.

```bash
# Anzeigen der letzten 10 Einträge
tail -n 10 history/monitor_history.jsonl

# Anzeigen aller Einträge
cat history/monitor_history.jsonl

# Filtern nach Zustand
grep "active_inference" history/monitor_history.jsonl
```

### CLI-Ausgabe

Die Live-Ausgabe zeigt aktuelle Werte an:

```
2025-01-01 12:00:00 | edge=65°C | hotspot=72°C | mem=68°C | gpu=45% | vram=32% | power=120W | models=llama3:8b,phi3:3b | error=- | docker_error=-
```

### Verarbeitung historischer Daten

Ein einfacher Skript zur Analyse der History:

```bash
# Umrechnung in CSV für Tabellenverarbeitung
python -c "
import json
import sys
with open('history/monitor_history.jsonl') as f:
    for line in f:
        data = json.loads(line)
        print(f'{data[\"timestamp\"]},{data.get(\"gpu_temp\", \"-\")},{data.get(\"vram_percent\", \"-\" )}')
"
```

## 4. Was bereits ausgewertet wird und was noch fehlt

### Bereits ausgewertet

- GPU-Temperatur (edge, hotspot, memory)
- GPU-Auslastung (%)
- VRAM-Auslastung (%)
- Leistungsaufnahme (W)
- Aktive Ollama-Modelle
- Docker-Status von Containern
- Thermische Warnungen
- Kritische Zustände (überhitzen)
- Modell-Idle-Zustände
- Fehlermeldungen

### Noch fehlende Auswertungen

- CPU-Auslastung
- Netzwerk-Nutzung
- Speicher (RAM) Auslastung
- CPU-Temperatur
- Container-Ressourcennutzung (CPU, RAM)
- Modell-Performance-Indikatoren
- Spezifische Ollama-Modelle-Details

## 5. Offene TODOs als Checkboxen

- [x] Grundlegende GPU-Überwachung implementiert
- [x] Docker-Container-Überwachung implementiert
- [x] Ollama-Model-Überwachung implementiert
- [x] Zustandsklassifizierung implementiert
- [x] Historische Daten-Speicherung implementiert
- [x] Live-CLI-Ausgabe implementiert
- [ ] CPU-Auslastung hinzufügen
- [ ] CPU-Temperatur hinzufügen
- [ ] RAM-Nutzung hinzufügen
- [ ] Container-Ressourcennutzung (CPU, RAM) hinzufügen
- [ ] Netzwerk-Nutzung hinzufügen
- [ ] Spezifische Ollama-Modelle-Details hinzufügen
- [ ] Modell-Performance-Indikatoren hinzufügen
- [ ] Verbesserte Benachrichtigungssysteme (ntfy)
- [ ] Webinterface für Historische Daten
- [ ] Export-Funktionen für Analysen