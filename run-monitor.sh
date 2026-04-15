#!/usr/bin/env bash
set -euo pipefail
cd /mnt/ai-bulk/projects/ai-monitor

# Lade Umgebungsvariablen
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Aktiviere virtuelle Umgebung, falls vorhanden
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "Starting AI Monitor..."

# Führe das Monitor-Skript aus
python3 monitor.py

echo "AI Monitor finished."
