# ai-monitor – Projektspezifikation v2

## Kontext & Ziel

Monitoring-Daemon für den lokalen AI-Stack auf `ai-debian` (192.168.178.182).
Hardware: ASRock B650M Pro RS, AMD RX 7900 XTX (24 GB VRAM), ROCm 6.x.

**Primärziel:** Erkennen welches Ollama-Modell mit welchen Tools (Aider, Cursor,
OpenWebUI) die besten Ergebnisse liefert – quantifiziert durch Metriken.

**Drei Output-Kanäle:**
1. ntfy-Alerts (192.168.178.183:7777) – kritische Ereignisse
2. REST-API (lokaler HTTP-Server) – für Homepage-Widget und Benchmark-Zugriff
3. Benchmark-Reports (JSON/SQLite) – Modellvergleich persistent

---

## Architektur

```
┌─────────────────────────────────────────────────────────┐
│                    ai-monitor daemon                     │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐  │
│  │ Monitor  │  │Benchmark │  │    REST API          │  │
│  │  Loop    │  │ Runner   │  │  (FastAPI :8765)     │  │
│  │ 15s tick │  │ on-demand│  │  /metrics /benchmark │  │
│  └────┬─────┘  └────┬─────┘  └──────────────────────┘  │
│       │              │                                   │
│  ┌────▼──────────────▼──────────────────────────────┐   │
│  │              Collector Layer                      │   │
│  │  gpu_stats  │  ollama_stats  │  docker_stats     │   │
│  └────┬─────────────────────────────────────────────┘   │
│       │                                                  │
│  ┌────▼──────────────────────────────────────────────┐  │
│  │              Policy Layer (stateful)               │  │
│  │  ThermalPolicy  │  AlertPolicy  │  ActionPolicy   │  │
│  └────┬──────────────────────────────────────────────┘  │
│       │                                                  │
│  ┌────▼──────────────────────────────────────────────┐  │
│  │              Output Layer                          │  │
│  │  NtfyAlerter  │  StateStore  │  BenchmarkStore   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Modul-Übersicht

### `util/gpu_stats.py` ✅ (vorhanden, stabil)
- `get_gpu_stats(gpu_index=0) -> GpuStats`
- Nutzt `amd-smi metric -g 0 -u -p -t -m --json`
- `GpuStats`: edge/hotspot/mem Temp, VRAM used/total/ratio, gpu_use, power_w

### `util/thermal_policy.py` ✅ (vorhanden, stabil)
- Hysterese-Zustandsmaschine: ok / warn / critical / unknown
- Latch nur bei critical, unknown-Spam-Schutz
- Schwellenwerte: warn=85°C, critical=95°C, recover=75°C (edge-basiert)

### `util/ollama_stats.py` ✅ (vorhanden)
Erweiterung nötig:
- `get_loaded_models() -> list[LoadedModel]`
- `LoadedModel`: name, size_gb, processor (GPU%/CPU%), context, vram_gb
- Erkennung CPU-Fallback: `processor` enthält "CPU"-Anteil > 20%

### `util/docker_stats.py` ✅ (vorhanden)
Keine Änderung nötig.

### `util/alert_policy.py` 🆕 (neu)
Zentrale Alert-Logik, getrennt von monitor.py:

```python
@dataclass
class AlertEvent:
    level: str        # warn | critical
    category: str     # thermal | gpu | ollama | docker
    message: str
    once: bool        # True = nur bei Zustandswechsel senden
```

**Die 3 kritischen Alert-Typen:**

```
ALERT_CPU_FALLBACK:
  Trigger: LoadedModel.cpu_pct > 20%
  Bedeutung: Modell nicht vollständig auf GPU
  Aktion: Log + ntfy (once=True, nur bei Wechsel)

ALERT_OLLAMA_HANG:
  Trigger: Ollama-Prozess läuft (docker ps ok) ABER
           GET /api/tags antwortet nicht innerhalb 3s
  Bedeutung: Ollama hängt trotz laufendem Container
  Aktion: Log + ntfy + optional Container-Restart

ALERT_VRAM_LEAK:
  Trigger: gpu.vram_used_gib > 2.0 AND ollama ps gibt keine Modelle zurück
  Bedeutung: VRAM belegt ohne aktives Modell → Leak oder Zombie-Prozess
  Aktion: Log + ntfy (critical)
```

### `util/action_policy.py` 🆕 (neu)
Aktor-Logik – trennt Entscheidung von Ausführung:

```python
class ActionPolicy:
    def evaluate(self, state: SystemState) -> list[Action]:
        # Gibt Liste von Actions zurück, monitor.py führt sie aus
        # Actions: UnloadModel | RestartContainer | SendAlert | NoOp
```

### `util/benchmark_runner.py` 🆕 (neu)

```python
@dataclass
class BenchmarkConfig:
    model: str
    prompts: list[str]          # Standard-Prompt-Suite
    tool: str                   # "aider" | "cursor" | "openwebui" | "direct"
    context_length: int = 4096

@dataclass
class BenchmarkResult:
    model: str
    tool: str
    timestamp: datetime
    tokens_per_second: float
    vram_used_gib: float
    gpu_utilization_pct: float
    time_to_first_token_ms: float
    total_duration_ms: float
    prompt_eval_ms: float
    prompt: str
    response_length_tokens: int
```

Messung über Ollama's `/api/generate` Response-Felder:
- `eval_count / eval_duration` → tokens/s
- GPU-Stats: Polling während Inference via `get_gpu_stats()`

### `api/server.py` 🆕 (neu)
FastAPI, Port 8765:

```
GET  /health                    → {"status": "ok"}
GET  /metrics                   → aktueller SystemState als JSON
GET  /metrics/history?minutes=60 → letzte N Messungen
GET  /benchmark/results         → alle BenchmarkResults
GET  /benchmark/results/{model} → gefiltert nach Modell
POST /benchmark/run             → startet Benchmark-Run (async)
GET  /benchmark/status          → laufender Run-Status
```

### `util/state_store.py` 🆕 (neu)
SQLite-basiert (`~/.ai-monitor/store.db`):
- `metrics` Tabelle: SystemState-Snapshots (15s-Takt, 7 Tage Retention)
- `benchmark_results` Tabelle: alle BenchmarkResults, permanent

### `monitor.py` (Refactoring)
Aktueller Loop bleibt, aber aufgeräumt:

```python
# Klare Trennung:
state = collect_system_state()     # alle Collector
alerts = alert_policy.evaluate(state)   # was soll gemeldet werden?
actions = action_policy.evaluate(state) # was soll getan werden?
execute_actions(actions)           # ntfy, unload, restart
store.save_snapshot(state)         # Persistenz
```

---

## Homepage-Widget

Homepage (port 3002) bekommt ein Custom-Widget das `/metrics` pollt:

```yaml
# homepage config
- AI Stack:
    - GPU:
        widget:
          type: customapi
          url: http://192.168.178.182:8765/metrics
          refreshInterval: 15000
          mappings:
            - field: gpu.temperature_edge
              label: Edge Temp
              format: float
              suffix: "°C"
            - field: gpu.gpu_use
              label: GPU Use
              format: float
              suffix: "%"
            - field: gpu.vram_used_gib
              label: VRAM
              format: float
              suffix: " GiB"
            - field: thermal.state
              label: Thermal
              format: text
```

---

## Benchmark-Prompt-Suite

Drei Kategorien, je 2 Prompts, reproduzierbar:

```python
BENCHMARK_PROMPTS = {
    "coding_simple": [
        "Write a Python function that parses a CSV file and returns a list of dicts.",
        "Fix this bug: def add(a, b): return a - b",
    ],
    "coding_complex": [
        "Refactor this class to use dependency injection: [50-line Python class]",
        "Write a async FastAPI endpoint with SQLite backend and error handling.",
    ],
    "reasoning": [
        "Explain the tradeoffs between MoE and dense transformer architectures.",
        "What are the implications of setting OLLAMA_NUM_GPU=999 on an RX 7900 XTX?",
    ],
}
```

Qualitätsbewertung: zunächst manuell (1-5 Skala), später optional automatisch
via zweitem Modell als Judge.

---

## Tests

```
tests/
├── test_thermal_policy.py     # Hysterese, Latch, unknown-Spam
├── test_alert_policy.py       # alle 3 Alert-Typen, Zustandswechsel
├── test_action_policy.py      # Aktor-Entscheidungen
├── test_gpu_stats.py          # Parser mit Mock-JSON
├── test_benchmark_runner.py   # Mock-Ollama-Responses
└── conftest.py                # Fixtures: mock_amd_smi, mock_ollama
```

Tooling: `pytest` + `pytest-mock`, kein externes Test-Framework.

---

## Konfiguration (.env)

```env
# Ollama
OLLAMA_URL=http://127.0.0.1:11434
AI_MONITOR_POLL_INTERVAL=15

# ntfy
NTFY_URL=http://192.168.178.183:7777
NTFY_TOPIC=ai-monitor
NTFY_TOKEN=

# Thermal Thresholds (edge-basiert, °C)
THERMAL_WARN_C=85
THERMAL_CRITICAL_C=95
THERMAL_RECOVER_C=75

# Alert Policy
ALERT_CPU_FALLBACK_THRESHOLD_PCT=20
ALERT_VRAM_LEAK_THRESHOLD_GIB=2.0
ALERT_OLLAMA_TIMEOUT_S=3

# API
API_PORT=8765
API_HOST=0.0.0.0

# Storage
STORE_PATH=/home/macdet/.ai-monitor/store.db
METRICS_RETENTION_DAYS=7

# GPU
GPU_INDEX=0
```

---

## Projektstruktur (Ziel)

```
ai-monitor/
├── monitor.py                 # Haupt-Loop
├── .env                       # Konfiguration
├── api/
│   └── server.py              # FastAPI REST-API
├── util/
│   ├── gpu_stats.py           ✅
│   ├── thermal_policy.py      ✅
│   ├── ollama_stats.py        (erweitern)
│   ├── docker_stats.py        ✅
│   ├── alerts.py              ✅
│   ├── alert_policy.py        🆕
│   ├── action_policy.py       🆕
│   ├── state_store.py         🆕
│   └── benchmark_runner.py    🆕
└── tests/
    ├── conftest.py
    ├── test_thermal_policy.py
    ├── test_alert_policy.py
    ├── test_action_policy.py
    ├── test_gpu_stats.py
    └── test_benchmark_runner.py
```

---

## Implementierungs-Reihenfolge

```
Phase 1 – Stabilität (diese Woche)
  [x] gpu_stats.py – amd-smi Parser
  [x] thermal_policy.py – Hysterese
  [ ] alert_policy.py – die 3 kritischen Alerts
  [ ] action_policy.py – Aktor-Logik
  [ ] Tests für alle Policy-Module

Phase 2 – API & Widget (nächste Woche)
  [ ] state_store.py – SQLite
  [ ] api/server.py – FastAPI
  [ ] Homepage-Widget konfigurieren
  [ ] monitor.py Refactoring

Phase 3 – Benchmarking
  [ ] benchmark_runner.py
  [ ] Prompt-Suite definieren
  [ ] /benchmark API-Endpoints
  [ ] Ergebnisse in Homepage integrieren
```

---

## Verwendung als opencode/aider Kontext

```bash
# opencode mit dieser Spec starten:
opencode --context ai-monitor-spec.md

# aider:
aider --read ai-monitor-spec.md \
      --read util/gpu_stats.py \
      --read util/thermal_policy.py \
      monitor.py util/alert_policy.py

# Konkreter Einstiegs-Prompt für den Agenten:
# "Implementiere util/alert_policy.py gemäß Spec.
#  Die drei Alert-Typen sind ALERT_CPU_FALLBACK, ALERT_OLLAMA_HANG,
#  ALERT_VRAM_LEAK. Schreibe gleichzeitig tests/test_alert_policy.py.
#  Nutze nur die in gpu_stats.py und ollama_stats.py definierten Typen."
```
