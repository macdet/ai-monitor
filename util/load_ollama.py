#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from typing import Any


OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"


def run_chat_load(model: str, prompt: str, num_predict: int) -> None:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": True,
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict,
        },
    }

    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.time()
    token_chunks = 0

    print(f"Starte Lasttest mit Modell: {model}")
    print()

    with urllib.request.urlopen(request, timeout=600) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()

            if not line:
                continue

            event = json.loads(line)

            message = event.get("message", {})
            content = message.get("content", "")

            if content:
                print(content, end="", flush=True)
                token_chunks += 1

            if event.get("done"):
                break

    duration = time.time() - started

    print()
    print()
    print("== Lasttest fertig ==")
    print(f"Dauer:        {duration:.1f}s")
    print(f"Text-Chunks:  {token_chunks}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Erzeugt kontrollierte Ollama-Last")
    parser.add_argument(
        "--model",
        default="qwen3.6:27b",
        help="Ollama-Modellname",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=1200,
        help="Maximale Antwortlänge",
    )
    parser.add_argument(
        "--prompt",
        default=(
            "Analysiere ausführlich die Architektur eines lokalen AI-Monitoring-Cockpits "
            "für Ollama, ROCm-GPU, Docker-Stats, JSONL-History und Zustandsklassifikation. "
            "Erstelle eine lange technische Review mit Risiken, Optimierungen, Tests, "
            "Betriebszuständen und konkreten Empfehlungen. Antworte auf Deutsch."
        ),
        help="Prompt für den Lasttest",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_chat_load(
        model=args.model,
        prompt=args.prompt,
        num_predict=args.num_predict,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())