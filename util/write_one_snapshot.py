#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def find_project_dir() -> Path:
    current = Path(__file__).resolve()

    for candidate in [current.parent, *current.parents]:
        if (candidate / "util" / "gpu_stats.py").exists():
            return candidate

    raise RuntimeError("Projektverzeichnis mit util/gpu_stats.py nicht gefunden")


PROJECT_DIR = find_project_dir()

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from util.gpu_stats import collect_gpu_stats  # noqa: E402


HISTORY_FILE = PROJECT_DIR / "history" / "monitor_history.jsonl"
OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"


def collect_ollama_models() -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(OLLAMA_PS_URL, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))

        models = payload.get("models", [])
        if isinstance(models, list):
            return models

        return []

    except Exception:
        return []


def build_snapshot() -> dict[str, Any]:
    gpu = collect_gpu_stats()

    snapshot: dict[str, Any] = {
        "timestamp": int(time.time()),
        **gpu,
        "ollama_models": collect_ollama_models(),
    }

    return snapshot


def append_snapshot(snapshot: dict[str, Any]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with HISTORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def main() -> None:
    snapshot = build_snapshot()
    append_snapshot(snapshot)
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()