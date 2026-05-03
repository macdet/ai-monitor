# AI-Monitor Projektregeln für OpenCode


Monitor für GPU, Ollama, Docker auf ai-debian.

## Test
python -c "from util import system_stats; print(system_stats.get_system_stats())"

## Entry point
python monitor.py

## Sprache

- Antworte dem Nutzer immer auf Deutsch.
- Auch Zusammenfassungen, Pläne, Rückfragen und Abschlussberichte müssen auf Deutsch sein.
- Code, Dateinamen, Befehle, Fehlermeldungen und API-Namen bleiben im Original.
- Interne Toolnamen dürfen Englisch bleiben.

## Arbeitsweise

- Arbeite defensiv und in kleinen Schritten.
- Lies zuerst relevante Dateien, bevor du Änderungen vorschlägst.
- Ändere Dateien nur, wenn die Aufgabe ausdrücklich eine Umsetzung verlangt.
- Vor Änderungen: kurz erklären, welche Dateien geändert werden sollen und warum.
- Keine großen Refactorings ohne ausdrückliche Aufforderung.
- Keine unrelated files ändern.
- Keine Prompt-Dateien ändern, außer die Aufgabe verlangt es ausdrücklich.

## Python

- Python-Code soll lesbar, typisiert und gut testbar sein.
- Bestehenden Stil respektieren.
- Bei Monitoring-/Policy-Code besonders auf robuste Eingaben, klare Zustände und einfache Tests achten.

## Sicherheit

- Bash-Befehle nur vorschlagen oder ausführen, wenn sie zur Aufgabe passen.
- Riskante Änderungen klar benennen.
