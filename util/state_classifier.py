#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any


def as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    if value is None:
        return None

    try:
        return float(str(value).strip())
    except ValueError:
        return None


def get_ollama_model_names(snapshot: dict[str, Any]) -> list[str]:
    models = snapshot.get("ollama_models")

    if not isinstance(models, list):
        return []

    names: list[str] = []

    for model in models:
        if not isinstance(model, dict):
            continue

        name = model.get("name") or model.get("model")
        if isinstance(name, str) and name:
            names.append(name)

    return names


def get_docker_ollama(snapshot: dict[str, Any]) -> dict[str, Any]:
    docker = snapshot.get("docker")

    if not isinstance(docker, dict):
        return {}

    ollama = docker.get("ollama")

    if not isinstance(ollama, dict):
        return {}

    return ollama


def classify_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    gpu_error = snapshot.get("gpu_error")
    gpu_temp = as_float(snapshot.get("gpu_temp"))
    gpu_hotspot = as_float(snapshot.get("gpu_temp_junction"))
    gpu_mem_temp = as_float(snapshot.get("gpu_temp_memory"))
    gpu_use = as_float(snapshot.get("gpu_use"))
    power_w = as_float(snapshot.get("power_w"))
    vram_percent = as_float(snapshot.get("vram_percent"))

    model_names = get_ollama_model_names(snapshot)
    docker_ollama = get_docker_ollama(snapshot)
    docker_error = docker_ollama.get("docker_error") if docker_ollama else None
    docker_cpu = as_float(docker_ollama.get("cpu_percent")) if docker_ollama else None

    has_model = bool(model_names)

    gpu_active = gpu_use is not None and gpu_use >= 10
    power_active = power_w is not None and power_w >= 40
    docker_active = docker_cpu is not None and docker_cpu >= 20

    active = has_model and (gpu_active or power_active or docker_active)

    warm = (
        (gpu_hotspot is not None and gpu_hotspot >= 80)
        or (gpu_mem_temp is not None and gpu_mem_temp >= 80)
    )

    hot_warning = (
        (gpu_hotspot is not None and gpu_hotspot >= 88)
        or (gpu_mem_temp is not None and gpu_mem_temp >= 88)
    )

    critical = (
        (gpu_hotspot is not None and gpu_hotspot >= 95)
        or (gpu_mem_temp is not None and gpu_mem_temp >= 95)
    )

    cooling = (
        has_model
        and not active
        and (
            (gpu_hotspot is not None and gpu_hotspot >= 50)
            or (gpu_mem_temp is not None and gpu_mem_temp >= 55)
            or (gpu_temp is not None and gpu_temp >= 45)
        )
    )

    if gpu_error:
        return {
            "label": "gpu_collector_error",
            "severity": "error",
            "summary": "GPU-Messwerte konnten nicht zuverlässig gelesen werden.",
            "recommendation": "GPU-Collector, rocm-smi und Berechtigungen prüfen.",
        }

    if docker_error:
        return {
            "label": "docker_collector_error",
            "severity": "error",
            "summary": "Docker-Stats für Ollama konnten nicht gelesen werden.",
            "recommendation": "Prüfen, ob der Ollama-Container läuft und Docker erreichbar ist.",
        }

    if critical:
        return {
            "label": "thermal_critical",
            "severity": "critical",
            "summary": "GPU-Temperatur ist kritisch hoch.",
            "recommendation": "Inference stoppen, Modell entladen und Kühlung prüfen.",
        }

    if hot_warning:
        return {
            "label": "thermal_warning",
            "severity": "warning",
            "summary": "GPU-Temperatur ist erhöht.",
            "recommendation": "Temperatur beobachten. Bei weiterem Anstieg Last reduzieren.",
        }

    if active and warm:
        return {
            "label": "active_inference_warm",
            "severity": "busy",
            "summary": "Ollama nutzt die GPU aktiv; die Karte ist warm, aber noch unter Warnschwelle.",
            "recommendation": "Laufende Inferenz beobachten. Kein Eingriff nötig, solange Hotspot und Memory stabil bleiben.",
        }

    if active:
        return {
            "label": "active_inference",
            "severity": "busy",
            "summary": "Ollama nutzt die GPU aktiv.",
            "recommendation": "Laufende Inferenz beobachten.",
        }

    if cooling:
        return {
            "label": "model_loaded_idle_cooling",
            "severity": "ok",
            "summary": "Das Modell liegt im VRAM, die GPU rechnet nicht mehr und kühlt nach Last ab.",
            "recommendation": "Kein Eingriff nötig. Temperatur sollte weiter fallen.",
        }

    if has_model and vram_percent is not None and vram_percent >= 80:
        return {
            "label": "model_loaded_idle",
            "severity": "ok",
            "summary": "Ein Modell liegt im VRAM, aber es läuft aktuell keine Inferenz.",
            "recommendation": "Kein Eingriff nötig. Modell nur entladen, wenn VRAM für anderes gebraucht wird.",
        }

    if not has_model and vram_percent is not None and vram_percent < 20:
        return {
            "label": "idle_empty",
            "severity": "ok",
            "summary": "Kein Modell geladen und GPU weitgehend frei.",
            "recommendation": "System ist bereit.",
        }

    if has_model and gpu_use is not None and gpu_use < 5 and docker_cpu is not None and docker_cpu >= 50:
        return {
            "label": "possible_cpu_fallback",
            "severity": "warning",
            "summary": "Ollama zeigt CPU-Last, aber kaum GPU-Last.",
            "recommendation": "Prüfen, ob das Modell teilweise auf CPU läuft oder ein Prozess hängt.",
        }

    # Handle the new case where gpu_use could be None but docker_cpu is high
    if has_model and gpu_use is None and docker_cpu is not None and docker_cpu >= 50:
        return {
            "label": "possible_gpu_issue",
            "severity": "warning",
            "summary": "Ollama zeigt hohe CPU-Last, aber keine GPU-Last; GPU-Status nicht ermittelbar.",
            "recommendation": "Prüfen, ob GPU-Zugriff funktioniert. Möglicherweise rocm-smi oder Berechtigungenproblem.",
        }

    return {
        "label": "unknown_normal",
        "severity": "ok",
        "summary": "Keine kritischen Auffälligkeiten erkannt.",
        "recommendation": "Weiter beobachten.",
    }

def enrich_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        **snapshot,
        "state": classify_snapshot(snapshot),
    }


if __name__ == "__main__":
    sample = {
        "gpu_temp": 28.0,
        "gpu_temp_junction": 34.0,
        "gpu_temp_memory": 38.0,
        "gpu_use": 0.0,
        "power_w": 8.0,
        "vram_percent": 90.0,
        "gpu_error": None,
        "ollama_models": [{"name": "qwen3.6:27b"}],
        "docker": {
            "ollama": {
                "cpu_percent": 0.0,
                "docker_error": None,
            }
        },
    }

    print(json.dumps(classify_snapshot(sample), indent=2, ensure_ascii=False))