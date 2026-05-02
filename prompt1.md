# Prompt: Thermal-Policy Review & Verbesserung

Du bist ein strenger Senior-Python-Reviewer und arbeitest in meinem lokalen Projekt `ai-monitor`.

Wichtig:
- Antworte immer auf Deutsch.
- Arbeite defensiv und in kleinen Schritten.
- Ändere nur Dateien, die für diese Aufgabe nötig sind.
- Keine großen Refactorings.
- Keine Formatierungsorgien.
- Lies zuerst den vorhandenen Code und vorhandene Tests.
- Ändere erst Dateien, nachdem du kurz erklärt hast, was du ändern willst.
- Ziel ist robuste Produktionsnähe, nicht maximale Eleganz.

Kontext:
Dieses Projekt überwacht eine AMD-GPU in einer Proxmox/VM/Ollama-Umgebung.
Die Datei `util/thermal_policy.py` bewertet GPU-Temperaturen und entscheidet, ob gewarnt oder ein Ollama-Modell entladen werden soll.

Aktuell soll besonders diese Datei geprüft und verbessert werden:

`util/thermal_policy.py`

Die bestehende Logik:
- warn ab ca. 85 °C
- critical ab ca. 90 °C
- unload erst nach mehreren kritischen Messungen
- recovery/ok erst unter ca. 80 °C
- Hysterese soll erhalten bleiben

Aufgabe:

## 1. Analyse
Analysiere zuerst `util/thermal_policy.py`.
Erkläre kurz:
- was die aktuelle Klasse macht
- wie die Hysterese funktioniert
- wann `should_warn` gesetzt wird
- wann `should_unload` gesetzt wird
- welche Schwachstellen du konkret siehst

Ändere in diesem ersten Schritt noch nichts, außer du musst Dateien nur lesen.

## 2. Verbesserungsplan
Erstelle danach einen kleinen Änderungsplan mit maximal 5 Punkten.

Die Zielverbesserungen sind:

- Parameter im `__init__` validieren:
  - `recover_temp_c < warn_temp_c < critical_temp_c`
  - `critical_hits_needed >= 1`
  - `history_size >= critical_hits_needed`

- Temperaturwerte robuster behandeln:
  - `NaN` ignorieren
  - `inf` ignorieren
  - `bool` nicht als Temperatur akzeptieren
  - `int` und `float` akzeptieren
  - nur endliche echte Zahlen verwenden

- Sensorfelder berücksichtigen:
  - `temperature_edge`
  - `temperature_hotspot`
  - `temperature_memory`

- Weiterhin konservativ den höchsten gültigen Temperaturwert verwenden.

- Bestehende öffentliche Struktur möglichst behalten:
  - `ThermalDecision`
  - `ThermalPolicy`
  - `evaluate(...)`
  - `_pick_temperature(...)`

- Keine externen Abhängigkeiten einführen.

## 3. Umsetzung
Setze die Verbesserungen in `util/thermal_policy.py` um.

Achte auf:
- klare Typen
- einfache Lesbarkeit
- keine unnötige Komplexität
- stabile Fehlermeldungen bei ungültiger Konfiguration
- keine Änderung an unrelated files

## 4. Tests
Prüfe, ob es bereits Tests gibt.

Falls Tests existieren:
- ergänze passende Tests für `ThermalPolicy`

Falls noch keine passenden Tests.existieren:
- lege eine kleine pytest-Datei an, z. B. `test_thermal_policy.py` oder passend zur bestehenden Projektstruktur

Die Tests sollen mindestens abdecken:

1. OK-Zustand bei normaler Temperatur
2. Warnzustand ab `warn_temp_c`
3. Critical-Zustand ab `critical_temp_c`
4. `should_unload` erst nach `critical_hits_needed` kritischen Messungen
5. Recovery erst unter `recover_temp_c`
6. `unknown`, wenn keine Temperatur verfügbar ist
7. `NaN` wird ignoriert
8. `inf` wird ignoriert
9. `bool` wird ignoriert
10. `temperature_memory` wird berücksichtigt
11. höchster gültiger Sensorwert wird verwendet
12. ungültige Schwellenwerte werfen `ValueError`
13. `critical_hits_needed < 1` wirft `ValueError`
14. `history_size < critical_hits_needed` wirft `ValueError`

## 5. Prüfung
Führe nach Möglichkeit die passenden Tests aus.

Wenn du keine Befehle ausführen darfst oder eine Erlaubnis brauchst:
- nenne exakt den Befehl
- erkläre kurz, warum er nötig ist

Geeignete Befehle könnten sein:
- `pytest`
- `pytest -q`
- `pytest -q test_thermal_policy.py`
- oder der passende Pfad, falls Tests in einem Unterordner liegen

## 6. Abschlussbericht
Am Ende liefere bitte:

- geänderte Dateien
- kurze Zusammenfassung der Änderungen
- welche Schwachstellen behoben wurden
- welche Tests ergänzt wurden
- welche Tests erfolgreich liefen oder noch manuell auszuführen sind
- welche offenen Risiken bleiben

Wichtig:
Wenn du unsicher bist, lies zuerst weitere relevante Dateien wie:
- `monitor_loop.py`
- `util/gpu_stats.py`
- vorhandene Tests
- README oder Projektkonventionen

Aber ändere nur, was für diese Aufgabe wirklich nötig ist.
