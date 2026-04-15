# AI Monitor

AI System Monitor für Ollama, Docker und GPU Ressourcen.

## Funktionen

- Überwachung von Ollama-Modellen und deren Ausführung auf CPU/GPU
- Überwachung von Docker-Containern (Status und Gesundheit)
- Überwachung von GPU VRAM-Auslastung
- Benachrichtigung über ntfy bei Problemen

## Abhängigkeiten

- Python 3.12+
- Docker
- rocm-smi (für GPU-Statistiken)

## Konfiguration

Umgebungsvairablen:

- `NTFY_URL` - ntfy Server URL (Standard: http://192.168.178.183:7777)
- `NTFY_TOPIC` - ntfy Topic (Standard: ai-monitor)
- `OLLAMA_API_BASE` - Ollama API URL (Standard: http://localhost:11434)
- `ROCM_SMI_PATH` - Pfad zu rocm-smi (Standard: /opt/rocm/bin/rocm-smi)

## Setup

```bash
# Erstelle virtuelle Umgebung
python -m venv .venv
source .venv/bin/activate

# Installiere Abhängigkeiten
pip install -e .
```

## Nutzung

```bash
python monitor.py
```

## Überwachte Container

- ollama
- anythingllm
- open-webui
- qdrant
- searxng
- homepage